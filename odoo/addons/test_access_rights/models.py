# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class SomeObj(models.Model):
    _name = 'test_access_right.some_obj'
    _description = 'Object For Test Access Right'

    val = fields.Integer()
    company_id = fields.Many2one('res.company')
    forbidden = fields.Integer(
        groups='test_access_rights.test_group,!base.group_no_one,base.group_user,!base.group_public',
        default=5
    )
    forbidden2 = fields.Integer(groups='test_access_rights.test_group')

class Container(models.Model):
    _name = 'test_access_right.container'
    _description = 'Test Access Right Container'

    some_ids = fields.Many2many('test_access_right.some_obj', 'test_access_right_rel', 'container_id', 'some_id')
