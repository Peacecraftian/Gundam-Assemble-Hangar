using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Hangar.Launcher;

public sealed record PrimaryEntry
{
    public string Label { get; init; } = "Gundam Assemble Hangar";
    public string Path { get; init; } = "";
    public string WorkingDirectory { get; init; } = "";
    public string[] Arguments { get; init; } = [];
}

public sealed record SupportEntry
{
    public string Label { get; init; } = "";
    public string Description { get; init; } = "";
    public string Kind { get; init; } = "document";
    public string Path { get; init; } = "";
    public string WorkingDirectory { get; init; } = "";
    public string[] Arguments { get; init; } = [];
}

public sealed record LauncherConfig
{
    public int SchemaVersion { get; init; } = 1;
    public string TerminalName { get; init; } = "HANGAR TERMINAL";
    public bool Fullscreen { get; init; } = true;
    public bool ReturnToLauncher { get; init; } = true;
    public PrimaryEntry Primary { get; init; } = new();
    public SupportEntry[] References { get; init; } = [];
    public SupportEntry[] Tools { get; init; } = [];
}

public sealed class Configuration
{
    public string FilePath { get; }
    public string DirectoryPath => System.IO.Path.GetDirectoryName(FilePath)!;
    public LauncherConfig Value { get; }
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
    };
    private static readonly HashSet<string> SettingsPages = ["ms-settings:sound", "ms-settings:display", "ms-settings:network-wifi"];

    public Configuration(string filePath)
    {
        FilePath = System.IO.Path.GetFullPath(filePath);
        Value = JsonSerializer.Deserialize<LauncherConfig>(File.ReadAllText(FilePath), Options)
            ?? throw new InvalidDataException("Configuration must be a JSON object.");
        if (Value.SchemaVersion != 1) throw new InvalidDataException("Supported schemaVersion is 1.");
        if (string.IsNullOrWhiteSpace(Value.TerminalName) || Value.TerminalName.Length > 80)
            throw new InvalidDataException("terminalName must contain 1–80 characters.");
        if (Value.Primary is null || Value.References is null || Value.Tools is null)
            throw new InvalidDataException("primary, references and tools cannot be null.");
        if (Value.References.Length > 12 || Value.Tools.Length > 2)
            throw new InvalidDataException("Configure at most 12 references and 2 tools.");
        if (Value.Primary.Arguments is null || Value.Primary.Arguments.Any(a => a is null))
            throw new InvalidDataException("primary.arguments must be an array of strings.");
        foreach (var item in Value.References.Concat(Value.Tools))
        {
            if (item is null || string.IsNullOrWhiteSpace(item.Label) || item.Label.Length > 80 ||
                item.Arguments is null || item.Arguments.Any(a => a is null) || item.Description is null)
                throw new InvalidDataException("Each support item needs a label (1–80 characters), description and string arguments.");
            if (item.Kind is not ("document" or "executable" or "settings"))
                throw new InvalidDataException($"Unsupported kind for {item.Label}.");
        }
        if (Value.References.Any(x => x.Kind != "document"))
            throw new InvalidDataException("Reference items must use kind document.");
    }

    public string Resolve(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) throw new InvalidDataException("A path has not been configured.");
        var expanded = Environment.ExpandEnvironmentVariables(path);
        if (expanded.StartsWith("\\\\", StringComparison.Ordinal) || expanded.StartsWith("//", StringComparison.Ordinal) ||
            expanded.Contains("://", StringComparison.Ordinal))
            throw new InvalidDataException("Choose a local file, not a network location or URL.");
        var resolved = System.IO.Path.GetFullPath(expanded, DirectoryPath);
        // Reject device paths and alternate data streams; permit the drive-letter colon.
        if (resolved.StartsWith("\\\\", StringComparison.Ordinal) || resolved[2..].Contains(':'))
            throw new InvalidDataException("Choose an ordinary local file path.");
        return resolved;
    }

    public (string Path, string WorkingDirectory) ResolveExecutable(string path, string? workingDirectory)
    {
        var full = Resolve(path);
        if (!System.IO.Path.GetExtension(full).Equals(".exe", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Choose a directly launched .exe file.");
        if (!File.Exists(full)) throw new FileNotFoundException("Executable is missing. Check its configured path.", full);
        var directory = string.IsNullOrWhiteSpace(workingDirectory) ? System.IO.Path.GetDirectoryName(full)! : Resolve(workingDirectory);
        if (!Directory.Exists(directory)) throw new DirectoryNotFoundException("Working directory is missing. Check configuration.");
        return (full, directory);
    }

    public string? PrimaryProblem()
    {
        try { ResolveExecutable(Value.Primary.Path, Value.Primary.WorkingDirectory); return null; }
        catch (Exception e) when (IsConfigurationError(e)) { return e.Message; }
    }

    public string? SupportProblem(SupportEntry item)
    {
        try
        {
            if (item.Kind == "settings")
            {
                if (!SettingsPages.Contains(item.Path)) throw new InvalidDataException("Supported settings: sound, display, network-wifi.");
                if (item.Arguments.Length != 0) throw new InvalidDataException("Settings pages do not accept arguments.");
            }
            else if (item.Kind == "executable") ResolveExecutable(item.Path, item.WorkingDirectory);
            else
            {
                var path = Resolve(item.Path);
                if (!System.IO.Path.GetExtension(path).Equals(".pdf", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Reference must be a local PDF.");
                if (item.Arguments.Length != 0) throw new InvalidDataException("PDF references do not accept arguments.");
                if (!File.Exists(path)) throw new FileNotFoundException("PDF is missing. Check its configured path.");
            }
            return null;
        }
        catch (Exception e) when (IsConfigurationError(e)) { return e.Message; }
    }

    public static bool IsConfigurationError(Exception e) => e is IOException or InvalidDataException or UnauthorizedAccessException or
        JsonException or ArgumentException or NotSupportedException;
}
