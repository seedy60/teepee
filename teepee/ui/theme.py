import ctypes
import sys

import wx

_dark_mode = None
_high_contrast = None


def is_high_contrast():
    global _high_contrast
    if _high_contrast is not None:
        return _high_contrast
    if sys.platform == "win32":
        try:
            class HIGHCONTRAST(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("dwFlags", ctypes.c_uint),
                    ("lpszDefaultScheme", ctypes.c_wchar_p),
                ]
            hc = HIGHCONTRAST()
            hc.cbSize = ctypes.sizeof(HIGHCONTRAST)
            ctypes.windll.user32.SystemParametersInfoW(
                0x0042, hc.cbSize, ctypes.byref(hc), 0
            )
            _high_contrast = bool(hc.dwFlags & 1)
        except Exception:
            _high_contrast = False
    else:
        _high_contrast = False
    return _high_contrast


def is_dark_mode():
    global _dark_mode
    if _dark_mode is not None:
        return _dark_mode
    try:
        appearance = wx.SystemSettings.GetAppearance()
        _dark_mode = appearance.IsDark()
    except AttributeError:
        _dark_mode = False
    return _dark_mode


def apply_dark_title_bar(window):
    if sys.platform != "win32" or not is_dark_mode():
        return
    try:
        hwnd = window.GetHandle()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        pass


def apply_theme(window):
    if is_high_contrast() or not is_dark_mode():
        return
    if isinstance(window, wx.TopLevelWindow):
        apply_dark_title_bar(window)
    _apply_colors(window)


def _system_color(key, fallback):
    try:
        return wx.SystemSettings.GetColour(key)
    except Exception:
        return fallback


def _apply_colors(window):
    bg = _system_color(wx.SYS_COLOUR_WINDOW, wx.Colour(30, 30, 30))
    fg = _system_color(wx.SYS_COLOUR_WINDOWTEXT, wx.Colour(212, 212, 212))
    ctrl_bg = _system_color(wx.SYS_COLOUR_3DFACE, wx.Colour(45, 45, 45))
    border_bg = _system_color(wx.SYS_COLOUR_BTNFACE, wx.Colour(60, 60, 60))

    if isinstance(window, (wx.TextCtrl, wx.ListBox, wx.Choice, wx.SpinCtrl)):
        window.SetBackgroundColour(ctrl_bg)
        window.SetForegroundColour(fg)
    elif isinstance(window, wx.StatusBar):
        window.SetBackgroundColour(bg)
        window.SetForegroundColour(fg)
    elif isinstance(window, wx.Button):
        window.SetBackgroundColour(border_bg)
        window.SetForegroundColour(fg)
    elif isinstance(window, (wx.Panel, wx.Dialog, wx.Frame)):
        window.SetBackgroundColour(bg)
        window.SetForegroundColour(fg)
    elif isinstance(window, wx.StaticText):
        window.SetForegroundColour(fg)
        window.SetBackgroundColour(bg)
    elif isinstance(window, wx.StaticBox):
        window.SetForegroundColour(fg)
        window.SetBackgroundColour(bg)
    elif isinstance(window, wx.CheckBox):
        window.SetForegroundColour(fg)
        window.SetBackgroundColour(bg)
    elif isinstance(window, wx.RadioButton):
        window.SetForegroundColour(fg)
        window.SetBackgroundColour(bg)
    elif isinstance(window, wx.SplitterWindow):
        window.SetBackgroundColour(border_bg)
    for child in window.GetChildren():
        _apply_colors(child)
