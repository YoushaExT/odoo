# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Base',
    'version': '1.3',
    'category': 'Hidden',
    'description': """
The kernel of Odoo, needed for all installation.
===================================================
""",
    'depends': [],
    'data': [
        'res/res.lang.csv',
        'base_data.xml',
        'res/res_currency_data.xml',
        'res/res_country_data.xml',
        'security/base_security.xml',
        'base_menu.xml',
        'res/res_config.xml',
        'res/res.country.state.csv',
        'ir/ir_actions.xml',
        'ir/ir_config_parameter_view.xml',
        'ir/ir_cron_view.xml',
        'ir/ir_filters.xml',
        'ir/ir_mail_server_view.xml',
        'ir/ir_model_view.xml',
        'ir/ir_attachment_view.xml',
        'ir/ir_rule_view.xml',
        'ir/ir_sequence_view.xml',
        'ir/ir_translation_view.xml',
        'ir/ir_ui_menu_view.xml',
        'ir/ir_ui_view_view.xml',
        'ir/ir_values_view.xml',
        'ir/ir_default_view.xml',
        'ir/ir_autovacuum.xml',
        'ir/ir_model_report.xml',
        'ir/report_ir_model.xml',
        'ir/ir_logging_view.xml',
        'ir/ir_qweb.xml',
        'module/module_view.xml',
        'module/module_data.xml',
        'module/module_report.xml',
        'module/report/report_ir_module_reference.xml',
        'module/wizard/base_module_update_view.xml',
        'module/wizard/base_language_install_view.xml',
        'module/wizard/base_import_language_view.xml',
        'module/wizard/base_module_upgrade_view.xml',
        'module/wizard/base_module_uninstall_view.xml',
        'module/wizard/base_export_language_view.xml',
        'module/wizard/base_update_translations_view.xml',
        'module/wizard/base_module_immediate_install.xml',
        'res/res_company_view.xml',
        'res/res_request_view.xml',
        'res/res_lang_view.xml',
        'res/res_partner_view.xml',
        'res/res_bank_view.xml',
        'res/res_country_view.xml',
        'res/res_currency_view.xml',
        'res/res_users_view.xml',
        'res/res_partner_data.xml',
        'res/ir_property_view.xml',
        'res/res_security.xml',
        'res/report_paperformat_views.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'base_demo.xml',
        'res/res_currency_demo.xml',
        'res/res_bank_demo.xml',
        'res/res_partner_demo.xml',
        'res/res_partner_demo.yml',
        'res/res_partner_image_demo.xml',
    ],
    'test': [],
    'installable': True,
    'auto_install': True,
    'post_init_hook': 'post_init',
}
