# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sale_line_id = fields.Many2one('sale.order.line')

    @api.multi
    def _prepare_stock_moves(self, picking):
        res = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        for re in res:
            re['sale_line_id'] = self.sale_line_id.id
        return res


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _prepare_purchase_order_line(self, values, rule, po, supplier):
        res = super(ProcurementGroup, self)._prepare_purchase_order_line(values, rule, po, supplier)
        res['sale_line_id'] = values.get('sale_line_id', False)
        return res

