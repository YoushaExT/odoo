{
    'name': 'eCommerce',
    'category': 'Website',
    'sequence': 55,
    'summary': 'Sell your products online',
    'website': 'https://www.odoo.com/page/e-commerce',
    'version': '1.0',
    'description': "",
    'depends': ['website', 'sale', 'website_payment', 'website_mail', 'website_form', 'website_rating', 'digest'],
    'data': [
        'security/ir.model.access.csv',
        'security/website_sale.xml',
        'data/data.xml',
        'data/mail_template_data.xml',
        'data/digest_data.xml',
        'views/product_views.xml',
        'views/account_views.xml',
        'views/onboarding_views.xml',
        'views/sale_report_views.xml',
        'views/sale_order_views.xml',
        'views/crm_team_views.xml',
        'views/templates.xml',
        'views/snippets.xml',
        'views/res_config_settings_views.xml',
        'views/digest_views.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': True,
}
