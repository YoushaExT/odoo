# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Invoicing',
    'version' : '1.1',
    'summary': 'Invoices & Payments',
    'sequence': 10,
    'description': """
Invoicing & Payments
====================
The specific and easy-to-use Invoicing system in Odoo allows you to keep track of your accounting, even when you are not an accountant. It provides an easy way to follow up on your vendors and customers.

You could use this simplified accounting in case you work with an (external) account to keep your books, and you still want to keep track of payments. This module also offers you an easy method of registering payments, without having to encode complete abstracts of account.
    """,
    'category': 'Accounting/Accounting',
    'website': 'https://www.odoo.com/app/billing',
    'images' : ['images/accounts.jpeg','images/bank_statement.jpeg','images/cash_register.jpeg','images/chart_of_accounts.jpeg','images/customer_invoice.jpeg','images/journal_entries.jpeg'],
    'depends' : ['base_setup', 'product', 'analytic', 'portal', 'digest'],
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'data/data_account_type.xml',
        'data/account_data.xml',
        'data/digest_data.xml',
        'views/account_report.xml',
        'data/mail_template_data.xml',
        'views/account_payment_view.xml',
        'wizard/account_automatic_entry_wizard_views.xml',
        'wizard/account_unreconcile_view.xml',
        'wizard/account_move_reversal_view.xml',
        'wizard/account_resequence_views.xml',
        'wizard/account_payment_register_views.xml',
        'views/account_move_views.xml',
        'wizard/setup_wizards_view.xml',
        'wizard/pos_box.xml',
        'views/partner_view.xml',
        'views/account_account_type_views.xml',
        'views/account_account_views.xml',
        'views/account_group_views.xml',
        'views/account_journal_views.xml',
        'views/account_account_tag_views.xml',
        'views/account_bank_statement_views.xml',
        'views/account_reconcile_model_views.xml',
        'views/account_tax_views.xml',
        'views/account_full_reconcile_views.xml',
        'views/account_payment_term_views.xml',
        'views/account_chart_template_views.xml',
        'views/res_partner_bank_views.xml',
        'views/report_statement.xml',
        'views/terms_template.xml',
        'wizard/account_validate_move_view.xml',
        'views/res_company_views.xml',
        'views/product_view.xml',
        'views/account_analytic_view.xml',
        'views/report_invoice.xml',
        'report/account_invoice_report_view.xml',
        'views/account_cash_rounding_view.xml',
        'wizard/account_report_common_view.xml',
        'views/report_journal.xml',
        'views/tax_adjustments.xml',
        'wizard/wizard_tax_adjustments_view.xml',
        'views/ir_module_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_dashboard_view.xml',
        'views/account_portal_templates.xml',
        'views/report_payment_receipt_templates.xml',
        'views/account_onboarding_templates.xml',
        'data/service_cron.xml',
        'views/account_incoterms_view.xml',
        'data/account_incoterms_data.xml',
        'views/digest_views.xml',
        'wizard/account_invoice_send_views.xml',
        'views/account_tax_report_views.xml',
        'report/account_hash_integrity_templates.xml',
        'views/res_currency.xml',
        'views/account_menuitem.xml',
        'views/account_analytic_default_view.xml',
        'wizard/account_tour_upload_bill.xml',
        'wizard/accrued_orders.xml',
    ],
    'demo': [
        'demo/account_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': '_account_post_init',
    'assets': {
        'web._assets_primary_variables': [
            'account/static/src/scss/variables.scss',
        ],
        'web.assets_backend': [
            'account/static/src/css/account_bank_and_cash.css',
            'account/static/src/css/account.css',
            'account/static/src/css/tax_group.css',
            'account/static/src/scss/account_reconciliation.scss',
            'account/static/src/scss/account_journal_dashboard.scss',
            'account/static/src/scss/account_dashboard.scss',
            'account/static/src/scss/account_searchpanel.scss',
            'account/static/src/scss/section_and_note_backend.scss',
            'account/static/src/scss/account_activity.scss',
            'account/static/src/js/account_payment_field.js',
            'account/static/src/js/account_resequence_field.js',
            'account/static/src/js/grouped_view_widget.js',
            'account/static/src/js/mail_activity.js',
            'account/static/src/js/tax_group.js',
            'account/static/src/js/section_and_note_fields_backend.js',
            'account/static/src/js/tours/account.js',
            'account/static/src/js/bills_upload.js',
            'account/static/src/js/account_selection.js',
        ],
        'web.assets_frontend': [
            'account/static/src/js/account_portal_sidebar.js',
        ],
        'web.assets_tests': [
            'account/static/tests/tours/**/*',
        ],
        'web.qunit_suite_tests': [
            ('after', 'web/static/tests/legacy/views/kanban_tests.js', 'account/static/tests/account_payment_field_tests.js'),
            ('after', 'web/static/tests/legacy/views/kanban_tests.js', 'account/static/tests/section_and_note_tests.js'),
        ],
        'web.assets_qweb': [
            'account/static/src/xml/**/*',
        ],
    },
    'license': 'LGPL-3',
}
