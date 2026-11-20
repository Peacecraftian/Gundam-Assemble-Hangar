using System.IO;

namespace Hangar.Launcher;

public sealed class TerminalLog
{
    public string DirectoryPath { get; }
    public string? WriteProblem { get; private set; }
    private readonly object gate = new();
    private readonly long maxBytes;

    public TerminalLog(string? directory = null, long maxBytes = 1024 * 1024)
    {
        DirectoryPath = directory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Gundam Assemble Hangar", "Launcher", "Logs");
        this.maxBytes = maxBytes;
    }

    public void Write(string message)
    {
        lock (gate)
        {
            try
            {
                Directory.CreateDirectory(DirectoryPath);
                var path = Path.Combine(DirectoryPath, "launcher.log");
                if (File.Exists(path) && new FileInfo(path).Length >= maxBytes)
                {
                    if (File.Exists(path + ".1")) File.Move(path + ".1", path + ".2", true);
                    File.Move(path, path + ".1", true);
                }
                File.AppendAllText(path, $"{DateTimeOffset.Now:O} {message.ReplaceLineEndings(" ")}\n");
                WriteProblem = null;
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
            { WriteProblem = "Logs could not be written. Check the log folder's permissions or free space."; }
        }
    }
}
