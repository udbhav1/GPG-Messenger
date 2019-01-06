import tkinter, threading, time
from tkinter import messagebox
import messenger

#By Udbhav Muthakana, Stephen Huan
#GUI messenging app

HISTORY = 50
DELAY = 0.1
END = tkinter.END

client = messenger.client
recipient = recipientid = recipientkeyid = None
defaultMessageText = "Type a message"
defaultRecipientText = "Update Recipient"

def error(title, text):
    """ Shows alert box. """
    messagebox.showerror(title, text)

def parse_fb_message(msg):
    update_messages(messenger.format_message(msg.timestamp, messenger.decrypt_message(msg.text), recipient if msg.author == recipientid else "You "))

def update_messages(text):
    msg_list.insert(END, text)
    msg_list.insert(END, "")
    # scroll to bottom
    msg_list.yview(END)

def updateRecipient(event=None):
    """ Changes who to chat with and checks for a public key. """
    global recipient
    global recipientid
    global recipientkeyid
    global status
    entry = recipient_field.get("1.0", END).strip()
    recipient_field.delete("1.0", END)
    recipientkeyid = None
    try:
        users = client.searchForUsers(entry)
        recipientid = users[0].uid
    except messenger.FBchatException:
        print("Facebook error: Try again later")
    except IndexError:
        print("Error: User not found")
    else:
        recipient = entry
        # update status bar
        status_bar['text'] = f"Chatting with: {recipient}"
        # update recipients list
        if not (recipient in recipients_list.get(0, "end")):
            recipients_list.insert(END, recipient)
        # try to find their public key
        for key in messenger.gpg.list_keys():
            for uid in key["uids"]:
                if recipient.lower() in uid.lower():
                    recipientkeyid = key["keyid"]
        # warn user if key not found
        if recipientkeyid == None:
            error("Warning", "Recipient public key not found \n\nMessages will not be encrypted")
        # clear listbox before updating
        msg_list.delete(0, END)
        updateLast()

def updateLast(n=HISTORY):
    """
    Gets a bit of history instead of just an empty box.
    n [int]: takes in how many messages to update
    """
    try:
        prev = client.fetchThreadMessages(thread_id=recipientid, limit=n)[::-1]
    except messenger.FBchatException:
        return
    for i in prev: parse_fb_message(i)

def send(event=None):
    """ Attempts to encrypt and send the message in the entry_field text box """
    tosend = entry_field.get("1.0", END)
    if tosend == "#QUIT":
        master.quit()
    entry_field.delete("1.0", END)

    update_messages(client.send_message(tosend, recipientid, recipientkeyid))
    return 'break'

def receive():
    """ Threaded function to continuously receive messages. """
    while True:
        time.sleep(DELAY)
        if client.recieved:
            parse_fb_message(client.message)
            client.recieved = False

def listboxUpdateRecipient(event=None):
    """ Triggered when an item is selected in the listbox of recipients """
    if len(recipients_list.curselection()) != 0:
        if recipients_list.get(recipients_list.curselection()[0]) != recipient:
            # roundabout way to use updateRecipient() rather than making a new func
            recipient_field.delete("1.0", END)
            recipient_field.insert(END, recipients_list.get(recipients_list.curselection()[0]))
            updateRecipient()
            recipient_field.delete("1.0", END)
            recipient_field.insert("1.0", defaultRecipientText)

def updateDefaultText(field, text, event):
    """ Manages the default text a box. """
    current = field.get("1.0", END)
    if current == text + "\n":
        field.delete("1.0", END)
    elif current == "\n":
        field.insert("1.0", text)

updateDefaultMessageText = lambda event=None: updateDefaultText(entry_field, defaultMessageText, event)
updateDefaultRecipientText = lambda event=None: updateDefaultText(recipient_field, defaultRecipientText, event)

master = tkinter.Tk()
master.title("GPG Messenger Client")

# shows who you're currently chatting with
status_bar = tkinter.Label(master, text="Chatting with: No one :(")
status_bar.grid(row=0,column=2)

recipients_list = tkinter.Listbox(master, height=30, width=30)
recipients_list.grid(row=1,column=0)
recipients_list.bind('<FocusOut>', lambda e: recipients_list.selection_clear(0, END))
recipients_list.bind('<<ListboxSelect>>', listboxUpdateRecipient)

msg_frame = tkinter.Frame(master)
msg_frame.grid(row=1,column=1, columnspan=4)

scrollbar = tkinter.Scrollbar(msg_frame)
msg_list = tkinter.Listbox(msg_frame, height=30, width=100, yscrollcommand=scrollbar.set)
scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
msg_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

# messages entered here
entry_field = tkinter.Text(master, wrap=tkinter.WORD, height=2, width=128, borderwidth=2, relief=tkinter.RIDGE)
entry_field.insert(END, defaultMessageText)
entry_field.grid(row=2,column=1, columnspan=4)
entry_field.bind("<Return>", send)
entry_field.bind("<FocusIn>", updateDefaultMessageText)
entry_field.bind("<FocusOut>", updateDefaultMessageText)

# to change recipient
recipient_field = tkinter.Text(master, width=25, height=1, borderwidth=2, relief=tkinter.RIDGE)
recipient_field.insert(END, defaultRecipientText)
recipient_field.grid(row=2,column=0)
recipient_field.bind("<Return>", updateRecipient)
recipient_field.bind("<FocusIn>", updateDefaultRecipientText)
recipient_field.bind("<FocusOut>", updateDefaultRecipientText)

receive_thread = threading.Thread(target=receive)
receive_thread.daemon = True
receive_thread.start()

tkinter.mainloop()

if not messenger.dev:
    client.logout()
