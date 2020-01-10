# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    margin = fields.Float(
        "Margin", compute='_compute_margin',
        digits='Product Price', store=True, groups="base.group_user")
    margin_percent = fields.Float(
        "Margin (%)", compute='_compute_margin', store=True, groups="base.group_user")
    purchase_price = fields.Float(
        string='Cost', compute="_compute_purchase_price",
        digits='Product Price', store=True, readonly=False,
        groups="base.group_user")

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
    def _compute_purchase_price(self):
        for line in self:
            if not line.product_id:
                line.purchase_price = 0.0
                continue
            line = line.with_company(line.company_id)
            product = line.product_id
            product_cost = product.standard_price
            fro_cur = product.cost_currency_id
            to_cur = line.currency_id or line.order_id.currency_id
            if line.product_uom and line.product_uom != product.uom_id:
                product_cost = product.uom_id._compute_price(
                    product_cost,
                    line.product_uom,
                )
            line.purchase_price = fro_cur._convert(
                from_amount=product_cost,
                to_currency=to_cur,
                company=line.company_id or self.env.company,
                date=line.order_id.date_order or fields.Date.today(),
                round=False,
            ) if to_cur else product_cost
            # The pricelist may not have been set, therefore no conversion
            # is needed because we don't know the target currency..

    @api.depends('price_subtotal', 'product_uom_qty', 'purchase_price')
    def _compute_margin(self):
        for line in self:
            line.margin = line.price_subtotal - (line.purchase_price * line.product_uom_qty)
            line.margin_percent = line.price_subtotal  and line.margin/line.price_subtotal


class SaleOrder(models.Model):
    _inherit = "sale.order"

    margin = fields.Monetary("Margin", compute='_compute_margin', store=True)
    margin_percent = fields.Float("Margin (%)", compute='_compute_margin', store=True)

    @api.depends('order_line.margin', 'amount_untaxed')
    def _compute_margin(self):
        for order in self:
            order.margin = sum(order.order_line.mapped('margin'))
            order.margin_percent = order.amount_untaxed and order.margin/order.amount_untaxed
