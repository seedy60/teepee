import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import wx

from . import APP_VERSION

log = logging.getLogger(__name__)

GITHUB_REPO = "seedy60/teepee"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/teepee.zip"


def _parse_version(tag: str) -> tuple[int, ...]:
    tag = tag.lstrip("vV")
    parts = []
    for part in tag.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _fetch_latest_tag() -> str | None:
    req = Request(LATEST_RELEASE_API)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "Teepee-Updater")
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("tag_name")
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        log.error("Failed to check for updates: %s", exc)
        return None


def check_for_update() -> str | None:
    latest_tag = _fetch_latest_tag()
    if latest_tag is None:
        return None
    if _parse_version(latest_tag) > _parse_version(APP_VERSION):
        return latest_tag
    return None


def _download_and_apply(parent: wx.Window) -> bool:
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    tmp_zip = Path(tempfile.mkdtemp()) / "teepee_update.zip"

    try:
        req = Request(DOWNLOAD_URL)
        req.add_header("User-Agent", "Teepee-Updater")
        with urlopen(req, timeout=120) as resp:
            tmp_zip.write_bytes(resp.read())
    except (URLError, OSError) as exc:
        log.error("Download failed: %s", exc)
        wx.CallAfter(
            wx.MessageBox,
            f"Download failed:\n{exc}",
            "Update Error",
            wx.OK | wx.ICON_ERROR,
            parent,
        )
        return False

    try:
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            for member in zf.infolist():
                parts = Path(member.filename).parts
                if len(parts) <= 1:
                    continue
                rel = Path(*parts[1:])
                target = app_dir / rel
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    except (zipfile.BadZipFile, OSError) as exc:
        log.error("Extraction failed: %s", exc)
        wx.CallAfter(
            wx.MessageBox,
            f"Extraction failed:\n{exc}",
            "Update Error",
            wx.OK | wx.ICON_ERROR,
            parent,
        )
        return False
    finally:
        try:
            tmp_zip.unlink(missing_ok=True)
            tmp_zip.parent.rmdir()
        except OSError:
            pass

    return True


def _restart_app():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        subprocess.Popen([exe])
    else:
        subprocess.Popen([sys.executable] + sys.argv)
    wx.GetApp().GetTopWindow().quit()


def prompt_and_update(parent: wx.Window, latest_tag: str):
    result = wx.MessageBox(
        f"A new version of Teepee is available: {latest_tag}\n"
        f"You are currently running version {APP_VERSION}.\n\n"
        "Would you like to download and install the update now?",
        "Update Available",
        wx.YES_NO | wx.ICON_INFORMATION,
        parent,
    )
    if result != wx.YES:
        return

    from .ui.theme import apply_theme

    progress = wx.ProgressDialog(
        "Updating Teepee",
        "Downloading and installing update, please wait...",
        maximum=100,
        parent=parent,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
    )
    apply_theme(progress)
    progress.Pulse()

    def _do_update():
        success = _download_and_apply(parent)
        wx.CallAfter(_finish_update, success, progress, parent)

    threading.Thread(target=_do_update, daemon=True).start()


def _finish_update(success: bool, progress: wx.ProgressDialog, parent: wx.Window):
    progress.Destroy()
    if success:
        wx.MessageBox(
            "Update installed successfully. Teepee will now restart.",
            "Update Complete",
            wx.OK | wx.ICON_INFORMATION,
            parent,
        )
        _restart_app()


def check_for_update_background(parent: wx.Window):
    def _check():
        latest_tag = check_for_update()
        if latest_tag:
            wx.CallAfter(prompt_and_update, parent, latest_tag)

    threading.Thread(target=_check, daemon=True).start()


def check_for_update_manual(parent: wx.Window):
    def _check():
        latest_tag = check_for_update()
        if latest_tag:
            wx.CallAfter(prompt_and_update, parent, latest_tag)
        else:
            wx.CallAfter(
                wx.MessageBox,
                "You are running the highest version of Teepee.",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
                parent,
            )

    threading.Thread(target=_check, daemon=True).start()
