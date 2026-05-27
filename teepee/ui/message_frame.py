import wx

from .files_panel import FilesPanel
from .links_panel import LinksPanel
from .message_panel import MessagePanel
from .theme import apply_theme


class MessageFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Teepee - Messages", size=(700, 500))
        self.main_frame = parent

        self.notebook = wx.Notebook(self)
        self.notebook.SetName("Chat tabs")

        self.message_panel = MessagePanel(self.notebook, parent)
        self.message_panel.set_enabled(False)
        self.notebook.AddPage(self.message_panel, "Messages")

        self.files_panel = FilesPanel(self.notebook, parent)
        self.notebook.AddPage(self.files_panel, "Files")

        self.links_panel = LinksPanel(self.notebook, parent)
        self.notebook.AddPage(self.links_panel, "Links")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetMinSize((400, 300))
        self.CenterOnScreen()

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        apply_theme(self)

    def _on_close(self, event):
        self.Hide()
        self.main_frame.Raise()
        self.main_frame.chat_list.list_ctrl.SetFocus()

    def _copy_selected_message(self):
        idx = self.message_panel.messages_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        text = self.message_panel.messages_list.GetString(idx)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            self.main_frame.SetStatusText("Message copied")
            self.SetStatusText("Message copied")
            from .announce import announce
            announce("Message copied")

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()

        if focused == self.links_panel.links_list:
            if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.links_panel.open_selected()
                return
            if (
                key == ord("C")
                and event.ControlDown()
                and not event.ShiftDown()
                and not event.AltDown()
            ):
                self.links_panel.copy_selected()
                return

        if focused == self.message_panel.input_ctrl:
            if key == wx.WXK_RETURN and not event.ShiftDown():
                self.message_panel.do_send()
                return

        if key == wx.WXK_DELETE:
            if focused == self.message_panel.messages_list:
                self.main_frame.delete_selected_message()
                return

        if (
            key == ord("R")
            and event.ControlDown()
            and not event.ShiftDown()
            and not event.AltDown()
        ):
            self.main_frame.reply_to_selected_message()
            return

        if (
            key == ord("E")
            and event.ControlDown()
            and not event.ShiftDown()
            and not event.AltDown()
        ):
            self.main_frame.edit_selected_message()
            return

        if key == wx.WXK_ESCAPE:
            if self.message_panel._reply_to_msg:
                self.message_panel.clear_reply()
                return
            self._on_close(event)
            return

        if key == wx.WXK_F1:
            self.main_frame._on_shortcuts(event)
            return

        if event.ControlDown() and event.ShiftDown() and not event.AltDown():
            if key == ord("C"):
                self.main_frame._on_call(event)
                return
            if key == ord("H"):
                self.main_frame._on_hangup(event)
                return
            if key == ord("V"):
                self.main_frame._on_video_call(event)
                return
            if key == ord("A"):
                self.message_panel._on_attach(event)
                return
            if key == ord("S"):
                self.main_frame.save_selected_media()
                return
            if key == ord("D"):
                self.main_frame.describe_selected_media()
                return
            if key == ord(";"):
                self.main_frame.show_reply_target_for_selected_message()
                return

        if event.ControlDown() and not event.ShiftDown() and not event.AltDown():
            if key == ord("C"):
                if focused == self.message_panel.messages_list:
                    self._copy_selected_message()
                    return
            if key == ord("1"):
                self.main_frame.Raise()
                self.main_frame.chat_list.list_ctrl.SetFocus()
                return
            if key == ord("2"):
                self.message_panel.messages_list.SetFocus()
                return
            if key == ord("3"):
                self.message_panel.input_ctrl.SetFocus()
                return
            if key == ord("4"):
                self.notebook.SetSelection(1)
                self.files_panel.file_list.SetFocus()
                return
            if key == ord("5"):
                self.notebook.SetSelection(1)
                self.files_panel.search_ctrl.SetFocus()
                return
            if key == ord("6"):
                self.notebook.SetSelection(2)
                self.links_panel.links_list.SetFocus()
                return
            if key == ord("Q"):
                self.main_frame.quit()
                return
            if key == ord(","):
                self.main_frame._on_settings(event)
                return

        event.Skip()
