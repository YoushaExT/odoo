# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from random import randint

from odoo import api, fields, models
from odoo.tools.translate import _, html_translate
from odoo.addons.http_routing.models.ir_http import slug


class TrackTag(models.Model):
    _name = "event.track.tag"
    _description = 'Event Track Tag'
    _order = 'name'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char('Tag Name', required=True)
    track_ids = fields.Many2many('event.track', string='Tracks')
    color = fields.Integer(
        string='Color Index', default=lambda self: self._default_color(),
        help="Note that colorless tags won't be available on the website.")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class TrackLocation(models.Model):
    _name = "event.track.location"
    _description = 'Event Track Location'

    name = fields.Char('Location', required=True)


class Track(models.Model):
    _name = "event.track"
    _description = 'Event Track'
    _order = 'priority, date'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.seo.metadata', 'website.published.mixin']

    @api.model
    def _get_default_stage_id(self):
        return self.env['event.track.stage'].search([], limit=1).id

    name = fields.Char('Title', required=True, translate=True)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', related='event_id.company_id')
    partner_id = fields.Many2one('res.partner', 'Speaker')
    partner_name = fields.Char(
        string='Name', compute='_compute_partner_info',
        readonly=False, store=True, tracking=10)
    partner_email = fields.Char(
        string='Email', compute='_compute_partner_info',
        readonly=False, store=True, tracking=20)
    partner_phone = fields.Char(
        string='Phone', compute='_compute_partner_info',
        readonly=False, store=True, tracking=30)
    partner_biography = fields.Html(string='Biography')
    tag_ids = fields.Many2many('event.track.tag', string='Tags')
    stage_id = fields.Many2one(
        'event.track.stage', string='Stage', ondelete='restrict',
        index=True, copy=False, default=_get_default_stage_id,
        group_expand='_read_group_stage_ids',
        required=True, tracking=True)
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        copy=False, default='normal', required=True, tracking=True,
        help="A track's kanban state indicates special situations affecting it:\n"
             " * Grey is the default situation\n"
             " * Red indicates something is preventing the progress of this track\n"
             " * Green indicates the track is ready to be pulled to the next stage")
    description = fields.Html(translate=html_translate, sanitize_attributes=False, sanitize_form=False)
    date = fields.Datetime('Track Date')
    date_end = fields.Datetime('Track End Date', compute='_compute_end_date', store=True)
    duration = fields.Float('Duration', default=1.5, help="Track duration in hours.")
    location_id = fields.Many2one('event.track.location', 'Location')
    event_id = fields.Many2one('event.event', 'Event', required=True)
    color = fields.Integer('Color')
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Medium'),
        ('2', 'High'), ('3', 'Highest')],
        'Priority', required=True, default='1')
    image = fields.Image("Image", max_width=128, max_height=128)

    @api.depends('name')
    def _compute_website_url(self):
        super(Track, self)._compute_website_url()
        for track in self:
            if track.id:
                track.website_url = '/event/%s/track/%s' % (slug(track.event_id), slug(track))

    @api.depends('partner_id')
    def _compute_partner_info(self):
        for track in self:
            if track.partner_id:
                track.partner_name = track.partner_id.name
                track.partner_email = track.partner_id.email
                track.partner_phone = track.partner_id.phone

    @api.depends('date', 'duration')
    def _compute_end_date(self):
        for track in self:
            if track.date:
                delta = timedelta(minutes=60 * track.duration)
                track.date_end = track.date + delta
            else:
                track.date_end = False

    @api.model_create_multi
    def create(self, vals_list):
        tracks = super(Track, self).create(vals_list)

        for track in tracks:
            track.event_id.message_post_with_view(
                'website_event_track.event_track_template_new',
                values={'track': track},
                subject=track.name,
                subtype_id=self.env.ref('website_event_track.mt_event_track').id,
            )

        return tracks

    def write(self, vals):
        if 'stage_id' in vals and 'kanban_state' not in vals:
            vals['kanban_state'] = 'normal'
        res = super(Track, self).write(vals)
        if vals.get('partner_id'):
            self.message_subscribe([vals['partner_id']])
        return res

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Always display all stages """
        return stages.search([], order=order)

    def _track_template(self, changes):
        res = super(Track, self)._track_template(changes)
        track = self[0]
        if 'stage_id' in changes and track.stage_id.mail_template_id:
            res['stage_id'] = (track.stage_id.mail_template_id, {
                'composition_mode': 'comment',
                'auto_delete_message': True,
                'subtype_id': self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light'
            })
        return res

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'kanban_state' in init_values and self.kanban_state == 'blocked':
            return self.env.ref('website_event_track.mt_track_blocked')
        elif 'kanban_state' in init_values and self.kanban_state == 'done':
            return self.env.ref('website_event_track.mt_track_ready')
        return super(Track, self)._track_subtype(init_values)

    def _message_get_suggested_recipients(self):
        recipients = super(Track, self)._message_get_suggested_recipients()
        for track in self:
            if track.partner_email and track.partner_email != track.partner_id.email:
                track._message_add_suggested_recipient(recipients, email=track.partner_email, reason=_('Speaker Email'))
        return recipients

    def _message_post_after_hook(self, message, msg_vals):
        if self.partner_email and not self.partner_id:
            # we consider that posting a message with a specified recipient (not a follower, a specific one)
            # on a document without customer means that it was created through the chatter using
            # suggested recipients. This heuristic allows to avoid ugly hacks in JS.
            new_partner = message.partner_ids.filtered(lambda partner: partner.email == self.partner_email)
            if new_partner:
                self.search([
                    ('partner_id', '=', False),
                    ('partner_email', '=', new_partner.email),
                    ('stage_id.is_cancel', '=', False),
                ]).write({'partner_id': new_partner.id})
        return super(Track, self)._message_post_after_hook(message, msg_vals)

    def open_track_speakers_list(self):
        return {
            'name': _('Speakers'),
            'domain': [('id', 'in', self.mapped('partner_id').ids)],
            'view_mode': 'kanban,form',
            'res_model': 'res.partner',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
