# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        if self.env.context.get('mark_so_as_sent') and self.model == 'sale.order':
            self = self.with_context(mail_notify_author=self.env.user.partner_id in self.partner_ids)
        return super(MailComposeMessage, self)._action_send_mail(auto_commit=auto_commit)
