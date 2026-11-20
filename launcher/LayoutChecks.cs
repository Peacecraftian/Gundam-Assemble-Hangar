using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Hangar.Launcher;

// Exercises real WPF layout at the logical viewports corresponding to each DPI.
// This does not change Windows settings or claim to simulate physical touch input.
internal static class LayoutChecks
{
    public static int Run(string configPath, string output)
    {
        Directory.CreateDirectory(output);
        var report = new List<string>();
        var failures = new List<string>();
        var window = new MainWindow(configPath, true);
        var content = window.Shell;
        window.Content = null;
        var host = new Border { Background = window.Background, Child = content };
        var scenarios = new[] { (1920, 1080, 1d), (1920, 1080, 1.25), (1920, 1080, 1.5), (1920, 1080, 2d), (1280, 720, 1d) };
        foreach (var (pixelsWide, pixelsHigh, scale) in scenarios)
        {
            var width = pixelsWide / scale;
            var height = pixelsHigh / scale;
            foreach (var page in new[] { "home", "reference", "tools", "maintenance" })
            {
                if (page == "home") window.HomePanel.Visibility = Visibility.Visible;
                else window.ShowPage(page);
                window.DetailPanel.Visibility = page == "home" ? Visibility.Collapsed : Visibility.Visible;
                window.MainScroll.Visibility = window.DetailPanel.Visibility;
                host.Width = width; host.Height = height;
                window.AdaptLayout(width - 40);
                host.Measure(new Size(width, height));
                host.Arrange(new Rect(0, 0, width, height));
                host.UpdateLayout();
                var name = $"{pixelsWide}x{pixelsHigh}-{scale * 100:0}-{page}";
                foreach (var button in Descendants<Button>(host).Where(b => IsLayoutVisible(b, host) && b.IsEnabled))
                    CheckButton(button, name, failures);
                foreach (var text in Descendants<TextBlock>(host).Where(t => IsLayoutVisible(t, host)))
                {
                    if (text.ActualWidth + 2 < text.DesiredSize.Width - text.Margin.Left - text.Margin.Right ||
                        text.ActualHeight + 2 < text.DesiredSize.Height - text.Margin.Top - text.Margin.Bottom)
                        failures.Add($"{name}: text clipped: {text.Text}");
                }
                if (window.MaintenanceButton.ActualHeight < 56 || window.MaintenanceButton.ActualWidth < 56)
                    failures.Add($"{name}: maintenance target too small");
                if (page == "maintenance")
                {
                    var exit = window.DetailItems.Children.OfType<Button>().First();
                    if (!exit.IsEnabled) failures.Add($"{name}: desktop exit disabled");
                }
                var bitmap = new RenderTargetBitmap(pixelsWide, pixelsHigh, 96 * scale, 96 * scale, PixelFormats.Pbgra32);
                bitmap.Render(host);
                var encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(bitmap));
                using (var file = File.Create(Path.Combine(output, name + ".png"))) encoder.Save(file);
                report.Add($"PASS layout rendered: {name}; content extent {window.MainScroll.ExtentHeight:F0} DIP; viewport {window.MainScroll.ViewportHeight:F0} DIP.");
            }
        }
        foreach (var key in new[] { "Heading", "Stencil" })
        {
            var face = new Typeface((FontFamily)Application.Current.FindResource(key), FontStyles.Normal,
                key == "Heading" ? FontWeights.Bold : FontWeights.Normal, FontStretches.Normal);
            if (!face.TryGetGlyphTypeface(out var glyph) || !glyph.FontUri.ToString().Contains("Assets/Fonts", StringComparison.OrdinalIgnoreCase))
                failures.Add($"Embedded font unavailable: {key}");
            else report.Add($"PASS embedded font: {key} ({glyph.FontUri})");
        }
        report.AddRange(failures.Select(f => "FAIL " + f));
        report.Add($"Result: {failures.Count} failure(s). Logical layout only; physical touch and real DPI changes require device testing.");
        File.WriteAllLines(Path.Combine(output, "layout-report.txt"), report);
        window.Close();
        return failures.Count == 0 ? 0 : 1;
    }

    private static void CheckButton(Button button, string name, List<string> failures)
    {
        if (button.ActualHeight < 56 || button.ActualWidth < 56) failures.Add($"{name}: undersized button {button.Name}");
    }

    private static bool IsLayoutVisible(DependencyObject item, DependencyObject root)
    {
        for (DependencyObject? current = item; current is not null && current != root; current = VisualTreeHelper.GetParent(current))
            if (current is UIElement element && element.Visibility != Visibility.Visible) return false;
        return true;
    }

    private static IEnumerable<T> Descendants<T>(DependencyObject parent) where T : DependencyObject
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is T value) yield return value;
            foreach (var descendant in Descendants<T>(child)) yield return descendant;
        }
    }
}
