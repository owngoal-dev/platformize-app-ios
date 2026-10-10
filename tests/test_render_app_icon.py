"""An Icon Composer icon comes out as three JPEGs that actool keeps as JPEG.

The point of the script is the second half: a plain icon set whose images
actool stores untouched. If a later actool re-encodes them losslessly, the
catalogue is back to megabytes and nothing else would say so.
"""
from pathlib import Path
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/render-app-icon.py'


def png(path, size=1024):
    """A vertical gradient, opaque, written without any imaging library."""
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        shade = 40 + y * 180 // size
        rows.extend(bytes((shade, 90, 255 - shade)) * size)

    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body))

    header = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header)
                     + chunk(b'IDAT', zlib.compress(bytes(rows), 9)) + chunk(b'IEND', b''))


def icon(folder):
    document = folder / 'AppIcon.icon'
    (document / 'Assets').mkdir(parents=True)
    png(document / 'Assets/layer.png')
    (document / 'icon.json').write_text(json.dumps({
        'fill': {'automatic-gradient': 'extended-srgb:0.00000,0.53333,1.00000,1.00000'},
        'groups': [{'layers': [{'image-name': 'layer.png', 'name': 'layer', 'glass': False}]}],
        'supported-platforms': {'squares': 'shared'},
    }, indent=2))
    return document


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('xcrun'), 'needs Xcode')
class RenderAppIconTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def render(self, *extra):
        catalog = self.root / 'Assets.xcassets'
        catalog.mkdir(exist_ok=True)
        (catalog / 'Contents.json').write_text('{"info":{"author":"xcode","version":1}}\n')
        iconset = catalog / 'AppIcon.appiconset'
        result = subprocess.run([sys.executable, str(SCRIPT), str(icon(self.root)), str(iconset), *extra],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return catalog, iconset

    def test_three_jpegs_listed_as_any_dark_and_tinted(self):
        _, iconset = self.render()
        images = json.loads((iconset / 'Contents.json').read_text())['images']
        self.assertEqual([i['filename'] for i in images], ['AppIcon.jpg', 'AppIcon-dark.jpg', 'AppIcon-tinted.jpg'])
        self.assertNotIn('appearances', images[0])
        self.assertEqual([i['appearances'][0]['value'] for i in images[1:]], ['dark', 'tinted'])
        for image in images:
            self.assertEqual((image['idiom'], image['platform'], image['size']), ('universal', 'ios', '1024x1024'))
            self.assertEqual((iconset / image['filename']).read_bytes()[:3], b'\xff\xd8\xff')

    def test_actool_keeps_them_as_jpeg(self):
        catalog, _ = self.render()
        out = self.root / 'out'
        out.mkdir()
        subprocess.run(['xcrun', 'actool', str(catalog), '--compile', str(out), '--platform', 'iphoneos',
                        '--minimum-deployment-target', '15.0', '--target-device', 'iphone',
                        '--target-device', 'ipad', '--app-icon', 'AppIcon',
                        '--output-partial-info-plist', str(self.root / 'p.plist'),
                        '--output-format', 'human-readable-text'], check=True, capture_output=True)
        info = json.loads(subprocess.run(['xcrun', 'assetutil', '--info', str(out / 'Assets.car')],
                                         check=True, capture_output=True, text=True).stdout)
        renditions = [r for r in info if r.get('Name') == 'AppIcon' and r.get('AssetType') == 'Icon Image']
        self.assertEqual(len(renditions), 6, renditions)  # three appearances, phone and pad
        self.assertEqual({r.get('Encoding') for r in renditions}, {'JPEG'})

    def test_a_second_run_replaces_the_images(self):
        _, iconset = self.render()
        (iconset / 'leftover.png').write_bytes(b'x')
        shutil.rmtree(self.root / 'AppIcon.icon')
        self.render()
        self.assertEqual(sorted(p.name for p in iconset.iterdir()),
                         ['AppIcon-dark.jpg', 'AppIcon-tinted.jpg', 'AppIcon.jpg', 'Contents.json'])

    def test_refuses_what_is_not_an_icon(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root), str(self.root / 'x.appiconset')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 64)


if __name__ == '__main__':
    unittest.main()
