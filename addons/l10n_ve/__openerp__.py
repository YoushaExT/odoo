# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

#    Module programed and financed by:
#    Vauxoo, C.A. (<http://vauxoo.com>).
#    Our Community team mantain this module:
#    https://launchpad.net/~openerp-venezuela

{
    'name' : 'Venezuela - Accounting',
    'version': '1.0',
    'author': ['OpenERP SA', 'Vauxoo'],
    'category': 'Localization/Account Charts',
    'description':
"""
Chart of Account for Venezuela.
===============================

Venezuela doesn't have any chart of account by law, but the default
proposed in OpenERP should comply with some Accepted best practices in Venezuela, 
this plan comply with this practices.

This module has been tested as base for more of 1000 companies, because 
it is based in a mixtures of most common software in the Venezuelan 
market what will allow for sure to accountants feel them first steps with 
OpenERP more confortable.

This module doesn't pretend be the total localization for Venezuela, 
but it will help you to start really quickly with OpenERP in this country.

This module give you.
---------------------

- Basic taxes for Venezuela.
- Have basic data to run tests with community localization.
- Start a company from 0 if your needs are basic from an accounting PoV.

We recomend use of account_anglo_saxon if you want valued your 
stocks as Venezuela does with out invoices.

If you install this module, and select Custom chart a basic chart will be proposed, 
but you will need set manually account defaults for taxes.
""",
    'depends': ['account',
                'base_vat',
    ],
    'demo': [],
    'data': [
             'data/account_user_types.xml',
             'data/account_chart.xml',
             'data/account_tax.xml',
             'data/l10n_chart_ve_wizard.xml'
    ],
    'auto_install': False,
    'installable': False,
}
