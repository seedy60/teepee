import logging
import os
import threading

import wx

from .announce import announce
from .theme import apply_theme

log = logging.getLogger(__name__)


class FilesPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self._files = []
        self._filtered = []
        self._entity = None
        self._loading = False
        self._search_timer = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        search_label = wx.StaticText(self, label="Search files:")
        sizer.Add(search_label, 0, wx.LEFT | wx.TOP, 5)

        self.search_ctrl = wx.TextCtrl(self)
        self.search_ctrl.SetName("Search files")
        sizer.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        list_label = wx.StaticText(self, label="Files:")
        sizer.Add(list_label, 0, wx.LEFT, 5)

        self.file_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.file_list.SetName("Files")
        sizer.Add(self.file_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.download_btn = wx.Button(self, label="&Download")
        self.download_btn.SetName("Download")
        self.download_btn.SetToolTip("Download the selected file")
        btn_sizer.Add(self.download_btn, 0, wx.ALL, 5)

        self.load_more_btn = wx.Button(self, label="&Load More")
        self.load_more_btn.SetName("Load More")
        self.load_more_btn.SetToolTip("Load more files from this chat")
        btn_sizer.Add(self.load_more_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT, 5)

        self.SetSizer(sizer)

        self.search_ctrl.Bind(wx.EVT_TEXT, self._on_search_text)
        self.download_btn.Bind(wx.EVT_BUTTON, self._on_download)
        self.load_more_btn.Bind(wx.EVT_BUTTON, self._on_load_more)
        self.file_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_download)

    def set_entity(self, entity):
        self._entity = entity
        self._files = []
        self._filtered = []
        self.search_ctrl.SetValue("")
        self.file_list.Clear()

    def load_files(self, entity, query=""):
        if self._loading:
            return
        self._entity = entity
        self._loading = True
        self._files = []
        self._filtered = []
        self.file_list.Freeze()
        self.file_list.Clear()
        self.file_list.Thaw()
        self._set_status("Loading files...")
        announce("Loading files")
        threading.Thread(
            target=self._load_files_thread,
            args=(entity, query, False),
            daemon=True,
        ).start()

    def _load_files_thread(self, entity, query, append):
        try:
            offset_id = 0
            if append and self._files:
                offset_id = self._files[-1].id
            files = self.frame.tg.submit_wait(
                self.frame.tg.search_files(
                    entity, query=query, limit=50, offset_id=offset_id,
                )
            )
            wx.CallAfter(self._on_files_loaded, list(files), append)
        except Exception as e:
            log.error("Failed to load files: %s", e)
            wx.CallAfter(self._set_status, f"Failed to load files: {e}")
            self._loading = False

    def _on_files_loaded(self, files, append):
        self._loading = False
        if append:
            self._files.extend(files)
        else:
            self._files = files
        self._apply_filter()
        count = len(self._files)
        status = f"{count} file{'s' if count != 1 else ''} found"
        self._set_status(status)
        announce(status)

    def _apply_filter(self):
        query = self.search_ctrl.GetValue().strip().lower()
        if query:
            self._filtered = [
                f for f in self._files
                if query in self._file_display_name(f).lower()
            ]
        else:
            self._filtered = list(self._files)
        self.file_list.Freeze()
        self.file_list.Clear()
        for f in self._filtered:
            self.file_list.Append(self._format_file(f))
        self.file_list.Thaw()
        if self.file_list.GetCount() > 0:
            self.file_list.SetSelection(0)

    def _on_search_text(self, event):
        if self._search_timer:
            self._search_timer.Stop()
        self._search_timer = wx.CallLater(300, self._do_search)

    def _do_search(self):
        if not self._entity:
            return
        query = self.search_ctrl.GetValue().strip()
        if query:
            # Search server-side for better results
            if self._loading:
                return
            self._loading = True
            self._set_status("Searching...")
            threading.Thread(
                target=self._load_files_thread,
                args=(self._entity, query, False),
                daemon=True,
            ).start()
        else:
            # Empty query: reload all files
            self.load_files(self._entity)

    def _on_load_more(self, event):
        if not self._entity or self._loading:
            return
        self._loading = True
        query = self.search_ctrl.GetValue().strip()
        self._set_status("Loading more files...")
        threading.Thread(
            target=self._load_files_thread,
            args=(self._entity, query, True),
            daemon=True,
        ).start()

    def _on_download(self, event):
        idx = self.file_list.GetSelection()
        if idx == wx.NOT_FOUND:
            parent = self.GetTopLevelParent()
            wx.MessageBox(
                "Select a file to download.",
                "Download",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )
            return
        if idx >= len(self._filtered):
            return
        msg = self._filtered[idx]
        suggested = self._file_display_name(msg)
        parent = self.GetTopLevelParent()
        with wx.FileDialog(
            parent,
            "Save file",
            defaultFile=suggested,
            wildcard="All files (*.*)|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            save_path = dlg.GetPath()
        self._set_status("Downloading...")
        announce("Downloading")
        threading.Thread(
            target=self._download_thread,
            args=(msg, save_path),
            daemon=True,
        ).start()

    def _download_thread(self, msg, save_path):
        try:
            result = self.frame.tg.submit_wait(
                self.frame.tg.download_media(msg, save_path)
            )
            if result:
                name = os.path.basename(save_path)
                wx.CallAfter(self._set_status, f"Saved {name}")
                wx.CallAfter(announce, f"Saved {name}")
            else:
                wx.CallAfter(self._set_status, "Download failed")
                wx.CallAfter(announce, "Download failed")
        except Exception as e:
            log.error("Failed to download file: %s", e)
            wx.CallAfter(self._set_status, f"Download failed: {e}")

    def _set_status(self, text):
        top = self.GetTopLevelParent()
        if hasattr(top, "SetStatusText"):
            top.SetStatusText(text)
        if hasattr(self.frame, "SetStatusText"):
            self.frame.SetStatusText(text)

    @staticmethod
    def _file_display_name(msg):
        if msg.document:
            for attr in getattr(msg.document, "attributes", []):
                name = getattr(attr, "file_name", None)
                if name:
                    return name
        if msg.photo:
            return f"photo_{msg.id}.jpg"
        if msg.video or msg.video_note:
            return f"video_{msg.id}.mp4"
        if msg.audio:
            return f"audio_{msg.id}.mp3"
        return f"file_{msg.id}"

    @staticmethod
    def _file_size_str(msg):
        size = None
        if msg.document:
            size = getattr(msg.document, "size", None)
        elif msg.photo:
            sizes = getattr(msg.photo, "sizes", [])
            if sizes:
                last = sizes[-1]
                size = getattr(last, "size", None) or getattr(last, "w", 0) * getattr(last, "h", 0)
        if size is None:
            return ""
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _format_file(self, msg):
        name = self._file_display_name(msg)
        size = self._file_size_str(msg)
        date_str = ""
        if msg.date:
            tf = self.frame.config.get("time_format", "24h")
            time_fmt = "%I:%M %p" if tf == "12h" else "%H:%M"
            date_str = msg.date.astimezone().strftime(f"%Y-%m-%d {time_fmt}")
        sender = ""
        if msg.sender:
            first = getattr(msg.sender, "first_name", None) or ""
            last = getattr(msg.sender, "last_name", None) or ""
            sender = f"{first} {last}".strip()
            if not sender:
                sender = getattr(msg.sender, "title", None) or ""
        parts = [name]
        if size:
            parts.append(size)
        if sender:
            parts.append(f"by {sender}")
        if date_str:
            parts.append(date_str)
        return " - ".join(parts)
