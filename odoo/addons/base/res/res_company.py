# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import os
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class Company(models.Model):
    _name = "res.company"
    _description = 'Companies'
    _order = 'sequence, name'

    _header = """
<header>
<pageTemplate>
    <frame id="first" x1="28.0" y1="28.0" width="%s" height="%s"/>
    <stylesheet>
       <!-- Set here the default font to use for all <para> tags -->
       <paraStyle name='Normal' fontName="DejaVuSans"/>
    </stylesheet>
    <pageGraphics>
        <fill color="black"/>
        <stroke color="black"/>
        <setFont name="DejaVuSans" size="8"/>
        <drawString x="%s" y="%s"> [[ formatLang(time.strftime("%%Y-%%m-%%d"), date=True) ]]  [[ time.strftime("%%H:%%M") ]]</drawString>
        <setFont name="DejaVuSans-Bold" size="10"/>
        <drawCentredString x="%s" y="%s">[[ company.partner_id.name ]]</drawCentredString>
        <stroke color="#000000"/>
        <lines>%s</lines>
        <!-- Set here the default font to use for all <drawString> tags -->
        <!-- don't forget to change the 2 other occurence of <setFont> above if needed --> 
        <setFont name="DejaVuSans" size="8"/>
    </pageGraphics>
</pageTemplate>
</header>"""

    _header2 = _header % (539, 772, "1.0cm", "28.3cm", "11.1cm", "28.3cm", "1.0cm 28.1cm 20.1cm 28.1cm")
    _header3 = _header % (786, 525, 25, 555, 440, 555, "25 550 818 550")

    _header_main = """
<header>
    <pageTemplate>
        <frame id="first" x1="1.3cm" y1="3.0cm" height="%s" width="19.0cm"/>
         <stylesheet>
            <!-- Set here the default font to use for all <para> tags -->
            <paraStyle name='Normal' fontName="DejaVuSans"/>
            <paraStyle name="main_footer" fontSize="8.0" alignment="CENTER"/>
            <paraStyle name="main_header" fontSize="8.0" leading="10" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
         </stylesheet>
        <pageGraphics>
            <!-- Set here the default font to use for all <drawString> tags -->
            <setFont name="DejaVuSans" size="8"/>
            <!-- You Logo - Change X,Y,Width and Height -->
            <image x="1.3cm" y="%s" height="40.0" >[[ company.logo or removeParentNode('image') ]]</image>
            <fill color="black"/>
            <stroke color="black"/>

            <!-- page header -->
            <lines>1.3cm %s 20cm %s</lines>
            <drawRightString x="20cm" y="%s">[[ company.rml_header1 ]]</drawRightString>
            <drawString x="1.3cm" y="%s">[[ company.partner_id.name ]]</drawString>
            <place x="1.3cm" y="%s" height="1.8cm" width="15.0cm">
                <para style="main_header">[[ display_address(company.partner_id) or  '' ]]</para>
            </place>
            <drawString x="1.3cm" y="%s">Phone:</drawString>
            <drawRightString x="7cm" y="%s">[[ company.partner_id.phone or '' ]]</drawRightString>
            <drawString x="1.3cm" y="%s">Mail:</drawString>
            <drawRightString x="7cm" y="%s">[[ company.partner_id.email or '' ]]</drawRightString>
            <lines>1.3cm %s 7cm %s</lines>

            <!-- left margin -->
            <rotate degrees="90"/>
            <fill color="grey"/>
            <drawString x="2.65cm" y="-0.4cm">generated by Odoo.com</drawString>
            <fill color="black"/>
            <rotate degrees="-90"/>

            <!--page bottom-->
            <lines>1.2cm 2.65cm 19.9cm 2.65cm</lines>
            <place x="1.3cm" y="0cm" height="2.55cm" width="19.0cm">
                <para style="main_footer">[[ company.rml_footer ]]</para>
                <para style="main_footer">Contact : [[ user.name ]] - Page: <pageNumber/></para>
            </place>
        </pageGraphics>
    </pageTemplate>
</header>"""

    _header_a4 = _header_main % ('21.7cm', '27.7cm', '27.7cm', '27.7cm', '27.8cm', '27.3cm', '25.3cm', '25.0cm', '25.0cm', '24.6cm', '24.6cm', '24.5cm', '24.5cm')
    _header_letter = _header_main % ('20cm', '26.0cm', '26.0cm', '26.0cm', '26.1cm', '25.6cm', '23.6cm', '23.3cm', '23.3cm', '22.9cm', '22.9cm', '22.8cm', '22.8cm')

    def _get_header(self):
        try:
            header_file = tools.file_open(os.path.join(
                'base', 'report', 'corporate_rml_header.rml'))
            try:
                return header_file.read()
            finally:
                header_file.close()
        except:
            return self._header_a4

    def _get_font(self):
        return self.env['res.font'].search([('family', '=', 'Helvetica'), ('mode', '=', 'all')], limit=1)

    def _get_logo(self):
        return open(os.path.join(tools.config['root_path'], 'addons', 'base', 'res', 'res_company_logo.png'), 'rb') .read().encode('base64')

    @api.model
    def _get_euro(self):
        return self.env['res.currency.rate'].search([('rate', '=', 1)], limit=1).currency_id

    @api.model
    def _get_user_currency(self):
        currency_id = self.env['res.users'].browse(self._uid).company_id.currency_id
        return currency_id or self._get_euro()

    name = fields.Char(related='partner_id.name', string='Company Name', required=True, store=True)
    parent_id = fields.Many2one('res.company', string='Parent Company', index=True)
    child_ids = fields.One2many('res.company', 'parent_id', string='Child Companies')
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    rml_header = fields.Text(required=True, default=_get_header)
    rml_header1 = fields.Char(string='Company Tagline', help="Appears by default on the top right corner of your printed documents (report header).")
    rml_header2 = fields.Text(string='RML Internal Header', required=True, default=_header2)
    rml_header3 = fields.Text(string='RML Internal Header for Landscape Reports', required=True, default=_header3)
    rml_footer = fields.Text(string='Custom Report Footer', translate=True, help="Footer text displayed at the bottom of all reports.")
    rml_footer_readonly = fields.Text(related='rml_footer', string='Report Footer', readonly=True)
    custom_footer = fields.Boolean(help="Check this to define the report footer manually. Otherwise it will be filled in automatically.")
    font = fields.Many2one('res.font', string="Font", default=lambda self: self._get_font(),
                           domain=[('mode', 'in', ('Normal', 'Regular', 'all', 'Book'))],
                           help="Set the font into the report header, it will be used as default font in the RML reports of the user company")
    logo = fields.Binary(related='partner_id.image', default=_get_logo)
    # logo_web: do not store in attachments, since the image is retrieved in SQL for
    # performance reasons (see addons/web/controllers/main.py, Binary.company_logo)
    logo_web = fields.Binary(compute='_compute_logo_web', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self._get_user_currency())
    user_ids = fields.Many2many('res.users', 'res_company_users_rel', 'cid', 'user_id', string='Accepted Users')
    account_no = fields.Char(string='Account No.')
    street = fields.Char(compute='_compute_address', inverse='_inverse_street')
    street2 = fields.Char(compute='_compute_address', inverse='_inverse_street2')
    zip = fields.Char(compute='_compute_address', inverse='_inverse_zip')
    city = fields.Char(compute='_compute_address', inverse='_inverse_city')
    state_id = fields.Many2one('res.country.state', compute='_compute_address', inverse='_inverse_state', string="Fed. State")
    bank_ids = fields.One2many('res.partner.bank', 'company_id', string='Bank Accounts', help='Bank accounts related to this company')
    country_id = fields.Many2one('res.country', compute='_compute_address', inverse='_inverse_country', string="Country")
    email = fields.Char(related='partner_id.email', store=True)
    phone = fields.Char(related='partner_id.phone', store=True)
    fax = fields.Char(compute='_compute_address', inverse='_inverse_fax')
    website = fields.Char(related='partner_id.website')
    vat = fields.Char(related='partner_id.vat', string="Tax ID")
    company_registry = fields.Char()
    rml_paper_format = fields.Selection([('a4', 'A4'), ('us_letter', 'US Letter')], string="Paper Format", required=True, default='a4', oldname='paper_format')
    sequence = fields.Integer(help='Used to order Companies in the company switcher', default=10)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The company name must be unique !')
    ]

    # TODO @api.depends(): currently now way to formulate the dependency on the
    # partner's contact address
    def _compute_address(self):
        for company in self.filtered(lambda company: company.partner_id):
            address_data = company.partner_id.sudo().address_get(adr_pref=['contact'])
            if address_data['contact']:
                partner = company.partner_id.browse(address_data['contact']).sudo()
                company.street = partner.street
                company.street2 = partner.street2
                company.city = partner.city
                company.zip = partner.zip
                company.state_id = partner.state_id
                company.country_id = partner.country_id
                company.fax = partner.fax

    def _inverse_street(self):
        for company in self:
            company.partner_id.street = company.street

    def _inverse_street2(self):
        for company in self:
            company.partner_id.street2 = company.street2

    def _inverse_zip(self):
        for company in self:
            company.partner_id.zip = company.zip

    def _inverse_city(self):
        for company in self:
            company.partner_id.city = company.city

    def _inverse_state(self):
        for company in self:
            company.partner_id.state_id = company.state_id

    def _inverse_country(self):
        for company in self:
            company.partner_id.country_id = company.country_id

    def _inverse_fax(self):
        for company in self:
            company.partner_id.fax = company.fax

    @api.depends('partner_id', 'partner_id.image')
    def _compute_logo_web(self):
        for company in self:
            company.logo_web = tools.image_resize_image(company.partner_id.image, (180, None))

    @api.onchange('custom_footer', 'phone', 'fax', 'email', 'website', 'vat', 'company_registry')
    def onchange_footer(self):
        if not self.custom_footer:
            # first line (notice that missing elements are filtered out before the join)
            res = ' | '.join(filter(bool, [
                self.phone            and '%s: %s' % (_('Phone'), self.phone),
                self.fax              and '%s: %s' % (_('Fax'), self.fax),
                self.email            and '%s: %s' % (_('Email'), self.email),
                self.website          and '%s: %s' % (_('Website'), self.website),
                self.vat              and '%s: %s' % (_('TIN'), self.vat),
                self.company_registry and '%s: %s' % (_('Reg'), self.company_registry),
            ]))
            self.rml_footer_readonly = res
            self.rml_footer = res

    @api.onchange('state_id')
    def _onchange_state(self):
        self.country_id = self.state_id.country_id

    @api.onchange('font')
    def _onchange_font_name(self):
        """ To change default header style of all <para> and drawstring. """
        def _change_header(header, font):
            """ Replace default fontname use in header and setfont tag """
            default_para = re.sub(r'fontName.?=.?".*"', 'fontName="%s"' % font, header)
            return re.sub(r'(<setFont.?name.?=.?)(".*?")(.)', '\g<1>"%s"\g<3>' % font, default_para)

        if self.font:
            fontname = self.font.name
            self.rml_header = _change_header(self.rml_header, fontname)
            self.rml_header2 = _change_header(self.rml_header2, fontname)
            self.rml_header3 = _change_header(self.rml_header3, fontname)

    @api.multi
    def on_change_country(self, country_id):
        # This function is called from account/models/chart_template.py, hence decorated with `multi`.
        self.ensure_one()
        currency_id = self._get_user_currency()
        if country_id:
            currency_id = self.env['res.country'].browse(country_id).currency_id.id
        return {'value': {'currency_id': currency_id}}

    @api.onchange('country_id')
    def _onchange_country_id_wrapper(self):
        res = {'domain': {'state_id': []}}
        if self.country_id:
            res['domain']['state_id'] = [('country_id', '=', self.country_id.id)]
        values = self.on_change_country(self.country_id.id)['value']
        for fname, value in values.iteritems():
            setattr(self, fname, value)
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        context = dict(self.env.context)
        newself = self
        if context.pop('user_preference', None):
            # We browse as superuser. Otherwise, the user would be able to
            # select only the currently visible companies (according to rules,
            # which are probably to allow to see the child companies) even if
            # she belongs to some other companies.
            companies = self.env.user.company_id + self.env.user.company_ids
            args = (args or []) + [('id', 'in', companies.ids)]
            newself = newself.sudo()
        return super(Company, newself.with_context(context)).name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    @api.returns('self', lambda value: value.id)
    def _company_default_get(self, object=False, field=False):
        """ Returns the default company (usually the user's company).
        The 'object' and 'field' arguments are ignored but left here for
        backward compatibility and potential override.
        """
        return self.env['res.users']._get_company()

    @api.model
    @tools.ormcache('self.env.uid', 'company')
    def _get_company_children(self, company=None):
        if not company:
            return []
        return self.search([('parent_id', 'child_of', [company])]).ids

    @api.multi
    def _get_partner_hierarchy(self):
        self.ensure_one()
        parent = self.parent_id
        if parent:
            return parent._get_partner_hierarchy()
        else:
            return self._get_partner_descendance([])

    @api.multi
    def _get_partner_descendance(self, descendance):
        self.ensure_one()
        descendance.append(self.partner_id.id)
        for child_id in self._get_company_children(self.id):
            if child_id != self.id:
                descendance = self.browse(child_id)._get_partner_descendance(descendance)
        return descendance

    # deprecated, use clear_caches() instead
    def cache_restart(self):
        self.clear_caches()

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('partner_id'):
            self.clear_caches()
            return super(Company, self).create(vals)
        partner = self.env['res.partner'].create({
            'name': vals['name'],
            'is_company': True,
            'image': vals.get('logo'),
            'customer': False,
            'email': vals.get('email'),
            'phone': vals.get('phone'),
            'website': vals.get('website'),
            'vat': vals.get('vat'),
        })
        vals['partner_id'] = partner.id
        self.clear_caches()
        company = super(Company, self).create(vals)
        partner.write({'company_id': company.id})
        return company

    @api.multi
    def write(self, values):
        self.clear_caches()
        return super(Company, self).write(values)

    @api.onchange('rml_paper_format')
    def _onchange_rml_paper_format(self):
        if self.rml_paper_format == 'us_letter':
            self.rml_header = self._header_letter
        else:
            self.rml_header = self._header_a4

    @api.multi
    def act_discover_fonts(self):
        self.ensure_one()
        return self.env["res.font"].font_scan()

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create recursive companies.'))
