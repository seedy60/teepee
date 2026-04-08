import logging
import os
import sys
import threading

import wx
import wx.adv
from telethon.errors import SessionPasswordNeededError

from .auth_dialogs import (
    APISetupDialog,
    CodeDialog,
    NewChatDialog,
    PhoneDialog,
    TwoFactorDialog,
)
from .chat_list import ChatListPanel
from .message_frame import MessageFrame
from .settings_dialog import SettingsDialog

log = logging.getLogger(__name__)


def _make_tray_icon():
    """Create a simple 16x16 tray icon with a 'T' on a blue background."""
    bmp = wx.Bitmap(16, 16)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(70, 130, 180)))
    dc.Clear()
    dc.SetTextForeground(wx.WHITE)
    dc.SetFont(
        wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    )
    tw, th = dc.GetTextExtent("T")
    dc.DrawText("T", (16 - tw) // 2, (16 - th) // 2)
    dc.SelectObject(wx.NullBitmap)
    icon = wx.Icon()
    icon.CopyFromBitmap(bmp)
    return icon


class TeepeeTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.SetIcon(_make_tray_icon(), "Teepee")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self._on_restore)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self._on_restore)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        restore_item = menu.Append(wx.ID_ANY, "&Restore")
        quit_item = menu.Append(wx.ID_ANY, "&Quit")
        self.Bind(wx.EVT_MENU, self._on_restore, restore_item)
        self.Bind(wx.EVT_MENU, self._on_quit, quit_item)
        return menu

    def _on_restore(self, event):
        self.frame.restore_from_tray()

    def _on_quit(self, event):
        self.frame.quit()


class MainFrame(wx.Frame):
    def __init__(
        self,
        parent,
        config,
        telegram_manager,
        sound_manager,
        voice_manager,
        call_manager,
    ):
        super().__init__(parent, title="Teepee", size=(450, 600))

        self.config = config
        self.tg = telegram_manager
        self.sound = sound_manager
        self.voice = voice_manager
        self.calls = call_manager

        self._current_entity = None
        self._current_messages = []
        self._dialogs = []
        self._shown_msg_ids = set()
        self._muted_chats = {}
        self._pending_chat_focus = False

        self._create_ui()
        self._create_menu()
        self._create_status_bar()

        self._force_quit = False
        self._tray_icon = None

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        self.tg.on_new_message = self._on_incoming_message
        self.tg.on_message_sent = self._on_message_sent

        self.calls.on_call_state_changed = self._on_call_state

        self._restore_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_restore_timer, self._restore_timer)
        self._restore_timer.Start(500)

        self.SetMinSize((350, 400))
        self.CenterOnScreen()

        from .theme import apply_theme
        apply_theme(self)

    # ------------------------------------------------------------------ UI

    def _create_ui(self):
        panel = wx.Panel(self)
        self.chat_list = ChatListPanel(panel, self)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.chat_list, 1, wx.EXPAND)
        panel.SetSizer(sizer)

        self._msg_frame = MessageFrame(self)
        self.message_panel = self._msg_frame.message_panel
        self._msg_frame_was_shown = False

    def _create_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        self._profile_id = wx.NewIdRef()
        file_menu.Append(
            self._profile_id,
            "My &Profile...",
            "View and edit your Telegram profile",
        )
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "&Quit\tCtrl+Q")
        menubar.Append(file_menu, "&File")

        chat_menu = wx.Menu()
        self._mute_id = wx.NewIdRef()
        chat_menu.Append(
            self._mute_id,
            "&Mute Chat...",
            "Mute notifications for the selected chat",
        )
        self._unmute_id = wx.NewIdRef()
        chat_menu.Append(
            self._unmute_id,
            "&Unmute Chat",
            "Unmute notifications for the selected chat",
        )
        menubar.Append(chat_menu, "&Chat")

        tools_menu = wx.Menu()
        self._call_id = wx.NewIdRef()
        tools_menu.Append(
            self._call_id, "&Call Contact\tCtrl+Shift+C", "Start a voice call"
        )
        self._hangup_id = wx.NewIdRef()
        tools_menu.Append(
            self._hangup_id, "&Hang Up\tCtrl+Shift+H", "End the current call"
        )
        menubar.Append(tools_menu, "&Tools")

        group_menu = wx.Menu()
        self._join_id = wx.NewIdRef()
        group_menu.Append(
            self._join_id,
            "&Join Group/Channel",
            "Join a group or channel by link or username",
        )
        self._leave_id = wx.NewIdRef()
        group_menu.Append(
            self._leave_id,
            "&Leave Group/Channel",
            "Leave the currently selected group or channel",
        )
        group_menu.AppendSeparator()
        self._members_id = wx.NewIdRef()
        group_menu.Append(
            self._members_id,
            "View &Members",
            "List members of the selected group",
        )
        self._kick_id = wx.NewIdRef()
        group_menu.Append(
            self._kick_id,
            "&Kick Member",
            "Remove a member from the selected group",
        )
        self._edit_title_id = wx.NewIdRef()
        group_menu.Append(
            self._edit_title_id,
            "Edit &Title",
            "Change the title of the selected group",
        )
        menubar.Append(group_menu, "&Group")

        settings_menu = wx.Menu()
        self._settings_id = wx.NewIdRef()
        settings_menu.Append(
            self._settings_id,
            "&Settings...\tCtrl+,",
            "Configure audio devices, sound packs, and notifications",
        )
        menubar.Append(settings_menu, "S&ettings")

        help_menu = wx.Menu()
        self._shortcuts_id = wx.NewIdRef()
        help_menu.Append(
            self._shortcuts_id,
            "&Keyboard Shortcuts\tF1",
            "View keyboard shortcuts",
        )
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, "&About Teepee")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_profile, id=self._profile_id)
        self.Bind(wx.EVT_MENU, self._on_mute_chat, id=self._mute_id)
        self.Bind(wx.EVT_MENU, self._on_unmute_chat, id=self._unmute_id)
        self.Bind(wx.EVT_MENU, self._on_call, id=self._call_id)
        self.Bind(wx.EVT_MENU, self._on_hangup, id=self._hangup_id)
        self.Bind(wx.EVT_MENU, self._on_settings, id=self._settings_id)
        self.Bind(wx.EVT_MENU, self._on_shortcuts, id=self._shortcuts_id)
        self.Bind(wx.EVT_MENU, self._on_about, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self._on_join_group, id=self._join_id)
        self.Bind(wx.EVT_MENU, self._on_leave_group, id=self._leave_id)
        self.Bind(wx.EVT_MENU, self._on_view_members, id=self._members_id)
        self.Bind(wx.EVT_MENU, self._on_kick_member, id=self._kick_id)
        self.Bind(wx.EVT_MENU, self._on_edit_title, id=self._edit_title_id)

    def _create_status_bar(self):
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.SetStatusText("Not connected")

    # ----------------------------------------------------------- Keyboard

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()

        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if focused == self.chat_list.list_ctrl:
                self.chat_list._open_selected()
                return

        if key == wx.WXK_DELETE:
            if focused == self.chat_list.list_ctrl:
                self.delete_selected_chat()
                return

        if event.ControlDown() and not event.ShiftDown() and not event.AltDown():
            if key == ord('1'):
                self.chat_list.list_ctrl.SetFocus()
                return
            if key == ord('2'):
                if self._msg_frame.IsShown():
                    self._msg_frame.Raise()
                    self.message_panel.messages_list.SetFocus()
                return
            if key == ord('3'):
                if self._msg_frame.IsShown():
                    self._msg_frame.Raise()
                    self.message_panel.input_ctrl.SetFocus()
                return

        event.Skip()

    # --------------------------------------------------------- Connection

    def start_connection(self):
        if not self.config["api_id"] or not self.config["api_hash"]:
            # Try embedded credentials first (shipped in releases)
            from teepee.credentials import get_credentials

            embedded = get_credentials()
            if embedded:
                self.config["api_id"], self.config["api_hash"] = embedded
            elif not self._show_api_setup():
                self.Close()
                return

        self.SetStatusText("Connecting...")
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _show_api_setup(self):
        with APISetupDialog(self) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                api_id = dlg.GetAPIId()
                api_hash = dlg.GetAPIHash()
                if api_id and api_hash:
                    self.config["api_id"] = api_id
                    self.config["api_hash"] = api_hash
                    self.config.save()
                    return True
        return False

    def _connect_thread(self):
        try:
            authorized = self.tg.submit_wait(self.tg.connect(), timeout=30)
            if authorized:
                wx.CallAfter(self._on_connected)
            else:
                wx.CallAfter(self._start_auth_flow)
        except Exception as e:
            log.error("Connection failed: %s", e)
            wx.CallAfter(self._on_connection_error, str(e))

    def _on_connected(self):
        self.SetStatusText("Connected")
        try:
            me = self.tg.submit_wait(self.tg.get_me())
            name = getattr(me, "first_name", "User") or "User"
            self.SetTitle(f"Teepee - {name}")
            self.SetStatusText(f"Logged in as {name}", 1)
        except Exception:
            pass
        self._load_dialogs()

    def _on_connection_error(self, error):
        wx.MessageBox(
            f"Connection failed:\n{error}",
            "Error",
            wx.OK | wx.ICON_ERROR,
            self,
        )
        self.SetStatusText("Connection failed")

    # -------------------------------------------------------------- Auth

    def _start_auth_flow(self):
        with PhoneDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                self.Close()
                return
            phone = dlg.GetPhone()

        if not phone:
            self.Close()
            return

        self.SetStatusText("Sending code...")
        try:
            sent_code = self.tg.submit_wait(self.tg.send_code(phone))
        except Exception as e:
            wx.MessageBox(
                f"Failed to send code:\n{e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            self.Close()
            return

        with CodeDialog(self, phone) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                self.Close()
                return
            code = dlg.GetCode()

        self.SetStatusText("Verifying code...")
        try:
            self.tg.submit_wait(
                self.tg.sign_in_code(phone, code, sent_code.phone_code_hash)
            )
            self._on_connected()
        except SessionPasswordNeededError:
            self._handle_2fa()
        except Exception as e:
            wx.MessageBox(
                f"Sign in failed:\n{e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            self.Close()

    def _handle_2fa(self):
        with TwoFactorDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                self.Close()
                return
            password = dlg.GetPassword()

        self.SetStatusText("Verifying 2FA password...")
        try:
            self.tg.submit_wait(self.tg.sign_in_password(password))
            self._on_connected()
        except Exception as e:
            wx.MessageBox(
                f"2FA authentication failed:\n{e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            self.Close()

    # ----------------------------------------------------------- Dialogs

    def _load_dialogs(self):
        self.SetStatusText("Loading chats...")
        threading.Thread(target=self._load_dialogs_thread, daemon=True).start()

    def _load_dialogs_thread(self):
        try:
            dialogs = self.tg.submit_wait(self.tg.get_dialogs(limit=100))
            wx.CallAfter(self._on_dialogs_loaded, dialogs)
        except Exception as e:
            log.error("Failed to load dialogs: %s", e)
            wx.CallAfter(self.SetStatusText, f"Failed to load chats: {e}")

    def _on_dialogs_loaded(self, dialogs):
        self._dialogs = list(dialogs)
        self._update_muted_chats()
        self.chat_list.set_dialogs(self._dialogs, set(self._muted_chats.keys()))
        self.SetStatusText(f"{len(self._dialogs)} chats loaded")

    def on_new_chat(self):
        with NewChatDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            recipient = dlg.GetRecipient()
        if not recipient:
            return
        self.SetStatusText(f"Looking up {recipient}...")
        log.info("New chat: looking up %r", recipient)
        threading.Thread(
            target=self._resolve_new_chat_thread,
            args=(recipient,),
            daemon=True,
        ).start()

    def _resolve_new_chat_thread(self, recipient):
        try:
            entity = self.tg.submit_wait(self.tg.get_entity(recipient))
            log.info("Resolved %r to %s", recipient, entity)
            wx.CallAfter(self._on_new_chat_resolved, entity)
        except Exception as e:
            log.error("Failed to find user: %s", e)
            wx.CallAfter(self._on_new_chat_error, str(e))

    def _on_new_chat_error(self, error_msg):
        wx.MessageBox(
            f"Could not find user:\n{error_msg}",
            "New Chat",
            wx.OK | wx.ICON_ERROR,
            self,
        )
        self.SetStatusText("Ready")

    def _on_new_chat_resolved(self, entity):
        self._current_entity = entity
        self._current_messages = []
        self._shown_msg_ids.clear()
        self.message_panel.clear_reply()
        self.message_panel._clear_inline_buttons()
        self.message_panel.set_enabled(True)
        self.message_panel._show_chat()
        self.message_panel.messages_list.Freeze()
        self.message_panel.messages_list.Clear()
        self.message_panel.messages_list.Thaw()
        name = (
            getattr(entity, "first_name", None)
            or getattr(entity, "title", None)
            or getattr(entity, "username", None)
            or "Unknown"
        )
        self._msg_frame.SetTitle(f"{name} - Teepee")
        self._msg_frame.SetStatusText(f"Loading messages from {name}...")
        self._msg_frame.Show()
        self._msg_frame.Raise()
        self.message_panel.input_ctrl.SetFocus()
        self._pending_chat_focus = True
        self.SetStatusText(f"Loading messages from {name}...")
        self._load_dialogs()
        threading.Thread(
            target=self._load_messages_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def on_dialog_selected(self, dialog):
        self._current_entity = dialog.entity
        self._current_messages = []
        self._shown_msg_ids.clear()
        self.message_panel.clear_reply()
        self.message_panel._clear_inline_buttons()
        self.message_panel.set_enabled(True)
        self.message_panel._show_chat()
        self.message_panel.messages_list.Freeze()
        self.message_panel.messages_list.Clear()
        self.message_panel.messages_list.Thaw()
        name = dialog.name or "Chat"
        self._msg_frame.SetTitle(f"{name} - Teepee")
        self._msg_frame.SetStatusText(f"Loading messages from {name}...")
        self._msg_frame.Show()
        self._msg_frame.Raise()
        self.message_panel.input_ctrl.SetFocus()
        self._pending_chat_focus = True
        self.SetStatusText(f"Loading messages from {name}...")
        threading.Thread(
            target=self._load_messages_thread,
            args=(dialog.entity,),
            daemon=True,
        ).start()

    def _load_messages_thread(self, entity):
        try:
            log.info("Loading messages for entity %s", getattr(entity, "id", entity))
            messages = self.tg.submit_wait(
                self.tg.get_messages(entity, limit=50)
            )
            log.info("Loaded %d messages", len(messages))
            try:
                self.tg.submit_wait(self.tg.mark_as_read(entity))
            except Exception:
                pass
            wx.CallAfter(self._on_messages_loaded, list(messages), entity)
        except Exception as e:
            log.error("Failed to load messages: %s", e, exc_info=True)
            self._pending_chat_focus = False
            wx.CallAfter(self.SetStatusText, f"Failed to load messages: {e}")
            wx.CallAfter(self._msg_frame.SetStatusText, f"Failed to load messages: {e}")

    def _on_messages_loaded(self, messages, entity):
        if entity != self._current_entity:
            log.warning("Entity mismatch in _on_messages_loaded, ignoring")
            return
        log.info("Displaying %d messages", len(messages))
        self._current_messages = messages
        self.message_panel.display_messages(messages)
        # Show inline buttons for the last message if it has markup
        if messages:
            self.message_panel.update_inline_buttons(messages[0])
            self.message_panel.show_play_button(bool(messages[0].voice))
        else:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)
        name = (
            getattr(entity, "first_name", None)
            or getattr(entity, "title", None)
            or getattr(entity, "username", None)
            or "Chat"
        )
        if messages:
            status = f"{name} - {len(messages)} messages"
        else:
            status = f"{name} - No messages yet"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)

        if self._pending_chat_focus:
            self._pending_chat_focus = False
            if self._msg_frame.IsShown():
                self._msg_frame.Raise()
                if messages:
                    self.message_panel.messages_list.SetFocus()
                else:
                    self.message_panel.input_ctrl.SetFocus()
            self._load_dialogs()

    def on_message_selected(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if 0 <= msg_idx < len(self._current_messages):
            msg = self._current_messages[msg_idx]
            self.message_panel.update_inline_buttons(msg)
            self.message_panel.show_play_button(bool(msg.voice))
        else:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)

    def on_inline_button_click(self, msg, tl_button):
        from telethon.tl.types import KeyboardButtonUrl

        if isinstance(tl_button, KeyboardButtonUrl):
            import webbrowser

            webbrowser.open(tl_button.url)
            return
        threading.Thread(
            target=self._click_inline_thread,
            args=(msg, tl_button),
            daemon=True,
        ).start()

    def _click_inline_thread(self, msg, tl_button):
        try:
            self.tg.submit_wait(
                self.tg.click_inline_button(msg, tl_button.data)
            )
            # Bots often edit the message after a callback; reload to pick
            # up the updated markup.
            if self._current_entity:
                entity = self._current_entity
                messages = self.tg.submit_wait(
                    self.tg.get_messages(entity, limit=50)
                )
                wx.CallAfter(
                    self._on_messages_loaded, list(messages), entity
                )
        except Exception as e:
            log.error("Inline button click failed: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Button action failed:\n{e}",
            )

    # ---------------------------------------------------------- Messaging

    def send_message(self, text, reply_to=None):
        if not self._current_entity:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._send_message_thread,
            args=(entity, text, reply_to),
            daemon=True,
        ).start()

    def _send_message_thread(self, entity, text, reply_to=None):
        try:
            msg = self.tg.submit_wait(
                self.tg.send_message(entity, text, reply_to=reply_to)
            )
            wx.CallAfter(self._on_send_success, entity, msg)
        except Exception as e:
            log.error("Failed to send message: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to send message:\n{e}",
            )

    def _on_send_success(self, entity, msg):
        if entity != self._current_entity:
            return
        self._shown_msg_ids.add(msg.id)
        data = {
            "message": msg,
            "sender_name": "You",
            "chat_id": getattr(entity, "id", None),
            "text": msg.text or "",
            "date": msg.date,
            "is_voice": bool(msg.voice),
            "is_media": bool(msg.media),
            "out": True,
            "reply_to_msg_id": (
                msg.reply_to.reply_to_msg_id if msg.reply_to else None
            ),
        }
        self.message_panel.append_new_message(data)
        self.sound.play_sent()
        self.SetStatusText("Message sent")
        self._msg_frame.SetStatusText("Message sent")

    # ---------------------------------------------------------- Deletion

    def reply_to_selected_message(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Select a message to reply to.",
                "Reply",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        msg = self._current_messages[msg_idx]
        preview = ""
        if msg.text:
            preview = msg.text[:50]
        elif msg.voice:
            preview = "[Voice message]"
        elif msg.media:
            preview = "[Media]"
        else:
            preview = "[Message]"
        self.message_panel.set_reply(msg, preview)
        self.message_panel.input_ctrl.SetFocus()
        self.SetStatusText(f"Replying to: {preview}")
        self._msg_frame.SetStatusText(f"Replying to: {preview}")

    def delete_selected_message(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Select a message to delete.",
                "Delete Message",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        # Messages are displayed in reversed order
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        msg = self._current_messages[msg_idx]
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        if wx.MessageBox(
            "Delete this message?",
            "Confirm Delete",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            parent,
        ) != wx.YES:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._delete_message_thread,
            args=(entity, msg, msg_idx, idx),
            daemon=True,
        ).start()

    def _delete_message_thread(self, entity, msg, msg_idx, list_idx):
        try:
            self.tg.submit_wait(
                self.tg.delete_messages(entity, [msg.id])
            )
            wx.CallAfter(self._on_message_deleted, msg_idx, list_idx)
        except Exception as e:
            log.error("Failed to delete message: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to delete message:\n{e}",
            )

    def _on_message_deleted(self, msg_idx, list_idx):
        if msg_idx < len(self._current_messages):
            self._current_messages.pop(msg_idx)
        self.message_panel.remove_message_at(list_idx)
        count = self.message_panel.messages_list.GetCount()
        if count > 0:
            new_sel = min(list_idx, count - 1)
            self.message_panel.messages_list.SetSelection(new_sel)
            self.message_panel.messages_list.SetFocus()
        else:
            self.message_panel.input_ctrl.SetFocus()
        self.SetStatusText("Message deleted")
        self._msg_frame.SetStatusText("Message deleted")

    def delete_selected_chat(self):
        dialog = self.chat_list.get_selected_dialog()
        if not dialog:
            wx.MessageBox(
                "Select a chat to delete.",
                "Delete Chat",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        name = dialog.name or "Unknown"
        if wx.MessageBox(
            f"Delete the entire chat with {name}?\n\n"
            "This cannot be undone.",
            "Confirm Delete Chat",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        ) != wx.YES:
            return
        entity = dialog.entity
        threading.Thread(
            target=self._delete_chat_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _delete_chat_thread(self, entity):
        try:
            self.tg.submit_wait(self.tg.delete_dialog(entity))
            wx.CallAfter(self._on_chat_deleted, entity)
        except Exception as e:
            log.error("Failed to delete chat: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to delete chat:\n{e}",
            )

    def _on_chat_deleted(self, entity):
        current_id = getattr(self._current_entity, "id", None)
        deleted_id = getattr(entity, "id", None)
        if current_id and current_id == deleted_id:
            self._current_entity = None
            self._current_messages = []
            self._shown_msg_ids.clear()
            self.message_panel.clear_reply()
            self.message_panel._clear_inline_buttons()
            self.message_panel.set_enabled(False)
            self.message_panel.messages_list.Clear()
            self._msg_frame.Hide()
        self.SetStatusText("Chat deleted")
        self._load_dialogs()
        self.Raise()
        self.chat_list.list_ctrl.SetFocus()

    # ---------------------------------------------------- Voice messages

    def start_voice_recording(self):
        path = self.voice.start_recording()
        if not path:
            self.message_panel._recording = False
            self.message_panel.voice_btn.SetLabel("&Voice")
            self.message_panel.voice_btn.SetToolTip("Record a voice message")
            self.SetStatusText("Recording failed")
            self._msg_frame.SetStatusText("Recording failed")
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Failed to start recording. Check that sound_lib is installed.",
                "Recording Error",
                wx.OK | wx.ICON_ERROR,
                parent,
            )

    def stop_voice_recording(self):
        file_path = self.voice.stop_recording()
        if file_path and self._current_entity:
            entity = self._current_entity
            threading.Thread(
                target=self._send_voice_thread,
                args=(entity, file_path),
                daemon=True,
            ).start()
        elif not file_path:
            self.SetStatusText("Recording failed")
            self._msg_frame.SetStatusText("Recording failed")

    def _send_voice_thread(self, entity, file_path):
        try:
            self.tg.submit_wait(self.tg.send_voice(entity, file_path))
            wx.CallAfter(self._on_voice_sent)
        except Exception as e:
            log.error("Failed to send voice message: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to send voice message:\n{e}",
            )

    def _on_voice_sent(self):
        self.SetStatusText("Voice message sent")
        self._msg_frame.SetStatusText("Voice message sent")
        self.sound.play_sent()

    def play_last_voice(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        voice_msg = self._current_messages[msg_idx]
        if not voice_msg.voice:
            return
        self.SetStatusText("Downloading voice message...")
        self._msg_frame.SetStatusText("Downloading voice message...")
        threading.Thread(
            target=self._play_voice_thread,
            args=(voice_msg,),
            daemon=True,
        ).start()

    def _play_voice_thread(self, msg):
        try:
            dl_path = self.voice.get_download_path(msg.id)
            if not os.path.exists(dl_path):
                self.tg.submit_wait(self.tg.download_media(msg, dl_path))
            wx.CallAfter(self._play_voice_file, dl_path)
        except Exception as e:
            log.error("Failed to download voice message: %s", e)
            wx.CallAfter(self.SetStatusText, "Failed to download voice")
            wx.CallAfter(self._msg_frame.SetStatusText, "Failed to download voice")

    def _play_voice_file(self, path):
        self.voice.play_voice(path)
        self.SetStatusText("Playing voice message...")
        self._msg_frame.SetStatusText("Playing voice message...")

    # --------------------------------------------------- Real-time events

    def _on_incoming_message(self, data):
        chat_id = data.get("chat_id")
        if not self._is_chat_muted(chat_id):
            if data.get("is_group"):
                self.sound.play_group_received()
            elif data.get("is_channel"):
                self.sound.play_channel_received()
            else:
                self.sound.play_received()
        sender = data.get("sender_name", "Someone")
        preview = data.get("text", "")
        if data.get("is_voice"):
            preview = "Voice message"
        elif not preview:
            preview = "Media" if data.get("is_media") else "Message"
        else:
            preview = preview[:60]
        status = f"New message from {sender}: {preview}"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        if self._current_entity:
            current_id = getattr(self._current_entity, "id", None)
            if current_id and data["chat_id"] == current_id:
                msg = data.get("message")
                if msg:
                    self._current_messages.insert(0, msg)
                self.message_panel.append_new_message(data)
                if msg:
                    self.message_panel.update_inline_buttons(msg)
                # Mark as read since the chat is currently open
                entity = self._current_entity
                threading.Thread(
                    target=self._mark_read_thread,
                    args=(entity,),
                    daemon=True,
                ).start()
        self._load_dialogs()

    def _mark_read_thread(self, entity):
        try:
            self.tg.submit_wait(self.tg.mark_as_read(entity))
        except Exception:
            pass

    def _on_message_sent(self, data):
        # Sent messages are already shown by _on_send_success;
        # this handler catches messages sent from other sessions.
        msg = data.get("message")
        if msg and msg.id in self._shown_msg_ids:
            return
        if self._current_entity:
            current_id = getattr(self._current_entity, "id", None)
            if current_id and data["chat_id"] == current_id:
                self.message_panel.append_new_message(data)

    # ------------------------------------------------------------ Calls

    def _on_call(self, event):
        if not self._current_entity:
            wx.MessageBox(
                "Select a chat first.",
                "Call",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        entity = self._current_entity
        status = "Calling..."
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        threading.Thread(
            target=self._request_call_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _request_call_thread(self, entity):
        try:
            self.tg.submit_wait(self.calls.request_call(entity))
        except Exception as e:
            log.error("Call failed: %s", e)
            def _update_status(msg=f"Call failed: {e}"):
                self.SetStatusText(msg)
                self._msg_frame.SetStatusText(msg)
            wx.CallAfter(_update_status)

    def _on_hangup(self, event):
        if self.calls.in_call:
            threading.Thread(
                target=self._hangup_thread, daemon=True
            ).start()
        else:
            self.SetStatusText("No active call")
            self._msg_frame.SetStatusText("No active call")

    def _hangup_thread(self):
        try:
            self.tg.submit_wait(self.calls.discard_call())
        except Exception as e:
            log.error("Hangup failed: %s", e)

    def _on_call_state(self, state, data):
        status_map = {
            "calling": "Calling...",
            "active": "Call active",
            "ended": "Call ended",
            "error": f"Call error: {data}",
        }
        status = status_map.get(state, state)
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)

    # ---------------------------------------------------------- Settings

    def _on_settings(self, event):
        with SettingsDialog(self, self.config, self.sound) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.config["output_device_index"] = dlg.GetOutputDeviceIndex()
                self.config["input_device_index"] = dlg.GetInputDeviceIndex()
                self.config["sounds_enabled"] = dlg.GetSoundsEnabled()
                self.config["sound_pack"] = dlg.GetSoundPack()
                self.config.save()
                self.sound.set_output_device(dlg.GetOutputDeviceIndex())

    # ---------------------------------------------------- Profile / Mute

    def _on_profile(self, event):
        self.SetStatusText("Loading profile...")
        threading.Thread(
            target=self._load_profile_thread, daemon=True
        ).start()

    def _load_profile_thread(self):
        try:
            me = self.tg.submit_wait(self.tg.get_me())
            full = self.tg.submit_wait(self.tg.get_full_me())
            user_info = {
                "first_name": getattr(me, "first_name", "") or "",
                "last_name": getattr(me, "last_name", "") or "",
                "username": getattr(me, "username", "") or "",
                "phone": getattr(me, "phone", "") or "",
                "bio": getattr(full.full_user, "about", "") or "",
            }
            wx.CallAfter(self._show_profile_dialog, user_info)
        except Exception as e:
            log.error("Failed to load profile: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to load profile:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _show_profile_dialog(self, user_info):
        from .profile_dialog import ProfileDialog

        self.SetStatusText("Ready")
        with ProfileDialog(self, user_info) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                changes = {}
                new_first = dlg.GetFirstName()
                new_last = dlg.GetLastName()
                new_bio = dlg.GetBio()
                if new_first != user_info["first_name"]:
                    changes["first_name"] = new_first
                if new_last != user_info["last_name"]:
                    changes["last_name"] = new_last
                if new_bio != user_info["bio"]:
                    changes["about"] = new_bio
                if changes:
                    self.SetStatusText("Updating profile...")
                    threading.Thread(
                        target=self._update_profile_thread,
                        args=(changes,),
                        daemon=True,
                    ).start()

    def _update_profile_thread(self, changes):
        try:
            self.tg.submit_wait(self.tg.update_profile(**changes))
            if "first_name" in changes:
                me = self.tg.submit_wait(self.tg.get_me())
                name = getattr(me, "first_name", "User") or "User"
                wx.CallAfter(self.SetTitle, f"Teepee - {name}")
            wx.CallAfter(self.SetStatusText, "Profile updated")
        except Exception as e:
            log.error("Failed to update profile: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to update profile:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_mute_chat(self, event):
        dialog = self.chat_list.get_selected_dialog()
        if not dialog:
            wx.MessageBox(
                "Select a chat first.",
                "Mute Chat",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        from .theme import apply_theme

        choices = [
            "1 hour",
            "8 hours",
            "1 day",
            "1 week",
            "Permanently",
        ]
        dlg = wx.SingleChoiceDialog(
            self, "Mute notifications for:", "Mute Chat", choices
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        selection = dlg.GetSelection()
        dlg.Destroy()

        import time

        now = int(time.time())
        mute_times = [
            now + 3600,
            now + 28800,
            now + 86400,
            now + 604800,
            2147483647,
        ]
        mute_until = mute_times[selection]
        entity = dialog.entity
        chat_id = getattr(entity, "id", None)
        if chat_id:
            from datetime import datetime, timezone

            self._muted_chats[chat_id] = datetime.fromtimestamp(
                mute_until, tz=timezone.utc
            )
        threading.Thread(
            target=self._mute_chat_thread,
            args=(entity, mute_until),
            daemon=True,
        ).start()

    def _mute_chat_thread(self, entity, mute_until):
        try:
            self.tg.submit_wait(self.tg.mute_chat(entity, mute_until))
            wx.CallAfter(self._on_mute_done)
        except Exception as e:
            log.error("Failed to mute chat: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to mute chat:\n{e}"
            )

    def _on_mute_done(self):
        self.SetStatusText("Chat muted")
        self._msg_frame.SetStatusText("Chat muted")
        self._load_dialogs()

    def _on_unmute_chat(self, event):
        dialog = self.chat_list.get_selected_dialog()
        if not dialog:
            wx.MessageBox(
                "Select a chat first.",
                "Unmute Chat",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        entity = dialog.entity
        chat_id = getattr(entity, "id", None)
        if chat_id:
            self._muted_chats.pop(chat_id, None)
        threading.Thread(
            target=self._unmute_chat_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _unmute_chat_thread(self, entity):
        try:
            self.tg.submit_wait(self.tg.unmute_chat(entity))
            wx.CallAfter(self._on_unmute_done)
        except Exception as e:
            log.error("Failed to unmute chat: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to unmute chat:\n{e}"
            )

    def _on_unmute_done(self):
        self.SetStatusText("Chat unmuted")
        self._msg_frame.SetStatusText("Chat unmuted")
        self._load_dialogs()

    def _is_chat_muted(self, chat_id):
        mute_until = self._muted_chats.get(chat_id)
        if not mute_until:
            return False
        from datetime import datetime, timezone

        return mute_until > datetime.now(tz=timezone.utc)

    def _update_muted_chats(self):
        self._muted_chats.clear()
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        for d in self._dialogs:
            ns = getattr(d.dialog, "notify_settings", None)
            if not ns:
                continue
            mute_until = getattr(ns, "mute_until", None)
            if mute_until and mute_until > now:
                chat_id = getattr(d.entity, "id", None)
                if chat_id:
                    self._muted_chats[chat_id] = mute_until

    # ------------------------------------------------------- Group Actions

    def _is_group_or_channel(self):
        if not self._current_entity:
            return False
        from telethon.tl.types import Channel, Chat

        return isinstance(self._current_entity, (Channel, Chat))

    def _on_join_group(self, event):
        from .theme import apply_theme

        dlg = wx.TextEntryDialog(
            self,
            "Enter group/channel username or invite link:",
            "Join Group/Channel",
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        target = dlg.GetValue().strip()
        dlg.Destroy()
        if not target:
            return
        self.SetStatusText(f"Joining {target}...")
        threading.Thread(
            target=self._join_group_thread,
            args=(target,),
            daemon=True,
        ).start()

    def _join_group_thread(self, target):
        try:
            entity = self.tg.submit_wait(self.tg.get_entity(target))
            self.tg.submit_wait(self.tg.join_channel(entity))
            wx.CallAfter(self._on_group_joined, target)
        except Exception as e:
            log.error("Failed to join group: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to join:\n{e}",
                "Join Group",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_group_joined(self, target):
        self.SetStatusText(f"Joined {target}")
        self._msg_frame.SetStatusText(f"Joined {target}")
        self._load_dialogs()

    def _on_leave_group(self, event):
        if not self._is_group_or_channel():
            wx.MessageBox(
                "Select a group or channel first.",
                "Leave Group",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        name = (
            getattr(self._current_entity, "title", None)
            or getattr(self._current_entity, "username", None)
            or "this group"
        )
        if wx.MessageBox(
            f"Leave {name}?",
            "Confirm Leave",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            self,
        ) != wx.YES:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._leave_group_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _leave_group_thread(self, entity):
        try:
            self.tg.submit_wait(self.tg.leave_channel(entity))
            wx.CallAfter(self._on_group_left)
        except Exception as e:
            log.error("Failed to leave group: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to leave:\n{e}",
                "Leave Group",
            )

    def _on_group_left(self):
        self._current_entity = None
        self._current_messages = []
        self._shown_msg_ids.clear()
        self.message_panel.clear_reply()
        self.message_panel._clear_inline_buttons()
        self.message_panel.set_enabled(False)
        self.message_panel.messages_list.Clear()
        self._msg_frame.Hide()
        self.SetStatusText("Left group")
        self._load_dialogs()
        self.Raise()
        self.chat_list.list_ctrl.SetFocus()

    def _on_view_members(self, event):
        if not self._is_group_or_channel():
            wx.MessageBox(
                "Select a group or channel first.",
                "Members",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self.SetStatusText("Loading members...")
        entity = self._current_entity
        threading.Thread(
            target=self._load_members_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _load_members_thread(self, entity):
        try:
            participants = self.tg.submit_wait(
                self.tg.get_participants(entity)
            )
            wx.CallAfter(self._on_members_loaded, list(participants))
        except Exception as e:
            log.error("Failed to load members: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to load members:\n{e}",
                "Members",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_members_loaded(self, participants):
        from .theme import apply_theme

        lines = []
        for p in participants:
            name = getattr(p, "first_name", "") or ""
            last = getattr(p, "last_name", "") or ""
            uname = getattr(p, "username", "") or ""
            display = f"{name} {last}".strip()
            if uname:
                display += f" (@{uname})"
            lines.append(display)
        self.SetStatusText(f"{len(participants)} members")
        dlg = wx.SingleChoiceDialog(
            self,
            f"{len(participants)} members:",
            "Group Members",
            lines if lines else ["No members found"],
        )
        apply_theme(dlg)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_kick_member(self, event):
        from .theme import apply_theme

        if not self._is_group_or_channel():
            wx.MessageBox(
                "Select a group or channel first.",
                "Kick Member",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        dlg = wx.TextEntryDialog(
            self,
            "Enter the username of the member to kick:",
            "Kick Member",
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        username = dlg.GetValue().strip()
        dlg.Destroy()
        if not username:
            return
        if wx.MessageBox(
            f"Kick {username} from this group?",
            "Confirm Kick",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        ) != wx.YES:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._kick_member_thread,
            args=(entity, username),
            daemon=True,
        ).start()

    def _kick_member_thread(self, entity, username):
        try:
            user = self.tg.submit_wait(self.tg.get_entity(username))
            self.tg.submit_wait(self.tg.kick_participant(entity, user))
            def _on_kicked(u=username):
                self.SetStatusText(f"Kicked {u}")
                self._msg_frame.SetStatusText(f"Kicked {u}")
            wx.CallAfter(_on_kicked)
        except Exception as e:
            log.error("Failed to kick member: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to kick member:\n{e}",
                "Kick Member",
            )

    def _on_edit_title(self, event):
        from .theme import apply_theme

        if not self._is_group_or_channel():
            wx.MessageBox(
                "Select a group or channel first.",
                "Edit Title",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        current_title = (
            getattr(self._current_entity, "title", "") or ""
        )
        dlg = wx.TextEntryDialog(
            self,
            "Enter new group title:",
            "Edit Title",
            current_title,
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        new_title = dlg.GetValue().strip()
        dlg.Destroy()
        if not new_title:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._edit_title_thread,
            args=(entity, new_title),
            daemon=True,
        ).start()

    def _edit_title_thread(self, entity, new_title):
        try:
            self.tg.submit_wait(self.tg.edit_chat_title(entity, new_title))
            def _on_title_changed(t=new_title):
                self.SetStatusText(f"Title changed to: {t}")
                self._msg_frame.SetStatusText(f"Title changed to: {t}")
            wx.CallAfter(_on_title_changed)
            wx.CallAfter(self._load_dialogs)
        except Exception as e:
            log.error("Failed to edit title: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to edit title:\n{e}",
                "Edit Title",
            )

    # ------------------------------------------------------------ Other

    def _show_error(self, message, title="Error"):
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR, parent)

    def _on_about(self, event):
        wx.MessageBox(
            "Teepee v2516.2\n\nThe simple, speedy Telegram client with the blind in mind.",
            "About Teepee",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _on_shortcuts(self, event):
        shortcuts = (
            "Navigation:\n"
            "  Ctrl+1: Focus chat list\n"
            "  Ctrl+2: Focus message list\n"
            "  Ctrl+3: Focus message input\n\n"
            "Messaging:\n"
            "  Enter: Open selected chat (in chat list) or send message (in input field)\n"
            "  Shift+Enter: New line in message\n"
            "  Ctrl+R: Reply to selected message\n"
            "  Escape: Cancel reply or close chat view\n"
            "  Delete: Delete selected message or chat\n\n"
            "Calls:\n"
            "  Ctrl+Shift+C: Start voice call\n"
            "  Ctrl+Shift+H: Hang up\n\n"
            "Voice:\n"
            "  Press the Voice button to start recording, press Stop to send\n\n"
            "Other:\n"
            "  Ctrl+,: Settings\n"
            "  Alt+F4: Minimize to system tray\n"
            "  Ctrl+Q: Quit\n\n"
            "Tip: Press the Applications key or Shift+F10 on a chat to mute, unmute, or delete it."
        )
        wx.MessageBox(
            shortcuts,
            "Keyboard Shortcuts",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _on_exit(self, event):
        self.quit()

    def _on_close(self, event):
        if sys.platform == "win32" and event.CanVeto() and not self._force_quit:
            event.Veto()
            self._minimize_to_tray()
            return
        self._cleanup_and_destroy()

    def _minimize_to_tray(self):
        if not self._tray_icon:
            self._tray_icon = TeepeeTaskBarIcon(self)
        self._msg_frame_was_shown = self._msg_frame.IsShown()
        if self._msg_frame_was_shown:
            self._msg_frame.Hide()
        self.Hide()
        try:
            self._tray_icon.ShowBalloon(
                "Teepee",
                "Teepee is still running in the system tray.",
            )
        except Exception:
            pass

    def restore_from_tray(self):
        self.Show()
        self.Restore()
        self.Raise()
        if self._msg_frame_was_shown:
            self._msg_frame.Show()
            self._msg_frame.Raise()
        if self._tray_icon:
            self._tray_icon.RemoveIcon()
            self._tray_icon.Destroy()
            self._tray_icon = None
        if self._msg_frame_was_shown:
            self.message_panel.messages_list.SetFocus()
        else:
            self.chat_list.list_ctrl.SetFocus()

    def quit(self):
        self._force_quit = True
        self.Close()

    def _cleanup_and_destroy(self):
        self._restore_timer.Stop()
        if self._tray_icon:
            self._tray_icon.RemoveIcon()
            self._tray_icon.Destroy()
            self._tray_icon = None
        signal_file = self.config.data_dir / ".restore"
        signal_file.unlink(missing_ok=True)
        self.voice.cleanup()
        self.tg.stop()
        self.Destroy()

    def _on_restore_timer(self, event):
        signal_file = self.config.data_dir / ".restore"
        if signal_file.exists():
            signal_file.unlink(missing_ok=True)
            if not self.IsShown():
                self.restore_from_tray()
            else:
                self.Raise()
