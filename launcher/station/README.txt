GUNDAM STATION
Portable edition for Windows 11 x64

FIRST RUN
1. In File Explorer, right-click the ZIP and choose Extract All. Choose a
   writable local folder, for example Documents\Game Station. Allow about
   300 MB for the extracted files in addition to the ZIP.
2. Open Gundam-Station\Launcher and double-click Hangar.Launcher.exe.
   The terminal opens fullscreen. Its diagnostics should show the Hangar
   executable ready and all three local references available.
3. Select ENTER HANGAR to open Mission Sortie fullscreen. To return to the
   terminal, close Hangar with Alt+F4. Esc switches Hangar to windowed mode.
   To leave the terminal, select MAINTENANCE, then RETURN TO DESKTOP.

Keep Launcher, Hangar and Setup together. Copy the entire Gundam-Station
folder to move the station. Both Windows runtimes are included. The game
runs offline. Opening a rules PDF uses the PC's default PDF reader.

SAVES AND BACKUP
Starting Hangar through the terminal creates Data\match.sqlite3 inside
Gundam-Station on first use. This is a new station save. With both programs
closed, back up the whole Data folder, including any SQLite sidecar files.
Extract upgrades to a new folder and copy your backed-up Data folder into it.
Opening Hangar\Gundam Assemble Hangar.exe directly without arguments uses
the game's regular per-user save. Use the terminal for station play.

OPTIONAL START AT SIGN-IN
First test the station manually. From your normal account, double-click
Setup\StationStartup.cmd and press E to enable. At your next Windows sign-in,
Task Scheduler opens this copy of the terminal on your desktop. To remove
the task, run the same utility and press R. Press Q to leave without changes.

Remove the task before moving the folder, then run the setup script again
from the new location. Setup uses an account-specific task name and refuses
to overwrite an existing task. If Windows blocks the downloaded script,
review it and use its file Properties > Unblock if available and permitted
by your device policy. Manual launch works independently of this utility.

TROUBLESHOOTING
If ENTER HANGAR is unavailable, check that you extracted the full ZIP and
that Hangar\Gundam Assemble Hangar.exe and its _internal folder are present.
If the terminal reports Exit 2, check Launcher\launcher.json and the game
version. Older game builds reject --fullscreen. Extract the matched pair
from this ZIP into a fresh folder. Do not mix files across releases.
Maintenance can open the launcher log. The log is in the Windows user's
local app data under Gundam Assemble Hangar\Launcher\Logs.

License and asset notices accompany the programs in Launcher\Licenses,
Hangar\_internal\NOTICE.md and Hangar\_internal\Licenses.
