# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    has_accounting_entries = fields.Boolean(compute='_compute_has_chart_of_accounts')
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id", required=True,
        string='Currency', help="Main currency of the company.")
    currency_exchange_journal_id = fields.Many2one(
        'account.journal',
        related='company_id.currency_exchange_journal_id',
        string="Exchange Gain or Loss Journal",
        domain=[('type', '=', 'general')],
        help='The accounting journal where automatic exchange differences will be registered')
    has_chart_of_accounts = fields.Boolean(compute='_compute_has_chart_of_accounts', string='Company has a chart of accounts')
    chart_template_id = fields.Many2one('account.chart.template', string='Template',
        domain="[('visible','=', True)]")
    sale_tax_id = fields.Many2one('account.tax', string="Default Sale Tax", related='company_id.account_sale_tax_id')
    purchase_tax_id = fields.Many2one('account.tax', string="Default Purchase Tax", related='company_id.account_purchase_tax_id')
    tax_calculation_rounding_method = fields.Selection([
        ('round_per_line', 'Round calculation of taxes per line'),
        ('round_globally', 'Round globally calculation of taxes '),
        ], related='company_id.tax_calculation_rounding_method', string='Tax calculation rounding method')
    module_account_accountant = fields.Boolean(string='Accounting')
    group_analytic_accounting = fields.Boolean(string='Analytic Accounting',
        implied_group='analytic.group_analytic_accounting')
    group_warning_account = fields.Boolean(string="Warnings in Invoices", implied_group='account.group_warning_account')
    group_cash_rounding = fields.Boolean(string="Cash Rounding", implied_group='account.group_cash_rounding')
    module_account_asset = fields.Boolean(string='Assets Management')
    module_account_deferred_revenue = fields.Boolean(string="Revenue Recognition")
    module_account_budget = fields.Boolean(string='Budget Management')
    module_account_payment = fields.Boolean(string='Online Payment')
    module_account_reports = fields.Boolean("Dynamic Reports")
    module_account_reports_followup = fields.Boolean("Enable payment followup management")
    module_l10n_us_check_printing = fields.Boolean("Allow check printing and deposits")
    module_account_batch_deposit = fields.Boolean(string='Use batch deposit',
        help='This allows you to group received checks before you deposit them to the bank.\n'
             '-This installs the module account_batch_deposit.')
    module_account_sepa = fields.Boolean(string='Use SEPA payments')
    module_account_sepa_direct_debit = fields.Boolean(string='Use SEPA Direct Debit')
    module_account_plaid = fields.Boolean(string="Plaid Connector")
    module_account_yodlee = fields.Boolean("Bank Interface - Sync your bank feeds automatically")
    module_account_bank_statement_import_qif = fields.Boolean("Import .qif files")
    module_account_bank_statement_import_ofx = fields.Boolean("Import in .ofx format")
    module_account_bank_statement_import_csv = fields.Boolean("Import in .csv format")
    module_account_bank_statement_import_camt = fields.Boolean("Import in CAMT.053 format")
    module_currency_rate_live = fields.Boolean(string="Allow Currency Rate Live")
    module_print_docsaway = fields.Boolean(string="Docsaway")
    module_product_margin = fields.Boolean(string="Allow Product Margin")
    module_l10n_eu_service = fields.Boolean(string="EU Digital Goods VAT")
    module_account_taxcloud = fields.Boolean(string="Account TaxCloud")
    tax_exigibility = fields.Boolean(string='Cash Basis', related='company_id.tax_exigibility')
    tax_cash_basis_journal_id = fields.Many2one('account.journal', related='company_id.tax_cash_basis_journal_id', string="Tax Cash Basis Journal")
    account_hide_setup_bar = fields.Boolean(string='Hide Setup Bar', related='company_id.account_setup_bar_closed',help="Tick if you wish to hide the setup bar on the dashboard")
    group_allow_recurring = fields.Boolean(string="Recurring Vendor Bills", implied_group="account.group_allow_recurring")

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env.ref('account.recurrent_vendor_bills_cron').write({'active': self.group_allow_recurring})
        if self.group_multi_currency:
            self.env.ref('base.group_user').write({'implied_ids': [(4, self.env.ref('product.group_sale_pricelist').id)]})
        """ install a chart of accounts for the given company (if required) """
        if self.chart_template_id and self.chart_template_id != self.company_id.chart_template_id:
            wizard = self.env['wizard.multi.charts.accounts'].create({
                'company_id': self.company_id.id,
                'chart_template_id': self.chart_template_id.id,
                'transfer_account_id': self.chart_template_id.transfer_account_id.id,
                'code_digits': self.chart_template_id.code_digits,
                'sale_tax_rate': 15.0,
                'purchase_tax_rate': 15.0,
                'code_digits': self.chart_template_id.code_digits,
                'complete_tax_set': self.chart_template_id.complete_tax_set,
                'currency_id': self.currency_id.id,
                'bank_account_code_prefix': self.chart_template_id.bank_account_code_prefix,
                'cash_account_code_prefix': self.chart_template_id.cash_account_code_prefix,
            })
            wizard.onchange_chart_template_id()
            wizard.execute()

    @api.depends('company_id')
    def _compute_has_chart_of_accounts(self):
        self.has_chart_of_accounts = bool(self.company_id.chart_template_id)
        self.chart_template_id = self.company_id.chart_template_id or False
        self.has_accounting_entries = self.env['wizard.multi.charts.accounts'].existing_accounting(self.company_id)

    @api.onchange('group_analytic_accounting')
    def onchange_analytic_accounting(self):
        if self.group_analytic_accounting:
            self.module_account_accountant = True

    @api.onchange('module_account_budget')
    def onchange_module_account_budget(self):
        if self.module_account_budget:
            self.group_analytic_accounting = True

    @api.onchange('module_account_yodlee')
    def onchange_account_yodlee(self):
        if self.module_account_yodlee:
            self.module_account_plaid = True

    @api.onchange('tax_exigibility')
    def _onchange_tax_exigibility(self):
        res = {}
        tax = self.env['account.tax'].search([
            ('company_id', '=', self.env.user.company_id.id), ('tax_exigibility', '=', 'on_payment')
        ], limit=1)
        if not self.tax_exigibility and tax:
            self.tax_exigibility = True
            res['warning'] = {
                'title': _('Error!'),
                'message': _('You cannot disable this setting because some of your taxes are cash basis. '
                             'Modify your taxes first before disabling this setting.')
            }
        return res

    @api.model
    def create(self, values):
        # Optimisation purpose, saving a res_config even without changing any values will trigger the write of all
        # related values, including the currency_id field on res_company. This in turn will trigger the recomputation
        # of account_move_line related field company_currency_id which can be slow depending on the number of entries
        # in the database. Thus, if we do not explicitly change the currency_id, we should not write it on the company
        if ('company_id' in values and 'currency_id' in values):
            company = self.env['res.company'].browse(values.get('company_id'))
            if company.currency_id.id == values.get('currency_id'):
                values.pop('currency_id')
        return super(ResConfigSettings, self).create(values)
