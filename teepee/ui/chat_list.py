import wx


class ChatListPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame

        sizer = wx.BoxSizer(wx.VERTICAL)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)

        self.new_chat_btn = wx.Button(self, label="&New Chat")
        self.new_chat_btn.SetName("New Chat")
        self.new_chat_btn.SetToolTip("Start a new chat with a user")
        btn_row.Add(self.new_chat_btn, 1, wx.ALL, 5)

        self.delete_chat_btn = wx.Button(self, label="De&lete Chat")
        self.delete_chat_btn.SetName("Delete Chat")
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
                preview = ": Voice message"
            elif msg.media and msg.text:
                label = self._media_label(msg.media)
                caption = msg.text.replace("\n", " ")
                if len(caption) > 40:
                    caption = caption[:40] + "..."
                preview = f": [{label}] {caption}"
            elif msg.text:
                text = msg.text.replace("\n", " ")
                if len(text) > 40:
                    text = text[:40] + "..."
                preview = f": {text}"
            elif msg.media:
                preview = f": [{self._media_label(msg.media)}]"
        return f"{name}{muted}{unread}{preview}"

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

    def update_chat_preview(self, chat_id, message, increment_unread=True):
        for i, dialog in enumerate(self._dialogs):
            entity_id = getattr(dialog.entity, "id", None)
            if entity_id == chat_id:
                dialog.message = message
                if increment_unread:
                    dialog.unread_count = (dialog.unread_count or 0) + 1
                # Move to top of list
                self._dialogs.remove(dialog)
                self._dialogs.insert(0, dialog)
                self._apply_filter()
                return True
        return False

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
        if idx < len(self._filtered_dialogs):
            chat_id = getattr(self._filtered_dialogs[idx].entity, "id", None)
            is_muted = chat_id in self._muted_ids
            mute_item.Enable(not is_muted)
            unmute_item.Enable(is_muted)
        menu.AppendSeparator()
        block_item = menu.Append(wx.ID_ANY, "&Block User")
        unblock_item = menu.Append(wx.ID_ANY, "U&nblock User")
        report_item = menu.Append(wx.ID_ANY, "&Report User...")
        # Disable block/unblock/report for non-user chats
        if idx < len(self._filtered_dialogs):
            from telethon.tl.types import User
            entity = self._filtered_dialogs[idx].entity
            if not isinstance(entity, User):
                block_item.Enable(False)
                unblock_item.Enable(False)
                report_item.Enable(False)
            else:
                user_id = getattr(entity, "id", None)
                is_blocked = user_id in self.frame._blocked_users
                block_item.Enable(not is_blocked)
                unblock_item.Enable(is_blocked)
        menu.AppendSeparator()
        delete_item = menu.Append(wx.ID_ANY, "&Delete Chat")
        self.Bind(wx.EVT_MENU, self._on_ctx_mute, mute_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_unmute, unmute_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_block, block_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_unblock, unblock_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_report, report_item)
        self.Bind(wx.EVT_MENU, self._on_ctx_delete, delete_item)
        self.PopupMenu(menu)
        menu.Destroy()

    def _on_ctx_mute(self, event):
        self.frame._on_mute_chat(event)

    def _on_ctx_unmute(self, event):
        self.frame._on_unmute_chat(event)

    def _on_ctx_block(self, event):
        self.frame._on_block_user(event)

    def _on_ctx_unblock(self, event):
        self.frame._on_unblock_user(event)

    def _on_ctx_report(self, event):
        self.frame._on_report_user(event)

    def _on_ctx_delete(self, event):
        self.frame.delete_selected_chat()
