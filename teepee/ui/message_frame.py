import wx

from .message_panel import MessagePanel
from .theme import apply_theme


class MessageFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Teepee - Messages", size=(700, 500))
        self.main_frame = parent

        self.message_panel = MessagePanel(self, parent)
        self.message_panel.set_enabled(False)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.message_panel, 1, wx.EXPAND)
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

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()

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
            if key == ord("A"):
                self.message_panel._on_attach(event)
                return
            if key == ord("S"):
                self.main_frame.save_selected_media()
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
            if key == ord("Q"):
                self.main_frame.quit()
                return
            if key == ord(","):
                self.main_frame._on_settings(event)
                return

        event.Skip()
