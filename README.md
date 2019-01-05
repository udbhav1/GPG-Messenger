# GPG-Messenger
GnuPG (GPG) based messenger client that implements the openPGP encryption standard while using Facebook Messenger or an equivalent as a backend. Very similar to [Pidgin](https://pidgin.im/) or [Adium](https://adium.im/).

Implemented using [**Python 3.7**](https://www.python.org/).

Libraries used:
- [fbchat](https://fbchat.readthedocs.io/en/master/)
- [python-gnupg](https://pythonhosted.org/python-gnupg/)
- tkinter

## Setup

1. Set ***"gpgpath"*** in config.json to the path of your **.gnupg**
2. Create and gpg-encrypt a text file that contains your facebook password with:
```
$ echo "FACEBOOK_PASSWORD" | gpg --armor -r "YOUR_PUBLIC_KEY" -e > FILENAME
```
3. Set ***"passpath"*** to the **path of this encrypted password file**
4. Set ***"email"*** to the email associated with your **GPG key** and ***"username"*** to the email associated with your **Facebook account**

Now navigate to the directory where the files are saved and
```
$ python3 app.py
```
