# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
import uuid

from odoo import fields, models, api, registry, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import UserError
from odoo.tools.misc import _format_time_ago
from odoo.http import request
from odoo.osv import expression


class WebsiteTrack(models.Model):
    _name = 'website.track'
    _description = 'Visited Pages'
    _order = 'visit_datetime DESC'
    _log_access = False

    visitor_id = fields.Many2one('website.visitor', ondelete="cascade", index=True, required=True, readonly=True)
    page_id = fields.Many2one('website.page', index=True, ondelete='cascade', readonly=True)
    url = fields.Text('Url', index=True)
    visit_datetime = fields.Datetime('Visit Date', default=fields.Datetime.now, required=True, readonly=True)


class WebsiteVisitor(models.Model):
    _name = 'website.visitor'
    _description = 'Website Visitor'
    _order = 'last_connection_datetime DESC'

    name = fields.Char('Name')
    access_token = fields.Char(required=True, default=lambda x: uuid.uuid4().hex, index=True, copy=False, groups='base.group_website_publisher')
    active = fields.Boolean('Active', default=True)
    website_id = fields.Many2one('website', "Website", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Linked Partner", help="Partner of the last logged in user.")
    partner_image = fields.Binary(related='partner_id.image_1920')

    # localisation and info
    country_id = fields.Many2one('res.country', 'Country', readonly=True)
    country_flag = fields.Binary(related="country_id.image", string="Country Flag")
    lang_id = fields.Many2one('res.lang', string='Language', help="Language from the website when visitor has been created")
    timezone = fields.Selection(_tz_get, string='Timezone')
    email = fields.Char(string='Email', compute='_compute_email_phone')
    mobile = fields.Char(string='Mobile Phone', compute='_compute_email_phone')

    # Visit fields
    visit_count = fields.Integer('Number of visits', default=1, readonly=True, help="A new visit is considered if last connection was more than 8 hours ago.")
    website_track_ids = fields.One2many('website.track', 'visitor_id', string='Visited Pages History', readonly=True)
    visitor_page_count = fields.Integer('Page Views', compute="_compute_page_statistics", help="Total number of visits on tracked pages")
    page_ids = fields.Many2many('website.page', string="Visited Pages", compute="_compute_page_statistics")
    page_count = fields.Integer('# Visited Pages', compute="_compute_page_statistics", help="Total number of tracked page visited")
    last_visited_page_id = fields.Many2one('website.page', string="Last Visited Page", compute="_compute_last_visited_page_id")

    # Time fields
    create_date = fields.Datetime('First connection date', readonly=True)
    last_connection_datetime = fields.Datetime('Last Connection', default=fields.Datetime.now, help="Last page view date", readonly=True)
    time_since_last_action = fields.Char('Last action', compute="_compute_time_statistics", help='Time since last page view. E.g.: 2 minutes ago')
    is_connected = fields.Boolean('Is connected ?', compute='_compute_time_statistics', help='A visitor is considered as connected if his last page view was within the last 5 minutes.')

    _sql_constraints = [
        ('access_token_unique', 'unique(access_token)', 'Access token should be unique.'),
        ('partner_uniq', 'unique(partner_id)', 'A partner is linked to only one visitor.'),
    ]

    @api.depends('name')
    def name_get(self):
        return [(
            record.id,
            (record.name or _('Website Visitor #%s') % record.id)
        ) for record in self]

    @api.depends('partner_id.email_normalized', 'partner_id.mobile')
    def _compute_email_phone(self):
        results = self.env['res.partner'].search_read(
            [('id', 'in', self.partner_id.ids)],
            ['id', 'email_normalized', 'mobile'],
        )
        mapped_data = {
            result['id']: {
                'email_normalized': result['email_normalized'],
                'mobile': result['mobile']
            } for result in results
        }

        for visitor in self:
            visitor.email = mapped_data.get(visitor.partner_id.id, {}).get('email_normalized')
            visitor.mobile = mapped_data.get(visitor.partner_id.id, {}).get('mobile')

    @api.depends('website_track_ids')
    def _compute_page_statistics(self):
        results = self.env['website.track'].read_group(
            [('visitor_id', 'in', self.ids), ('url', '!=', False)], ['visitor_id', 'page_id', 'url'], ['visitor_id', 'page_id', 'url'], lazy=False)
        mapped_data = {}
        for result in results:
            visitor_info = mapped_data.get(result['visitor_id'][0], {'page_count': 0, 'visitor_page_count': 0, 'page_ids': set()})
            visitor_info['visitor_page_count'] += result['__count']
            visitor_info['page_count'] += 1
            if result['page_id']:
                visitor_info['page_ids'].add(result['page_id'][0])
            mapped_data[result['visitor_id'][0]] = visitor_info

        for visitor in self:
            visitor_info = mapped_data.get(visitor.id, {'page_count': 0, 'visitor_page_count': 0, 'page_ids': set()})
            visitor.page_ids = [(6, 0, visitor_info['page_ids'])]
            visitor.visitor_page_count = visitor_info['visitor_page_count']
            visitor.page_count = visitor_info['page_count']

    @api.depends('website_track_ids.page_id')
    def _compute_last_visited_page_id(self):
        results = self.env['website.track'].read_group([('visitor_id', 'in', self.ids)],
                                                       ['visitor_id', 'page_id', 'visit_datetime:max'],
                                                       ['visitor_id', 'page_id'], lazy=False)
        mapped_data = {result['visitor_id'][0]: result['page_id'][0] for result in results if result['page_id']}
        for visitor in self:
            visitor.last_visited_page_id = mapped_data.get(visitor.id, False)

    @api.depends('last_connection_datetime')
    def _compute_time_statistics(self):
        results = self.env['website.visitor'].search_read([('id', 'in', self.ids)], ['id', 'last_connection_datetime'])
        mapped_data = {result['id']: result['last_connection_datetime'] for result in results}

        for visitor in self:
            last_connection_date = mapped_data[visitor.id]
            visitor.time_since_last_action = _format_time_ago(self.env, (datetime.now() - last_connection_date))
            visitor.is_connected = (datetime.now() - last_connection_date) < timedelta(minutes=5)

    def _prepare_visitor_send_mail_values(self):
        if self.partner_id.email:
            return {
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'partner_ids': [self.partner_id.id],
            }
        return {}

    def action_send_mail(self):
        self.ensure_one()
        visitor_mail_values = self._prepare_visitor_send_mail_values()
        if not visitor_mail_values:
            raise UserError(_("There is no email linked this visitor."))
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model=visitor_mail_values.get('res_model'),
            default_res_id=visitor_mail_values.get('res_id'),
            default_use_template=False,
            default_partner_ids=[(6, 0, visitor_mail_values.get('partner_ids'))],
            default_composition_mode='comment',
            default_reply_to=self.env.user.partner_id.email,
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def _get_visitor_from_request(self):
        """ Return the visitor as sudo from the request if there is a visitor_uuid cookie.
            It is possible that the partner has changed or has disconnected.
            In that case the cookie is still referencing the old visitor and need to be replaced
            with the one of the visitor returned !!!. """
        if not request:
            return None
        Visitor = self.env['website.visitor'].sudo()
        visitor = Visitor
        access_token = request.httprequest.cookies.get('visitor_uuid')
        if access_token:
            visitor = Visitor.with_context(active_test=False).search([('access_token', '=', access_token)])

        if not request.env.user._is_public():
            partner_id = request.env.user.partner_id
            if not visitor or visitor.partner_id != partner_id:
                # Partner and no cookie or wrong cookie
                visitor = Visitor.with_context(active_test=False).search([('partner_id', '=', partner_id.id)])
        elif visitor and visitor.partner_id:
            # Cookie associated to a Partner
            visitor = Visitor
        return visitor

    def _get_visitor_from_request_or_create(self):
        """ Return a tuple (visitor, response), see _get_visitor_from_request
            If there is no visitor creates it and ensure the consistancy of the cookie. """
        visitor_sudo = self._get_visitor_from_request()
        if not visitor_sudo:
            visitor_sudo = self._create_visitor()
        return visitor_sudo

    def _handle_webpage_dispatch(self, response, website_page):
        # get visitor. Done here to avoid having to do it multiple times in case of override.
        visitor_sudo = self._get_visitor_from_request_or_create()
        if request.httprequest.cookies.get('visitor_uuid', '') != visitor_sudo.access_token:
            expiration_date = datetime.now() + timedelta(days=365)
            response.set_cookie('visitor_uuid', visitor_sudo.access_token, expires=expiration_date)
        self._handle_website_page_visit(response, website_page, visitor_sudo)

    def _handle_website_page_visit(self, response, website_page, visitor_sudo):
        """ Called on dispatch. This will create a website.visitor if the http request object
        is a tracked website page or a tracked view. Only on tracked elements to avoid having
        too much operations done on every page or other http requests.
        Note: The side effect is that the last_connection_datetime is updated ONLY on tracked elements."""
        url = request.httprequest.url
        website_track_values = {
            'url': url,
            'visit_datetime': datetime.now(),
        }
        if website_page:
            website_track_values['page_id'] = website_page.id
            domain = [('page_id', '=', website_page.id)]
        else:
            domain = [('url', '=', url)]
        visitor_sudo._add_tracking(domain, website_track_values)
        if visitor_sudo.lang_id.id != request.lang.id:
            visitor_sudo.write({'lang_id': request.lang.id})

    def _add_tracking(self, domain, website_track_values):
        """ Add the track and update the visitor"""
        domain = expression.AND([domain, [('visitor_id', '=', self.id)]])
        last_view = self.env['website.track'].sudo().search(domain, limit=1)
        if not last_view or last_view.visit_datetime < datetime.now() - timedelta(minutes=30):
            website_track_values['visitor_id'] = self.id
            self.env['website.track'].create(website_track_values)
        self._update_visitor_last_visit()

    def _create_visitor(self, website_track_values=None):
        """ Create a visitor and add a track to it if website_track_values is set."""
        country_code = request.session.get('geoip', {}).get('country_code', False)
        country_id = request.env['res.country'].sudo().search([('code', '=', country_code)], limit=1).id if country_code else False
        vals = {
            'lang_id': request.lang.id,
            'country_id': country_id,
            'website_id': request.website.id,
        }
        if not self.env.user._is_public():
            vals['partner_id'] = self.env.user.partner_id.id
            vals['name'] = self.env.user.partner_id.name
        if website_track_values:
            vals['website_track_ids'] = [(0, 0, website_track_values)]
        return self.sudo().create(vals)

    def _cron_archive_visitors(self):
        one_week_ago = datetime.now() - timedelta(days=7)
        visitors_to_archive = self.env['website.visitor'].sudo().search([('last_connection_datetime', '<', one_week_ago)])
        visitors_to_archive.write({'active': False})

    def _update_visitor_last_visit(self):
        """ We need to do this part here to avoid concurrent updates error. """
        with registry(self.env.cr.dbname).cursor() as cr:
            date_now = datetime.now()
            query = "UPDATE website_visitor SET "
            if self.last_connection_datetime < (date_now - timedelta(hours=8)):
                query += "visit_count = visit_count + 1,"
            query += """
                active = True,
                last_connection_datetime = %s
                WHERE id = %s
            """
            try:
                cr.execute(query, (date_now, self.id), log_exceptions=False)
                cr.commit()
            except Exception:
                cr.rollback()
