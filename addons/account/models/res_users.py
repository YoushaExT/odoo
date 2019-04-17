# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import ValidationError


class Users(models.Model):
    _inherit = "res.users"

    @api.multi
    @api.constrains('groups_id')
    def _check_one_user_type(self):
        super(Users, self)._check_one_user_type()

        users_with_both_groups = self.filtered(lambda user:
            user.has_group('account.group_show_line_subtotals_tax_included') and
            user.has_group('account.group_show_line_subtotals_tax_excluded')
        )
        if users_with_both_groups:
            names = ", ".join(users_with_both_groups.mapped('name'))
            raise ValidationError(_("A user cannot have both Tax B2B and Tax B2C.\n"
                                    "Problematic user(s): %s\n"
                                    "You should go in General Settings, and choose to display Product Prices\n"
                                    "either in 'Tax-Included' or in 'Tax-Excluded' mode\n"
                                    "(or switch twice the mode if you are already in the desired one).") % names)
