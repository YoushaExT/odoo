# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MassMailingList(models.Model):
    _inherit = 'mail.mass_mailing.list'

    def _default_toast_content(self):
        return '<p>Thanks for subscribing!</p>'

    website_popup_ids = fields.One2many('website.mass_mailing.popup', 'mailing_list_id', string="Website Popups")
    toast_content = fields.Html(default=_default_toast_content, translate=True)


class MassMailingPopup(models.Model):
    _name = 'website.mass_mailing.popup'
    _description = "Mailing list popup"

    def _default_popup_content(self):
        return self.env['ir.ui.view'].render_template('website_mass_mailing.s_newsletter_block')

    mailing_list_id = fields.Many2one('mail.mass_mailing.list')
    website_id = fields.Many2one('website')
    popup_content = fields.Html(string="Website Popup Content", default=_default_popup_content, translate=True, sanitize=False)
