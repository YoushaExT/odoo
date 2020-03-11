# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools


class MailingTraceReport(models.Model):
    _name = 'mailing.trace.report'
    _auto = False
    _description = 'Mass Mailing Statistics'

    # mailing
    name = fields.Char(string='Mass Mail', readonly=True)
    mailing_type = fields.Selection([('mail', 'Mail')], string='Type', default='mail', required=True)
    campaign = fields.Char(string='Mailing Campaign', readonly=True)
    scheduled_date = fields.Datetime(string='Scheduled Date', readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('test', 'Tested'), ('done', 'Sent')],
        string='Status', readonly=True)
    email_from = fields.Char('From', readonly=True)
    # traces
    sent = fields.Integer(readonly=True)
    delivered = fields.Integer(readonly=True)
    opened = fields.Integer(readonly=True)
    replied = fields.Integer(readonly=True)
    clicked = fields.Integer(readonly=True)
    bounced = fields.Integer(readonly=True)

    def init(self):
        """Mass Mail Statistical Report: based on mailing.trace that models the various
        statistics collected for each mailing, and mailing.mailing model that models the
        various mailing performed. """
        tools.drop_view_if_exists(self.env.cr, 'mailing_trace_report')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW mailing_trace_report AS (
                SELECT
                    min(trace.id) as id,
                    utm_source.name as name,
                    mailing.mailing_type,
                    utm_campaign.name as campaign,
                    trace.scheduled as scheduled_date,
                    mailing.state,
                    mailing.email_from,
                    count(trace.sent) as sent,
                    (count(trace.sent) - count(trace.bounced)) as delivered,
                    count(trace.opened) as opened,
                    count(trace.replied) as replied,
                    count(trace.clicked) as clicked,
                    count(trace.bounced) as bounced
                FROM
                    mailing_trace as trace
                    left join mailing_mailing as mailing ON (trace.mass_mailing_id=mailing.id)
                    left join utm_campaign as utm_campaign ON (mailing.campaign_id = utm_campaign.id)
                    left join utm_source as utm_source ON (mailing.source_id = utm_source.id)
                GROUP BY trace.scheduled, utm_source.name, utm_campaign.name, mailing.mailing_type, mailing.state, mailing.email_from
            )""")
