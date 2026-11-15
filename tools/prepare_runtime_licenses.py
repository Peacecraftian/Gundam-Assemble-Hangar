"""Collect the installed Windows runtime's unmodified license notices for packaging."""
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


def distribution_notice(distribution, filename):
    package = importlib.metadata.distribution(distribution)
    candidates = [package.locate_file(path) for path in package.files or ()
                  if path.name == filename and 'licenses' in path.parts]
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one {distribution} license notice, found {len(candidates)}')
    return candidates[0], package.version


def prepare_runtime_licenses(destination):
    destination = Path(destination)
    python_notice = Path(sys.base_prefix) / 'LICENSE.txt'
    pillow_notice, pillow_version = distribution_notice('Pillow', 'LICENSE')
    packager_notice, packager_version = distribution_notice('PyInstaller', 'COPYING.txt')
    sources = {
        'Python-LICENSE.txt': (python_notice, 'Python', sys.version.split()[0]),
        'Pillow-LICENSE.txt': (pillow_notice, 'Pillow', pillow_version),
        'PyInstaller-COPYING.txt': (packager_notice, 'PyInstaller', packager_version),
    }
    # Read everything before writing; a missing upstream notice must fail the build.
    notices = {name: path.read_bytes() for name, (path, _, _) in sources.items()}
    if any(len(contents) < 200 for contents in notices.values()):
        raise RuntimeError('A runtime license notice is unexpectedly empty or truncated')
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, contents in notices.items():
        (destination / name).write_bytes(contents)
        _, component, version = sources[name]
        manifest[name] = {'component': component, 'version': version,
                          'sha256': hashlib.sha256(contents).hexdigest()}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (destination / 'README.txt').write_text(
        'Third-party runtime notices\n\n'
        'Python-LICENSE.txt: the installed Windows Python distribution and its bundled notices.\n'
        'Pillow-LICENSE.txt: Pillow and the image/font libraries covered by its wheel notices.\n'
        'PyInstaller-COPYING.txt: executable bootloader exception and runtime licensing terms.\n\n'
        'Original notice bytes are preserved. manifest.json records component versions and hashes;\n'
        'it contains no build-machine paths. These files do not replace upstream copyright notices.\n\n'
        'Additional packaged notices: ../Fonts/OFL-*.txt, ../Images/Navigation/LICENSE-*.txt,\n'
        '../Dice/LICENSE-Cannon-es.txt, ../Dice/licenses/, ../mini_racer-*.dist-info/licenses/,\n'
        'and ../_tk_data/license.terms. The original application source code license is ../LICENSE.\n'
        'See ../NOTICE.md for license scope, official game material ownership, and asset notices.\n'
        'Official game artwork and other third-party assets are not licensed by the application MIT license.\n',
        encoding='utf-8')
    return manifest


def verify_runtime_licenses(directory):
    directory = Path(directory)
    expected = Path(__file__).resolve().parents[1] / '.build' / 'runtime-licenses'
    for source in expected.iterdir():
        if source.is_file() and (directory / source.name).read_bytes() != source.read_bytes():
            raise RuntimeError(f'Packaged runtime notice mismatch: {source.name}')
    print('Packaged runtime license notices verified.')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--verify':
        verify_runtime_licenses(sys.argv[2])
        raise SystemExit(0)
    target = Path(__file__).resolve().parents[1] / '.build' / 'runtime-licenses'
    result = prepare_runtime_licenses(target)
    print(f'Prepared {len(result)} runtime license notices.')
