# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Point of Sale',
    'version': '1.0.1',
    'category': 'Point Of Sale',
    'sequence': 20,
    'summary': 'Register sales in shops and restaurants with a touchscreen interface',
    'description': "",
    'depends': ['stock_account', 'barcodes', 'web_editor', 'digest'],
    'data': [
        'security/point_of_sale_security.xml',
        'security/ir.model.access.csv',
        'data/default_barcode_patterns.xml',
        'data/digest_data.xml',
        'wizard/pos_box.xml',
        'wizard/pos_details.xml',
        'wizard/pos_discount.xml',
        'wizard/pos_open_statement.xml',
        'wizard/pos_payment.xml',
        'views/pos_templates.xml',
        'views/point_of_sale_template.xml',
        'views/point_of_sale_report.xml',
        'views/point_of_sale_view.xml',
        'views/pos_order_view.xml',
        'views/pos_category_view.xml',
        'views/product_view.xml',
        'views/account_journal_view.xml',
        'views/pos_config_view.xml',
        'views/pos_session_view.xml',
        'views/point_of_sale_sequence.xml',
        'views/point_of_sale.xml',
        'data/point_of_sale_data.xml',
        'views/pos_order_report_view.xml',
        'views/account_statement_view.xml',
        'views/account_statement_report.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/digest_views.xml',
        'views/res_partner_view.xml',
        'views/report_statement.xml',
        'views/report_userlabel.xml',
        'views/report_saledetails.xml',
        'views/point_of_sale_dashboard.xml',
    ],
    'demo': [
        'data/point_of_sale_demo.xml',
    ],
    'installable': True,
    'application': True,
    'qweb': ['static/src/xml/pos.xml'],
    'website': 'https://www.odoo.com/page/point-of-sale-shop',
}
