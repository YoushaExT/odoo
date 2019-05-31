# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    employee_cars_count = fields.Integer(compute="_compute_employee_cars_count", string="Cars", groups="fleet.fleet_group_manager")

    def action_open_employee_cars(self):
        self.ensure_one()
        cars = self.env['fleet.vehicle.assignation.log'].search([
            ('driver_id', 'in', (self.user_id.partner_id | self.sudo().address_home_id).ids)]).mapped('vehicle_id')

        return {
            "type": "ir.actions.act_window",
            "res_model": "fleet.vehicle",
            "views": [[False, "kanban"], [False, "form"], [False, "tree"]],
            "domain": [("id", "in", cars.ids)],
            "name": "History Employee Cars",
        }

    def _compute_employee_cars_count(self):
        driver_ids = (self.mapped('user_id.partner_id') | self.sudo().mapped('address_home_id')).ids
        fleet_data = self.env['fleet.vehicle.assignation.log'].read_group(
            domain=[('driver_id', 'in', driver_ids)], fields=['driver_id'], groupby=['driver_id'])
        mapped_data = {m['driver_id'][0]: m['driver_id_count'] for m in fleet_data}
        for employee in self:
            drivers = employee.user_id.partner_id | employee.sudo().address_home_id
            employee.employee_cars_count = sum(mapped_data.get(pid, 0) for pid in drivers.ids)

    def action_get_claim_report(self):
        self.ensure_one()
        return {
            'name': 'Claim Report',
            'type': 'ir.actions.act_url',
            'url': '/fleet/print_claim_report/%(employee_id)s' % {'employee_id': self.id},
        }
