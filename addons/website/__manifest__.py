# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Website',
    'category': 'Website/Website',
    'sequence': 7,
    'summary': 'Enterprise website builder',
    'website': 'https://www.odoo.com/page/website-builder',
    'version': '1.0',
    'description': "",
    'depends': [
        'web',
        'web_editor',
        'http_routing',
        'portal',
        'social_media',
        'auth_signup',
    ],
    'installable': True,
    'data': [
        'data/website_data.xml',
        'data/website_visitor_cron.xml',
        'security/website_security.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/website_templates.xml',
        'views/website_navbar_templates.xml',
        'views/snippets/snippets.xml',
        'views/snippets/s_title.xml',
        'views/snippets/s_cover.xml',
        'views/snippets/s_text_image.xml',
        'views/snippets/s_image_text.xml',
        'views/snippets/s_banner.xml',
        'views/snippets/s_text_block.xml',
        'views/snippets/s_features.xml',
        'views/snippets/s_three_columns.xml',
        'views/snippets/s_picture.xml',
        'views/snippets/s_carousel.xml',
        'views/snippets/s_alert.xml',
        'views/website_views.xml',
        'views/website_visitor_views.xml',
        'views/res_config_settings_views.xml',
        'views/website_rewrite.xml',
        'views/ir_actions_views.xml',
        'views/ir_attachment_views.xml',
        'views/res_partner_views.xml',
        'wizard/base_language_install_views.xml',
        'wizard/website_robots.xml',
    ],
    'demo': [
        'data/website_demo.xml',
    ],
    'qweb': [
        'static/src/xml/website.backend.xml',
        'static/src/xml/website_widget.xml',
        'static/src/xml/theme_preview.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
}
