# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Events Online',
    'category': 'Marketing/Events',
    'sequence': 1001,
    'version': '1.0',
    'summary': 'Bridge module to support Online Events',
    'website': 'https://www.odoo.com/page/events',
    'description': "",
    'depends': [
        'website_event'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/event_security.xml',
        'views/assets.xml',
        'views/event_event_views.xml',
        'views/event_registration_views.xml',
        'views/event_tag_views.xml',
        'views/event_type_views.xml',
        'views/website_visitor_views.xml',
        'views/event_templates_event.xml',
        'views/event_templates_widgets.xml',
    ],
    'demo': [
        'data/website_visitor_demo.xml',
        'data/event_demo.xml',
        'data/event_registration_demo.xml',
        'data/event_tag_demo.xml',
    ],
    'application': False,
    'installable': True,
}
