# Hangar Terminal

Touch-first Windows 11 launcher for Gundam Assemble Hangar. The mint CRT screen uses the supplied terminal illustration, live Hangar controls, the project fonts and its orange cursors. No installer, administrator access, web service or separate .NET runtime is needed for the self-contained Windows x64 build.

## Build and run from the checkout

Install the **.NET 10 SDK for Windows x64** from [Microsoft](https://dotnet.microsoft.com/download/dotnet/10.0). The shader build uses the Python environment in `.venv` and the Windows D3D compiler. A locally installed SDK at `.build/dotnet/dotnet.exe` is preferred automatically. Run these commands from the active repository root:

```powershell
./launcher/build.ps1
& './dist/Hangar Terminal/Hangar.Launcher.exe' --config "$PWD/launcher/launcher.development.json"
```

`build.ps1` builds and runs dependency-free C# integration tests, then publishes a self-contained folder to `dist/Hangar Terminal`. All intermediate outputs, packages and test fixtures stay under `.build`. There is no change to the root game build. `-DotNet <path>` selects an SDK; `-SkipTests` is available for repeat packaging after verification. The first self-contained publish needs access to Microsoft's runtime packages through NuGet. No third-party NuGet packages are used.

The development configuration uses `dist/Gundam Assemble Hangar/Gundam Assemble Hangar.exe`. Build the **game** with the root `build.ps1` using the checkout's Python 3.13 x64 environment, or point `primary.path` to a current portable Hangar app. Both supplied configurations pass `--fullscreen`, so ENTER HANGAR opens the application directly in fullscreen. Rebuild older game executables to support that flag; rebuilding the launcher alone does not rebuild the game. Development also passes `--save-path ../../.build/launcher-smoke.sqlite3` relative to the game directory, so it does not open the regular saved match.

Use `--windowed` to preview in a regular window. Normal launch is borderless fullscreen. F11 toggles window mode. Escape opens maintenance; Escape again returns home. Alt+F4 closes the terminal. The Windows taskbar entry, Alt+Tab and Windows security screen remain available. A visible **MAINTENANCE → RETURN TO DESKTOP** button provides a keyboard-free exit. The terminal is never topmost and does not trap keys. Closing it leaves Hangar and support applications running.

## Portable device layout

Copy the entire output folder and the separate game folder to a permanent location, preserving this layout:

```text
Gundam Terminal/
  Hangar Terminal/
    Hangar.Launcher.exe
    launcher.json
    References/                 # the three explicitly selected Rules PDFs
    Licenses/                   # font, icon and original asset notices
    ...                         # self-contained .NET files; keep these together
  Gundam Assemble Hangar/
    Gundam Assemble Hangar.exe
    _internal/
```

Launch `Hangar.Launcher.exe` without arguments to use its adjacent `launcher.json`. Its primary path already matches this layout; the local development build under `dist` matches it as well. Production passes `--fullscreen` and uses the game's normal per-user save location. The PDFs are included only if present in the checkout; missing references remain visible and unavailable. Official rules and artwork retain their owners' rights; see `Licenses/NOTICE.md` before redistributing.

The launcher has no app-update mechanism. Exit it before replacing its files. Keep saved matches and a backup separately; the launcher does not migrate them.

## Configuration

Edit JSON in a text editor, save it, then choose **Maintenance → Reload configuration**. Primary launch is blocked on malformed JSON; maintenance and desktop exit remain usable. Reload is disabled while a launched Hangar session is running. Reload applies paths, descriptions and the return policy; restart to apply `fullscreen`. F11 changes the current session only.

- `schemaVersion`: `1`. Unknown keys fail validation to catch typos.
- `terminalName`: 1–80 characters.
- `fullscreen`: starts borderless/maximized by default.
- `returnToLauncher`: `true` restores the terminal when the directly launched process exits; `false` leaves it minimized, available on the taskbar. Start errors always restore it.
- `primary`: `label`, `path`, optional `workingDirectory`, and `arguments` as a string array. Use a foreground `.exe` that remains running for the lifetime of the app. Hangar supports `--fullscreen` and `--save-path`. Both supplied configurations include `--fullscreen`; remove it from `primary.arguments` for a windowed game launch. This is separate from the launcher's own `fullscreen` setting. Inside Hangar, **Esc** or either header screw restores window mode, and Alt+F4 closes Hangar and returns to the terminal.
- `references`: up to 12 items with `label`, `description`, `kind: "document"`, and a local `.pdf` path. Windows needs a default PDF reader. A file's existence is checked; PDF contents are left to that reader.
- `tools`: at most 2 entries. `kind: "settings"` supports `ms-settings:sound`, `ms-settings:display`, or `ms-settings:network-wifi`. `kind: "executable"` uses a local `.exe` with optional working directory and argument array. Shell scripts and arbitrary URI handlers are not supported. Sound and Display are the default utilities; neither changes any setting until the operator acts.

All file paths resolve relative to **the JSON file**, even when a startup shortcut uses another working directory. `%ENVIRONMENT_VARIABLES%` expand in file/directory paths. JSON backslashes must be escaped (`C:\\Apps\\Hangar.exe`); forward slashes also work. Omit `workingDirectory` to use the executable's folder. Arguments are literal strings, not shell commands; environment variables in arguments are not expanded. Network/UNC paths are refused. Treat the JSON as trusted local operator configuration because it can select local executables.

Primary launching is serialized. While it runs, reopening the terminal offers **RETURN TO HANGAR** and attempts to focus that process's main window; if Windows refuses foreground activation, use the taskbar or Alt+Tab. A nonzero exit displays an error and permits manual retry. A clean exit within two seconds displays an early-close warning. There are no automatic relaunches. Support apps run independently and are not killed on terminal exit.

The terminal prevents a second terminal instance within the same session. It does not find or prevent Hangar instances launched separately, and it cannot supervise detached child processes or apps that immediately hand off to another instance. Use the direct packaged Hangar executable, rather than a wrapper that exits early.

Logs: `%LOCALAPPDATA%/Gundam Assemble Hangar/Launcher/Logs/launcher.log`, with `.1` and `.2` backups at 1 MiB. Maintenance opens the folder. Logs contain timestamps, lifecycle, exit codes and errors; launch arguments are not logged. Path-related errors may include local paths. Logging errors are shown without blocking escape. No telemetry is sent by the launcher.

## Startup and optional automatic sign-in

1. Verify the portable layout, normal launch, PDFs and game exit on the target device **before** enabling startup. Test maintenance and desktop exit using touch.
2. Create a shortcut to `Hangar.Launcher.exe` in the dedicated user's Startup folder: open File Explorer and enter `shell:startup`, then place the shortcut there. Set its target to the permanent executable path; an external configuration can be selected with `--config "C:\\Terminal\\launcher.json"`. Use the actual path in the shortcut, with ordinary Windows quotes. This starts the terminal **after sign-in**, not before sign-in. Remove the shortcut to undo. See [Microsoft's startup instructions](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows).
3. Prefer a dedicated standard Windows account with no unrelated files or signed-in services. Keep a separate administrator account for maintenance. Normal startup does not require automatic sign-in.
4. If physical access is trusted and unattended sign-in is necessary, an administrator can optionally configure [Microsoft Sysinternals Autologon](https://learn.microsoft.com/en-us/sysinternals/downloads/autologon) using its interactive UI. It stores the password as an LSA secret; administrators can recover it. Anyone who can reach the device after boot gets access to that signed-in account. Do not place credentials in the launcher, JSON, shortcuts or scripts. Check organizational policy first. Autologon can be disabled in that tool; holding Shift before automatic sign-in bypasses it for that sign-in.
5. Verify a reboot manually. Windows updates, sleep, USB reconnects and account policy can interrupt the appliance experience. Keep Windows updates and security controls enabled. Display scaling and power behavior are manual device setup decisions.

Nothing in the build or executable enables startup, autologin, shell replacement, administrator privileges, key interception, password/PIN gates, shutdown/restart actions, or Windows lockdown. [Shell Launcher](https://learn.microsoft.com/en-us/windows/configuration/shell-launcher/) is a separate, edition-dependent managed Windows feature and is outside this MVP. This launch screen is not a security boundary.

## Verification

The build runs real child-process tests for normal/nonzero exit, argument preservation, working directory, concurrent-launch refusal, missing/corrupt executable recovery, malformed configuration, missing references, settings allowlist, reload, and log rotation/failure. Reports are written to `.build/launcher/tests/test-report.txt`.

Run the real WPF layout probe after publishing:

```powershell
$process = Start-Process -FilePath './dist/Hangar Terminal/Hangar.Launcher.exe' -ArgumentList '--config', "`"$PWD/launcher/launcher.development.json`"", '--layout-check', "`"$PWD/.build/launcher/layout`"" -WindowStyle Hidden -Wait -PassThru
$process.ExitCode
Get-Content .build/launcher/layout/layout-report.txt
```

The probe renders home, reference, tools and maintenance at logical viewports for 1920×1080 at 100/125/150/200% scaling and 1280×720 at 100%. It checks text fit, touch-target dimensions, embedded fonts and desktop-exit availability, saving PNGs and a report under `.build/launcher/layout`. This is layout testing, not a substitute for physical touch or live monitor-DPI testing.

For device acceptance: exercise actual scaling and multi-monitor moves, tap all pages, use PDFs in the installed reader, open tools, launch/close Hangar, forcibly terminate a **test** game session to check recovery, toggle `returnToLauncher`, repair/reload missing paths and malformed JSON, test Alt+F4/F11/Escape, and verify startup/remove-startup. Keep `--save-path` pointed at a separate test database. Latest performed checks and limitations are recorded in `VERIFICATION.md` in the source checkout.

Build reference: [Microsoft dotnet publish documentation](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-publish). WPF is published self-contained without trimming; ship the full output folder.

