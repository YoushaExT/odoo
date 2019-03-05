# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare


class ChooseDeliveryPackage(models.TransientModel):
    _name = 'choose.delivery.package'
    _description = 'Delivery Package Selection Wizard'

    def _default_shipping_weight(self):
        picking = self.env['stock.picking'].browse(self.env.context.get('default_picking_id'))
        move_line_ids = picking.move_line_ids.filtered(lambda m:
            float_compare(m.qty_done, 0.0, precision_rounding=m.product_uom_id.rounding) > 0
            and not m.result_package_id
        )
        total_weight = 0.0
        for ml in move_line_ids:
            qty = ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id)
            total_weight += qty * ml.product_id.weight
        return total_weight

    picking_id = fields.Many2one('stock.picking', 'Picking')
    delivery_packaging_id = fields.Many2one('product.packaging', 'Delivery Packaging')
    shipping_weight = fields.Float('Shipping Weight', default=_default_shipping_weight)
    weight_uom_name = fields.Char(string='Weight unit of measure label', compute='_compute_weight_uom_name')

    @api.depends('delivery_packaging_id')
    def _compute_weight_uom_name(self):
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        for package in self:
            package.weight_uom_name = weight_uom_id.name

    @api.onchange('delivery_packaging_id', 'shipping_weight')
    def _onchange_packaging_weight(self):
        if self.delivery_packaging_id.max_weight and self.shipping_weight > self.delivery_packaging_id.max_weight:
            warning_mess = {
                'title': _('Package too heavy!'),
                'message': _('The weight of your package is higher than the maximum weight authorized for this package type. Please choose another package type.')
            }
            return {'warning': warning_mess}

    def put_in_pack(self):
        move_line_ids = self.picking_id.move_line_ids.filtered(lambda ml:
            float_compare(ml.qty_done, 0.0, precision_rounding=ml.product_uom_id.rounding) > 0
            and not ml.result_package_id
        )
        delivery_package = self.picking_id._put_in_pack(move_line_ids)
        # write shipping weight and product_packaging on 'stock_quant_package' if needed
        if self.delivery_packaging_id:
            delivery_package.packaging_id = self.delivery_packaging_id
            if self.shipping_weight:
                delivery_package.shipping_weight = self.shipping_weight
