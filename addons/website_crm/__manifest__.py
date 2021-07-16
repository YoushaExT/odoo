# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Contact Form',
    'category': 'Website/Website',
    'sequence': 54,
    'summary': 'Generate leads from a contact form',
    'version': '2.1',
    'description': """
Add capability to your website forms to generate leads or opportunities in the CRM app.
Forms has to be customized inside the *Website Builder* in order to generate leads.

This module includes contact phone and mobile numbers validation.""",
    'depends': ['website', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/website_crm_data.xml',
        'views/website_crm_lead_views.xml',
        'views/website_crm_templates.xml',
        'views/res_config_settings_views.xml',
        'views/website_visitor_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'assets': {
        'website.assets_editor': [
            'website_crm/static/src/**/*',
        ],
        'web.assets_tests': [
            'website_crm/static/tests/**/*',
        ],
    }
}
