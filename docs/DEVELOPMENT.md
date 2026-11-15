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

Bordered Tk frames need explicit widget padding: the image slices in `frame_surface` paint the bezel but do not reserve space for child widgets. Keep content at least two pixels inside the stroke, allowing additional bottom space for shadows. Use `PanelFill.TFrame` or `RailFill.TFrame` for nested layout groups that should not draw another border. Shared `Dialog` windows allocate their footer before the expanding body; place action buttons directly in that footer before packing flexible status text. Native layout regression tests run when a Tk display is available.

Use `FooterButton` for footer actions. Its shared width, padding and responsive font keep primary, quiet, destructive and RWS controls the same size. Battlefield moves brush guidance above the action row when editing in a narrow window. Check both 1366×768 and the minimum 1020×595 layout, including all seven custom-scenario editing buttons and attack results with Accuracy, Reroll Selected and Apply Damage visible.

The app loads Chakra Petch Bold for display text and Saira Stencil One for VP totals privately on Windows. Both fonts and their SIL Open Font Licenses are bundled in [Fonts](../Fonts). [Chakra Petch source](https://github.com/google/fonts/tree/main/ofl/chakrapetch) · [Saira Stencil One source](https://github.com/google/fonts/tree/main/ofl/sairastencilone)

The D10 tray runs Cannon-es in embedded V8. Asset preparation publishes the pinned physics module and its MIT license from `tools/node_modules`. PyInstaller bundles PyMiniRacer and its license metadata. V8 14.4.258.23 and ICU notices are in [Dice/licenses](../Dice/licenses). Refresh those notices when updating the embedded runtime. [Cannon-es](https://github.com/pmndrs/cannon-es/tree/v0.20.0) · [PyMiniRacer](https://github.com/bpcreech/PyMiniRacer) · [V8](https://github.com/v8/v8/tree/14.4.258.23) · [ICU](https://chromium.googlesource.com/chromium/deps/icu.git/+/a86a32e67b8d1384b33f8fa48c83a6079b86f8cd/LICENSE)

## Bundle an official scenario

Build and test the scenario in **Battlefield**, then use **Export** in the footer. From the repository root, run the bundling command with the exported file, a stable official ID, and its publication date or revision.

```powershell
.venv\Scripts\python.exe -m tools.bundle_scenario "path\to\coastal-assault.json" --id official-coastal-assault --revision "1.0"
.\build.ps1 -Python .venv\Scripts\python.exe
```

The command archives the original export in [authoring/scenarios](../authoring/scenarios) and adds its validated record to [scenarios.json](../scenarios.json). Use the published identifier when one exists and keep IDs stable so saved matches stay linked.

The Windows build includes the catalog. Bundled scenarios appear in **Battlefield** and **Mission Sortie**. Saving edits to a bundled scenario in Battlefield creates a local copy.

Operation Sleeping Leviathan retains the archived VER2 export as its source. The runtime catalog rotates its terrain and tokens clockwise to match the board orientation in Entry Set Scenario 01, pages 34–35.

Operation Azure Fang uses the user's archived REV2 export while retaining the official ID `official-azure-fang` and its unsuffixed display name. See [its revision history](../authoring/scenarios/azure-fang-revisions.md) for the changed hexes and preserved original source.

Operation Lockdown is bundled from the user’s saved Battlefield scenario with stable ID `official-lockdown`. Its briefing, Urban palette, terrain and numbered objectives are preserved in the [archived source and inclusion record](../authoring/scenarios/lockdown-revisions.md).

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

Official WEBPs and editable SVG masters live in `authoring/cards/Unit Cards` and `authoring/cards/Tactics Cards`. The original card IDs and filenames remain compatible with saved matches. Full-resolution PNG exports, display derivatives and publication bundles are generated under ignored `.build`; they are not version-controlled.

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
