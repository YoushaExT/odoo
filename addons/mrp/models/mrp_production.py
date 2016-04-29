# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from collections import OrderedDict

import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare, float_is_zero
from openerp import SUPERUSER_ID
from openerp.exceptions import UserError, AccessError

from odoo import api, fields, models, _


class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _name = 'mrp.production'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Manufacturing Order'
    _date_name = 'date_planned'
    _order = 'priority desc, date_planned asc'

    @api.model
    def _get_default_location_src_id(self):
        location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if location:
            try:
                location.check_access_rule('read')
                return location.id
            except AccessError:
                pass
        return False

    @api.model
    def _get_default_location_dest_id(self):
        return self._get_default_location_src_id()

    name = fields.Char(
        'Reference',
        copy=False, default=lambda self: self.env['ir.sequence'].next_by_code('mrp.production') or '/',
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    origin = fields.Char(
        'Source Document',
        copy=False, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Reference of the document that generated this production order request.")
    priority = fields.Selection([
        ('0', 'Not urgent'),
        ('1', 'Normal'),
        ('2', 'Urgent'),
        ('3', 'Very Urgent')], 'Priority',
        default='1', index=True, readonly=True,
        states=dict.fromkeys(['draft', 'confirmed'], [('readonly', False)]))

    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', 'in', ['product', 'consu'])],
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product Template',
        related='product_id.product_tmpl_id')
    product_qty = fields.Float(
        'Product Quantity',
        default=1.0, digits_compute=dp.get_precision('Product Unit of Measure'),
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    product_uom = fields.Many2one(
        'product.uom', 'Product Unit of Measure',
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    progress = fields.Float('Production progress', compute='_compute_progress')

    location_src_id = fields.Many2one(
        'stock.location', 'Raw Materials Location',
        default=_get_default_location_src_id,
        readonly=True,  required=True,
        states={'draft': [('readonly', False)]},
        help="Location where the system will look for components.")
    location_dest_id = fields.Many2one(
        'stock.location', 'Finished Products Location',
        default=_get_default_location_dest_id,
        readonly=True,  required=True,
        states={'draft': [('readonly', False)]},
        help="Location where the system will stock the finished products.")
    date_planned = fields.Datetime(
        'Scheduled Date',
        copy=False, default=fields.Datetime.now,
        index=True, required=True, readonly=True,
        states={'draft': [('readonly', False)]})
    date_start = fields.Datetime('Start Date', copy=False, index=True, readonly=True)
    date_finished = fields.Datetime('End Date', copy=False, index=True, readonly=True)
    bom_id = fields.Many2one(
        'mrp.bom', 'Bill of Material',
        readonly=True, states={'draft': [('readonly', False)]},
        help="Bill of Materials allow you to define the list of required raw materials to make a finished product.")
    routing_id = fields.Many2one(
        'mrp.routing', 'Routing',
        on_delete='set null', readonly=True,
        states={'draft': [('readonly', False)]},
        help="The list of operations (list of work centers) to produce the finished product. The routing "
             "is mainly used to compute work center costs during operations and to plan future loads on "
             "work centers based on production plannification.")
    move_prod_id = fields.Many2one(
        'stock.move', 'Product Move',
        copy=False, readonly=True)
    move_lines = fields.One2many(
        'stock.move', 'raw_material_production_id', 'Products to Consume',
        domain=[('state', 'not in', ('done', 'cancel'))],
        readonly=True, states={'draft': [('readonly', False)]})
    move_lines2 = fields.One2many(
        'stock.move', 'raw_material_production_id', 'Consumed Products',
        domain=[('state', 'in', ('done', 'cancel'))],
        readonly=True)
    move_created_ids = fields.One2many(
        'stock.move', 'production_id', 'Products to Produce',
        domain=[('state', 'not in', ('done', 'cancel'))],
        readonly=True)
    move_created_ids2 = fields.One2many(
        'stock.move', 'production_id', 'Produced Products',
        domain=[('state', 'in', ('done', 'cancel'))],
        readonly=True)
    product_lines = fields.One2many(
        'mrp.production.product.line', 'production_id', 'Scheduled goods',
        readonly=True)
    workcenter_lines = fields.One2many(
        'mrp.production.workcenter.line', 'production_id', 'Work Centers Utilisation',
        readonly=True,
        states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'New'),
        ('cancel', 'Cancelled'),
        ('confirmed', 'Awaiting Raw Materials'),
        ('ready', 'Ready to Produce'),
        ('in_production', 'Production Started'),
        ('done', 'Done')], string='Status',
        copy=False, default='draft', readonly=True, track_visibility='onchange',
        help="When the production order is created the status is set to 'Draft'.\n"
             "If the order is confirmed the status is set to 'Waiting Goods.\n"
             "If any exceptions are there, the status is set to 'Picking Exception.\n"
             "If the stock is available then the status is set to 'Ready to Produce.\n"
             "When the production gets started then the status is set to 'In Production.\n"
             "When the production is over, the status is set to 'Done'.")
    hour_total = fields.Float('Total Hours', compute='_compute_hour_total', store=True)
    cycle_total = fields.Float('Total Cycles', compute='_compute_cycle_total', store=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self._uid)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.production'),
        required=True)
    ready_production = fields.Boolean(
        "Ready for production", compute='_compute_ready_production', store=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per Company!'),
    ]

    @api.one
    def _compute_progress(self):
        """ Return product quantity percentage """
        if self.product_qty:
            self.progress = self.move_created_ids2 and sum(
                move.product_qty for move in self.move_created_ids2.filtered(
                    lambda move: not move.scrapped and move.product_id == self.product_id)
                ) or 0.0 / self.product_qty

    @api.one
    @api.depends('workcenter_lines.hour')
    def _compute_hour_total(self):
        self.hour_total = self.workcenter_lines and sum(wc_line.hour for wc_line in self.workcenter_lines) or 0.0

    @api.one
    @api.depends('workcenter_lines.cycle')
    def _compute_cycle_total(self):
        self.cycle_total = self.workcenter_lines and sum(wc_line.cycle for wc_line in self.workcenter_lines) or 0.0

    @api.one
    @api.depends('move_lines.state')
    def _compute_ready_production(self):
        """ Test whether all the consume lines are assigned """
        self.ready_production = self.move_lines and all(move.state == 'assigned' for move in self.move_lines)

    @api.multi
    @api.constrains('product_qty')
    def _check_qty(self):
        if any(production.product_qty <= 0 for production in self):
            raise UserError(_('Order quantity cannot be negative or zero!'))

    @api.onchange('location_src_id', 'location_dest_id')
    def onchange_location_id(self):
        """ Changes destination location if source location is changed. """
        if self.location_src_id and not self.location_dest_id:
            self.location_dest_id = self.location_src_id.id

    @api.onchange('product_id')
    def onchange_product_id(self):
        """ Finds UoM of changed product. """
        if not self.product_id:
            self.bom_id = False
        else:
            bom = self.env['mrp.bom']._bom_find(product_id=self.product_id.id, properties=[])
            self.bom_id = bom.id
        self.product_uom = self.product_id.uom_id.id
        self.product_tmpl_id = self.product_id.product_tmpl_id.id

    @api.onchange('bom_id')
    def onchange_bom_id(self):
        """ Finds routing for changed BoM. """
        self.routing_id = self.bom_id.routing_id.id

    @api.model
    def create(self, values):
        if values.get('product_id') and 'product_uom' not in values:
            values['product_uom'] = self.env['product.product'].browse(values['product_id']).uom_id.id
        return super(MrpProduction, self).create(values)

    @api.multi
    def unlink(self):
        if any(production.state not in ('draft', 'cancel') for production in self):
            raise UserError(_('Cannot delete a manufacturing order not in draft or cancel state'))
        return super(MrpProduction, self).unlink()


    def _prepare_lines(self, cr, uid, production, properties=None, context=None):
        # search BoM structure and route
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        bom_point = production.bom_id
        bom_id = production.bom_id.id
        if not bom_point:
            bom_id = bom_obj._bom_find(cr, uid, product_id=production.product_id.id, properties=properties, context=context)
            if bom_id:
                bom_point = bom_obj.browse(cr, uid, bom_id)
                routing_id = bom_point.routing_id.id or False
                self.write(cr, uid, [production.id], {'bom_id': bom_id, 'routing_id': routing_id})

        if not bom_id:
            raise UserError(_("Cannot find a bill of material for this product."))

        # get components and workcenter_lines from BoM structure
        factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, bom_point.product_uom.id)
        # product_lines, workcenter_lines
        return bom_obj._bom_explode(cr, uid, bom_point, production.product_id, factor / bom_point.product_qty, properties, routing_id=production.routing_id.id, context=context)

    def _action_compute_lines(self, cr, uid, ids, properties=None, context=None):
        """ Compute product_lines and workcenter_lines from BoM structure
        @return: product_lines
        """
        if properties is None:
            properties = []
        results = []
        prod_line_obj = self.pool.get('mrp.production.product.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for production in self.browse(cr, uid, ids, context=context):
            #unlink product_lines
            prod_line_obj.unlink(cr, SUPERUSER_ID, [line.id for line in production.product_lines], context=context)
            #unlink workcenter_lines
            workcenter_line_obj.unlink(cr, SUPERUSER_ID, [line.id for line in production.workcenter_lines], context=context)

            res = self._prepare_lines(cr, uid, production, properties=properties, context=context)
            results = res[0] # product_lines
            results2 = res[1] # workcenter_lines

            # reset product_lines in production order
            for line in results:
                line['production_id'] = production.id
                prod_line_obj.create(cr, uid, line)

            #reset workcenter_lines in production order
            for line in results2:
                line['production_id'] = production.id
                workcenter_line_obj.create(cr, uid, line, context)
        return results

    @api.multi
    def action_compute(self, properties=None):
        """ Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        return len(self._action_compute_lines(properties=properties))

    def action_cancel(self, cr, uid, ids, context=None):
        """ Cancels the production order and related stock moves.
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        for production in self.browse(cr, uid, ids, context=context):
            if production.move_created_ids:
                move_obj.action_cancel(cr, uid, [x.id for x in production.move_created_ids])
            procs = proc_obj.search(cr, uid, [('move_dest_id', 'in', [x.id for x in production.move_lines])], context=context)
            if procs:
                proc_obj.cancel(cr, uid, procs, context=context)
            move_obj.action_cancel(cr, uid, [x.id for x in production.move_lines])
        self.write(cr, uid, ids, {'state': 'cancel'})
        # Put related procurements in exception
        proc_obj = self.pool.get("procurement.order")
        procs = proc_obj.search(cr, uid, [('production_id', 'in', ids)], context=context)
        if procs:
            proc_obj.message_post(cr, uid, procs, body=_('Manufacturing order cancelled.'), context=context)
            proc_obj.write(cr, uid, procs, {'state': 'exception'}, context=context)
        return True

    def action_ready(self, cr, uid, ids, context=None):
        """ Changes the production state to Ready and location id of stock move.
        @return: True
        """
        move_obj = self.pool.get('stock.move')
        self.write(cr, uid, ids, {'state': 'ready'})

        for production in self.browse(cr, uid, ids, context=context):
            if not production.move_created_ids:
                self._make_production_produce_line(cr, uid, production, context=context)

            if production.move_prod_id and production.move_prod_id.location_id.id != production.location_dest_id.id:
                move_obj.write(cr, uid, [production.move_prod_id.id],
                        {'location_id': production.location_dest_id.id})
        return True

    def _compute_costs_from_production(self, cr, uid, ids, context=None):
        """ Generate workcenter costs in analytic accounts"""
        for production in self.browse(cr, uid, ids):
            total_cost = self._costs_generate(cr, uid, production)

    def action_production_end(self, cr, uid, ids, context=None):
        """ Changes production state to Finish and writes finished date.
        @return: True
        """
        self._compute_costs_from_production(cr, uid, ids, context)
        write_res = self.write(cr, uid, ids, {'state': 'done', 'date_finished': time.strftime('%Y-%m-%d %H:%M:%S')})
        # Check related procurements
        proc_obj = self.pool.get("procurement.order")
        procs = proc_obj.search(cr, uid, [('production_id', 'in', ids)], context=context)
        proc_obj.check(cr, uid, procs, context=context)
        return write_res

    def test_production_done(self, cr, uid, ids):
        """ Tests whether production is done or not.
        @return: True or False
        """
        res = True
        for production in self.browse(cr, uid, ids):
            if production.move_lines:
                res = False

            if production.move_created_ids:
                res = False
        return res

    def _get_produced_qty(self, cr, uid, production, context=None):
        ''' returns the produced quantity of product 'production.product_id' for the given production, in the product UoM
        '''
        produced_qty = 0
        for produced_product in production.move_created_ids2:
            if (produced_product.scrapped) or (produced_product.product_id.id != production.product_id.id):
                continue
            produced_qty += produced_product.product_qty
        return produced_qty

    def _get_consumed_data(self, cr, uid, production, context=None):
        ''' returns a dictionary containing for each raw material of the given production, its quantity already consumed (in the raw material UoM)
        '''
        consumed_data = {}
        # Calculate already consumed qtys
        for consumed in production.move_lines2:
            if consumed.scrapped:
                continue
            if not consumed_data.get(consumed.product_id.id, False):
                consumed_data[consumed.product_id.id] = 0
            consumed_data[consumed.product_id.id] += consumed.product_qty
        return consumed_data

    def _calculate_qty(self, cr, uid, production, product_qty=0.0, context=None):
        """
            Calculates the quantity still needed to produce an extra number of products
            product_qty is in the uom of the product
        """
        quant_obj = self.pool.get("stock.quant")
        uom_obj = self.pool.get("product.uom")
        produced_qty = self._get_produced_qty(cr, uid, production, context=context)
        consumed_data = self._get_consumed_data(cr, uid, production, context=context)

        #In case no product_qty is given, take the remaining qty to produce for the given production
        if not product_qty:
            product_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, production.product_id.uom_id.id) - produced_qty
        production_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, production.product_id.uom_id.id)

        scheduled_qty = OrderedDict()
        for scheduled in production.product_lines:
            if scheduled.product_id.type not in ['product', 'consu']:
                continue
            qty = uom_obj._compute_qty(cr, uid, scheduled.product_uom.id, scheduled.product_qty, scheduled.product_id.uom_id.id)
            if scheduled_qty.get(scheduled.product_id.id):
                scheduled_qty[scheduled.product_id.id] += qty
            else:
                scheduled_qty[scheduled.product_id.id] = qty
        dicts = OrderedDict()
        # Find product qty to be consumed and consume it
        for product_id in scheduled_qty.keys():

            consumed_qty = consumed_data.get(product_id, 0.0)
            
            # qty available for consume and produce
            sched_product_qty = scheduled_qty[product_id]
            qty_avail = sched_product_qty - consumed_qty
            if qty_avail <= 0.0:
                # there will be nothing to consume for this raw material
                continue

            if not dicts.get(product_id):
                dicts[product_id] = {}

            # total qty of consumed product we need after this consumption
            if product_qty + produced_qty <= production_qty:
                total_consume = ((product_qty + produced_qty) * sched_product_qty / production_qty)
            else:
                total_consume = sched_product_qty
            qty = total_consume - consumed_qty

            # Search for quants related to this related move
            for move in production.move_lines:
                if qty <= 0.0:
                    break
                if move.product_id.id != product_id:
                    continue

                q = min(move.product_qty, qty)
                quants = quant_obj.quants_get_preferred_domain(cr, uid, q, move, domain=[('qty', '>', 0.0)],
                                                     preferred_domain_list=[[('reservation_id', '=', move.id)]], context=context)
                for quant, quant_qty in quants:
                    if quant:
                        lot_id = quant.lot_id.id
                        if not product_id in dicts.keys():
                            dicts[product_id] = {lot_id: quant_qty}
                        elif lot_id in dicts[product_id].keys():
                            dicts[product_id][lot_id] += quant_qty
                        else:
                            dicts[product_id][lot_id] = quant_qty
                        qty -= quant_qty
            if float_compare(qty, 0, self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')) == 1:
                if dicts[product_id].get(False):
                    dicts[product_id][False] += qty
                else:
                    dicts[product_id][False] = qty

        consume_lines = []
        for prod in dicts.keys():
            for lot, qty in dicts[prod].items():
                consume_lines.append({'product_id': prod, 'product_qty': qty, 'lot_id': lot})
        return consume_lines

    def _calculate_produce_line_qty(self, cr, uid, move, quantity, context=None):
        """ Compute the quantity and remainig quantity of products to produce.
        :param move: Record set of stock move that needs to be produced, identify the product to produce.
        :param quantity: specify quantity to produce in the uom of the production order.
        :return: The quantity and remaining quantity of product produce.
        """
        qty = min(quantity, move.product_qty)
        remaining_qty = quantity - qty
        return qty, remaining_qty

    def _calculate_total_cost(self, cr, uid, total_consume_moves, context=None):
        total_cost = 0
        for consumed_move in self.pool['stock.move'].browse(cr, uid, total_consume_moves, context=context):
            total_cost += sum([x.inventory_value for x in consumed_move.quant_ids if x.qty > 0])
        return total_cost

    def _calculate_workcenter_cost(self, cr, uid, production_id, context=None):
        """ Compute the planned production cost from the workcenters """
        production = self.browse(cr, uid, production_id, context=context)
        total_cost = 0.0
        for wc_line in production.workcenter_lines:
            wc = wc_line.workcenter_id
            total_cost += wc_line.hour*wc.costs_hour + wc_line.cycle*wc.costs_cycle
        return total_cost

    def action_produce(self, cr, uid, ids, production_qty, production_mode, wiz=False, context=None):
        """ To produce final product based on production mode (consume/consume&produce).
        If Production mode is consume, all stock move lines of raw materials will be done/consumed.
        If Production mode is consume & produce, all stock move lines of raw materials will be done/consumed
        and stock move lines of final product will be also done/produced.
        @param production_id: the ID of mrp.production object
        @param production_qty: specify qty to produce in the uom of the production order
        @param production_mode: specify production mode (consume/consume&produce).
        @param wiz: the mrp produce product wizard, which will tell the amount of consumed products needed
        @return: True
        """
        stock_mov_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get("product.uom")
        production = self.browse(cr, uid, ids[0], context=context)
        production_qty_uom = uom_obj._compute_qty(cr, uid, production.product_uom.id, production_qty, production.product_id.uom_id.id)
        precision = self.pool['decimal.precision'].precision_get(cr, uid, 'Product Unit of Measure')

        main_production_move = False
        if production_mode == 'consume_produce':
            for produce_product in production.move_created_ids:
                if produce_product.product_id.id == production.product_id.id:
                    main_production_move = produce_product.id

        total_consume_moves = set()
        if production_mode in ['consume', 'consume_produce']:
            if wiz:
                consume_lines = []
                for cons in wiz.consume_lines:
                    consume_lines.append({'product_id': cons.product_id.id, 'lot_id': cons.lot_id.id, 'product_qty': cons.product_qty})
            else:
                consume_lines = self._calculate_qty(cr, uid, production, production_qty_uom, context=context)
            for consume in consume_lines:
                remaining_qty = consume['product_qty']
                for raw_material_line in production.move_lines:
                    if raw_material_line.state in ('done', 'cancel'):
                        continue
                    if remaining_qty <= 0:
                        break
                    if consume['product_id'] != raw_material_line.product_id.id:
                        continue
                    consumed_qty = min(remaining_qty, raw_material_line.product_qty)
                    stock_mov_obj.action_consume(cr, uid, [raw_material_line.id], consumed_qty, raw_material_line.location_id.id,
                                                 restrict_lot_id=consume['lot_id'], consumed_for=main_production_move, context=context)
                    total_consume_moves.add(raw_material_line.id)
                    remaining_qty -= consumed_qty
                if not float_is_zero(remaining_qty, precision_digits=precision):
                    #consumed more in wizard than previously planned
                    product = self.pool.get('product.product').browse(cr, uid, consume['product_id'], context=context)
                    extra_move_id = self._make_consume_line_from_data(cr, uid, production, product, product.uom_id.id, remaining_qty, context=context)
                    stock_mov_obj.write(cr, uid, [extra_move_id], {'restrict_lot_id': consume['lot_id'],
                                                                    'consumed_for': main_production_move}, context=context)
                    stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)
                    total_consume_moves.add(extra_move_id)

        if production_mode == 'consume_produce':
            # add production lines that have already been consumed since the last 'consume & produce'
            last_production_date = production.move_created_ids2 and max(production.move_created_ids2.mapped('date')) or False
            already_consumed_lines = production.move_lines2.filtered(lambda l: l.date > last_production_date)
            total_consume_moves = total_consume_moves.union(already_consumed_lines.ids)

            price_unit = 0
            for produce_product in production.move_created_ids:
                is_main_product = (produce_product.product_id.id == production.product_id.id) and production.product_id.cost_method=='real'
                if is_main_product:
                    total_cost = self._calculate_total_cost(cr, uid, list(total_consume_moves), context=context)
                    production_cost = self._calculate_workcenter_cost(cr, uid, production.id, context=context)
                    price_unit = (total_cost + production_cost) / production_qty_uom

                lot_id = False
                if wiz:
                    lot_id = wiz.lot_id.id
                qty, remaining_qty = self._calculate_produce_line_qty(cr, uid, produce_product, production_qty_uom, context=context)
                if is_main_product and price_unit:
                    stock_mov_obj.write(cr, uid, [produce_product.id], {'price_unit': price_unit}, context=context)
                new_moves = stock_mov_obj.action_consume(cr, uid, [produce_product.id], qty,
                                                         location_id=produce_product.location_id.id, restrict_lot_id=lot_id, context=context)
                stock_mov_obj.write(cr, uid, new_moves, {'production_id': production.id}, context=context)
                if not float_is_zero(remaining_qty, precision_digits=precision):
                    # In case you need to make more than planned
                    #consumed more in wizard than previously planned
                    extra_move_id = stock_mov_obj.copy(cr, uid, produce_product.id, default={'product_uom_qty': remaining_qty,
                                                                                             'production_id': production.id}, context=context)
                    if is_main_product:
                        stock_mov_obj.write(cr, uid, [extra_move_id], {'price_unit': price_unit}, context=context)
                    stock_mov_obj.action_confirm(cr, uid, [extra_move_id], context=context)
                    stock_mov_obj.action_done(cr, uid, [extra_move_id], context=context)

        self.message_post(cr, uid, production.id, body=_("%s produced") % self._description, context=context)

        # Remove remaining products to consume if no more products to produce
        if not production.move_created_ids and production.move_lines:
            stock_mov_obj.action_cancel(cr, uid, [x.id for x in production.move_lines], context=context)

        self.signal_workflow(cr, uid, [production.id], 'button_produce_done')
        return True

    def _costs_generate(self, cr, uid, production):
        """ Calculates total costs at the end of the production.
        @param production: Id of production order.
        @return: Calculated amount.
        """
        amount = 0.0
        analytic_line_obj = self.pool.get('account.analytic.line')
        for wc_line in production.workcenter_lines:
            wc = wc_line.workcenter_id
            if wc.costs_general_account_id:
                # Cost per hour
                value = wc_line.hour * wc.costs_hour
                account = wc.costs_hour_account_id.id
                if value and account:
                    amount += value
                    # we user SUPERUSER_ID as we do not garantee an mrp user
                    # has access to account analytic lines but still should be
                    # able to produce orders
                    analytic_line_obj.create(cr, SUPERUSER_ID, {
                        'name': wc_line.name + ' (H)',
                        'amount': value,
                        'account_id': account,
                        'general_account_id': wc.costs_general_account_id.id,
                        'ref': wc.code,
                        'product_id': wc.product_id.id,
                        'unit_amount': wc_line.hour,
                        'product_uom_id': wc.product_id and wc.product_id.uom_id.id or False
                    })
                # Cost per cycle
                value = wc_line.cycle * wc.costs_cycle
                account = wc.costs_cycle_account_id.id
                if value and account:
                    amount += value
                    analytic_line_obj.create(cr, SUPERUSER_ID, {
                        'name': wc_line.name + ' (C)',
                        'amount': value,
                        'account_id': account,
                        'general_account_id': wc.costs_general_account_id.id,
                        'ref': wc.code,
                        'product_id': wc.product_id.id,
                        'unit_amount': wc_line.cycle,
                        'product_uom_id': wc.product_id and wc.product_id.uom_id.id or False
                    })
        return amount

    @api.multi
    def action_in_production(self):
        """ Changes state to In Production and writes starting date. """
        return self.write({'state': 'in_production', 'date_start': fields.Datetime.now()})

    def consume_lines_get(self, cr, uid, ids, *args):
        # TDE: DEAD CODE
        res = []
        for order in self.browse(cr, uid, ids, context={}):
            res += [x.id for x in order.move_lines]
        return res

    @api.multi
    def test_ready(self):
        return all(production.ready_production for production in self)

    def _make_production_produce_line(self, cr, uid, production, context=None):
        stock_move = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        source_location_id = production.product_id.property_stock_production.id
        destination_location_id = production.location_dest_id.id
        procs = proc_obj.search(cr, uid, [('production_id', '=', production.id)], context=context)
        procurement = procs and\
            proc_obj.browse(cr, uid, procs[0], context=context) or False
        data = {
            'name': production.name,
            'date': production.date_planned,
            'date_expected': production.date_planned,
            'product_id': production.product_id.id,
            'product_uom': production.product_uom.id,
            'product_uom_qty': production.product_qty,
            'location_id': source_location_id,
            'location_dest_id': destination_location_id,
            'move_dest_id': production.move_prod_id.id,
            'procurement_id': procurement and procurement.id,
            'company_id': production.company_id.id,
            'production_id': production.id,
            'origin': production.name,
            'group_id': procurement and procurement.group_id.id,
        }
        move_id = stock_move.create(cr, uid, data, context=context)
        # TDE FIXME: necessary return ?
        stock_move.action_confirm(cr, uid, [move_id], context=context)
        return move_id

    def _get_raw_material_procure_method(self, cr, uid, product, location_id=False, location_dest_id=False, context=None):
        '''This method returns the procure_method to use when creating the stock move for the production raw materials
        Besides the standard configuration of looking if the product or product category has the MTO route,
        you can also define a rule e.g. from Stock to Production (which might be used in the future like the sale orders)
        '''
        warehouse_obj = self.pool['stock.warehouse']
        routes = product.route_ids + product.categ_id.total_route_ids

        if location_id and location_dest_id:
            pull_obj = self.pool['procurement.rule']
            pulls = pull_obj.search(cr, uid, [('route_id', 'in', [x.id for x in routes]),
                                            ('location_id', '=', location_dest_id),
                                            ('location_src_id', '=', location_id)], limit=1, context=context)
            if pulls:
                return pull_obj.browse(cr, uid, pulls[0], context=context).procure_method

        try:
            mto_route = warehouse_obj._get_mto_route(cr, uid, context=context)
        except:
            return "make_to_stock"

        if mto_route in [x.id for x in routes]:
            return "make_to_order"
        return "make_to_stock"

    def _create_previous_move(self, cr, uid, move_id, product, source_location_id, dest_location_id, context=None):
        '''
        When the routing gives a different location than the raw material location of the production order, 
        we should create an extra move from the raw material location to the location of the routing, which 
        precedes the consumption line (chained).  The picking type depends on the warehouse in which this happens
        and the type of locations. 
        '''
        loc_obj = self.pool.get("stock.location")
        stock_move = self.pool.get('stock.move')
        type_obj = self.pool.get('stock.picking.type')
        # Need to search for a picking type
        move = stock_move.browse(cr, uid, move_id, context=context)
        src_loc = loc_obj.browse(cr, uid, source_location_id, context=context)
        dest_loc = loc_obj.browse(cr, uid, dest_location_id, context=context)
        code = stock_move.get_code_from_locs(cr, uid, [move.id], src_loc, dest_loc, context=context)
        if code == 'outgoing':
            check_loc = src_loc
        else:
            check_loc = dest_loc
        wh = loc_obj.get_warehouse(cr, uid, [check_loc.id], context=context)
        domain = [('code', '=', code)]
        if wh: 
            domain += [('warehouse_id', '=', wh)]
        types = type_obj.search(cr, uid, domain, context=context)
        move = stock_move.copy(cr, uid, move_id, default = {
            'location_id': source_location_id,
            'location_dest_id': dest_location_id,
            'procure_method': self._get_raw_material_procure_method(cr, uid, product, location_id=source_location_id,
                                                                    location_dest_id=dest_location_id, context=context),
            'raw_material_production_id': False, 
            'move_dest_id': move_id,
            'picking_type_id': types and types[0] or False,
        }, context=context)
        return move

    def _make_consume_line_from_data(self, cr, uid, production, product, uom_id, qty, context=None):
        stock_move = self.pool.get('stock.move')
        loc_obj = self.pool.get('stock.location')
        # Internal shipment is created for Stockable and Consumer Products
        if product.type not in ('product', 'consu'):
            return False
        # Take routing location as a Source Location.
        source_location_id = production.location_src_id.id
        prod_location_id = source_location_id
        prev_move= False
        if production.bom_id.routing_id and production.bom_id.routing_id.location_id and production.bom_id.routing_id.location_id.id != source_location_id:
            source_location_id = production.bom_id.routing_id.location_id.id
            prev_move = True

        destination_location_id = production.product_id.property_stock_production.id
        move_id = stock_move.create(cr, uid, {
            'name': production.name,
            'date': production.date_planned,
            'date_expected': production.date_planned,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': uom_id,
            'location_id': source_location_id,
            'location_dest_id': destination_location_id,
            'company_id': production.company_id.id,
            'procure_method': prev_move and 'make_to_stock' or self._get_raw_material_procure_method(cr, uid, product, location_id=source_location_id,
                                                                                                     location_dest_id=destination_location_id, context=context), #Make_to_stock avoids creating procurement
            'raw_material_production_id': production.id,
            #this saves us a browse in create()
            'price_unit': product.standard_price,
            'origin': production.name,
            'warehouse_id': loc_obj.get_warehouse(cr, uid, [production.location_src_id.id], context=context),
            'group_id': production.move_prod_id.group_id.id,
        }, context=context)
        
        if prev_move:
            prev_move = self._create_previous_move(cr, uid, move_id, product, prod_location_id, source_location_id, context=context)
            stock_move.action_confirm(cr, uid, [prev_move], context=context)
        return move_id

    def _make_production_consume_line(self, cr, uid, line, context=None):
        return self._make_consume_line_from_data(cr, uid, line.production_id, line.product_id, line.product_uom.id, line.product_qty, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms production order.
        @return: Newly generated Shipment Id.
        """
        user_lang = self.pool.get('res.users').browse(cr, uid, [uid]).partner_id.lang
        context = dict(context, lang=user_lang)
        uncompute_ids = filter(lambda x: x, [not x.product_lines and x.id or False for x in self.browse(cr, uid, ids, context=context)])
        self.action_compute(cr, uid, uncompute_ids, context=context)
        for production in self.browse(cr, uid, ids, context=context):
            self._make_production_produce_line(cr, uid, production, context=context)
            stock_moves = []
            for line in production.product_lines:
                if line.product_id.type in ['product', 'consu']:
                    stock_move_id = self._make_production_consume_line(cr, uid, line, context=context)
                    stock_moves.append(stock_move_id)
            if stock_moves:
                self.pool.get('stock.move').action_confirm(cr, uid, stock_moves, context=context)
            production.write({'state': 'confirmed'})
        return 0

    def action_assign(self, cr, uid, ids, context=None):
        """
        Checks the availability on the consume lines of the production order
        """
        from openerp import workflow
        move_obj = self.pool.get("stock.move")
        for production in self.browse(cr, uid, ids, context=context):
            move_obj.action_assign(cr, uid, [x.id for x in production.move_lines], context=context)
            if self.pool.get('mrp.production').test_ready(cr, uid, [production.id]):
                workflow.trg_validate(uid, 'mrp.production', production.id, 'moves_ready', cr)


    def force_production(self, cr, uid, ids, *args):
        """ Assigns products.
        @param *args: Arguments
        @return: True
        """
        from openerp import workflow
        move_obj = self.pool.get('stock.move')
        for order in self.browse(cr, uid, ids):
            move_obj.force_assign(cr, uid, [x.id for x in order.move_lines])
            if self.pool.get('mrp.production').test_ready(cr, uid, [order.id]):
                workflow.trg_validate(uid, 'mrp.production', order.id, 'moves_ready', cr)
        return True


class ProductionWorkcenterLine(models.Model):
    _name = 'mrp.production.workcenter.line'
    _description = 'Work Order'
    _order = 'sequence'
    _inherit = ['mail.thread']

    name = fields.Char('Work Order', required=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center', required=True)
    cycle = fields.Float(
        'Number of Cycles', default=0.0, digits=(16, 2))
    hour = fields.Float(
        'Number of Hours', default=0.0, digits=(16, 2))
    sequence = fields.Integer(
        'Sequence', default=1,
        required=True, help="Gives the sequence order when displaying a list of work orders.")
    production_id = fields.Many2one(
        'mrp.production', 'Manufacturing Order',
        index=True, ondelete='cascade', required=True, track_visibility='onchange')


class ProductionProductLine(models.Model):
    _name = 'mrp.production.product.line'
    _description = 'Production Scheduled Product'

    name = fields.Char('Name', required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    product_qty = fields.Float('Product Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True)
    product_uom = fields.Many2one('product.uom', 'Product Unit of Measure', required=True)
    production_id = fields.Many2one('mrp.production', 'Production Order', select=True)
