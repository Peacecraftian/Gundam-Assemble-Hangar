# Operation Azure Fang revisions

Stable bundled ID: `official-azure-fang`. Display name remains `Operation Azure Fang`.

## REV2 — incorporated 2026-11-10

Source: [Operation Azure Fang REV2 export](export-official-azure-fang-rev2.json), captured from the user's saved Battlefield scenario `local-b77f30474a1146ce8dd8b08ae5057a55`, local edit revision 1. This is the user's authoring revision, not a claim of a new publisher-issued rules revision.

- `03-12`: Ground Level becomes Height 1; add a blue Garrison.
- `04-11`, `04-12`, `04-13`: Ground Level becomes Height 1.
- Mission briefing, location, Jungle palette and all other terrain/token placements are unchanged.
- Objective numbers 1–4 are now explicit in the catalog, preserving the order already assigned by the loader.

The runtime catalog removes the authoring-only `REV2` name suffix and records `revision: REV2`. Existing matches linked to the stable official ID load the revised board. The custom scenario and current match in the user's save database were read only and were not modified.

## 1.0 — previous bundled source

Retained unchanged: [original export](export-official-azure-fang.json). The pre-REV2 catalog snapshot is retained locally in `.local-authoring/scenario-revisions/azure-fang-pre-rev2-catalog.json`.
