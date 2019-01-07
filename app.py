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

def error(title, text):
    """ Shows alert box. """
    messagebox.showerror(title, text)

def parse_fb_message(msg):
    update_messages(messenger.format_message(msg.timestamp, messenger.decrypt_message(msg.text), recipient if msg.author == recipientid else "You "))
    return msg

def update_messages(text):
    msg_list.insert(END, text)
    msg_list.insert(END, "")
    # scroll to bottom
    msg_list.yview(END)

def update_recipient(event=None):
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
        error("Error", "Facebook chat exception")
    except IndexError:
        error("Error", "User not found \n\nTry again")
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
        if recipientkeyid is None:
            error("Warning", "Recipient public key not found \n\nMessages will not be encrypted")
        # clear listbox before updating
        msg_list.delete(0, END)
        update_last()

def update_last(n=HISTORY):
    """
    Gets a bit of history instead of just an empty box.
    n [int]: takes in how many messages to update
    """
    try: prev = client.fetchThreadMessages(thread_id=recipientid, limit=n)[::-1]
    except messenger.FBchatException: return []
    return list(map(parse_fb_message, prev))

def send(event=None):
    """ Attempts to encrypt and send the message in the entry_field text box """
    tosend = entry_field.get("1.0", END)
    if tosend == "#QUIT\n":
        master.quit()
        return

    entry_field.delete("1.0", END)

    client.send_message(tosend, recipientid, recipientkeyid)

def receive():
    """ Threaded function to continuously receive messages. """
    while True:
        time.sleep(DELAY)
        if client.recieved:
            client.recieved = False
            if client.thread == recipientid:
                parse_fb_message(client.message)

def listbox_update_recipient(event=None):
    """ Triggered when an item is selected in the listbox of recipients """
    if len(recipients_list.curselection()) != 0:
        if recipients_list.get(recipients_list.curselection()[0]) != recipient:
            # roundabout way to use update_recipient() rather than making a new func
            recipient_field.delete("1.0", END)
            recipient_field.insert(END, recipients_list.get(recipients_list.curselection()[0]))
            update_recipient()
            recipient_field.delete("1.0", END)

def update_default_text(field, text, event):
    """ Manages the default text a box. """
    current = field.get("1.0", END)
    if current == text + "\n":
        field.delete("1.0", END)
    elif current == "\n":
        field.insert("1.0", text)

def create_field(f, text, tkparam, gridparam):
    field = tkinter.Text(master, **tkparam, borderwidth=2, relief=tkinter.RIDGE)
    field.insert(END, text)
    field.grid(**gridparam)
    field.bind("<Return>", f)
    f = lambda event=None: update_default_text(field, text, event)
    field.bind("<FocusIn>", f)
    field.bind("<FocusOut>", f)
    return field

master = tkinter.Tk()
master.title("GPG Messenger Client")

# shows who you're currently chatting with
status_bar = tkinter.Label(master, text="Chatting with: No one :(")
status_bar.grid(row=0,column=2)

recipients_list = tkinter.Listbox(master, height=30, width=30)
recipients_list.grid(row=1,column=0)
recipients_list.bind('<FocusOut>', lambda e: recipients_list.selection_clear(0, END))
recipients_list.bind('<<ListboxSelect>>', listbox_update_recipient)

msg_frame = tkinter.Frame(master)
msg_frame.grid(row=1,column=1, columnspan=4)

scrollbar = tkinter.Scrollbar(msg_frame)
msg_list = tkinter.Listbox(msg_frame, height=30, width=100, yscrollcommand=scrollbar.set)
scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
msg_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

entry_field = create_field(send, "Type a message", {"wrap": tkinter.WORD, "height": 2, "width": 128}, {"row":2, "column":1, "columnspan": 4})
recipient_field = create_field(update_recipient, "Update Recipient", {"height": 1, "width": 25}, {"row":2, "column":0})

messenger.make_thread(receive)
tkinter.mainloop()

if not messenger.dev:
    client.logout()
