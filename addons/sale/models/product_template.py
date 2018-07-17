# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons.base.models.res_partner import WARNING_MESSAGE, WARNING_HELP


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_type = fields.Selection([('manual', 'Manually set quantities on order')], string='Track Service',
        help="Manually set quantities on order: Invoice based on the manually entered quantity, without creating an analytic account.\n"
             "Timesheets on contract: Invoice based on the tracked hours on the related timesheet.\n"
             "Create a task and track hours: Create a task on the sales order validation and track the work hours.",
        default='manual', oldname='track_service')
    sale_line_warn = fields.Selection(WARNING_MESSAGE, 'Sales Order Line', help=WARNING_HELP, required=True, default="no-message")
    sale_line_warn_msg = fields.Text('Message for Sales Order Line')
    expense_policy = fields.Selection(
        [('no', 'No'), ('cost', 'At cost'), ('sales_price', 'Sales price')],
        string='Re-Invoice Policy',
        default='no')

    @api.multi
    @api.depends('product_variant_ids.sales_count')
    def _sales_count(self):
        for product in self:
            product.sales_count = sum([p.sales_count for p in product.with_context(active_test=False).product_variant_ids])

    @api.multi
    def action_view_sales(self):
        self.ensure_one()
        action = self.env.ref('sale.action_product_sale_list')
        product_ids = self.with_context(active_test=False).product_variant_ids.ids

        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'view_type': action.view_type,
            'view_mode': action.view_mode,
            'target': action.target,
            'context': "{'default_product_id': " + str(product_ids[0]) + "}",
            'res_model': action.res_model,
            'domain': [('state', 'in', ['sale', 'done']), ('product_id.product_tmpl_id', '=', self.id)],
        }

    sales_count = fields.Integer(compute='_sales_count', string='# Sales')
    invoice_policy = fields.Selection(
        [('order', 'Ordered quantities'),
         ('delivery', 'Delivered quantities'),
        ], string='Invoicing Policy',
        help='Ordered Quantity: Invoice based on the quantity the customer ordered.\n'
             'Delivered Quantity: Invoiced based on the quantity the vendor delivered (time or deliveries).',
        default='order')

    @api.onchange('type')
    def _onchange_type(self):
        """ Force values to stay consistent with integrity constraints """
        if self.type == 'consu':
            self.invoice_policy = 'order'
            self.service_type = 'manual'

    @api.model
    def get_import_templates(self):
        res = super(ProductTemplate, self).get_import_templates()
        if self.env.context.get('sale_multi_pricelist_product_template'):
            sale_pricelist_setting = self.env['ir.config_parameter'].sudo().get_param('sale.sale_pricelist_setting')
            if sale_pricelist_setting == 'percentage':
                return [{
                    'label': _('Import Template for Products'),
                    'template': '/product/static/xls/product_template.xls'
                }, {
                    'label': _('Import Template for Products (with several prices)'),
                    'template': '/sale/static/xls/product_pricelist_several.xls'
                }]
        return res
