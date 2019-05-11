# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockValuationLayer(models.Model):
    """Stock Valuation Layer"""

    _name = 'stock.valuation.layer'
    _description = 'Stock Valuation Layer'
    _order = 'create_date, id'

    _rec_name = 'product_id'

    company_id = fields.Many2one('res.company', 'Company', readonly=True, required=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True, required=True)
    quantity = fields.Float('Quantity', digits=0, help='Quantity', readonly=True)
    uom_id = fields.Many2one(related='product_id.uom_id', readonly=True, required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='company_id.currency_id', readonly=True, required=True)
    unit_cost = fields.Monetary('Unit Value', readonly=True)
    value = fields.Monetary('Total Value', readonly=True)
    remaining_qty = fields.Float(digits=0, readonly=True)
    description = fields.Char('Description', readonly=True)
    stock_move_id = fields.Many2one('stock.move', 'Stock Move', readonly=True)
    account_move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True)

