import wx

from .theme import apply_theme


class APISetupDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Teepee - API Setup",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            self,
            label=(
                "To use Teepee, you need Telegram API credentials.\n"
                "Get them from https://my.telegram.org/apps"
            ),
        )
        sizer.Add(info, flag=wx.ALL, border=10)

        sizer.Add(
            wx.StaticText(self, label="API ID:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.api_id_ctrl = wx.TextCtrl(self)
        self.api_id_ctrl.SetName("API ID")
        sizer.Add(
            self.api_id_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        sizer.Add(
            wx.StaticText(self, label="API Hash:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.api_hash_ctrl = wx.TextCtrl(self)
        self.api_hash_ctrl.SetName("API Hash")
        sizer.Add(
            self.api_hash_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((400, -1))
        self.CenterOnParent()
        self.api_id_ctrl.SetFocus()
        apply_theme(self)

    def GetAPIId(self):
        return self.api_id_ctrl.GetValue().strip()

    def GetAPIHash(self):
        return self.api_hash_ctrl.GetValue().strip()


class NewChatDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="New Chat",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="Username or phone number:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.recipient_ctrl = wx.TextCtrl(self)
        self.recipient_ctrl.SetName("Username or phone number")
        sizer.Add(
            self.recipient_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((350, -1))
        self.CenterOnParent()
        self.recipient_ctrl.SetFocus()
        apply_theme(self)

    def GetRecipient(self):
        return self.recipient_ctrl.GetValue().strip()


class PhoneDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Teepee - Phone Number",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(
                self, label="Enter your phone number (with country code):"
            ),
            flag=wx.ALL,
            border=10,
        )

        self.phone_ctrl = wx.TextCtrl(self, value="+")
        self.phone_ctrl.SetName("Phone number")
        sizer.Add(
            self.phone_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((350, -1))
        self.CenterOnParent()
        self.phone_ctrl.SetFocus()
        apply_theme(self)

    def GetPhone(self):
        return self.phone_ctrl.GetValue().strip()


class CodeDialog(wx.Dialog):
    def __init__(self, parent, phone):
        super().__init__(
            parent,
            title="Teepee - Verification Code",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label=f"Enter the code sent to {phone}:"),
            flag=wx.ALL,
            border=10,
        )

        self.code_ctrl = wx.TextCtrl(self)
        self.code_ctrl.SetName("Verification code")
        sizer.Add(
            self.code_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((350, -1))
        self.CenterOnParent()
        self.code_ctrl.SetFocus()
        apply_theme(self)

    def GetCode(self):
        return self.code_ctrl.GetValue().strip()


class TwoFactorDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Teepee - Two-Factor Authentication",
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="Enter your 2FA password:"),
            flag=wx.ALL,
            border=10,
        )

        self.password_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.password_ctrl.SetName("2FA password")
        sizer.Add(
            self.password_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((350, -1))
        self.CenterOnParent()
        self.password_ctrl.SetFocus()
        apply_theme(self)

    def GetPassword(self):
        return self.password_ctrl.GetValue()
