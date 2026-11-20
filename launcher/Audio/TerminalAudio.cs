using System.IO;
using System.Windows.Media;

namespace Hangar.Launcher;

internal sealed class TerminalAudio : IDisposable
{
    private readonly MediaPlayer keyPress = Open("key-press.wav");
    private readonly MediaPlayer pilotLock = Open("pilot-lock.wav");

    private static MediaPlayer Open(string name)
    {
        var player = new MediaPlayer { Volume = 1 };
        player.MediaFailed += (_, e) => App.Log.Write($"Terminal cue {name} unavailable: {e.ErrorException.Message}");
        player.Open(new Uri(Path.Combine(AppContext.BaseDirectory, "Audio", name)));
        return player;
    }

    public void Press()
    {
        keyPress.Position = TimeSpan.Zero;
        keyPress.Play();
    }

    public void Lock() => pilotLock.Play();

    public void Dispose()
    {
        keyPress.Close();
        pilotLock.Close();
    }
}
