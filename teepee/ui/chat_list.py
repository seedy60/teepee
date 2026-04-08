import wx


class ChatListPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame

        sizer = wx.BoxSizer(wx.VERTICAL)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)

        self.new_chat_btn = wx.Button(self, label="&New Chat")
        self.new_chat_btn.SetToolTip("Start a new chat with a user")
        btn_row.Add(self.new_chat_btn, 1, wx.ALL, 5)

        self.delete_chat_btn = wx.Button(self, label="De&lete Chat")
        self.delete_chat_btn.SetToolTip("Delete the selected chat")
        btn_row.Add(self.delete_chat_btn, 1, wx.ALL, 5)

        sizer.Add(btn_row, flag=wx.EXPAND)

        sizer.Add(
            wx.StaticText(self, label="Search:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.search_ctrl = wx.TextCtrl(self)
        self.search_ctrl.SetName("Search")
        sizer.Add(self.search_ctrl, flag=wx.EXPAND | wx.ALL, border=5)

        sizer.Add(
            wx.StaticText(self, label="Chats:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.list_ctrl = wx.ListBox(self)
        self.list_ctrl.SetName("Chats")
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

        self._dialogs = []
        self._filtered_dialogs = []
        self._muted_ids = set()
        self._updating = False

        self.list_ctrl.Bind(wx.EVT_LISTBOX_DCLICK, self._on_activate)
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.search_ctrl.Bind(wx.EVT_TEXT, self._on_search)
        self.new_chat_btn.Bind(wx.EVT_BUTTON, self._on_new_chat)
        self.delete_chat_btn.Bind(wx.EVT_BUTTON, self._on_delete_chat)

    def set_dialogs(self, dialogs, muted_ids=None):
        self._dialogs = list(dialogs)
        self._muted_ids = muted_ids or set()
        self._apply_filter()

    def _format_dialog(self, dialog):
        name = dialog.name or "Unknown"
        chat_id = getattr(dialog.entity, "id", None)
        muted = " [Muted]" if chat_id in self._muted_ids else ""
        unread = f" ({dialog.unread_count} unread)" if dialog.unread_count else ""
        preview = ""
        msg = dialog.message
        if msg:
            if msg.voice:
                preview = " Voice message"
            elif msg.text:
                text = msg.text.replace("\n", " ")
                if len(text) > 40:
                    text = text[:40] + "..."
                preview = f" {text}"
            elif msg.media:
                preview = f" [{self._media_label(msg.media)}]"
        return f"{name}{muted}{unread}{preview}"

    @staticmethod
    def _media_label(media):
        type_name = type(media).__name__
        labels = {
            "MessageMediaPhoto": "Photo",
            "MessageMediaDocument": "Document",
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

    def _apply_filter(self):
        self._updating = True
        prev_idx = self.list_ctrl.GetSelection()
        prev_id = None
        if prev_idx != wx.NOT_FOUND and prev_idx < len(self._filtered_dialogs):
            prev_entity = self._filtered_dialogs[prev_idx].entity
            prev_id = getattr(prev_entity, "id", None)

        query = self.search_ctrl.GetValue().lower()
        self._filtered_dialogs = []
        self.list_ctrl.Freeze()
        self.list_ctrl.Clear()

        new_sel = wx.NOT_FOUND
        for dialog in self._dialogs:
            name = dialog.name or "Unknown"
            if query and query not in name.lower():
                continue
            idx = len(self._filtered_dialogs)
            self._filtered_dialogs.append(dialog)
            self.list_ctrl.Append(self._format_dialog(dialog))
            if prev_id is not None and getattr(dialog.entity, "id", None) == prev_id:
                new_sel = idx

        if new_sel != wx.NOT_FOUND:
            self.list_ctrl.SetSelection(new_sel)
        self.list_ctrl.Thaw()
        self._updating = False

    def _on_list_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._open_selected()
        else:
            event.Skip()

    def _on_activate(self, event):
        self._open_selected()

    def _open_selected(self):
        idx = self.list_ctrl.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self._filtered_dialogs):
            dialog = self._filtered_dialogs[idx]
            self.frame.on_dialog_selected(dialog)

    def _on_new_chat(self, event):
        self.frame.on_new_chat()

    def _on_delete_chat(self, event):
        self.frame.delete_selected_chat()

    def _on_search(self, event):
        self._apply_filter()

    def get_selected_dialog(self):
        idx = self.list_ctrl.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self._filtered_dialogs):
            return self._filtered_dialogs[idx]
        return None

    def _on_context_menu(self, event):
        idx = self.list_ctrl.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        menu = wx.Menu()
        mute_item = menu.Append(wx.ID_ANY, "&Mute Chat...")
        unmute_item = menu.Append(wx.ID_ANY, "&Unmute Chat")
        menu.AppendSeparator()
        delete_item = menu.Append(wx.ID_ANY, "&Delete Chat")
        self.Bind(wx.EVT_MENU, self._on_ctx_mute, mute_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_unmute, unmute_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_delete, delete_item)
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_ctx_mute(self, event):
        self.frame._on_mute_chat(event)

    def _on_ctx_unmute(self, event):
        self.frame._on_unmute_chat(event)

    def _on_ctx_delete(self, event):
        self.frame.delete_selected_chat()
