using System.Diagnostics;
using System.IO;

namespace Hangar.Launcher;

public sealed record LaunchResult(int ExitCode, TimeSpan Duration);

public sealed class LaunchService
{
    private int busy;
    public bool IsRunning => Volatile.Read(ref busy) != 0;
    public Process? ActiveProcess { get; private set; }
    public event Action? Started;
    private readonly Action<string> log;

    public LaunchService(Action<string> log) => this.log = log;

    public async Task<LaunchResult> RunPrimaryAsync(Configuration configuration)
    {
        if (Interlocked.CompareExchange(ref busy, 1, 0) != 0)
            throw new InvalidOperationException("Hangar is already running from this terminal.");
        var watch = Stopwatch.StartNew();
        try
        {
            var entry = configuration.Value.Primary;
            var (path, workingDirectory) = configuration.ResolveExecutable(entry.Path, entry.WorkingDirectory);
            var start = ExecutableStart(path, workingDirectory, entry.Arguments);
            using var process = Process.Start(start) ?? throw new IOException("Windows did not create an application process.");
            ActiveProcess = process;
            log($"Primary started; PID {process.Id}.");
            Started?.Invoke();
            await process.WaitForExitAsync();
            var result = new LaunchResult(process.ExitCode, watch.Elapsed);
            log($"Primary exited; code {result.ExitCode}; duration {result.Duration.TotalSeconds:F1}s.");
            return result;
        }
        finally { ActiveProcess = null; Volatile.Write(ref busy, 0); }
    }

    public static ProcessStartInfo ExecutableStart(string path, string directory, IEnumerable<string> arguments)
    {
        var info = new ProcessStartInfo(path) { UseShellExecute = false, WorkingDirectory = directory };
        foreach (var argument in arguments) info.ArgumentList.Add(argument);
        return info;
    }

    public void OpenSupport(Configuration configuration, SupportEntry entry)
    {
        var problem = configuration.SupportProblem(entry);
        if (problem is not null) throw new InvalidDataException(problem);
        ProcessStartInfo start;
        if (entry.Kind == "executable")
        {
            var (path, directory) = configuration.ResolveExecutable(entry.Path, entry.WorkingDirectory);
            start = ExecutableStart(path, directory, entry.Arguments);
        }
        else start = new(entry.Kind == "settings" ? entry.Path : configuration.Resolve(entry.Path)) { UseShellExecute = true };
        using var process = Process.Start(start);
        log($"Support item opened ({entry.Kind}).");
    }
}
