from odoo import models, fields

class EstatePropertyTag(models.Model):
    _name = 'estate.property.tag'
    name = fields.Char(required=True)