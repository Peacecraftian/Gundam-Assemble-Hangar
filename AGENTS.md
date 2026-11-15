# Gundam Assemble repository instructions

## Active workspace and publishing

Use the active Gundam Assemble Hangar checkout for all development, tests, asset preparation and builds. Set the command's working directory explicitly to this checkout. Confirm the Git root and origin before editing; a checkout whose origin ends in `Gundam-Assemble-Hangar-Archive.git` or contains `.ARCHIVED-WORKSPACE` is historical reference only. Do not develop, build, commit or push there, or use its Python environment. Read-only reference access and explicitly requested archive maintenance are permitted.

Use this checkout's `.venv` and keep generated files under its `.build` and `dist` directories. On Windows, `build.ps1` automatically prefers `.venv/Scripts/python.exe`. Keep development changes and builds local until the user explicitly requests a commit, push or release update. Never merge or restore archived Git history into the active repository.

## Interface and runtime compatibility

Use the Hangar orange, dark outline and soft glow for pointer shapes, with appropriate hotspots. The text caret is a thin orange line. Regenerate Windows cursors with `python -m tools.render_cursor`. Keep published card IDs and original image filenames stable: saved matches reference them. Preserve rule validation, revision conflicts and the 20-edit undo limit.

## Authoring and published assets

`authoring/cards/Unit Cards` and `authoring/cards/Tactics Cards` contain the official English WEBPs and editable `SVG/<CARD-ID>.svg` masters. Keep original filenames and bytes. Do not commit generated PNGs, display copies, ZIPs or `.build/published`. Runtime files are selected explicitly by `companion/asset_pipeline.py`, not by copying the repository into a deployment. Retain icon and font license notices.

Run from the repository root:

```powershell
npm ci --prefix tools
python -m tools.prepare_assets
python -m unittest discover -s tests -v
```

The renderer uses installed Google Chrome, or the executable specified by `CARD_RENDER_CHROME`. To use Playwright's bundled Chromium instead, run `npm exec --prefix tools -- playwright install chromium` and set that variable to Playwright's `chromium.executablePath()`. `CARD_RENDER_ROOT` selects an isolated project root for direct rendering; it must contain the same `authoring/cards` structure. SVGs are served from a temporary loopback server with an exact input allowlist, disabled document JavaScript, and external requests blocked. Do not disable TLS or browser security policies.

`python -m tools.prepare_assets --check` reports pending renders without rendering or publishing; it exits nonzero if onboarding or rendering is needed. It writes `.build/onboarding.json`. `--watch --interval 30` periodically rescans the local checkout, rebuilds changed approved inputs, and republishes. It does not fetch remote Git or modify printed metadata. CI runs on pushes, pull requests and a weekly schedule. Restart the desktop application to load newly indexed cards; do not change active match snapshots to match an edited catalog.

## Onboard a Unit, Remote Weapon System or Tactics Card

1. Add the original English WEBP to the appropriate authoring card folder. Names must match `img_card_<number>_en.webp` or `img_card_front_<number>_en.webp`. IDs use uppercase printed numbers, including suffixes such as `EX02-U01A`. There must be one source per ID. Run preparation to generate the missing-input report; incomplete cards block publication rather than appearing with guessed rules.
2. Copy an existing matching SVG layout into `SVG/<CARD-ID>.svg`. Preserve the original artwork as embedded, replaceable raster elements. Rebuild typography, stats, labels, rules and geometry as editable text/shapes in named layers. Verify printed wording, punctuation, line breaks, `textLength`, icon positions and all values. Use solid off-white `#f8f6ef` instead of paper texture. Embed images and fonts, including required licenses; external asset references are not supported.
3. Match the viewBox and full-card rounded `clipPath#card-edge`: standard Units are 800×567; current RWS cards are 793×567; Tactics masters are 746×1044, including originals with a 1043px source height. Inspect new layouts before choosing geometry.
4. Add playable Unit metadata to `catalog.json`: `name`, `title`, `hp`, `vp`, `timeline`, `image`, and optional boolean `mass_produced`. Add Tactics printed names to `tactics.json`. Add RWS records to `remote_weapons.json` with `name`, `image`, `parent`, `hp`, `vp`, `icon_bounds`. Bounds are `[left, top, right, bottom]` fractions of the parent's SVG, covering both companion icons but excluding the count label. Parent IDs must refer to playable Units.
5. Run `python -m tools.prepare_assets`. It detects changed WEBPs, SVG masters and renderer code, then renders only affected cards. Direct commands remain `node tools/render_cards.cjs unit EX02-U01A` and `node tools/render_cards.cjs tactics EX01-T01`. Intermediate PNGs go to `.build/card-renders/<folder>/PNG`, never the authoring tree. Rendering adds the off-white edge in memory without changing masters. Unit exports are 3200×2268, current RWS 3172×2268 and Tactics 3200×4478. Geometry, transparent corners and three-pixel edge colors are verified automatically.
6. Compare finished renders with originals at application size and full resolution: all artwork, text, symbols, alignment, wrapping and alpha. Original publication remains authoritative; automated rendering cannot verify wording. Display derivatives use lossless WebP, content-based names, source and output hashes, and versioned size/crop/encoder recipes. Bump `RENDER_VERSION` when changing rendering behavior. Removed derivative variants are pruned only from generated caches.
7. Run tests and smoke-test the affected cards in Mission Sortie, Match Console, RWS overlays/deployment/defeat/undo, Tactics search/fan/draw and missing/corrupt derivative fallbacks. Full previews and the fan retain off-white rims; Hangar crops extend to bleed. Use a separate `--save-path` SQLite file.
8. Build with `build.ps1` using Windows x64 Python 3.13 with Tcl/Tk. It prepares and packages only `.build/published`, including original WEBPs for fallback and manifest-selected display copies. No authoring SVGs, high-resolution PNGs or design studies belong in the portable app. If an editable export ZIP is needed, generate it under `.build` or attach it to a release; do not commit it.

## Future scenarios and errata

Follow the [Battlefield palette rules](DESIGN.MD) when creating environments for new scenarios.

Retain official source files, publication dates/revisions and printed identifiers. Introduce a separate scenario index when needed. Record corrections with source revisions and affected card IDs, distinguishing artwork-only updates from gameplay changes. Check saved-match compatibility before changing published stats or identifiers.
