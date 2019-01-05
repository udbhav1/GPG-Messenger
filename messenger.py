import sys, os, pickle, json, logging
import fbchat
from fbchat import Client
from fbchat.models import *
import gnupg

#By Stephen Huan, Udbhav Muthakana
#API for application as well as command line interface (CLI)

#logging.basicConfig(filename='stdout.log', level=logging.DEBUG)

SETTINGS = "config.json"
HELPSTR = """GPG-Messenger v1

Usage:
messenger [options] <command>

Commands:
global  Edits the top-level settings
help    Shows this help for commands. """

defaults = {SETTINGS: {"gpg":{"gpgbinary": "gpg", "gnupghome": f"{os.environ['HOME']}/.gnupg/"}, "backend":"facebook"},
            "cookie.gpg": {},
           }

def tty_input(prompt, default):
    ans = input(prompt + f"? Default {default}: ").strip()
    return ans if len(ans) != 0 else default

def setup_global_settings(**kwargs):
    prompts = {"binary": "What is the name/path of your gpg binary", "homedir": "Where are your keys stored"}
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
    if config["2FA"]:
        if tfa is None: tfa = input("Please enter your 2FA code --> ")
        Client.on2FACode = lambda x: tfa
    client = Client(config["username"], get_pass(config["pass"]), session_cookies=cookies)
    with open("cookie.gpg", "w") as f:
        f.write(str(gpg.encrypt(pickle.dumps(client.getSession()), keyid)))
    return client

class GPGClient():

    def __init__(self):
        self.client = make_client()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        com = sys.argv[1]
        if "help" in com:
            print(HELPSTR)
        elif com == "global":
            setup_global_settings()
        elif com in ["facebook"]:
            setup_settings(com)
    #sys.exit()

config = load_file(SETTINGS, lambda x: json.load(x))
gpg = gnupg.GPG(**config["gpg"])
keyid = gpg.list_keys(True)[0]['keyid']

config = load_file(f"accounts/{config['backend']}/{SETTINGS}", lambda x: json.load(x))
cookies = load_file("cookie.gpg", lambda x: pickle.loads(gpg.decrypt(x.read()).data))
client = make_client()
