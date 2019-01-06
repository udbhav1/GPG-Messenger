import tkinter
from tkinter import messagebox
import fbchat
import threading
from fbchat import Client
from fbchat.models import *
import messenger
import datetime
import time

#By Udbhav Muthakana, Stephen Huan
#GUI messenging app

client = messenger.client
recipient = None
recipientid = None
recipientkeyid = None
header = "-----BEGIN PGP MESSAGE-----"
defaultMessageText = "Type a message"
defaultRecipientText = "Update Recipient"

def actualTime(ts):
    """takes in a unix timestamp and spits out actual time as a string without microseconds"""
    dt = datetime.datetime.fromtimestamp(float(ts)/1000.0)
    dt = dt.replace(microsecond=0)
    return str(dt)

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
    # update recipients list
    if not (recipient in recipients_list.get(0, "end")):
        recipients_list.insert(tkinter.END, recipient)
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
            actualmessage = actualTime(i.timestamp) + " " + str(recipient.split(" ")[0]) + ": " + str(actualmessage)
            msg_list.insert(tkinter.END, actualmessage)
            msg_list.insert(tkinter.END, "")
            # scroll to bottom
            msg_list.yview(tkinter.END)
        else:
            msg_list.insert(tkinter.END, actualTime(i.timestamp) + " You: " + actualmessage)
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
        encrypted = str(messenger.gpg.encrypt(tosend, [recipientkeyid, messenger.keyid]))
    else:
        encrypted = tosend
    client.send(Message(text=encrypted), thread_id=recipientid, thread_type=ThreadType.USER)

    msg_list.insert(tkinter.END, actualTime(time.time()) + " You: " + tosend)
    msg_list.insert(tkinter.END, "")
    msg_list.yview(tkinter.END)
    return 'break'

def receive():
    """ Threaded function to continuously receive messages, but only if a recipient is set. """
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
                        actualmessage = actualTime(msg.timestamp) + " " + str(recipient.split(" ")[0]) + ": " + str(actualmessage)
                        msg_list.insert(tkinter.END, actualmessage)
                        msg_list.insert(tkinter.END, "")
                        msg_list.yview(tkinter.END)
                    lastTime = msg.timestamp
                except OSError:  # Possibly client has left the chat.
                    break

def listboxUpdateRecipient(event=None):
    """ Triggered when an item is selected in the listbox of recipients """
    if len(recipients_list.curselection()) != 0:
        if recipients_list.get(recipients_list.curselection()[0]) != recipient:
            # roundabout way to use updateRecipient() rather than making a new func
            recipient_field.delete("1.0", tkinter.END)
            recipient_field.insert(tkinter.END, recipients_list.get(recipients_list.curselection()[0]))
            updateRecipient()
            recipient_field.delete("1.0", tkinter.END)
            recipient_field.insert("1.0", defaultRecipientText)


def updateDefaultMessageText(event=None):
    """ Manages the default text inside the message text box """
    current = entry_field.get("1.0", tkinter.END)
    if current == defaultMessageText + "\n":
        entry_field.delete("1.0", tkinter.END)
    elif current == "\n":
        entry_field.insert("1.0", defaultMessageText)

def updateDefaultRecipientText(event=None):
    """ Manages the default text inside the update recipient text box """
    current = recipient_field.get("1.0", tkinter.END)
    if current == defaultRecipientText + "\n":
        recipient_field.delete("1.0", tkinter.END)
    elif current == "\n":
        recipient_field.insert("1.0", defaultRecipientText)

master = tkinter.Tk()
master.title("GPG Messenger Client")

# shows who you're currently chatting with
status_bar = tkinter.Label(master, text="Chatting with: No one :(")
status_bar.grid(row=0,column=2)

recipients_list = tkinter.Listbox(master, height=30, width=30)
recipients_list.grid(row=1,column=0)
recipients_list.bind('<FocusOut>', lambda e: recipients_list.selection_clear(0, tkinter.END))
recipients_list.bind('<<ListboxSelect>>', listboxUpdateRecipient)

msg_frame = tkinter.Frame(master)
msg_frame.grid(row=1,column=1, columnspan=4)

scrollbar = tkinter.Scrollbar(msg_frame)
msg_list = tkinter.Listbox(msg_frame, height=30, width=100, yscrollcommand=scrollbar.set)
scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
msg_list.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

# messages entered here
entry_field = tkinter.Text(master, wrap=tkinter.WORD, height=2, width=128, borderwidth=2, relief=tkinter.RIDGE)
entry_field.insert(tkinter.END, defaultMessageText)
entry_field.grid(row=2,column=1, columnspan=4)
entry_field.bind("<Return>", send)
entry_field.bind("<FocusIn>", updateDefaultMessageText)
entry_field.bind("<FocusOut>", updateDefaultMessageText)


# to change recipient
recipient_field = tkinter.Text(master, width=25, height=1, borderwidth=2, relief=tkinter.RIDGE)
recipient_field.insert(tkinter.END, defaultRecipientText)
recipient_field.grid(row=2,column=0)
recipient_field.bind("<Return>", updateRecipient)
recipient_field.bind("<FocusIn>", updateDefaultRecipientText)
recipient_field.bind("<FocusOut>", updateDefaultRecipientText)


receive_thread = threading.Thread(target=receive)
receive_thread.daemon = True
receive_thread.start()


tkinter.mainloop()
