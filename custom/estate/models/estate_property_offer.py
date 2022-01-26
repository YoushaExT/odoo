from odoo import fields, models, api
from datetime import timedelta

class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    price = fields.Float()
    status = fields.Selection(copy=False, selection=[('refused', 'Refused'), ('accepted', 'Accepted')])
    partner_id = fields.Many2one('res.partner')
    property_id = fields.Many2one('estate.property')
    validity = fields.Integer(default=7)
    date_deadline = fields.Date(compute='_compute_date_deadline', inverse='_inverse_date_deadline')
    # computed fields
    @api.depends("validity")
    def _compute_date_deadline(self):
        for property_offer in self:
            date = property_offer.create_date.date() if property_offer.create_date else fields.Date.today()
            property_offer.date_deadline = date + timedelta(days=property_offer.validity)

    def _inverse_date_deadline(self):
        for property_offer in self:
            date = property_offer.create_date.date() if property_offer.create_date else fields.Date.today()
            property_offer.validity = (property_offer.date_deadline - date).days

    def action_accept(self):
        if self.property_id.state not in ('sold', 'canceled'):
            self.status = 'accepted'
            self.property_id.state = 'offer_accepted'
            self.property_id.buyer_id = self.partner_id
            self.property_id.selling_price = self.price
        else:
            print('ALREADY SOLD')


    def action_refuse(self):
        if self.property_id.state not in ('sold', 'canceled'):
            self.status = 'refused'
        else:
            print('ALREADY SOLD')
