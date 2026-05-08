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
    CreateChannelDialog,
    CreateGroupDialog,
    NewChatDialog,
    PhoneDialog,
    TwoFactorDialog,
)
from .chat_list import ChatListPanel
from .message_frame import MessageFrame
from .settings_dialog import SettingsDialog
from .announce import (
    announce,
    set_announcements_enabled,
    set_announcement_preferences,
)

log = logging.getLogger(__name__)


class DeleteScopeDialog(wx.Dialog):
    def __init__(self, parent, title, message):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(wx.StaticText(self, label=message), flag=wx.ALL, border=10)

        self.for_me = wx.RadioButton(
            self, label="Delete for &me only", style=wx.RB_GROUP
        )
        self.for_me.SetName("Delete for me only")
        self.for_everyone = wx.RadioButton(
            self, label="Delete for &everyone"
        )
        self.for_everyone.SetName("Delete for everyone")
        self.for_me.SetValue(True)

        sizer.Add(self.for_me, flag=wx.LEFT | wx.RIGHT, border=10)
        sizer.Add(
            self.for_everyone,
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=5,
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
        self.for_me.SetFocus()

        from .theme import apply_theme

        apply_theme(self)

    def GetRevoke(self):
        return self.for_everyone.GetValue()


class IncomingCallDialog(wx.Dialog):
    ACCEPT = wx.ID_YES
    DECLINE = wx.ID_NO

    def __init__(self, parent, caller_name, video=False):
        title = "Incoming Video Call" if video else "Incoming Call"
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        call_type = "video call" if video else "call"
        label = wx.StaticText(
            self, label=f"Incoming {call_type} from {caller_name}"
        )
        sizer.Add(label, flag=wx.ALL, border=10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.accept_btn = wx.Button(self, id=self.ACCEPT, label="&Accept")
        self.accept_btn.SetName("Accept")
        self.accept_btn.SetToolTip("Accept the incoming call")
        self.decline_btn = wx.Button(self, id=self.DECLINE, label="&Decline")
        self.decline_btn.SetName("Decline")
        self.decline_btn.SetToolTip("Decline the incoming call")
        btn_sizer.Add(self.accept_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.decline_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
        self.accept_btn.SetFocus()

        self.accept_btn.Bind(wx.EVT_BUTTON, self._on_accept)
        self.decline_btn.Bind(wx.EVT_BUTTON, self._on_decline)

        from .theme import apply_theme

        apply_theme(self)

    def _on_accept(self, event):
        self.EndModal(self.ACCEPT)

    def _on_decline(self, event):
        self.EndModal(self.DECLINE)


class InCallDialog(wx.Dialog):
    def __init__(self, parent, hang_up_callback, mute_callback):
        super().__init__(
            parent,
            title="In Call",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
        )
        self._muted = False
        self._hang_up_callback = hang_up_callback
        self._mute_callback = mute_callback

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label="Call in progress")
        sizer.Add(label, flag=wx.ALL, border=10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mute_btn = wx.Button(self, label="&Mute")
        self.mute_btn.SetName("Mute")
        self.mute_btn.SetToolTip("Mute your microphone")
        self.hangup_btn = wx.Button(self, label="&Hang Up")
        self.hangup_btn.SetName("Hang Up")
        self.hangup_btn.SetToolTip("End the call")
        btn_sizer.Add(self.mute_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.hangup_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
        self.hangup_btn.SetFocus()

        self.mute_btn.Bind(wx.EVT_BUTTON, self._on_mute)
        self.hangup_btn.Bind(wx.EVT_BUTTON, self._on_hangup)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        from .theme import apply_theme

        apply_theme(self)

    def _on_mute(self, event):
        self._muted = not self._muted
        if self._muted:
            self.mute_btn.SetLabel("Un&mute")
            self.mute_btn.SetName("Unmute")
            self.mute_btn.SetToolTip("Unmute your microphone")
        else:
            self.mute_btn.SetLabel("&Mute")
            self.mute_btn.SetName("Mute")
            self.mute_btn.SetToolTip("Mute your microphone")
        self._mute_callback(self._muted)

    def _on_hangup(self, event):
        self._hang_up_callback()
        self.Destroy()

    def _on_close(self, event):
        self._hang_up_callback()
        self.Destroy()


class MemberPermissionsDialog(wx.Dialog):
    def __init__(self, parent, member_name):
        super().__init__(
            parent,
            title=f"Permissions - {member_name}",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(self, label="Allowed actions for this member:"),
            flag=wx.ALL,
            border=10,
        )

        self.send_messages = wx.CheckBox(self, label="Send &messages")
        self.send_media = wx.CheckBox(self, label="Send &media")
        self.send_stickers = wx.CheckBox(self, label="Send s&tickers")
        self.send_polls = wx.CheckBox(self, label="Send &polls")
        self.change_info = wx.CheckBox(self, label="Change group &info")
        self.invite_users = wx.CheckBox(self, label="&Invite users")
        self.pin_messages = wx.CheckBox(self, label="&Pin messages")

        for checkbox in (
            self.send_messages,
            self.send_media,
            self.send_stickers,
            self.send_polls,
            self.change_info,
            self.invite_users,
            self.pin_messages,
        ):
            checkbox.SetValue(True)
            sizer.Add(checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.CenterOnParent()
        self.send_messages.SetFocus()

        from .theme import apply_theme

        apply_theme(self)

    def GetPermissions(self):
        return {
            "send_messages": self.send_messages.GetValue(),
            "send_media": self.send_media.GetValue(),
            "send_stickers": self.send_stickers.GetValue(),
            "send_polls": self.send_polls.GetValue(),
            "change_info": self.change_info.GetValue(),
            "invite_users": self.invite_users.GetValue(),
            "pin_messages": self.pin_messages.GetValue(),
        }


def _make_tray_icon():
    """Create a simple 16x16 tray icon with a 'T' on a blue background."""
    bmp = wx.Bitmap(16, 16)
    dc = wx.MemoryDC(bmp)
    bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
    fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT)
    dc.SetBackground(wx.Brush(bg))
    dc.Clear()
    dc.SetTextForeground(fg)
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
        self._read_outbox_max_id = 0
        self._dialogs = []
        self._shown_msg_ids = set()
        self._muted_chats = {}
        self._blocked_users = set()
        self._pending_chat_focus = False
        self._media_cache = {}
        self._ringing_stream = None
        self._call_out_stream = None
        self._in_call_dlg = None

        self._create_ui()
        self._create_menu()
        self._create_status_bar()

        self._force_quit = False
        self._tray_icon = None

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)

        self.tg.on_new_message = self._on_incoming_message
        self.tg.on_message_sent = self._on_message_sent
        self.tg.on_message_edited = self._on_remote_message_edited
        self.tg.on_message_read = self._on_outbox_read
        self.tg.on_incoming_call = self._on_incoming_call

        self.calls.on_call_state_changed = self._on_call_state

        set_announcements_enabled(self.config.get("announcements_enabled", False))
        backend_pref = self.config.get("announcement_backend", "auto")
        set_announcement_preferences(
            auto_best=(not backend_pref or str(backend_pref).lower() == "auto"),
            backend_name="" if not backend_pref else str(backend_pref),
            voice_index=self.config.get("announcement_voice_index", -1),
        )

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
        self._account_id = wx.NewIdRef()
        file_menu.Append(
            self._account_id,
            "My &Account...",
            "View and edit your Telegram account settings",
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
        chat_menu.AppendSeparator()
        self._block_id = wx.NewIdRef()
        chat_menu.Append(
            self._block_id,
            "&Block User",
            "Block the user in the selected chat",
        )
        self._unblock_id = wx.NewIdRef()
        chat_menu.Append(
            self._unblock_id,
            "U&nblock User",
            "Unblock the user in the selected chat",
        )
        self._report_id = wx.NewIdRef()
        chat_menu.Append(
            self._report_id,
            "&Report User...",
            "Report the user in the selected chat",
        )
        menubar.Append(chat_menu, "&Chat")

        tools_menu = wx.Menu()
        self._call_id = wx.NewIdRef()
        tools_menu.Append(
            self._call_id, "Voice &Call\tCtrl+Shift+C", "Start a voice call"
        )
        self._video_call_id = wx.NewIdRef()
        tools_menu.Append(
            self._video_call_id, "&Video Call\tCtrl+Shift+V", "Start a video call"
        )
        self._hangup_id = wx.NewIdRef()
        tools_menu.Append(
            self._hangup_id, "&Hang Up\tCtrl+Shift+H", "End the current call"
        )
        menubar.Append(tools_menu, "&Tools")

        group_menu = wx.Menu()
        self._create_group_id = wx.NewIdRef()
        group_menu.Append(
            self._create_group_id,
            "Create &Group...",
            "Create a new group chat",
        )
        self._create_channel_id = wx.NewIdRef()
        group_menu.Append(
            self._create_channel_id,
            "Create C&hannel...",
            "Create a new channel",
        )
        group_menu.AppendSeparator()
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
        self._invite_link_id = wx.NewIdRef()
        group_menu.Append(
            self._invite_link_id,
            "Generate Invite &Link",
            "Create and copy an invite link for the selected group or channel",
        )
        group_menu.AppendSeparator()
        self._invite_id = wx.NewIdRef()
        group_menu.Append(
            self._invite_id,
            "&Invite User...",
            "Invite a user to the selected group or channel",
        )
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
        self._update_id = wx.NewIdRef()
        help_menu.Append(
            self._update_id,
            "Check for &Updates...",
            "Check for a newer version of Teepee",
        )
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, "&About Teepee")
        menubar.Append(help_menu, "&Help")

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_account, id=self._account_id)
        self.Bind(wx.EVT_MENU, self._on_mute_chat, id=self._mute_id)
        self.Bind(wx.EVT_MENU, self._on_unmute_chat, id=self._unmute_id)
        self.Bind(wx.EVT_MENU, self._on_block_user, id=self._block_id)
        self.Bind(wx.EVT_MENU, self._on_unblock_user, id=self._unblock_id)
        self.Bind(wx.EVT_MENU, self._on_report_user, id=self._report_id)
        self.Bind(wx.EVT_MENU, self._on_call, id=self._call_id)
        self.Bind(wx.EVT_MENU, self._on_video_call, id=self._video_call_id)
        self.Bind(wx.EVT_MENU, self._on_hangup, id=self._hangup_id)
        self.Bind(wx.EVT_MENU, self._on_settings, id=self._settings_id)
        self.Bind(wx.EVT_MENU, self._on_shortcuts, id=self._shortcuts_id)
        self.Bind(wx.EVT_MENU, self._on_about, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self._on_check_updates, id=self._update_id)
        self.Bind(wx.EVT_MENU, self._on_join_group, id=self._join_id)
        self.Bind(wx.EVT_MENU, self._on_leave_group, id=self._leave_id)
        self.Bind(wx.EVT_MENU, self._on_generate_invite_link, id=self._invite_link_id)
        self.Bind(wx.EVT_MENU, self._on_create_group, id=self._create_group_id)
        self.Bind(wx.EVT_MENU, self._on_create_channel, id=self._create_channel_id)
        self.Bind(wx.EVT_MENU, self._on_invite_user, id=self._invite_id)
        self.Bind(wx.EVT_MENU, self._on_view_members, id=self._members_id)
        self.Bind(wx.EVT_MENU, self._on_kick_member, id=self._kick_id)
        self.Bind(wx.EVT_MENU, self._on_edit_title, id=self._edit_title_id)

    def _create_status_bar(self):
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-3, -1])
        self.SetStatusText("Not connected")

    # ----------------------------------------------------------- Keyboard

    def _on_menu_open(self, event):
        menu = event.GetMenu()
        if not menu:
            event.Skip()
            return
        # Check if this menu contains our mute/unmute/block/unblock items
        mute_item = menu.FindItemById(self._mute_id.GetId())
        unmute_item = menu.FindItemById(self._unmute_id.GetId())
        block_item = menu.FindItemById(self._block_id.GetId())
        unblock_item = menu.FindItemById(self._unblock_id.GetId())
        if mute_item and unmute_item:
            dialog = self.chat_list.get_selected_dialog()
            if dialog:
                chat_id = getattr(dialog.entity, "id", None)
                is_muted = self._is_chat_muted(chat_id)
                mute_item.Enable(not is_muted)
                unmute_item.Enable(is_muted)
            else:
                mute_item.Enable(False)
                unmute_item.Enable(False)
        if block_item and unblock_item:
            from telethon.tl.types import User

            dialog = self.chat_list.get_selected_dialog()
            entity = dialog.entity if dialog else None
            if entity and isinstance(entity, User):
                user_id = getattr(entity, "id", None)
                is_blocked = user_id in self._blocked_users
                block_item.Enable(not is_blocked)
                unblock_item.Enable(is_blocked)
            else:
                block_item.Enable(False)
                unblock_item.Enable(False)
        event.Skip()

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
            if key == ord('4'):
                if self._msg_frame.IsShown():
                    self._msg_frame.Raise()
                    self._msg_frame.notebook.SetSelection(1)
                    self._msg_frame.files_panel.file_list.SetFocus()
                return
            if key == ord('5'):
                if self._msg_frame.IsShown():
                    self._msg_frame.Raise()
                    self._msg_frame.notebook.SetSelection(1)
                    self._msg_frame.files_panel.search_ctrl.SetFocus()
                return

        if event.ControlDown() and event.ShiftDown() and not event.AltDown():
            if key == ord("A"):
                if self._current_entity and self._msg_frame.IsShown():
                    self.message_panel._on_attach(event)
                return
            if key == ord("S"):
                if self._current_entity and self._msg_frame.IsShown():
                    self.save_selected_media()
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
        self._reconnect_timer_running = False
        self.SetStatusText("Connected")
        try:
            me = self.tg.submit_wait(self.tg.get_me())
            name = getattr(me, "first_name", "User") or "User"
            self.SetTitle(f"Teepee - {name}")
            self.SetStatusText(f"Logged in as {name}", 1)
            announce(f"Logged in as {name}")
        except Exception:
            pass
        self._load_dialogs()
        self._load_blocked_users()

        from ..updater import check_for_update_background
        check_for_update_background(self)

        # Start a periodic connection monitor
        if not hasattr(self, "_conn_timer"):
            self._conn_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_conn_check, self._conn_timer)
        self._conn_timer.Start(10000)  # check every 10 seconds

    def _on_conn_check(self, event):
        """Periodically verify the Telegram connection and reconnect if lost."""
        if self.tg.client and self.tg.client.is_connected():
            return
        if getattr(self, "_reconnect_timer_running", False):
            return
        self._reconnect_timer_running = True
        log.warning("Connection lost, attempting to reconnect...")
        self.SetStatusText("Reconnecting...")
        self._msg_frame.SetStatusText("Reconnecting...")
        announce("Connection lost. Reconnecting...")
        threading.Thread(target=self._reconnect_thread, daemon=True).start()

    def _reconnect_thread(self):
        import time
        for attempt in range(1, 13):  # try for up to ~2 minutes
            try:
                self.tg.submit_wait(self.tg.client.connect(), timeout=15)
                if self.tg.client.is_connected():
                    log.info("Reconnected on attempt %d", attempt)
                    wx.CallAfter(self._on_reconnected)
                    return
            except Exception as e:
                log.warning("Reconnect attempt %d failed: %s", attempt, e)
            time.sleep(10)
        wx.CallAfter(self._on_reconnect_failed)

    def _on_reconnected(self):
        self._reconnect_timer_running = False
        self.SetStatusText("Reconnected")
        self._msg_frame.SetStatusText("Reconnected")
        announce("Reconnected")
        self._load_dialogs()

    def _on_reconnect_failed(self):
        self._reconnect_timer_running = False
        self.SetStatusText("Disconnected")
        self._msg_frame.SetStatusText("Disconnected")
        announce("Could not reconnect. Use File menu or restart to try again.")

    def _on_connection_error(self, error):
        announce("Connection failed")
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
            dialogs = self.tg.submit_wait(self.tg.get_dialogs(limit=self.config.get("chat_limit", 100)))
            wx.CallAfter(self._on_dialogs_loaded, dialogs)
        except Exception as e:
            log.error("Failed to load dialogs: %s", e)
            wx.CallAfter(self.SetStatusText, f"Failed to load chats: {e}")
            wx.CallAfter(announce, f"Failed to load chats: {e}")

    def _on_dialogs_loaded(self, dialogs):
        self._dialogs = list(dialogs)
        self._update_muted_chats()
        self.chat_list.set_dialogs(self._dialogs, set(self._muted_chats.keys()))
        self.SetStatusText(f"{len(self._dialogs)} chats loaded")

    def _load_blocked_users(self):
        threading.Thread(target=self._load_blocked_thread, daemon=True).start()

    def _load_blocked_thread(self):
        try:
            blocked = self.tg.submit_wait(self.tg.get_blocked_users())
            wx.CallAfter(self._on_blocked_loaded, blocked)
        except Exception as e:
            log.error("Failed to load blocked users: %s", e)

    def _on_blocked_loaded(self, blocked):
        self._blocked_users = blocked

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
        name = self._entity_display_name(entity)
        self._msg_frame.SetTitle(f"{name} - Teepee")
        self._msg_frame.SetStatusText(f"Loading messages from {name}...")
        self._msg_frame.notebook.SetSelection(0)
        self._msg_frame.Show()
        self._msg_frame.Raise()
        self.message_panel.input_ctrl.SetFocus()
        self._pending_chat_focus = True
        self.SetStatusText(f"Loading messages from {name}...")
        self._load_dialogs()
        self._load_files_if_group(entity)
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
        self._msg_frame.notebook.SetSelection(0)
        self._msg_frame.Show()
        self._msg_frame.Raise()
        self.message_panel.input_ctrl.SetFocus()
        self._pending_chat_focus = True
        self.SetStatusText(f"Loading messages from {name}...")
        self._load_files_if_group(dialog.entity)
        threading.Thread(
            target=self._load_messages_thread,
            args=(dialog.entity,),
            daemon=True,
        ).start()

    def _load_messages_thread(self, entity):
        try:
            log.info("Loading messages for entity %s", getattr(entity, "id", entity))
            messages = self.tg.submit_wait(
                self.tg.get_messages(entity, limit=self.config.get("message_limit", 50))
            )
            log.info("Loaded %d messages", len(messages))
            try:
                read_outbox_max_id = self.tg.submit_wait(
                    self.tg.get_read_outbox_max_id(entity)
                )
            except Exception:
                read_outbox_max_id = 0
            try:
                self.tg.submit_wait(self.tg.mark_as_read(entity))
            except Exception:
                pass
            wx.CallAfter(self._on_messages_loaded, list(messages), entity, read_outbox_max_id)
        except Exception as e:
            log.error("Failed to load messages: %s", e, exc_info=True)
            self._pending_chat_focus = False
            wx.CallAfter(self.SetStatusText, f"Failed to load messages: {e}")
            wx.CallAfter(self._msg_frame.SetStatusText, f"Failed to load messages: {e}")
            wx.CallAfter(announce, f"Failed to load messages: {e}")

    def _on_messages_loaded(self, messages, entity, read_outbox_max_id=0):
        if entity != self._current_entity:
            log.warning("Entity mismatch in _on_messages_loaded, ignoring")
            return
        log.info("Displaying %d messages", len(messages))
        self._current_messages = messages
        self._read_outbox_max_id = read_outbox_max_id
        self.message_panel.display_messages(messages, read_outbox_max_id)
        # Show inline buttons for the last message if it has markup
        if messages:
            self.message_panel.update_inline_buttons(messages[0])
            last_msg = messages[0]
            if last_msg.voice:
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected voice message"
                )
            elif last_msg.audio or self._is_audio_document(last_msg):
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected audio file"
                )
            elif last_msg.video or last_msg.video_note:
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected video"
                )
            else:
                self.message_panel.show_play_button(False)
            self.message_panel.show_stop_button(False)
            self.message_panel.show_save_button(
                self._has_downloadable_media(last_msg)
            )
            self.message_panel.show_open_link_button(
                bool(self._extract_urls(last_msg.text))
            )
        else:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)
            self.message_panel.show_stop_button(False)
            self.message_panel.show_save_button(False)
            self.message_panel.show_open_link_button(False)
        name = self._entity_display_name(entity)
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

    _AUDIO_EXTENSIONS = frozenset({
        ".wav", ".mp3", ".flac", ".aac", ".m4a", ".wma", ".ogg", ".opus",
    })

    @staticmethod
    def _is_audio_document(msg):
        """Return True if the message is a document with an audio file extension."""
        if not msg.document:
            return False
        for attr in getattr(msg.document, "attributes", []):
            name = getattr(attr, "file_name", None)
            if name:
                ext = os.path.splitext(name)[1].lower()
                if ext in MainFrame._AUDIO_EXTENSIONS:
                    return True
        return False

    def on_message_selected(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)
            self.message_panel.show_stop_button(False)
            self.message_panel.show_save_button(False)
            self.message_panel.show_open_link_button(False)
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if 0 <= msg_idx < len(self._current_messages):
            msg = self._current_messages[msg_idx]
            self.message_panel.update_inline_buttons(msg)
            if msg.voice:
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected voice message"
                )
            elif msg.audio or self._is_audio_document(msg):
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected audio file"
                )
            elif msg.video or msg.video_note:
                self.message_panel.show_play_button(
                    True, "&Play", "Play the selected video"
                )
            else:
                self.message_panel.show_play_button(False)
            self.message_panel.show_stop_button(False)
            self.message_panel.show_save_button(
                self._has_downloadable_media(msg)
            )
            self.message_panel.show_open_link_button(
                bool(self._extract_urls(msg.text))
            )
        else:
            self.message_panel.update_inline_buttons(None)
            self.message_panel.show_play_button(False)
            self.message_panel.show_stop_button(False)
            self.message_panel.show_save_button(False)
            self.message_panel.show_open_link_button(False)

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
                    self.tg.get_messages(entity, limit=self.config.get("message_limit", 50))
                )
                wx.CallAfter(
                    self._on_messages_loaded, list(messages), entity,
                    self._read_outbox_max_id,
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
        self._current_messages.insert(0, msg)
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
        self.on_message_selected()
        self.chat_list.update_chat_preview(
            data["chat_id"], msg, increment_unread=False
        )
        if data["reply_to_msg_id"]:
            self.sound.play_reply_sent()
        else:
            self.sound.play_sent()
        self.SetStatusText("Message sent")
        self._msg_frame.SetStatusText("Message sent")
        announce("Message sent")

    def send_file(self, file_path, reply_to=None, caption=""):
        if not self._current_entity:
            return
        entity = self._current_entity
        name = os.path.basename(file_path)
        self.SetStatusText(f"Sending {name}...")
        self._msg_frame.SetStatusText(f"Sending {name}...")
        threading.Thread(
            target=self._send_file_thread,
            args=(entity, file_path, reply_to, caption),
            daemon=True,
        ).start()

    def _send_file_thread(self, entity, file_path, reply_to=None, caption=""):
        try:
            msg = self.tg.submit_wait(
                self.tg.send_file(
                    entity,
                    file_path,
                    reply_to=reply_to,
                    caption=caption,
                    force_document=True,
                )
            )
            wx.CallAfter(self._on_send_success, entity, msg)
        except Exception as e:
            log.error("Failed to send file: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to send file:\n{e}",
            )
            wx.CallAfter(self.SetStatusText, "Ready")
            wx.CallAfter(self._msg_frame.SetStatusText, "Ready")

    # ---------------------------------------------------------- Stickers

    def send_sticker_dialog(self):
        if not self._current_entity:
            return
        from .theme import apply_theme

        parent = self._msg_frame if self._msg_frame.IsShown() else self
        dlg = wx.Dialog(
            parent,
            title="Send Sticker",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(
                dlg,
                label="Search by text (e.g. smile, cat, love) or paste an emoji:",
            ),
            flag=wx.ALL,
            border=10,
        )
        emoji_ctrl = wx.TextCtrl(dlg, style=wx.TE_PROCESS_ENTER)
        emoji_ctrl.SetName("Search query")
        emoji_ctrl.SetToolTip(
            "Type words like smile or cat, or paste an emoji"
        )
        sizer.Add(emoji_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        search_btn = wx.Button(dlg, label="&Search")
        search_btn.SetName("Search stickers")
        search_btn.SetToolTip(
            "Search sticker sets by name, or find stickers for a specific emoji"
        )
        sizer.Add(search_btn, flag=wx.LEFT | wx.TOP, border=10)

        sizer.Add(
            wx.StaticText(dlg, label="Results:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        results_list = wx.ListBox(dlg, style=wx.LB_SINGLE)
        results_list.SetName("Sticker results")
        sizer.Add(results_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        dlg.SetSizerAndFit(sizer)
        dlg.SetMinSize((400, 350))
        dlg.CenterOnParent()
        emoji_ctrl.SetFocus()
        apply_theme(dlg)

        sticker_docs = []

        def _on_search(event):
            emoji = emoji_ctrl.GetValue().strip()
            if not emoji:
                announce("Enter text or an emoji to search stickers")
                self.SetStatusText("Enter text or an emoji to search stickers")
                self._msg_frame.SetStatusText(
                    "Enter text or an emoji to search stickers"
                )
                wx.MessageBox(
                    "Enter text or an emoji to search stickers.",
                    "Sticker Search",
                    wx.OK | wx.ICON_INFORMATION,
                    dlg,
                )
                return
            search_btn.Disable()
            results_list.Clear()
            sticker_docs.clear()
            threading.Thread(
                target=self._search_stickers_thread,
                args=(emoji, results_list, sticker_docs, search_btn, dlg),
                daemon=True,
            ).start()

        def _on_list_key(event):
            if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                dlg.EndModal(wx.ID_OK)
            else:
                event.Skip()

        search_btn.Bind(wx.EVT_BUTTON, _on_search)
        emoji_ctrl.Bind(wx.EVT_TEXT_ENTER, _on_search)
        results_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: dlg.EndModal(wx.ID_OK))
        results_list.Bind(wx.EVT_KEY_DOWN, _on_list_key)

        if dlg.ShowModal() == wx.ID_OK:
            sel = results_list.GetSelection()
            if sel != wx.NOT_FOUND and sel < len(sticker_docs):
                sticker = sticker_docs[sel]
                entity = self._current_entity
                reply_to = None
                if self.message_panel._reply_to_msg:
                    reply_to = self.message_panel._reply_to_msg.id
                self.message_panel.clear_reply()
                self.SetStatusText("Sending sticker...")
                self._msg_frame.SetStatusText("Sending sticker...")
                threading.Thread(
                    target=self._send_sticker_thread,
                    args=(entity, sticker, reply_to),
                    daemon=True,
                ).start()
        dlg.Destroy()

    def _search_stickers_thread(self, emoji, results_list, sticker_docs, search_btn, dlg):
        try:
            result = self.tg.submit_wait(self.tg.search_stickers(emoji))
            stickers = getattr(result, "stickers", [])
            items = []
            docs = []
            for doc in stickers[:50]:
                alt = ""
                name = ""
                set_name = ""
                for attr in getattr(doc, "attributes", []):
                    attr_name = type(attr).__name__
                    if attr_name == "DocumentAttributeSticker":
                        alt = getattr(attr, "alt", "") or ""
                        stickerset = getattr(attr, "stickerset", None)
                        if stickerset:
                            set_name = getattr(stickerset, "short_name", "") or ""
                    elif attr_name == "DocumentAttributeFilename":
                        name = getattr(attr, "file_name", "") or ""
                display = alt or name or f"Sticker {doc.id}"
                if set_name:
                    display = f"{display} ({set_name})"
                items.append(display)
                docs.append(doc)

            def _update():
                if not dlg:
                    return
                results_list.Clear()
                sticker_docs.clear()
                for item in items:
                    results_list.Append(item)
                sticker_docs.extend(docs)
                if results_list.GetCount() > 0:
                    results_list.SetSelection(0)
                search_btn.Enable()
                if items:
                    announce(f"{len(items)} stickers found")
                else:
                    announce("No stickers found")

            wx.CallAfter(_update)
        except Exception as e:
            log.error("Sticker search failed: %s", e)
            wx.CallAfter(search_btn.Enable)
            wx.CallAfter(announce, "Sticker search failed")

    def _send_sticker_thread(self, entity, sticker, reply_to=None):
        try:
            msg = self.tg.submit_wait(
                self.tg.send_sticker(entity, sticker, reply_to=reply_to)
            )
            wx.CallAfter(self._on_send_success, entity, msg)
        except Exception as e:
            log.error("Failed to send sticker: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to send sticker:\n{e}",
            )
            wx.CallAfter(self.SetStatusText, "Ready")
            wx.CallAfter(self._msg_frame.SetStatusText, "Ready")

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

    def edit_selected_message(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Select a message to edit.",
                "Edit Message",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        msg = self._current_messages[msg_idx]
        if not msg.out:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "You can only edit your own messages.",
                "Edit Message",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        if not msg.text:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Only text messages can be edited.",
                "Edit Message",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        from .theme import apply_theme

        parent = self._msg_frame if self._msg_frame.IsShown() else self
        dlg = wx.TextEntryDialog(
            parent,
            "Edit your message:",
            "Edit Message",
            msg.text,
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        new_text = dlg.GetValue().strip()
        dlg.Destroy()
        if not new_text or new_text == msg.text:
            return
        entity = self._current_entity
        threading.Thread(
            target=self._edit_message_thread,
            args=(entity, msg, msg_idx, idx, new_text),
            daemon=True,
        ).start()

    def _edit_message_thread(self, entity, msg, msg_idx, list_idx, new_text):
        try:
            self.tg.submit_wait(
                self.tg.edit_message(entity, msg.id, new_text)
            )
            wx.CallAfter(
                self._on_message_edited, msg, msg_idx, list_idx, new_text
            )
        except Exception as e:
            log.error("Failed to edit message: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to edit message:\n{e}"
            )

    def _on_message_edited(self, msg, msg_idx, list_idx, new_text):
        msg.text = new_text
        self.message_panel.update_message_at(list_idx, msg)
        self.message_panel.messages_list.SetSelection(list_idx)
        self.SetStatusText("Message edited")
        self._msg_frame.SetStatusText("Message edited")
        announce("Message edited")
        # Update chat preview if this is the latest message
        if msg_idx == 0 and self._current_entity:
            self.chat_list.update_chat_preview(
                getattr(self._current_entity, "id", None),
                msg,
                increment_unread=False,
            )

    def _on_remote_message_edited(self, data):
        msg = data.get("message")
        chat_id = data.get("chat_id")
        if not msg:
            return
        # Update the message in the open chat if it matches
        if self._current_entity:
            current_id = getattr(self._current_entity, "id", None)
            if current_id and chat_id == current_id:
                for i, m in enumerate(self._current_messages):
                    if m.id == msg.id:
                        self._current_messages[i] = msg
                        list_idx = len(self._current_messages) - 1 - i
                        self.message_panel.update_message_at(list_idx, msg)
                        break
        # Update chat preview if edited message is the latest
        self.chat_list.update_chat_preview(
            chat_id, msg, increment_unread=False
        )

    def _on_outbox_read(self, data):
        chat_id = data.get("chat_id")
        max_id = data.get("max_id", 0)
        if not self._current_entity:
            return
        current_id = getattr(self._current_entity, "id", None)
        if not current_id or chat_id != current_id:
            return
        # Update read_outbox_max_id and refresh affected messages
        if max_id > self._read_outbox_max_id:
            self._read_outbox_max_id = max_id
            self.message_panel._read_outbox_max_id = max_id
            # Update displayed strings for outgoing messages now marked as seen
            for i, msg in enumerate(self._current_messages):
                if msg.out and msg.id <= max_id:
                    list_idx = len(self._current_messages) - 1 - i
                    self.message_panel.update_message_at(list_idx, msg)

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
        with DeleteScopeDialog(
            parent, "Delete Message", "Delete this message?"
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            revoke = dlg.GetRevoke()
        entity = self._current_entity
        threading.Thread(
            target=self._delete_message_thread,
            args=(entity, msg, msg_idx, idx, revoke),
            daemon=True,
        ).start()

    def _delete_message_thread(self, entity, msg, msg_idx, list_idx, revoke):
        try:
            self.tg.submit_wait(
                self.tg.delete_messages(entity, [msg.id], revoke=revoke)
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
        self.on_message_selected()
        self.SetStatusText("Message deleted")
        self._msg_frame.SetStatusText("Message deleted")
        announce("Message deleted")

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
        with DeleteScopeDialog(
            self,
            "Delete Chat",
            f"Delete the entire chat with {name}?\n\nThis cannot be undone.",
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            revoke = dlg.GetRevoke()
        entity = dialog.entity
        threading.Thread(
            target=self._delete_chat_thread,
            args=(entity, revoke),
            daemon=True,
        ).start()

    def _delete_chat_thread(self, entity, revoke):
        try:
            self.tg.submit_wait(self.tg.delete_dialog(entity, revoke=revoke))
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
        announce("Chat deleted")
        self._load_dialogs()
        self.Raise()
        self.chat_list.list_ctrl.SetFocus()

    # ---------------------------------------------------- Voice messages

    def start_voice_recording(self):
        path = self.voice.start_recording()
        if not path:
            self.message_panel._recording = False
            self.message_panel.voice_btn.SetLabel("&Voice")
            self.message_panel.voice_btn.SetName("Voice")
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
            announce("Recording failed")

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
        announce("Voice message sent")
        self.sound.play_sent()

    def play_last_voice(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        media_msg = self._current_messages[msg_idx]
        if media_msg.voice:
            self.SetStatusText("Downloading voice message...")
            self._msg_frame.SetStatusText("Downloading voice message...")
            threading.Thread(
                target=self._play_voice_thread,
                args=(media_msg,),
                daemon=True,
            ).start()
        elif media_msg.audio or self._is_audio_document(media_msg):
            self.SetStatusText("Downloading audio...")
            self._msg_frame.SetStatusText("Downloading audio...")
            threading.Thread(
                target=self._play_media_thread,
                args=(media_msg, "audio"),
                daemon=True,
            ).start()
        elif media_msg.video or media_msg.video_note:
            self.SetStatusText("Downloading video...")
            self._msg_frame.SetStatusText("Downloading video...")
            threading.Thread(
                target=self._play_media_thread,
                args=(media_msg, "video"),
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
            wx.CallAfter(announce, "Failed to download voice")

    def _play_voice_file(self, path, label="voice message"):
        self.voice.play_voice(path)
        self.message_panel.show_stop_button(True)
        self.SetStatusText(f"Playing {label}...")
        self._msg_frame.SetStatusText(f"Playing {label}...")
        announce(f"Playing {label}")

    def stop_voice_playback(self):
        self.voice.stop_playback()
        self.message_panel.show_stop_button(False)
        self.SetStatusText("Playback stopped")
        self._msg_frame.SetStatusText("Playback stopped")
        announce("Playback stopped")

    def _play_media_thread(self, msg, media_type):
        try:
            if msg.id in self._media_cache and os.path.exists(
                self._media_cache[msg.id]
            ):
                downloaded = self._media_cache[msg.id]
            else:
                dl_dir = self.voice.download_dir + os.sep
                downloaded = self.tg.submit_wait(
                    self.tg.download_media(msg, dl_dir)
                )
                if downloaded:
                    self._media_cache[msg.id] = downloaded
            if not downloaded:
                wx.CallAfter(self.SetStatusText, "Download failed")
                wx.CallAfter(
                    self._msg_frame.SetStatusText, "Download failed"
                )
                wx.CallAfter(announce, "Download failed")
                return
            if media_type == "video":
                wx.CallAfter(self._open_video_file, downloaded)
            else:
                wx.CallAfter(self._play_voice_file, downloaded, "audio")
        except Exception as e:
            log.error("Failed to download %s: %s", media_type, e)
            wx.CallAfter(
                self.SetStatusText,
                f"Failed to download {media_type}",
            )
            wx.CallAfter(
                self._msg_frame.SetStatusText,
                f"Failed to download {media_type}",
            )

    def _open_video_file(self, path):
        self.SetStatusText("Opening video...")
        self._msg_frame.SetStatusText("Opening video...")
        announce("Opening video")
        try:
            os.startfile(path)
        except Exception as e:
            log.error("Failed to open video: %s", e)
            self._show_error(f"Failed to open video:\n{e}")

    # -------------------------------------------------- Download / Save

    @staticmethod
    def _has_downloadable_media(msg):
        return bool(
            msg.voice
            or msg.audio
            or msg.video
            or msg.video_note
            or msg.photo
            or msg.document
        )

    @staticmethod
    def _suggested_filename(msg):
        if msg.document:
            for attr in getattr(msg.document, "attributes", []):
                name = getattr(attr, "file_name", None)
                if name:
                    return name
        if msg.voice:
            return f"voice_{msg.id}.ogg"
        if msg.audio:
            return f"audio_{msg.id}.mp3"
        if msg.video or msg.video_note:
            return f"video_{msg.id}.mp4"
        if msg.photo:
            return f"photo_{msg.id}.jpg"
        return f"file_{msg.id}"

    def save_selected_media(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "Select a message with media to save.",
                "Save",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        msg = self._current_messages[msg_idx]
        if not self._has_downloadable_media(msg):
            parent = self._msg_frame if self._msg_frame.IsShown() else self
            wx.MessageBox(
                "The selected message has no downloadable media.",
                "Save",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        suggested = self._suggested_filename(msg)
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        with wx.FileDialog(
            parent,
            "Save file",
            defaultFile=suggested,
            wildcard="All files (*.*)|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            save_path = dlg.GetPath()
        self.SetStatusText("Downloading...")
        self._msg_frame.SetStatusText("Downloading...")
        threading.Thread(
            target=self._save_media_thread,
            args=(msg, save_path),
            daemon=True,
        ).start()

    def _save_media_thread(self, msg, save_path):
        try:
            result = self.tg.submit_wait(
                self.tg.download_media(msg, save_path)
            )
            if result:
                name = os.path.basename(save_path)
                wx.CallAfter(self.SetStatusText, f"Saved {name}")
                wx.CallAfter(
                    self._msg_frame.SetStatusText, f"Saved {name}"
                )
                wx.CallAfter(announce, f"Saved {name}")
            else:
                wx.CallAfter(self.SetStatusText, "Download failed")
                wx.CallAfter(
                    self._msg_frame.SetStatusText, "Download failed"
                )
                wx.CallAfter(announce, "Download failed")
        except Exception as e:
            log.error("Failed to save media: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to save file:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")
            wx.CallAfter(self._msg_frame.SetStatusText, "Ready")

    # --------------------------------------------------- Real-time events

    def _on_incoming_message(self, data):
        chat_id = data.get("chat_id")
        # Telethon event.chat_id is negative for groups/channels (e.g.
        # -1001234567890) but entity.id stored in _muted_chats is always
        # positive.  Strip the -100 prefix so the mute lookup matches.
        if chat_id and chat_id < 0:
            positive_id = int(str(chat_id).lstrip("-").removeprefix("100"))
            muted = self._is_chat_muted(chat_id) or self._is_chat_muted(positive_id)
        else:
            muted = self._is_chat_muted(chat_id)
        if not muted:
            is_reply = bool(data.get("reply_to_msg_id"))
            if data.get("is_group"):
                self.sound.play_group_received()
            elif data.get("is_channel"):
                self.sound.play_channel_received()
            elif is_reply:
                self.sound.play_reply_received()
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
        if data.get("is_group"):
            chat_type = "group"
        elif data.get("is_channel"):
            chat_type = "channel"
        else:
            chat_type = "chat"
        status = f"New message in {chat_type} from {sender}: {preview}"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        if not muted:
            announce(status)
        if not muted and self.config.get("notify_when_minimized", True):
            if not self.IsShown() or self.IsIconized():
                try:
                    title = f"{sender} ({chat_type})"
                    notif = wx.adv.NotificationMessage(title, preview, self)
                    notif.SetFlags(wx.ICON_INFORMATION)
                    notif.Show()
                except Exception:
                    pass
        if self._current_entity:
            current_id = getattr(self._current_entity, "id", None)
            if current_id and data["chat_id"] == current_id:
                msg = data.get("message")
                if msg:
                    self._current_messages.insert(0, msg)
                self.message_panel.append_new_message(data)
                self.on_message_selected()
                # Mark as read since the chat is currently open,
                # then reload dialogs so the unread count clears.
                entity = self._current_entity
                threading.Thread(
                    target=self._mark_read_and_reload_thread,
                    args=(entity,),
                    daemon=True,
                ).start()
                return
        msg = data.get("message")
        chat_id = data.get("chat_id")
        if not msg or not self.chat_list.update_chat_preview(chat_id, msg):
            self._load_dialogs()

    def _mark_read_and_reload_thread(self, entity):
        try:
            self.tg.submit_wait(self.tg.mark_as_read(entity))
        except Exception:
            pass
        wx.CallAfter(self._load_dialogs)

    def _on_message_sent(self, data):
        # Sent messages are already shown by _on_send_success;
        # this handler catches messages sent from other sessions.
        msg = data.get("message")
        if msg and msg.id in self._shown_msg_ids:
            return
        if self._current_entity:
            current_id = getattr(self._current_entity, "id", None)
            if current_id and data["chat_id"] == current_id:
                if msg:
                    self._current_messages.insert(0, msg)
                self.message_panel.append_new_message(data)
                self.on_message_selected()
        msg = data.get("message")
        chat_id = data.get("chat_id")
        if msg:
            self.chat_list.update_chat_preview(
                chat_id, msg, increment_unread=False
            )

    # ------------------------------------------------------------ Calls

    def _on_call(self, event):
        self._start_call(video=False)

    def _on_video_call(self, event):
        self._start_call(video=True)

    def _start_call(self, video=False):
        # Prefer the chat list selection when the message frame is hidden,
        # because _current_entity may be stale from a previously closed chat.
        entity = None
        if self._msg_frame.IsShown():
            entity = self._current_entity
        if not entity:
            dialog = self.chat_list.get_selected_dialog()
            if dialog:
                entity = dialog.entity
        if not entity:
            wx.MessageBox(
                "Select a chat first.",
                "Call",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self._call_out_stream = self.sound.play_call_out()
        call_type = "Video call" if video else "Calling"
        status = f"{call_type}..."
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status)
        self._show_in_call_dialog(None)
        threading.Thread(
            target=self._request_call_thread,
            args=(entity, video),
            daemon=True,
        ).start()

    def _request_call_thread(self, entity, video=False):
        try:
            result = self.tg.submit_wait(
                self.calls.request_call(entity, video=video), timeout=90,
            )
            if not result:
                wx.CallAfter(self._on_outgoing_call_failed, "Call was not accepted")
        except Exception as e:
            log.error("Call failed: %s", e)
            wx.CallAfter(self._on_outgoing_call_failed, str(e))

    def _on_outgoing_call_failed(self, error):
        if self._call_out_stream:
            self.sound.stop_stream(self._call_out_stream)
            self._call_out_stream = None
        dlg = getattr(self, "_in_call_dlg", None)
        if dlg is not None:
            try:
                dlg.Destroy()
            except Exception:
                pass
            self._in_call_dlg = None
        msg = f"Call failed: {error}"
        self.SetStatusText(msg)
        self._msg_frame.SetStatusText(msg)
        announce(msg, interrupt=True)

    def _on_hangup(self, event):
        if self.calls.in_call:
            threading.Thread(
                target=self._hangup_thread, daemon=True
            ).start()
        else:
            self.SetStatusText("No active call")
            self._msg_frame.SetStatusText("No active call")
            announce("No active call")

    def _hangup_thread(self):
        try:
            self.tg.submit_wait(self.calls.discard_call())
        except Exception as e:
            log.error("Hangup failed: %s", e)

    def _on_incoming_call(self, phone_call, caller_name):
        is_video = getattr(phone_call, "video", False)
        self._ringing_stream = self.sound.play_call_in()
        call_type = "video call" if is_video else "call"
        status = f"Incoming {call_type} from {caller_name}"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status, interrupt=True)

        parent = self._msg_frame if self._msg_frame.IsShown() else self
        with IncomingCallDialog(parent, caller_name, video=is_video) as dlg:
            result = dlg.ShowModal()

        self.sound.stop_stream(self._ringing_stream)
        self._ringing_stream = None

        if result == IncomingCallDialog.ACCEPT:
            self.SetStatusText("Accepting call...")
            self._msg_frame.SetStatusText("Accepting call...")
            threading.Thread(
                target=self._accept_call_thread,
                args=(phone_call, is_video),
                daemon=True,
            ).start()
        else:
            self.SetStatusText("Call declined")
            self._msg_frame.SetStatusText("Call declined")
            announce("Call declined")
            threading.Thread(
                target=self._decline_call_thread,
                args=(phone_call,),
                daemon=True,
            ).start()

    def _accept_call_thread(self, phone_call, video=False):
        try:
            result = self.tg.submit_wait(
                self.calls.accept_call(phone_call, video=video), timeout=45,
            )
            if result is None:
                wx.CallAfter(self.SetStatusText, "Call accept failed")
                wx.CallAfter(self._msg_frame.SetStatusText, "Call accept failed")
                wx.CallAfter(announce, "Call accept failed")
                return
            status = "Call connected"
            wx.CallAfter(self.SetStatusText, status)
            wx.CallAfter(self._msg_frame.SetStatusText, status)
            wx.CallAfter(announce, status)
            wx.CallAfter(self._show_in_call_dialog, phone_call)
        except Exception as e:
            log.error("Failed to accept call: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to accept call:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")
            wx.CallAfter(self._msg_frame.SetStatusText, "Ready")

    def _decline_call_thread(self, phone_call):
        try:
            from telethon.tl.functions.phone import DiscardCallRequest
            from telethon.tl.types import (
                InputPhoneCall,
                PhoneCallDiscardReasonBusy,
            )

            input_call = InputPhoneCall(
                id=phone_call.id,
                access_hash=phone_call.access_hash,
            )
            self.tg.submit_wait(
                self.tg.client(
                    DiscardCallRequest(
                        peer=input_call,
                        duration=0,
                        reason=PhoneCallDiscardReasonBusy(),
                        connection_id=0,
                    )
                )
            )
        except Exception as e:
            log.error("Failed to decline call: %s", e)

    def _show_in_call_dialog(self, phone_call):
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        self._in_call_dlg = InCallDialog(
            parent, self._hang_up, self._toggle_mute,
        )
        self._in_call_dlg.Show()

    def _hang_up(self):
        self.SetStatusText("Hanging up...")
        self._msg_frame.SetStatusText("Hanging up...")

        def _do_hang_up():
            try:
                self.tg.submit_wait(self.calls.discard_call())
            except Exception as e:
                log.error("Failed to hang up: %s", e)

        threading.Thread(target=_do_hang_up, daemon=True).start()

    def _toggle_mute(self, muted):
        def _do():
            try:
                if muted:
                    self.tg.submit_wait(self.calls.mute())
                    wx.CallAfter(self.SetStatusText, "Muted")
                    wx.CallAfter(self._msg_frame.SetStatusText, "Muted")
                    wx.CallAfter(announce, "Muted")
                else:
                    self.tg.submit_wait(self.calls.unmute())
                    wx.CallAfter(self.SetStatusText, "Unmuted")
                    wx.CallAfter(self._msg_frame.SetStatusText, "Unmuted")
                    wx.CallAfter(announce, "Unmuted")
            except Exception as e:
                log.error("Mute/unmute failed: %s", e)

        threading.Thread(target=_do, daemon=True).start()

    def _on_call_state(self, state, data):
        if state in ("connecting", "active", "ended", "error"):
            if self._call_out_stream:
                self.sound.stop_stream(self._call_out_stream)
                self._call_out_stream = None
        status_map = {
            "calling": "Calling...",
            "connecting": "Connecting call...",
            "active": "Call active",
            "ended": "Call ended",
            "error": f"Call error: {data}",
        }
        status = status_map.get(state, state)
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status)
        if state in ("ended", "error"):
            dlg = getattr(self, "_in_call_dlg", None)
            if dlg is not None:
                try:
                    dlg.Destroy()
                except Exception:
                    pass
                self._in_call_dlg = None

    # ---------------------------------------------------------- Settings

    def _on_settings(self, event):
        with SettingsDialog(self, self.config, self.sound) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.config["output_device_index"] = dlg.GetOutputDeviceIndex()
                self.config["input_device_index"] = dlg.GetInputDeviceIndex()
                self.config["camera_device_index"] = dlg.GetCameraDeviceIndex()
                self.config["sounds_enabled"] = dlg.GetSoundsEnabled()
                self.config["announcements_enabled"] = dlg.GetAnnouncementsEnabled()
                self.config["announcement_backend"] = dlg.GetAnnouncementBackend()
                self.config["announcement_voice_index"] = dlg.GetAnnouncementVoiceIndex()
                self.config["sound_pack"] = dlg.GetSoundPack()
                self.config["notify_when_minimized"] = dlg.GetNotifyWhenMinimized()
                self.config["time_format"] = dlg.GetTimeFormat()
                self.config["chat_limit"] = dlg.GetChatLimit()
                self.config["message_limit"] = dlg.GetMessageLimit()
                self.config["message_template"] = dlg.GetMessageTemplate()
                self.config.save()
                self.sound.set_output_device(dlg.GetOutputDeviceIndex())
                set_announcements_enabled(
                    self.config.get("announcements_enabled", False)
                )
                backend_pref = self.config.get("announcement_backend", "auto")
                set_announcement_preferences(
                    auto_best=(not backend_pref or str(backend_pref).lower() == "auto"),
                    backend_name="" if not backend_pref else str(backend_pref),
                    voice_index=self.config.get("announcement_voice_index", -1),
                )

    # ---------------------------------------------------- Account / Mute

    def _on_account(self, event):
        self.SetStatusText("Loading account data...")
        threading.Thread(
            target=self._load_account_thread, daemon=True
        ).start()

    def _load_account_thread(self):
        try:
            me = self.tg.submit_wait(self.tg.get_me())
            full = self.tg.submit_wait(self.tg.get_full_me())
            account_data = {
                "first_name": getattr(me, "first_name", "") or "",
                "last_name": getattr(me, "last_name", "") or "",
                "username": getattr(me, "username", "") or "",
                "phone": getattr(me, "phone", "") or "",
                "bio": getattr(full.full_user, "about", "") or "",
                "birthday": getattr(full.full_user, "birthday", None),
            }

            from telethon.tl.types import (
                InputPrivacyKeyChatInvite,
                InputPrivacyKeyForwards,
                InputPrivacyKeyPhoneCall,
                InputPrivacyKeyPhoneNumber,
                InputPrivacyKeyProfilePhoto,
                InputPrivacyKeyStatusTimestamp,
            )

            privacy_keys = {
                "privacy_last_seen": InputPrivacyKeyStatusTimestamp(),
                "privacy_phone": InputPrivacyKeyPhoneNumber(),
                "privacy_photo": InputPrivacyKeyProfilePhoto(),
                "privacy_forwards": InputPrivacyKeyForwards(),
                "privacy_calls": InputPrivacyKeyPhoneCall(),
                "privacy_groups": InputPrivacyKeyChatInvite(),
            }
            try:
                from telethon.tl.types import InputPrivacyKeyBirthday
                privacy_keys["privacy_birthday"] = InputPrivacyKeyBirthday()
            except ImportError:
                pass
            for key, tl_key in privacy_keys.items():
                try:
                    account_data[key] = self.tg.submit_wait(
                        self.tg.get_privacy_setting(tl_key)
                    )
                except Exception:
                    account_data[key] = 0

            try:
                account_data["account_ttl_days"] = self.tg.submit_wait(
                    self.tg.get_account_ttl()
                )
            except Exception:
                account_data["account_ttl_days"] = 180

            try:
                password = self.tg.submit_wait(self.tg.get_password_info())
                account_data["has_2fa"] = getattr(
                    password, "has_password", False
                )
            except Exception:
                account_data["has_2fa"] = False

            try:
                photos = self.tg.submit_wait(
                    self.tg.get_profile_photos()
                )
                account_data["photo_count"] = len(photos)
                account_data["photos"] = photos
            except Exception:
                account_data["photo_count"] = 0
                account_data["photos"] = []

            try:
                from datetime import datetime, timezone

                auths = self.tg.submit_wait(self.tg.get_authorizations())
                sessions = []
                for auth in auths.authorizations:
                    display = auth.app_name or "Unknown app"
                    if auth.app_version:
                        display += f" {auth.app_version}"
                    display += f" on {auth.device_model or 'Unknown device'}"
                    if auth.country:
                        display += f", {auth.country}"
                    date_active = auth.date_active
                    if isinstance(date_active, int):
                        date_active = datetime.fromtimestamp(
                            date_active, tz=timezone.utc
                        )
                    if date_active:
                        local_str = date_active.astimezone().strftime(
                            "%d %b %Y %H:%M"
                        )
                        display += f", active {local_str}"
                    if auth.current:
                        display += " (current session)"
                    sessions.append(
                        {
                            "display": display,
                            "hash": auth.hash,
                            "current": bool(auth.current),
                        }
                    )
                account_data["sessions"] = sessions
            except Exception:
                account_data["sessions"] = []

            wx.CallAfter(self._show_account_dialog, account_data)
        except Exception as e:
            log.error("Failed to load account data: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to load account:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _show_account_dialog(self, account_data):
        from .account_dialog import AccountDialog

        self.SetStatusText("Ready")
        with AccountDialog(self, account_data) as dlg:
            result = dlg.ShowModal()
            terminated = dlg.GetTerminatedSessions()
            changes = None
            if result == wx.ID_OK:
                changes = {
                    "first_name": dlg.GetFirstName(),
                    "last_name": dlg.GetLastName(),
                    "username": dlg.GetUsername(),
                    "bio": dlg.GetBio(),
                    "account_ttl_days": dlg.GetAccountTTLDays(),
                    "birthday": dlg.GetBirthday(),
                    "photo_to_upload": dlg.GetPhotoToUpload(),
                    "delete_current_photo": dlg.GetDeleteCurrentPhoto(),
                }
                changes.update(dlg.GetPrivacySettings())

        if terminated or changes is not None:
            self.SetStatusText("Updating account...")
            self._msg_frame.SetStatusText("Updating account...")
            threading.Thread(
                target=self._save_account_thread,
                args=(account_data, changes, terminated),
                daemon=True,
            ).start()

    def _save_account_thread(self, original, changes, terminated_sessions):
        try:
            for auth_hash in terminated_sessions:
                try:
                    self.tg.submit_wait(
                        self.tg.reset_authorization(auth_hash)
                    )
                except Exception as e:
                    log.error("Failed to terminate session: %s", e)

            if changes is None:
                if terminated_sessions:
                    wx.CallAfter(
                        self.SetStatusText, "Sessions terminated"
                    )
                    wx.CallAfter(
                        self._msg_frame.SetStatusText,
                        "Sessions terminated",
                    )
                return

            profile_kwargs = {}
            if changes["first_name"] != original["first_name"]:
                profile_kwargs["first_name"] = changes["first_name"]
            if changes["last_name"] != original["last_name"]:
                profile_kwargs["last_name"] = changes["last_name"]
            if changes["bio"] != original["bio"]:
                profile_kwargs["about"] = changes["bio"]
            if profile_kwargs:
                self.tg.submit_wait(
                    self.tg.update_profile(**profile_kwargs)
                )

            if changes["username"] != original["username"]:
                self.tg.submit_wait(
                    self.tg.update_username(changes["username"])
                )

            from telethon.tl.types import (
                InputPrivacyKeyChatInvite,
                InputPrivacyKeyForwards,
                InputPrivacyKeyPhoneCall,
                InputPrivacyKeyPhoneNumber,
                InputPrivacyKeyProfilePhoto,
                InputPrivacyKeyStatusTimestamp,
            )

            privacy_map = {
                "privacy_last_seen": InputPrivacyKeyStatusTimestamp(),
                "privacy_phone": InputPrivacyKeyPhoneNumber(),
                "privacy_photo": InputPrivacyKeyProfilePhoto(),
                "privacy_forwards": InputPrivacyKeyForwards(),
                "privacy_calls": InputPrivacyKeyPhoneCall(),
                "privacy_groups": InputPrivacyKeyChatInvite(),
            }
            try:
                from telethon.tl.types import InputPrivacyKeyBirthday
                privacy_map["privacy_birthday"] = InputPrivacyKeyBirthday()
            except ImportError:
                pass
            for key, tl_key in privacy_map.items():
                if changes.get(key) != original.get(key):
                    self.tg.submit_wait(
                        self.tg.set_privacy_setting(tl_key, changes[key])
                    )

            if changes["account_ttl_days"] != original.get(
                "account_ttl_days"
            ):
                self.tg.submit_wait(
                    self.tg.set_account_ttl(changes["account_ttl_days"])
                )

            birthday_change = changes.get("birthday")
            original_bday = original.get("birthday")
            if birthday_change is None and original_bday is not None:
                self.tg.submit_wait(self.tg.clear_birthday())
            elif birthday_change is not None:
                need_update = True
                if original_bday:
                    if (
                        birthday_change["day"]
                        == original_bday.day
                        and birthday_change["month"]
                        == original_bday.month
                        and birthday_change.get("year")
                        == getattr(original_bday, "year", None)
                    ):
                        need_update = False
                if need_update:
                    self.tg.submit_wait(
                        self.tg.set_birthday(
                            birthday_change["day"],
                            birthday_change["month"],
                            birthday_change.get("year"),
                        )
                    )

            if changes.get("photo_to_upload"):
                self.tg.submit_wait(
                    self.tg.upload_profile_photo(
                        changes["photo_to_upload"]
                    )
                )
            if changes.get("delete_current_photo"):
                photos = original.get("photos", [])
                if photos:
                    self.tg.submit_wait(
                        self.tg.delete_profile_photo(photos[0])
                    )

            if "first_name" in profile_kwargs:
                me = self.tg.submit_wait(self.tg.get_me())
                name = getattr(me, "first_name", "User") or "User"
                wx.CallAfter(self.SetTitle, f"Teepee - {name}")

            wx.CallAfter(self.SetStatusText, "Account updated")
            wx.CallAfter(
                self._msg_frame.SetStatusText, "Account updated"
            )
            wx.CallAfter(announce, "Account updated")
        except Exception as e:
            log.error("Failed to update account: %s", e)
            wx.CallAfter(
                self._show_error, f"Failed to update account:\n{e}"
            )
            wx.CallAfter(self.SetStatusText, "Ready")
            wx.CallAfter(self._msg_frame.SetStatusText, "Ready")

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
        announce("Chat muted")
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
        announce("Chat unmuted")
        self._load_dialogs()

    # ------------------------------------------------- Block / Report

    def _get_selected_user_entity(self, action_label):
        """Return the entity for the selected chat, or None if not a user."""
        dialog = self.chat_list.get_selected_dialog()
        if not dialog:
            wx.MessageBox(
                "Select a chat first.",
                action_label,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return None
        entity = dialog.entity
        from telethon.tl.types import User
        if not isinstance(entity, User):
            wx.MessageBox(
                "This action is only available for user chats.",
                action_label,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return None
        return entity

    def _on_block_user(self, event):
        entity = self._get_selected_user_entity("Block User")
        if not entity:
            return
        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        name = f"{first} {last}".strip() or "this user"
        result = wx.MessageBox(
            f"Block {name}? They will no longer be able to contact you.",
            "Block User",
            wx.YES_NO | wx.ICON_QUESTION,
            self,
        )
        if result != wx.YES:
            return
        threading.Thread(
            target=self._block_user_thread,
            args=(entity, name),
            daemon=True,
        ).start()

    def _block_user_thread(self, entity, name):
        try:
            self.tg.submit_wait(self.tg.block_user(entity))
            wx.CallAfter(self._on_block_done, name, entity)
        except Exception as e:
            log.error("Failed to block user: %s", e)
            wx.CallAfter(self._show_error, f"Failed to block user:\n{e}")

    def _on_block_done(self, name, entity):
        self._blocked_users.add(getattr(entity, "id", None))
        status = f"{name} blocked"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status)

    def _on_unblock_user(self, event):
        entity = self._get_selected_user_entity("Unblock User")
        if not entity:
            return
        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        name = f"{first} {last}".strip() or "this user"
        threading.Thread(
            target=self._unblock_user_thread,
            args=(entity, name),
            daemon=True,
        ).start()

    def _unblock_user_thread(self, entity, name):
        try:
            self.tg.submit_wait(self.tg.unblock_user(entity))
            wx.CallAfter(self._on_unblock_done, name, entity)
        except Exception as e:
            log.error("Failed to unblock user: %s", e)
            wx.CallAfter(self._show_error, f"Failed to unblock user:\n{e}")

    def _on_unblock_done(self, name, entity):
        self._blocked_users.discard(getattr(entity, "id", None))
        status = f"{name} unblocked"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status)

    def _on_report_user(self, event):
        entity = self._get_selected_user_entity("Report User")
        if not entity:
            return
        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        name = f"{first} {last}".strip() or "this user"

        from .theme import apply_theme

        parent = self._msg_frame if self._msg_frame.IsShown() else self
        dlg = wx.Dialog(
            parent,
            title=f"Report {name}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(dlg, label="Reason:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        reasons = [
            "Spam",
            "Violence",
            "Pornography",
            "Child abuse",
            "Illegal drugs",
            "Personal details shared",
            "Fake account",
            "Other",
        ]
        reason_choice = wx.Choice(dlg, choices=reasons)
        reason_choice.SetName("Report reason")
        reason_choice.SetSelection(0)
        sizer.Add(reason_choice, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(dlg, label="Additional details (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        details_ctrl = wx.TextCtrl(dlg, style=wx.TE_MULTILINE)
        details_ctrl.SetName("Additional details")
        sizer.Add(
            details_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10
        )

        btn_sizer = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        dlg.SetSizerAndFit(sizer)
        dlg.SetMinSize((400, 280))
        dlg.CenterOnParent()
        reason_choice.SetFocus()
        apply_theme(dlg)

        if dlg.ShowModal() == wx.ID_OK:
            reason_idx = reason_choice.GetSelection()
            details = details_ctrl.GetValue().strip()
            dlg.Destroy()
            threading.Thread(
                target=self._report_user_thread,
                args=(entity, name, reason_idx, details),
                daemon=True,
            ).start()
        else:
            dlg.Destroy()

    def _report_user_thread(self, entity, name, reason_idx, details):
        from telethon.tl.types import (
            InputReportReasonSpam,
            InputReportReasonViolence,
            InputReportReasonPornography,
            InputReportReasonChildAbuse,
            InputReportReasonIllegalDrugs,
            InputReportReasonPersonalDetails,
            InputReportReasonFake,
            InputReportReasonOther,
        )

        reason_map = {
            0: InputReportReasonSpam(),
            1: InputReportReasonViolence(),
            2: InputReportReasonPornography(),
            3: InputReportReasonChildAbuse(),
            4: InputReportReasonIllegalDrugs(),
            5: InputReportReasonPersonalDetails(),
            6: InputReportReasonFake(),
            7: InputReportReasonOther(),
        }
        reason = reason_map.get(reason_idx, InputReportReasonOther())
        try:
            self.tg.submit_wait(
                self.tg.report_user(entity, reason, message=details)
            )
            wx.CallAfter(self._on_report_done, name)
        except Exception as e:
            log.error("Failed to report user: %s", e)
            wx.CallAfter(self._show_error, f"Failed to report user:\n{e}")

    def _on_report_done(self, name):
        status = f"{name} reported"
        self.SetStatusText(status)
        self._msg_frame.SetStatusText(status)
        announce(status)

    def _is_chat_muted(self, chat_id):
        mute_until = self._muted_chats.get(chat_id)
        if not mute_until:
            return False
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        if isinstance(mute_until, (int, float)):
            return mute_until > now.timestamp()
        try:
            if mute_until.tzinfo is None:
                mute_until = mute_until.replace(tzinfo=timezone.utc)
            return mute_until > now
        except Exception:
            return False

    def _update_muted_chats(self):
        self._muted_chats.clear()
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        for d in self._dialogs:
            ns = getattr(d.dialog, "notify_settings", None)
            if not ns:
                continue
            chat_id = getattr(d.entity, "id", None)
            if not chat_id:
                continue
            # Check the silent flag (some Telethon versions use this)
            if getattr(ns, "silent", False):
                self._muted_chats[chat_id] = 2147483647
                continue
            mute_until = getattr(ns, "mute_until", None)
            if not mute_until:
                continue
            if isinstance(mute_until, (int, float)):
                if mute_until > now.timestamp():
                    self._muted_chats[chat_id] = mute_until
            else:
                try:
                    if mute_until.tzinfo is None:
                        mute_until = mute_until.replace(tzinfo=timezone.utc)
                    if mute_until > now:
                        self._muted_chats[chat_id] = mute_until
                except Exception:
                    pass

    # ------------------------------------------------------- Group Actions

    def _get_selected_group_or_channel_entity(self):
        # Prefer the chat list selection so menu actions work without opening
        # and closing the chat first (which would refresh _current_entity).
        dialog = self.chat_list.get_selected_dialog()
        if dialog and self._is_entity_group_or_channel(dialog.entity):
            return dialog.entity
        if self._current_entity and self._is_entity_group_or_channel(self._current_entity):
            return self._current_entity
        return None

    def _is_group_or_channel(self):
        return self._get_selected_group_or_channel_entity() is not None

    @staticmethod
    def _is_entity_group_or_channel(entity):
        from telethon.tl.types import Channel, Chat
        return isinstance(entity, (Channel, Chat))

    def _load_files_if_group(self, entity):
        files_panel = self._msg_frame.files_panel
        if self._is_entity_group_or_channel(entity):
            files_panel.set_entity(entity)
            files_panel.load_files(entity)
        else:
            files_panel.set_entity(None)

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
        announce(f"Joined {target}")
        self._load_dialogs()

    def _on_create_group(self, event):
        dlg = CreateGroupDialog(self)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        title = dlg.GetTitle()
        usernames_text = dlg.GetInviteUsernames()
        is_public = dlg.IsPublic()
        public_username = dlg.GetPublicUsername()
        dlg.Destroy()
        if not title:
            return
        if is_public and not public_username:
            wx.MessageBox(
                "Public groups require a public username.",
                "Create Group",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self.SetStatusText(f"Creating group {title}...")
        threading.Thread(
            target=self._create_group_thread,
            args=(title, usernames_text, is_public, public_username),
            daemon=True,
        ).start()

    def _create_group_thread(self, title, usernames_text, is_public, public_username):
        try:
            users = []
            if usernames_text:
                for u in usernames_text.split(","):
                    u = u.strip()
                    if u:
                        entity = self.tg.submit_wait(
                            self.tg.get_entity(u)
                        )
                        users.append(entity)
            if not users and not is_public:
                me = self.tg.submit_wait(self.tg.get_me())
                users.append(me)
            self.tg.submit_wait(
                self.tg.create_group(
                    title,
                    users,
                    is_public=is_public,
                    public_username=public_username,
                )
            )
            wx.CallAfter(self._on_group_created, title)
        except Exception as e:
            log.error("Failed to create group: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to create group:\n{e}",
                "Create Group",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_group_created(self, title):
        self.SetStatusText(f"Group '{title}' created")
        self._msg_frame.SetStatusText(f"Group '{title}' created")
        announce(f"Group {title} created")
        self._load_dialogs()

    def _on_create_channel(self, event):
        dlg = CreateChannelDialog(self)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        title = dlg.GetTitle()
        about = dlg.GetAbout()
        is_public = dlg.IsPublic()
        public_username = dlg.GetPublicUsername()
        dlg.Destroy()
        if not title:
            return
        if is_public and not public_username:
            wx.MessageBox(
                "Public channels require a public username.",
                "Create Channel",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self.SetStatusText(f"Creating channel {title}...")
        threading.Thread(
            target=self._create_channel_thread,
            args=(title, about, is_public, public_username),
            daemon=True,
        ).start()

    def _create_channel_thread(self, title, about, is_public, public_username):
        try:
            self.tg.submit_wait(
                self.tg.create_channel(
                    title,
                    about=about,
                    is_public=is_public,
                    public_username=public_username,
                )
            )
            wx.CallAfter(self._on_channel_created, title)
        except Exception as e:
            log.error("Failed to create channel: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to create channel:\n{e}",
                "Create Channel",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_channel_created(self, title):
        self.SetStatusText(f"Channel '{title}' created")
        self._msg_frame.SetStatusText(f"Channel '{title}' created")
        announce(f"Channel {title} created")
        self._load_dialogs()

    def _on_invite_user(self, event):
        from .theme import apply_theme

        entity = self._get_selected_group_or_channel_entity()
        if not entity:
            wx.MessageBox(
                "Select a group or channel first.",
                "Invite User",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        dlg = wx.TextEntryDialog(
            self,
            "Enter the username of the user to invite:",
            "Invite User",
        )
        apply_theme(dlg)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        username = dlg.GetValue().strip()
        dlg.Destroy()
        if not username:
            return
        self.SetStatusText(f"Inviting {username}...")
        threading.Thread(
            target=self._invite_user_thread,
            args=(entity, username),
            daemon=True,
        ).start()

    def _invite_user_thread(self, entity, username):
        try:
            user = self.tg.submit_wait(self.tg.get_entity(username))
            self.tg.submit_wait(
                self.tg.invite_to_channel(entity, [user])
            )
            def _on_invited(u=username):
                self.SetStatusText(f"Invited {u}")
                self._msg_frame.SetStatusText(f"Invited {u}")
                announce(f"Invited {u}")
            wx.CallAfter(_on_invited)
        except Exception as e:
            log.error("Failed to invite user: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to invite user:\n{e}",
                "Invite User",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_leave_group(self, event):
        entity = self._get_selected_group_or_channel_entity()
        if not entity:
            wx.MessageBox(
                "Select a group or channel first.",
                "Leave Group",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        name = (
            getattr(entity, "title", None)
            or getattr(entity, "username", None)
            or "this group"
        )
        if wx.MessageBox(
            f"Leave {name}?",
            "Confirm Leave",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            self,
        ) != wx.YES:
            return
        threading.Thread(
            target=self._leave_group_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _on_generate_invite_link(self, event):
        entity = self._get_selected_group_or_channel_entity()
        if not entity:
            wx.MessageBox(
                "Select a group or channel first.",
                "Invite Link",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self.SetStatusText("Generating invite link...")
        threading.Thread(
            target=self._generate_invite_link_thread,
            args=(entity,),
            daemon=True,
        ).start()

    def _generate_invite_link_thread(self, entity):
        try:
            link = self.tg.submit_wait(self.tg.export_invite_link(entity))
            wx.CallAfter(self._on_invite_link_generated, link)
        except Exception as e:
            log.error("Failed to generate invite link: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to generate invite link:\n{e}",
                "Invite Link",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_invite_link_generated(self, link):
        if not link:
            self._show_error("No invite link was returned.", "Invite Link")
            self.SetStatusText("Ready")
            return
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(link))
            wx.TheClipboard.Close()
        self.SetStatusText("Invite link copied to clipboard")
        self._msg_frame.SetStatusText("Invite link copied to clipboard")
        announce("Invite link copied to clipboard")
        wx.MessageBox(
            f"Invite link:\n{link}\n\nThe link has been copied to your clipboard.",
            "Invite Link",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

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
        announce("Left group")
        self._load_dialogs()
        self.Raise()
        self.chat_list.list_ctrl.SetFocus()

    def _on_view_members(self, event):
        entity = self._get_selected_group_or_channel_entity()
        if not entity:
            wx.MessageBox(
                "Select a group or channel first.",
                "Members",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        self.SetStatusText("Loading members...")
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
            wx.CallAfter(self._on_members_loaded, entity, list(participants))
        except Exception as e:
            log.error("Failed to load members: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to load members:\n{e}",
                "Members",
            )
            wx.CallAfter(self.SetStatusText, "Ready")

    def _on_members_loaded(self, entity, participants):
        from .theme import apply_theme

        lines = [self._member_entry_text(p) for p in participants]
        scope_label, permissions_supported = self._members_scope(entity)
        self.SetStatusText(f"{len(participants)} members")

        dlg = wx.Dialog(
            self,
            title="Group Members",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(dlg, label=f"{len(participants)} members:"),
            flag=wx.ALL,
            border=10,
        )
        sizer.Add(
            wx.StaticText(dlg, label=f"Type: {scope_label}"),
            flag=wx.LEFT | wx.RIGHT,
            border=10,
        )
        members_list = wx.ListBox(dlg, choices=lines, style=wx.LB_SINGLE)
        members_list.SetName("Group members")
        if lines:
            members_list.SetSelection(0)
        sizer.Add(members_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        role_btn = wx.Button(dlg, label="&Role...")
        permissions_btn = wx.Button(dlg, label="&Permissions...")
        kick_btn = wx.Button(dlg, label="&Kick")
        close_btn = wx.Button(dlg, wx.ID_CLOSE, "&Close")
        if not permissions_supported:
            permissions_btn.SetToolTip(
                "Per-member permissions are available only in channels and supergroups"
            )
        actions.Add(role_btn, 0, wx.RIGHT, 8)
        actions.Add(permissions_btn, 0, wx.RIGHT, 8)
        actions.Add(kick_btn, 0, wx.RIGHT, 8)
        actions.Add(close_btn, 0)
        sizer.Add(actions, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        def _selected_member():
            idx = members_list.GetSelection()
            if idx == wx.NOT_FOUND or idx >= len(participants):
                return None, None
            return participants[idx], lines[idx]

        def _update_member_action_state():
            member, _ = _selected_member()
            if not member:
                role_btn.Enable(False)
                permissions_btn.Enable(False)
                kick_btn.Enable(False)
                return

            role_kind = self._member_role_kind(member)
            is_owner = role_kind == "owner"
            role_btn.Enable(not is_owner)
            kick_btn.Enable(not is_owner)
            permissions_btn.Enable(permissions_supported and not is_owner)

        _update_member_action_state()

        def _on_permissions(event):
            member, display = _selected_member()
            if not member:
                return
            if self._member_role_kind(member) == "owner":
                wx.MessageBox(
                    "The chat owner permissions cannot be edited from here.",
                    "Permissions",
                    wx.OK | wx.ICON_INFORMATION,
                    dlg,
                )
                return
            with MemberPermissionsDialog(dlg, display) as permissions_dlg:
                if permissions_dlg.ShowModal() != wx.ID_OK:
                    return
                permissions = permissions_dlg.GetPermissions()
            self.SetStatusText(f"Updating permissions for {display}...")
            threading.Thread(
                target=self._set_member_permissions_thread,
                args=(entity, member, display, permissions),
                daemon=True,
            ).start()

        def _on_role(event):
            member, display = _selected_member()
            if not member:
                return
            role_kind = self._member_role_kind(member)
            if role_kind == "owner":
                wx.MessageBox(
                    "The chat owner role cannot be changed.",
                    "Member Role",
                    wx.OK | wx.ICON_INFORMATION,
                    dlg,
                )
                return

            choices = ["Member", "Admin"]
            role_dlg = wx.SingleChoiceDialog(
                dlg,
                f"Set role for {display}:",
                "Member Role",
                choices,
            )
            apply_theme(role_dlg)
            role_dlg.SetSelection(1 if role_kind == "admin" else 0)
            if role_dlg.ShowModal() != wx.ID_OK:
                role_dlg.Destroy()
                return
            selected = role_dlg.GetStringSelection()
            role_dlg.Destroy()

            make_admin = selected == "Admin"
            action_text = "Promoting" if make_admin else "Removing admin role from"
            self.SetStatusText(f"{action_text} {display}...")
            threading.Thread(
                target=self._set_member_role_thread,
                args=(entity, member, display, make_admin),
                daemon=True,
            ).start()

        def _on_kick(event):
            member, display = _selected_member()
            if not member:
                return
            if self._member_role_kind(member) == "owner":
                wx.MessageBox(
                    "The chat owner cannot be removed.",
                    "Kick Member",
                    wx.OK | wx.ICON_INFORMATION,
                    dlg,
                )
                return
            if wx.MessageBox(
                f"Kick {display} from this group?",
                "Confirm Kick",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
                dlg,
            ) != wx.YES:
                return
            self.SetStatusText(f"Kicking {display}...")
            threading.Thread(
                target=self._kick_member_entity_thread,
                args=(entity, member, display),
                daemon=True,
            ).start()

        members_list.Bind(wx.EVT_LISTBOX, lambda e: _update_member_action_state())
        role_btn.Bind(wx.EVT_BUTTON, _on_role)
        permissions_btn.Bind(wx.EVT_BUTTON, _on_permissions)
        kick_btn.Bind(wx.EVT_BUTTON, _on_kick)
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))

        dlg.SetSizerAndFit(sizer)
        dlg.SetMinSize((460, 360))
        dlg.CenterOnParent()
        apply_theme(dlg)
        dlg.ShowModal()
        dlg.Destroy()

    @staticmethod
    def _member_display_name(member):
        name = getattr(member, "first_name", "") or ""
        last = getattr(member, "last_name", "") or ""
        uname = getattr(member, "username", "") or ""
        display = f"{name} {last}".strip() or "Unknown"
        if uname:
            display += f" (@{uname})"
        return display

    @classmethod
    def _member_entry_text(cls, member):
        display = cls._member_display_name(member)
        role_kind = cls._member_role_kind(member)
        role_suffix = {
            "owner": "Owner",
            "admin": "Admin",
            "member": "Member",
        }.get(role_kind, "Member")
        return f"{display} [{role_suffix}]"

    @staticmethod
    def _member_role_kind(member):
        participant = getattr(member, "participant", None)
        part_name = type(participant).__name__ if participant is not None else ""
        if "Creator" in part_name:
            return "owner"
        if "Admin" in part_name:
            return "admin"
        return "member"

    @staticmethod
    def _members_scope(entity):
        from telethon.tl.types import Channel, Chat

        if isinstance(entity, Chat):
            return "Basic Group", False
        if isinstance(entity, Channel):
            if getattr(entity, "megagroup", False):
                return "Supergroup", True
            return "Channel", True
        return "Unknown", False

    def _on_kick_member(self, event):
        from .theme import apply_theme

        entity = self._get_selected_group_or_channel_entity()
        if not entity:
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
                announce(f"Kicked {u}")
            wx.CallAfter(_on_kicked)
        except Exception as e:
            log.error("Failed to kick member: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to kick member:\n{e}",
                "Kick Member",
            )

    def _kick_member_entity_thread(self, entity, user, display_name):
        try:
            self.tg.submit_wait(self.tg.kick_participant(entity, user))

            def _on_kicked(name=display_name):
                self.SetStatusText(f"Kicked {name}")
                self._msg_frame.SetStatusText(f"Kicked {name}")
                announce(f"Kicked {name}")

            wx.CallAfter(_on_kicked)
        except Exception as e:
            log.error("Failed to kick member: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to kick member:\n{e}",
                "Kick Member",
            )

    def _set_member_permissions_thread(self, entity, user, display_name, permissions):
        try:
            self.tg.submit_wait(
                self.tg.set_member_permissions(entity, user, permissions)
            )

            def _on_permissions_updated(name=display_name):
                self.SetStatusText(f"Updated permissions for {name}")
                self._msg_frame.SetStatusText(f"Updated permissions for {name}")
                announce(f"Updated permissions for {name}")

            wx.CallAfter(_on_permissions_updated)
        except Exception as e:
            log.error("Failed to update member permissions: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to update permissions:\n{e}",
                "Permissions",
            )

    def _set_member_role_thread(self, entity, user, display_name, make_admin):
        try:
            self.tg.submit_wait(
                self.tg.set_member_admin_role(
                    entity,
                    user,
                    make_admin=make_admin,
                    rank="Admin" if make_admin else "",
                )
            )

            def _on_role_updated(name=display_name, is_admin=make_admin):
                if is_admin:
                    self.SetStatusText(f"Promoted {name} to admin")
                    self._msg_frame.SetStatusText(f"Promoted {name} to admin")
                    announce(f"Promoted {name} to admin")
                else:
                    self.SetStatusText(f"Removed admin role from {name}")
                    self._msg_frame.SetStatusText(f"Removed admin role from {name}")
                    announce(f"Removed admin role from {name}")

            wx.CallAfter(_on_role_updated)
        except Exception as e:
            log.error("Failed to update member role: %s", e)
            wx.CallAfter(
                self._show_error,
                f"Failed to update member role:\n{e}",
                "Member Role",
            )

    def _on_edit_title(self, event):
        from .theme import apply_theme

        entity = self._get_selected_group_or_channel_entity()
        if not entity:
            wx.MessageBox(
                "Select a group or channel first.",
                "Edit Title",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        current_title = (
            getattr(entity, "title", "") or ""
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
                announce(f"Title changed to: {t}")
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

    @staticmethod
    def _entity_display_name(entity):
        first = getattr(entity, "first_name", "") or ""
        last = getattr(entity, "last_name", "") or ""
        full = f"{first} {last}".strip()
        return full or getattr(entity, "title", None) or getattr(entity, "username", None) or "Unknown"

    @staticmethod
    def _extract_urls(text):
        import re
        if not text:
            return []
        return re.findall(r'https?://[^\s<>\"\')]+', text)

    def _show_error(self, message, title="Error"):
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR, parent)

    def open_message_link(self):
        idx = self.message_panel.get_selected_message_index()
        if idx == wx.NOT_FOUND:
            return
        msg_idx = len(self._current_messages) - 1 - idx
        if msg_idx < 0 or msg_idx >= len(self._current_messages):
            return
        msg = self._current_messages[msg_idx]
        urls = self._extract_urls(msg.text)
        if not urls:
            return
        import webbrowser

        if len(urls) == 1:
            webbrowser.open(urls[0])
            return
        from .theme import apply_theme

        parent = self._msg_frame if self._msg_frame.IsShown() else self
        dlg = wx.Dialog(
            parent,
            title="Open Link",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(
                dlg,
                label="This message contains multiple links. Choose one to open:",
            ),
            flag=wx.ALL,
            border=10,
        )
        url_list = wx.ListBox(dlg, choices=urls, style=wx.LB_SINGLE)
        url_list.SetName("Message links")
        url_list.SetSelection(0)
        sizer.Add(url_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        btn_sizer = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)
        dlg.SetSizerAndFit(sizer)
        dlg.SetMinSize((400, 250))
        dlg.CenterOnParent()
        url_list.SetFocus()

        def _on_dclick(event):
            dlg.EndModal(wx.ID_OK)

        def _on_list_key(event):
            if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                dlg.EndModal(wx.ID_OK)
            else:
                event.Skip()

        url_list.Bind(wx.EVT_LISTBOX_DCLICK, _on_dclick)
        url_list.Bind(wx.EVT_KEY_DOWN, _on_list_key)
        apply_theme(dlg)

        if dlg.ShowModal() == wx.ID_OK:
            sel = url_list.GetSelection()
            if sel != wx.NOT_FOUND:
                webbrowser.open(url_list.GetString(sel))
        dlg.Destroy()

    def _on_check_updates(self, event):
        from ..updater import check_for_update_manual
        check_for_update_manual(self)

    def _on_about(self, event):
        from .. import APP_VERSION
        wx.MessageBox(
            f"Teepee v{APP_VERSION}\n\nThe simple, speedy Telegram client with the blind in mind.",
            "About Teepee",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def _on_shortcuts(self, event):
        shortcuts = (
            "Navigation:\n"
            "  Ctrl+1: Focus chat list\n"
            "  Ctrl+2: Focus message list\n"
            "  Ctrl+3: Focus message input\n"
            "  Ctrl+4: Focus files list (groups/channels)\n"
            "  Ctrl+5: Focus file search (groups/channels)\n\n"
            "Messaging:\n"
            "  Enter: Open selected chat (in chat list) or send message (in input field)\n"
            "  Shift+Enter: New line in message\n"
            "  Ctrl+R: Reply to selected message\n"
            "  Ctrl+E: Edit selected sent message\n"
            "  Ctrl+C: Copy selected message to clipboard (in message list)\n"
            "  Ctrl+Shift+A: Attach and send a file (you can add a caption)\n"
            "  Escape: Cancel reply or close chat view\n"
            "  Delete: Delete selected message or chat\n\n"
            "Calls:\n"
            "  Ctrl+Shift+C: Start voice call\n"
            "  Ctrl+Shift+V: Start video call\n"
            "  Ctrl+Shift+H: Hang up\n"
            "  Incoming calls show a dialog with Accept and Decline buttons\n\n"
            "Voice and Media:\n"
            "  Press the Voice button to start recording, press Stop to send\n"
            "  Press Play on a voice message, audio, or video to play it\n"
            "  Press Stop to stop audio playback\n"
            "  Audio plays inline, video opens in your default player\n"
            "  Ctrl+Shift+S: Save the selected voice message or file attachment\n"
            "  Press the Save button on a message with media to download it\n"
            "  Press the Open Link button on a message with a URL to open it\n"
            "  Press the Sticker button to search and send stickers by emoji\n\n"
            "Files (Groups and Channels):\n"
            "  The Files tab shows all documents shared in a group or channel\n"
            "  Type in the search box to search by file name\n"
            "  Enter or double-click to download, or use the Download button\n"
            "  Press Load More to fetch older files\n\n"
            "Chat Management (Chat menu):\n"
            "  Mute/Unmute: Mute or unmute the selected chat's notifications\n"
            "  Block/Unblock: Block or unblock a user (user chats only)\n"
            "  Report: Report a user for spam, abuse, or other reasons\n\n"
            "Groups and Channels (Group menu):\n"
            "  Create Group, Create Channel: Start a new group or channel\n"
            "  Join/Leave: Join or leave a group or channel\n"
            "  Invite User: Invite someone to the selected group or channel\n"
            "  View Members, Kick Member, Edit Title: Manage group settings\n\n"
            "Other:\n"
            "  Ctrl+,: Settings\n"
            "  F1: Keyboard shortcuts\n"
            "  Help > Check for Updates: Check for a newer version\n"
            "  Alt+F4: Minimize to system tray\n"
            "  Ctrl+Q: Quit\n\n"
            "Tip: Press the Applications key or Shift+F10 on a chat to\n"
            "mute, unmute, block, unblock, report, or delete it."
        )
        parent = self._msg_frame if self._msg_frame.IsShown() else self
        wx.MessageBox(
            shortcuts,
            "Keyboard Shortcuts",
            wx.OK | wx.ICON_INFORMATION,
            parent,
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

    @staticmethod
    def _terminate_process():
        """Kill this process immediately, bypassing DLL cleanup."""
        import os
        import signal
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os._exit(1)

    def _cleanup_and_destroy(self):
        import os

        self._restore_timer.Stop()
        if self._tray_icon:
            self._tray_icon.RemoveIcon()
            self._tray_icon.Destroy()
            self._tray_icon = None
        signal_file = self.config.data_dir / ".restore"
        signal_file.unlink(missing_ok=True)
        self.voice.cleanup()
        self.Hide()
        if self._msg_frame:
            self._msg_frame.Hide()

        # Attempt graceful shutdown in background, then force-terminate.
        def _bg_shutdown():
            try:
                self.calls.shutdown()
            except BaseException:
                pass
            try:
                self.tg.stop()
            except BaseException:
                pass
            self._terminate_process()

        threading.Thread(target=_bg_shutdown, daemon=True).start()

        # Explicitly destroy child top-level windows first, then self.
        # If only self.Destroy() is called, MessageFrame may survive
        # briefly, keeping MainLoop alive because it's a top-level window.
        dlg = getattr(self, "_in_call_dlg", None)
        if dlg:
            try:
                dlg.Destroy()
            except Exception:
                pass
            self._in_call_dlg = None
        if self._msg_frame:
            try:
                self._msg_frame.Destroy()
            except Exception:
                pass
            self._msg_frame = None
        self.Destroy()

    def _on_restore_timer(self, event):
        signal_file = self.config.data_dir / ".restore"
        if signal_file.exists():
            signal_file.unlink(missing_ok=True)
            if not self.IsShown():
                self.restore_from_tray()
            else:
                self.Raise()
