using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace Hangar.Launcher;

public partial class MainWindow : Window
{
    private readonly string configPath;
    private readonly LaunchService launch = new(App.Log.Write);
    private Configuration? configuration;
    private bool fullscreen;
    private bool closed;
    private string currentPage = "home";
    private Cursor? hand;

    public MainWindow(string configPath, bool forceWindowed = false)
    {
        this.configPath = configPath;
        InitializeComponent();
        var tube = new TubeEffect();
        Shell.Effect = tube;
        SetUpDisplayMotion(tube);
        void UpdateTube()
        {
            var dpi = VisualTreeHelper.GetDpi(Shell);
            tube.PixelSize = new Point(1 / Math.Max(1, Shell.ActualWidth * dpi.DpiScaleX),
                                       1 / Math.Max(1, Shell.ActualHeight * dpi.DpiScaleY));
        }
        Shell.SizeChanged += (_, _) => { UpdateTube(); AdaptLayout(Shell.ActualWidth); };
        DpiChanged += (_, _) => UpdateTube();
        try
        {
            using var arrowData = Application.GetResourceStream(new Uri("pack://application:,,,/Assets/hangar-pointer.cur")).Stream;
            using var handData = Application.GetResourceStream(new Uri("pack://application:,,,/Assets/hangar-hand.cur")).Stream;
            Cursor = new Cursor(arrowData);
            hand = new Cursor(handData);
            foreach (var key in new[] { BackButton, LaunchButton, ReferenceButton, ToolsButton, MaintenanceButton })
                key.Cursor = hand;
        }
        catch (Exception e) when (e is IOException or ArgumentException) { App.Log.Write($"Cursor fallback: {e.Message}"); }
        launch.Started += () =>
        {
            LaunchTitle.Text = "▶  RETURN TO HANGAR";
            AutomationProperties.SetName(LaunchButton, "Return to Hangar");
            SetStatus("HANGAR RUNNING", false);
            WindowState = WindowState.Minimized;
        };
        Closed += (_, _) => { closed = true; Cursor?.Dispose(); hand?.Dispose(); };
        LoadConfiguration();
        SetFullscreen(configuration?.Value.Fullscreen != false && !forceWindowed);
        Loaded += (_, _) => LaunchButton.Focus();
    }

    private void LoadConfiguration()
    {
        try
        {
            configuration = new Configuration(configPath);
            var model = configuration.Value;
            TerminalLabel.Text = model.TerminalName;
            var problem = configuration.PrimaryProblem();
            var references = model.References.Count(item => configuration.SupportProblem(item) == null);
            var tools = model.Tools.Count(item => configuration.SupportProblem(item) == null);
            Diagnostics.Text = $"[01] TERMINAL CONFIGURATION ..... OK\n" +
                $"[02] HANGAR EXECUTABLE .......... {(problem == null ? "OK" : "CHECK")}\n" +
                $"[03] LOCAL REFERENCES ........... {references}/{model.References.Length}\n" +
                $"[04] SUPPORT TOOLS .............. {tools}/{model.Tools.Length}";
            LaunchButton.IsEnabled = problem is null;
            SetStatus(problem ?? "READY FOR SORTIE", problem is not null);
            App.Log.Write("Configuration loaded.");
            if (App.Log.WriteProblem is not null) SetStatus(App.Log.WriteProblem, true);
        }
        catch (Exception e) when (Configuration.IsConfigurationError(e))
        {
            configuration = null;
            LaunchButton.IsEnabled = false;
            Diagnostics.Text = "CONFIGURATION OFFLINE\nOPEN MAINTENANCE TO RELOAD";
            SetStatus($"CONFIGURATION ERROR · {e.Message}", true);
            App.Log.Write($"Configuration failed: {e.Message}");
        }
    }

    private async void LaunchPrimary(object sender, RoutedEventArgs e)
    {
        if (launch.IsRunning)
        {
            if (NativeWindow.TryActivate(launch.ActiveProcess)) WindowState = WindowState.Minimized;
            else SetStatus("Hangar is running. Select its window from the taskbar or use Alt+Tab.", true);
            return;
        }
        if (configuration is null) return;
        var launchConfiguration = configuration;
        SetStatus("STARTING HANGAR…", false);
        try
        {
            var result = await launch.RunPrimaryAsync(launchConfiguration);
            if (closed) return;
            if (launchConfiguration.Value.ReturnToLauncher) RestoreTerminal();
            if (result.ExitCode != 0)
                SetStatus($"HANGAR CLOSED UNEXPECTEDLY · EXIT {result.ExitCode} · TAP ENTER HANGAR TO RETRY", true);
            else if (result.Duration < TimeSpan.FromSeconds(2))
                SetStatus("HANGAR CLOSED BEFORE READY · CHECK CONFIGURATION OR LOGS, THEN RETRY", true);
            else SetStatus("SESSION CLOSED · READY FOR SORTIE", false);
        }
        catch (Exception error) when (error is not OutOfMemoryException)
        {
            if (closed) return;
            RestoreTerminal();
            SetStatus($"COULD NOT OPEN HANGAR · {error.Message}", true);
            App.Log.Write($"Primary failed: {error.Message}");
        }
        finally
        {
            if (!closed)
            {
                LaunchTitle.Text = "▶  ENTER HANGAR";
                AutomationProperties.SetName(LaunchButton, "Enter Hangar");
                if (currentPage == "maintenance") ShowPage("maintenance");
            }
        }
    }

    private void RestoreTerminal()
    {
        WindowState = fullscreen ? WindowState.Maximized : WindowState.Normal;
        Activate();
        LaunchButton.Focus();
    }

    private void SetStatus(string text, bool error)
    {
        StatusText.Text = text;
        StatusText.Foreground = (Brush)FindResource(error ? "Danger" : "Ready");
        AutomationProperties.SetLiveSetting(StatusText, AutomationLiveSetting.Polite);
    }

    private void ShowHome(object sender, RoutedEventArgs e)
    {
        currentPage = "home";
        MainScroll.Visibility = DetailPanel.Visibility = Visibility.Collapsed;
        HomePanel.Visibility = Visibility.Visible;
        LaunchButton.Focus();
    }

    internal void ShowPage(string page)
    {
        currentPage = page;
        HomePanel.Visibility = Visibility.Collapsed;
        MainScroll.Visibility = DetailPanel.Visibility = Visibility.Visible;
        DetailItems.Children.Clear();
        MainScroll.ScrollToTop();
        BackButton.Focus();
        if (page == "maintenance") { BuildMaintenance(); return; }
        var reference = page == "reference";
        DetailTitle.Text = reference ? "REFERENCE LIBRARY" : "TERMINAL TOOLS";
        DetailDescription.Text = reference ? "Open a local PDF in your Windows reader." : "Select a utility to open it in Windows.";
        var entries = reference ? configuration?.Value.References : configuration?.Value.Tools;
        if (entries is null || entries.Length == 0)
        {
            DetailItems.Children.Add(new TextBlock { Text = "No items configured. Open Maintenance to configure this terminal." });
            return;
        }
        foreach (var entry in entries)
        {
            var problem = configuration!.SupportProblem(entry);
            AddAction(entry.Label, problem ?? entry.Description, () =>
            {
                try
                {
                    launch.OpenSupport(configuration!, entry);
                    SetStatus($"OPENED · {entry.Label}", false);
                }
                catch (Exception error) when (error is not OutOfMemoryException)
                { SetStatus($"COULD NOT OPEN {entry.Label} · {error.Message}", true); App.Log.Write($"Support failed: {error.Message}"); }
            }, problem is null);
        }
    }

    private void ShowReferences(object sender, RoutedEventArgs e) => ShowPage("reference");
    private void ShowTools(object sender, RoutedEventArgs e) => ShowPage("tools");
    private void ShowMaintenance(object sender, RoutedEventArgs e) => ShowPage("maintenance");

    private void BuildMaintenance()
    {
        DetailTitle.Text = "MAINTENANCE";
        DetailDescription.Text = "Reload changes after editing the configuration file.";
        AddAction("RETURN TO DESKTOP", "Close the terminal. Any running Hangar session stays open.", Close);
        AddAction("RELOAD CONFIGURATION", "Refresh application paths, references and tools.", () =>
        { LoadConfiguration(); ShowPage("maintenance"); }, !launch.IsRunning);
        AddAction("CONFIGURATION FOLDER", configPath, () => OpenFolder(Path.GetDirectoryName(configPath)!));
        AddAction("LOG FOLDER", App.Log.DirectoryPath, () =>
        {
            try { Directory.CreateDirectory(App.Log.DirectoryPath); OpenFolder(App.Log.DirectoryPath); }
            catch (Exception e) when (Configuration.IsConfigurationError(e)) { SetStatus(e.Message, true); }
        });
        AddAction(fullscreen ? "SWITCH TO WINDOW MODE" : "SWITCH TO FULLSCREEN", "F11 toggles window mode. Alt+F4 exits.", () => { SetFullscreen(!fullscreen); ShowPage("maintenance"); });
        if (launch.IsRunning) DetailItems.Children.Add(new TextBlock { Text = "Hangar is running. Configuration reload is available after it closes." });
    }

    private void AddAction(string label, string description, Action action, bool enabled = true)
    {
        var text = new StackPanel();
        text.Children.Add(new TextBlock { Text = label, FontFamily = (FontFamily)FindResource("Heading"), FontWeight = FontWeights.Bold, FontSize = 23 });
        text.Children.Add(new TextBlock { Text = description, FontFamily = new FontFamily("Segoe UI"), FontWeight = FontWeights.Normal, FontSize = 16, Foreground = (Brush)FindResource("Muted"), Margin = new Thickness(0, 8, 0, 0) });
        var button = new Button { Content = text, Style = (Style)FindResource("SupportButton"), Margin = new Thickness(0, 0, 0, 14), IsEnabled = enabled, MinHeight = 96, Cursor = hand };
        AutomationProperties.SetName(button, label);
        AutomationProperties.SetHelpText(button, description);
        button.Click += (_, _) => action();
        DetailItems.Children.Add(button);
        if (!enabled) DetailItems.Children.Add(new TextBlock { Text = $"Unavailable: {label}. {description}", FontSize = 16, Foreground = (Brush)FindResource("Danger"), Margin = new Thickness(4, -4, 4, 18) });
    }

    private void OpenFolder(string directory)
    {
        try { using var process = Process.Start(new ProcessStartInfo(directory) { UseShellExecute = true }); }
        catch (Exception error) when (error is not OutOfMemoryException) { SetStatus($"COULD NOT OPEN FOLDER · {error.Message}", true); }
    }

    private void SetFullscreen(bool value)
    {
        fullscreen = value;
        WindowState = WindowState.Normal;
        WindowStyle = value ? WindowStyle.None : WindowStyle.SingleBorderWindow;
        ResizeMode = value ? ResizeMode.NoResize : ResizeMode.CanResize;
        WindowState = value ? WindowState.Maximized : WindowState.Normal;
    }

    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        // Enter activates native WPF buttons immediately without a held state.
        if (e.Key == Key.Enter && !e.IsRepeat && Keyboard.FocusedElement is Button key &&
            key.Template.FindName("Face", key) is KeyFace face)
        {
            face.SetPressure(true);
            face.SetPressure(false);
        }
        if (e.Key == Key.Escape)
        {
            if (currentPage == "maintenance") ShowHome(this, new RoutedEventArgs());
            else ShowPage("maintenance");
            e.Handled = true;
        }
        else if (e.Key == Key.F11) { SetFullscreen(!fullscreen); e.Handled = true; }
    }

    internal void AdaptLayout(double width)
    {
        var compact = width < 860;
        ArtPanel.Visibility = compact ? Visibility.Collapsed : Visibility.Visible;
        ArtColumn.Width = new GridLength(compact ? 0 : 54, GridUnitType.Star);
        TerminalLabel.FontSize = compact ? 17 : 24;
    }
}
