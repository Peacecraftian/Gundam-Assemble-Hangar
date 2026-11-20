"""Build the station ZIP from the two published win-x64 distributions."""

import hashlib
import json
import marshal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import CodeType
from zipfile import ZIP_DEFLATED, ZipFile

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
FRONTEND = DIST / "Hangar Terminal"
GAME = DIST / "Gundam Assemble Hangar"
TEMPLATE = ROOT / "launcher" / "station"
PREFIX = "Gundam-Station"


def station_config():
    config = json.loads((FRONTEND / "launcher.json").read_text(encoding="utf-8"))
    primary = config["primary"]
    if (FRONTEND / primary["path"]).resolve() != GAME / "Gundam Assemble Hangar.exe":
        raise ValueError("Expected the production Hangar target in the published configuration.")
    args = primary["arguments"]
    if "--fullscreen" not in args or "--save-path" in args:
        raise ValueError("Expected production launch arguments with fullscreen and no save override.")
    for reference in config["references"]:
        path = (FRONTEND / reference["path"]).resolve()
        if not path.is_relative_to(FRONTEND) or not path.is_file():
            raise ValueError(f"Missing bundled reference: {reference['path']}")
    primary["path"] = "../Hangar/Gundam Assemble Hangar.exe"
    primary.pop("workingDirectory", None)  # LaunchService defaults to the EXE's directory.
    args.extend(["--save-path", "../Data/match.sqlite3"])
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def check_game():
    # An older frozen entry point accepts --save-path but exits 2 on --fullscreen.
    archive = CArchiveReader(str(GAME / "Gundam Assemble Hangar.exe"))
    entry = marshal.loads(archive.extract("run_companion"))
    main = next(c for c in entry.co_consts if isinstance(c, CodeType) and c.co_name == "main")
    if not {"--fullscreen", "--save-path"}.issubset(s for s in main.co_consts if isinstance(s, str)):
        raise ValueError("Rebuild Hangar with fullscreen and alternate-save support.")
    internal = GAME / "_internal"
    assets = json.loads((internal / "assets.json").read_text(encoding="utf-8"))
    for name, record in assets["files"].items():
        with (internal / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != record["sha256"]:
                raise ValueError(f"Published asset differs from manifest: {name}")


def add_distribution(bundle, source, destination, skip=()):
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(source).as_posix()
        if name in skip:
            continue
        if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log"} or path.name.endswith(("-wal", "-shm", "-journal")):
            raise ValueError(f"Unexpected user data in distribution: {name}")
        bundle.write(path, f"{PREFIX}/{destination}/{name}")


def package():
    if (ROOT / ".ARCHIVED-WORKSPACE").exists():
        raise ValueError("Build the station from the active checkout.")
    config = station_config()
    check_game()
    for name in ("Hangar.Launcher.exe", "Hangar.Launcher.dll", "hostfxr.dll", "coreclr.dll",
                 "PresentationFramework.dll", "Audio/key-press.wav", "Audio/pilot-lock.wav"):
        if not (FRONTEND / name).is_file():
            raise FileNotFoundError(FRONTEND / name)
    runtime = json.loads((FRONTEND / "Hangar.Launcher.runtimeconfig.json").read_text(encoding="utf-8"))
    notices = ROOT / ".build" / "nuget"
    output = DIST / "Gundam-Station-Portable.zip"
    with TemporaryDirectory(dir=ROOT / ".build") as work:
        pending = Path(work) / output.name
        with ZipFile(pending, "w", ZIP_DEFLATED, compresslevel=6) as bundle:
            add_distribution(bundle, FRONTEND, "Launcher", {"launcher.json", "README.md", "Hangar.Launcher.pdb"})
            add_distribution(bundle, GAME, "Hangar")
            bundle.writestr(f"{PREFIX}/Launcher/launcher.json", config.encode("utf-8"))
            for framework in runtime["runtimeOptions"]["includedFrameworks"]:
                component = framework["name"]
                pack = notices / f"{component.lower()}.runtime.win-x64" / framework["version"]
                licenses = ("LICENSE",) if component == "Microsoft.WindowsDesktop.App" else ("LICENSE.TXT", "THIRD-PARTY-NOTICES.TXT")
                for license_file in licenses:
                    bundle.write(pack / license_file, f"{PREFIX}/Launcher/Licenses/{component}/{license_file}")
            bundle.write(TEMPLATE / "README.txt", f"{PREFIX}/README.txt")
            bundle.write(TEMPLATE / "StationStartup.ps1", f"{PREFIX}/Setup/StationStartup.ps1")
            menu = (TEMPLATE / "StationStartup.cmd").read_text(encoding="ascii")
            bundle.writestr(f"{PREFIX}/Setup/StationStartup.cmd", menu.replace("\n", "\r\n").encode("ascii"))
        with ZipFile(pending) as bundle:
            damaged = bundle.testzip()
            if damaged:
                raise ValueError(f"Archive verification failed: {damaged}")
        pending.replace(output)
    return output


if __name__ == "__main__":
    print(package())
