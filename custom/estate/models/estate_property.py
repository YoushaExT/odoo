from odoo import fields, models, api
from odoo.exceptions import UserError
from datetime import timedelta

class EstateProperty(models.Model):
    _name = "estate.property"
    _description = "This is an estate property"

    name = fields.Char(string='Title', required=True)
    description = fields.Text()
    postcode = fields.Char()
    date_availability = fields.Date(string='Available From', copy=False, default=fields.Date.today()+timedelta(days=90))
    expected_price = fields.Float(required=True)
    selling_price = fields.Float(readonly=True, copy=False)
    bedrooms = fields.Integer(default=2)
    living_area = fields.Integer(string='Living Area (sqm)')
    facades = fields.Integer()
    garage = fields.Boolean()
    garden = fields.Boolean()
    garden_area = fields.Integer(string='Garden Area (sqm)')
    garden_orientation = fields.Selection(selection=[('north', 'North'), ('south', 'South'), ('east', 'East'), ('west', 'West')])
    state = fields.Selection(selection=[('new', 'New'), ('offer_received', 'Offer Received'), ('offer_accepted', 'Offer Accepted'), ('sold', 'Sold'), ('canceled', 'Canceled')], required=True, copy=False, default='new', string='Status')
    active = fields.Boolean(default=True)
    # linked fields
    property_type_id = fields.Many2one('estate.property.type', string='Property Type')
    buyer_id = fields.Many2one('res.partner')
    seller_id = fields.Many2one('res.users', string="Salesman", default=lambda self: self.env.user)
    tag_ids = fields.Many2many('estate.property.tag', string="Property Tags")
    offer_ids = fields.One2many('estate.property.offer', 'property_id', string='Offers')
    # computed fields
    total_area = fields.Integer(compute="_compute_total_area", string="Total Area (sqm)")
    best_price = fields.Float(compute="_compute_best_price")

    @api.depends("garden_area", "living_area")
    def _compute_total_area(self):
        for record in self:
            record.total_area = record.living_area + record.garden_area

    @api.depends("offer_ids.price")
    def _compute_best_price(self):
        for estate_property in self:
            estate_property.best_price = max(estate_property.offer_ids.mapped("price")) if estate_property.offer_ids else 0.0

    @api.onchange("garden")
    def _onchange_garden(self):
        if self.garden:
            self.garden_area = 10
            self.garden_orientation = 'north'
        else:
            self.garden_area = 0
            self.garden_orientation = False

    def action_sold(self):
        if self.state == 'canceled':
            raise UserError("Canceled properties cannot be sold!")
        else:
            self.state = 'sold'
        return True

    def action_cancel(self):
        if self.state == 'sold':
            raise UserError("Sold properties cannot be canceled!")
        else:
            self.state = 'canceled'
        return True