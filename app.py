from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import ListProperty
from kivy.properties import ObjectProperty
from kivy.properties import BooleanProperty
from kivy.animation import Animation
from functools import partial
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
import time
import messenger

client = messenger.client
HISTORY = 10
DELAY = 0.1

KV = '''
#:import RGBA kivy.utils.rgba
#:import Clock kivy.clock.Clock
<ImageButton@ButtonBehavior+Image>:
    size_hint: None, None
    size: self.texture_size
    canvas.before:
        PushMatrix
        Scale:
            origin: self.center
            x: .75 if self.state == 'down' else 1
            y: .75 if self.state == 'down' else 1
    canvas.after:
        PopMatrix
BoxLayout:
    orientation: 'horizontal'
    RecycleView:
        id: rl
        data: app.recipient_list
        do_scroll_x: False
        size_hint: 0.3, 1
        viewclass: 'Recipient'
        RecycleBoxLayout:
            id: box
            orientation: 'vertical'
            size_hint_y: None
            size: self.minimum_size
            default_size_hint: 1, None
            key_size: '_size'
            padding: 0
            spacing: 0
            canvas.before:
                Color:
                    rgba: 1,1,1,1
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: 0,0,0,0
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: .5, .5, .5, 1
            Line:
                width: 1
                rectangle: self.x, self.y, self.width, self.height
        RecycleView:
            id: rv
            data: app.messages
            viewclass: 'Message'
            do_scroll_x: False
            RecycleBoxLayout:
                id: box
                orientation: 'vertical'
                size_hint_y: None
                size: self.minimum_size
                default_size_hint: 1, None
                key_size: '_size'
                spacing: 10
        FloatLayout:
            size_hint_y: None
            height: 0
            Button:
                size_hint_y: None
                height: self.texture_size[1]
                opacity: 0 if not self.height else 1
                text: 'go to last message' if rv.height < box.height and rv.scroll_y > 0 else ''
                pos_hint: {'pos': (0, 0)}
                on_release: app.scroll_bottom()
        BoxLayout:
            size_hint: 1, None
            size: self.minimum_size
            TextInput:
                id: ti
                size_hint: 1, None
                height: min(max(self.line_height, self.minimum_height), 150)
                multiline: False
                on_text_validate:
                    app.send_out(ti.text.strip())
                    ti.text = ''
                    app.schedule_refocus(ti)
            ImageButton:
                source: 'data/logo/kivy-icon-48.png'
                on_release:
                    app.send_out(ti.text.strip())
                    ti.text = ''
                    app.schedule_refocus(ti)

<Message@FloatLayout>:
    message_id: -1
    bg_color: '#0078FF'
    side: 'left'
    text: ''
    m_color: 0, 0, 0, 1
    size_hint_y: None
    _size: 0, 0
    rounding: (25, 10, 10, 25)
    t_size: {'text_size': (None, None)}
    Label:
        text: root.text
        color: root.m_color
        padding: 15, 10
        size_hint: None, None
        size: self.texture_size
        text_size: root.t_size['text_size']

        on_texture_size:
            message = dict(app.messages[root.message_id])
            message['_size'] = self.texture_size
            app.messages[root.message_id] = message
        pos_hint:
            (
            {'x': 0, 'center_y': .5}
            if root.side == 'left' else
            {'right': 1, 'center_y': .5}
            )
        canvas.before:
            Color:
                rgba: RGBA(root.bg_color)
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: root.rounding
<Recipient@FloatLayout>:
    r_id: -1
    bg_color: (0.847, 0.847, 0.847, 1)
    side: 'left'
    text: ''
    m_color: 0, 0, 0, 1
    size_hint_y: None
    _size: 0, 0
    t_size: {'text_size': (None, None)}
    chat_uid: ""
    type: "USER"
    HoverButton:
        text: root.text
        color: root.m_color
        background_normal: ''
        background_color: (0.949,0.949,0.949,1) if self.hovered else (1,1,1,1)
        padding: 0, 31
        size_hint: 1, None
        size: self.texture_size
        text_size: root.t_size['text_size']
        c_uid: root.chat_uid
        on_press:
            self.background_color=(0.6,0.6,0.6,1)
            app.switch_recipient(self.c_uid, root.type)
        on_texture_size:
            recipient_list = dict(app.recipient_list[root.r_id])
            recipient_list['_size'] = self.text_size
            app.recipient_list[root.r_id] = recipient_list
        pos_hint: {'x': 0, 'center_y': .5}
        canvas.before:
            Color:
                rgba: .75, .75, .75, 1
            Line:
                width: 1
                rectangle: self.x, self.y, self.width, self.height
'''

class GPG_Messenger(App):

    recipient_list = ListProperty()
    messages = ListProperty()

    def __init__(self):
        """
        Obtains the last 20 threads and adds them to the left hand bar.
        """
        super().__init__()
        for thread in client.fetchThreadList():
            self.add_recipient(thread.name if thread.name is not None else "Unnamed", thread.uid, thread.type)
        messenger.make_thread(self.receive)
        self.intialize()

    def intialize(self):
        self.messages = []
        #uid_to_name [dict] ([str] -> [str]): fbchat uid mapped to name
        #current_members [list] of [str]: member uids in active chat
        #active_chat_uid [str]: uid of the current chat
        #active_chat_type [str]: type of chat that is open - either "USER" or "GROUP" (NOT the ThreadType.USER FBChat constant!)
        #gpg_keys [list] of [str]: length 16 fingerpints of the public keys of everyone in the chat in the order of self.current_members
        self.uid_to_name = {}
        self.current_members = []
        self.active_chat_uid = ''
        self.active_chat_type = ""
        self.gpg_keys = []

    def build(self): return Builder.load_string(KV)

    def switch_recipient(self, chat_uid, chat_type, *args):
        """
        Called on press of button in kv - sets variables, clears messages, rebuilds UID to name map, and loads last 50 messages.
        """
        self.intialize() #reset

        self.active_chat_type = chat_type
        self.active_chat_uid = chat_uid

        if chat_type == "GROUP":
            self.current_members = (client.fetchThreadInfo(chat_uid)[chat_uid]).participants
        else:
            self.current_members = {client.uid, chat_uid}
        self.update_uid_to_name()
        self.update_keys()
        self.load_last(chat_uid, chat_type)

    def update_keys(self):
        for user_id in self.current_members:
            if user_id != client.uid:
                for key in messenger.gpg.list_keys():
                    for uid in key["uids"]:
                        name = self.uid_to_name[user_id]
                        if name.lower() in uid.lower() and not (key["keyid"] in self.gpg_keys):
                            self.gpg_keys.append(key["keyid"])

        if len(self.gpg_keys) < len(self.current_members) - 1:
            #shouldn't encrypt
            self.gpg_keys = None

    def update_uid_to_name(self):
        """
        Helper func to rebuild map of UIDs to names.
        """
        for i in self.current_members:
            if i != client.uid:
                self.uid_to_name[i] = (client.fetchUserInfo(i)[i]).name

    def load_last(self, chat_uid, chat_type, n=HISTORY, *args):
        """
        Loads last n (default 50) messages.
        """
        try:
            prev = client.fetchThreadMessages(thread_id=chat_uid, limit=n)[::-1]
        except messenger.FBchatException:
            print("FBchatException")
            return

        for i in prev:
            first_name = self.uid_to_name.get(i.author, "Unknown").split(" ")[0]
            self.render_message(i.author, i.text, first_name)

        self.scroll_bottom()

    def add_message(self, text, side, bg_color, text_color, rounding, t_size):
        """
        Adds a message to the GUI.
        """
        self.messages.append({
            'message_id': len(self.messages),
            'text': text,
            'side': side,
            'bg_color': bg_color,
            'm_color': text_color,
            'rounding': rounding,
            't_size': {'text_size': (t_size, None)}
        })

    def add_recipient(self, name, uid, type):
        """
        Adds a clickable recipient to the GUI.
        """
        self.recipient_list.append({
            'r_id': len(self.recipient_list),
            'text': name,
            'side': 'left',
            'chat_uid': uid,
            'type': "USER" if type == messenger.USER else "GROUP"
        })

    def render_message(self, author, text, name=None):
        """
        Wraps text and calls add_message.
        """

        #TODO: find out a good name for var1 and var2
        dir, color, var1, var2 = ("right", "#0078FF", (1,1,1,1), (25,5,5,25)) if author == client.uid else ("left", "#F1F0F0", (0,0,0,1), (5,25,25,5))

        if text is not None and text.strip() != "":
            text = messenger.decrypt_message(text)
            wrap = 760 if len(text.strip()) > 50 else None
            msg = f"{name}: {text}" if self.active_chat_type == "GROUP" and author != client.uid else text
            self.add_message(msg, dir, color, var1, var2, wrap)

    def send_out(self, text):
        """
        Triggered on enter or clicking the kivy logo - actually sends out message through facebook and calls send_message for the GUI.
        """
        self.render_message(client.uid, text)
        client.send_message(text, self.active_chat_uid, self.active_chat_type, self.gpg_keys)

    def receive(self):
        while True:
            time.sleep(DELAY)
            if client.received:
                client.received = False
                if client.thread == self.active_chat_uid and client.author_uid != client.uid:
                    self.receive_message(client.message.text, self.uid_to_name[client.author_uid])

    def scroll_bottom(self):
        """
        Animates a scroll to the bottom of the messages in d=*seconds* time.
        """
        Animation.cancel_all(self.root.ids.rv, 'scroll_y')
        Animation(scroll_y=0, t='out_quad', d=.3).start(self.root.ids.rv)

    def schedule_refocus(self, obj):
        """
        Used for text entry box - needs to schedule or it won't work.
        """
        Clock.schedule_once(partial(self.refocus, obj), 0.05)

    def refocus(self, obj, *args):
        obj.focus = True

class HoverBehavior(object):
    """Hover behavior.
    :Events:
        `on_enter`
            Fired when mouse enter the bbox of the widget.
        `on_leave`
            Fired when the mouse exit the widget
    """

    hovered = BooleanProperty(False)
    border_point= ObjectProperty(None)
    '''Contains the last relevant point received by the Hoverable. This can
    be used in `on_enter` or `on_leave` in order to know where was dispatched the event.
    '''

    def __init__(self, **kwargs):
        self.register_event_type('on_enter')
        self.register_event_type('on_leave')
        Window.bind(mouse_pos=self.on_mouse_pos)
        super(HoverBehavior, self).__init__(**kwargs)

    def on_mouse_pos(self, *args):
        if not self.get_root_window():
            return # do proceed if I'm not displayed <=> If have no parent
        pos = args[1]
        #Next line to_widget allow to compensate for relative layout
        inside = self.collide_point(*self.to_widget(*pos))
        if self.hovered == inside:
            #We have already done what was needed
            return
        self.border_point = pos
        self.hovered = inside
        if inside:
            self.dispatch('on_enter')
        else:
            self.dispatch('on_leave')

    def on_enter(self):
        pass

    def on_leave(self):
        pass


Factory.register('HoverBehavior', HoverBehavior)
class HoverButton(Button, HoverBehavior):
    def on_enter(self, *args):
        pass

    def on_leave(self, *args):
        pass


Window.clearcolor = (1, 1, 1, 1)
if __name__ == '__main__':
    GPG_Messenger().run()
