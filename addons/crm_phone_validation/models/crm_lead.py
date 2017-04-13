# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class Lead(models.Model):
    _name = 'crm.lead'
    _inherit = ['crm.lead', 'phone.validation.mixin']

    @api.onchange('phone', 'country_id')
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self.phone_format(self.phone)

    @api.onchange('mobile', 'country_id')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self.phone_format(self.mobile)

    @api.onchange('fax', 'country_id')
    def _onchange_fax_validation(self):
        if self.fax:
            self.fax = self.phone_format(self.fax)
