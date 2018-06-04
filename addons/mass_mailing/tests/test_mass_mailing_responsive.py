# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestResponsiveMail(common.SavepointCase):

    def test_responsive_mail(self):
        """
            Testing mail mailing responsive mail body
        """
        test_record = self.env['res.partner'].create({'name': 'Mass Mail Partner'})
        mass_mail_record = self.env.ref('mass_mailing.mass_mail_2')

        composer = self.env['mail.compose.message'].sudo().with_context({
            'default_composition_mode': 'mass_mail',
            'default_model': 'res.partner',
            'default_res_id': test_record.id,
        }).create({
            'subject': 'Mass Mail Responsive',
            'body': 'I am Responsive body',
            'mass_mailing_id': mass_mail_record.id
        })

        mail_values = composer.get_mail_values([test_record.id])
        body_html = str(mail_values[test_record.id]['body_html'])

        self.assertIn('<!DOCTYPE html>', body_html)
        self.assertIn('<head>', body_html)
        self.assertIn('viewport', body_html)
        self.assertIn('@media', body_html)
        self.assertIn('I am Responsive body', body_html)
