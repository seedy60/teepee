import os
import threading
from datetime import datetime as _dt

import wx

from .theme import apply_theme


class _TFASetupDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Set Up Two-factor Authentication",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(
                self,
                label=(
                    "Choose a password. You will need to enter it when\n"
                    "logging in to Telegram on new devices."
                ),
            ),
            flag=wx.ALL,
            border=10,
        )
        sizer.Add(
            wx.StaticText(self, label="New Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.new_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.new_ctrl.SetName("New Password")
        sizer.Add(self.new_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(self, label="Confirm New Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.confirm_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.confirm_ctrl.SetName("Confirm New Password")
        sizer.Add(self.confirm_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(self, label="Hint (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.hint_ctrl = wx.TextCtrl(self)
        self.hint_ctrl.SetName("Password Hint")
        self.hint_ctrl.SetToolTip(
            "A reminder shown when you need to enter your password. "
            "Do not put your password in the hint."
        )
        sizer.Add(self.hint_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(self, label="Recovery email (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.email_ctrl = wx.TextCtrl(self)
        self.email_ctrl.SetName("Recovery Email")
        self.email_ctrl.SetToolTip(
            "If you forget your password, you can recover access using this email. "
            "Telegram will send a code you need to enter once to confirm the address."
        )
        sizer.Add(self.email_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((400, -1))
        self.CenterOnParent()
        self.new_ctrl.SetFocus()
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        apply_theme(self)

    def _on_ok(self, event):
        new = self.new_ctrl.GetValue()
        confirm = self.confirm_ctrl.GetValue()
        if not new:
            wx.MessageBox(
                "Enter a new password.",
                "Set Up Two-factor Authentication",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.new_ctrl.SetFocus()
            return
        if new != confirm:
            wx.MessageBox(
                "The passwords do not match.",
                "Set Up Two-factor Authentication",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.confirm_ctrl.SetValue("")
            self.confirm_ctrl.SetFocus()
            return
        email = self.email_ctrl.GetValue().strip()
        if email and "@" not in email:
            wx.MessageBox(
                "Enter a valid recovery email, or leave the field blank.",
                "Set Up Two-factor Authentication",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.email_ctrl.SetFocus()
            return
        event.Skip()

    def GetNewPassword(self):
        return self.new_ctrl.GetValue()

    def GetHint(self):
        return self.hint_ctrl.GetValue().strip()

    def GetEmail(self):
        return self.email_ctrl.GetValue().strip()


class _TFAChangeDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Change Two-factor Authentication Password",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(self, label="Current Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.current_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.current_ctrl.SetName("Current Password")
        sizer.Add(
            self.current_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        sizer.Add(
            wx.StaticText(self, label="New Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.new_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.new_ctrl.SetName("New Password")
        sizer.Add(self.new_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(self, label="Confirm New Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.confirm_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.confirm_ctrl.SetName("Confirm New Password")
        sizer.Add(
            self.confirm_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        sizer.Add(
            wx.StaticText(self, label="Hint (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.hint_ctrl = wx.TextCtrl(self)
        self.hint_ctrl.SetName("Password Hint")
        self.hint_ctrl.SetToolTip(
            "A reminder shown when you need to enter your password. "
            "Do not put your password in the hint."
        )
        sizer.Add(self.hint_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        sizer.Add(
            wx.StaticText(self, label="Update recovery email (optional):"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.email_ctrl = wx.TextCtrl(self)
        self.email_ctrl.SetName("Recovery Email")
        self.email_ctrl.SetToolTip(
            "Leave blank to keep your current recovery email. Enter a new email "
            "address to replace it; Telegram will send a code you must enter once."
        )
        sizer.Add(self.email_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((400, -1))
        self.CenterOnParent()
        self.current_ctrl.SetFocus()
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        apply_theme(self)

    def _on_ok(self, event):
        if not self.current_ctrl.GetValue():
            wx.MessageBox(
                "Enter your current password.",
                "Change Password",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.current_ctrl.SetFocus()
            return
        new = self.new_ctrl.GetValue()
        confirm = self.confirm_ctrl.GetValue()
        if not new:
            wx.MessageBox(
                "Enter a new password.",
                "Change Password",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.new_ctrl.SetFocus()
            return
        if new != confirm:
            wx.MessageBox(
                "The new passwords do not match.",
                "Change Password",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.confirm_ctrl.SetValue("")
            self.confirm_ctrl.SetFocus()
            return
        email = self.email_ctrl.GetValue().strip()
        if email and "@" not in email:
            wx.MessageBox(
                "Enter a valid recovery email, or leave the field blank.",
                "Change Password",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.email_ctrl.SetFocus()
            return
        event.Skip()

    def GetCurrentPassword(self):
        return self.current_ctrl.GetValue()

    def GetNewPassword(self):
        return self.new_ctrl.GetValue()

    def GetHint(self):
        return self.hint_ctrl.GetValue().strip()

    def GetEmail(self):
        return self.email_ctrl.GetValue().strip()


class _EmailCodeDialog(wx.Dialog):
    def __init__(self, parent, code_length):
        super().__init__(
            parent,
            title="Confirm Recovery Email",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        if code_length and code_length > 0:
            msg = (
                f"Telegram has sent a {code_length}-digit verification code\n"
                "to your recovery email. Enter it below to confirm the\n"
                "address."
            )
        else:
            msg = (
                "Telegram has sent a verification code to your recovery\n"
                "email. Enter it below to confirm the address."
            )
        sizer.Add(wx.StaticText(self, label=msg), flag=wx.ALL, border=10)

        sizer.Add(
            wx.StaticText(self, label="Verification Code:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.code_ctrl = wx.TextCtrl(self)
        self.code_ctrl.SetName("Verification Code")
        sizer.Add(
            self.code_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((360, -1))
        self.CenterOnParent()
        self.code_ctrl.SetFocus()
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        apply_theme(self)

    def _on_ok(self, event):
        if not self.code_ctrl.GetValue().strip():
            wx.MessageBox(
                "Enter the verification code from your email.",
                "Confirm Recovery Email",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.code_ctrl.SetFocus()
            return
        event.Skip()

    def GetCode(self):
        return self.code_ctrl.GetValue().strip()


class _TFADisableDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Disable Two-factor Authentication",
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(
                self,
                label=(
                    "Enter your current password to disable\n"
                    "two-factor authentication."
                ),
            ),
            flag=wx.ALL,
            border=10,
        )
        sizer.Add(
            wx.StaticText(self, label="Current Password:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.current_ctrl = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        self.current_ctrl.SetName("Current Password")
        sizer.Add(
            self.current_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((360, -1))
        self.CenterOnParent()
        self.current_ctrl.SetFocus()
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        apply_theme(self)

    def _on_ok(self, event):
        if not self.current_ctrl.GetValue():
            wx.MessageBox(
                "Enter your current password.",
                "Disable Two-factor Authentication",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.current_ctrl.SetFocus()
            return
        event.Skip()

    def GetCurrentPassword(self):
        return self.current_ctrl.GetValue()


class AccountDialog(wx.Dialog):
    def __init__(self, parent, account_data):
        super().__init__(
            parent,
            title="Teepee - My Account",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._account_data = account_data
        self._sessions = list(account_data.get("sessions", []))
        self._terminated_hashes = []
        self._photo_to_upload = None
        self._delete_current_photo = False

        sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(self)
        self.notebook.SetName("Account settings")

        self._create_profile_tab()
        self._create_privacy_tab()
        self._create_security_tab()
        self._create_account_tab()

        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((500, 550))
        self.CenterOnParent()
        self.first_name_ctrl.SetFocus()
        apply_theme(self)

    def _create_profile_tab(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        d = self._account_data

        sizer.Add(
            wx.StaticText(panel, label="First Name:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.first_name_ctrl = wx.TextCtrl(
            panel, value=d.get("first_name", "")
        )
        self.first_name_ctrl.SetName("First Name")
        sizer.Add(
            self.first_name_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(panel, label="Last Name:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.last_name_ctrl = wx.TextCtrl(
            panel, value=d.get("last_name", "")
        )
        self.last_name_ctrl.SetName("Last Name")
        sizer.Add(
            self.last_name_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(panel, label="Username:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.username_ctrl = wx.TextCtrl(
            panel, value=d.get("username", "")
        )
        self.username_ctrl.SetName("Username")
        sizer.Add(
            self.username_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(panel, label="Phone:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.phone_ctrl = wx.TextCtrl(
            panel, value=d.get("phone", ""), style=wx.TE_READONLY
        )
        self.phone_ctrl.SetName("Phone")
        sizer.Add(
            self.phone_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        sizer.Add(
            wx.StaticText(panel, label="Bio:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.bio_ctrl = wx.TextCtrl(
            panel, value=d.get("bio", ""), style=wx.TE_MULTILINE
        )
        self.bio_ctrl.SetName("Bio")
        sizer.Add(
            self.bio_ctrl,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        # --- Birthday section ---
        sizer.Add(
            wx.StaticLine(panel),
            flag=wx.EXPAND | wx.TOP | wx.BOTTOM,
            border=5,
        )

        self.bday_set_check = wx.CheckBox(panel, label="Set birthday")
        self.bday_set_check.SetName("Set birthday")
        sizer.Add(
            self.bday_set_check, flag=wx.LEFT | wx.TOP, border=10
        )

        bday_row = wx.BoxSizer(wx.HORIZONTAL)

        bday_row.Add(
            wx.StaticText(panel, label="Day:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.bday_day = wx.SpinCtrl(panel, min=1, max=31, initial=1)
        self.bday_day.SetName("Birthday day")
        bday_row.Add(self.bday_day, 0, wx.RIGHT, 10)

        bday_row.Add(
            wx.StaticText(panel, label="Month:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        self.bday_month = wx.Choice(panel, choices=months)
        self.bday_month.SetName("Birthday month")
        self.bday_month.SetSelection(0)
        bday_row.Add(self.bday_month, 0, wx.RIGHT, 10)

        self.bday_year_check = wx.CheckBox(panel, label="Include year")
        self.bday_year_check.SetName("Include year in birthday")
        bday_row.Add(
            self.bday_year_check,
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )

        self.bday_year = wx.SpinCtrl(
            panel, min=1900, max=_dt.now().year, initial=2000
        )
        self.bday_year.SetName("Birthday year")
        bday_row.Add(self.bday_year, 0)

        sizer.Add(bday_row, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        birthday = d.get("birthday")
        has_birthday = birthday is not None
        self.bday_set_check.SetValue(has_birthday)
        if has_birthday:
            self.bday_day.SetValue(birthday.day)
            self.bday_month.SetSelection(birthday.month - 1)
            if getattr(birthday, "year", None):
                self.bday_year_check.SetValue(True)
                self.bday_year.SetValue(birthday.year)
                self.bday_year.Enable(True)
            else:
                self.bday_year.Enable(False)
        else:
            self.bday_day.Enable(False)
            self.bday_month.Enable(False)
            self.bday_year_check.Enable(False)
            self.bday_year.Enable(False)

        self.bday_set_check.Bind(
            wx.EVT_CHECKBOX, self._on_bday_set_toggle
        )
        self.bday_year_check.Bind(
            wx.EVT_CHECKBOX, self._on_bday_year_toggle
        )

        # --- Profile photo section ---
        sizer.Add(
            wx.StaticLine(panel),
            flag=wx.EXPAND | wx.TOP | wx.BOTTOM,
            border=5,
        )

        photo_sizer = wx.BoxSizer(wx.HORIZONTAL)
        photo_count = d.get("photo_count", 0)
        self.photo_label = wx.StaticText(
            panel, label=f"Profile photos: {photo_count}"
        )
        photo_sizer.Add(
            self.photo_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10
        )

        self.upload_photo_btn = wx.Button(
            panel, label="&Upload Photo..."
        )
        self.upload_photo_btn.SetName("Upload Photo")
        self.upload_photo_btn.SetToolTip("Upload a new profile photo")
        photo_sizer.Add(self.upload_photo_btn, 0, wx.ALL, 2)

        self.delete_photo_btn = wx.Button(
            panel, label="D&elete Current Photo"
        )
        self.delete_photo_btn.SetName("Delete Current Photo")
        self.delete_photo_btn.SetToolTip(
            "Delete your current profile photo"
        )
        self.delete_photo_btn.Enable(photo_count > 0)
        photo_sizer.Add(self.delete_photo_btn, 0, wx.ALL, 2)

        sizer.Add(
            photo_sizer,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        self.upload_photo_btn.Bind(
            wx.EVT_BUTTON, self._on_upload_photo
        )
        self.delete_photo_btn.Bind(
            wx.EVT_BUTTON, self._on_delete_photo
        )

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Profile")

    def _create_privacy_tab(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        d = self._account_data
        choices = ["Everyone", "My contacts", "Nobody"]

        sizer.Add(
            wx.StaticText(
                panel, label="Choose who can see your information:"
            ),
            flag=wx.ALL,
            border=10,
        )

        privacy_fields = [
            ("Last seen:", "privacy_last_seen", "Last seen"),
            ("Phone number:", "privacy_phone", "Phone number visibility"),
            ("Profile photo:", "privacy_photo", "Profile photo visibility"),
            (
                "Forwarded messages:",
                "privacy_forwards",
                "Forwarded messages",
            ),
            ("Calls:", "privacy_calls", "Who can call me"),
            ("Groups:", "privacy_groups", "Who can add me to groups"),
        ]

        if "privacy_birthday" in d:
            privacy_fields.append(
                ("Birthday:", "privacy_birthday", "Birthday visibility")
            )

        self._privacy_choices = {}
        for label_text, key, name in privacy_fields:
            sizer.Add(
                wx.StaticText(panel, label=label_text),
                flag=wx.LEFT | wx.TOP,
                border=10,
            )
            choice = wx.Choice(panel, choices=choices)
            choice.SetName(name)
            choice.SetSelection(d.get(key, 0))
            sizer.Add(
                choice, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
            )
            self._privacy_choices[key] = choice

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Privacy")

    def _create_security_tab(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        d = self._account_data

        sizer.Add(
            wx.StaticText(panel, label="Two-factor authentication:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self._tfa_status_ctrl = wx.TextCtrl(
            panel,
            value=("Enabled" if d.get("has_2fa") else "Disabled"),
            style=wx.TE_READONLY,
        )
        self._tfa_status_ctrl.SetName("Two-factor authentication status")
        sizer.Add(
            self._tfa_status_ctrl,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        tfa_btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._setup_2fa_btn = wx.Button(
            panel, label="&Set Up Two-factor Authentication..."
        )
        self._setup_2fa_btn.SetName("Set Up Two-factor Authentication")
        self._setup_2fa_btn.SetToolTip(
            "Choose a password that protects logins on new devices"
        )
        self._setup_2fa_btn.Bind(wx.EVT_BUTTON, self._on_setup_2fa)
        tfa_btn_row.Add(self._setup_2fa_btn, 0, wx.RIGHT, 5)

        self._change_2fa_btn = wx.Button(panel, label="&Change Password...")
        self._change_2fa_btn.SetName("Change Two-factor Authentication Password")
        self._change_2fa_btn.SetToolTip(
            "Change your existing two-factor authentication password"
        )
        self._change_2fa_btn.Bind(wx.EVT_BUTTON, self._on_change_2fa)
        tfa_btn_row.Add(self._change_2fa_btn, 0, wx.RIGHT, 5)

        self._disable_2fa_btn = wx.Button(
            panel, label="&Disable Two-factor Authentication..."
        )
        self._disable_2fa_btn.SetName("Disable Two-factor Authentication")
        self._disable_2fa_btn.SetToolTip(
            "Remove your two-factor authentication password"
        )
        self._disable_2fa_btn.Bind(wx.EVT_BUTTON, self._on_disable_2fa)
        tfa_btn_row.Add(self._disable_2fa_btn, 0)

        sizer.Add(
            tfa_btn_row, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
        )
        self._update_tfa_buttons()

        sizer.Add(
            wx.StaticText(panel, label="Active sessions:"),
            flag=wx.LEFT | wx.TOP,
            border=10,
        )
        self.sessions_list = wx.ListBox(panel)
        self.sessions_list.SetName("Active sessions")
        for s in self._sessions:
            self.sessions_list.Append(s["display"])
        sizer.Add(
            self.sessions_list,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            10,
        )

        self.terminate_btn = wx.Button(
            panel, label="&Terminate Selected Session"
        )
        self.terminate_btn.SetName("Terminate Selected Session")
        self.terminate_btn.SetToolTip("End the selected session remotely")
        sizer.Add(
            self.terminate_btn,
            flag=wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )
        self.terminate_btn.Bind(
            wx.EVT_BUTTON, self._on_terminate_session
        )
        self.sessions_list.Bind(wx.EVT_LISTBOX, self._on_session_selected)

        if self.sessions_list.GetCount() > 0:
            self.sessions_list.SetSelection(0)
        self._sync_session_controls()

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Security")

    def _on_bday_set_toggle(self, event):
        enabled = self.bday_set_check.IsChecked()
        self.bday_day.Enable(enabled)
        self.bday_month.Enable(enabled)
        self.bday_year_check.Enable(enabled)
        self.bday_year.Enable(
            enabled and self.bday_year_check.IsChecked()
        )

    def _on_bday_year_toggle(self, event):
        self.bday_year.Enable(self.bday_year_check.IsChecked())

    def _on_upload_photo(self, event):
        wildcard = (
            "Image files (*.jpg;*.jpeg;*.png;*.bmp)"
            "|*.jpg;*.jpeg;*.png;*.bmp"
            "|All files (*.*)|*.*"
        )
        with wx.FileDialog(
            self,
            "Choose a profile photo",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._photo_to_upload = dlg.GetPath()
                name = os.path.basename(self._photo_to_upload)
                self.photo_label.SetLabel(
                    f"Profile photos: will upload {name}"
                )

    def _on_delete_photo(self, event):
        if (
            wx.MessageBox(
                "Delete your current profile photo?",
                "Confirm Delete",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            == wx.YES
        ):
            self._delete_current_photo = True
            self.delete_photo_btn.Enable(False)
            self.photo_label.SetLabel(
                "Profile photos: current photo will be deleted"
            )

    def _create_account_tab(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        d = self._account_data

        sizer.Add(
            wx.StaticText(
                panel,
                label="If you do not log in for this long,\n"
                "your account will be deleted:",
            ),
            flag=wx.ALL,
            border=10,
        )

        ttl_choices = ["1 month", "3 months", "6 months", "12 months"]
        self._ttl_days = [30, 90, 180, 365]

        self.ttl_choice = wx.Choice(panel, choices=ttl_choices)
        self.ttl_choice.SetName("Account self-destruct timer")

        current_days = d.get("account_ttl_days", 180)
        closest_idx = 2
        for i, days in enumerate(self._ttl_days):
            if current_days <= days:
                closest_idx = i
                break
        self.ttl_choice.SetSelection(closest_idx)

        sizer.Add(
            self.ttl_choice,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=10,
        )

        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, "Account")

    def _on_terminate_session(self, event):
        idx = self.sessions_list.GetSelection()
        if idx == wx.NOT_FOUND:
            wx.MessageBox(
                "Select a session to terminate.",
                "Terminate Session",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        session = self._sessions[idx]
        if session["current"]:
            wx.MessageBox(
                "You cannot terminate your current session.",
                "Terminate Session",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return

        if (
            wx.MessageBox(
                f"Terminate this session?\n\n{session['display']}",
                "Confirm Terminate",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            != wx.YES
        ):
            return

        self._terminated_hashes.append(session["hash"])
        self._sessions.pop(idx)
        self.sessions_list.Delete(idx)

        from .announce import announce
        announce("Session marked for termination")

        count = self.sessions_list.GetCount()
        if count > 0:
            new_sel = min(idx, count - 1)
            self.sessions_list.SetSelection(new_sel)
            self.sessions_list.SetFocus()
        else:
            # No sessions left; terminate_btn will be disabled, so park
            # focus on the (still-focusable) sessions list itself rather
            # than a disabled button.
            self.sessions_list.SetFocus()
        self._sync_session_controls()

    def _on_session_selected(self, event):
        self._sync_session_controls()
        event.Skip()

    # ---------------------------------------------- Two-factor authentication

    def _update_tfa_buttons(self):
        enabled = bool(self._account_data.get("has_2fa"))
        self._setup_2fa_btn.Show(not enabled)
        self._change_2fa_btn.Show(enabled)
        self._disable_2fa_btn.Show(enabled)
        self._setup_2fa_btn.GetContainingSizer().Layout()

    def _set_tfa_buttons_enabled(self, enabled):
        for btn in (
            self._setup_2fa_btn,
            self._change_2fa_btn,
            self._disable_2fa_btn,
        ):
            btn.Enable(enabled)

    def _on_setup_2fa(self, event):
        with _TFASetupDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            new_password = dlg.GetNewPassword()
            hint = dlg.GetHint()
            email = dlg.GetEmail()
        self._run_2fa_change(
            action="setup",
            current=None,
            new_password=new_password,
            hint=hint,
            email=email,
        )

    def _on_change_2fa(self, event):
        with _TFAChangeDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            current = dlg.GetCurrentPassword()
            new_password = dlg.GetNewPassword()
            hint = dlg.GetHint()
            email = dlg.GetEmail()
        self._run_2fa_change(
            action="change",
            current=current,
            new_password=new_password,
            hint=hint,
            email=email,
        )

    def _on_disable_2fa(self, event):
        with _TFADisableDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            current = dlg.GetCurrentPassword()
        if (
            wx.MessageBox(
                "Disable two-factor authentication?",
                "Confirm Disable",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            != wx.YES
        ):
            return
        self._run_2fa_change(
            action="disable",
            current=current,
            new_password=None,
            hint="",
            email=None,
        )

    def _run_2fa_change(self, action, current, new_password, hint, email=None):
        self._set_tfa_buttons_enabled(False)
        self._tfa_status_ctrl.SetValue("Working...")
        from .announce import announce
        announce("Updating two-factor authentication")
        threading.Thread(
            target=self._tfa_change_thread,
            args=(action, current, new_password, hint, email),
            daemon=True,
        ).start()

    def _prompt_email_code(self, code_length):
        """Run the email-code dialog on the wx UI thread and block this
        thread until the user submits or cancels. Returns the code string,
        or empty string on cancel."""
        result = {"code": ""}
        done = threading.Event()

        def _show():
            try:
                with _EmailCodeDialog(self, code_length) as dlg:
                    if dlg.ShowModal() == wx.ID_OK:
                        result["code"] = dlg.GetCode()
            finally:
                done.set()

        wx.CallAfter(_show)
        done.wait()
        return result["code"]

    def _tfa_change_thread(self, action, current, new_password, hint, email):
        import asyncio

        tg = self.GetParent().tg

        async def email_code_callback(code_length):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._prompt_email_code, code_length
            )

        try:
            tg.submit_wait(
                tg.set_password(
                    current_password=current,
                    new_password=new_password,
                    hint=hint,
                    email=email or None,
                    email_code_callback=(
                        email_code_callback if email else None
                    ),
                )
            )
            wx.CallAfter(self._on_tfa_change_done, action, None)
        except Exception as e:
            wx.CallAfter(self._on_tfa_change_done, action, e)

    def _on_tfa_change_done(self, action, error):
        from .announce import announce
        if error is None:
            self._account_data["has_2fa"] = action != "disable"
            self._tfa_status_ctrl.SetValue(
                "Enabled" if self._account_data["has_2fa"] else "Disabled"
            )
            messages = {
                "setup": "Two-factor authentication enabled.",
                "change": "Password changed.",
                "disable": "Two-factor authentication disabled.",
            }
            msg = messages.get(action, "Two-factor authentication updated.")
            self._update_tfa_buttons()
            self._set_tfa_buttons_enabled(True)
            announce(msg)
            wx.MessageBox(msg, "Two-factor Authentication", wx.OK | wx.ICON_INFORMATION, self)
            # The button the user just clicked may have been hidden by
            # _update_tfa_buttons; park focus on whichever TFA button is now
            # visible so screen reader users land somewhere meaningful.
            for btn in (
                self._setup_2fa_btn,
                self._change_2fa_btn,
                self._disable_2fa_btn,
            ):
                if btn.IsShown():
                    btn.SetFocus()
                    break
        else:
            self._tfa_status_ctrl.SetValue(
                "Enabled" if self._account_data.get("has_2fa") else "Disabled"
            )
            self._set_tfa_buttons_enabled(True)
            err_text = self._format_2fa_error(error)
            announce("Two-factor authentication update failed")
            wx.MessageBox(
                err_text,
                "Two-factor Authentication",
                wx.OK | wx.ICON_ERROR,
                self,
            )

    @staticmethod
    def _format_2fa_error(error):
        msg = str(error) or type(error).__name__
        name = type(error).__name__
        if "PasswordHashInvalid" in name:
            return "The current password is incorrect."
        if "PasswordTooFresh" in name or "FreshChangePhone" in name:
            return (
                "Telegram does not allow changing your password yet because "
                "the account was authorized too recently. Try again later."
            )
        if "EmailUnconfirmed" in name:
            return (
                "The recovery email was set, but the verification code was not "
                "entered. Your password is active; you can confirm the recovery "
                "email later from the official Telegram app, or re-run Set Up "
                "to redo it."
            )
        if "EmailInvalid" in name:
            return "Telegram rejected the recovery email address."
        if "EmailHashExpired" in name:
            return (
                "The email verification code expired before it was entered. "
                "Try Set Up or Change Password again."
            )
        if "CodeInvalid" in name:
            return "The verification code is incorrect."
        return f"Could not update two-factor authentication:\n{msg}"

    def _sync_session_controls(self):
        idx = self.sessions_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._sessions):
            self.terminate_btn.Enable(False)
            return

        session = self._sessions[idx]
        # Current session cannot be terminated remotely.
        can_terminate = not bool(session.get("current"))
        self.terminate_btn.Enable(can_terminate)

    def GetFirstName(self):
        return self.first_name_ctrl.GetValue().strip()

    def GetLastName(self):
        return self.last_name_ctrl.GetValue().strip()

    def GetUsername(self):
        return self.username_ctrl.GetValue().strip()

    def GetBio(self):
        return self.bio_ctrl.GetValue().strip()

    def GetPrivacySettings(self):
        return {
            key: choice.GetSelection()
            for key, choice in self._privacy_choices.items()
        }

    def GetAccountTTLDays(self):
        idx = self.ttl_choice.GetSelection()
        if idx != wx.NOT_FOUND:
            return self._ttl_days[idx]
        return 180

    def GetTerminatedSessions(self):
        return self._terminated_hashes

    def GetBirthday(self):
        if not self.bday_set_check.IsChecked():
            return None
        return {
            "day": self.bday_day.GetValue(),
            "month": self.bday_month.GetSelection() + 1,
            "year": (
                self.bday_year.GetValue()
                if self.bday_year_check.IsChecked()
                else None
            ),
        }

    def GetPhotoToUpload(self):
        return self._photo_to_upload

    def GetDeleteCurrentPhoto(self):
        return self._delete_current_photo
