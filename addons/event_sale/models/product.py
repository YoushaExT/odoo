# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    event_ok = fields.Boolean(string='Is an Event Ticket', help="If checked this product automatically "
      "creates an event registration at the sales order confirmation.")

    @api.onchange('event_ok')
    def _onchange_event_ok(self):
        if self.event_ok:
            self.type = 'service'
            self.invoice_policy = 'order'

    def _compute_show_service_fields(self):
        super()._compute_show_service_fields()
        for record in self:
            record.show_service_fields |= record.type == 'event'


class Product(models.Model):
    _inherit = 'product.product'

    event_ticket_ids = fields.One2many('event.event.ticket', 'product_id', string='Event Tickets')

    @api.onchange('event_ok')
    def _onchange_event_ok(self):
        """ Redirection, inheritance mechanism hides the method on the model """
        if self.event_ok:
            self.type = 'service'
            self.invoice_policy = 'order'
