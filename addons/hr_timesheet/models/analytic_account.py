# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    _description = 'Analytic Account'

    company_uom_id = fields.Many2one('uom.uom', related='company_id.project_time_mode_id', string="Company UOM", readonly=False)
    project_ids = fields.One2many('project.project', 'analytic_account_id', string='Projects')
    project_count = fields.Integer("Project Count", compute='_compute_project_count')

    @api.multi
    @api.depends('project_ids')
    def _compute_project_count(self):
        project_data = self.env['project.project'].read_group([('analytic_account_id', 'in', self.ids)], ['analytic_account_id'], ['analytic_account_id'])
        mapping = {m['analytic_account_id'][0]: m['analytic_account_id_count'] for m in project_data}
        for account in self:
            account.project_count = mapping.get(account.id, 0)

    @api.multi
    def unlink(self):
        projects = self.env['project.project'].search([('analytic_account_id', 'in', self.ids)])
        has_tasks = self.env['project.task'].search_count([('project_id', 'in', projects.ids)])
        if has_tasks:
            raise UserError(_('Please remove existing tasks in the project linked to the accounts you want to delete.'))
        return super(AccountAnalyticAccount, self).unlink()

    @api.multi
    def action_view_projects(self):
        kanban_view_id = self.env.ref('project.view_project_kanban').id
        result = {
            "type": "ir.actions.act_window",
            "res_model": "project.project",
            "views": [[kanban_view_id, "kanban"], [False, "form"]],
            "domain": [['analytic_account_id', '=', self.id]],
            "context": {"create": False},
            "name": "Projects",
        }
        if len(self.project_ids) == 1:
            result['views'] = [(False, "form")]
            result['res_id'] = self.project_ids.id
        return result
