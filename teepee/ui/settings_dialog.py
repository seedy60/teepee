import threading
import wx

from ..config import DEFAULT_GEMINI_MODEL, DEFAULT_MESSAGE_TEMPLATE
from .. import gemini
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

        template_help = (
            "Message Template (placeholders: [user], [msg], [ftype], "
            "[fname], [fsize], [datetime], [seen]):"
        )
        display_box.Add(
            wx.StaticText(self, label=template_help),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.message_template_ctrl = wx.TextCtrl(
            self,
            value=config.get("message_template", DEFAULT_MESSAGE_TEMPLATE) or "",
        )
        self.message_template_ctrl.SetName("Message Template")
        self.message_template_ctrl.SetToolTip(
            "Controls how each message is presented in a chat.\n"
            "[user] - sender name\n"
            "[msg] - message content\n"
            "[ftype] - attachment type (e.g. Photo, Document)\n"
            "[fname] - attachment file name\n"
            "[fsize] - attachment file size\n"
            "[datetime] - time or date the message was sent\n"
            "[seen] - sent/seen status for outgoing messages"
        )
        display_box.Add(
            self.message_template_ctrl, flag=wx.EXPAND | wx.ALL, border=5
        )

        self.reset_template_btn = wx.Button(
            self, label="Reset Template to &Default"
        )
        self.reset_template_btn.SetName("Reset Template to Default")
        self.reset_template_btn.SetToolTip(
            "Replace the current template with the built-in default"
        )
        self.reset_template_btn.Bind(wx.EVT_BUTTON, self._on_reset_template)
        display_box.Add(
            self.reset_template_btn, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5
        )

        sizer.Add(
            display_box,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=10,
        )

        # --- AI descriptions ---
        ai_box = wx.StaticBoxSizer(wx.VERTICAL, self, "AI descriptions")
        ai_box.Add(
            wx.StaticText(
                self,
                label=(
                    "Gemini API key (for describing images and videos that\n"
                    "arrive without a useful caption):"
                ),
            ),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        self.gemini_key_ctrl = wx.TextCtrl(
            self,
            value=config.get_gemini_api_key() or "",
            style=wx.TE_PASSWORD,
        )
        self.gemini_key_ctrl.SetName("Gemini API key")
        self.gemini_key_ctrl.SetToolTip(
            "Paste your Google Gemini API key from aistudio.google.com. "
            "Leave blank to disable AI descriptions."
        )
        ai_box.Add(
            self.gemini_key_ctrl, flag=wx.EXPAND | wx.ALL, border=5
        )

        ai_box.Add(
            wx.StaticText(self, label="Model:"),
            flag=wx.LEFT | wx.TOP,
            border=5,
        )
        current_model = config.get("gemini_model", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL
        model_choices = list(gemini.COMMON_MODELS)
        if current_model not in model_choices:
            model_choices.insert(0, current_model)
        self.gemini_model_combo = wx.ComboBox(
            self,
            value=current_model,
            choices=model_choices,
            style=wx.CB_DROPDOWN,
        )
        self.gemini_model_combo.SetName("Gemini model")
        self.gemini_model_combo.SetToolTip(
            "Choose a Gemini model, or type one. Press Refresh models to "
            "list the models available to your API key."
        )
        ai_box.Add(
            self.gemini_model_combo, flag=wx.EXPAND | wx.ALL, border=5
        )

        self.refresh_models_btn = wx.Button(self, label="&Refresh models")
        self.refresh_models_btn.SetName("Refresh models")
        self.refresh_models_btn.SetToolTip(
            "Fetch the list of models available to the entered API key"
        )
        self.refresh_models_btn.Bind(wx.EVT_BUTTON, self._on_refresh_models)
        ai_box.Add(
            self.refresh_models_btn,
            flag=wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=5,
        )

        sizer.Add(
            ai_box,
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

        # Automatically pull the live model list if a key is already saved, so
        # the dropdown reflects the latest models without a manual refresh.
        self._models_loading = False
        saved_key = config.get_gemini_api_key()
        if saved_key:
            self._start_model_fetch(saved_key, manual=False)

    def GetGeminiApiKey(self):
        return self.gemini_key_ctrl.GetValue().strip()

    def GetGeminiModel(self):
        value = self.gemini_model_combo.GetValue().strip()
        return value or DEFAULT_GEMINI_MODEL

    def _on_refresh_models(self, event):
        api_key = self.gemini_key_ctrl.GetValue().strip()
        if not api_key:
            wx.MessageBox(
                "Enter your Gemini API key first, then refresh.",
                "Refresh Models",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.gemini_key_ctrl.SetFocus()
            return
        self._start_model_fetch(api_key, manual=True)

    def _start_model_fetch(self, api_key, manual):
        if self._models_loading:
            return
        self._models_loading = True
        self.refresh_models_btn.Enable(False)
        self.refresh_models_btn.SetLabel("Refreshing...")
        threading.Thread(
            target=self._refresh_models_thread,
            args=(api_key, manual),
            daemon=True,
        ).start()

    def _refresh_models_thread(self, api_key, manual):
        try:
            models = gemini.list_models(api_key)
            wx.CallAfter(self._on_models_loaded, models, None, manual)
        except gemini.GeminiError as e:
            wx.CallAfter(self._on_models_loaded, None, str(e), manual)
        except Exception as e:
            wx.CallAfter(
                self._on_models_loaded, None, f"Unexpected error: {e}", manual
            )

    def _on_models_loaded(self, models, error, manual):
        # The dialog may have been closed while the fetch was in flight.
        try:
            self.refresh_models_btn.Enable(True)
            self.refresh_models_btn.SetLabel("&Refresh models")
        except RuntimeError:
            return
        self._models_loading = False
        if error:
            # Auto-fetch on open fails quietly; only the manual button reports.
            if manual:
                wx.MessageBox(
                    error, "Refresh Models", wx.OK | wx.ICON_WARNING, self
                )
            return
        if not models:
            if manual:
                wx.MessageBox(
                    "No usable models were returned for this key.",
                    "Refresh Models",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            return
        current = self.gemini_model_combo.GetValue().strip()
        self.gemini_model_combo.Set(models)
        if current in models:
            self.gemini_model_combo.SetValue(current)
        elif current:
            # Preserve a custom/typed model even if the live list lacks it.
            self.gemini_model_combo.SetValue(current)
        else:
            self.gemini_model_combo.SetValue(models[0])
        if manual:
            self.gemini_model_combo.SetFocus()
            from .announce import announce
            announce(f"{len(models)} models available")

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

    def GetMessageTemplate(self):
        value = self.message_template_ctrl.GetValue()
        value = (
            value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()
        )
        return value or DEFAULT_MESSAGE_TEMPLATE

    def _on_reset_template(self, event):
        self.message_template_ctrl.SetValue(DEFAULT_MESSAGE_TEMPLATE)
        self.message_template_ctrl.SetFocus()

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
