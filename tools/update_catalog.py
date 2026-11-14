"""Offline, append-only public shortlist updater (Python standard library only)."""
import argparse
from html import escape
import json
from pathlib import Path
import re
import os
import tempfile
import fcntl
import unicodedata


STREETS = ('LAS BRISAS', 'LAS GAVIOTAS', 'LOS CORMORANES', 'LOS PELICANOS',
           'LOS PIQUEROS', 'LOS QUELTEHUES', 'LOS MIRLOS', 'LAS GARZAS',
           'LAS LOICAS', 'LAS TORCAZAS', 'LAS PERDICES', 'LAS TORTOLAS',
           'LOS FLAMENCOS', 'LAS GRULLAS', 'LAS BANDURRIAS', 'LOS PETRELES',
           'LOS CAUQUENES', 'LOS ALBATROS')


def matching_address(address):
    """Fold case/accents for comparisons only; never change stored/public text."""
    return ''.join(c for c in unicodedata.normalize('NFD', address)
                   if not unicodedata.combining(c)).upper()


def write_pair(contents):
    """Stage both files first; replace whole files and roll back ordinary I/O failures.

    A process/host crash between replacements is recovered by replaying the batch.
    """
    staged = []
    replaced = []
    previous = {}
    try:
        for path, content in contents:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f'expected existing regular file: {path}')
            previous[path] = path.read_bytes()
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.update-', delete=False) as stream:
                staged.append((path, Path(stream.name)))
                stream.write(content.encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(stream.name, 0o644)
        for path, temporary in staged:
            os.replace(temporary, path)
            replaced.append(path)
    except OSError:
        for path in replaced:
            path.write_bytes(previous[path])
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)


def render(records, template):
    cards = []
    used = set()
    for record in records:
        address = record['address']
        parts = address.lower().split()
        anchor = parts[1] + ('-' + parts[2] if parts[2].isdigit() else '')
        if anchor in used:
            anchor += '-' + str(len(cards) + 1)
        used.add(anchor)
        maps = (f'<a class="maps" href="{escape(record["maps_url"], quote=True)}">Google Maps</a>'
                if record['maps_url'] else '<p>Google Maps no disponible en la ficha</p>')
        cards.append(f'      <article aria-labelledby="{anchor}">\n'
                     f'        <h2 id="{anchor}">{escape(address)}</h2>\n'
                     f'        {maps}\n'
                     f'        <a class="source" href="{escape(record["source_url"], quote=True)}">Ficha original de MisRemates</a>\n'
                     '      </article>')
    return template.replace('{{count}}', str(len(records))).replace('{{cards}}', '\n'.join(cards))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['add'])
    parser.add_argument('batch', type=Path)
    parser.add_argument('--commune-verified', action='store_true',
                        help='attest Santo Domingo was checked in the readable body of every incoming listing')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        lock_dir = args.root / '.local'
        lock_dir.mkdir(exist_ok=True)
        with (lock_dir / 'update.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            update(args, parser)
    except (OSError, ValueError) as error:
        parser.error(str(error))


def update(args, parser):
    path = args.root / 'data/catalog.json'
    records = json.loads(path.read_text(encoding='utf-8'))
    incoming = json.loads(args.batch.read_text(encoding='utf-8'))
    if not isinstance(records, list) or not isinstance(incoming, list):
        parser.error('expected JSON array')
    if incoming and not args.commune_verified:
        parser.error('--commune-verified required: check Santo Domingo in each listing body, not just its slug')
    original_count = len(records)
    by_id = {}
    for record in records + incoming:
        if (not isinstance(record, dict)
                or set(record) != {'id', 'address', 'maps_url', 'source_url'}
                or not isinstance(record['id'], str)
                or not re.fullmatch(r'[1-9][0-9]*', record['id'])
                or not isinstance(record['address'], str)
                or not isinstance(record['source_url'], str)
                or not (record['maps_url'] is None or isinstance(record['maps_url'], str))):
            parser.error('invalid minimal schema')
        if (not re.fullmatch(r'https://www\.misremates\.cl/remate/[a-z0-9]+(?:-[a-z0-9]+)*-' + record['id'], record['source_url'])
                or (record['maps_url'] is not None and not re.fullmatch(
                    r'https://www\.google\.com/maps/search/\?api=1&query=-?[0-9]+(?:\.[0-9]+)?(?:%2C|,)-?[0-9]+(?:\.[0-9]+)?', record['maps_url']))):
            parser.error('URL not allowed')
        address = matching_address(record['address'])
        # A complete street plus address-only components, never free prose.
        identifier = r'(?:[0-9]+[A-Z]?(?:-[A-Z0-9]+)?|[A-Z](?:[ -][0-9]+)?)'
        label = r'(?:MZ|MZA|MANZANA|LT|LOTE|DPC|DP|DEPTO|DEPARTAMENTO|UNIDAD|BD|BODEGA|N[º°]?)\.?'
        component = label + ' ' + identifier
        address_pattern = ('(?:' + '|'.join(STREETS) + ') '
                           r'(?:[1-9][0-9]*(?:-[A-Z0-9]+| [A-Z])?|S/?N|'
                           + component + ')(?:,? ' + component + ')*')
        slug_address = re.sub(r'[^a-z0-9]+', '-', address.lower()).strip('-')
        suffix = '-' + slug_address + '-santo-domingo-' + record['id']
        if not re.fullmatch(address_pattern, address) or not record['source_url'].endswith(suffix):
            parser.error('address out of scope or not matched by Santo Domingo source URL')
        key = record['id']
        if key in by_id and by_id[key] != record:
            parser.error(f'conflicting id: {key}')
        by_id[key] = record
    records = list(by_id.values())
    output = render(records, (args.root / 'tools/index.template.html').read_text(encoding='utf-8'))
    write_pair([(path, json.dumps(records, ensure_ascii=False, indent=2) + '\n'),
                (args.root / 'docs/index.html', output)])
    print(f'added={len(records) - original_count} total={len(records)}')


if __name__ == '__main__':
    main()
