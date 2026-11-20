# Hangar Terminal — MVP

Dedicated Windows 11 front door for a 15.6-inch, 1920×1080 landscape touchscreen. A standalone .NET 10 WPF application starts in borderless fullscreen and hands off to the existing Tk/PyInstaller Hangar app. It never edits matches, card catalogs, or Windows security configuration.

## User journeys

- **ENTER HANGAR:** validate the configured executable and working directory, launch once, minimize the terminal, and monitor that exact process. Repeated taps cannot create another instance. If already running, offer to return to its window. Return to the terminal on exit by default, with clear nonzero-exit feedback and a manual retry. No automatic crash/restart loop.
- **REFERENCE:** select a local rules PDF; Windows opens it in the registered viewer. Missing files remain visible with a reason. No network is needed. Viewer availability is a device setup responsibility.
- **TOOLS:** up to two configured utilities; default choices are Sound and Display settings. Executables and supported Windows settings pages are allowed. Support apps have independent lifetimes.
- **MAINTENANCE:** reload configuration, open configuration/log folders, toggle window mode, or exit to desktop. Always reachable by touch. Escape opens maintenance; Alt+F4 exits; F11 toggles window mode. Explorer, task switching and Windows emergency shortcuts remain available.

## Integration

Production `launcher.json` expects a sibling `Gundam Assemble Hangar` portable folder. Development configuration uses this checkout's `dist/Gundam Assemble Hangar/Gundam Assemble Hangar.exe`, existing `Rules/*.pdf`, and an isolated `.build/launcher-smoke.sqlite3`. The source entry point `run_companion.py` supports `--save-path` and opt-in `--fullscreen`. Both launcher configurations pass `--fullscreen`; the game enters its existing monitor-aware fullscreen mode before its window becomes visible. Direct game launches remain windowed unless that flag is supplied. Esc or either header screw restores window mode; closing the game returns to the launcher. Older packaged game executables must be rebuilt for flag support.

JSON paths are relative to the configuration file, with environment variables expanded. Argument arrays preserve spaces without command-line string concatenation. Explicit executable paths are required; no PATH search, shell scripts, arbitrary URI handlers or elevation requests. Configuration is trusted local operator input. Malformed configuration leaves a usable recovery screen with primary launch blocked until repaired/reloaded.

Per-user logs rotate at 1 MiB with two backups. Record lifecycle, exit codes and errors, excluding launch arguments. Log-write failure must not prevent desktop escape. Another terminal instance in the same Windows session is refused. Exiting the terminal leaves a running Hangar untouched.

## Acceptance and limits

- Home, reference, tools, maintenance, error and running states support touch, Tab, Enter and visible keyboard focus.
- Layout uses WPF device-independent units, per-monitor DPI awareness, fluid columns and scrolling at high scaling. Controls have at least 56-DIP targets. Target checks: 1920×1080 at 100%, 125%, 150%, 200%; 1280×720 fallback.
- Missing executable/directory/PDF, malformed JSON, nonzero exit, fast exit, double launch, disabled auto-return, recovery/reload and desktop escape have defined outcomes.
- This is a launcher, not an enforced kiosk. No password storage, shell replacement, autologin, startup changes, reboot/power controls or privileged lockdown are performed. Setup documentation describes opt-in Windows startup and autologin.
- Monitor a directly launched foreground application that stays alive for its UI lifetime. Wrapper processes, detached children, externally started Hangar instances and already-running PDF/settings viewers are not supervised. There is no global Hangar instance lock.
- Physical touch hardware, wake/sleep and actual Windows display-scale changes require acceptance on the dedicated device. Automated layout probes supplement that test.
