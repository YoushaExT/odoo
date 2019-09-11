import base64
import unittest

from odoo.tests.common import BaseCase
from odoo.tools.mimetypes import guess_mimetype

PNG = b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC'
GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="
BMP = b"""Qk1+AAAAAAAAAHoAAABsAAAAAQAAAAEAAAABABgAAAAAAAQAAAATCwAAEwsAAAAAAAAAAAAAQkdScwAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAD///8A"""
JPG = """/9j/4AAQSkZJRgABAQEASABIAAD//gATQ3JlYXRlZCB3aXRoIEdJTVD/2wBDAP
//////////////////////////////////////////////////////////////////////////////////////2wBDAf///////
///////////////////////////////////////////////////////////////////////////////wgARCAABAAEDAREAAhEB
AxEB/8QAFAABAAAAAAAAAAAAAAAAAAAAAv/EABQBAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhADEAAAAUf/xAAUEAEAAAAAAAA
AAAAAAAAAAAAA/9oACAEBAAEFAn//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AX//xAAUEQEAAAAAAAAAAAAAAAAAAA
AA/9oACAECAQE/AX//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/An//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBA
AE/IX//2gAMAwEAAgADAAAAEB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EH//xAAUEQEAAAAAAAAAAAAAAAAAAAAA
/9oACAECAQE/EH//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EH//2Q=="""
SVG = b"""PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iaXNvLTg4NTktMSI/PjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMjAwMDExMDIvL0VOIlxuICJodHRwOi8vd3d3LnczLm9yZy9UUi8yMDAwL0NSLVNWRy0yMDAwMTEwMi9EVEQvc3ZnLTIwMDAxMTAyLmR0ZCI+PHN2ZyB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSg1MCw1MCkiPjxyZWN0IHg9IjAiIHk9IjAiIHdpZHRoPSIxNTAiIGhlaWdodD0iNTAiIHN0eWxlPSJmaWxsOnJlZDsiIC8+PC9nPjwvc3ZnPg=="""


class test_guess_mimetype(BaseCase):

    def test_default_mimetype_empty(self):
        mimetype = guess_mimetype(b'')
        # odoo implementation returns application/octet-stream by default
        # if available, python-magic returns application/x-empty
        self.assertIn(mimetype, ('application/octet-stream', 'application/x-empty'))

    def test_default_mimetype(self):
        mimetype = guess_mimetype(b'', default='test')
        # if available, python-magic returns application/x-empty
        self.assertIn(mimetype, ('test', 'application/x-empty'))

    def test_mimetype_octet_stream(self):
        mimetype = guess_mimetype(b'\0')
        self.assertEqual(mimetype, 'application/octet-stream')

    def test_mimetype_png(self):
        content = base64.b64decode(PNG)
        mimetype = guess_mimetype(content, default='test')
        self.assertEqual(mimetype, 'image/png')

    def test_mimetype_bmp(self):
        content = base64.b64decode(BMP)
        mimetype = guess_mimetype(content, default='test')
        # mimetype should match image/bmp, image/x-ms-bmp, ...
        self.assertRegex(mimetype, r'image/.*\bbmp')

    def test_mimetype_jpg(self):
        content = base64.b64decode(JPG)
        mimetype = guess_mimetype(content, default='test')
        self.assertEqual(mimetype, 'image/jpeg')

    def test_mimetype_gif(self):
        content = base64.b64decode(GIF)
        mimetype = guess_mimetype(content, default='test')
        self.assertEqual(mimetype, 'image/gif')

    def test_mimetype_svg(self):
        content = base64.b64decode(SVG)
        mimetype = guess_mimetype(content, default='test')
        self.assertTrue(mimetype.startswith('image/svg'))
        # Tests that whitespace padded SVG are not detected as SVG
        mimetype = guess_mimetype(b"   " + content, default='test')
        self.assertNotIn("svg", mimetype)



if __name__ == '__main__':
    unittest.main()
