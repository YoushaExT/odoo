# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Project',
    'version': '1.2',
    'website': 'https://www.odoo.com/app/project',
    'category': 'Services/Project',
    'sequence': 45,
    'summary': 'Organize and plan your projects',
    'depends': [
        'analytic',
        'base_setup',
        'mail',
        'portal',
        'rating',
        'resource',
        'web',
        'web_tour',
        'digest',
    ],
    'description': "",
    'data': [
        'security/project_security.xml',
        'security/ir.model.access.csv',
        'security/ir.model.access.xml',
        'data/digest_data.xml',
        'report/project_report_views.xml',
        'report/project_task_burndown_chart_report_views.xml',
        'views/analytic_views.xml',
        'views/digest_views.xml',
        'views/rating_views.xml',
        'views/project_update_views.xml',
        'views/project_update_templates.xml',
        'views/project_project_stage_views.xml',
        'wizard/project_share_wizard_views.xml',
        'views/project_collaborator_views.xml',
        'views/project_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/mail_activity_views.xml',
        'views/project_sharing_views.xml',
        'views/project_portal_templates.xml',
        'views/project_task_templates.xml',
        'views/project_sharing_templates.xml',
        'data/ir_cron_data.xml',
        'data/mail_data.xml',
        'data/mail_template_data.xml',
        'data/project_data.xml',
        'wizard/project_delete_wizard_views.xml',
        'wizard/project_task_type_delete_views.xml',
    ],
    'demo': ['data/project_demo.xml'],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'post_init_hook': '_project_post_init',
    'assets': {
        'web.assets_backend': [
            'project/static/src/css/project.css',
            'project/static/src/js/project_activity.js',
            'project/static/src/js/project_control_panel.js',
            'project/static/src/js/project_form.js',
            'project/static/src/js/project_graph.js',
            'project/static/src/js/project_kanban.js',
            'project/static/src/js/project_list.js',
            'project/static/src/js/project_pivot.js',
            'project/static/src/js/project_rating_reporting.js',
            'project/static/src/js/project_task_kanban_examples.js',
            'project/static/src/js/tours/project.js',
            'project/static/src/js/project_calendar.js',
            'project/static/src/js/burndown_chart/*',
            'project/static/src/js/right_panel/*',
            'project/static/src/js/update/*',
            'project/static/src/js/widgets/*',
            'project/static/src/scss/project_dashboard.scss',
            'project/static/src/scss/project_form.scss',
            'project/static/src/scss/project_rightpanel.scss',
            'project/static/src/scss/project_widgets.scss',
        ],
        'web.assets_frontend': [
            'project/static/src/scss/portal_rating.scss',
            'project/static/src/js/portal_rating.js',
        ],
        'web.assets_qweb': [
            'project/static/src/xml/**/*',
        ],
        'web.qunit_suite_tests': [
            'project/static/tests/burndown_chart_tests.js',
        ],
        'web.assets_tests': [
            'project/static/tests/tours/**/*',
        ],
        'project.assets_qweb': [
            ('include', 'web.assets_qweb'),
            'project/static/src/project_sharing/**/*.xml',
        ],
        'project.webclient': [
            ('include', 'web.assets_backend'),
            ('remove', 'web/static/src/webclient/menu_service.js'),

            # Remove Longpolling bus and packages needed this bus
            ('remove', 'bus/static/src/js/services/assets_watchdog_service.js'),
            ('remove', 'mail/static/src/services/messaging/messaging.js'),

            ('remove', 'mail/static/src/components/dialog_manager/dialog_manager.js'),
            ('remove', 'mail/static/src/services/dialog_service/dialog_service.js'),
            ('remove', 'mail/static/src/components/chat_window_manager/chat_window_manager.js'),
            ('remove', 'mail/static/src/services/chat_window_service/chat_window_service.js'),

            'web/static/src/legacy/js/public/public_widget.js',
            'portal/static/src/js/portal_chatter.js',
            'portal/static/src/js/portal_composer.js',
            'project/static/src/project_sharing/**/*.js',
            'project/static/src/scss/project_sharing/*',
            'web/static/src/start.js',
            'web/static/src/legacy/legacy_setup.js',
        ],
    },
    'license': 'LGPL-3',
}
