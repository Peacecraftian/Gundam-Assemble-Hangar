"""python -m tools.prepare_assets [--check | --watch --interval 30]"""
import argparse
import json
import subprocess
import time
from pathlib import Path

from companion.asset_pipeline import prepare_assets
from companion.catalog import ASSETS


def main():
    parser = argparse.ArgumentParser(description='Discover cards, report onboarding needs, and prepare runtime assets.')
    parser.add_argument('--root', type=Path, default=ASSETS)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='Check metadata and report pending SVG renders without rendering.')
    modes.add_argument('--watch', action='store_true', help='Rescan local repository contents periodically; does not fetch Git.')
    parser.add_argument('--interval', type=float, default=30)
    options = parser.parse_args()
    if options.interval < 1:
        parser.error('--interval must be at least one second')
    try:
        while True:
            try:
                result = prepare_assets(options.root, check=options.check)
                print(json.dumps(result, sort_keys=True), flush=True)
                status = int(bool(result.get('render_pending')))
            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                print(str(error), flush=True)
                status = 1
            if not options.watch:
                return status
            time.sleep(options.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
