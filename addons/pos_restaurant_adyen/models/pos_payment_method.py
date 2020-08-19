# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    adyen_merchant_account = fields.Char(help='The POS merchant account code used in Adyen')
