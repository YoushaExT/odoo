# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict
from datetime import datetime, time
from dateutil import relativedelta
from itertools import groupby
from psycopg2 import OperationalError

from odoo import SUPERUSER_ID, _, api, fields, models, registry
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import add, float_compare, frozendict, split_every

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

    @api.model
    def _domain_product_id(self):
        domain = "('type', '=', 'product')"
        if self.env.context.get('active_model') == 'product.template':
            product_template_id = self.env.context.get('active_id', False)
            domain = f"('product_tmpl_id', '=', {product_template_id})"
        elif self.env.context.get('default_product_id', False):
            product_id = self.env.context.get('default_product_id', False)
            domain = f"('id', '=', {product_id})"
        return f"[{domain}, '|', ('company_id', '=', False), ('company_id', '=', company_id)]"

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
        domain=lambda self: self._domain_product_id(),
        ondelete='cascade', required=True, check_company=True)
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
    lead_days_date = fields.Date(compute='_compute_lead_days')
    route_id = fields.Many2one(
        'stock.location.route', string='Preferred Route', domain="[('product_selectable', '=', True)]")
    qty_on_hand = fields.Float('On Hand', readonly=True, compute='_compute_qty')
    qty_forecast = fields.Float('Forecast', readonly=True, compute='_compute_qty')
    qty_to_order = fields.Float('To Order', compute='_compute_qty_to_order', store=True, readonly=False)

    _sql_constraints = [
        ('qty_multiple_check', 'CHECK( qty_multiple >= 0 )', 'Qty Multiple must be greater than or equal to zero.'),
        ('product_location_check', 'unique (product_id, location_id, company_id)', 'The combination of product and location must be unique.'),
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

    @api.depends('rule_ids', 'product_id.seller_ids', 'product_id.seller_ids.delay')
    def _compute_lead_days(self):
        for orderpoint in self.with_context(bypass_delay_description=True):
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.lead_days_date = False
                continue
            values = orderpoint._get_lead_days_values()
            lead_days, dummy = orderpoint.rule_ids._get_lead_days(orderpoint.product_id, **values)
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
            raise ValidationError(_('You have to select a product unit of measure that is in the same category as the default unit of measure of the product'))

    @api.onchange('location_id')
    def _onchange_location_id(self):
        warehouse = self.location_id.warehouse_id.id
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

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            self.qty_multiple = self._get_qty_multiple_to_order()

    def write(self, vals):
        if 'company_id' in vals:
            for orderpoint in self:
                if orderpoint.company_id.id != vals['company_id']:
                    raise UserError(_("Changing the company of this record is forbidden at this point, you should rather archive it and create a new one."))
        return super().write(vals)

    def action_product_forecast_report(self):
        self.ensure_one()
        action = self.product_id.action_product_forecast_report()
        action['context'] = {
            'active_id': self.product_id.id,
            'active_model': 'product.product',
        }
        warehouse = self.warehouse_id
        if warehouse:
            action['context']['warehouse'] = warehouse.id
        return action

    @api.model
    def action_open_orderpoints(self):
        return self._get_orderpoint_action()

    def action_stock_replenishment_info(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_stock_replenishment_info')
        action['name'] = _('Replenishment Information for %s in %s', self.product_id.display_name, self.warehouse_id.display_name)
        res = self.env['stock.replenishment.info'].create({
            'orderpoint_id': self.id,
        })
        action['res_id'] = res.id
        return action

    def action_replenish(self):
        try:
            self._procure_orderpoint_confirm(company_id=self.env.company)
        except UserError as e:
            if len(self) != 1:
                raise e
            raise RedirectWarning(e, {
                'name': self.product_id.display_name,
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'views': [(self.env.ref('product.product_normal_form_view').id, 'form')],
                'context': {'form_view_initial_mode': 'edit'}
            }, _('Edit Product'))
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

    @api.depends('product_id', 'location_id', 'product_id.stock_move_ids', 'product_id.stock_move_ids.state', 'product_id.stock_move_ids.product_uom_qty')
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
            products_qty = {
                p['id']: p for p in orderpoints_by_context.product_id.with_context(orderpoint_context).read(['qty_available', 'virtual_available'])
            }
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

    def _get_qty_multiple_to_order(self):
        """ Calculates the minimum quantity that can be ordered according to the PO UoM or BoM
        """
        self.ensure_one()
        return 0

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
            orderpoints = self.filtered(lambda o: o.location_id.id == g['location_id'][0])
            orderpoints.route_id = g['route_id']

    def _get_lead_days_values(self):
        self.ensure_one()
        return dict()

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
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context
        # Search also with archived ones to avoid to trigger product_location_check SQL constraints later
        # It means that when there will be a archived orderpoint on a location + product, the replenishment
        # report won't take in account this location + product and it won't create any manual orderpoint
        # In master: the active field should be remove
        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])
        # Remove previous automatically created orderpoint that has been refilled.
        orderpoints_removed = orderpoints._unlink_processed_orderpoints()
        orderpoints = orderpoints - orderpoints_removed
        to_refill = defaultdict(float)
        all_product_ids = []
        all_warehouse_ids = []
        # Take 3 months since it's the max for the forecast report
        to_date = add(fields.date.today(), months=3)
        qty_by_product_warehouse = self.env['report.stock.quantity'].read_group(
            [('date', '=', to_date), ('state', '=', 'forecast')],
            ['product_id', 'product_qty', 'warehouse_id'],
            ['product_id', 'warehouse_id'], lazy=False)
        for group in qty_by_product_warehouse:
            warehouse_id = group.get('warehouse_id') and group['warehouse_id'][0]
            if group['product_qty'] >= 0.0 or not warehouse_id:
                continue
            all_product_ids.append(group['product_id'][0])
            all_warehouse_ids.append(warehouse_id)
            to_refill[(group['product_id'][0], warehouse_id)] = group['product_qty']
        if not to_refill:
            return action

        # Recompute the forecasted quantity for missing product today but at this time
        # with their real lead days.
        key_to_remove = []
        pwh_per_day = defaultdict(list)
        for (product, warehouse) in to_refill.keys():
            product = self.env['product.product'].browse(product).with_prefetch(all_product_ids)
            warehouse = self.env['stock.warehouse'].browse(warehouse).with_prefetch(all_warehouse_ids)
            rules = product._get_rules_from_location(warehouse.lot_stock_id)
            lead_days = rules.with_context(bypass_delay_description=True)._get_lead_days(product)[0]
            pwh_per_day[(lead_days, warehouse)].append(product.id)
        # group product by lead_days and warehouse in order to read virtual_available
        # in batch
        for (days, warehouse), p_ids in pwh_per_day.items():
            products = self.env['product.product'].browse(p_ids)
            qties = products.with_context(
                warehouse=warehouse.id,
                to_date=fields.datetime.now() + relativedelta.relativedelta(days=days)
            ).read(['virtual_available'])
            for qty in qties:
                if float_compare(qty['virtual_available'], 0, precision_rounding=product.uom_id.rounding) >= 0:
                    key_to_remove.append((qty['id'], warehouse.id))
                else:
                    to_refill[(qty['id'], warehouse.id)] = qty['virtual_available']

        for key in key_to_remove:
            del to_refill[key]
        if not to_refill:
            return action

        # Remove incoming quantity from other origin than moves (e.g RFQ)
        product_ids, warehouse_ids = zip(*to_refill)
        dummy, qty_by_product_wh = self.env['product.product'].browse(product_ids)._get_quantity_in_progress(warehouse_ids=warehouse_ids)
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        # Group orderpoint by product-warehouse
        orderpoint_by_product_warehouse = self.env['stock.warehouse.orderpoint'].read_group(
            [('id', 'in', orderpoints.ids)],
            ['product_id', 'warehouse_id', 'qty_to_order:sum'],
            ['product_id', 'warehouse_id'], lazy=False)
        orderpoint_by_product_warehouse = {
            (record.get('product_id')[0], record.get('warehouse_id')[0]): record.get('qty_to_order')
            for record in orderpoint_by_product_warehouse
        }
        for (product, warehouse), product_qty in to_refill.items():
            qty_in_progress = qty_by_product_wh.get((product, warehouse)) or 0.0
            qty_in_progress += orderpoint_by_product_warehouse.get((product, warehouse), 0.0)
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

        # With archived ones to avoid `product_location_check` SQL constraints
        orderpoint_by_product_location = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).read_group(
            [('id', 'in', orderpoints.ids)],
            ['product_id', 'location_id', 'ids:array_agg(id)'],
            ['product_id', 'location_id'], lazy=False)
        orderpoint_by_product_location = {
            (record.get('product_id')[0], record.get('location_id')[0]): record.get('ids')[0]
            for record in orderpoint_by_product_location
        }

        orderpoint_values_list = []
        for (product, warehouse), product_qty in to_refill.items():
            lot_stock_id = lot_stock_id_by_warehouse[warehouse]
            orderpoint_id = orderpoint_by_product_location.get((product, lot_stock_id))
            if orderpoint_id:
                self.env['stock.warehouse.orderpoint'].browse(orderpoint_id).qty_forecast += product_qty
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
            orderpoint.route_id = orderpoint.product_id.route_ids[:1] or orderpoint._set_default_route_id()
            orderpoint.qty_multiple = orderpoint._get_qty_multiple_to_order()
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

    @api.autovacuum
    def _unlink_processed_orderpoints(self):
        domain = [
            ('create_uid', '=', SUPERUSER_ID),
            ('trigger', '=', 'manual'),
            ('qty_to_order', '<=', 0)
        ]
        if self.ids:
            expression.AND([domain, [('ids', 'in', self.ids)]])
        orderpoints_to_remove = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search(domain)
        # Remove previous automatically created orderpoint that has been refilled.
        orderpoints_to_remove.unlink()
        return orderpoints_to_remove

    def _prepare_procurement_values(self, date=False, group=False):
        """ Prepare specific key for moves or other components that will be created from a stock rule
        comming from an orderpoint. This method could be override in order to add other custom key that could
        be used in move/po creation.
        """
        date_planned = date or fields.Date.today()
        return {
            'route_ids': self.route_id,
            'date_planned': date_planned,
            'date_deadline': date or False,
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

        for orderpoints_batch_ids in split_every(1000, self.ids):
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))
            orderpoints_batch = self.env['stock.warehouse.orderpoint'].browse(orderpoints_batch_ids)
            all_orderpoints_exceptions = []
            while orderpoints_batch:
                procurements = []
                for orderpoint in orderpoints_batch:
                    origins = orderpoint.env.context.get('origins', {}).get(orderpoint.id, False)
                    if origins:
                        origin = '%s - %s' % (orderpoint.display_name, ','.join(origins))
                    else:
                        origin = orderpoint.name
                    if float_compare(orderpoint.qty_to_order, 0.0, precision_rounding=orderpoint.product_uom.rounding) == 1:
                        date = datetime.combine(orderpoint.lead_days_date, time.min)
                        values = orderpoint._prepare_procurement_values(date=date)
                        procurements.append(self.env['procurement.group'].Procurement(
                            orderpoint.product_id, orderpoint.qty_to_order, orderpoint.product_uom,
                            orderpoint.location_id, orderpoint.name, origin,
                            orderpoint.company_id, values))

                try:
                    with self.env.cr.savepoint():
                        self.env['procurement.group'].with_context(from_orderpoint=True).run(procurements, raise_user_error=raise_user_error)
                except ProcurementException as errors:
                    orderpoints_exceptions = []
                    for procurement, error_msg in errors.procurement_exceptions:
                        orderpoints_exceptions += [(procurement.values.get('orderpoint_id'), error_msg)]
                    all_orderpoints_exceptions += orderpoints_exceptions
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
            for orderpoint, error_msg in all_orderpoints_exceptions:
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
                _logger.info("A batch of %d orderpoints is processed and committed", len(orderpoints_batch_ids))

        return {}

    def _post_process_scheduler(self):
        return True
