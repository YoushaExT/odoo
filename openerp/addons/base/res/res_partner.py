# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import datetime
import hashlib
import pytz
import threading
import urllib2
import urlparse
from lxml import etree

from odoo import api, fields, models, tools, _
from odoo.modules import get_module_resource
from odoo.osv.expression import get_unaccent_wrapper
from odoo.exceptions import UserError, ValidationError

ADDRESS_FORMAT_CLASSES = {
    '%(city)s %(state_code)s\n%(zip)s': 'o_city_state',
    '%(zip)s %(city)s': 'o_zip_city'
}

ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')
@api.model
def _lang_get(self):
    return self.env['res.lang'].get_installed()

@api.model
def _tz_get(self):
    # put POSIX 'Etc/*' entries at the end to avoid confusing users - see bug 1086728
    return [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]


class FormatAddress(object):
    @api.model
    def fields_view_get_address(self, arch):
        address_format = self.env.user.company_id.country_id.address_format or ''
        for format_pattern, format_class in ADDRESS_FORMAT_CLASSES.iteritems():
            if format_pattern in address_format:
                doc = etree.fromstring(arch)
                for address_node in doc.xpath("//div[@class='o_address_format']"):
                    # add address format class to address block
                    address_node.attrib['class'] += ' ' + format_class
                    if format_class.startswith('o_zip'):
                        zip_fields = address_node.xpath("//field[@name='zip']")
                        city_fields = address_node.xpath("//field[@name='city']")
                        if zip_fields and city_fields:
                            # move zip field before city field
                            city_fields[0].addprevious(zip_fields[0])
                arch = etree.tostring(doc)
                break
        return arch


class PartnerCategory(models.Model):
    _description = 'Partner Tags'
    _name = 'res.partner.category'
    _order = 'parent_left, name'
    _parent_store = True
    _parent_order = 'name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')
    parent_id = fields.Many2one('res.partner.category', string='Parent Category', index=True, ondelete='cascade')
    child_ids = fields.One2many('res.partner.category', 'parent_id', string='Child Tags')
    active = fields.Boolean(default=True, help="The active field allows you to hide the category without removing it.")
    parent_left = fields.Integer(string='Left parent', index=True)
    parent_right = fields.Integer(string='Right parent', index=True)
    partner_ids = fields.Many2many('res.partner', column1='category_id', column2='partner_id', string='Partners')

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You can not create recursive tags.'))

    @api.multi
    def name_get(self):
        """ Return the categories' display name, including their direct
            parent by default.

            If ``context['partner_category_display']`` is ``'short'``, the short
            version of the category name (without the direct parent) is used.
            The default is the long version.
        """
        if self._context.get('partner_category_display') == 'short':
            return super(PartnerCategory, self).name_get()

        res = []
        for category in self:
            names = []
            current = category
            while current:
                names.append(current.name)
                current = current.parent_id
            res.append((category.id, ' / '.join(reversed(names))))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            # Be sure name_search is symetric to name_get
            name = name.split(' / ')[-1]
            args = [('name', operator, name)] + args
        return self.search(args, limit=limit).name_get()


class PartnerTitle(models.Model):
    _name = 'res.partner.title'
    _order = 'name'

    name = fields.Char(string='Title', required=True, translate=True)
    shortcut = fields.Char(string='Abbreviation', translate=True)

    _sql_constraints = [('name_uniq', 'unique (name)', "Title name already exists !")]


class Partner(models.Model, FormatAddress):
    _description = 'Partner'
    _name = "res.partner"
    _order = "display_name"

    def _default_category(self):
        return self.env['res.partner.category'].browse(self._context.get('category_id'))

    def _default_company(self):
        return self.env['res.company']._company_default_get('res.partner')

    name = fields.Char(index=True)
    display_name = fields.Char(compute='_compute_display_name', string='Name', store=True, index=True)
    date = fields.Date(index=True)
    title = fields.Many2one('res.partner.title')
    parent_id = fields.Many2one('res.partner', string='Related Company', index=True)
    parent_name = fields.Char(related='parent_id.name', readonly=True, string='Parent name')
    child_ids = fields.One2many('res.partner', 'parent_id', string='Contacts', domain=[('active', '=', True)])  # force "active_test" domain to bypass _search() override
    ref = fields.Char(string='Internal Reference', index=True)
    lang = fields.Selection(_lang_get, string='Language', default=lambda self: self.env.lang,
                            help="If the selected language is loaded in the system, all documents related to "
                                 "this contact will be printed in this language. If not, it will be English.")
    tz = fields.Selection(_tz_get, string='Timezone', default=lambda self: self._context.get('tz'),
                          help="The partner's timezone, used to output proper date and time values "
                               "inside printed reports. It is important to set a value for this field. "
                               "You should use the same timezone that is otherwise used to pick and "
                               "render date and time values: your computer's timezone.")
    tz_offset = fields.Char(compute='_compute_tz_offset', string='Timezone offset', invisible=True)
    user_id = fields.Many2one('res.users', string='Salesperson',
      help='The internal user that is in charge of communicating with this contact if any.')
    vat = fields.Char(string='TIN', help="Tax Identification Number. "
                                         "Fill it if the company is subjected to taxes. "
                                         "Used by the some of the legal statements.")
    bank_ids = fields.One2many('res.partner.bank', 'partner_id', string='Banks')
    website = fields.Char(help="Website of Partner or Company")
    comment = fields.Text(string='Notes')

    category_id = fields.Many2many('res.partner.category', column1='partner_id',
                                    column2='category_id', string='Tags', default=_default_category)
    credit_limit = fields.Float(string='Credit Limit')
    barcode = fields.Char(oldname='ean13')
    active = fields.Boolean(default=True)
    customer = fields.Boolean(string='Is a Customer', default=True,
                               help="Check this box if this contact is a customer.")
    supplier = fields.Boolean(string='Is a Vendor',
                               help="Check this box if this contact is a vendor. "
                               "If it's not checked, purchase people will not see it when encoding a purchase order.")
    employee = fields.Boolean(help="Check this box if this contact is an Employee.")
    function = fields.Char(string='Job Position')
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Other address')], string='Address Type',
        default='contact',
        help="Used to select automatically the right address according to the context in sales and purchases documents.")
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict')
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    email = fields.Char()
    phone = fields.Char()
    fax = fields.Char()
    mobile = fields.Char()
    birthdate = fields.Char()
    is_company = fields.Boolean(string='Is a Company', default=False,
        help="Check if the contact is a company, otherwise it is a person")
    # company_type is only an interface field, do not use it in business logic
    company_type = fields.Selection(string='Company Type',
        selection=[('person', 'Individual'), ('company', 'Company')],
        compute='_compute_company_type', readonly=False)
    company_id = fields.Many2one('res.company', 'Company', index=True, default=_default_company)
    color = fields.Integer(string='Color Index', default=0)
    user_ids = fields.One2many('res.users', 'partner_id', string='Users', auto_join=True)
    contact_address = fields.Char(compute='_compute_contact_address', string='Complete Address')

    # technical field used for managing commercial fields
    commercial_partner_id = fields.Many2one('res.partner', compute='_compute_commercial_partner',
                                             string='Commercial Entity', store=True)

    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary("Image", attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    image_medium = fields.Binary("Medium-sized image", attachment=True,
        help="Medium-sized image of this contact. It is automatically "\
             "resized as a 128x128px image, with aspect ratio preserved. "\
             "Use this field in form views or some kanban views.")
    image_small = fields.Binary("Small-sized image", attachment=True,
        help="Small-sized image of this contact. It is automatically "\
             "resized as a 64x64px image, with aspect ratio preserved. "\
             "Use this field anywhere a small image is required.")

    _sql_constraints = [
        ('check_name', "CHECK( (type='contact' AND name IS NOT NULL) or (type!='contact') )", 'Contacts require a name.'),
    ]

    @api.depends('is_company', 'name', 'parent_id.name', 'type')
    def _compute_display_name(self):
        diff = dict(show_address=None, show_address_only=None, show_email=None)
        names = dict(self.with_context(**diff).name_get())
        for partner in self:
            partner.display_name = names.get(partner.id)

    @api.depends('tz')
    def _compute_tz_offset(self):
        for partner in self:
            partner.tz_offset = datetime.datetime.now(pytz.timezone(partner.tz or 'GMT')).strftime('%z')

    @api.depends(lambda self: self._display_address_depends())
    def _compute_contact_address(self):
        for partner in self:
            partner.contact_address = partner._display_address()

    @api.depends('is_company', 'parent_id.commercial_partner_id')
    def _compute_commercial_partner(self):
        for partner in self:
            if partner.is_company or not partner.parent_id:
                partner.commercial_partner_id = partner
            else:
                partner.commercial_partner_id = partner.parent_id.commercial_partner_id

    @api.model
    def _get_default_image(self, partner_type, is_company, parent_id):
        if getattr(threading.currentThread(), 'testing', False) or self._context.get('install_mode'):
            return False

        colorize, img_path, image = False, False, False

        if partner_type in ['contact', 'other'] and parent_id:
            parent_image = self.browse(parent_id).image
            image = parent_image and parent_image.decode('base64') or None

        if not image and partner_type == 'invoice':
            img_path = get_module_resource('base', 'static/src/img', 'money.png')
        elif not image and partner_type == 'delivery':
            img_path = get_module_resource('base', 'static/src/img', 'truck.png')
        elif not image and is_company:
            img_path = get_module_resource('base', 'static/src/img', 'company_image.png')
        elif not image:
            img_path = get_module_resource('base', 'static/src/img', 'avatar.png')
            colorize = True

        if img_path:
            with open(img_path, 'rb') as f:
                image = f.read()
        if image and colorize:
            image = tools.image_colorize(image)

        return tools.image_resize_image_big(image.encode('base64'))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        if (not view_id) and (view_type == 'form') and self._context.get('force_email'):
            view_id = self.env.ref('base.view_partner_simple_form').id
        res = super(Partner, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            res['arch'] = self.fields_view_get_address(res['arch'])
        return res

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive Partner hierarchies.'))

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {}, name=_('%s (copy)') % self.name)
        return super(Partner, self).copy(default)

    @api.onchange('parent_id')
    def onchange_parent_id(self):
        # return values in result, as this method is used by _fields_sync()
        if not self.parent_id:
            return
        result = {}
        partner = getattr(self, '_origin', self)
        if partner.parent_id and partner.parent_id != self.parent_id:
            result['warning'] = {
                'title': _('Warning'),
                'message': _('Changing the company of a contact should only be done if it '
                             'was never correctly set. If an existing contact starts working for a new '
                             'company then a new contact should be created under that new '
                             'company. You can use the "Discard" button to abandon this change.')}
        if partner.type == 'contact' or self.type == 'contact':
            # for contacts: copy the parent address, if set (aka, at least one
            # value is set in the address: otherwise, keep the one from the
            # contact)
            address_fields = self._address_fields()
            if any(self.parent_id[key] for key in address_fields):
                def convert(value):
                    return value.id if isinstance(value, models.BaseModel) else value
                result['value'] = {key: convert(self.parent_id[key]) for key in address_fields}
        return result

    @api.onchange('state_id')
    def onchange_state(self):
        if self.state_id:
            self.country_id = self.state_id.country_id

    @api.onchange('email')
    def onchange_email(self):
        if not self.image and not self._context.get('yaml_onchange') and self.email:
            self.image = self._get_gravatar_image(self.email)

    @api.depends('is_company')
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = 'company' if partner.is_company else 'person'

    @api.onchange('company_type')
    def onchange_company_type(self):
        self.is_company = (self.company_type == 'company')

    @api.v7
    def _update_fields_values(self, cr, uid, partner, fields, context=None):
        return Partner._update_fields_values(partner, fields)

    @api.v8
    def _update_fields_values(self, fields):
        """ Returns dict of write() values for synchronizing ``fields`` """
        values = {}
        for fname in fields:
            field = self._fields[fname]
            if field.type == 'many2one':
                values[fname] = self[fname].id
            elif field.type == 'one2many':
                raise AssertionError(_('One2Many fields cannot be synchronized as part of `commercial_fields` or `address fields`'))
            elif field.type == 'many2many':
                values[fname] = [(6, 0, self[fname].ids)]
            else:
                values[fname] = self[fname]
        return values

    @api.model
    def _address_fields(self):
        """Returns the list of address fields that are synced from the parent."""
        return list(ADDRESS_FIELDS)

    @api.multi
    def update_address(self, vals):
        addr_vals = {key: vals[key] for key in self._address_fields() if key in vals}
        if addr_vals:
            return super(Partner, self).write(addr_vals)

    @api.model
    def _commercial_fields(self):
        """ Returns the list of fields that are managed by the commercial entity
        to which a partner belongs. These fields are meant to be hidden on
        partners that aren't `commercial entities` themselves, and will be
        delegated to the parent `commercial entity`. The list is meant to be
        extended by inheriting classes. """
        return ['vat', 'credit_limit']

    @api.v7
    def _commercial_sync_from_company(self, cr, uid, partner, context=None):
        return Partner._commercial_sync_from_company(partner)

    @api.v8
    def _commercial_sync_from_company(self):
        """ Handle sync of commercial fields when a new parent commercial entity is set,
        as if they were related fields """
        commercial_partner = self.commercial_partner_id
        if commercial_partner != self:
            sync_vals = commercial_partner._update_fields_values(self._commercial_fields())
            self.write(sync_vals)

    @api.v7
    def _commercial_sync_to_children(self, cr, uid, partner, context=None):
        return Partner._commercial_sync_to_children(partner)

    @api.v8
    def _commercial_sync_to_children(self):
        """ Handle sync of commercial fields to descendants """
        commercial_partner = self.commercial_partner_id
        sync_vals = commercial_partner._update_fields_values(self._commercial_fields())
        sync_children = self.child_ids.filtered(lambda c: not c.is_company)
        for child in sync_children:
            child._commercial_sync_to_children()
        return sync_children.write(sync_vals)

    @api.v7
    def _fields_sync(self, cr, uid, partner, values, context=None):
        return Partner._fields_sync(partner, values)

    @api.v8
    def _fields_sync(self, values):
        """ Sync commercial fields and address fields from company and to children after create/update,
        just as if those were all modeled as fields.related to the parent """
        # 1. From UPSTREAM: sync from parent
        if values.get('parent_id') or values.get('type', 'contact'):
            # 1a. Commercial fields: sync if parent changed
            if values.get('parent_id'):
                self._commercial_sync_from_company()
            # 1b. Address fields: sync if parent or use_parent changed *and* both are now set 
            if self.parent_id and self.type == 'contact':
                onchange_vals = self.onchange_parent_id().get('value', {})
                self.update_address(onchange_vals)

        # 2. To DOWNSTREAM: sync children
        if self.child_ids:
            # 2a. Commercial Fields: sync if commercial entity
            if self.commercial_partner_id == self:
                commercial_fields = self._commercial_fields()
                if any(field in values for field in commercial_fields):
                    self._commercial_sync_to_children()
            # 2b. Address fields: sync if address changed
            address_fields = self._address_fields()
            if any(field in values for field in address_fields):
                contacts = self.child_ids.filtered(lambda c: c.type == 'contact')
                contacts.update_address(values)

    @api.v7
    def _handle_first_contact_creation(self, cr, uid, partner, context=None):
        return Partner._handle_first_contact_creation(partner)

    @api.v8
    def _handle_first_contact_creation(self):
        """ On creation of first contact for a company (or root) that has no address, assume contact address
        was meant to be company address """
        parent = self.parent_id
        address_fields = self._address_fields()
        if (parent.is_company or not parent.parent_id) and len(parent.child_ids) == 1 and \
            any(self[f] for f in address_fields) and not any(parent[f] for f in address_fields):
            addr_vals = self._update_fields_values(address_fields)
            parent.update_address(addr_vals)

    def _clean_website(self, website):
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(website)
        if not scheme:
            if not netloc:
                netloc, path = path, ''
            website = urlparse.urlunparse(('http', netloc, path, params, query, fragment))
        return website

    @api.multi
    def write(self, vals):
        # res.partner must only allow to set the company_id of a partner if it
        # is the same as the company of all users that inherit from this partner
        # (this is to allow the code from res_users to write to the partner!) or
        # if setting the company_id to False (this is compatible with any user
        # company)
        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])
            for partner in self:
                if partner.user_ids:
                    companies = set(user.company_id for user in partner.user_ids)
                    if len(companies) > 1 or company not in companies:
                        raise UserError(_("You can not change the company as the partner/user has multiple user linked with different companies."))
        tools.image_resize_images(vals)

        result = super(Partner, self).write(vals)
        for partner in self:
            if any(u.has_group('base.group_user') for u in partner.user_ids if u != self.env.user):
                self.env['res.users'].check_access_rights('write')
            partner._fields_sync(vals)
        return result

    @api.model
    def create(self, vals):
        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        # compute default image in create, because computing gravatar in the onchange
        # cannot be easily performed if default images are in the way
        if not vals.get('image'):
            vals['image'] = self._get_default_image(vals.get('type'), vals.get('is_company'), vals.get('parent_id'))
        partner = super(Partner, self).create(vals)
        partner._fields_sync(vals)
        partner._handle_first_contact_creation()
        tools.image_resize_images(vals)
        return partner

    @api.multi
    def open_commercial_entity(self):
        """ Utility method used to add an "Open Company" button in partner views """
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'res_id': self.commercial_partner_id.id,
                'target': 'current',
                'flags': {'form': {'action_buttons': True}}}

    @api.multi
    def open_parent(self):
        """ Utility method used to add an "Open Parent" button in partner views """
        self.ensure_one()
        address_form_id = self.env.ref('base.view_partner_address_form').id
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'views': [(address_form_id, 'form')],
                'res_id': self.parent_id.id,
                'target': 'new',
                'flags': {'form': {'action_buttons': True}}}

    @api.multi
    def name_get(self):
        res = []
        types_dict = dict(self.fields_get()['type']['selection'])
        for partner in self:
            name = partner.name or ''
            if partner.parent_id and not partner.is_company:
                if not name and partner.type in ['invoice', 'delivery', 'other']:
                    name = types_dict[partner.type]
                name = "%s, %s" % (partner.parent_name, name)
            if self._context.get('show_address_only'):
                name = partner._display_address(without_company=True)
            if self._context.get('show_address'):
                name = name + "\n" + partner._display_address(without_company=True)
            name = name.replace('\n\n', '\n')
            name = name.replace('\n\n', '\n')
            if self._context.get('show_email') and partner.email:
                name = "%s <%s>" % (name, partner.email)
            if self._context.get('html_format'):
                name = name.replace('\n', '<br/>')
            res.append((partner.id, name))
        return res

    def _parse_partner_name(self, text, context=None):
        """ Supported syntax:
            - 'Raoul <raoul@grosbedon.fr>': will find name and email address
            - otherwise: default, everything is set as the name """
        emails = tools.email_split(text.replace(' ', ','))
        if emails:
            email = emails[0]
            name = text[:text.index(email)].replace('"', '').replace('<', '').strip()
        else:
            name, email = text, ''
        return name, email

    @api.model
    def name_create(self, name):
        """ Override of orm's name_create method for partners. The purpose is
            to handle some basic formats to create partners using the
            name_create.
            If only an email address is received and that the regex cannot find
            a name, the name will have the email value.
            If 'force_email' key in context: must find the email address. """
        name, email = self._parse_partner_name(name)
        if self._context.get('force_email') and not email:
            raise UserError(_("Couldn't create contact without email address!"))
        if not name and email:
            name = email
        partner = self.create({self._rec_name: name or email, 'email': email or False})
        return partner.name_get()[0]

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """ Override search() to always show inactive children when searching via ``child_of`` operator. The ORM will
        always call search() with a simple domain of the form [('parent_id', 'in', [ids])]. """
        # a special ``domain`` is set on the ``child_ids`` o2m to bypass this logic, as it uses similar domain expressions
        if len(args) == 1 and len(args[0]) == 3 and args[0][:2] == ('parent_id','in') \
                and args[0][2] != [False]:
            self = self.with_context(active_test=False)
        return super(Partner, self)._search(args, offset=offset, limit=limit, order=order,
                                            count=count, access_rights_uid=access_rights_uid)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            self.check_access_rights('read')
            where_query = self._where_calc(args)
            self._apply_ir_rules(where_query, 'read')
            from_clause, where_clause, where_clause_params = where_query.get_sql()
            where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

            # search on the name of the contacts and of its company
            search_name = name
            if operator in ('ilike', 'like'):
                search_name = '%%%s%%' % name
            if operator in ('=ilike', '=like'):
                operator = operator[1:]

            unaccent = get_unaccent_wrapper(self.env.cr)

            query = """SELECT id
                         FROM res_partner
                      {where} ({email} {operator} {percent}
                           OR {display_name} {operator} {percent}
                           OR {reference} {operator} {percent})
                           -- don't panic, trust postgres bitmap
                     ORDER BY {display_name} {operator} {percent} desc,
                              {display_name}
                    """.format(where=where_str,
                               operator=operator,
                               email=unaccent('email'),
                               display_name=unaccent('display_name'),
                               reference=unaccent('ref'),
                               percent=unaccent('%s'))

            where_clause_params += [search_name]*4
            if limit:
                query += ' limit %s'
                where_clause_params.append(limit)
            self.env.cr.execute(query, where_clause_params)
            partner_ids = map(lambda x: x[0], self.env.cr.fetchall())

            if partner_ids:
                return self.browse(partner_ids).name_get()
            else:
                return []
        return super(Partner, self).name_search(name, args, operator=operator, limit=limit)

    @api.model
    def find_or_create(self, email):
        """ Find a partner with the given ``email`` or use :py:method:`~.name_create`
            to create one

            :param str email: email-like string, which should contain at least one email,
                e.g. ``"Raoul Grosbedon <r.g@grosbedon.fr>"``"""
        assert email, 'an email is required for find_or_create to work'
        emails = tools.email_split(email)
        if emails:
            email = emails[0]
        partners = self.search([('email', '=ilike', email)], limit=1)
        return partners.id or self.name_create(email)[0]

    def _get_gravatar_image(self, email):
        gravatar_image = False
        email_hash = hashlib.md5(email.lower()).hexdigest()
        url = "https://www.gravatar.com/avatar/" + email_hash
        try:
            image_content = urllib2.urlopen(url + "?d=404&s=128", timeout=5).read()
            gravatar_image = base64.b64encode(image_content)
        except Exception:
            pass
        return gravatar_image

    @api.multi
    def _email_send(self, email_from, subject, body, on_error=None):
        for partner in self.filtered('email'):
            tools.email_send(email_from, [partner.email], subject, body, on_error)
        return True

    @api.multi
    def address_get(self, adr_pref=None):
        """ Find contacts/addresses of the right type(s) by doing a depth-first-search
        through descendants within company boundaries (stop at entities flagged ``is_company``)
        then continuing the search at the ancestors that are within the same company boundaries.
        Defaults to partners of type ``'default'`` when the exact type is not found, or to the
        provided partner itself if no type ``'default'`` is found either. """
        adr_pref = set(adr_pref or [])
        if 'contact' not in adr_pref:
            adr_pref.add('contact')
        result = {}
        visited = set()
        for partner in self:
            current_partner = partner
            while current_partner:
                to_scan = [current_partner]
                # Scan descendants, DFS
                while to_scan:
                    record = to_scan.pop(0)
                    visited.add(record)
                    if record.type in adr_pref and not result.get(record.type):
                        result[record.type] = record.id
                    if len(result) == len(adr_pref):
                        return result
                    to_scan = [c for c in record.child_ids
                                 if c not in visited
                                 if not c.is_company] + to_scan

                # Continue scanning at ancestor if current_partner is not a commercial entity
                if current_partner.is_company or not current_partner.parent_id:
                    break
                current_partner = current_partner.parent_id

        # default to type 'contact' or the partner itself
        default = result.get('contact', self.id or False)
        for adr_type in adr_pref:
            result[adr_type] = result.get(adr_type) or default
        return result

    @api.model
    def view_header_get(self, view_id, view_type):
        res = super(Partner, self).view_header_get(view_id, view_type)
        if res: return res
        if not self._context.get('category_id'):
            return False
        return _('Partners: ') + self.env['res.partner.category'].browse(self._context['category_id']).name

    @api.model
    @api.returns('self')
    def main_partner(self):
        ''' Return the main partner '''
        return self.env.ref('base.main_partner')

    @api.v7
    def _display_address(self, cr, uid, address, without_company=False, context=None):
        return self.browse(cr, uid, address.id, context=context)._display_address(without_company=without_company)

    @api.v8
    def _display_address(self, without_company=False):

        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.

        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format
        address_format = self.country_id.address_format or \
              "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"
        args = {
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self.country_id.name or '',
            'company_name': self.parent_name or '',
        }
        for field in self._address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.parent_id:
            address_format = '%(company_name)s\n' + address_format
        return address_format % args

    def _display_address_depends(self):
        # field dependencies of method _display_address()
        return self._address_fields() + [
            'country_id.address_format', 'country_id.code', 'country_id.name',
            'parent_id.name', 'state_id.code', 'state_id.name',
        ]
