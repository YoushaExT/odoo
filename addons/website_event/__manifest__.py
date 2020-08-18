# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Events',
    'version': '1.1',
    'category': 'Marketing/Events',
    'sequence': 140,
    'summary': 'Publish events, sell tickets',
    'website': 'https://www.odoo.com/page/events',
    'description': "",
    'depends': [
        'event',
        'website',
        'website_partner',
        'website_mail',
    ],
    'data': [
        'data/event_data.xml',
        'views/assets.xml',
        'views/res_config_settings_views.xml',
        'views/event_snippets.xml',
        'views/event_templates_list.xml',
        'views/event_templates_page.xml',
        'views/event_templates_page_registration.xml',
        'views/event_templates_page_misc.xml',
        'views/event_templates_widgets.xml',
        'views/website_templates.xml',
        'views/event_event_views.xml',
        'views/event_type_views.xml',
        'views/website_event_menu_views.xml',
        'views/event_menus.xml',
        'security/ir.model.access.csv',
        'security/event_security.xml',
    ],
    'demo': [
        'data/res_partner_demo.xml',
        'data/event_demo.xml'
    ],
    'application': True,
}
