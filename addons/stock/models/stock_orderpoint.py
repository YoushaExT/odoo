# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict
from datetime import datetime, time
from dateutil import relativedelta
from itertools import groupby
from json import dumps
from psycopg2 import OperationalError

from odoo import SUPERUSER_ID, _, api, fields, models, registry
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_compare, frozendict, split_every

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    """ Defines Minimum stock rules. """
    _name = "stock.warehouse.orderpoint"
    _description = "Minimum Inventory Rule"
    _check_company_auto = True
    _order = "location_id,company_id,id"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        warehouse = None
        if 'warehouse_id' not in res and res.get('company_id'):
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', res['company_id'])], limit=1)
        if warehouse:
            res['warehouse_id'] = warehouse.id
            res['location_id'] = warehouse.lot_stock_id.id
        return res

    name = fields.Char(
        'Name', copy=False, required=True, readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('stock.orderpoint'))
    trigger = fields.Selection([
        ('auto', 'Auto'), ('manual', 'Manual')], string='Trigger', default='auto', required=True)
    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the orderpoint without removing it.")
    snoozed_until = fields.Date('Snoozed', help="Hidden until next scheduler.")
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Warehouse',
        check_company=True, ondelete="cascade", required=True)
    location_id = fields.Many2one(
        'stock.location', 'Location', index=True,
        ondelete="cascade", required=True, check_company=True)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
    product_id = fields.Many2one(
        'product.product', 'Product', index=True,
        domain="[('type', '=', 'product'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]", ondelete='cascade', required=True, check_company=True)
    product_category_id = fields.Many2one('product.category', name='Product Category', related='product_id.categ_id', store=True)
    product_uom = fields.Many2one(
        'uom.uom', 'Unit of Measure', related='product_id.uom_id')
    product_uom_name = fields.Char(string='Product unit of measure label', related='product_uom.display_name', readonly=True)
    product_min_qty = fields.Float(
        'Min Quantity', digits='Product Unit of Measure', required=True, default=0.0,
        help="When the virtual stock equals to or goes below the Min Quantity specified for this field, Odoo generates "
             "a procurement to bring the forecasted quantity to the Max Quantity.")
    product_max_qty = fields.Float(
        'Max Quantity', digits='Product Unit of Measure', required=True, default=0.0,
        help="When the virtual stock goes below the Min Quantity, Odoo generates "
             "a procurement to bring the forecasted quantity to the Quantity specified as Max Quantity.")
    qty_multiple = fields.Float(
        'Multiple Quantity', digits='Product Unit of Measure',
        default=1, required=True,
        help="The procurement quantity will be rounded up to this multiple.  If it is 0, the exact quantity will be used.")
    group_id = fields.Many2one(
        'procurement.group', 'Procurement Group', copy=False,
        help="Moves created through this orderpoint will be put in this procurement group. If none is given, the moves generated by stock rules will be grouped into one big picking.")
    company_id = fields.Many2one(
        'res.company', 'Company', required=True, index=True,
        default=lambda self: self.env.company)
    allowed_location_ids = fields.One2many(comodel_name='stock.location', compute='_compute_allowed_location_ids')

    rule_ids = fields.Many2many('stock.rule', string='Rules used', compute='_compute_rules')
    json_lead_days_popover = fields.Char(compute='_compute_json_popover')
    lead_days_date = fields.Date(compute='_compute_lead_days')
    allowed_route_ids = fields.Many2many('stock.location.route', compute='_compute_allowed_route_ids')
    route_id = fields.Many2one(
        'stock.location.route', string='Preferred Route', domain="[('id', 'in', allowed_route_ids)]")
    qty_on_hand = fields.Float('On Hand', readonly=True, compute='_compute_qty')
    qty_forecast = fields.Float('Forecast', readonly=True, compute='_compute_qty')
    qty_to_order = fields.Float('To Order', compute='_compute_qty_to_order', store=True, readonly=False)


    _sql_constraints = [
        ('qty_multiple_check', 'CHECK( qty_multiple >= 0 )', 'Qty Multiple must be greater than or equal to zero.'),
    ]

    @api.depends('warehouse_id')
    def _compute_allowed_location_ids(self):
        loc_domain = [('usage', 'in', ('internal', 'view'))]
        # We want to keep only the locations
        #  - strictly belonging to our warehouse
        #  - not belonging to any warehouses
        for orderpoint in self:
            other_warehouses = self.env['stock.warehouse'].search([('id', '!=', orderpoint.warehouse_id.id)])
            for view_location_id in other_warehouses.mapped('view_location_id'):
                loc_domain = expression.AND([loc_domain, ['!', ('id', 'child_of', view_location_id.id)]])
                loc_domain = expression.AND([loc_domain, ['|', ('company_id', '=', False), ('company_id', '=', orderpoint.company_id.id)]])
            orderpoint.allowed_location_ids = self.env['stock.location'].search(loc_domain)

    @api.depends('warehouse_id', 'location_id')
    def _compute_allowed_route_ids(self):
        route_by_product = self.env['stock.location.route'].search([
            ('product_selectable', '=', True),
        ])
        self.allowed_route_ids = route_by_product.ids

    @api.depends('rule_ids', 'product_id.seller_ids', 'product_id.seller_ids.delay')
    def _compute_json_popover(self):
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.json_lead_days_popover = False
                continue
            dummy, lead_days_description = orderpoint.rule_ids._get_lead_days(orderpoint.product_id)
            orderpoint.json_lead_days_popover = dumps({
                'title': _('Replenishment'),
                'popoverTemplate': 'stock.leadDaysPopOver',
                'lead_days_date': fields.Date.to_string(orderpoint.lead_days_date),
                'lead_days_description': lead_days_description,
                'today': fields.Date.to_string(fields.Date.today()),
                'trigger': orderpoint.trigger,
                'qty_forecast': orderpoint.qty_forecast,
                'qty_to_order': orderpoint.qty_to_order,
                'product_min_qty': orderpoint.product_min_qty,
                'product_max_qty': orderpoint.product_max_qty,
                'product_uom_name': orderpoint.product_uom_name,
                'virtual': orderpoint.trigger == 'manual' and orderpoint.create_uid.id == SUPERUSER_ID,
            })

    @api.depends('rule_ids', 'product_id.seller_ids', 'product_id.seller_ids.delay')
    def _compute_lead_days(self):
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.lead_days_date = False
                continue
            lead_days, dummy = orderpoint.rule_ids._get_lead_days(orderpoint.product_id)
            lead_days_date = fields.Date.today() + relativedelta.relativedelta(days=lead_days)
            orderpoint.lead_days_date = lead_days_date

    @api.depends('route_id', 'product_id', 'location_id', 'company_id', 'warehouse_id', 'product_id.route_ids')
    def _compute_rules(self):
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.rule_ids = False
                continue
            orderpoint.rule_ids = orderpoint.product_id._get_rules_from_location(orderpoint.location_id, route_ids=orderpoint.route_id)

    @api.constrains('product_id')
    def _check_product_uom(self):
        ''' Check if the UoM has the same category as the product standard UoM '''
        if any(orderpoint.product_id.uom_id.category_id != orderpoint.product_uom.category_id for orderpoint in self):
            raise ValidationError(_('You have to select a product unit of measure that is in the same category than the default unit of measure of the product'))

    @api.onchange('location_id')
    def _onchange_location_id(self):
        warehouse = self.location_id.get_warehouse().id
        if warehouse:
            self.warehouse_id = warehouse

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """ Finds location id for changed warehouse. """
        if self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id.id
        else:
            self.location_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.warehouse_id = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id)
            ], limit=1)

    def write(self, vals):
        if 'company_id' in vals:
            for orderpoint in self:
                if orderpoint.company_id.id != vals['company_id']:
                    raise UserError(_("Changing the company of this record is forbidden at this point, you should rather archive it and create a new one."))
        return super().write(vals)

    @api.model
    def action_open_orderpoints(self):
        return self._get_orderpoint_action()

    def action_replenish(self):
        self._procure_orderpoint_confirm(company_id=self.env.company)
        notification = False
        if len(self) == 1:
            notification = self._get_replenishment_order_notification()
        # Forced to call compute quantity because we don't have a link.
        self._compute_qty()
        self.filtered(lambda o: o.create_uid.id == SUPERUSER_ID and o.qty_to_order <= 0.0 and o.trigger == 'manual').unlink()
        return notification

    def action_replenish_auto(self):
        self.trigger = 'auto'
        return self.action_replenish()

    @api.depends('product_id', 'location_id', 'product_id.stock_move_ids', 'product_id.stock_move_ids.state')
    def _compute_qty(self):
        orderpoints_contexts = defaultdict(lambda: self.env['stock.warehouse.orderpoint'])
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.qty_on_hand = False
                orderpoint.qty_forecast = False
                continue
            orderpoint_context = orderpoint._get_product_context()
            product_context = frozendict({**self.env.context, **orderpoint_context})
            orderpoints_contexts[product_context] |= orderpoint
        for orderpoint_context, orderpoints_by_context in orderpoints_contexts.items():
            products_qty = orderpoints_by_context.product_id.with_context(orderpoint_context)._product_available()
            products_qty_in_progress = orderpoints_by_context._quantity_in_progress()
            for orderpoint in orderpoints_by_context:
                orderpoint.qty_on_hand = products_qty[orderpoint.product_id.id]['qty_available']
                orderpoint.qty_forecast = products_qty[orderpoint.product_id.id]['virtual_available'] + products_qty_in_progress[orderpoint.id]

    @api.depends('qty_multiple', 'qty_forecast', 'product_min_qty', 'product_max_qty')
    def _compute_qty_to_order(self):
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.qty_to_order = False
                continue
            qty_to_order = 0.0
            rounding = orderpoint.product_uom.rounding
            if float_compare(orderpoint.qty_forecast, orderpoint.product_min_qty, precision_rounding=rounding) < 0:
                qty_to_order = max(orderpoint.product_min_qty, orderpoint.product_max_qty) - orderpoint.qty_forecast

                remainder = orderpoint.qty_multiple > 0 and qty_to_order % orderpoint.qty_multiple or 0.0
                if float_compare(remainder, 0.0, precision_rounding=rounding) > 0:
                    qty_to_order += orderpoint.qty_multiple - remainder
            orderpoint.qty_to_order = qty_to_order

    def _set_default_route_id(self):
        """ Write the `route_id` field on `self`. This method is intendend to be called on the
        orderpoints generated when openning the replenish report.
        """
        self = self.filtered(lambda o: not o.route_id)
        rules_groups = self.env['stock.rule'].read_group([
            ('route_id.product_selectable', '!=', False),
            ('location_id', 'in', self.location_id.ids),
            ('action', 'in', ['pull_push', 'pull'])
        ], ['location_id', 'route_id'], ['location_id', 'route_id'], lazy=False)
        for g in rules_groups:
            if not g.get('route_id'):
                continue
            orderpoints = self.filtered(lambda o: o.location_id == g['location_id'])
            orderpoints.route_id = g['route_id']

    def _get_product_context(self):
        """Used to call `virtual_available` when running an orderpoint."""
        self.ensure_one()
        return {
            'location': self.location_id.id,
            'to_date': datetime.combine(self.lead_days_date, time.max)
        }

    def _get_orderpoint_action(self):
        """Create manual orderpoints for missing product in each warehouses. It also removes
        orderpoints that have been replenish. In order to do it:
        - It uses the report.stock.quantity to find missing quantity per product/warehouse
        - It checks if orderpoint already exist to refill this location.
        - It checks if it exists other sources (e.g RFQ) tha refill the warehouse.
        - It creates the orderpoints for missing quantity that were not refill by an upper option.

        return replenish report ir.actions.act_window
        """
        action = self.env.ref('stock.action_orderpoint_replenish').read()[0]
        action['context'] = self.env.context
        orderpoints = self.env['stock.warehouse.orderpoint'].search([])
        # Remove previous automatically created orderpoint that has been refilled.
        to_remove = orderpoints.filtered(lambda o: o.create_uid.id == SUPERUSER_ID and o.qty_to_order <= 0.0 and o.trigger == 'manual')
        to_remove.unlink()
        orderpoints = orderpoints - to_remove
        to_refill = defaultdict(float)
        qty_by_product_warehouse = self.env['report.stock.quantity'].read_group(
            [('date', '=', fields.date.today()), ('state', '=', 'forecast')],
            ['product_id', 'product_qty', 'warehouse_id'],
            ['product_id', 'warehouse_id'], lazy=False)
        for group in qty_by_product_warehouse:
            warehouse_id = group.get('warehouse_id') and group['warehouse_id'][0]
            if group['product_qty'] >= 0.0 or not warehouse_id:
                continue
            to_refill[(group['product_id'][0], warehouse_id)] = group['product_qty']
        if not to_refill:
            return action

        # Remove incoming quantity from other otigin than moves (e.g RFQ)
        product_ids, warehouse_ids = zip(*to_refill)
        # lot_stock_ids = [lot_stock_id_by_warehouse[w] for w in warehouse_ids]
        dummy, qty_by_product_wh = self.env['product.product'].browse(product_ids)._get_quantity_in_progress(warehouse_ids=warehouse_ids)
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for (product, warehouse), product_qty in to_refill.items():
            qty_in_progress = qty_by_product_wh.get((product, warehouse)) or 0.0
            qty_in_progress += sum(orderpoints.filtered(
                lambda o: o.product_id.id == product and o.warehouse_id.id == warehouse
            ).mapped('qty_to_order'))
            # Add qty to order for other orderpoint under this warehouse.
            if not qty_in_progress:
                continue
            to_refill[(product, warehouse)] = product_qty + qty_in_progress
        to_refill = {k: v for k, v in to_refill.items() if float_compare(
            v, 0.0, precision_digits=rounding) < 0.0}

        lot_stock_id_by_warehouse = self.env['stock.warehouse'].search_read([
            ('id', 'in', [g[1] for g in to_refill.keys()])
        ], ['lot_stock_id'])
        lot_stock_id_by_warehouse = {w['id']: w['lot_stock_id'][0] for w in lot_stock_id_by_warehouse}

        product_qty_available = {}
        for warehouse, group in groupby(sorted(to_refill, key=lambda p_w: p_w[1]), key=lambda p_w: p_w[1]):
            products = self.env['product.product'].browse([p for p, w in group])
            products_qty_available_list = products.with_context(location=lot_stock_id_by_warehouse[warehouse]).mapped('qty_available')
            product_qty_available.update({(p.id, warehouse): q for p, q in zip(products, products_qty_available_list)})

        orderpoint_values_list = []
        for (product, warehouse), product_qty in to_refill.items():
            lot_stock_id = lot_stock_id_by_warehouse[warehouse]
            orderpoint = self.filtered(lambda o: o.product_id == product and o.location_id == lot_stock_id)
            if orderpoint:
                orderpoint[0].qty_forecast += product_qty
            else:
                orderpoint_values = self.env['stock.warehouse.orderpoint']._get_orderpoint_values(product, lot_stock_id)
                orderpoint_values.update({
                    'name': _('Replenishment Report'),
                    'warehouse_id': warehouse,
                    'company_id': self.env['stock.warehouse'].browse(warehouse).company_id.id,
                })
            orderpoint_values_list.append(orderpoint_values)

        orderpoints = self.env['stock.warehouse.orderpoint'].with_user(SUPERUSER_ID).create(orderpoint_values_list)
        for orderpoint in orderpoints:
            orderpoint.route_id = orderpoint.product_id.route_ids[:1]
        orderpoints.filtered(lambda o: not o.route_id)._set_default_route_id()
        return action

    @api.model
    def _get_orderpoint_values(self, product, location):
        return {
            'product_id': product,
            'location_id': location,
            'product_max_qty': 0.0,
            'product_min_qty': 0.0,
            'trigger': 'manual',
        }

    def _get_replenishment_order_notification(self):
        return False

    def _quantity_in_progress(self):
        """Return Quantities that are not yet in virtual stock but should be deduced from orderpoint rule
        (example: purchases created from orderpoints)"""
        return dict(self.mapped(lambda x: (x.id, 0.0)))

    def _prepare_procurement_values(self, date=False, group=False):
        """ Prepare specific key for moves or other components that will be created from a stock rule
        comming from an orderpoint. This method could be override in order to add other custom key that could
        be used in move/po creation.
        """
        date_planned = date or fields.Date.today()
        return {
            'route_ids': self.route_id,
            'date_planned': date_planned,
            'warehouse_id': self.warehouse_id,
            'orderpoint_id': self,
            'group_id': group or self.group_id,
        }

    def _procure_orderpoint_confirm(self, use_new_cursor=False, company_id=None, raise_user_error=True):
        """ Create procurements based on orderpoints.
        :param bool use_new_cursor: if set, use a dedicated cursor and auto-commit after processing
            1000 orderpoints.
            This is appropriate for batch jobs only.
        """
        self = self.with_company(company_id)
        orderpoints_noprefetch = self.read(['id'])
        orderpoints_noprefetch = [orderpoint['id'] for orderpoint in orderpoints_noprefetch]

        for orderpoints_batch in split_every(1000, orderpoints_noprefetch):
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))
            orderpoints_batch = self.env['stock.warehouse.orderpoint'].browse(orderpoints_batch)
            orderpoints_exceptions = []
            while orderpoints_batch:
                procurements = []
                for orderpoint in orderpoints_batch:
                    if float_compare(orderpoint.qty_to_order, 0.0, precision_rounding=orderpoint.product_uom.rounding) == 1:
                        date = datetime.combine(orderpoint.lead_days_date, time.min)
                        values = orderpoint._prepare_procurement_values(date=date)
                        procurements.append(self.env['procurement.group'].Procurement(
                            orderpoint.product_id, orderpoint.qty_to_order, orderpoint.product_uom,
                            orderpoint.location_id, orderpoint.name, orderpoint.name,
                            orderpoint.company_id, values))

                try:
                    with self.env.cr.savepoint():
                        self.env['procurement.group'].with_context(from_orderpoint=True).run(procurements, raise_user_error=raise_user_error)
                except ProcurementException as errors:
                    for procurement, error_msg in errors.procurement_exceptions:
                        orderpoints_exceptions += [(procurement.values.get('orderpoint_id'), error_msg)]
                    failed_orderpoints = self.env['stock.warehouse.orderpoint'].concat(*[o[0] for o in orderpoints_exceptions])
                    if not failed_orderpoints:
                        _logger.error('Unable to process orderpoints')
                        break
                    orderpoints_batch -= failed_orderpoints

                except OperationalError:
                    if use_new_cursor:
                        cr.rollback()
                        continue
                    else:
                        raise
                else:
                    orderpoints_batch._post_process_scheduler()
                    break

            # Log an activity on product template for failed orderpoints.
            for orderpoint, error_msg in orderpoints_exceptions:
                existing_activity = self.env['mail.activity'].search([
                    ('res_id', '=', orderpoint.product_id.product_tmpl_id.id),
                    ('res_model_id', '=', self.env.ref('product.model_product_template').id),
                    ('note', '=', error_msg)])
                if not existing_activity:
                    orderpoint.product_id.product_tmpl_id.activity_schedule(
                        'mail.mail_activity_data_warning',
                        note=error_msg,
                        user_id=orderpoint.product_id.responsible_id.id or SUPERUSER_ID,
                    )

            if use_new_cursor:
                cr.commit()
                cr.close()

        return {}

    def _post_process_scheduler(self):
        return True
