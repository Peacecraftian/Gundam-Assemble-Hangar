using System.ComponentModel;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;

namespace Hangar.Launcher;

public partial class MainWindow
{
    internal TerminalAudio? Cues { get; private set; }

    private void SetUpDisplayMotion(TubeEffect tube)
    {
        var elapsed = new Stopwatch();
        var timer = new DispatcherTimer(DispatcherPriority.Background, Dispatcher)
        {
            Interval = TimeSpan.FromSeconds(1.0 / 24)
        };
        DrawDensityTrace(0);
        int syncPercent = 100;
        bool firstLoad = true;
        void SetPilotSync(int percent)
        {
            if (percent == syncPercent) return;
            syncPercent = percent;
            PilotPercent.Text = $"{percent}%";
            PilotUnlit.Data = percent == 100 ? null : UnlitDialArc(percent);
            if (percent == 100) Cues?.Lock();
        }

        timer.Tick += (_, _) =>
        {
            double t = elapsed.Elapsed.TotalSeconds;
            if (syncPercent < 100)
            {
                double ramp = Math.Min(1, t / 2.4);
                SetPilotSync((int)(100 * (1 - Math.Pow(1 - ramp, 1.45))));
            }
            // The band wraps outside the bezel. Small, overlapping gain changes
            // keep the tube from pulsing like a regular status indicator.
            double sweep = (t % 14) / 14 * 1.08 - 0.04;
            double gain = 1 + 0.007 * Math.Sin(t * 4.1) + 0.004 * Math.Sin(t * 11.3);
            tube.Refresh = new Point(sweep, gain);
            if (DensityTrace.IsVisible) DrawDensityTrace(t);
        };

        void UpdateMotion()
        {
            if (!SystemParameters.ClientAreaAnimation) SetPilotSync(100);
            if (IsLoaded && IsVisible && WindowState != WindowState.Minimized && SystemParameters.ClientAreaAnimation)
            {
                elapsed.Start();
                timer.Start();
                return;
            }
            timer.Stop();
            elapsed.Stop();
            tube.Refresh = new Point(-1, 1);
        }

        void OnAnimationPreferenceChanged(object? sender, PropertyChangedEventArgs e)
        {
            if (e.PropertyName == nameof(SystemParameters.ClientAreaAnimation)) UpdateMotion();
        }
        Loaded += (_, _) =>
        {
            if (firstLoad)
            {
                firstLoad = false;
                Cues = new TerminalAudio();
                if (SystemParameters.ClientAreaAnimation) SetPilotSync(0);
                else Cues.Lock();
            }
            SystemParameters.StaticPropertyChanged += OnAnimationPreferenceChanged;
            UpdateMotion();
        };
        StateChanged += (_, _) => UpdateMotion();
        IsVisibleChanged += (_, _) => UpdateMotion();
        Closed += (_, _) =>
        {
            timer.Stop();
            Cues?.Dispose();
            Cues = null;
            SystemParameters.StaticPropertyChanged -= OnAnimationPreferenceChanged;
        };
    }

    internal void EmitKeyPuff(KeyFace face)
    {
        // Draw over the console so the next row or a page change cannot clip the exhaust.
        var origin = face.TranslatePoint(new Point(0, face.ActualHeight), PressEffects);
        var image = (ImageSource)FindResource("KeyPuff");
        double width = Math.Clamp(face.ActualWidth * 0.17, 28, 72);
        foreach (int direction in new[] { -1, 1 })
        {
            var puff = new Image { Source = image, Width = width, Height = width * 0.35, Opacity = 0.56,
                                   RenderTransformOrigin = new Point(0.5, 0.2) };
            var spread = new ScaleTransform(0.45, 0.38);
            var drift = new TranslateTransform();
            var motion = new TransformGroup();
            motion.Children.Add(spread);
            motion.Children.Add(drift);
            puff.RenderTransform = motion;
            double vent = direction < 0 ? 0.17 : 0.83;
            Canvas.SetLeft(puff, origin.X + face.ActualWidth * vent - width / 2);
            Canvas.SetTop(puff, origin.Y - 4);
            PressEffects.Children.Add(puff);
            var duration = TimeSpan.FromMilliseconds(360);
            spread.BeginAnimation(ScaleTransform.ScaleXProperty, new DoubleAnimation(1.32, duration));
            spread.BeginAnimation(ScaleTransform.ScaleYProperty, new DoubleAnimation(1.05, duration));
            drift.BeginAnimation(TranslateTransform.XProperty, new DoubleAnimation(direction * 11, duration));
            drift.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(7, duration));
            var fade = new DoubleAnimation(0, duration) { AccelerationRatio = 0.5 };
            fade.Completed += (_, _) => PressEffects.Children.Remove(puff);
            puff.BeginAnimation(OpacityProperty, fade);
        }
    }

    private static StreamGeometry UnlitDialArc(int percent)
    {
        // Dial coordinates refer to the 350 x 560 instrument crop. Leave both
        // sides of the horizontal reticle visible as the segmented arc fills.
        const double radius = 93;
        static Point DialPoint(double degrees)
        {
            double radians = degrees * Math.PI / 180;
            return new Point(180.5 + radius * Math.Sin(radians), 196 - radius * Math.Cos(radians));
        }
        var mask = new StreamGeometry();
        using (var arc = mask.Open())
        {
            double leadingEdge = 170 * percent / 100.0;
            void Shade(double start, double end)
            {
                start = Math.Max(start, leadingEdge);
                if (start >= end) return;
                arc.BeginFigure(DialPoint(start), false, false);
                arc.ArcTo(DialPoint(end), new Size(radius, radius), 0, false, SweepDirection.Clockwise, true, false);
            }
            Shade(1.5, 89);
            Shade(91, 171);
        }
        mask.Freeze();
        return mask;
    }

    private void DrawDensityTrace(double seconds)
    {
        // Sample a continuous signal so old readings drift left as new ones enter.
        // The slow envelope varies the fine detail without jumping between frames.
        var geometry = new StreamGeometry();
        using (var trace = geometry.Open())
        {
            for (int x = 0; x <= 300; x += 2)
            {
                double sample = x + seconds * 11;
                double ripple = 2.1 + 1.3 * Math.Sin(sample * 0.031);
                double y = 29 + 7 * Math.Sin(sample * 0.151)
                              + 4 * Math.Sin(sample * 0.068 + 1.6)
                              + ripple * Math.Sin(sample * 0.42)
                              + 1.6 * Math.Sin(sample * 0.93 + 0.4);
                var point = new Point(x, y);
                if (x == 0) trace.BeginFigure(point, false, false);
                else trace.LineTo(point, true, false);
            }
        }
        geometry.Freeze();
        DensityTrace.Data = geometry;
    }
}
