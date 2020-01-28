# -*- coding: utf-8 -*-

{
    'name': 'Questions on Events',
    'description': 'Questions on Events',
    'category': 'Marketing',
    'version': '1.0',
    'depends': ['website_event'],
    'data': [
        'views/event_views.xml',
        'views/event_templates.xml',
        'report/report_event_question_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'data/event_demo.xml',
        'data/event_registration_demo.xml',
    ],
    'installable': True,
}
