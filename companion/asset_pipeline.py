"""Discover authoring inputs and prepare an allowlisted, reproducible runtime bundle."""
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from PIL import Image

from Video import ANIMATION_FILES

from .attacks import load_attacks
from .card_display import (build_display_cache, display_cache_path, read_manifest,
                           source_digest, write_manifest)
from .catalog import (TACTICS_CARDS, UNIT_CARDS, card_source_directory, load_catalog,
                      load_remote_weapons, load_tactics, published_number, unique_keys)
from .dice import DICE_FILES
from .scenarios import SPECIAL_TERRAIN, load_scenarios

CARD_SETS = (UNIT_CARDS, TACTICS_CARDS)
BATTLEFIELD_ART = {artwork: (256, 256) for _, artwork in SPECIAL_TERRAIN.values()}
BATTLEFIELD_ART['objective'] = (720, 616)
BATTLEFIELD_RENDER_DIR = Path('.build/battlefield-renders')
BATTLEFIELD_RENDERER = Path('tools/render_battlefield_tokens.cjs')
STATIC_FILES = (
    'scenarios.json',
    'attacks.json', 'Dice/physics.js',
    *(f'Dice/licenses/{name}.txt' for name in ('V8', 'Strongtalk', 'fdlibm', 'ICU')),
    'LICENSE',
    'Fonts/ChakraPetch-Bold.ttf', 'Fonts/SairaStencilOne-Regular.ttf',
    'Fonts/OFL-Chakra-Petch.txt', 'Fonts/OFL-Saira-Stencil-One.txt',
    'Images/gundam-assemble-hangar.png', 'Images/gundam-assemble-hangar.ico',
    'Images/speaker-grille.png', 'Images/sortie-warning.png', 'Images/sortie-chevrons.png',
    'Images/sortie-arrow.png', 'Images/pixel-decal.png', 'Images/score-warning.png', 'Images/hangar-chevrons.png',
    *(f'Images/hangar-{name}.cur' for name in ('pointer', 'hand', 'drag', 'text', 'resize')),
    *(f'Images/Navigation/{name}.png' for name in ('layers', 'sliders-vertical', 'map', 'gallery-vertical-end')),
    'Images/Navigation/LICENSE-Feather.txt', 'Images/Navigation/LICENSE-Lucide.txt',
    *(f'Video/{name}' for name in ANIMATION_FILES),
    *(f'Tokens/rendered/{name}.png' for name in ('red-deployment-base', 'blue-deployment-base',
      'red-garrison', 'blue-garrison', 'generic-upgrade')),
    *(f'Tokens/rendered/{name}.png' for name in ('blue-objective', 'red-objective', 'disarmed-status',
      'fractured-status', 'slow-status', 'hp', 'energy', 'shields-upgrade', 'speed-upgrade', 'strength-upgrade')),
)


def index(root, name):
    records = json.loads((root / name).read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
    if not isinstance(records, dict):
        raise ValueError(f'{name} must be keyed by printed card number')
    return records


def discover_cards(root):
    """Report missing metadata/masters instead of inventing card rules or overwriting templates."""
    units, remote, tactics = (index(root, name) for name in ('catalog.json', 'remote_weapons.json', 'tactics.json'))
    if units.keys() & remote.keys():
        raise ValueError('Unit and Remote Weapon System card numbers overlap')
    records = []
    for folder, metadata in ((UNIT_CARDS, units | remote), (TACTICS_CARDS, tactics)):
        source = card_source_directory(root, folder)
        originals = {}
        expected_letter = 'U' if folder == UNIT_CARDS else 'T'
        for path in sorted(source.glob('*')):
            if path.suffix.lower() != '.webp':
                continue
            number = published_number(path.name)
            if not number or not number.split('-')[-1].startswith(expected_letter):
                raise ValueError(f'Unrecognized card source: {path.relative_to(root)}')
            if number in originals:
                raise ValueError(f'Duplicate published image for {number}')
            originals[number] = path
        masters = {path.stem: path for path in (source / 'SVG').glob('*.svg')}
        for path in (*originals.values(), *masters.values()):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'Authoring input escapes checkout: {path.relative_to(root)}')
        for number in sorted(originals.keys() | metadata.keys() | masters.keys()):
            missing = []
            if number not in originals:
                missing.append('original WEBP')
            if number not in metadata or (folder == TACTICS_CARDS and
                    (not isinstance(metadata[number], str) or not metadata[number].strip())):
                missing.append('printed metadata')
            if number not in masters:
                missing.append('editable SVG master (copy matching layout and verify all printed text/stats)')
            if number in originals and number in metadata and folder == UNIT_CARDS:
                if not isinstance(metadata[number], dict) or metadata[number].get('image') != originals[number].name:
                    missing.append('metadata image must match the unique original filename')
            records.append({'folder': folder, 'number': number, 'missing': missing,
                            'original': originals[number].relative_to(root).as_posix() if number in originals else None,
                            'master': masters[number].relative_to(root).as_posix() if number in masters else None})
    return records


def render_fingerprint(root, card, toolchain=None):
    from hashlib import sha256
    return sha256(json.dumps([source_digest(root / card[key]) for key in ('original', 'master')] +
                             [source_digest(root / 'tools/render_cards.cjs'),
                              source_digest(root / 'tools/package-lock.json'), toolchain]).encode()).hexdigest()


def needed_renders(root, cards, toolchain=None):
    result = []
    for card in cards:
        if card['missing']:
            continue
        output = root / '.build/card-renders' / card['folder']
        stamp = read_manifest(output).get(card['number'], {})
        png = output / 'PNG' / f"{card['number']}.png"
        if (stamp.get('fingerprint') != render_fingerprint(root, card, toolchain) or
                not stamp.get('sha256') or stamp['sha256'] != source_digest(png)):
            result.append(card)
    return result


@contextmanager
def pipeline_lock(root):
    path = root / '.build/prepare.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Asset preparation is already running in this checkout') from error
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def publish_assets(root, cards, *, battlefield_art=False):
    """Publish only explicit runtime files and currently referenced derivatives."""
    output = root / '.build/published'
    stage = root / '.build' / f'.publish-{uuid4().hex}'
    stage.mkdir(parents=True)
    try:
        paths = {name: root / name for name in (*STATIC_FILES, 'catalog.json', 'remote_weapons.json', 'tactics.json')}
        paths.update({name: root / source for name, source in DICE_FILES.items()})
        if battlefield_art:
            paths.update({f'Tokens/rendered/{name}.png': root / BATTLEFIELD_RENDER_DIR / f'{name}.png'
                          for name in BATTLEFIELD_ART})
        for card in cards:
            paths[f"{card['folder']}/{Path(card['original']).name}"] = root / card['original']
        for folder in CARD_SETS:
            cache = display_cache_path(root, folder)
            paths[f'{folder}/Display/sources.json'] = cache / 'sources.json'
            for record in read_manifest(cache).values():
                for variant in record['variants'].values():
                    paths[f"{folder}/Display/{variant['file']}"] = cache / variant['file']
        entries = {}
        for name, source in sorted(paths.items()):
            if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'Published input must stay inside checkout: {name}')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            entries[name] = {'sha256': source_digest(target), 'bytes': target.stat().st_size}
        write_manifest(stage / 'assets.json', {'version': 1, 'files': entries})
        if output.is_symlink():
            raise ValueError('Published output may not be a symlink')
        if output.exists():
            if not (output / 'assets.json').is_file():
                raise ValueError('Refusing to replace an unrecognized published directory')
            current = json.loads((output / 'assets.json').read_text())
            actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
            if (current == {'version': 1, 'files': entries} and actual == set(entries) | {'assets.json'}
                    and all(source_digest(output / name) == entry['sha256'] for name, entry in entries.items())):
                return output
            backup = output.with_name(f'.old-publish-{uuid4().hex}')
            output.rename(backup)
            try:
                stage.rename(output)
            except BaseException:
                backup.rename(output)
                raise
            shutil.rmtree(backup)
        else:
            stage.rename(output)
        return output
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def battlefield_render_state(root, toolchain):
    inputs = {}
    for relative in (BATTLEFIELD_RENDERER, *(Path('Tokens') / f'{name}.svg' for name in BATTLEFIELD_ART)):
        path = root / relative
        digest = source_digest(path) if path.resolve().is_relative_to(root) else None
        if digest is None:
            raise ValueError(f'Missing or invalid Battlefield render source: {relative.as_posix()}')
        inputs[relative.as_posix()] = digest
    return {'inputs': inputs, 'toolchain': toolchain,
            'outputs': {name: source_digest(root / BATTLEFIELD_RENDER_DIR / f'{name}.png')
                        for name in BATTLEFIELD_ART}}


def prepare_assets(root, *, check=False):
    root = root.resolve()
    with pipeline_lock(root):
        cards = discover_cards(root)
        pending = [card for card in cards if card['missing']]
        write_manifest(root / '.build/onboarding.json', {'pending': pending})
        if pending:
            raise ValueError(f'{len(pending)} cards need onboarding; see .build/onboarding.json')
        # Validate gameplay metadata before rendering or publishing anything.
        units = load_catalog(root)
        load_attacks(units, root)
        remote = load_remote_weapons(units, root)
        tactics = load_tactics(root)
        load_scenarios(root)
        toolchain = json.loads(subprocess.check_output(
            ['node', str(root / 'tools/render_cards.cjs'), '--version'], text=True))
        dirty = needed_renders(root, cards, toolchain)
        battlefield_cache = root / BATTLEFIELD_RENDER_DIR
        battlefield_state = battlefield_render_state(root, toolchain)
        dirty_battlefield = (not all(battlefield_state['outputs'].values())
                             or battlefield_state != read_manifest(battlefield_cache))
        if check:
            return {'cards': len(cards), 'render_pending': [card['number'] for card in dirty] +
                    (list(BATTLEFIELD_ART) if dirty_battlefield else [])}
        environment = dict(os.environ, CARD_RENDER_ROOT=str(root))
        if dirty_battlefield:
            subprocess.run(['node', str(root / BATTLEFIELD_RENDERER), '--battlefield'], check=True, env=environment)
            for name, size in BATTLEFIELD_ART.items():
                with Image.open(battlefield_cache / f'{name}.png') as image:
                    if (image.size != size or image.mode != 'RGBA'
                            or not image.getchannel('A').getbbox() or image.getpixel((0, 0))[3]):
                        raise ValueError(f'Invalid transparent Battlefield render: {name}')
            rendered = battlefield_render_state(root, toolchain)
            if rendered['inputs'] != battlefield_state['inputs']:
                raise ValueError('Battlefield artwork changed during rendering. Run preparation again.')
            write_manifest(battlefield_cache / 'sources.json', rendered)
        for folder, kind in ((UNIT_CARDS, 'unit'), (TACTICS_CARDS, 'tactics')):
            selected = [card for card in dirty if card['folder'] == folder]
            if selected:
                # No shell interpolation; an explicit root also supports isolated fixture runs.
                subprocess.run(['node', str(root / 'tools/render_cards.cjs'), kind,
                                *(card['number'] for card in selected)], check=True, env=environment)
                output = root / '.build/card-renders' / folder
                stamps = read_manifest(output)
                for card in selected:
                    stamps[card['number']] = {'fingerprint': render_fingerprint(root, card, toolchain),
                        'sha256': source_digest(output / 'PNG' / f"{card['number']}.png")}
                write_manifest(output / 'sources.json', stamps)
        build_display_cache((*units.values(), *remote.values()), root, folder=UNIT_CARDS, preview_only=remote)
        build_display_cache(tactics.values(), root, folder=TACTICS_CARDS)
        output = publish_assets(root, cards, battlefield_art=True)
        return {'cards': len(cards), 'rendered': len(dirty),
                'battlefield_rendered': len(BATTLEFIELD_ART) if dirty_battlefield else 0, 'published': str(output)}
