import wx

from .theme import apply_theme


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, config, sound_manager):
        super().__init__(
            parent,
            title="Teepee - Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.config = config
        self.sound_manager = sound_manager

        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Audio output ---
        audio_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Audio Devices")

        audio_box.Add(
            wx.StaticText(self, label="Output Device:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )

        output_devices = sound_manager.get_output_devices()
        self.output_choice = wx.Choice(self, choices=output_devices)
        self.output_choice.SetName("Output Device")
        current_output = config.get("output_device_index", -1)
        if 0 <= current_output < len(output_devices):
            self.output_choice.SetSelection(current_output)
        elif output_devices:
            self.output_choice.SetSelection(0)
        audio_box.Add(
            self.output_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        # --- Audio input ---
        audio_box.Add(
            wx.StaticText(self, label="Input Device:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )

        input_devices = sound_manager.get_input_devices()
        self.input_choice = wx.Choice(self, choices=input_devices)
        self.input_choice.SetName("Input Device")
        current_input = config.get("input_device_index", -1)
        if 0 <= current_input < len(input_devices):
            self.input_choice.SetSelection(current_input)
        elif input_devices:
            self.input_choice.SetSelection(0)
        audio_box.Add(
            self.input_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        sizer.Add(audio_box, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Notifications ---
        sounds_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Notifications")
        self.sounds_enabled = wx.CheckBox(
            self, label="Enable notification sounds"
        )
        self.sounds_enabled.SetValue(config.get("sounds_enabled", True))
        sounds_box.Add(self.sounds_enabled, flag=wx.ALL, border=5)

        sounds_box.Add(
            wx.StaticText(self, label="Sound Pack:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        packs = config.get_sound_packs()
        self.sound_pack_choice = wx.Choice(self, choices=packs)
        self.sound_pack_choice.SetName("Sound Pack")
        current_pack = config.get("sound_pack", "default")
        if current_pack in packs:
            self.sound_pack_choice.SetSelection(packs.index(current_pack))
        elif packs:
            self.sound_pack_choice.SetSelection(0)
        sounds_box.Add(
            self.sound_pack_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        sizer.Add(
            sounds_box,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # --- Buttons ---
        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((420, -1))
        self.CenterOnParent()
        apply_theme(self)

    def GetOutputDeviceIndex(self):
        return self.output_choice.GetSelection()

    def GetInputDeviceIndex(self):
        return self.input_choice.GetSelection()

    def GetSoundsEnabled(self):
        return self.sounds_enabled.GetValue()

    def GetSoundPack(self):
        idx = self.sound_pack_choice.GetSelection()
        if idx != wx.NOT_FOUND:
            return self.sound_pack_choice.GetString(idx)
        return "default"
