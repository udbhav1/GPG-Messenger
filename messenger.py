import datetime
import sys, os, pickle, json, time, logging, threading
import fbchat
from fbchat import Client
from fbchat.models import *
import gnupg

#By Stephen Huan, Udbhav Muthakana
#API for application as well as command line interface (CLI)

#logging.basicConfig(filename='stdout.log', level=logging.DEBUG)

HEADER = "-----BEGIN PGP MESSAGE-----"
SETTINGS = "config.json"
HELPSTR = """GPG-Messenger v1

Usage:
messenger [options] <command>

Commands:
global  Edits the top-level settings
help    Shows this help for commands. """

defaults = {SETTINGS: {"gpg":{"gpgbinary": "gpg", "gnupghome": f"{os.environ['HOME']}/.gnupg/"}, "backend":"facebook", "dev": False},
            "cookie.gpg": {},
           }

def actual_time(ts):
    """ Takes in a UNIX timestamp and spits out actual time as a string without microseconds. """
    dt = datetime.datetime.fromtimestamp(float(ts)/1000.0)
    dt = dt.replace(microsecond=0)
    return str(dt)

def format_message(time, msg, author="You "):
    return f"{actual_time(time)} {str(author.split()[0])}: {msg}"

def decrypt_message(msg):
    return str(gpg.decrypt(msg)) if msg.split("\n")[0].strip() == HEADER else msg

def tty_input(prompt, default):
    ans = input(prompt + f"? Default {default}: ").strip()
    return ans if len(ans) != 0 else default

def setup_global_settings(**kwargs):
    prompts = {"gpgbinary": "What is the name/path of your gpg binary", "gnupghome": "Where are your keys stored"}
    for param, default in defaults[SETTINGS]["gpg"].items():
        if param not in kwargs:
            kwargs[param] = tty_input(prompts[param], default)
    config = defaults[SETTINGS].copy()
    config["gpg"] = kwargs
    with open(SETTINGS, "w") as f:
        json.dump(config, f)

def setup_settings(chat_backend):
    params = {"username": "What is your username",
               "pass": "What is your password / path to file with your password",
               "2FA": "Is two factor authentication active (y/n)"}
    data = {param: input(params[param] + "? ").strip() for param in params}
    data["2FA"] = "y" in data['2FA'].lower()
    with open(f"accounts/{chat_backend}/{SETTINGS}", "w") as f:
        json.dump(data, f)

def load_file(fname, func):
    try:
        with open(fname) as f:
            return func(f)
    except FileNotFoundError:
        return defaults[fname]

def get_pass(fname):
    try:
        open(fname)
    except FileNotFoundError:
        return fname

    return str(gpg.decrypt_file(open(fname, "rb"))).split("\n")[0]

def make_client(tfa=None):
    if config["2FA"] and tfa is not None: Client.on2FACode = tfa
    client = GPGClient(config["username"], get_pass(config["pass"]), session_cookies=cookies)
    with open("cookie.gpg", "w") as f:
        f.write(str(gpg.encrypt(pickle.dumps(client.getSession()), keyid)))
    return client

def make_thread(f):
    thread = threading.Thread(target=f)
    thread.daemon = True
    thread.start()

class GPGClient(Client):

    def init(self): self.recieved, self.message, self.thread = False, None, 0

    def send_message(self, msg, uid, fingerprint):
        """ Sends an message over the chat backend, attempts to encrypt so that both
        recipient and author can decrypt, but only encrypts if you have their public key

        msg [str]: message to be sent
        uid [int]: facebook id of the user to send to
        fingerprint [str]: gpg fingerprint of the recipient (None if does not exit [DNE])

        returns formatted str of original msg
        """

        encrypted = str(gpg.encrypt(msg, [fingerprint, keyid])) if fingerprint != None else msg
        self.send(Message(text=encrypted), thread_id=uid, thread_type=ThreadType.USER)
        return format_message(time.time(), msg)

    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        """ Recives a message from a given user
        Uses instance variables to return value
        """

        self.markAsDelivered(thread_id, message_object.uid)
        self.markAsRead(thread_id)

        self.recieved, self.message, self.thread = True, message_object, thread_id

config = load_file(SETTINGS, lambda x: json.load(x))
dev = config["dev"]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        com = sys.argv[1]
        if "help" in com:
            print(HELPSTR)
        elif com == "global":
            setup_global_settings()
        elif com in ["facebook"]:
            setup_settings(com)
    if not dev:
        sys.exit()

gpg = gnupg.GPG(**config["gpg"])
keyid = gpg.list_keys(True)[0]['keyid']

config = load_file(f"accounts/{config['backend']}/{SETTINGS}", lambda x: json.load(x))
cookies = load_file("cookie.gpg", lambda x: pickle.loads(gpg.decrypt(x.read()).data))

client = make_client()
client.init()

make_thread(f=lambda: client.listen())
