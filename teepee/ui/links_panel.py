import logging
import re
import threading
import webbrowser

import wx

from .announce import announce

log = logging.getLogger(__name__)

_URL_RE = re.compile(r'https?://[^\s<>"\')]+')


def extract_urls_from_message(msg):
    """Return a list of URLs contained in a telethon message.

    Looks at inline entities (both plain URL entities and hidden text-link
    entities), the linked web page preview, and finally a plain-text regex as
    a fallback. Order is preserved and duplicates within one message removed.
    """
    urls = []
    text = msg.message or ""

    for entity in (msg.entities or []):
        type_name = type(entity).__name__
        if type_name == "MessageEntityTextUrl":
            url = getattr(entity, "url", None)
            if url:
                urls.append(url)
        elif type_name == "MessageEntityUrl":
            try:
                # Entity offsets index UTF-16 code units; encode to match.
                encoded = text.encode("utf-16-le")
                start = entity.offset * 2
                end = (entity.offset + entity.length) * 2
                piece = encoded[start:end].decode("utf-16-le")
                if piece:
                    urls.append(piece if "://" in piece else f"https://{piece}")
            except Exception:
                pass

    webpage = getattr(msg, "web_preview", None)
    web_url = getattr(webpage, "url", None) if webpage else None
    if web_url:
        urls.append(web_url)

    if not urls:
        urls.extend(_URL_RE.findall(text))

    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


class LinksPanel(wx.Panel):
    def __init__(self, parent, frame):
        super().__init__(parent)
        self.frame = frame
        self._entity = None
        self._loading = False
        # Each item: dict with url, sender, date_str (one row per URL).
        self._links = []
        self._oldest_msg_id = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        list_label = wx.StaticText(self, label="Links:")
        sizer.Add(list_label, 0, wx.LEFT | wx.TOP, 5)

        self.links_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.links_list.SetName("Links")
        self.links_list.SetToolTip(
            "Links shared in this chat. Enter to open, or use the buttons below."
        )
        sizer.Add(self.links_list, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.open_btn = wx.Button(self, label="&Open")
        self.open_btn.SetName("Open Link")
        self.open_btn.SetToolTip("Open the selected link in your browser")
        btn_sizer.Add(self.open_btn, 0, wx.ALL, 5)

        self.copy_btn = wx.Button(self, label="&Copy")
        self.copy_btn.SetName("Copy Link")
        self.copy_btn.SetToolTip("Copy the selected link to the clipboard")
        btn_sizer.Add(self.copy_btn, 0, wx.ALL, 5)

        self.load_more_btn = wx.Button(self, label="&Load More")
        self.load_more_btn.SetName("Load More")
        self.load_more_btn.SetToolTip("Load older links from this chat")
        btn_sizer.Add(self.load_more_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT, 5)

        self.SetSizer(sizer)

        self.open_btn.Bind(wx.EVT_BUTTON, self._on_open)
        self.copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
        self.load_more_btn.Bind(wx.EVT_BUTTON, self._on_load_more)
        self.links_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_open)
        self.links_list.Bind(wx.EVT_LISTBOX, self._on_selected)
        self.links_list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)

        self._sync_controls()

    # ------------------------------------------------------------ loading

    def set_entity(self, entity):
        self._entity = entity
        self._loading = False
        self._links = []
        self._oldest_msg_id = None
        self.links_list.Clear()
        self._sync_controls()

    def load_links(self, entity):
        if self._loading:
            return
        self._entity = entity
        self._loading = True
        self._links = []
        self._oldest_msg_id = None
        self.links_list.Freeze()
        self.links_list.Clear()
        self.links_list.Thaw()
        self._sync_controls()
        self._set_status("Loading links...")
        announce("Loading links")
        threading.Thread(
            target=self._load_thread,
            args=(entity, False),
            daemon=True,
        ).start()

    def _on_load_more(self, event):
        if not self._entity or self._loading:
            return
        self._loading = True
        self._sync_controls()
        self._set_status("Loading more links...")
        threading.Thread(
            target=self._load_thread,
            args=(self._entity, True),
            daemon=True,
        ).start()

    def _load_thread(self, entity, append):
        try:
            offset_id = self._oldest_msg_id if append else 0
            messages = self.frame.tg.submit_wait(
                self.frame.tg.search_links(
                    entity, limit=50, offset_id=offset_id or 0,
                )
            )
            wx.CallAfter(self._on_loaded, list(messages), append)
        except Exception as e:
            log.error("Failed to load links: %s", e)
            wx.CallAfter(self._on_load_failed, str(e))

    def _on_load_failed(self, error_text):
        self._loading = False
        self._set_status(f"Failed to load links: {error_text}")
        announce(f"Failed to load links: {error_text}")
        self._sync_controls()

    def _on_loaded(self, messages, append):
        self._loading = False
        if messages:
            self._oldest_msg_id = messages[-1].id
        new_rows = []
        for msg in messages:
            urls = extract_urls_from_message(msg)
            if not urls:
                continue
            sender = self._sender_name(msg)
            date_str = self._date_str(msg)
            for url in urls:
                new_rows.append(
                    {"url": url, "sender": sender, "date": date_str}
                )
        if append:
            self._links.extend(new_rows)
            for row in new_rows:
                self.links_list.Append(self._format_row(row))
        else:
            self._links = new_rows
            self.links_list.Freeze()
            self.links_list.Clear()
            for row in new_rows:
                self.links_list.Append(self._format_row(row))
            self.links_list.Thaw()
            if self.links_list.GetCount() > 0:
                self.links_list.SetSelection(0)
        count = len(self._links)
        status = f"{count} link{'s' if count != 1 else ''} found"
        self._set_status(status)
        announce(status)
        self._sync_controls()

    # ------------------------------------------------------------ actions

    def _selected_url(self):
        idx = self.links_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._links):
            return None
        return self._links[idx]["url"]

    def open_selected(self):
        url = self._selected_url()
        if not url:
            wx.MessageBox(
                "Select a link to open.",
                "Open Link",
                wx.OK | wx.ICON_INFORMATION,
                self.GetTopLevelParent(),
            )
            return
        webbrowser.open(url)
        self._set_status("Opening link")
        announce("Opening link")

    def copy_selected(self):
        url = self._selected_url()
        if not url:
            wx.MessageBox(
                "Select a link to copy.",
                "Copy Link",
                wx.OK | wx.ICON_INFORMATION,
                self.GetTopLevelParent(),
            )
            return
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(url))
            wx.TheClipboard.Close()
            self._set_status("Link copied")
            announce("Link copied")

    def _on_open(self, event):
        self.open_selected()

    def _on_copy(self, event):
        self.copy_selected()

    def _on_list_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.open_selected()
        else:
            event.Skip()

    def _on_selected(self, event):
        self._sync_controls()
        event.Skip()

    def _sync_controls(self):
        has_entity = self._entity is not None
        has_selection = (
            self.links_list.GetSelection() != wx.NOT_FOUND
            and self.links_list.GetSelection() < len(self._links)
        )
        self.links_list.Enable(has_entity)
        self.open_btn.Enable(has_entity and has_selection)
        self.copy_btn.Enable(has_entity and has_selection)
        self.load_more_btn.Enable(has_entity and not self._loading)

    # ------------------------------------------------------------ helpers

    def _set_status(self, text):
        top = self.GetTopLevelParent()
        if hasattr(top, "SetStatusText"):
            top.SetStatusText(text)
        if hasattr(self.frame, "SetStatusText"):
            self.frame.SetStatusText(text)

    @staticmethod
    def _sender_name(msg):
        sender = getattr(msg, "sender", None)
        if sender:
            first = getattr(sender, "first_name", None) or ""
            last = getattr(sender, "last_name", None) or ""
            name = f"{first} {last}".strip()
            if not name:
                name = getattr(sender, "title", None) or ""
            return name
        return ""

    def _date_str(self, msg):
        if not msg.date:
            return ""
        tf = self.frame.config.get("time_format", "24h")
        time_fmt = "%I:%M %p" if tf == "12h" else "%H:%M"
        return msg.date.astimezone().strftime(f"%Y-%m-%d {time_fmt}")

    @staticmethod
    def _format_row(row):
        parts = [row["url"]]
        if row["sender"]:
            parts.append(f"by {row['sender']}")
        if row["date"]:
            parts.append(row["date"])
        return " - ".join(parts)
