# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models, tools
from odoo.addons.bus.models.bus_presence import AWAY_TIMER
from odoo.addons.bus.models.bus_presence import DISCONNECTION_TIMER
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    """ Update partner to add a field about notification preferences. Add a generic opt-out field that can be used
       to restrict usage of automatic email templates. """
    _name = "res.partner"
    _inherit = ['res.partner', 'mail.activity.mixin', 'mail.thread.blacklist']
    _mail_flat_thread = False

    email = fields.Char(tracking=1)
    phone = fields.Char(tracking=2)

    channel_ids = fields.Many2many('mail.channel', 'mail_channel_partner', 'partner_id', 'channel_id', string='Channels', copy=False)
    # override the field to track the visibility of user
    user_id = fields.Many2one(tracking=True)

    def _compute_im_status(self):
        super()._compute_im_status()
        odoobot_id = self.env['ir.model.data']._xmlid_to_res_id('base.partner_root')
        odoobot = self.env['res.partner'].browse(odoobot_id)
        if odoobot in self:
            odoobot.im_status = 'bot'

    def _message_get_suggested_recipients(self):
        recipients = super(Partner, self)._message_get_suggested_recipients()
        for partner in self:
            partner._message_add_suggested_recipient(recipients, partner=partner, reason=_('Partner Profile'))
        return recipients

    def _message_get_default_recipients(self):
        return {r.id: {
            'partner_ids': [r.id],
            'email_to': False,
            'email_cc': False}
            for r in self}

    @api.model
    @api.returns('self', lambda value: value.id)
    def find_or_create(self, email, assert_valid_email=False):
        """ Override to use the email_normalized field. """
        if not email:
            raise ValueError(_('An email is required for find_or_create to work'))

        parsed_name, parsed_email = self._parse_partner_name(email)
        if parsed_email:
            email_normalized = tools.email_normalize(parsed_email)
            if email_normalized:
                partners = self.search([('email_normalized', '=', email_normalized)], limit=1)
                if partners:
                    return partners

        # We don't want to call `super()` to avoid searching twice on the email
        # Especially when the search `email =ilike` cannot be as efficient as
        # a search on email_normalized with a btree index
        # If you want to override `find_or_create()` your module should depend on `mail`
        create_values = {self._rec_name: parsed_name or parsed_email}
        if parsed_email:  # otherwise keep default_email in context
            create_values['email'] = parsed_email
        return self.create(create_values)

    def mail_partner_format(self):
        self.ensure_one()
        internal_users = self.user_ids - self.user_ids.filtered('share')
        main_user = internal_users[0] if len(internal_users) > 0 else self.user_ids[0] if len(self.user_ids) > 0 else self.env['res.users']
        res = {
            "id": self.id,
            "display_name": self.display_name,
            "name": self.name,
            "email": self.email,
            "active": self.active,
            "im_status": self.im_status,
            "user_id": main_user.id,
        }
        if main_user:
            res["is_internal_user"] = not main_user.share
        return res

    def _get_needaction_count(self):
        """ compute the number of needaction of the current partner """
        self.ensure_one()
        self.env['mail.notification'].flush(['is_read', 'res_partner_id'])
        self.env.cr.execute("""
            SELECT count(*) as needaction_count
            FROM mail_notification R
            WHERE R.res_partner_id = %s AND (R.is_read = false OR R.is_read IS NULL)""", (self.id,))
        return self.env.cr.dictfetchall()[0].get('needaction_count')

    def _get_starred_count(self):
        """ compute the number of starred of the current partner """
        self.ensure_one()
        self.env.cr.execute("""
            SELECT count(*) as starred_count
            FROM mail_message_res_partner_starred_rel R
            WHERE R.res_partner_id = %s """, (self.id,))
        return self.env.cr.dictfetchall()[0].get('starred_count')

    def _message_fetch_failed(self):
        """Returns all messages, sent by the current partner, that have errors, in
        the format expected by the web client."""
        self.ensure_one()
        messages = self.env['mail.message'].search([
            ('has_error', '=', True),
            ('author_id', '=', self.id),
            ('res_id', '!=', 0),
            ('model', '!=', False),
            ('message_type', '!=', 'user_notification')
        ])
        return messages._message_notification_format()

    def _get_channels_as_member(self):
        """Returns the channels of the partner."""
        self.ensure_one()
        channels = self.env['mail.channel']
        # get the channels
        channels |= self.env['mail.channel'].search([
            ('channel_type', '=', 'channel'),
            ('channel_partner_ids', 'in', [self.id]),
        ])
        # get the pinned direct messages
        channels |= self.env['mail.channel'].search([
            ('channel_type', '=', 'chat'),
            ('channel_last_seen_partner_ids', 'in', self.env['mail.channel.partner'].sudo()._search([
                ('partner_id', '=', self.id),
                ('is_pinned', '=', True),
            ])),
        ])
        return channels

    @api.model
    def search_for_channel_invite(self, search_term, channel_id=None, limit=30):
        """ Returns partners matching search_term that can be invited to a channel.
        If the channel_id is specified, only partners that can actually be invited to the channel
        are returned (not already members, and in accordance to the channel configuration).
        """
        domain = expression.AND([
            expression.OR([
                [('name', 'ilike', search_term)],
                [('email', 'ilike', search_term)],
            ]),
            [('active', '=', True)],
            [('type', '!=', 'private')],
            [('user_ids', '!=', False)],
            [('user_ids.active', '=', True)],
            [('user_ids.share', '=', False)],
        ])
        if channel_id:
            channel = self.env['mail.channel'].search([('id', '=', int(channel_id))])
            domain = expression.AND([domain, [('channel_ids', 'not in', channel.id)]])
            if channel.public == 'groups':
                domain = expression.AND([domain, [('user_ids.groups_id', 'in', channel.group_public_id.id)]])
        query = self.env['res.partner']._search(domain, order='name, id')
        query.order = 'LOWER("res_partner"."name"), "res_partner"."id"'  # bypass lack of support for case insensitive order in search()
        query.limit = int(limit)
        return {
            'count': self.env['res.partner'].search_count(domain),
            'partners': [p.mail_partner_format() for p in self.env['res.partner'].browse(query)],
        }

    @api.model
    def get_mention_suggestions(self, search, limit=8, channel_id=None):
        """ Return 'limit'-first partners' such that the name or email matches a 'search' string.
            Prioritize partners that are also users, and then extend the research to all partners.
            If channel_id is given, only members of this channel are returned.
            The return format is a list of partner data (as per returned by `mail_partner_format()`).
        """
        search_dom = expression.OR([[('name', 'ilike', search)], [('email', 'ilike', search)]])
        search_dom = expression.AND([[('active', '=', True), ('type', '!=', 'private')], search_dom])
        if channel_id:
            search_dom = expression.AND([[('channel_ids', 'in', channel_id)], search_dom])

        # Search partners that are also users
        domain = expression.AND([[('user_ids.id', '!=', False), ('user_ids.active', '=', True)], search_dom])
        partners = self.search(domain, limit=limit)

        # Search partners that are not users if less than 'limit' partner that are users found
        remaining_limit = limit - len(partners)
        if remaining_limit > 0:
            partners |= self.search(expression.AND([[('id', 'not in', partners.ids)], search_dom]), limit=remaining_limit)

        return [partner.mail_partner_format() for partner in partners]

    @api.model
    def im_search(self, name, limit=20):
        """ Search partner with a name and return its id, name and im_status.
            Note : the user must be logged
            :param name : the partner name to search
            :param limit : the limit of result to return
        """
        # This method is supposed to be used only in the context of channel creation or
        # extension via an invite. As both of these actions require the 'create' access
        # right, we check this specific ACL.
        if self.env['mail.channel'].check_access_rights('create', raise_exception=False):
            name = '%' + name + '%'
            excluded_partner_ids = [self.env.user.partner_id.id]
            self.env.cr.execute("""
                SELECT
                    U.id as user_id,
                    P.id as id,
                    P.name as name,
                    P.email as email,
                    CASE WHEN B.last_poll IS NULL THEN 'offline'
                         WHEN age(now() AT TIME ZONE 'UTC', B.last_poll) > interval %s THEN 'offline'
                         WHEN age(now() AT TIME ZONE 'UTC', B.last_presence) > interval %s THEN 'away'
                         ELSE 'online'
                    END as im_status
                FROM res_users U
                    JOIN res_partner P ON P.id = U.partner_id
                    LEFT JOIN bus_presence B ON B.user_id = U.id
                WHERE P.name ILIKE %s
                    AND P.id NOT IN %s
                    AND U.active = 't'
                ORDER BY P.name ASC, P.id ASC
                LIMIT %s
            """, ("%s seconds" % DISCONNECTION_TIMER, "%s seconds" % AWAY_TIMER, name, tuple(excluded_partner_ids), limit))
            return self.env.cr.dictfetchall()
        else:
            return {}
