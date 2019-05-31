# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'website.published.multi.mixin']

    public_info = fields.Char(string='Public Info')

    @api.multi
    def _compute_website_url(self):
        super(HrEmployee, self)._compute_website_url()
        for employee in self:
            employee.website_url = '/aboutus#team'

class HrEmployeePublic(models.Model):
    _name = 'hr.employee.public'
    _inherit = ['hr.employee.public', 'website.published.multi.mixin']

    public_info = fields.Char(string='Public Info')

