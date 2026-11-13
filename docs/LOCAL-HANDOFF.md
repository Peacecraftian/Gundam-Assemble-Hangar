# Continue development with the local agent

GitHub is the shared source of truth. The cloud cleanup and asset-pipeline changes are in the commit containing this document. Before removing the cloud environment, synchronize this commit into the existing Windows project and verify the Windows build there. Publishing a cloud environment is not a Git push or a website deployment.

## Preserve the existing project first

Have the local agent inspect the project's Git root, remote, branch, status (including ignored and untracked files), and any local-only commits. Make and verify a recoverable backup outside the project directory before synchronization. Preserve working files, local configuration, save databases, previous production output, and Git metadata. Keep credentials and save data private and out of commits. Do not reset, clean, force-push, or overwrite the project to make its status appear clean.

Old planning studies, original high-resolution PNG exports, alternate media, and editable design documents can remain local. Preserve these in the backup and, when useful, in ignored `.local-authoring/` inside the working project. The pull removes retired files from tracked paths; preserve any local files you still need before pulling. Do not restore the old layout over the new authoring tree.

## Synchronize the source

Confirm the remote is `https://github.com/Peacecraftian/Gundam-Assemble-Hangar.git`. Fetch `origin` and inspect `origin/main` before applying it. For a clean checkout with no divergent commits, fast-forward to `origin/main`. If the local project has additional code or asset changes, preserve them on a local branch or verified backup and reconcile them with the cleanup. Do not discard them. If the working folder is not a Git checkout, use a separate checkout to compare with and migrate the backed-up project; do not blindly overlay or delete its contents.

Use the existing Windows working folder once reconciled. You do not need to maintain another application copy in the cloud. Keep the final tracked source committed and pushed so local `HEAD` and `origin/main` identify the same commit. Ignored local authoring files and generated outputs are expected to differ between machines; byte-for-byte equality of those folders is not the goal.

The authoritative card sources are now:

- `authoring/cards/Unit Cards`: original WEBPs and editable `SVG/` masters.
- `authoring/cards/Tactics Cards`: original WEBPs and editable `SVG/` masters.

All 126 original card WEBPs and SVG masters were relocated without changing their bytes. Original card IDs and saved image filenames are unchanged. Generated PNG exports, display images, and runtime bundles now belong under ignored `.build/`. Card masters remain tracked so contributors can reproduce the build; moving them to a separate downloadable asset pack would be a later change.

## Validate on Windows

Use Windows x64 Python 3.13 with Tcl/Tk, Node.js 24, and Google Chrome (or a Chromium executable selected by `CARD_RENDER_CHROME`). Do not copy cloud executable paths or the cloud virtual environment to Windows. Set up or refresh the local virtual environment using the README.

From the reconciled project root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix tools
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tools.prepare_assets
.venv\Scripts\python.exe -m tools.prepare_assets --check
.venv\Scripts\python.exe run_companion.py --save-path (Join-Path $env:TEMP 'gundam-handoff-smoke.sqlite3')
.\build.ps1 -Python .venv\Scripts\python.exe
```

Use a new temporary save filename if the example already exists. Close the test application before packaging. Never replace the user's real match database for a smoke test.

Baseline verified in the cloud: 46 passing tests; all 63 card masters render; all 123 display variants load from the standalone runtime bundle; a clean fixture regenerates assets without existing PNGs or caches; repeat preparation renders zero unchanged cards. The first Windows preparation may rerender everything because browser and toolchain versions are part of the render signature. Subsequent unchanged runs should report zero renders and `--check` should have no pending cards.

Smoke-test Mission Sortie, Match Console, Unit/RWS previews, Tactics, saving and undo using the temporary save. Launch the packaged executable with a separate `--save-path` as well. Windows-specific fonts, cursors, overlays and packaging must be verified locally: Linux checks did not verify those capabilities. Do not push generated PNGs, `.build`, `dist`, ZIPs, `.local-authoring`, credentials, or saves.

## When the cloud environment can be removed

The local agent should report the local and GitHub commit IDs, any reconciled local-only work, test results, card-preparation results, packaged-app smoke results, and the location/status of the verified private backup. Address any failures first. Once this evidence confirms the local development workflow is working and the shared source is pushed, delete the cloud environment through its settings. There is no need to publish a cloud environment snapshot when retiring it.

The GitHub Actions workflow prepares runtime asset artifacts; it does not deploy a website. The browser interface is still future work. Removing large files from the current source tree does not erase their blobs from Git history; no history rewrite was performed.
