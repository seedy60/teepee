import ctypes
import sys

import wx


_DARK_BG = wx.Colour(30, 30, 30)
_DARK_BG_ALT = wx.Colour(45, 45, 45)
_DARK_FG = wx.Colour(212, 212, 212)
_DARK_BORDER = wx.Colour(60, 60, 60)

_dark_mode = None
_high_contrast = None
_theme_override = None  # None = auto-detect, True/False = forced


def is_legacy_windows():
    """True on Windows 8.1 and earlier, where there's no system dark-mode
    setting for ``wx.SystemSettings.GetAppearance()`` to report on."""
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().major < 10
    except Exception:
        return False


def set_theme_override(force_dark):
    """Manually force dark mode on (``True``) or off (``False``).

    Pass ``None`` to clear the override and fall back to auto-detection.
    Used on legacy Windows where there's no system-level dark setting to
    follow, so the user opts in or out via Teepee's settings instead.
    """
    global _theme_override, _dark_mode
    _theme_override = None if force_dark is None else bool(force_dark)
    _dark_mode = None  # invalidate cache so the new value takes effect


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
    if _theme_override is not None:
        return _theme_override
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
        _ensure_titlebar_on_show(window)
    _apply_colors(window)


def _ensure_titlebar_on_show(window):
    if getattr(window, "_teepee_show_bound", False):
        return
    window._teepee_show_bound = True

    def _on_show(event):
        event.Skip()
        if event.IsShown():
            apply_dark_title_bar(window)

    window.Bind(wx.EVT_SHOW, _on_show)


_SET_WINDOW_THEME = None


def _set_window_theme(hwnd, theme_name):
    global _SET_WINDOW_THEME
    if _SET_WINDOW_THEME is None:
        fn = ctypes.windll.uxtheme.SetWindowTheme
        fn.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
        ]
        fn.restype = ctypes.c_long
        _SET_WINDOW_THEME = fn
    _SET_WINDOW_THEME(hwnd, theme_name, None)


def _disable_visual_styles(window):
    """Force a control to use Windows 11's built-in dark theme for native
    Win32 controls so that the wx colour properties are actually visible.

    Falls back to disabling visual styles entirely on older Windows that
    don't ship the "DarkMode_*" private themes."""
    if sys.platform != "win32":
        return
    try:
        hwnd = window.GetHandle()
    except Exception:
        return
    if isinstance(window, wx.Button):
        theme = "DarkMode_Explorer"
    elif isinstance(window, (wx.Choice, wx.ComboBox)):
        theme = "DarkMode_CFD"
    elif isinstance(window, wx.SpinCtrl):
        theme = "DarkMode_Explorer"
    elif isinstance(window, (wx.CheckBox, wx.RadioButton, wx.StaticBox)):
        theme = "DarkMode_Explorer"
    else:
        theme = "DarkMode_Explorer"
    try:
        _set_window_theme(hwnd, theme)
    except Exception:
        try:
            _set_window_theme(hwnd, "")
        except Exception:
            pass


def _apply_colors(window):
    if isinstance(window, (wx.TextCtrl, wx.ListBox, wx.Choice, wx.SpinCtrl)):
        window.SetBackgroundColour(_DARK_BG_ALT)
        window.SetForegroundColour(_DARK_FG)
        if isinstance(window, (wx.Choice, wx.SpinCtrl)):
            _disable_visual_styles(window)
    elif isinstance(window, wx.StatusBar):
        window.SetBackgroundColour(_DARK_BG)
        window.SetForegroundColour(_DARK_FG)
    elif isinstance(window, wx.Button):
        window.SetBackgroundColour(_DARK_BORDER)
        window.SetForegroundColour(_DARK_FG)
        _disable_visual_styles(window)
    elif isinstance(window, (wx.Panel, wx.Dialog, wx.Frame)):
        window.SetBackgroundColour(_DARK_BG)
        window.SetForegroundColour(_DARK_FG)
    elif isinstance(window, wx.StaticText):
        window.SetForegroundColour(_DARK_FG)
        window.SetBackgroundColour(_DARK_BG)
    elif isinstance(window, wx.StaticBox):
        window.SetForegroundColour(_DARK_FG)
        window.SetBackgroundColour(_DARK_BG)
        _disable_visual_styles(window)
    elif isinstance(window, wx.CheckBox):
        window.SetForegroundColour(_DARK_FG)
        window.SetBackgroundColour(_DARK_BG)
        _disable_visual_styles(window)
    elif isinstance(window, wx.RadioButton):
        window.SetForegroundColour(_DARK_FG)
        window.SetBackgroundColour(_DARK_BG)
        _disable_visual_styles(window)
    elif isinstance(window, wx.SplitterWindow):
        window.SetBackgroundColour(_DARK_BORDER)
    for child in window.GetChildren():
        _apply_colors(child)
