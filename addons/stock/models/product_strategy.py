# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class RemovalStrategy(models.Model):
    _name = 'product.removal'
    _description = 'Removal Strategy'

    name = fields.Char('Name', required=True)
    method = fields.Char("Method", required=True, help="FIFO, LIFO...")


class StockPutawayRule(models.Model):
    _name = 'stock.putaway.rule'
    _order = 'sequence,product_id'
    _description = 'Putaway Rule'

    def _default_category_id(self):
        if self.env.context.get('active_model') == 'product.category':
            return self.env.context.get('active_id')

    def _default_location_id(self):
        if self.env.context.get('active_model') == 'stock.location':
            return self.env.context.get('active_id')

    def _default_product_id(self):
        if self.env.context.get('active_model') == 'product.template' and self.env.context.get('active_id'):
            product_template = self.env['product.template'].browse(self.env.context.get('active_id'))
            product_template = product_template.exists()
            if product_template.product_variant_count == 1:
                return product_template.product_variant_id
        elif self.env.context.get('active_model') == 'product.product':
            return self.env.context.get('active_id')

    def _domain_category_id(self):
        active_model = self.env.context.get('active_model')
        if active_model in ('product.template', 'product.product') and self.env.context.get('active_id'):
            product = self.env[active_model].browse(self.env.context.get('active_id'))
            product = product.exists()
            if product:
                return [('id', '=', product.categ_id.id)]
        return []

    def _domain_product_id(self):
        if self.env.context.get('active_model') == 'product.template':
            return [('product_tmpl_id', '=', self.env.context.get('active_id'))]
        return []

    product_id = fields.Many2one('product.product', 'Product',
        default=_default_product_id, domain=_domain_product_id, ondelete='cascade')
    category_id = fields.Many2one('product.category', 'Product Category',
        default=_default_category_id, domain=_domain_category_id, ondelete='cascade')
    location_in_id = fields.Many2one('stock.location', 'When product arrives in',
        default=_default_location_id, required=True, ondelete='cascade')
    location_out_id = fields.Many2one('stock.location', 'Store to',
        required=True, ondelete='cascade')
    sequence = fields.Integer('Priority', help="Give to the more specialized category, a higher priority to have them in top of the list.")

    @api.onchange('location_in_id')
    def _onchange_location_in(self):
        if self.location_out_id:
            child_location_count = self.env['stock.location'].search_count([
                ('id', '=', self.location_out_id.id),
                ('id', 'child_of', self.location_in_id.id),
                ('id', '!=', self.location_in_id.id),
            ])
            if not child_location_count:
                self.location_out_id = None
