"""Contract checks for the deliberately minimal public directory."""
from html.parser import HTMLParser
from pathlib import Path
import os
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [
    ('LAS GAVIOTAS 182', '-33.692366%2C-71.636694', 'casa-las-gaviotas-182-santo-domingo-142172'),
    ('LAS TORCAZAS 52', '-33.701684%2C-71.641865', 'casa-las-torcazas-52-santo-domingo-142164'),
    ('LOS MIRLOS 53', '-33.695953%2C-71.646816', 'casa-los-mirlos-53-santo-domingo-141978'),
    ('LAS GAVIOTAS 399', '-33.699411%2C-71.630056', 'casa-las-gaviotas-399-santo-domingo-141981'),
    ('LOS ALBATROS 20 DPC 24', '-33.695683%2C-71.638062', 'departamento-los-albatros-20-dpc-24-santo-domingo-142171'),
    ('LOS ALBATROS 2 DP B 32 BD 6', '-33.695404%2C-71.639684', 'departamento-los-albatros-2-dp-b-32-bd-6-santo-domingo-141979'),
    ('LAS GARZAS MZ H LT 4', '-33.702795%2C-71.635413', 'terreno-sitio-las-garzas-mz-h-lt-4-santo-domingo-142170'),
]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.tags = []
        self.stack = []
        self.links = []
        self.visible = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == 'article':
            self.cards.append({'headings': [], 'links': [], 'text': []})
        if tag == 'a':
            link = {'href': attrs.get('href'), 'text': ''}
            self.links.append(link)
            if self.cards:
                self.cards[-1]['links'].append(link)
        if tag not in {'meta', 'link', 'br', 'hr', 'img', 'input'}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, f'Unbalanced HTML: {tag}'
        self.stack.pop()

    def handle_data(self, data):
        if not data.strip():
            return
        if not any(t in self.stack for t in ('style', 'script', 'head')):
            self.visible.append(data.strip())
        if 'article' in self.stack:
            self.cards[-1]['text'].append(data.strip())
        if 'article' in self.stack and self.stack[-1] == 'h2':
            self.cards[-1]['headings'].append(data.strip())
        if self.stack and self.stack[-1] == 'a':
            self.links[-1]['text'] += data.strip()


class SiteContract(unittest.TestCase):
    def test_catalogue_has_only_the_seven_authorized_address_link_pairs(self):
        url = os.environ.get('SITE_URL')
        path = ROOT / 'docs/index.html'
        self.assertTrue(url or path.exists(), 'The public index has not been implemented')
        text = urlopen(url, timeout=30).read().decode() if url else path.read_text()
        doc = Document(text)
        self.assertEqual(doc.stack, [])
        self.assertEqual(len(doc.cards), 7)
        self.assertEqual(len(doc.links), 14)
        for card, (address, coordinates, slug) in zip(doc.cards, EXPECTED):
            with self.subTest(address=address):
                self.assertEqual(card['headings'], [address])
                self.assertEqual(card['text'], [address, 'Google Maps', 'Ficha original de MisRemates'])
                self.assertEqual(card['links'], [
                    {'href': 'https://www.google.com/maps/search/?api=1&query=' + coordinates, 'text': 'Google Maps'},
                    {'href': 'https://www.misremates.cl/remate/' + slug, 'text': 'Ficha original de MisRemates'},
                ])
        self.assertNotIn('141980', text)
        self.assertFalse({'img', 'picture', 'video', 'iframe', 'script'} & {tag for tag, _ in doc.tags})
        visible = ' '.join(doc.visible)
        for _, _, slug in EXPECTED:
            self.assertNotIn(slug.rsplit('-', 1)[-1], visible)
        for term in ('precio', 'deuda', 'causa', 'mínimo', '2026', 'rol:'):
            self.assertNotIn(term, visible.lower())

    def test_accessible_responsive_directory_needs_no_external_assets(self):
        text = (ROOT / 'docs/index.html').read_text()
        doc = Document(text)
        self.assertIn(('html', {'lang': 'es'}), doc.tags)
        self.assertEqual(sum(tag == 'h1' for tag, _ in doc.tags), 1)
        self.assertIn(('meta', {'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}), doc.tags)
        ids = [attrs['id'] for _, attrs in doc.tags if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in doc.tags:
            for reference in attrs.get('aria-labelledby', '').split():
                self.assertIn(reference, ids)
        styles = [attrs['href'] for tag, attrs in doc.tags if tag == 'link' and attrs.get('rel') == 'stylesheet']
        self.assertEqual(styles, ['styles.css'], 'Missing responsive local stylesheet')
        css = (ROOT / 'docs/styles.css').read_text()
        self.assertIn('grid-template-columns:', css)
        self.assertIn(':focus-visible', css)
        self.assertIn('@media', css)
        self.assertNotIn('url(', css)
        self.assertNotIn('@import', css)
        self.assertIn('no reproduce detalles ni imágenes', text)


if __name__ == '__main__':
    unittest.main()
