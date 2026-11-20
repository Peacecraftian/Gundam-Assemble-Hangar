using System.Threading;
using System.Windows;

namespace Hangar.Launcher;

public partial class App : Application
{
    private Mutex? instance;
    private bool ownsInstance;
    public static TerminalLog Log { get; } = new();

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            Log.Write($"Unhandled UI error: {args.Exception}");
            MessageBox.Show("The terminal encountered an error and will close. Hangar will remain open if it is running. You can reopen the terminal from the desktop.", "Hangar Terminal", MessageBoxButton.OK, MessageBoxImage.Error);
            args.Handled = true;
            Shutdown(1);
        };
        try
        {
            string config = System.IO.Path.Combine(AppContext.BaseDirectory, "launcher.json");
            bool windowed = false;
            string? layoutOutput = null;
            for (var i = 0; i < e.Args.Length; i++)
            {
                switch (e.Args[i])
                {
                    case "--config" when i + 1 < e.Args.Length: config = System.IO.Path.GetFullPath(e.Args[++i]); break;
                    case "--windowed": windowed = true; break;
                    case "--layout-check" when i + 1 < e.Args.Length: layoutOutput = System.IO.Path.GetFullPath(e.Args[++i]); break;
                    default: throw new ArgumentException("Usage: Hangar.Launcher.exe [--config <JSON path>] [--windowed] [--layout-check <output folder>]");
                }
            }
            if (layoutOutput is not null)
            {
                ShutdownMode = ShutdownMode.OnExplicitShutdown;
                Shutdown(LayoutChecks.Run(config, layoutOutput));
                return;
            }
            instance = new Mutex(true, @"Local\GundamAssembleHangarTerminal", out ownsInstance);
            if (!ownsInstance)
            {
                MessageBox.Show("Hangar Terminal is already open. Switch to its window on the taskbar.", "Hangar Terminal");
                Shutdown();
                return;
            }
            Log.Write("Terminal starting.");
            MainWindow = new MainWindow(config, windowed);
            MainWindow.Show();
        }
        catch (Exception error)
        {
            Log.Write($"Startup failed: {error}");
            MessageBox.Show(error.Message, "Hangar Terminal could not start", MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(1);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        Log.Write("Terminal closed; child applications left running.");
        if (ownsInstance) instance?.ReleaseMutex();
        instance?.Dispose();
        base.OnExit(e);
    }
}
