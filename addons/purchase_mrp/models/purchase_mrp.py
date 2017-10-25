# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _update_received_qty(self):
        super(PurchaseOrderLine, self)._update_received_qty()
        for line in self.filtered(lambda x: x.move_ids and x.product_id.id not in x.move_ids.mapped('product_id').ids):
            bom = self.env['mrp.bom']._bom_find(product=line.product_id, company_id=line.company_id.id)
            if bom and bom.type == 'phantom':
                line.qty_received = line._get_bom_delivered(bom=bom)

    def _get_bom_delivered(self, bom=False):
        self.ensure_one()

        # In the case of a kit, we need to check if all components are shipped. Since the BOM might
        # have changed, we don't compute the quantities but verify the move state.
        if bom:
            bom_delivered = all([move.state == 'done' for move in self.move_ids])
            if bom_delivered:
                return self.product_qty
            else:
                return 0.0
