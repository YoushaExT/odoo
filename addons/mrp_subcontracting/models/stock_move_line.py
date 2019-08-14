# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def create(self, values):
        records = super(StockMoveLine, self).create(values)
        records.filtered(lambda ml: ml.move_id.is_subcontract).move_id._check_overprocessed_subcontract_qty()
        return records

    def write(self, values):
        res = super(StockMoveLine, self).write(values)
        self.filtered(lambda ml: ml.move_id.is_subcontract).move_id._check_overprocessed_subcontract_qty()
        return res
