# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.tools import float_compare, format_amount


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    timesheet_ids = fields.Many2many('account.analytic.line', compute='_compute_timesheet_ids', string='Timesheet activities associated to this sale')
    timesheet_count = fields.Float(string='Timesheet activities', compute='_compute_timesheet_ids', groups="hr_timesheet.group_hr_timesheet_user")

    # override domain
    project_id = fields.Many2one(domain="[('pricing_type', 'in', ('fixed_rate', 'task_rate')), ('analytic_account_id', '!=', False), ('company_id', '=', company_id)]")
    timesheet_encode_uom_id = fields.Many2one('uom.uom', related='company_id.timesheet_encode_uom_id')
    timesheet_total_duration = fields.Integer("Timesheet Total Duration", compute='_compute_timesheet_total_duration', help="Total recorded duration, expressed in the encoding UoM, and rounded to the unit")

    def _compute_timesheet_ids(self):
        timesheet_groups = self.env['account.analytic.line'].sudo().read_group(
            [('so_line', 'in', self.mapped('order_line').ids), ('project_id', '!=', False)],
            ['so_line', 'ids:array_agg(id)'],
            ['so_line'])
        timesheets_per_sol = {group['so_line'][0]: (group['ids'], group['so_line_count']) for group in timesheet_groups}

        for order in self:
            timesheet_ids = []
            timesheet_count = 0
            for sale_line_id in order.order_line.filtered('is_service').ids:
                list_timesheet_ids, count = timesheets_per_sol.get(sale_line_id, ([], 0))
                timesheet_ids.extend(list_timesheet_ids)
                timesheet_count += count

            order.update({
                'timesheet_ids': self.env['account.analytic.line'].browse(timesheet_ids),
                'timesheet_count': timesheet_count,
            })

    @api.depends('timesheet_ids', 'company_id.timesheet_encode_uom_id')
    def _compute_timesheet_total_duration(self):
        for sale_order in self:
            timesheets = sale_order.timesheet_ids if self.user_has_groups('hr_timesheet.group_hr_timesheet_approver') else sale_order.timesheet_ids.filtered(lambda t: t.user_id.id == self.env.uid)
            total_time = 0.0
            for timesheet in timesheets:
                # Timesheets may be stored in a different unit of measure, so first we convert all of them to the reference unit
                total_time += timesheet.unit_amount * timesheet.product_uom_id.factor_inv
            # Now convert to the proper unit of measure
            total_time *= sale_order.timesheet_encode_uom_id.factor
            sale_order.timesheet_total_duration = round(total_time)

    def _compute_field_value(self, field):
        super()._compute_field_value(field)
        if field.name != 'invoice_status' or self.env.context.get('mail_activity_automation_skip'):
            return

        # Get SOs which their state is not equal to upselling or invoied and if at least a SOL has warning prepaid service upsell set to True and the warning has not already been displayed
        upsellable_orders = self.filtered(lambda so:
            so.state == 'sale'
            and so.invoice_status not in ('upselling', 'invoiced')
            and (so.user_id or so.partner_id.user_id)  # salesperson needed to assign upsell activity
        )
        for order in upsellable_orders:
            upsellable_lines = order._get_prepaid_service_lines_to_upsell()
            if upsellable_lines:
                order._create_upsell_activity()
                # We want to display only one time the warning for each SOL
                upsellable_lines.write({'has_displayed_warning_upsell': True})

    def _get_prepaid_service_lines_to_upsell(self):
        """ Retrieve all sols which need to display an upsell activity warning in the SO

            These SOLs should contain a product which has:
                - type="service",
                - service_policy="ordered_timesheet",
                - service_upsell_warning=True.
        """
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        return self.order_line.filtered(lambda sol:
            sol.is_service
            and not sol.has_displayed_warning_upsell  # we don't want to display many times the warning each time we timesheet on the SOL
            and sol.product_id.service_policy == 'ordered_timesheet'
            and sol.product_id.service_upsell_warning
            and float_compare(
                sol.qty_delivered,
                sol.product_uom_qty * (sol.product_id.service_upsell_threshold or 1.0),
                precision_digits=precision
            ) >= 0
        )

    def action_view_project_ids(self):
        self.ensure_one()
        # redirect to form or kanban view
        if len(self.project_ids) == 1 and self.project_ids.project_overview and self.env.user.has_group('project.group_project_manager'):
            action = self.project_ids.action_view_timesheet_plan()
        else:
            action = super().action_view_project_ids()
        return action

    def action_view_timesheet(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale_timesheet.timesheet_action_from_sales_order")
        action['context'] = {
            'search_default_billable_timesheet': True
        }  # erase default filters
        if self.timesheet_count > 0:
            action['domain'] = [('so_line', 'in', self.order_line.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _create_invoices(self, grouped=False, final=False, start_date=None, end_date=None):
        """ Override the _create_invoice method in sale.order model in sale module
            Add new parameter in this method, to invoice sale.order with a date. This date is used in sale_make_invoice_advance_inv into this module.
            :param start_date: the start date of the period
            :param end_date: the end date of the period
            :return {account.move}: the invoices created
        """
        moves = super(SaleOrder, self)._create_invoices(grouped, final)
        moves._link_timesheets_to_invoice(start_date, end_date)
        return moves

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    qty_delivered_method = fields.Selection(selection_add=[('timesheet', 'Timesheets')])
    analytic_line_ids = fields.One2many(domain=[('project_id', '=', False)])  # only analytic lines, not timesheets (since this field determine if SO line came from expense)
    remaining_hours_available = fields.Boolean(compute='_compute_remaining_hours_available', compute_sudo=True)
    remaining_hours = fields.Float('Remaining Hours on SO', compute='_compute_remaining_hours', compute_sudo=True, store=True)
    has_displayed_warning_upsell = fields.Boolean('Has Displayed Warning Upsell')

    def name_get(self):
        res = super(SaleOrderLine, self).name_get()
        with_remaining_hours = self.env.context.get('with_remaining_hours')
        with_price_unit = self.env.context.get('with_price_unit')
        if with_remaining_hours or with_price_unit:
            names = dict(res)
            result = []
            uom_hour = with_remaining_hours and self.env.ref('uom.product_uom_hour')
            uom_day = with_remaining_hours and self.env.ref('uom.product_uom_day')
            sols_by_so_dict = with_price_unit and defaultdict(lambda: self.env[self._name])  # key: (sale_order_id, product_id), value: sale order line
            for line in self:
                if with_remaining_hours:
                    name = names.get(line.id)
                    if line.remaining_hours_available:
                        company = self.env.company
                        encoding_uom = company.timesheet_encode_uom_id
                        remaining_time = ''
                        if encoding_uom == uom_hour:
                            hours, minutes = divmod(abs(line.remaining_hours) * 60, 60)
                            round_minutes = minutes / 30
                            minutes = math.ceil(round_minutes) if line.remaining_hours >= 0 else math.floor(round_minutes)
                            if minutes > 1:
                                minutes = 0
                                hours += 1
                            else:
                                minutes = minutes * 30
                            remaining_time = ' ({sign}{hours:02.0f}:{minutes:02.0f})'.format(
                                sign='-' if line.remaining_hours < 0 else '',
                                hours=hours,
                                minutes=minutes)
                        elif encoding_uom == uom_day:
                            remaining_days = company.project_time_mode_id._compute_quantity(line.remaining_hours, encoding_uom, round=False)
                            remaining_time = ' ({qty:.02f} {unit})'.format(
                                qty=remaining_days,
                                unit=_('days') if abs(remaining_days) > 1 else _('day')
                            )
                        name = '{name}{remaining_time}'.format(
                            name=name,
                            remaining_time=remaining_time
                        )
                        if with_price_unit:
                            names[line.id] = name
                    if not with_price_unit:
                        result.append((line.id, name))
                if with_price_unit:
                    sols_by_so_dict[line.order_id.id, line.product_id.id] += line

            if with_price_unit:
                for sols in sols_by_so_dict.values():
                    if len(sols) > 1:
                        result += [(
                            line.id,
                            '%s - %s' % (
                                names.get(line.id), format_amount(self.env, line.price_unit, line.currency_id))
                        ) for line in sols]
                    else:
                        result.append((sols.id, names.get(sols.id)))
            return result
        return res

    @api.depends('product_id.service_policy')
    def _compute_remaining_hours_available(self):
        uom_hour = self.env.ref('uom.product_uom_hour')
        for line in self:
            is_ordered_timesheet = line.product_id.service_policy == 'ordered_timesheet'
            is_time_product = line.product_uom.category_id == uom_hour.category_id
            line.remaining_hours_available = is_ordered_timesheet and is_time_product

    @api.depends('qty_delivered', 'product_uom_qty', 'analytic_line_ids')
    def _compute_remaining_hours(self):
        uom_hour = self.env.ref('uom.product_uom_hour')
        for line in self:
            remaining_hours = None
            if line.remaining_hours_available:
                qty_left = line.product_uom_qty - line.qty_delivered
                remaining_hours = line.product_uom._compute_quantity(qty_left, uom_hour)
            line.remaining_hours = remaining_hours

    @api.depends('product_id')
    def _compute_qty_delivered_method(self):
        """ Sale Timesheet module compute delivered qty for product [('type', 'in', ['service']), ('service_type', '=', 'timesheet')] """
        super(SaleOrderLine, self)._compute_qty_delivered_method()
        for line in self:
            if not line.is_expense and line.product_id.type == 'service' and line.product_id.service_type == 'timesheet':
                line.qty_delivered_method = 'timesheet'

    @api.depends('analytic_line_ids.project_id', 'project_id.pricing_type')
    def _compute_qty_delivered(self):
        super(SaleOrderLine, self)._compute_qty_delivered()

        lines_by_timesheet = self.filtered(lambda sol: sol.qty_delivered_method == 'timesheet')
        domain = lines_by_timesheet._timesheet_compute_delivered_quantity_domain()
        mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)
        for line in lines_by_timesheet:
            line.qty_delivered = mapping.get(line.id or line._origin.id, 0.0)

    def _timesheet_compute_delivered_quantity_domain(self):
        """ Hook for validated timesheet in addionnal module """
        return [('project_id', '!=', False)]

    ###########################################
    # Service : Project and task generation
    ###########################################

    def _convert_qty_company_hours(self, dest_company):
        company_time_uom_id = dest_company.project_time_mode_id
        if self.product_uom.id != company_time_uom_id.id and self.product_uom.category_id.id == company_time_uom_id.category_id.id:
            planned_hours = self.product_uom._compute_quantity(self.product_uom_qty, company_time_uom_id)
        else:
            planned_hours = self.product_uom_qty
        return planned_hours

    def _timesheet_create_project(self):
        project = super()._timesheet_create_project()
        project.write({'allow_timesheets': True})
        return project

    def _timesheet_create_project_prepare_values(self):
        """Generate project values"""
        values = super()._timesheet_create_project_prepare_values()
        values['allow_billable'] = True
        values['pricing_type'] = 'fixed_rate'
        return values

    def _recompute_qty_to_invoice(self, start_date, end_date):
        """ Recompute the qty_to_invoice field for product containing timesheets

            Search the existed timesheets between the given period in parameter.
            Retrieve the unit_amount of this timesheet and then recompute
            the qty_to_invoice for each current product.

            :param start_date: the start date of the period
            :param end_date: the end date of the period
        """
        lines_by_timesheet = self.filtered(lambda sol: sol.product_id and sol.product_id._is_delivered_timesheet())
        domain = lines_by_timesheet._timesheet_compute_delivered_quantity_domain()
        domain = expression.AND([domain, [
            '|',
            ('timesheet_invoice_id', '=', False),
            ('timesheet_invoice_id.state', '=', 'cancel')]])
        if start_date:
            domain = expression.AND([domain, [('date', '>=', start_date)]])
        if end_date:
            domain = expression.AND([domain, [('date', '<=', end_date)]])
        mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)

        for line in lines_by_timesheet:
            line.qty_to_invoice = mapping.get(line.id, 0.0)
