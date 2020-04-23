# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailingSimple(models.Model):
    """ A very simple model only inheriting from mail.thread to test pure mass
    mailing features and base performances. """
    _description = 'Simple Mailing'
    _name = 'mailing.test.simple'
    _inherit = ['mail.thread']

    name = fields.Char()
    email_from = fields.Char()


class MailingBLacklist(models.Model):
    """ Model using blacklist mechanism for mass mailing features. """
    _description = 'Mailing Blacklist Enabled'
    _name = 'mailing.test.blacklist'
    _inherit = ['mail.thread.blacklist']
    _primary_email = 'email_from'

    name = fields.Char()
    email_from = fields.Char()
    customer_id = fields.Many2one('res.partner', 'Customer', tracking=True)
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True)


class MailingOptOut(models.Model):
    """ Model using blacklist mechanism and a hijacked opt-out mechanism for
    mass mailing features. """
    _description = 'Mailing Blacklist / Optout Enabled'
    _name = 'mailing.test.optout'
    _inherit = ['mail.thread.blacklist']
    _primary_email = 'email_from'

    name = fields.Char()
    email_from = fields.Char()
    opt_out = fields.Boolean()
    customer_id = fields.Many2one('res.partner', 'Customer', tracking=True)
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True)


class MailingPerformance(models.Model):
    """ A very simple model only inheriting from mail.thread to test pure mass
    mailing performances. """
    _name = 'mailing.performance'
    _description = 'Mailing: base performance'
    _inherit = ['mail.thread']

    name = fields.Char()
    email_from = fields.Char()


class MailingPerformanceBL(models.Model):
    """ Model using blacklist mechanism for mass mailing performance. """
    _name = 'mailing.performance.blacklist'
    _description = 'Mailing: blacklist performance'
    _inherit = ['mail.thread.blacklist']
    _primary_email = 'email_from'  # blacklist field to check

    name = fields.Char()
    email_from = fields.Char()
    user_id = fields.Many2one(
        'res.users', 'Responsible',
        tracking=True)
    container_id = fields.Many2one(
        'mail.test.container', 'Meta Container Record',
        tracking=True)
