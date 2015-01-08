# -*- coding: utf-8 -*-
{
    'name': 'Customer Rating',
    'version': '1.0',
    'category': 'Tools',
    'description': """
This module allows a customer to give rating.
""",
    'author': 'Odoo SA',
    'website': 'http://odoo.com',
    'depends': [
        'mail',
    ],
    'data': [
        'views/rating_view.xml',
        'views/rating_template.xml',
        'security/ir.model.access.csv'
     ],
    'installable': True,
    'auto_install': False,
}
