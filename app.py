import tkinter
from tkinter import messagebox
import fbchat
import threading
from fbchat import Client
from fbchat.models import *
import messenger

#By Udbhav Muthakana, Stephen Huan
#GUI messenging app

client = messenger.client
recipient = None
recipientid = None
recipientkeyid = None
header = "-----BEGIN PGP MESSAGE-----"

def error(title, text):
    """ Shows alert box. """
    messagebox.showerror(title, text)

def updateRecipient(event=None):
    """ Changes who to chat with and checks for a public key """
    global recipient
    global recipientid
    global recipientkeyid
    global status
    entry = recipient_field.get("1.0", tkinter.END).strip()
    recipient_field.delete("1.0", tkinter.END)
    recipientkeyid = None
    try:
        users = client.searchForUsers(entry)
    except FBchatException:
        error("Error", "User not found \n\nTry again")
        return
    recipient = entry
    # update status bar
    status_bar['text'] = "Chatting with: " + recipient
    recipientid = users[0].uid
    # try to find their public key
    for key in messenger.gpg.list_keys():
        for uid in key["uids"]:
            if recipient.lower() in uid.lower():
                recipientkeyid = key["keyid"]
    # warn user if key not found
    if recipientkeyid == None:
        error("Warning", "Recipient public key not found \n\nMessages will not be encrypted")
    # clear listbox before updating
    msg_list.delete(0, tkinter.END)
    updateLast(50)

def updateLast(n):
    """
    Gets a bit of history instead of just an empty box.
    n [int]: takes in how many messages to update
    """
    try:
        prev = client.fetchThreadMessages(thread_id=recipientid, limit=n)[::-1]
    except FBchatException:
        return
    # decrypt and format previous messages
    for i in prev:
        # only decrypt if message is, in fact, encrypted
        actualmessage = (str(messenger.gpg.decrypt(i.text)) if i.text.split("\n")[0].strip() == header else i.text)
        if i.author == recipientid:
            actualmessage = str(recipient.split(" ")[0]) + ": " + str(actualmessage)
            msg_list.insert(tkinter.END, actualmessage)
            msg_list.insert(tkinter.END, "")
            # scroll to bottom
            msg_list.yview(tkinter.END)
        else:
            msg_list.insert(tkinter.END, "You: " + actualmessage)
            msg_list.insert(tkinter.END, "")
            msg_list.yview(tkinter.END)

def send(event=None):
    """ Attempts to encrypt and send the message in the entry_field text box """
    tosend = entry_field.get("1.0", tkinter.END)
    if tosend == "#QUIT":
        master.quit()
    entry_field.delete("1.0", tkinter.END)

    # encrypt so that both the recipient and you can decrypt, but only encrypt if you have their public key
    if recipientkeyid != None:
        print(recipientkeyid, messenger.keyid)
        encrypted = str(messenger.gpg.encrypt(tosend, [recipientkeyid, messenger.keyid]))
        print(encrypted)
    else:
        encrypted = tosend
    client.send(Message(text=encrypted), thread_id=recipientid, thread_type=ThreadType.USER)

    msg_list.insert(tkinter.END, "You: " + tosend)
    msg_list.insert(tkinter.END, "")
    msg_list.yview(tkinter.END)
    return 'break'

def receive():
    """ Threaded function to continuously receive mesages, but only if a recipient is set. """
    if recipientid != None:
        last = client.fetchThreadMessages(thread_id=recipientid, limit=1)[0]
        lastTime = last.timestamp
        lastAuthor = last.author
        header = "-----BEGIN PGP MESSAGE-----"
        while True:
            if recipientid != None:
                try:
                    msg = client.fetchThreadMessages(thread_id=recipientid, limit=1)[0]
                    if msg.timestamp != lastTime and msg.author == recipientid:
                        actualmessage = (str(messenger.gpg.decrypt(msg.text)) if msg.text.split("\n")[0].strip() == header else msg.text)
                        actualmessage = str(recipient.split(" ")[0]) + ": " + str(actualmessage)
                        msg_list.insert(tkinter.END, actualmessage)
                        msg_list.insert(tkinter.END, "")
                        msg_list.yview(tkinter.END)
                    lastTime = msg.timestamp
                except OSError:  # Possibly client has left the chat.
                    break


master = tkinter.Tk()
master.title("GPG Messenger Client")

# shows who you're currently chatting with
status_bar = tkinter.Label(master, text="Chatting with: No one :(")
status_bar.pack()

# frame for message box and scrollbar
messages_frame = tkinter.Frame(master)
messages_frame.pack(expand=True)

scrollbar = tkinter.Scrollbar(messages_frame)  # To navigate through past messages.

msg_list = tkinter.Listbox(messages_frame, height=30, width=100, yscrollcommand=scrollbar.set)
scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
msg_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

# messages entered here
entry_field = tkinter.Text(master, wrap=tkinter.WORD, width=50, height=2, borderwidth=2, relief=tkinter.RIDGE)
entry_field.bind("<Return>", send)
entry_field.pack()
send_button = tkinter.Button(master, text="Send", command=send)
send_button.pack()

# to change recipient
recipient_field = tkinter.Text(master, width=25, height=1, borderwidth=2, relief=tkinter.RIDGE)
recipient_field.bind("<Return>", updateRecipient)
recipient_field.pack()
recipient_field_button = tkinter.Button(master, text="Update Recipient", command=updateRecipient)
recipient_field_button.pack()

receive_thread = threading.Thread(target=receive)
receive_thread.start()


tkinter.mainloop()
