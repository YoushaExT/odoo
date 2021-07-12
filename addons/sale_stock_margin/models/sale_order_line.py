# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('move_ids', 'move_ids.stock_valuation_layer_ids', 'order_id.picking_ids.state')
    def _compute_purchase_price(self):
        lines_without_moves = self.browse()
        for line in self:
            if not line.move_ids:
                lines_without_moves |= line
            elif line.product_id.categ_id.property_cost_method != 'standard':
                purch_price = line.product_id.with_company(line.company_id)._compute_average_price(0, line.product_uom_qty, line.move_ids)
                if line.product_uom and line.product_uom != line.product_id.uom_id:
                    purch_price = line.product_id.uom_id._compute_price(purch_price, line.product_uom)
                to_cur = line.currency_id or line.order_id.currency_id
                line.purchase_price = line.product_id.cost_currency_id._convert(
                    from_amount=purch_price,
                    to_currency=to_cur,
                    company=line.company_id or self.env.company,
                    date=line.order_id.date_order or fields.Date.today(),
                    round=False,
                ) if to_cur and purch_price else purch_price
        return super(SaleOrderLine, lines_without_moves)._compute_purchase_price()
