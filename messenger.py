import json, time, sys, logging
import fbchat
from fbchat import Client
from fbchat.models import *
import gnupg
#https://fbchat.readthedocs.io/en/master/
#https://pythonhosted.org/python-gnupg/
logging.basicConfig(filename='stdout.log',level=logging.DEBUG)

def get_pass(fname):
     return str(gpg.decrypt(open(fname).read())).split()[0]

def load_file(fname, func):
    try:
        with open(fname) as f:
            return func(f)
    except FileNotFoundError:
        return {}

def make_client(tfa=input("Please enter your 2FA code --> ")):
    Client.on2FACode = lambda x: tfa

    client = Client(config["username"], get_pass(config["passpath"]))

    return client

config = load_file("config.json", lambda x: json.load(x))

gpg = gnupg.GPG(homedir=config["gpgpath"], use_agent=True)
keyid = gpg.list_keys(True)[0]['keyid']

client = make_client()
