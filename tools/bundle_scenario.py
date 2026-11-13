"""Add a tested Battlefield export to the bundled scenario catalog."""
import argparse
import json
import re
from pathlib import Path

from companion.asset_pipeline import pipeline_lock
from companion.card_display import atomic_write
from companion.catalog import ASSETS
from companion.scenarios import load_scenarios, parse_scenario_export
from companion.storage import LOCAL_SCENARIO_PREFIX


def bundle_scenario(root, export, scenario_id, revision):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", scenario_id):
        raise ValueError("Use an ID of up to 80 letters, numbers, underscores, or hyphens, starting with a letter or number.")
    if scenario_id.casefold().startswith(LOCAL_SCENARIO_PREFIX):
        raise ValueError("IDs beginning with local- are reserved for player scenarios.")
    if not revision.strip():
        raise ValueError("Enter a publication date or revision.")

    original = export.read_bytes()
    scenario = parse_scenario_export(original)
    source = Path("authoring/scenarios") / f"export-{scenario_id}.json"
    record = {"id": scenario_id, "source": source.as_posix(), "revision": revision.strip(), **scenario}
    with pipeline_lock(root):
        catalog = load_scenarios(root)
        if any(entry["id"].casefold() == scenario_id.casefold() for entry in catalog):
            raise ValueError(f"Scenario ID {scenario_id!r} is already bundled.")
        archived = root / source
        if archived.exists() and archived.read_bytes() != original:
            raise ValueError(f"A different export is already archived at {source.as_posix()}.")
        contents = (json.dumps([*catalog, record], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        atomic_write(archived, original)
        atomic_write(root / "scenarios.json", contents)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="JSON file exported from Battlefield.")
    parser.add_argument("--id", required=True, help="Stable official scenario ID.")
    parser.add_argument("--revision", required=True, help="Publication date or revision.")
    parser.add_argument("--root", type=Path, default=ASSETS, help="Checkout containing scenarios.json.")
    args = parser.parse_args()
    try:
        record = bundle_scenario(args.root.resolve(), args.export, args.id, args.revision)
    except (OSError, ValueError, RecursionError) as error:
        parser.error(str(error))
    print(f'Added {record["name"]} ({record["id"]}) to scenarios.json.')


if __name__ == "__main__":
    main()
