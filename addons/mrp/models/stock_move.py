# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _
from odoo.tools import float_compare
from odoo.addons import decimal_precision as dp


class StockMoveLots(models.Model):
    _name = 'stock.move.lots'
    _description = "Quantities to Process by lots"

    move_id = fields.Many2one('stock.move', 'Move')
    workorder_id = fields.Many2one('mrp.workorder', 'Work Order')
    production_id = fields.Many2one('mrp.production', 'Production Order')
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot',
        domain="[('product_id', '=', product_id)]")
    lot_produced_id = fields.Many2one('stock.production.lot', 'Finished Lot')
    lot_produced_qty = fields.Float('Quantity Finished Product', help="Informative, not used in matching")
    quantity = fields.Float('To Do', default=1.0)
    quantity_done = fields.Float('Done')
    product_id = fields.Many2one(
        'product.product', 'Product',
        readonly=True, related="move_id.product_id", store=True)
    done_wo = fields.Boolean('Done for Work Order', default=True, help="Technical Field which is False when temporarily filled in in work order")  # TDE FIXME: naming
    done_move = fields.Boolean('Move Done', related='move_id.is_done', store=True)  # TDE FIXME: naming
    plus_visible = fields.Boolean("Plus Visible", compute='_compute_plus')

    def _compute_plus(self):
        for movelot in self:
            if movelot.move_id.product_id.tracking == 'serial':
                movelot.plus_visible = (movelot.quantity_done <= 0.0)
            else:
                movelot.plus_visible = (movelot.quantity == 0.0) or (movelot.quantity_done < movelot.quantity)

    @api.multi
    def do_plus(self):
        self.ensure_one()
        self.quantity_done = self.quantity_done + 1
        return self.move_id.split_move_lot()

    @api.multi
    def do_minus(self):
        self.ensure_one()
        self.quantity_done = self.quantity_done - 1
        return self.move_id.split_move_lot()


class StockMove(models.Model):
    _inherit = 'stock.move'

    production_id = fields.Many2one(
        'mrp.production', 'Production Order for finished products')
    raw_material_production_id = fields.Many2one(
        'mrp.production', 'Production Order for raw materials')
    unbuild_id = fields.Many2one(
        'mrp.unbuild', 'Unbuild Order')
    consume_unbuild_id = fields.Many2one(
        'mrp.unbuild', 'Consume Unbuild Order')
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', 'Operation To Consume')  # TDE FIXME: naming
    workorder_id = fields.Many2one(
        'mrp.workorder', 'Work Order To Consume')
    has_tracking = fields.Selection(related='product_id.tracking', string='Product with Tracking')  # TDE FIXME: naming ...
    # Quantities to process, in normalized UoMs
    quantity_available = fields.Float(
        'Quantity Available', compute="_qty_available",
        digits=dp.get_precision('Product Unit of Measure'))
    quantity_done_store = fields.Float('Quantity', digits=0)
    quantity_done = fields.Float(
        'Quantity', compute='_qty_done_compute', inverse='_qty_done_set',
        digits=dp.get_precision('Product Unit of Measure'))
    move_lot_ids = fields.One2many('stock.move.lots', 'move_id', string='Lots')
    bom_line_id = fields.Many2one('mrp.bom.line', 'BoM Line')
    unit_factor = fields.Float('Unit Factor')
    is_done = fields.Boolean(
        'Done', compute='_compute_is_done',
        store=True,
        help='Technical Field to order moves')  # TDE: what ?

    @api.multi
    def _qty_available(self):
        for move in self:
            # For consumables, state is available so availability = qty to do
            if move.state == 'assigned':
                move.quantity_available = move.product_uom_qty
            else:
                move.quantity_available = move.reserved_availability

    @api.multi
    @api.depends('move_lot_ids', 'move_lot_ids.quantity_done', 'quantity_done_store')
    def _qty_done_compute(self):
        for move in self:
            if move.has_tracking != 'none':
                move.quantity_done = sum(move.move_lot_ids.mapped('quantity_done'))
            else:
                move.quantity_done = move.quantity_done_store

    @api.multi
    def _qty_done_set(self):
        for move in self:
            if move.has_tracking == 'none':
                move.quantity_done_store = move.quantity_done

    @api.multi
    @api.depends('state')
    def _compute_is_done(self):
        for move in self:
            move.is_done = (move.state in ('done', 'cancel'))

    @api.multi
    def action_assign(self, no_prepare=False):
        res = super(StockMove, self).action_assign(no_prepare=no_prepare)
        self.check_move_lots()
        return res

    @api.multi
    def action_cancel(self):
        if any(move.quantity_done for move in self):
            raise exceptions.UserError(_('You cannot cancel a move move having already consumed material'))
        return super(StockMove, self).action_cancel()

    @api.multi
    def check_move_lots(self):
        moves_todo = self.filtered(lambda x: x.raw_material_production_id and x.state not in ('done', 'cancel'))
        return moves_todo.create_lots()

    @api.multi
    def create_lots(self):
        lots = self.env['stock.move.lots']
        uom_obj = self.env['product.uom']
        for move in self:
            unlink_move_lots = move.move_lot_ids.filtered(lambda x : (x.quantity_done == 0) and not x.workorder_id)
            unlink_move_lots.unlink()
            group_new_quant = {}
            old_move_lot = {}
            for movelot in move.move_lot_ids:
                key = (movelot.lot_id.id or False)
                old_move_lot.setdefault(key, []).append(movelot)
            for quant in move.reserved_quant_ids:
                key = (quant.lot_id.id or False)
                quantity = uom_obj._compute_qty(move.product_id.uom_id.id, quant.qty, move.product_uom.id)
                if group_new_quant.get(key):
                    group_new_quant[key] += quantity
                else:
                    group_new_quant[key] = quantity
            for key in group_new_quant:
                quantity = group_new_quant[key]
                if old_move_lot.get(key):
                    if old_move_lot[key][0].quantity == quantity:
                        continue
                    else:
                        old_move_lot[key][0].quantity = quantity
                else:
                    vals = {
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'workorder_id': move.workorder_id.id,
                        'production_id': move.raw_material_production_id.id,
                        'quantity': quantity,
                        'lot_id': key,
                    }
                    lots.create(vals)
        return True

    @api.multi
    def move_validate(self):
        ''' Validate moves based on a production order. '''
        moves = self._filter_closed_moves()
        quant_obj = self.env['stock.quant']
        moves_todo = self.env['stock.move']
        uom_obj = self.env['product.uom']
        for move in moves:
            rounding = move.product_uom.rounding
            if float_compare(move.quantity_done, 0.0, precision_rounding=rounding) <= 0:
                continue
            moves_todo |= move
            if float_compare(move.quantity_done, move.product_uom_qty, precision_rounding=rounding) > 0:
                remaining_qty = move.quantity_done - move.product_uom_qty  # In UoM of move
                extra_move = move.copy(default={'quantity_done': remaining_qty, 'product_uom_qty': remaining_qty, 'production_id': move.production_id.id, 
                                                'raw_material_production_id': move.raw_material_production_id.id})
                move.quantity_done = move.product_uom_qty
                extra_move.action_confirm()
                moves_todo |= extra_move
        for move in moves_todo:
            if float_compare(move.quantity_done, move.product_uom_qty, precision_rounding=rounding):
                # Need to do some kind of conversion here
                qty_split = uom_obj._compute_qty(move.product_uom.id, move.product_uom_qty - move.quantity_done, move.product_id.uom_id.id)
                new_move = move.split(qty_split)
                self.browse(new_move).quantity_done = 0.0
            main_domain = [('qty', '>', 0)]
            preferred_domain = [('reservation_id', '=', move.id)]
            fallback_domain = [('reservation_id', '=', False)]
            fallback_domain2 = ['&', ('reservation_id', '!=', move.id), ('reservation_id', '!=', False)]
            preferred_domain_list = [preferred_domain] + [fallback_domain] + [fallback_domain2]
            if move.has_tracking == 'none':
                quants = quant_obj.quants_get_preferred_domain(move.product_qty, move, domain=main_domain, preferred_domain_list=preferred_domain_list)
                self.env['stock.quant'].quants_move(quants, move, move.location_dest_id)
            else:
                for movelot in move.move_lot_ids:
                    if float_compare(movelot.quantity_done, 0, precision_rounding=rounding) > 0:
                        qty = uom_obj._compute_qty(move.product_uom.id, movelot.quantity_done, move.product_id.uom_id.id)
                        quants = quant_obj.quants_get_preferred_domain(qty, move, lot_id=movelot.lot_id.id, domain=main_domain, preferred_domain_list=preferred_domain_list)
                        self.env['stock.quant'].quants_move(quants, move, move.location_dest_id, lot_id = movelot.lot_id.id)
            move.quants_unreserve()
            # Next move in production order
            if move.move_dest_id:
                move.move_dest_id.action_assign()
        moves_todo.write({'state': 'done', 'date': fields.Datetime.now()})
        return moves_todo

    @api.multi
    def action_done(self):
        production_moves = self.filtered(lambda move: (move.production_id or move.raw_material_production_id) and not move.scrapped)
        production_moves.move_validate()
        return super(StockMove, self-production_moves).action_done()

    @api.multi
    def split_move_lot(self):
        ctx = dict(self.env.context)
        self.ensure_one()
        view = self.env.ref('mrp.view_stock_move_lots')
        serial = (self.has_tracking == 'serial')
        only_create = False  # Check picking type in theory
        show_reserved = any([x for x in self.move_lot_ids if x.quantity > 0.0])
        ctx.update({
            'serial': serial,
            'only_create': only_create,
            'create_lots': True,
            'state_done': self.is_done,
            'show_reserved': show_reserved,
        })
        if ctx.get('w_production'):
            action = self.env.ref('mrp.act_mrp_product_produce').read()[0]
            action['context'] = ctx
            return action
        result = {
            'name': _('Register Lots'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.move',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.id,
            'context': ctx,
        }
        return result

    @api.multi
    def save(self):
        return True

    @api.multi
    def action_confirm(self):
        moves = self.env['stock.move']
        for move in self:
            moves |= move.action_explode()
        # we go further with the list of ids potentially changed by action_explode
        return super(StockMove, moves).action_confirm()

    def action_explode(self):
        """ Explodes pickings """
        # in order to explode a move, we must have a picking_type_id on that move because otherwise the move
        # won't be assigned to a picking and it would be weird to explode a move into several if they aren't
        # all grouped in the same picking.
        if not self.picking_type_id:
            return self
        bom = self.env['mrp.bom'].sudo()._bom_find(product=self.product_id)
        if not bom or bom.type != 'phantom':
            return self
        phantom_moves = self.env['stock.move']
        processed_moves = self.env['stock.move']
        factor = self.env['product.uom']._compute_qty(self.product_uom.id, self.product_uom_qty, bom.product_uom_id.id) / bom.product_qty
        boms, lines = bom.sudo().explode(self.product_id, factor, picking_type=bom.picking_type_id)
        for bom_line, line_data in lines:
            phantom_moves += self._generate_move_phantom(bom_line, line_data['qty'])

        for new_move in phantom_moves:
            processed_moves |= new_move.action_explode()
        if not self.split_from and self.procurement_id:
            # Check if procurements have been made to wait for
            moves = self.procurement_id.move_ids
            if len(moves) == 1:
                self.procurement_id.write({'state': 'done'})
        if processed_moves and self.state == 'assigned':
            # Set the state of resulting moves according to 'assigned' as the original move is assigned
            processed_moves.write({'state': 'assigned'})
        # delete the move with original product which is not relevant anymore
        self.sudo().unlink()
        return processed_moves

    def _generate_move_phantom(self, bom_line, quantity):
        if bom_line.product_id.type in ['product', 'consu']:
            return self.copy(default={
                'picking_id': self.picking_id.id if self.picking_id else False,
                'product_id': bom_line.product_id.id,
                'product_uom': bom_line.product_uom_id.id,
                'product_uom_qty': quantity,
                'state': 'draft',  # will be confirmed below
                'name': self.name,
                'procurement_id': self.procurement_id.id,
                'split_from': self.id,  # Needed in order to keep sale connection, but will be removed by unlink
            })
        return self.env['stock.move']
