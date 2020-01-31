# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Bootswatch Theme',
    'description': 'Bootswatch themes',
    'category': 'Website/Theme',
    'sequence': 900,
    'version': '1.0',
    'depends': ['website'],
    'data': [
        'views/theme_bootswatch_templates.xml',
    ],
    'images': [
        'static/description/bootswatch.png',
        'static/description/bootswatch_screenshot.jpg',
    ],
    'application': False,
}
