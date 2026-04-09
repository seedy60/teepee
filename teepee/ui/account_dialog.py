import os
from datetime import datetime as _dt

import wx

from .theme import apply_theme


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
        self.upload_photo_btn.SetToolTip("Upload a new profile photo")
        photo_sizer.Add(self.upload_photo_btn, 0, wx.ALL, 2)

        self.delete_photo_btn = wx.Button(
            panel, label="D&elete Current Photo"
        )
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
        status_text = "Enabled" if d.get("has_2fa") else "Disabled"
        tfa_ctrl = wx.TextCtrl(
            panel, value=status_text, style=wx.TE_READONLY
        )
        tfa_ctrl.SetName("Two-factor authentication")
        sizer.Add(
            tfa_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10
        )

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
        self.terminate_btn.SetToolTip("End the selected session remotely")
        sizer.Add(
            self.terminate_btn,
            flag=wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )
        self.terminate_btn.Bind(
            wx.EVT_BUTTON, self._on_terminate_session
        )

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

        count = self.sessions_list.GetCount()
        if count > 0:
            new_sel = min(idx, count - 1)
            self.sessions_list.SetSelection(new_sel)
            self.sessions_list.SetFocus()
        else:
            self.terminate_btn.SetFocus()

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
