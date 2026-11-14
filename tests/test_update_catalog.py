"""Exercise the real updater in disposable copies; never mutate the live catalogue."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_site import Document, EXPECTED, ROOT


class UpdateCatalog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__', '.local'))
        self.batch = Path(self.temp.name) / 'batch.json'
        baseline = [{'id': slug.rsplit('-', 1)[-1], 'address': address,
                     'maps_url': 'https://www.google.com/maps/search/?api=1&query=' + coordinates,
                     'source_url': 'https://www.misremates.cl/remate/' + slug}
                    for address, coordinates, slug in EXPECTED]
        (self.root / 'data/catalog.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + '\n')
        shutil.copyfile(ROOT / 'tests/fixtures/seven.html', self.root / 'docs/index.html')

    def run_batch(self, records):
        self.batch.write_text(json.dumps(records), encoding='utf-8')
        return subprocess.run([sys.executable, str(self.root / 'tools/update_catalog.py'),
                               'add', str(self.batch), '--commune-verified', '--root', str(self.root)],
                              text=True, capture_output=True)

    def catalogue(self):
        return json.loads((self.root / 'data/catalog.json').read_text())

    def assert_rejected(self, records, reason):
        before = [(self.root / name).read_bytes() for name in ('data/catalog.json', 'docs/index.html')]
        result = self.run_batch(records)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertEqual(before, [(self.root / name).read_bytes() for name in ('data/catalog.json', 'docs/index.html')])

    def test_accepts_all_authorized_streets_preserving_literal_addresses(self):
        import unicodedata
        streets = ('Las Brisas', 'Las Gaviotas', 'Los Cormoranes', 'Los Pelícanos',
                   'Los Piqueros', 'Los Queltehues', 'Los Mirlos', 'Las Garzas',
                   'Las Loicas', 'Las Torcazas', 'Las Perdices', 'Las Tórtolas',
                   'Los Flamencos', 'Las Grullas', 'Las Bandurrias', 'Los Pétreles',
                   'Los Cauquenes', 'Los Albatros')
        for street in streets:
            plain = ''.join(c for c in unicodedata.normalize('NFD', street)
                            if not unicodedata.combining(c))
            for spelling in dict.fromkeys((street, plain.upper(), plain.lower())):
                with self.subTest(address=spelling):
                    address = spelling + ' 200'
                    slug = plain.lower().replace(' ', '-') + '-200'
                    record = {'id': '999001', 'address': address, 'maps_url': None,
                              'source_url': f'https://www.misremates.cl/remate/casa-{slug}-santo-domingo-999001'}
                    # Restore the same baseline between independent literal variants.
                    records = self.catalogue()[:7]
                    (self.root / 'data/catalog.json').write_text(json.dumps(records))
                    result = self.run_batch([record])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.catalogue()[-1]['address'], address)
                    doc = Document((self.root / 'docs/index.html').read_text())
                    self.assertEqual(doc.cards[-1]['headings'], [address])

    def test_accepts_legible_address_suffixes_with_matching_slugs(self):
        suffixes = ('SN', 'S/N', 'SN LT 4', 'LT 4', 'Lote 4',
                    'MZ H LT 4', 'Manzana H Lote 4', '200-A', '200 A',
                    '200 Depto 32', '200 Depto. B 32', '200 Departamento 32',
                    '200 Unidad B-32', '200 DPC 24', '200 DP B 32 BD 6',
                    '200, Depto. 32', '200 Nº 32')
        import re
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                address = 'Las Gaviotas ' + suffix
                slug = re.sub(r'[^a-z0-9]+', '-', address.lower()).strip('-')
                record = {'id': '999001', 'address': address, 'maps_url': None,
                          'source_url': f'https://www.misremates.cl/remate/casa-{slug}-santo-domingo-999001'}
                (self.root / 'data/catalog.json').write_text(json.dumps(self.catalogue()[:7]))
                result = self.run_batch([record])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Document((self.root / 'docs/index.html').read_text()).cards[-1]['headings'], [address])

    def test_rejects_full_prefix_false_positives_even_with_matching_slug(self):
        valid = self.catalogue()[0]
        self.assertEqual(self.run_batch([valid]).returncode, 0)
        for address in ('LAS GAVIOTAS FALSAS 182', 'LAS GAVIOTASX 182',
                        'LAS BRISAS DEL MAR 182', 'LOS PELICANOS NORTE 182',
                        'LAS GAVIOTAS 182 ROL 123-4', 'LAS GAVIOTAS 182 DEUDA 300',
                        'LAS GAVIOTAS 182 CASA LINDA', 'LAS GAVIOTAS 182\n'):
            with self.subTest(address=address):
                source = 'https://www.misremates.cl/remate/casa-' + address.lower().strip().replace(' ', '-') + '-santo-domingo-142172'
                self.assert_rejected([dict(valid, address=address, source_url=source)], 'address out of scope')

    def test_requires_explicit_body_commune_verification_for_nonempty_batch(self):
        record = self.catalogue()[0]
        self.assertEqual(self.run_batch([record]).returncode, 0)
        before = [(self.root / name).read_bytes() for name in ('data/catalog.json', 'docs/index.html')]
        result = subprocess.run([sys.executable, str(self.root / 'tools/update_catalog.py'),
                                 'add', str(self.batch), '--root', str(self.root)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('commune-verified', result.stderr)
        self.assertEqual(before, [(self.root / name).read_bytes() for name in ('data/catalog.json', 'docs/index.html')])

    def test_rejects_nonminimal_schema(self):
        valid = self.catalogue()[0]
        for bad in (dict(valid, photo='https://example.org/a.jpg'),
                    {k: v for k, v in valid.items() if k != 'maps_url'},
                    dict(valid, id=142172), dict(valid, id=''), None):
            with self.subTest(record=bad):
                self.assert_rejected([bad], 'schema')
        for bad in ({}, 'text', None):
            self.assert_rejected(bad, 'JSON array')

    def test_rejects_urls_outside_exact_allowlist(self):
        valid = self.catalogue()[0]
        self.assertEqual(self.run_batch([valid]).returncode, 0)
        for field, urls in {
            'maps_url': ['http://www.google.com/maps/search/?api=1&query=1',
                         'https://www.google.com.evil.test/maps/search/?api=1&query=1',
                         'https://evil.test/', 'javascript:alert(1)',
                         'https://www.google.com@evil.test/maps/',
                         'https://www.google.com:443/maps/search/?api=1&query=1',
                         'https://www.google.com/url?q=https://evil.test/',
                         'https://www.google.com/maps/search/?api=1&query=1&next=https://evil.test/', ''],
            'source_url': ['https://misremates.cl.evil.test/remate/casa-santo-domingo-142172',
                           'https://www.misremates.cl/terminos',
                           valid['source_url'] + '?redirect=https://evil.test/',
                           valid['source_url'] + '#photo',
                           valid['source_url'].replace('142172', '999001')]
        }.items():
            for url in urls:
                with self.subTest(field=field, url=url):
                    self.assert_rejected([dict(valid, **{field: url})], 'URL not allowed')

    def test_rejects_addresses_outside_streets_or_santo_domingo(self):
        valid = self.catalogue()[0]
        for address in ('LAS GAVIOTAS FALSAS 182', 'AVENIDA CHILE 182',
                        'LAS GAVIOTAS 182 ROL 123-4', 'LAS GAVIOTAS 182 <img>',
                        'LAS GAVIOTAS 182\n', 'LAS GAVIOTAS', ''):
            with self.subTest(address=address):
                self.assert_rejected([dict(valid, address=address)], 'address out of scope')
        for source in (valid['source_url'].replace('santo-domingo', 'cartagena'),
                       valid['source_url'].replace('gaviotas-182', 'gaviotas-183')):
            self.assert_rejected([dict(valid, source_url=source)], 'address out of scope')

    def test_future_catalogue_passes_public_contract(self):
        record = dict(self.catalogue()[0], id='999001', address='LAS GAVIOTAS 200', maps_url=None,
                      source_url='https://www.misremates.cl/remate/casa-las-gaviotas-200-santo-domingo-999001')
        self.assertEqual(self.run_batch([record]).returncode, 0)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                 '-p', 'test_site.py', '-v'], cwd=self.root, capture_output=True, text=True,
                                env={k: v for k, v in os.environ.items() if k != 'SITE_URL'})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_output_preparation_failure_leaves_catalogue_untouched(self):
        before = (self.root / 'data/catalog.json').read_bytes()
        target = self.root / 'docs/index.html'
        target.unlink()
        target.mkdir()
        record = dict(self.catalogue()[0], id='999001',
                      source_url='https://www.misremates.cl/remate/casa-las-gaviotas-182-santo-domingo-999001')
        result = self.run_batch([record])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'data/catalog.json').read_bytes(), before)

    def test_command_waits_for_repository_update_lock(self):
        import fcntl
        lock_path = self.root / '.local/update.lock'
        lock_path.parent.mkdir(exist_ok=True)
        self.batch.write_text('[]')
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen([sys.executable, str(self.root / 'tools/update_catalog.py'),
                                        'add', str(self.batch), '--root', str(self.root)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=0.4)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn('added=0', stdout)

    def test_conflicting_id_rejects_entire_batch(self):
        valid = dict(self.catalogue()[0], id='999001',
                     source_url='https://www.misremates.cl/remate/casa-las-gaviotas-182-santo-domingo-999001')
        conflict = dict(self.catalogue()[0], maps_url=None)
        self.assert_rejected([valid, conflict], 'conflicting id')

    def test_adds_null_maps_once_without_exposing_private_fields(self):
        record = dict(self.catalogue()[0], id='999001', address='LAS GAVIOTAS 200',
                      maps_url=None,
                      source_url='https://www.misremates.cl/remate/casa-las-gaviotas-200-santo-domingo-999001')
        for added in (1, 0):
            result = self.run_batch([record, record])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'added={added}', result.stdout)
            self.assertEqual(len(self.catalogue()), 8)
        text = (self.root / 'docs/index.html').read_text()
        doc = Document(text)
        self.assertEqual(doc.cards[-1]['text'], [record['address'],
                         'Google Maps no disponible en la ficha', 'Ficha original de MisRemates'])
        self.assertEqual(doc.cards[-1]['links'], [{'href': record['source_url'],
                                                  'text': 'Ficha original de MisRemates'}])
        self.assertNotIn('999001', ' '.join(doc.visible))
        self.assertFalse({'img', 'picture', 'script', 'iframe'} & {tag for tag, _ in doc.tags})
        self.assertEqual(doc.stack, [])

    def test_replaying_current_seven_preserves_exact_html(self):
        original = (self.root / 'docs/index.html').read_bytes()
        records = [{'id': slug.rsplit('-', 1)[-1], 'address': address,
                    'maps_url': 'https://www.google.com/maps/search/?api=1&query=' + coordinates,
                    'source_url': 'https://www.misremates.cl/remate/' + slug}
                   for address, coordinates, slug in EXPECTED]
        result = self.run_batch(records)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.catalogue(), records)
        self.assertEqual((self.root / 'docs/index.html').read_bytes(), original)
        self.assertIn('added=0', result.stdout)


if __name__ == '__main__':
    unittest.main()
