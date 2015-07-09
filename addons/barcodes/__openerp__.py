{
    'name': 'Barcodes',
    'version': '2.0',
    'category': 'Hidden/Dependency',
    'summary': 'Barcodes Scanning and Parsing',
    'description': """
This module adds support for barcode scanning and parsing.

Scanning
--------
Use an USB scanner (that mimics keyboard inputs) in order to work with barcodes in Odoo.
The scanner must be configured to use no prefix and a carriage return or tab as suffix.
The delay between each character input must be less than or equal to 50 milliseconds.
This is how most barcode scanners will work out of the box.
However, make sure the scanner uses the same keyboard layout as the device it's plugged in.

Parsing
-------
The barcodes are interpreted using the rules defined by a nomenclature.
It provides the following features:
- Patterns to identify barcodes containing a numerical value (e.g. weight, price)
- Definition of barcode aliases that allow to identify the same product with different barcodes
- Support for encodings EAN-13, EAN-8 and UPC-A
""",
    'author': 'Odoo SA',
    'depends': ['web'],
    'data': [
        'data/barcodes_data.xml',
        'barcodes_view.xml',
        'security/ir.model.access.csv',
        'views/templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
