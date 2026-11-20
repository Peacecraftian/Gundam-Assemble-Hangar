using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Hangar.Launcher;

internal static class NativeWindow
{
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern bool ShowWindowAsync(IntPtr window, int command);

    public static bool TryActivate(Process? process)
    {
        try
        {
            if (process is null || process.HasExited) return false;
            process.Refresh();
            if (process.MainWindowHandle == IntPtr.Zero) return false;
            ShowWindowAsync(process.MainWindowHandle, 9);
            return SetForegroundWindow(process.MainWindowHandle);
        }
        catch (Exception e) when (e is InvalidOperationException or System.ComponentModel.Win32Exception) { return false; }
    }
}
