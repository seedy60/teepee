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


def cleanup_old_files():
    """Remove the staging directory left over from a previous update."""
    if not getattr(sys, "frozen", False):
        return
    staging = Path(sys.executable).parent / "_update_staging"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)


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


def _download_and_extract(parent: wx.Window) -> Path | None:
    """Download the update zip and extract it to a staging directory.

    Returns the staging directory on success, or *None* on failure.
    The staging directory contains the unpacked files ready to be
    copied over the application directory once the app has exited.
    """
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    staging = app_dir / "_update_staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

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
        return None

    try:
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            for member in zf.infolist():
                parts = Path(member.filename).parts
                if len(parts) <= 1:
                    continue
                rel = Path(*parts[1:])
                target = staging / rel
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
        return None
    finally:
        try:
            tmp_zip.unlink(missing_ok=True)
            tmp_zip.parent.rmdir()
        except OSError:
            pass

    return staging


def _apply_via_batch(staging: Path):
    """Write a batch script that waits for the app to exit, copies new
    files over the install directory, then relaunches the app."""
    app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    exe = sys.executable if getattr(sys, "frozen", False) else None
    pid = os.getpid()
    bat = staging / "_apply_update.bat"
    lines = [
        "@echo off",
        f'echo Waiting for Teepee (PID {pid}) to exit...',
        ":wait",
        f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL',
        "if not errorlevel 1 (",
        "    timeout /t 1 /nobreak >NUL",
        "    goto wait",
        ")",
        f'echo Copying files to "{app_dir}"...',
        f'xcopy /s /y /q "{staging}\\*" "{app_dir}\\"',
    ]
    if exe:
        lines.append(f'echo Starting Teepee...')
        lines.append(f'start "" "{exe}"')
    lines += [
        f'rmdir /s /q "{staging}"',
        "del /f /q \"%~f0\"",
    ]
    bat.write_text("\r\n".join(lines), encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
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
        staging = _download_and_extract(parent)
        wx.CallAfter(_finish_update, staging, progress, parent)

    threading.Thread(target=_do_update, daemon=True).start()


def _finish_update(staging: Path | None, progress: wx.ProgressDialog, parent: wx.Window):
    progress.Destroy()
    if staging:
        wx.MessageBox(
            "Update downloaded. Teepee will now close, install the update, and restart.",
            "Update Ready",
            wx.OK | wx.ICON_INFORMATION,
            parent,
        )
        _apply_via_batch(staging)


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
