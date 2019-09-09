# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    use_expiration_date = fields.Boolean(string='Expiration Date',
        help='When this box is ticked, you have the possibility to specify dates to manage'
        ' product expiration, on the product and on the corresponding lot/serial numbers')
    expiration_time = fields.Integer(string='Product Life Time',
        help='Number of days before the goods may become dangerous and must not be consumed. It will be computed on the lot/serial number.')
    use_time = fields.Integer(string='Product Use Time',
        help='Number of days before the goods starts deteriorating, without being dangerous yet. It will be computed using the lot/serial number.')
    removal_time = fields.Integer(string='Product Removal Time',
        help='Number of days before the goods should be removed from the stock. It will be computed on the lot/serial number.')
    alert_time = fields.Integer(string='Product Alert Time',
        help='Number of days before an alert should be raised on the lot/serial number.')
