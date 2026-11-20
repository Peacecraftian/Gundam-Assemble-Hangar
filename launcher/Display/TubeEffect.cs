using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Effects;

namespace Hangar.Launcher;

internal sealed class TubeEffect : ShaderEffect
{
    private static readonly PixelShader Tube = new()
    {
        UriSource = new Uri("pack://application:,,,/Display/Tube.ps")
    };

    public static readonly DependencyProperty InputProperty =
        RegisterPixelShaderSamplerProperty(nameof(Input), typeof(TubeEffect), 0, SamplingMode.Bilinear);
    public Brush Input
    {
        get => (Brush)GetValue(InputProperty);
        set => SetValue(InputProperty, value);
    }

    public static readonly DependencyProperty PixelSizeProperty = DependencyProperty.Register(
        nameof(PixelSize), typeof(Point), typeof(TubeEffect),
        new UIPropertyMetadata(new Point(1.0 / 1920, 1.0 / 1080), PixelShaderConstantCallback(0)));
    public Point PixelSize
    {
        get => (Point)GetValue(PixelSizeProperty);
        set => SetValue(PixelSizeProperty, value);
    }

    public static readonly DependencyProperty RefreshProperty = DependencyProperty.Register(
        nameof(Refresh), typeof(Point), typeof(TubeEffect),
        new UIPropertyMetadata(new Point(-1, 1), PixelShaderConstantCallback(1)));
    public Point Refresh
    {
        get => (Point)GetValue(RefreshProperty);
        set => SetValue(RefreshProperty, value);
    }

    public TubeEffect()
    {
        PixelShader = Tube;
        UpdateShaderValue(InputProperty);
        UpdateShaderValue(PixelSizeProperty);
        UpdateShaderValue(RefreshProperty);
    }
}
