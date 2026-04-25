import threading
import wx

from .announce import list_announcement_backends, list_announcement_voices
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

        # --- Device test buttons ---
        test_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.test_speaker_btn = wx.Button(self, label="Test Speaker")
        self.test_speaker_btn.SetName("Test Speaker")
        self.test_speaker_btn.SetToolTip("Play a test tone through the selected output device")
        self.test_speaker_btn.Bind(wx.EVT_BUTTON, self._on_test_speaker)
        test_sizer.Add(self.test_speaker_btn, flag=wx.ALL, border=5)

        self.test_mic_btn = wx.Button(self, label="Test Microphone")
        self.test_mic_btn.SetName("Test Microphone")
        self.test_mic_btn.SetToolTip("Record a short clip and play it back")
        self.test_mic_btn.Bind(wx.EVT_BUTTON, self._on_test_mic)
        test_sizer.Add(self.test_mic_btn, flag=wx.ALL, border=5)

        audio_box.Add(test_sizer, flag=wx.EXPAND)

        sizer.Add(audio_box, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Video device ---
        video_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Video")

        video_box.Add(
            wx.StaticText(self, label="Camera:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )

        video_devices = sound_manager.get_video_devices()
        camera_choices = ["None (no camera)"] + video_devices
        self.camera_choice = wx.Choice(self, choices=camera_choices)
        self.camera_choice.SetName("Camera")
        current_camera = config.get("camera_device_index", -1)
        if 0 <= current_camera < len(video_devices):
            self.camera_choice.SetSelection(current_camera + 1)
        else:
            self.camera_choice.SetSelection(0)
        video_box.Add(
            self.camera_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        sizer.Add(video_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        # --- Notifications ---
        sounds_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Notifications")
        self.sounds_enabled = wx.CheckBox(
            self, label="Enable notification sounds"
        )
        self.sounds_enabled.SetName("Enable notification sounds")
        self.sounds_enabled.SetValue(config.get("sounds_enabled", True))
        sounds_box.Add(self.sounds_enabled, flag=wx.ALL, border=5)

        self.announcements_enabled = wx.CheckBox(
            self, label="Enable screen reader announcements"
        )
        self.announcements_enabled.SetName("Enable screen reader announcements")
        self.announcements_enabled.SetToolTip(
            "Enable spoken status and message updates for screen reader users"
        )
        self.announcements_enabled.SetValue(
            config.get("announcements_enabled", False)
        )
        sounds_box.Add(self.announcements_enabled, flag=wx.ALL, border=5)

        sounds_box.Add(
            wx.StaticText(self, label="Announcement backend:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self._announcement_backends = list_announcement_backends()
        backend_choices = ["Automatic (best available)"]
        for b in self._announcement_backends:
            backend_choices.append(f"{b['name']} ({b['id']})")
        self.announcement_backend_choice = wx.Choice(self, choices=backend_choices)
        self.announcement_backend_choice.SetName("Announcement backend")
        self.announcement_backend_choice.SetToolTip(
            "Choose automatic backend selection or a specific Prism backend"
        )
        saved_backend = (config.get("announcement_backend", "auto") or "auto").strip()
        if saved_backend and saved_backend.lower() != "auto":
            backend_idx = 0
            for i, b in enumerate(self._announcement_backends, start=1):
                if b["id"].lower() == saved_backend.lower():
                    backend_idx = i
                    break
            self.announcement_backend_choice.SetSelection(backend_idx)
        else:
            self.announcement_backend_choice.SetSelection(0)
        sounds_box.Add(
            self.announcement_backend_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        sounds_box.Add(
            wx.StaticText(self, label="Announcement voice:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.announcement_voice_choice = wx.Choice(self)
        self.announcement_voice_choice.SetName("Announcement voice")
        self.announcement_voice_choice.SetToolTip(
            "Choose a specific voice when supported by the selected backend"
        )
        self._announcement_voice_indices = [-1]
        self._load_announcement_voices(config.get("announcement_voice_index", -1))
        sounds_box.Add(
            self.announcement_voice_choice, flag=wx.EXPAND | wx.ALL, border=5
        )
        self.announcements_enabled.Bind(
            wx.EVT_CHECKBOX, self._on_announcements_enabled_changed
        )
        self.announcement_backend_choice.Bind(
            wx.EVT_CHOICE, self._on_announcement_backend_changed
        )
        self._sync_announcement_controls()

        self.notify_minimized = wx.CheckBox(
            self, label="Show notifications when minimized"
        )
        self.notify_minimized.SetName("Show notifications when minimized")
        self.notify_minimized.SetToolTip(
            "Show a system notification when a new message arrives while Teepee is minimized"
        )
        self.notify_minimized.SetValue(config.get("notify_when_minimized", True))
        sounds_box.Add(self.notify_minimized, flag=wx.ALL, border=5)

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

        # --- Display ---
        display_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Display")

        display_box.Add(
            wx.StaticText(self, label="Time Format:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        time_choices = ["12 hour (1:30 PM)", "24 hour (13:30)"]
        self.time_format_choice = wx.Choice(self, choices=time_choices)
        self.time_format_choice.SetName("Time Format")
        current_tf = config.get("time_format", "24h")
        self.time_format_choice.SetSelection(0 if current_tf == "12h" else 1)
        display_box.Add(
            self.time_format_choice, flag=wx.EXPAND | wx.ALL, border=5
        )

        display_box.Add(
            wx.StaticText(self, label="Number of chats to load:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.chat_limit_spin = wx.SpinCtrl(
            self, min=10, max=500, initial=config.get("chat_limit", 100)
        )
        self.chat_limit_spin.SetName("Number of chats to load")
        display_box.Add(
            self.chat_limit_spin, flag=wx.EXPAND | wx.ALL, border=5
        )

        display_box.Add(
            wx.StaticText(self, label="Number of messages to load per chat:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.message_limit_spin = wx.SpinCtrl(
            self, min=10, max=500, initial=config.get("message_limit", 50)
        )
        self.message_limit_spin.SetName("Number of messages to load per chat")
        display_box.Add(
            self.message_limit_spin, flag=wx.EXPAND | wx.ALL, border=5
        )

        sizer.Add(
            display_box,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # --- Buttons ---
        btn_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((420, -1))
        self.CenterOnParent()
        self.output_choice.SetFocus()
        apply_theme(self)

    def GetOutputDeviceIndex(self):
        return self.output_choice.GetSelection()

    def GetInputDeviceIndex(self):
        return self.input_choice.GetSelection()

    def GetCameraDeviceIndex(self):
        sel = self.camera_choice.GetSelection()
        if sel <= 0:
            return -1
        return sel - 1

    def GetSoundsEnabled(self):
        return self.sounds_enabled.GetValue()

    def GetAnnouncementsEnabled(self):
        return self.announcements_enabled.GetValue()

    def GetAnnouncementBackend(self):
        idx = self.announcement_backend_choice.GetSelection()
        if idx <= 0:
            return "auto"
        if 1 <= idx <= len(self._announcement_backends):
            return self._announcement_backends[idx - 1]["id"]
        return "auto"

    def GetAnnouncementVoiceIndex(self):
        idx = self.announcement_voice_choice.GetSelection()
        if idx == wx.NOT_FOUND:
            return -1
        if 0 <= idx < len(self._announcement_voice_indices):
            return self._announcement_voice_indices[idx]
        return -1

    def GetSoundPack(self):
        idx = self.sound_pack_choice.GetSelection()
        if idx != wx.NOT_FOUND:
            return self.sound_pack_choice.GetString(idx)
        return "default"

    def GetNotifyWhenMinimized(self):
        return self.notify_minimized.GetValue()

    def GetTimeFormat(self):
        return "12h" if self.time_format_choice.GetSelection() == 0 else "24h"

    def GetChatLimit(self):
        return self.chat_limit_spin.GetValue()

    def GetMessageLimit(self):
        return self.message_limit_spin.GetValue()

    def _on_test_speaker(self, event):
        from .announce import announce
        idx = self.output_choice.GetSelection()
        self.sound_manager.set_output_device(idx)
        stream = self.sound_manager.play_test_tone()
        if stream:
            self.test_speaker_btn.SetLabel("Playing...")
            self.test_speaker_btn.SetName("Speaker test playing")
            self.test_speaker_btn.SetToolTip("Playing test tone")
            self.test_speaker_btn.Disable()
            announce("Playing test tone")

            def _reset():
                import time
                time.sleep(2)
                wx.CallAfter(self._speaker_test_done)

            threading.Thread(target=_reset, daemon=True).start()
        else:
            wx.MessageBox(
                "Could not play test tone.",
                "Speaker Test",
                wx.OK | wx.ICON_WARNING,
                self,
            )

    def _speaker_test_done(self):
        from .announce import announce
        if self.test_speaker_btn:
            self.test_speaker_btn.SetLabel("Test Speaker")
            self.test_speaker_btn.SetName("Test Speaker")
            self.test_speaker_btn.SetToolTip("Play a test tone through the selected output device")
            self.test_speaker_btn.Enable()
            self.test_speaker_btn.SetFocus()
            announce("Speaker test complete")

    def _on_test_mic(self, event):
        from .announce import announce
        if getattr(self, "_recording", None) is not None:
            self._stop_mic_test()
            return
        self._recording = self.sound_manager.record_test()
        if self._recording is None:
            wx.MessageBox(
                "Could not start microphone recording.",
                "Microphone Test",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        self.test_mic_btn.SetLabel("Stop Recording (3s)")
        self.test_mic_btn.SetName("Stop Recording")
        self.test_mic_btn.SetToolTip("Stop recording and play it back")
        announce("Recording for 3 seconds")

        def _auto_stop():
            import time
            time.sleep(3)
            wx.CallAfter(self._stop_mic_test)

        threading.Thread(target=_auto_stop, daemon=True).start()

    def _stop_mic_test(self):
        from .announce import announce
        rec = getattr(self, "_recording", None)
        self._recording = None
        self.test_mic_btn.SetLabel("Test Microphone")
        self.test_mic_btn.SetName("Test Microphone")
        self.test_mic_btn.SetToolTip("Record a short clip and play it back")
        if rec is not None:
            stream = self.sound_manager.stop_recording_and_play(rec)
            if stream:
                self.test_mic_btn.SetLabel("Playing back...")
                self.test_mic_btn.SetName("Microphone playback")
                self.test_mic_btn.SetToolTip("Playing back microphone recording")
                self.test_mic_btn.Disable()
                announce("Playing back recording")

                def _reset():
                    import time
                    time.sleep(3)
                    wx.CallAfter(self._mic_playback_done)

                threading.Thread(target=_reset, daemon=True).start()

    def _mic_playback_done(self):
        from .announce import announce
        if self.test_mic_btn:
            self.test_mic_btn.SetLabel("Test Microphone")
            self.test_mic_btn.SetName("Test Microphone")
            self.test_mic_btn.SetToolTip("Record a short clip and play it back")
            self.test_mic_btn.Enable()
            self.test_mic_btn.SetFocus()
            announce("Microphone test complete")

    def _selected_announcement_backend_id(self):
        idx = self.announcement_backend_choice.GetSelection()
        if idx <= 0:
            return ""
        if 1 <= idx <= len(self._announcement_backends):
            return self._announcement_backends[idx - 1]["id"]
        return ""

    def _load_announcement_voices(self, selected_voice=-1):
        backend_id = self._selected_announcement_backend_id()
        voices = list_announcement_voices(backend_id)
        choices = ["Automatic (default voice)"]
        indices = [-1]
        sel = 0
        for i, voice in enumerate(voices, start=1):
            lang = voice.get("language", "")
            label = voice.get("name", f"Voice {voice.get('index', i - 1)}")
            if lang:
                label = f"{label} [{lang}]"
            choices.append(label)
            voice_index = int(voice.get("index", i - 1))
            indices.append(voice_index)
            if voice_index == selected_voice:
                sel = i
        self._announcement_voice_indices = indices
        self.announcement_voice_choice.SetItems(choices)
        self.announcement_voice_choice.SetSelection(sel)

    def _on_announcement_backend_changed(self, event):
        self._load_announcement_voices(-1)

    def _sync_announcement_controls(self):
        enabled = self.announcements_enabled.GetValue()
        self.announcement_backend_choice.Enable(enabled)
        self.announcement_voice_choice.Enable(enabled)

    def _on_announcements_enabled_changed(self, event):
        self._sync_announcement_controls()
