{
    'name': 'estate',
    'depends': ['base', 'web'],
    'data': [
        'views/estate_property_views.xml',
        'views/estate_property_type_views.xml',
        'views/estate_menus.xml',
        'security/ir.model.access.csv'
    ],
    'assets': {
        'web.assets_backend': [
            'estate/static/src/css/state_styling.scss',
        ]
    },
    'application': True
}
