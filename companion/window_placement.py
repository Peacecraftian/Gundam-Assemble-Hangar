import ctypes
import sys
from ctypes import wintypes


MONITOR_DEFAULTTONEAREST = 2
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("monitor", wintypes.RECT),
        ("work_area", wintypes.RECT),
        ("flags", wintypes.DWORD),
    ]


class WindowPlacement(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("show_command", wintypes.UINT),
        ("min_position", wintypes.POINT),
        ("max_position", wintypes.POINT),
        ("normal_position", wintypes.RECT),
    ]


def monitor_bounds(window):
    if sys.platform != "win32":
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    monitor_from_window = user32.MonitorFromWindow
    monitor_from_window.argtypes = wintypes.HWND, wintypes.DWORD
    monitor_from_window.restype = wintypes.HMONITOR
    get_monitor_info = user32.GetMonitorInfoW
    get_monitor_info.argtypes = wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)
    get_monitor_info.restype = wintypes.BOOL
    monitor = monitor_from_window(int(window.wm_frame(), 0), MONITOR_DEFAULTTONEAREST)
    info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
    if monitor and get_monitor_info(monitor, ctypes.byref(info)):
        rect = info.monitor
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def enter_fullscreen(window, bounds):
    if bounds is not None and window.state() == "zoomed":
        # Tk recreates the frame and loses the normal rectangle of a maximized window.
        placement = WindowPlacement(length=ctypes.sizeof(WindowPlacement))
        get_placement = ctypes.WinDLL("user32", use_last_error=True).GetWindowPlacement
        get_placement.argtypes = wintypes.HWND, ctypes.POINTER(WindowPlacement)
        get_placement.restype = wintypes.BOOL
        if not get_placement(int(window.wm_frame(), 0), ctypes.byref(placement)):
            raise ctypes.WinError(ctypes.get_last_error())
        window._fullscreen_placement = placement
    window.attributes("-fullscreen", True)
    if bounds is None:
        return
    # Tk can recreate its wrapper on the primary display when entering fullscreen.
    # Moving the new wrapper keeps Tk's saved windowed geometry intact.
    position = ctypes.WinDLL("user32", use_last_error=True).SetWindowPos
    position.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, ctypes.c_int, wintypes.UINT)
    position.restype = wintypes.BOOL
    left, top, right, bottom = bounds
    flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER

    def place(frame):
        if not position(frame, None, left, top, right - left, bottom - top, flags):
            raise ctypes.WinError(ctypes.get_last_error())

    frame = int(window.wm_frame(), 0)
    place(frame)
    if window.transient():
        # Tk can recreate an owned frame again when its owner's map event arrives.
        def place_recreated_frame():
            if window.winfo_exists() and window.attributes("-fullscreen"):
                current_frame = int(window.wm_frame(), 0)
                if current_frame != frame:
                    place(current_frame)

        window.master.after_idle(place_recreated_frame)


def exit_fullscreen(window):
    window.attributes("-fullscreen", False)
    placement = getattr(window, "_fullscreen_placement", None)
    if placement is not None:
        del window._fullscreen_placement
        set_placement = ctypes.WinDLL("user32", use_last_error=True).SetWindowPlacement
        set_placement.argtypes = wintypes.HWND, ctypes.POINTER(WindowPlacement)
        set_placement.restype = wintypes.BOOL
        if not set_placement(int(window.wm_frame(), 0), ctypes.byref(placement)):
            raise ctypes.WinError(ctypes.get_last_error())
