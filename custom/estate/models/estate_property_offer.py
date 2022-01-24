from odoo import fields, models

class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    price = fields.Float()
    status = fields.Selection(copy=False, selection=[('refused', 'Refused'), ('accepted', 'Accepted')])
    partner_id = fields.Many2one('res.partner')
    property_id = fields.Many2one('estate.property')
