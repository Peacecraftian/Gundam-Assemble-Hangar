param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$previousCache = $env:PYINSTALLER_CONFIG_DIR
Push-Location -LiteralPath $PSScriptRoot
try {
    @'
import sys
import sysconfig
import tkinter

from PIL import Image, ImageFont

from companion.artwork import (
    APP_CURSORS, APP_ICON, decal_art, hangar_art, logo_art, navigation_icon, objective_art, speaker_art,
    status_art, token_art, upgrade_art,
)
from companion.catalog import ASSETS, TACTICS_CARDS, UNIT_CARDS, load_card_image, load_catalog, load_remote_weapons, load_tactics
from Video.playback import DEFEAT_ART, DEPLOYMENT_ART_BY_SIDE
from Video.energize_effect import SURGE_ART
from Video.dash_effect import DASH_ART
from Video.goal_effect import GOAL_ART
from companion.dice import DiceWorld
from companion.match import STATUS_EFFECTS
from companion.theme import DISPLAY_FAMILY, DISPLAY_FONT, NAVIGATION_ICONS, SCORE_FAMILY, SCORE_FONT

assert sys.version_info[:2] == (3, 13) and sysconfig.get_platform() == "win-amd64", "Use Python 3.13 x64"
tkinter.Tcl()
for path, family, weight, license_name in (
    (DISPLAY_FONT, DISPLAY_FAMILY, "Bold", "OFL-Chakra-Petch.txt"),
    (SCORE_FONT, SCORE_FAMILY, "Regular", "OFL-Saira-Stencil-One.txt"),
):
    assert ImageFont.truetype(str(path), 20).getname() == (family, weight), f"Invalid font: {path.name}"
    assert path.with_name(license_name).is_file(), f"Missing font license: {license_name}"
assert len(hangar_art()) > 1, "Could not load animated Video/Freight Lift.webp"
assert logo_art() is not None, "Could not load Images/gundam-assemble-hangar.png"
grille = speaker_art()
assert grille is not None and grille.size == (75, 26) and grille.getbbox(), "Invalid Images/speaker-grille.png"
for name, size in (("sortie-warning", (222, 46)), ("sortie-chevrons", (45, 18)), ("sortie-arrow", (23, 23)),
                   ("pixel-decal", (74, 50)), ("score-warning", (105, 35)), ("hangar-chevrons", (50, 20))):
    decal = decal_art(name)
    assert decal is not None and decal.size == size and decal.getbbox(), f"Invalid Images/{name}.png"
for name in NAVIGATION_ICONS.values():
    icon = navigation_icon(name, "#ffffff")
    assert icon is not None and icon.getbbox() is not None, f"Missing or empty navigation icon: {name}"
with Image.open(APP_ICON) as icon:
    assert icon.format == "ICO" and {(16, 16), (32, 32), (256, 256)} <= icon.ico.sizes(), "Invalid Windows app icon"
    icon.load()
for path in APP_CURSORS.values():
    with Image.open(path) as pointer:
        assert pointer.format == "CUR", f"Invalid Windows app cursor: {path.name}"
        pointer.load()
for path in (*DEPLOYMENT_ART_BY_SIDE, DEFEAT_ART, SURGE_ART, DASH_ART, GOAL_ART):
    with Image.open(path) as overlay:
        assert overlay.is_animated, f"{path.name} must be animated"
        overlay.load()
for key in ("hp", "energy"):
    token_art(key, 28)
for side in range(2):
    objective_art(side)
for status in STATUS_EFFECTS:
    status_art(status, True)
for key in ("shield_active", "shield_spent", "shield_empty", "speed", "strength"):
    upgrade_art(key)
from companion.asset_pipeline import prepare_assets
print(prepare_assets(ASSETS))
with DiceWorld() as physics:
    physics.start(1, 2)
    assert len(physics.step(1)[0]) == 1, "D10 physics could not start"
from Video.energize_effect import reactor_frames
surge_frames, surge_deadlines = reactor_frames()
assert len(surge_frames) == 24 and surge_deadlines[-1] == 1.92, "Invalid Reactor Surge animation"
for frame in surge_frames:
    assert frame.size == (256, 256) and frame.getbbox(), "Invalid Reactor Surge frame"
    assert not any(frame.getchannel("A").histogram()[1:255]), "Reactor Surge needs color-key-safe alpha"
from Video.dash_effect import dash_frames
wake_frames, wake_deadlines = dash_frames()
assert len(wake_frames) == 25 and wake_deadlines[-1] == 1.5, "Invalid Sonic Wake animation"
assert wake_frames[-1].getbbox() is None, "Sonic Wake must finish transparent"
for frame in wake_frames:
    assert frame.size == (256, 256), "Invalid Sonic Wake frame size"
    assert not any(frame.getchannel("A").histogram()[1:255]), "Sonic Wake needs color-key-safe alpha"
units = load_catalog(verify_images=True)
from Video.goal_effect import goal_frames
victory_frames, victory_deadlines = goal_frames()
assert len(victory_frames) == 25 and victory_deadlines[-1] == 2.0, "Invalid Victory Standard animation"
assert victory_frames[-1].getbbox() is None, "Victory Standard must finish transparent"
for frame in victory_frames:
    assert frame.size == (256, 256), "Invalid Victory Standard frame size"
    assert not any(frame.getchannel("A").histogram()[1:255]), "Victory Standard needs color-key-safe alpha"
remote_weapons = load_remote_weapons(units, verify_images=True)
tactics = load_tactics()
for card in tactics.values():
    assert load_card_image(card.image, folder=TACTICS_CARDS, size=(1, 1)) is not None, f"Unreadable Tactics Card: {card.number}"
print(f"Verified {len(units)} Unit Cards, {len(remote_weapons)} Remote Weapon Systems, {len(tactics)} Tactics Cards, "
      "token art, Hangar image, speaker grille, app logo, and icon")
'@ | & $Python -
    if ($LASTEXITCODE -ne 0) { throw "Runtime or catalog validation failed." }

    $projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot ".build/pyinstaller-cache"
    $dist = Join-Path $projectRoot "dist"
    $name = "Gundam Assemble Hangar"
    $package = Join-Path $dist $name
    $appIcon = Join-Path $projectRoot "Images/gundam-assemble-hangar.ico"
    foreach ($path in @($dist, $package)) {
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Build output may not be a link: $path"
            }
        }
    }

    # The prepared bundle is an explicit runtime allowlist. Authoring masters and
    # high-resolution intermediate PNGs never enter the portable application.
    $published = Join-Path $projectRoot ".build/published"
    & $Python -m tools.prepare_runtime_licenses
    if ($LASTEXITCODE -ne 0) { throw "Runtime license preparation failed." }
    $runtimeLicenses = Join-Path $projectRoot ".build/runtime-licenses"
    & $Python -m PyInstaller --noconfirm --onedir --windowed --name $name --distpath $dist `
        --workpath ".build/pyinstaller" --specpath ".build" `
        --icon $appIcon --add-data "${published}:." --add-data "${runtimeLicenses}:Licenses" `
        --collect-all py_mini_racer --copy-metadata mini-racer run_companion.py
    if ($LASTEXITCODE -ne 0) { throw "Portable build failed." }

    & $Python -m tools.prepare_runtime_licenses --verify (Join-Path $package "_internal/Licenses")
    if ($LASTEXITCODE -ne 0) { throw "Packaged runtime license verification failed." }
    Compress-Archive -LiteralPath $package -DestinationPath (Join-Path $dist "$name.zip") -Force
} finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
    Pop-Location
}
