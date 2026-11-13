# Match animations

This folder holds the match cinematics, procedural effects, and playback code.

| File | Purpose |
| --- | --- |
| `Freight Lift.webp` | Animated Hangar doors |
| `Deploy_P1.webp`, `Deploy_P2.webp` | Player deployment cinematics |
| `UNIT-DEFEATED.webp` | Unit Defeat cinematic |
| `REACTOR-SURGE.webp` | Energize sprite sequence |
| `garrison_effect.py` | Generated Garrison Defeat explosion, Rescue particles, and shared placards |
| `energize_effect.py` | Reactor Surge frame loading and Energize presentation |
| `SONIC-WAKE.webp` | Compact blue bowl-shaped Vernier Dash sequence |
| `dash_effect.py` | Lazy Sonic Wake loading and player-aware Dash placard |
| `VICTORY-STANDARD.webp` | Green military standard and gold fireworks for Scenario Goal awards |
| `goal_effect.py` | Lazy Victory Standard loading and actual player/VP placard |
| `playback.py` | Overlay playback, Hangar door transitions, dimming, and timing |

Garrison animations are drawn at runtime so particles, player colors, and VP labels remain dynamic. They do not have separate video clips. Small interactive motions (dragging, hover, dice physics, and Battlefield token placement) belong to their respective UI controls.

`ANIMATION_FILES` in `__init__.py` explicitly selects the media shipped in the portable build. Add approved runtime clips there, then run `python -m tools.prepare_assets` and `build.ps1`. Python modules are bundled by PyInstaller through normal imports. Source MOV files are local-only and excluded from the portable build; experiments and exported studies stay in ignored `.local-authoring/`.

Reactor Surge authoring instructions are in [the development guide](../docs/DEVELOPMENT.md#reactor-surge-artwork).

Sonic Wake plays after a Dash successfully saves, with a 1.50-second sprite sequence and the shared 3.1-second notification timing. It loads on first use and renders at no more than 224px, shrinking to fit above the placard in smaller windows. Missing or corrupt artwork leaves the saved action and notification intact. Local previews and concepts are catalogued in the ignored `Images/Dash` folder. Rebuild the artwork with `python -m tools.prepare_sonic_wake .local-authoring/dash-sonic-wake/sprite-sheet.png`.

Scenario Goal plays Victory Standard only after a positive score is saved and its dialog closes. The 2.00-second clip retains the shared 3.1-second placard timing. It is loaded on first use and scales above the notification without rebuilding Match Console. Local previews and authoring notes are catalogued in the ignored `Images/Scenario Goal` folder. Repack with `python -m tools.prepare_victory_standard .local-authoring/victory-standard/sprite-sheet.png`.

## Animation studies

The local-only `VERNIER-BURST.webp` is a compact twin-afterburner study for Dash or future use: 256x256 transparent frames, 1.76 seconds. It is not wired to a match action or listed in `ANIMATION_FILES`, so it is excluded from portable builds. The storyboard and compact preview are catalogued locally in `Images/Dash`; original sheets remain in `.local-authoring/dash-vernier-burst`. Pack with `python -m tools.prepare_vernier_burst .local-authoring/dash-vernier-burst/sprite-sheet.png`.
