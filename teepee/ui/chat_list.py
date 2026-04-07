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
        sizer.Add(self.search_ctrl, flag=wx.EXPAND | wx.ALL, border=5)

        sizer.Add(
            wx.StaticText(self, label="Chats:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.list_ctrl = wx.ListBox(self)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(sizer)

        self._dialogs = []
        self._filtered_dialogs = []
        self._updating = False

        self.list_ctrl.Bind(wx.EVT_LISTBOX, self._on_select)
        self.search_ctrl.Bind(wx.EVT_TEXT, self._on_search)
        self.new_chat_btn.Bind(wx.EVT_BUTTON, self._on_new_chat)
        self.delete_chat_btn.Bind(wx.EVT_BUTTON, self._on_delete_chat)

    def set_dialogs(self, dialogs):
        self._dialogs = list(dialogs)
        self._apply_filter()

    def _format_dialog(self, dialog):
        name = dialog.name or "Unknown"
        unread = f" ({dialog.unread_count})" if dialog.unread_count else ""
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
                preview = f" [{type(msg.media).__name__}]"
        return f"{name}{unread}{preview}"

    def _apply_filter(self):
        self._updating = True
        prev_idx = self.list_ctrl.GetSelection()
        prev_id = None
        if prev_idx != wx.NOT_FOUND and prev_idx < len(self._filtered_dialogs):
            prev_entity = self._filtered_dialogs[prev_idx].entity
            prev_id = getattr(prev_entity, "id", None)

        query = self.search_ctrl.GetValue().lower()
        self._filtered_dialogs = []
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
        self._updating = False

    def _on_select(self, event):
        if self._updating:
            return
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
