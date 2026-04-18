import wx

from .theme import apply_theme, is_dark_mode
from .announce import announce


try:
    from telethon.tl.types import (
        KeyboardButtonCallback,
        KeyboardButtonUrl,
        ReplyInlineMarkup,
    )
except ImportError:
    ReplyInlineMarkup = None
    KeyboardButtonCallback = None
    KeyboardButtonUrl = None


class MessagePanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self._recording = False
        self._chat_open = False
        self._markup_buttons = []
        self._reply_to_msg = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Message list (hidden until a chat is opened) ---
        self.messages_label = wx.StaticText(self, label="Messages:")
        sizer.Add(self.messages_label, 0, wx.LEFT | wx.TOP, 5)
        sizer.Hide(self.messages_label)

        self.messages_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.messages_list.SetName("Messages")
        sizer.Add(self.messages_list, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Hide(self.messages_list)

        # --- Bot inline buttons panel (hidden by default) ---
        self.buttons_panel = wx.Panel(self)
        self.buttons_panel.SetName("Bot actions")
        self.buttons_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.buttons_panel.SetSizer(self.buttons_sizer)
        sizer.Add(
            self.buttons_panel,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            5,
        )
        sizer.Hide(self.buttons_panel)

        # --- Reply bar (hidden by default) ---
        self.reply_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.reply_label = wx.StaticText(self, label="")
        self.reply_sizer.Add(
            self.reply_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5
        )
        self.cancel_reply_btn = wx.Button(self, label="&Cancel reply")
        self.cancel_reply_btn.SetName("Cancel reply")
        self.cancel_reply_btn.SetToolTip("Cancel replying to this message")
        self.reply_sizer.Add(self.cancel_reply_btn, 0, wx.ALL, 2)
        sizer.Add(self.reply_sizer, 0, wx.EXPAND)
        sizer.Hide(self.reply_sizer)

        # --- Message action buttons (Play, Stop, Save, Delete, Reply) ---
        self.msg_actions_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.play_btn = wx.Button(self, label="&Play")
        self.play_btn.SetName("Play")
        self.play_btn.SetToolTip("Play the selected voice message")
        self.msg_actions_sizer.Add(self.play_btn, 0, wx.ALL, 2)
        self.play_btn.Hide()

        self.stop_btn = wx.Button(self, label="S&top")
        self.stop_btn.SetName("Stop")
        self.stop_btn.SetToolTip("Stop playback")
        self.msg_actions_sizer.Add(self.stop_btn, 0, wx.ALL, 2)
        self.stop_btn.Hide()

        self.save_btn = wx.Button(self, label="Sa&ve")
        self.save_btn.SetName("Save")
        self.save_btn.SetToolTip("Save the selected file or voice message")
        self.msg_actions_sizer.Add(self.save_btn, 0, wx.ALL, 2)
        self.save_btn.Hide()

        self.delete_msg_btn = wx.Button(self, label="&Delete")
        self.delete_msg_btn.SetName("Delete")
        self.delete_msg_btn.SetToolTip("Delete the selected message")
        self.msg_actions_sizer.Add(self.delete_msg_btn, 0, wx.ALL, 2)

        self.edit_msg_btn = wx.Button(self, label="&Edit")
        self.edit_msg_btn.SetName("Edit")
        self.edit_msg_btn.SetToolTip("Edit the selected sent message")
        self.msg_actions_sizer.Add(self.edit_msg_btn, 0, wx.ALL, 2)

        self.reply_btn = wx.Button(self, label="&Reply")
        self.reply_btn.SetName("Reply")
        self.reply_btn.SetToolTip("Reply to the selected message")
        self.msg_actions_sizer.Add(self.reply_btn, 0, wx.ALL, 2)

        self.open_link_btn = wx.Button(self, label="Open &Link")
        self.open_link_btn.SetName("Open Link")
        self.open_link_btn.SetToolTip("Open a URL from the selected message")
        self.msg_actions_sizer.Add(self.open_link_btn, 0, wx.ALL, 2)
        self.open_link_btn.Hide()

        sizer.Add(self.msg_actions_sizer, 0, wx.LEFT | wx.RIGHT, 5)
        sizer.Hide(self.msg_actions_sizer)

        # --- Input area (hidden initially) ---
        self.input_sizer = wx.BoxSizer(wx.HORIZONTAL)

        input_label = wx.StaticText(self, label="Message:")
        self.input_sizer.Add(input_label, 0, wx.ALIGN_TOP | wx.ALL, 5)

        self.input_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        self.input_ctrl.SetName("Message")
        self.input_sizer.Add(self.input_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.VERTICAL)

        self.send_btn = wx.Button(self, label="&Send")
        self.send_btn.SetName("Send")
        self.send_btn.SetToolTip("Send the message")
        btn_sizer.Add(self.send_btn, 0, wx.ALL, 2)

        self.attach_btn = wx.Button(self, label="&Attach")
        self.attach_btn.SetName("Attach")
        self.attach_btn.SetToolTip("Send a file")
        btn_sizer.Add(self.attach_btn, 0, wx.ALL, 2)

        self.voice_btn = wx.Button(self, label="&Voice")
        self.voice_btn.SetName("Voice")
        self.voice_btn.SetToolTip("Record a voice message")
        btn_sizer.Add(self.voice_btn, 0, wx.ALL, 2)

        self.input_sizer.Add(btn_sizer, 0, wx.ALIGN_BOTTOM)

        sizer.Add(self.input_sizer, 0, wx.EXPAND)
        sizer.Hide(self.input_sizer)

        self.SetSizer(sizer)

        self.send_btn.Bind(wx.EVT_BUTTON, self._on_send)
        self.attach_btn.Bind(wx.EVT_BUTTON, self._on_attach)
        self.voice_btn.Bind(wx.EVT_BUTTON, self._on_voice)
        self.play_btn.Bind(wx.EVT_BUTTON, self._on_play)
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        self.delete_msg_btn.Bind(wx.EVT_BUTTON, self._on_delete_message)
        self.edit_msg_btn.Bind(wx.EVT_BUTTON, self._on_edit_message)
        self.reply_btn.Bind(wx.EVT_BUTTON, self._on_reply)
        self.cancel_reply_btn.Bind(wx.EVT_BUTTON, self._on_cancel_reply)
        self.open_link_btn.Bind(wx.EVT_BUTTON, self._on_open_link)
        self.messages_list.Bind(wx.EVT_LISTBOX, self._on_message_selected)

    def _show_chat(self):
        if self._chat_open:
            return
        self._chat_open = True
        sizer = self.GetSizer()
        sizer.Show(self.messages_label)
        sizer.Show(self.messages_list)
        sizer.Show(self.msg_actions_sizer)
        sizer.Show(self.input_sizer)
        sizer.Layout()

    def _on_message_selected(self, event):
        self.frame.on_message_selected()

    def display_messages(self, messages):
        self._show_chat()
        self.messages_list.Freeze()
        self.messages_list.Clear()
        for msg in reversed(messages):
            self.messages_list.Append(self._format_message_obj(msg))
        if self.messages_list.GetCount() > 0:
            last = self.messages_list.GetCount() - 1
            self.messages_list.SetSelection(last)
            self.messages_list.EnsureVisible(last)
        self.messages_list.Thaw()

    @staticmethod
    def _display_name(obj):
        if not obj:
            return "Unknown"
        first = getattr(obj, "first_name", None) or ""
        last = getattr(obj, "last_name", None) or ""
        full = f"{first} {last}".strip()
        return full or getattr(obj, "title", None) or "Unknown"

    def _get_time_format(self):
        tf = self.frame.config.get("time_format", "24h")
        return "%I:%M %p" if tf == "12h" else "%H:%M"

    def _format_message_obj(self, msg):
        if msg.out:
            sender = "You"
        else:
            sender = self._display_name(msg.sender)

        time_str = msg.date.astimezone().strftime(self._get_time_format()) if msg.date else ""

        reply_prefix = ""
        if msg.reply_to:
            reply_prefix = "[Reply] "

        edited_suffix = ""
        if getattr(msg, "edit_date", None):
            edited_suffix = " (edited)"

        if msg.voice:
            text = "[Voice message]"
        elif msg.media and msg.text:
            label = self._media_label(msg.media)
            caption = msg.text.replace("\n", " | ")
            text = f"[{label}] {caption}"
        elif msg.text:
            text = msg.text.replace("\n", " | ")
        elif msg.media:
            text = f"[{self._media_label(msg.media)}]"
        elif msg.action:
            text = self._action_label(msg.action)
        else:
            text = "[Empty message]"

        return f"[{time_str}] {sender}: {reply_prefix}{text}{edited_suffix}"

    @staticmethod
    def _action_label(action):
        type_name = type(action).__name__
        labels = {
            "MessageActionPhoneCall": "Phone call",
            "MessageActionChatCreate": "Group created",
            "MessageActionChatEditTitle": "Changed group title",
            "MessageActionChatEditPhoto": "Changed group photo",
            "MessageActionChatDeletePhoto": "Removed group photo",
            "MessageActionChatAddUser": "Added user",
            "MessageActionChatDeleteUser": "Removed user",
            "MessageActionChatJoinedByLink": "Joined via link",
            "MessageActionPinMessage": "Pinned a message",
            "MessageActionContactSignUp": "Joined Telegram",
            "MessageActionScreenshotTaken": "Screenshot taken",
        }
        return f"[{labels.get(type_name, 'Service message')}]"

    @staticmethod
    def _media_label(media):
        type_name = type(media).__name__
        if type_name == "MessageMediaDocument":
            doc = getattr(media, "document", None)
            if doc:
                filename = None
                kind = None
                for attr in getattr(doc, "attributes", []):
                    attr_name = type(attr).__name__
                    if attr_name == "DocumentAttributeFilename":
                        filename = getattr(attr, "file_name", None)
                    elif attr_name == "DocumentAttributeAudio":
                        if getattr(attr, "voice", False):
                            return "Voice message"
                        kind = "Audio"
                    elif attr_name == "DocumentAttributeVideo":
                        if getattr(attr, "round_message", False):
                            return "Video message"
                        kind = "Video"
                    elif attr_name == "DocumentAttributeSticker":
                        return "Sticker"
                    elif attr_name == "DocumentAttributeAnimated":
                        return "GIF"
                if kind and filename:
                    return f"{kind}: {filename}"
                if kind:
                    return kind
                if filename:
                    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                    if ext in ("png", "jpg", "jpeg", "bmp", "gif", "webp", "tiff", "tif"):
                        return f"Picture: {filename}"
                    return f"File: {filename}"
            return "Document"
        labels = {
            "MessageMediaPhoto": "Photo",
            "MessageMediaContact": "Contact",
            "MessageMediaGeo": "Location",
            "MessageMediaGeoLive": "Live location",
            "MessageMediaVenue": "Venue",
            "MessageMediaGame": "Game",
            "MessageMediaInvoice": "Invoice",
            "MessageMediaPoll": "Poll",
            "MessageMediaDice": "Dice",
            "MessageMediaWebPage": "Link",
            "MessageMediaStory": "Story",
            "MessageMediaUnsupported": "Unsupported media",
        }
        return labels.get(type_name, "Media")

    def append_new_message(self, data):
        self._show_chat()
        sender = data["sender_name"]
        time_str = data["date"].astimezone().strftime(self._get_time_format()) if data["date"] else ""

        reply_prefix = ""
        if data.get("reply_to_msg_id"):
            reply_prefix = "[Reply] "

        if data["is_voice"]:
            text = "[Voice message]"
        elif data["is_media"] and data["text"]:
            msg = data.get("message")
            if msg and msg.media:
                label = self._media_label(msg.media)
                caption = data["text"].replace("\n", " | ")
                text = f"[{label}] {caption}"
            else:
                text = data["text"].replace("\n", " | ")
        elif data["text"]:
            text = data["text"].replace("\n", " | ")
        elif data["is_media"]:
            msg = data.get("message")
            if msg and msg.media:
                text = f"[{self._media_label(msg.media)}]"
            else:
                text = "[Media]"
        elif data.get("message") and getattr(data["message"], "action", None):
            text = self._action_label(data["message"].action)
        else:
            text = "[Empty message]"

        count = self.messages_list.GetCount()
        sel = self.messages_list.GetSelection()
        was_at_end = (count == 0 or sel == wx.NOT_FOUND or sel >= count - 1)

        self.messages_list.Append(
            f"[{time_str}] {sender}: {reply_prefix}{text}"
        )

        if was_at_end:
            last = self.messages_list.GetCount() - 1
            self.messages_list.SetSelection(last)
            self.messages_list.EnsureVisible(last)

    def do_send(self):
        text = self.input_ctrl.GetValue().strip()
        if text:
            reply_to = None
            if self._reply_to_msg:
                reply_to = self._reply_to_msg.id
            self.input_ctrl.Clear()
            self.clear_reply()
            self.frame.send_message(text, reply_to=reply_to)

    def _on_send(self, event):
        self.do_send()

    def _on_attach(self, event):
        with wx.FileDialog(
            self.GetTopLevelParent(),
            "Choose a file to send",
            wildcard="All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                caption = ""
                caption_dlg = wx.TextEntryDialog(
                    self.GetTopLevelParent(),
                    "Enter a caption for this file (leave blank for none):",
                    "File Caption",
                    "",
                )
                caption_dlg.SetName("File Caption")
                from .theme import apply_theme
                apply_theme(caption_dlg)
                if caption_dlg.ShowModal() == wx.ID_OK:
                    caption = caption_dlg.GetValue().strip()
                caption_dlg.Destroy()
                reply_to = None
                if self._reply_to_msg:
                    reply_to = self._reply_to_msg.id
                self.clear_reply()
                self.frame.send_file(path, reply_to=reply_to, caption=caption)

    def _on_voice(self, event):
        if not self._recording:
            self._recording = True
            self.voice_btn.SetLabel("S&top")
            self.voice_btn.SetName("Stop recording")
            self.voice_btn.SetToolTip(
                "Stop recording and send the voice message"
            )
            self.frame.SetStatusText("Recording...")
            self.frame._msg_frame.SetStatusText("Recording...")
            announce("Recording")
            self.frame.start_voice_recording()
        else:
            self._recording = False
            self.voice_btn.SetLabel("&Voice")
            self.voice_btn.SetName("Voice")
            self.voice_btn.SetToolTip("Record a voice message")
            self.frame.SetStatusText("Recording stopped, sending...")
            self.frame._msg_frame.SetStatusText("Recording stopped, sending...")
            announce("Recording stopped, sending")
            self.frame.stop_voice_recording()

    def _on_play(self, event):
        self.frame.play_last_voice()

    def _on_stop(self, event):
        self.frame.stop_voice_playback()

    def _on_save(self, event):
        self.frame.save_selected_media()

    def _on_reply(self, event):
        self.frame.reply_to_selected_message()

    def _on_cancel_reply(self, event):
        self.clear_reply()

    def _on_open_link(self, event):
        self.frame.open_message_link()

    def set_reply(self, msg, preview_text):
        self._reply_to_msg = msg
        self.reply_label.SetLabel(f"Replying to: {preview_text}")
        sizer = self.GetSizer()
        sizer.Show(self.reply_sizer)
        sizer.Layout()

    def clear_reply(self):
        self._reply_to_msg = None
        self.reply_label.SetLabel("")
        focused = wx.Window.FindFocus()
        sizer = self.GetSizer()
        sizer.Hide(self.reply_sizer)
        sizer.Layout()
        if focused is self.cancel_reply_btn:
            self.input_ctrl.SetFocus()

    def _on_delete_message(self, event):
        self.frame.delete_selected_message()

    def _on_edit_message(self, event):
        self.frame.edit_selected_message()

    def get_selected_message_index(self):
        return self.messages_list.GetSelection()

    def remove_message_at(self, index):
        if 0 <= index < self.messages_list.GetCount():
            self.messages_list.Delete(index)

    def update_message_at(self, index, msg):
        if 0 <= index < self.messages_list.GetCount():
            self.messages_list.SetString(index, self._format_message_obj(msg))

    def show_play_button(self, show, label="&Play", tooltip="Play the selected voice message"):
        if show:
            self.play_btn.SetLabel(label)
            self.play_btn.SetName(label.replace("&", ""))
            self.play_btn.SetToolTip(tooltip)
            if not self.play_btn.IsShown():
                self.play_btn.Show()
                self.msg_actions_sizer.Layout()
        elif not show and self.play_btn.IsShown():
            if wx.Window.FindFocus() is self.play_btn:
                self.messages_list.SetFocus()
            self.play_btn.Hide()
            self.msg_actions_sizer.Layout()

    def show_stop_button(self, show):
        if show:
            if not self.stop_btn.IsShown():
                self.stop_btn.Show()
                self.msg_actions_sizer.Layout()
        elif self.stop_btn.IsShown():
            if wx.Window.FindFocus() is self.stop_btn:
                self.messages_list.SetFocus()
            self.stop_btn.Hide()
            self.msg_actions_sizer.Layout()

    def show_save_button(self, show):
        if show:
            if not self.save_btn.IsShown():
                self.save_btn.Show()
                self.msg_actions_sizer.Layout()
        elif self.save_btn.IsShown():
            if wx.Window.FindFocus() is self.save_btn:
                self.messages_list.SetFocus()
            self.save_btn.Hide()
            self.msg_actions_sizer.Layout()

    def show_open_link_button(self, show):
        if show:
            if not self.open_link_btn.IsShown():
                self.open_link_btn.Show()
                self.msg_actions_sizer.Layout()
        elif self.open_link_btn.IsShown():
            if wx.Window.FindFocus() is self.open_link_btn:
                self.messages_list.SetFocus()
            self.open_link_btn.Hide()
            self.msg_actions_sizer.Layout()

    def set_enabled(self, enabled):
        self.input_ctrl.Enable(enabled)
        self.send_btn.Enable(enabled)
        self.attach_btn.Enable(enabled)
        self.voice_btn.Enable(enabled)
        self.save_btn.Enable(enabled)
        self.delete_msg_btn.Enable(enabled)
        self.edit_msg_btn.Enable(enabled)
        self.reply_btn.Enable(enabled)
        self.open_link_btn.Enable(enabled)
        if not enabled:
            focused = wx.Window.FindFocus()
            if focused and self.IsDescendant(focused):
                self.frame.chat_list.list_ctrl.SetFocus()

    def update_inline_buttons(self, msg):
        self._clear_inline_buttons()
        if not msg or not ReplyInlineMarkup:
            return
        markup = getattr(msg, "reply_markup", None)
        if not isinstance(markup, ReplyInlineMarkup):
            return
        for row in markup.rows:
            for button in row.buttons:
                label = button.text
                if KeyboardButtonUrl and isinstance(button, KeyboardButtonUrl):
                    label = f"{button.text} (link)"
                btn = wx.Button(self.buttons_panel, label=label)
                btn.SetName(label)
                btn.SetToolTip(self._button_tooltip(button))
                if is_dark_mode():
                    apply_theme(btn)
                self._markup_buttons.append((btn, button, msg))
                self.buttons_sizer.Add(btn, 0, wx.ALL, 2)
                btn.Bind(wx.EVT_BUTTON, self._on_inline_button)
        if self._markup_buttons:
            sizer = self.GetSizer()
            sizer.Show(self.buttons_panel)
            self.buttons_panel.Layout()
            sizer.Layout()

    def _button_tooltip(self, button):
        if KeyboardButtonUrl and isinstance(button, KeyboardButtonUrl):
            return f"Open {button.url}"
        if KeyboardButtonCallback and isinstance(button, KeyboardButtonCallback):
            return f"Send command: {button.text}"
        return button.text

    def _on_inline_button(self, event):
        btn_obj = event.GetEventObject()
        for wx_btn, tl_button, msg in self._markup_buttons:
            if wx_btn is btn_obj:
                self.frame.on_inline_button_click(msg, tl_button)
                return

    def _clear_inline_buttons(self):
        if self._markup_buttons:
            focused = wx.Window.FindFocus()
            for btn, _, _ in self._markup_buttons:
                if focused is btn:
                    self.messages_list.SetFocus()
                    break
        for btn, _, _ in self._markup_buttons:
            btn.Destroy()
        self._markup_buttons.clear()
        sizer = self.GetSizer()
        sizer.Hide(self.buttons_panel)
        self.buttons_panel.Layout()
        sizer.Layout()
