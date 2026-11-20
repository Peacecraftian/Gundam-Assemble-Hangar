# Hangar development guide

## Develop and build

Use the full Windows x64 distribution of Python 3.13 with Tcl/Tk.

Run these commands from the active checkout, not the retained archive. Check `git remote get-url origin` before starting work; the archived repository ends in `-Archive.git`. Keep the virtual environment, generated assets and build output in the active checkout. `build.ps1` defaults to this checkout's `.venv` when it exists and refuses an archived workspace or an interpreter located inside one.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix tools
.venv\Scripts\python.exe -m tools.prepare_assets
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe run_companion.py
.\build.ps1
```

The build validates the catalog and writes the portable folder and ZIP under `dist`. To test without modifying your match, launch with `--save-path` and a path to a separate SQLite file.

Add `--fullscreen` to open directly in monitor-aware fullscreen, for example `.venv\Scripts\python.exe run_companion.py --fullscreen --save-path .build/fullscreen-qa.sqlite3`. Hangar Terminal supplies this flag by default; rebuild the game executable after adding flag support. Escape or either header screw restores window mode. Without the flag, direct launches remain windowed.

Bordered Tk frames need explicit widget padding: the image slices in `frame_surface` paint the bezel but do not reserve space for child widgets. Keep content at least two pixels inside the stroke, allowing additional bottom space for shadows. Use `PanelFill.TFrame` or `RailFill.TFrame` for nested layout groups that should not draw another border. Shared `Dialog` windows allocate their footer before the expanding body; place action buttons directly in that footer before packing flexible status text. Native layout regression tests run when a Tk display is available.

Use `FooterButton` for footer actions. Its shared width, padding and responsive font keep primary, quiet, destructive and RWS controls the same size. Battlefield moves brush guidance above the action row when editing in a narrow window. Check both 1366×768 and the minimum 1020×595 layout, including all seven custom-scenario editing buttons and attack results with Accuracy, Reroll Selected and Apply Damage visible.

The app loads Chakra Petch Bold for display text and Saira Stencil One for VP totals privately on Windows. Both fonts and their SIL Open Font Licenses are bundled in [Fonts](../Fonts). [Chakra Petch source](https://github.com/google/fonts/tree/main/ofl/chakrapetch) · [Saira Stencil One source](https://github.com/google/fonts/tree/main/ofl/sairastencilone)

The D10 tray runs Cannon-es in embedded V8. Asset preparation publishes the pinned physics module and its MIT license from `tools/node_modules`. PyInstaller bundles PyMiniRacer and its license metadata. V8 14.4.258.23 and ICU notices are in [Dice/licenses](../Dice/licenses). Refresh those notices when updating the embedded runtime. [Cannon-es](https://github.com/pmndrs/cannon-es/tree/v0.20.0) · [PyMiniRacer](https://github.com/bpcreech/PyMiniRacer) · [V8](https://github.com/v8/v8/tree/14.4.258.23) · [ICU](https://chromium.googlesource.com/chromium/deps/icu.git/+/a86a32e67b8d1384b33f8fa48c83a6079b86f8cd/LICENSE)

## Android tablet build

Windows and Android share the match, scoring, scenario and persistence model. Android has its own native UI in `platforms/android`; changing shared Python behavior requires checks on both platforms, while UI-only changes need the affected platform's checks.

Install Android Studio with SDK Platform 35, Build Tools 35, Platform Tools and a landscape tablet emulator. Use the bundled JDK (or a compatible JDK 17+), set `JAVA_HOME` and `ANDROID_HOME`, and prepare the root Python environment and Node dependencies above. From the repository root:

```powershell
./platforms/android/gradlew.bat -p platforms/android assembleDebug
```

The debug APK is written to `platforms/android/app/build/outputs/apk/debug/app-debug.apk`. Install it with Android Studio or `adb install -r`. For the convenience launcher, create an AVD named `Hangar_Landscape_Tablet`, then run `./platforms/android/run-tablet.ps1`. Add `-LaunchOnly` to reuse the installed build. Use a separate emulator for tests so normal tablet saves stay intact.

`assembleRelease` produces an unsigned APK under `app/build/outputs/apk/release`. Align/sign it using Android SDK Build Tools and your own private keystore, then verify with `apksigner verify`. Published updates must use the same signing certificate and an increased `versionCode`. Keep signing keys, passwords and emulator state outside Git; `.local-authoring/` is ignored. Development APKs use a different certificate from the official release and cannot upgrade that installation in place. Do not uninstall an app with saves you need to keep.

The APK contains ARM64 and x86-64 builds, original printed cards, Sortie full-art variants, offline fonts, effects and notices. Runtime notices and their source versions live in `platforms/android/licenses`. No Google Play services or server is required for gameplay. Check the signed APK itself for installation, squad setup, deployment, actions, Undo and reopening a saved match before publishing.

## Combined Windows station

Build the station's game input with `./build.ps1` (root `dist` output), then the terminal with `./launcher/build.ps1`. The separate `./platforms/windows/build.ps1` entry point writes standalone Windows output to `platforms/windows/dist`; the station packager consumes root `dist`. Run `.venv/Scripts/python.exe -m tools.package_station` to create `dist/Gundam-Station-Portable.zip`. This includes both self-contained applications, local rules references, notices and optional startup setup. See [the terminal guide](../launcher/README.md). Preserve the station's `Data` directory when updating an installed station.

## Bundle an official scenario

Build and test the scenario in **Battlefield**, then use **Export** in the footer. From the repository root, run the bundling command with the exported file, a stable official ID, and its publication date or revision.

```powershell
.venv\Scripts\python.exe -m tools.bundle_scenario "path\to\coastal-assault.json" --id official-coastal-assault --revision "1.0"
.\build.ps1 -Python .venv\Scripts\python.exe
```

The command archives the original export in [authoring/scenarios](../authoring/scenarios) and adds its validated record to [scenarios.json](../scenarios.json). Use the published identifier when one exists and keep IDs stable so saved matches stay linked.

The Windows build includes the catalog. Bundled scenarios appear in **Battlefield** and **Mission Sortie**. Saving edits to a bundled scenario in Battlefield creates a local copy.

The gold flag **Objective** and gold Visor Cut helmet **Special Objective** each use an independent `objective_number` sequence starting at 1. Placement appends to that type’s sequence; removing or replacing a token closes its gap. Regular objectives retain their four-marker placement limit. The helmet’s meaning belongs in the scenario briefing. Existing unnumbered markers receive numbers in board order when loaded, without rewriting saved scenario payloads.

Operation Sleeping Leviathan retains the archived VER2 export as its source. The runtime catalog rotates its terrain and tokens clockwise to match the board orientation in Entry Set Scenario 01, pages 34–35.

Operation Azure Fang uses the user's REV2 map with the deployment zones restored on 2026-11-16 while retaining the official ID `official-azure-fang` and its unsuffixed display name. See [its revision history](../authoring/scenarios/azure-fang-revisions.md) for the changed hexes and preserved original source.

Operation Lockdown is bundled from the user’s saved Battlefield scenario with stable ID `official-lockdown`. Its briefing, Urban palette, terrain and numbered objectives are preserved in the [archived source and inclusion record](../authoring/scenarios/lockdown-revisions.md).

Operation Gravedigger is bundled as `official-gravedigger`, preserving the user's Space-palette map, briefing, regular and special objectives. See [its inclusion record](../authoring/scenarios/gravedigger-revisions.md).

Battlefield’s elevation fills, legend swatches, and hex outlines use exact colors from the [Pineapple 32 reference](../Images/palette_pineapple-32-32x.png).

Edit Special Terrain SVG masters in [Tokens](../Tokens) alongside the other token artwork. Asset preparation rerenders them as a batch when a master or the renderer changes and publishes the resulting transparent decals in the runtime’s `Tokens/rendered` folder.

## Match Console refresh

Normal saves and undo reuse the existing Match Console widgets. `Companion.refresh_console` compares the previous and saved match, updates VP text, round/phase controls and Timeline positions, and redraws only affected unit displays. Timeline-only moves leave Hangar/card art untouched; existing Hangar scroll positions, Timeline stack offsets and selected unit are retained. The Other Phases button queries the current match when opened instead of retaining a pre-save unit list.

Use full `render()` for navigation, replacement matches, changed roster/header structure, finishing/reopening a match, and conflict recovery. Targeted `refresh=` callbacks remain supported for existing inline controls. Trigger action animations only after a successful save; animation playback must not rebuild the page. Save revision checks and the 20-edit undo history are unchanged.

## Reactor Surge artwork

Match animation media and effect generators live together in [Video](../Video/README.md). `Video/playback.py` coordinates playback, and `Video/__init__.py` lists the runtime media explicitly. The animated Hangar door is `Video/Freight Lift.webp`.

Energize plays `Video/REACTOR-SURGE.webp`, an original 24-frame, lossless pixel animation (80 ms per frame). It is explicitly included in the runtime asset allowlist and decoded on first use. The sprite ends after 1.92 seconds; the existing action placard retains its 3.1-second lifecycle. Missing or damaged artwork leaves the saved action and placard functional.

The approved storyboard, generated source sheet and generation notes are preserved locally under ignored `.local-authoring/reactor-surge/`. To repack that source, run `python -m tools.prepare_reactor_surge .local-authoring/reactor-surge/sprite-sheet.png`, followed by normal asset preparation and the Windows build. The packer anchors this sheet's irregular row baselines, retains the original source, and converts coverage to binary alpha for the Windows color-key overlay. Authoring sheets are not included in portable builds. A different source layout needs its own reviewed row cuts and anchors.

## Navigation icons

The navigation icons use Lucide 0.468.0. The original SVGs, transparent PNG exports, and license notices are in [Images/Navigation](../Images/Navigation). For a future tab, export a 64×64 PNG from the matching Lucide SVG and register its name in `NAVIGATION_ICONS`. [Browse the Lucide icon set](https://lucide.dev/icons/).

## Cards and asset preparation

Windows builds collect the installed Python, Pillow (including its bundled library notices), and PyInstaller license texts into `_internal/Licenses`. The build fails if a required notice is missing or its packaged bytes differ from the source. A manifest records versions and hashes without build-machine paths. Font, icon, dice-engine, mini-racer and Tk notices remain alongside their assets. These software notices do not grant redistribution rights to official game media.

Official WEBPs and editable SVG masters live in `authoring/cards/Unit Cards` and `authoring/cards/Tactics Cards`. For Windows Mission Sortie, place the optional full-art `img_card_<id>_en.webp` beside the playable unit’s catalog-listed `img_card_front_<id>_en.webp`. Setup uses the full art when available. The printed front remains the source for the Match Console, rules-card renders, and saved matches. Full-resolution PNG exports, display derivatives and publication bundles are generated under ignored `.build`; they are not version-controlled.

Tracker portraits use card-specific horizontal face positions in `PORTRAIT_CENTERS` in `companion/card_display.py`, measured as a fraction of full card width. `PORTRAIT_WINDOWS` supplies tighter width/height fractions where printed titles intrude into the artwork. When adding a card or changing its artwork, inspect its face at narrow target-picker and wide Timeline sizes, checking that no card lettering remains. Set its framing point and any crop override by published ID and bump `RENDER_VERSION` when changing the crop recipe. Preparation rebuilds the portrait derivatives; the original-image fallback uses the same framing. Full cards and Hangar crops are unaffected.

For a new playable Unit Card, add its printed weapon profiles to [attacks.json](../attacks.json) under its card number. Verify the name, Timeline cost, Range and Strength against the original, and measure `bounds` as `[left, top, right, bottom]` fractions of the full card around the three stat symbols. Use `"SP"` for special range.

```powershell
npm ci --prefix tools
python -m tools.prepare_assets
python -m tools.prepare_assets --check
python -m tools.prepare_assets --watch --interval 30
```

Use installed Google Chrome, or set `CARD_RENDER_CHROME` to another Chromium executable. The renderer uses an input-only loopback HTTP server and never changes source masters. Preparation scans both card sets, rejects duplicate IDs, checks metadata and masters, renders changed cards, and creates smaller lossless WebP images. Cache keys cover source contents, requested dimensions, crop/renderer version and encoder settings; generated files have content-based names and checksums. Corrupt outputs are rebuilt, and removed card variants are pruned.

New cards missing printed metadata or SVG masters are recorded in `.build/onboarding.json` and block publication. Complete those steps using an existing matching template, verify text and stats against the original, then rerun preparation. See [AGENTS.md](../AGENTS.md) for the full procedure. The watcher rescans local files every 30 seconds; it does not fetch GitHub. Restart the desktop app after adding catalog entries. A GitHub Actions workflow also validates/prepares the bundle on pushes, pull requests and weekly; it does not automatically publish a website.

`.build/published` contains only runtime metadata, manifest-selected card images, original WEBPs for fallback, and explicitly allowed UI assets/fonts/license notices. `assets.json` lists every published file and checksum. This is the asset input for the portable Windows build and a future web interface; it is not yet a standalone website. Deploy this bundle with the application rather than exposing the source repository, authoring masters or local saves.

## Touch controls and status timing

The main UI imports `touch_cards`, `touch_scores_panel`, `touch_service`, `touch_scores`, and `touch_actions` directly. The normal full-card viewer installs `CardDismissGesture`; dice prompts explicitly create `StatusDiceTray`. There are no draft-launcher dependencies or runtime class replacements. The original shared widgets remain bases for the touch layouts.

`Match.resolve_attack` computes Fracture from adjusted combat damage before Shields, consumes it on triggering attacks, and saves damage/defeat as one edit. `Match.consume_disarm` clears the status after the required hit reroll. Disarm blocks critical effects throughout that attack; subsequent rerolls and Accuracy changes are locked once that timing step is resolved. All-miss and zero-die attacks consume Disarm at the resolution checkpoint. Slow is not tied to Timeline movement or Dash. Source: bundled Core Rulebook v1.2 (November 6, 2026), pp. 28–29, 35, 37–38.

Regression tests include native Tk controls, cancelled actions, target eligibility, dice limits, stale revisions, failed status saves, Fracture thresholds, and undo after reopening. GUI tests skip when no display is available. Use `run_companion.py --save-path .build/integration-qa/match.sqlite3` for an isolated native check; never test against the normal player save.


### Touch keyboards

Attach editable application fields with `dialogs.touch_keyboard(widget, title)` (implemented in `companion/touch_keyboard.py`). Use `live=True` for search, `multiline=True` for briefing text, and `numeric=True` for integer inputs. Do not attach read-only selectors, card viewers, or the keyboard's own input. The shared keyboard commits into the existing field/draft, not directly into saved matches or scenarios; existing validation and parent Save/Cancel flows remain authoritative. Live-search Cancel restores the original query. Multiline commits form one text undo operation. The four-tab field coverage test in `tests/test_touch_keyboard.py` should include new entry points.

Attack declarations persist their TL payment and settled dice. Saves for subsequent rolls, Disarm and final damage share the declaration Undo entry. An independent match edit ends a suspended attack with TL paid.
