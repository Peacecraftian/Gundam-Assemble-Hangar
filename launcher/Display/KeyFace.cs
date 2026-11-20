using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Hangar.Launcher;

// Keep the chamfers the same size as the control stretches across the screen.
public sealed class KeyFace : Border
{
    public static readonly DependencyProperty DepressedProperty = DependencyProperty.Register(
        nameof(Depressed), typeof(bool), typeof(KeyFace),
        new PropertyMetadata(false, (owner, e) => ((KeyFace)owner).SetPressure((bool)e.NewValue)));
    public bool Depressed
    {
        get => (bool)GetValue(DepressedProperty);
        set => SetValue(DepressedProperty, value);
    }

    private readonly TranslateTransform travel = new();
    public KeyFace() => RenderTransform = travel;

    internal void SetPressure(bool down)
    {
        bool motion = SystemParameters.ClientAreaAnimation;
        double fromOpacity = Opacity, fromY = travel.Y;
        BeginAnimation(OpacityProperty, null);
        travel.BeginAnimation(TranslateTransform.YProperty, null);
        Opacity = down ? 0.78 : 1;
        travel.Y = down && motion ? 1.5 : 0;
        if (down)
        {
            if (Window.GetWindow(this) is MainWindow window)
            {
                window.Cues?.Press();
                if (motion) window.EmitKeyPuff(this);
            }
        }
        else if (motion)
        {
            var recovery = TimeSpan.FromMilliseconds(150);
            BeginAnimation(OpacityProperty, new DoubleAnimation(fromOpacity, 1, recovery) { FillBehavior = FillBehavior.Stop });
            travel.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(fromY, 0, recovery) { FillBehavior = FillBehavior.Stop });
        }
    }

    protected override void OnRender(DrawingContext dc)
    {
        double stroke = BorderThickness.Left, inset = stroke / 2;
        double right = ActualWidth - inset, bottom = ActualHeight - inset;
        double cut = Math.Min(10, Math.Min(right, bottom) / 4);
        var outline = new StreamGeometry();
        using (var shape = outline.Open())
        {
            shape.BeginFigure(new Point(inset + cut, inset), true, true);
            shape.PolyLineTo(new[] { new Point(right - cut, inset), new Point(right, inset + cut),
                new Point(right, bottom - cut), new Point(right - cut, bottom), new Point(inset + cut, bottom),
                new Point(inset, bottom - cut), new Point(inset, inset + cut) }, true, false);
        }
        outline.Freeze();
        dc.DrawGeometry(Background, new Pen(BorderBrush, stroke), outline);
    }
}
