# GPG-Messenger
GnuPG (GPG) based messenger client that implements the openPGP encryption standard while using Facebook Messenger or an equivalent as a backend. Very similar to [Pidgin](https://pidgin.im/) or [Adium](https://adium.im/).

Implemented using [**Python 3.7**](https://www.python.org/).

Libraries used:
- [fbchat](https://fbchat.readthedocs.io/en/master/)
- [python-gnupg](https://pythonhosted.org/python-gnupg/)
- tkinter

## Setup

1. Create and gpg-encrypt a text file that contains your facebook password with:
```
$ echo "FACEBOOK_PASSWORD" | gpg --armor -r "YOUR_PUBLIC_KEY" -e > FILENAME
```
2. Create an empty file called **config.json** with the path /accounts/facebook/config.json in the project folder
3. Navigate to the directory where the files are saved and run `python messenger.py facebook`
and follow the prompts.

4. Finally, to launch the app, run
```
$ python3 app.py
```
