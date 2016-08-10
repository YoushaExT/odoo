# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api

class test_model(models.Model):
    _name = 'test_converter.test_model'

    char = fields.Char()
    integer = fields.Integer()
    float = fields.Float()
    numeric = fields.Float(digits=(16, 2))
    many2one = fields.Many2one('test_converter.test_model.sub')
    binary = fields.Binary()
    date = fields.Date()
    datetime = fields.Datetime()
    selection = fields.Selection([
        (1, "réponse A"),
        (2, "réponse B"),
        (3, "réponse C"),
        (4, "réponse <D>"),
    ])
    selection_str = fields.Selection([
        ('A', "Qu'il n'est pas arrivé à Toronto"),
        ('B', "Qu'il était supposé arriver à Toronto"),
        ('C', "Qu'est-ce qu'il fout ce maudit pancake, tabernacle ?"),
        ('D', "La réponse D"),
    ], string="Lorsqu'un pancake prend l'avion à destination de Toronto et "
              "qu'il fait une escale technique à St Claude, on dit:")
    html = fields.Html()
    text = fields.Text()

    # `base` module does not contains any model that implement the functionality
    # `_group_by_full`; test this feature here...

    @api.multi
    def _gbf_m2o(self, domain, read_group_order, access_rights_uid):
        Sub = self.env['test_converter.test_model.sub']
        subs = Sub.browse(Sub._search([], access_rights_uid=access_rights_uid))
        result = subs.sudo(access_rights_uid).name_get()
        folds = {i: i not in self.ids for i, _ in result}
        return result, folds

    _group_by_full = {
        'many2one': _gbf_m2o,
    }


class test_model_sub(models.Model):
    _name = 'test_converter.test_model.sub'
    name = fields.Char()


class test_model_monetary(models.Model):
    _name = 'test_converter.monetary'
    value = fields.Float(digits=(16, 55))
