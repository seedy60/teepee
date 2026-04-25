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


class CreateGroupDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Create Group",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="Group title:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.title_ctrl = wx.TextCtrl(self)
        self.title_ctrl.SetName("Group title")
        sizer.Add(
            self.title_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Visibility:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.private_radio = wx.RadioButton(
            self,
            label="&Private group",
            style=wx.RB_GROUP,
        )
        self.public_radio = wx.RadioButton(self, label="P&ublic group")
        self.private_radio.SetValue(True)
        sizer.Add(
            self.private_radio,
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=10,
        )
        sizer.Add(
            self.public_radio,
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Public username (required for public):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.public_username_ctrl = wx.TextCtrl(self)
        self.public_username_ctrl.SetName("Public username")
        self.public_username_ctrl.Enable(False)
        sizer.Add(
            self.public_username_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(
                self,
                label="Invite usernames (comma-separated, optional):",
            ),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.usernames_ctrl = wx.TextCtrl(self)
        self.usernames_ctrl.SetName("Invite usernames")
        sizer.Add(
            self.usernames_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.private_radio.Bind(wx.EVT_RADIOBUTTON, self._on_visibility_changed)
        self.public_radio.Bind(wx.EVT_RADIOBUTTON, self._on_visibility_changed)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((430, -1))
        self.CenterOnParent()
        self.title_ctrl.SetFocus()
        apply_theme(self)

    def _on_visibility_changed(self, event):
        is_public = self.public_radio.GetValue()
        self.public_username_ctrl.Enable(is_public)
        if is_public:
            self.public_username_ctrl.SetFocus()
        else:
            self.public_username_ctrl.SetValue("")

    def GetTitle(self):
        return self.title_ctrl.GetValue().strip()

    def IsPublic(self):
        return self.public_radio.GetValue()

    def GetPublicUsername(self):
        return self.public_username_ctrl.GetValue().strip().lstrip("@")

    def GetInviteUsernames(self):
        return self.usernames_ctrl.GetValue().strip()


class CreateChannelDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Create Channel",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="Channel title:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.title_ctrl = wx.TextCtrl(self)
        self.title_ctrl.SetName("Channel title")
        sizer.Add(
            self.title_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Description (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.about_ctrl = wx.TextCtrl(self)
        self.about_ctrl.SetName("Channel description")
        sizer.Add(
            self.about_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Visibility:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.private_radio = wx.RadioButton(
            self,
            label="&Private channel",
            style=wx.RB_GROUP,
        )
        self.public_radio = wx.RadioButton(self, label="P&ublic channel")
        self.private_radio.SetValue(True)
        sizer.Add(
            self.private_radio,
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=10,
        )
        sizer.Add(
            self.public_radio,
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Public username (required for public):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.public_username_ctrl = wx.TextCtrl(self)
        self.public_username_ctrl.SetName("Public username")
        self.public_username_ctrl.Enable(False)
        sizer.Add(
            self.public_username_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.private_radio.Bind(wx.EVT_RADIOBUTTON, self._on_visibility_changed)
        self.public_radio.Bind(wx.EVT_RADIOBUTTON, self._on_visibility_changed)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((430, -1))
        self.CenterOnParent()
        self.title_ctrl.SetFocus()
        apply_theme(self)

    def _on_visibility_changed(self, event):
        is_public = self.public_radio.GetValue()
        self.public_username_ctrl.Enable(is_public)
        if is_public:
            self.public_username_ctrl.SetFocus()
        else:
            self.public_username_ctrl.SetValue("")

    def GetTitle(self):
        return self.title_ctrl.GetValue().strip()

    def GetAbout(self):
        return self.about_ctrl.GetValue().strip()

    def IsPublic(self):
        return self.public_radio.GetValue()

    def GetPublicUsername(self):
        return self.public_username_ctrl.GetValue().strip().lstrip("@")
