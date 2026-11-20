using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Hangar.Launcher;

if (args.FirstOrDefault() == "--fixture")
{
    await Task.Delay(int.Parse(args[1]));
    if (args[3] != "-") File.WriteAllText(args[3], JsonSerializer.Serialize(new { arguments = args[4..], directory = Environment.CurrentDirectory }));
    return int.Parse(args[2]);
}

if (args.Length != 1) throw new ArgumentException("Pass an output folder under .build.");
var root = Path.GetFullPath(args[0]);
Directory.CreateDirectory(root);
var passed = new List<string>();
var failed = new List<string>();
var fixtureHost = Environment.ProcessPath!;
var fixtureAssembly = Assembly.GetExecutingAssembly().Location;

string WriteConfig(string name, LauncherConfig value)
{
    var path = Path.Combine(root, name + ".json");
    File.WriteAllText(path, JsonSerializer.Serialize(value));
    return path;
}

LauncherConfig Fixture(int exit = 0, int delay = 200, string output = "-", string[]? extra = null) => new()
{
    Primary = new() { Path = fixtureHost, WorkingDirectory = root, Arguments = new[] { fixtureAssembly, "--fixture", delay.ToString(), exit.ToString(), output }.Concat(extra ?? []).ToArray() }
};

void Check(bool value, string message) { if (!value) throw new Exception(message); }
void Reject(Action action)
{
    try { action(); }
    catch (Exception e) when (Configuration.IsConfigurationError(e)) { return; }
    throw new Exception("Invalid configuration unexpectedly accepted.");
}
async Task Test(string name, Func<Task> test)
{
    try { await test(); passed.Add(name); Console.WriteLine("PASS " + name); }
    catch (Exception e) { failed.Add(name + ": " + e.Message); Console.WriteLine("FAIL " + name + ": " + e.Message); }
}
Task Sync(Action action) { action(); return Task.CompletedTask; }

await Test("Relative paths resolve from config, independent of process working directory", () => Sync(() =>
{
    var config = new Configuration(WriteConfig("relative", new() { Primary = new() { Path = "nested/app.exe" } }));
    Check(config.Resolve(config.Value.Primary.Path) == Path.Combine(root, "nested", "app.exe"), "Wrong base directory.");
    Check(config.PrimaryProblem() is not null, "Missing executable should be unavailable.");
}));
await Test("Missing PDF remains an unavailable support item", () => Sync(() =>
{
    var config = new Configuration(WriteConfig("pdf", new()));
    Check(config.SupportProblem(new() { Label = "Rules", Path = "missing.pdf" }) is not null, "Missing PDF accepted.");
    var pdf = Path.Combine(root, "test.pdf"); File.WriteAllText(pdf, "%PDF-1.4\n%%EOF");
    Check(config.SupportProblem(new() { Label = "Rules", Path = pdf }) is null, "Existing PDF unavailable.");
}));
await Test("Malformed, null, unsupported-schema, unknown-key and oversized configs fail safely", () => Sync(() =>
{
    foreach (var raw in new[] { "{", "null", "{\"schemaVersion\":2}", "{\"typo\":true}", "{\"primary\":null}", "{\"references\":[null]}", "{\"primary\":{\"arguments\":null}}", "{\"terminalName\":null}" })
    {
        var file = Path.Combine(root, "invalid.json"); File.WriteAllText(file, raw);
        Reject(() => _ = new Configuration(file));
    }
    Reject(() => _ = new Configuration(WriteConfig("too-many", new() { Tools = Enumerable.Repeat(new SupportEntry { Label = "Tool" }, 3).ToArray() })));
}));
await Test("Shell scripts, remote paths, non-PDF references and unsupported settings are refused", () => Sync(() =>
{
    var config = new Configuration(WriteConfig("restrictions", new()));
    foreach (var path in new[] { "https://example.com/rules.pdf", "\\\\server\\share\\rules.pdf", "//server/share/rules.pdf" }) Reject(() => config.Resolve(path));
    Reject(() => config.ResolveExecutable("run.cmd", ""));
    Check(config.SupportProblem(new() { Label = "Other", Path = "other.txt" }) is not null, "Non PDF accepted.");
    Check(config.SupportProblem(new() { Label = "Settings", Kind = "settings", Path = "ms-settings:privacy" }) is not null, "Unsupported settings accepted.");
    Check(config.SupportProblem(new() { Label = "Sound", Kind = "settings", Path = "ms-settings:sound" }) is null, "Sound unavailable.");
}));
await Test("Missing working directory detected before creating a process", () => Sync(() =>
{
    var value = Fixture() with { Primary = Fixture().Primary with { WorkingDirectory = "does-not-exist" } };
    Check(new Configuration(WriteConfig("bad-directory", value)).PrimaryProblem() is not null, "Missing directory accepted.");
}));
await Test("Primary process preserves spaced and quoted arguments, working directory and normal exit", async () =>
{
    var output = Path.Combine(root, "arguments with spaces.json");
    var expected = new[] { "value with spaces", "quote\"inside", "trailing\\", "--fullscreen", "--save-path", "isolated.sqlite3" };
    var service = new LaunchService(_ => { });
    var result = await service.RunPrimaryAsync(new Configuration(WriteConfig("normal", Fixture(output: output, extra: expected))));
    var doc = JsonDocument.Parse(File.ReadAllText(output));
    Check(doc.RootElement.GetProperty("arguments").EnumerateArray().Select(x => x.GetString()).SequenceEqual(expected), "Arguments changed.");
    Check(doc.RootElement.GetProperty("directory").GetString() == root, "Wrong working directory.");
    Check(result.ExitCode == 0 && !service.IsRunning && service.ActiveProcess is null, "Incorrect lifecycle cleanup.");
});
await Test("Double launch rejected while primary is alive; retry works after exit", async () =>
{
    var config = new Configuration(WriteConfig("duplicate", Fixture(delay: 400)));
    var service = new LaunchService(_ => { });
    var first = service.RunPrimaryAsync(config);
    Check(service.IsRunning && service.ActiveProcess is not null, "Process not registered before yielding.");
    try { await service.RunPrimaryAsync(config); throw new Exception("Duplicate launch succeeded."); }
    catch (InvalidOperationException) { }
    await first;
    Check((await service.RunPrimaryAsync(config)).ExitCode == 0, "Retry failed.");
});
await Test("Nonzero exit captured and gate cleared after failed launch", async () =>
{
    var service = new LaunchService(_ => { });
    var result = await service.RunPrimaryAsync(new Configuration(WriteConfig("crash", Fixture(exit: 17))));
    Check(result.ExitCode == 17 && !service.IsRunning, "Crash not captured.");
    try { await service.RunPrimaryAsync(new Configuration(WriteConfig("absent", new()))); throw new Exception("Missing launch succeeded."); }
    catch (Exception e) when (Configuration.IsConfigurationError(e)) { }
    Check(!service.IsRunning, "Launch gate stuck after error.");
    Check((await service.RunPrimaryAsync(new Configuration(WriteConfig("recovery", Fixture())))).ExitCode == 0, "Recovery failed.");
});
await Test("Corrupt executable start failure releases gate", async () =>
{
    File.WriteAllText(Path.Combine(root, "corrupt.exe"), "not an executable");
    var service = new LaunchService(_ => { });
    try { await service.RunPrimaryAsync(new Configuration(WriteConfig("corrupt", new() { Primary = new() { Path = "corrupt.exe" } }))); throw new Exception("Corrupt EXE succeeded."); }
    catch (System.ComponentModel.Win32Exception) { }
    Check(!service.IsRunning && service.ActiveProcess is null, "Gate stuck after process failure.");
});
await Test("Return policy and missing-file recovery survive reload", () => Sync(() =>
{
    var later = "later-" + Guid.NewGuid().ToString("N") + ".exe";
    var path = WriteConfig("reload", new() { ReturnToLauncher = false, Primary = new() { Path = later } });
    var before = new Configuration(path);
    Check(!before.Value.ReturnToLauncher && before.PrimaryProblem() is not null, "Return policy lost.");
    File.Copy(fixtureHost, Path.Combine(root, later));
    Check(new Configuration(path).PrimaryProblem() is null, "Reload did not discover file.");
}));
await Test("Log rotates, survives unwritable destination and strips line breaks", () => Sync(() =>
{
    var directory = Path.Combine(root, "logs");
    var log = new TerminalLog(directory, 10);
    for (var i = 0; i < 4; i++) log.Write("test\r\ninjection");
    Check(File.Exists(Path.Combine(directory, "launcher.log.2")), "Backups missing.");
    Check(File.ReadAllLines(Path.Combine(directory, "launcher.log")).Length == 1, "Multiline log injection.");
    var blocked = Path.Combine(root, "blocked-log-directory"); File.WriteAllText(blocked, "file");
    var brokenLog = new TerminalLog(blocked); brokenLog.Write("survive");
    Check(brokenLog.WriteProblem is not null, "Failure not reported.");
}));

var lines = passed.Select(x => "PASS " + x).Concat(failed.Select(x => "FAIL " + x)).Append($"{passed.Count} passed; {failed.Count} failed.");
File.WriteAllLines(Path.Combine(root, "test-report.txt"), lines);
Console.WriteLine($"{passed.Count} passed; {failed.Count} failed.");
return failed.Count == 0 ? 0 : 1;
