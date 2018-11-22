# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def get_countries_posting_at_bank_rec(self):
        rslt = super(AccountChartTemplate, self).get_countries_posting_at_bank_rec()
        rslt.append('LU')
        return rslt

    @api.model
    def _prepare_all_journals(self, acc_template_ref, company, journals_dict=None):
        journal_data = super(AccountChartTemplate, self)._prepare_all_journals(
            acc_template_ref, company, journals_dict)
        for journal in journal_data:
            if journal['type'] in ('sale', 'purchase') and company.country_id == self.env.ref('base.lu'):
                journal.update({'refund_sequence': True})
        return journal_data
