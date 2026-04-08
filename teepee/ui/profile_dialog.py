import wx

from .theme import apply_theme


class ProfileDialog(wx.Dialog):
    def __init__(self, parent, user_info):
        super().__init__(
            parent,
            title="Teepee - My Profile",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="First Name:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.first_name_ctrl = wx.TextCtrl(
            self, value=user_info.get("first_name", "")
        )
        self.first_name_ctrl.SetName("First Name")
        sizer.Add(
            self.first_name_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Last Name:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.last_name_ctrl = wx.TextCtrl(
            self, value=user_info.get("last_name", "")
        )
        self.last_name_ctrl.SetName("Last Name")
        sizer.Add(
            self.last_name_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Username:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.username_ctrl = wx.TextCtrl(
            self,
            value=user_info.get("username", ""),
            style=wx.TE_READONLY,
        )
        self.username_ctrl.SetName("Username")
        sizer.Add(
            self.username_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Phone:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.phone_ctrl = wx.TextCtrl(
            self,
            value=user_info.get("phone", ""),
            style=wx.TE_READONLY,
        )
        self.phone_ctrl.SetName("Phone")
        sizer.Add(
            self.phone_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(self, label="Bio:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.bio_ctrl = wx.TextCtrl(
            self,
            value=user_info.get("bio", ""),
            style=wx.TE_MULTILINE,
        )
        self.bio_ctrl.SetName("Bio")
        sizer.Add(
            self.bio_ctrl,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((400, 350))
        self.CenterOnParent()
        self.first_name_ctrl.SetFocus()
        apply_theme(self)

    def GetFirstName(self):
        return self.first_name_ctrl.GetValue().strip()

    def GetLastName(self):
        return self.last_name_ctrl.GetValue().strip()

    def GetBio(self):
        return self.bio_ctrl.GetValue().strip()
