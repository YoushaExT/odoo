# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    purchase_line_ids = fields.One2many('purchase.order.line', 'sale_line_id')

    @api.multi
    def _get_qty_procurement(self):
        if not self.move_ids.filtered(lambda r: r.state != 'cancel') and self.purchase_line_ids.filtered(lambda r: r.state != 'cancel'):
            qty = 0.0
            for po_line in self.purchase_line_ids.filtered(lambda r: r.state != 'cancel'):
                qty += po_line.product_uom._compute_quantity(po_line.product_qty, self.product_uom, rounding_method='HALF-UP')
            return qty
        else:
            return super(SaleOrderLine, self)._get_qty_procurement()

