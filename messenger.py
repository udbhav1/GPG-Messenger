import datetime
import sys, os, pickle, json, time, logging, threading, argparse
import fbchat
from fbchat.models import *
import requests
import gnupg
from PIL import Image
import glob

#By Stephen Huan, Udbhav Muthakana
#API for application as well as command line interface (CLI)

#logging.basicConfig(filename='stdout.log', level=logging.DEBUG)

HEADER = "-----BEGIN PGP MESSAGE-----"
SETTINGS = "config.json"
IMAGES = "images/"
USER, GROUP = ThreadType.USER, ThreadType.GROUP

def get_path(chat_backend: str) -> str:
    """ Returns the path to a config file. """
    return SETTINGS if chat_backend == "global" else f"accounts/{chat_backend}/{SETTINGS}"

defaults = {get_path("global"): {"gpg": {"gpgbinary": "gpg", "gnupghome": f"{os.environ['HOME']}/.gnupg/"}, "backend": "facebook", "dev": False, "images": 10},
            get_path("facebook"): {"username": "", "pass": "", "2FA": False, "history": 25, "delay": 0.1, "instant": False},
            "cookie.gpg": {},
            "keys.pickle": {}
           }

def load_file(fname: str, func, mode: str="r"):
    """ Attempts to open a file, defaulting to the hardcoded default if file does not exist. """
    try:
        with open(fname, mode) as f:
            return func(f)
    except FileNotFoundError:
        return defaults[fname]

def tty_input(prompt: str, default):
    """ Prompts the user, using the default if the response is empty. """
    if isinstance(default, bool):
        return "y" in input(prompt + "? (y/n) ").strip().lower()

    suffix = f"Default {default}: " if default else ""
    ans = input(prompt + "? " + suffix).strip()
    return type(default)(ans) if len(ans) != 0 else default

def flatten_json(d, new={}):
    """ Flattens a nested dictionary. """
    for k, v in d.items():
        if isinstance(v, dict):
            flatten_json(v, new)
        else:
            new[k] = v
    return new

def round_json(d, new, rtn={}):
    """ Replaces values in a nested dictionary from a flattened dictionary. """
    for k, v in d.items():
        if isinstance(v, dict):
            rtn[k] = round_json(v, new, {})
        else:
            rtn[k] = new[k]
    return rtn

def setup_settings(chat_backend: str) -> None:
    """ Sets up the settings which apply to every account or those specific to a certain messenging platform. """

    path = get_path(chat_backend)
    prompts = {"global": {"gpgbinary": "What is the path to your gpg binary",
                          "gnupghome": "Where are your keys stored",
                          "backend": "Which messenging platform to use",
                          "dev": "Development mode",
                          "images": "Maximum number of images stored in the image cache"},
               "facebook": {"username": "What is your username",
                            "pass": "What is your password / path to file with your password",
                            "2FA": "Is two factor authentication active",
                            "history": "How many messages to get",
                            "delay": "Time between refresh",
                            "instant": "Whether to instantly update the GUI (smoother but doesn't correspond with real-time message sending)"
                            }
              }

    data = round_json(defaults[path], {param: tty_input(prompts[chat_backend][param], default) for param, default in flatten_json(defaults[path]).items()})

    with open(path, "w") as f:
        json.dump(data, f)

def get_pass(fname: str) -> str:
    """ Returns the password from a file. """
    try:
        open(fname)
    except FileNotFoundError:
        return fname

    return str(gpg.decrypt_file(open(fname, "rb"))).split("\n")[0]

def prompt_user(keys):
    """ Asks the user which key they would prefer if there is a conflict. """
    prompt = "There are multiple keys associated with the same user. \n\t"
    prompt += "\n\t".join(f"({i + 1}): {pretty_key(key)}" for i, key in enumerate(keys)) + '\nYour selection: '
    return keys[int(input(prompt)) - 1]

def pretty_key(key: str) -> str:
    """ Returns a formatted version of a GPG key. """
    return f"{key['uids'][0]} ({key['keyid']})"

def get_key(name: str) -> str:
    """ Takes in a string as a name and attemps to return the corresponding GPG fingerprint.
        Returns None if no key is found. """
    if name in gpg_keys:
        return gpg_keys[name]

    possible = []
    for key in gpg.list_keys():
        for uid in key["uids"]:
            if name.lower() in uid.lower():
                possible.append(key)
                break
    if len(possible) > 0:
        key = (prompt_user(possible) if len(possible) > 1 else possible[0])["keyid"]
        gpg_keys[name] = key
        with open("keys.pickle", "wb") as f:
            pickle.dump(gpg_keys, f)
        return key

def is_encrypted(s: str) -> bool:
    """ Returns whether a string is encrypted or not. """
    return s.split("\n")[0].strip() == HEADER

def decrypt_message(msg: str) -> str:
    """ Decrypts a GPG encrypted message if it begins with the valid header. """
    return str(gpg.decrypt(msg)) if msg.split("\n")[0].strip() == HEADER else msg

def write_img_disk(message_object: Message) -> list:
    """ Returns a list of (size, path) tuples for each image attached to the message. """
    imgs = [((0, 0), "")]
    for file in message_object.attachments:
        if isinstance(file, ImageAttachment):
            img_data = requests.get(client.fetchImageUrl(file.uid)).content
            path = f"{IMAGES}|{message_object.uid}|{file.preview_width}x{file.preview_height}|{time.time()}|.{file.original_extension}"
            with open(path, 'wb') as f:
                f.write(img_data)
            imgs.append(((file.preview_width, file.preview_height), path))
    return imgs

def remove_images() -> None:
    """ Removes enough images to make the size of the cache k. """
    imgs = sorted([(img.split("|")[3], img) for img in os.listdir(IMAGES)])
    for i in range(len(imgs) - global_config["images"]):
        os.remove(IMAGES + imgs[i][1])

def get_image(uid: str) -> tuple:
    """ Returns the (size, path) tuple of an image, if it exists. """
    for img in os.listdir(IMAGES):
        if uid in img:
            width, height = img.split("|")[2].split("x")
            return ((int(width), int(height)), IMAGES + img)
    return ((0, 0), "")

def scale_image(size, xmax):
    x, y = size
    c = min(xmax/x, 1)
    return (c*x, c*y)

def actual_time(ts) -> str:
    """ Takes in a UNIX timestamp and spits out actual time as a string without microseconds. """
    dt = datetime.datetime.fromtimestamp(float(ts)/1000.0)
    dt = dt.replace(microsecond=0)
    return str(dt)

def format_message(time, msg, author="You ") -> str:
    """ Formats a message with time and author """
    return f"{actual_time(time)} {str(author.split()[0])}: {msg}"

def make_client(tfa=None) -> fbchat.Client:
    """ Makes the client, as well as updates stored cookie. """
    if config["2FA"] and tfa is not None: fbchat.Client.on2FACode = tfa
    client = GPGClient(config["username"], get_pass(config["pass"]), session_cookies=cookies)
    with open("cookie.gpg", "w") as f:
        f.write(str(gpg.encrypt(pickle.dumps(client.getSession()), keyid)))
    return client

def make_thread(f) -> None:
    """ Makes a thread. """
    thread = threading.Thread(target=f)
    thread.daemon = True
    thread.start()

def get_sticker(token: str):
    """ Searches to see if a piece of text represents a valid sticker. """
    for pack in os.listdir("stickers/"):
        path = f"stickers/{pack}"
        if os.path.isdir(path):
            for sticker in os.listdir(path):
                if sticker.split('.')[1] == "png" and f"{pack}:{sticker.split('.')[0]}" in token:
                    size = token.split(":")[-1] if len(token.split(":")) == 3 else "medium"
                    return (f"{path}/{sticker}", size)

def parse_sticker(text: str) -> tuple:
    """ Determines whether or not to render a sticker. """
    rtn, new = [], []

    for token in text.split():
        sticker = get_sticker(token)
        if sticker is not None:
            rtn.append(sticker)
        else:
            new.append(token)

    return rtn, " ".join(new)

def gen_sticker(path: str, size: str) -> None:
    """ Makes a temp file with the right size and serves that temp file. """
    sizes = {"small": 100, "medium": 150, "large": 200}
    size = sizes[size] if size in sizes else int(size)

    im = Image.open(path)
    im.thumbnail((size, size))

    i = 0
    while os.path.exists(f"stickers/cache/temp{i}.png"):
        i += 1

    im.save(f"stickers/cache/temp{i}.png", "PNG")

def show_stickers(pack: str):
    stickers = glob.glob(f"stickers/{pack}/*.png")
    print(f"Number of stickers in {pack}: {len(stickers)}")
    for sticker in stickers:
        im = Image.open(sticker)
        w, h = im.size
        if w != h:
            print("Nonsquare sticker:", sticker)

def get_cache() -> list:
    """ Returns all the file paths from the cache. """
    return glob.glob("stickers/cache/*.png")

def clear_cache() -> None:
    """ Removes all files from the cache """
    for sticker in get_cache():
        os.remove(sticker)

class GPGClient(fbchat.Client):

    """ Subclass of fbchat.Client. """

    def init(self): self.received, self.message, self.thread, self.author_uid, self.new_message, self.new_message_thread = False, None, 0, 0, False, 0

    def send_message(self, msg: str, uid: int, chat_type: str, fingerprints: list) -> str:
        """ Sends an message over the chat backend, attempts to encrypt so that both
        recipient and author can decrypt, but only encrypts if you have their public key.

        msg: message to be sent
        uid: facebook id of the user to send to
        chat_type: type of the chat (can be ThreadType.USER or ThreadType.GROUP)
        fingerprint [array of str]: gpg fingerprints of the recipients (None if does not exist [DNE])

        returns formatted str of original msg
        """
        stickers, text = parse_sticker(msg)
        type = USER if chat_type == "USER" else GROUP

        msg = msg if len(stickers) == 0 else text
        encrypted = str(gpg.encrypt(msg, [*fingerprints, keyid])) if fingerprints is not None else msg

        if len(stickers) == 0:
            self.send(Message(text=encrypted), thread_id=uid, thread_type=type)
        else:
            for sticker in stickers:
                gen_sticker(*sticker)

            self.sendLocalFiles(get_cache(), message=Message(text=encrypted), thread_id=uid, thread_type=type)
            clear_cache()

        return format_message(time.time(), msg)

    def onMessage(self, author_id: str, message_object: Message, thread_id: str, thread_type, **kwargs):
        """ Receives a message from a given user.
        Uses instance variables to return value.
        """

        if self.thread == thread_id:
            self.markAsDelivered(thread_id, message_object.uid)
            self.markAsRead(thread_id)

            self.received, self.message, self.thread, self.author_uid = True, message_object, thread_id, author_id
        else:
            self.new_message, self.new_message_thread = True, thread_id

global_config = load_file(SETTINGS, lambda x: json.load(x))
dev = global_config["dev"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Uses GPG to encrypt messages.')
    parser.add_argument('-v', '--version', action='version', version='GPG-Messenger 1.0')

    subparsers = parser.add_subparsers(title="commands")
    parser_edit = subparsers.add_parser('edit', help="edits the settings")
    parser_edit.add_argument("setting", help="specifies which level of settings to edit. Either global or facebook.")
    parser_edit.set_defaults(func=lambda args: setup_settings(args.setting))

    args = parser.parse_args() #TODO: edit specific parameter without overwriting existing settings file
    args.func(args)

    if not dev:
        sys.exit()

gpg = gnupg.GPG(**global_config["gpg"])
keyid = gpg.list_keys(True)[0]['keyid']

config = load_file(get_path(global_config['backend']), lambda x: json.load(x))
cookies = load_file("cookie.gpg", lambda x: pickle.loads(gpg.decrypt(x.read()).data))
gpg_keys = load_file("keys.pickle", pickle.load, "rb")

client = make_client()
client.init()

make_thread(f=lambda: client.listen())
