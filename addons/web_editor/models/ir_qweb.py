# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Web_editor-context rendering needs to add some metadata to rendered and allow to edit fields,
as well as render a few fields differently.

Also, adds methods to convert values back to Odoo models.
"""

import ast
import cStringIO
import itertools
import json
import logging
import os
import urllib2
import urlparse
import re
import hashlib

import pytz
from dateutil import parser
from lxml import etree, html
from PIL import Image as I
import odoo.modules

from odoo import api, models, fields
from odoo.tools import ustr
from odoo.tools import html_escape as escape
from odoo.addons.base.ir import ir_qweb

REMOTE_CONNECTION_TIMEOUT = 2.5

logger = logging.getLogger(__name__)


class QWeb(models.AbstractModel):
    """ QWeb object for rendering editor stuff
    """
    _inherit = 'ir.qweb'

    # compile directives

    def _compile_directive_snippet(self, el, options):
        el.set('t-call', el.attrib.pop('t-snippet'))
        name = self.env['ir.ui.view'].search([('key', '=', el.attrib.get('t-call'))]).display_name
        thumbnail = el.attrib.pop('t-thumbnail', "oe-thumbnail")
        div = u'<div name="%s" data-oe-type="snippet" data-oe-thumbnail="%s">' % (escape(ir_qweb.unicodifier(name)), escape(ir_qweb.unicodifier(thumbnail)))
        return [self._append(ast.Str(div))] + self._compile_node(el, options) + [self._append(ast.Str(u'</div>'))]

    def _compile_directive_tag(self, el, options):
        if el.get('t-placeholder'):
            el.set('t-att-placeholder', el.attrib.pop('t-placeholder'))
        return super(QWeb, self)._compile_directive_tag(el, options)

    # order and ignore

    def _directives_eval_order(self):
        directives = super(QWeb, self)._directives_eval_order()
        directives.insert(directives.index('call'), 'snippet')
        return directives


#------------------------------------------------------
# QWeb fields
#------------------------------------------------------


class Field(models.AbstractModel):
    _name = 'ir.qweb.field'
    _inherit = 'ir.qweb.field'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(Field, self).attributes(record, field_name, options, values)
        field = record._fields[field_name]

        placeholder = options.get('placeholder') or getattr(field, 'placeholder', None)
        if placeholder:
            attrs['placeholder'] = placeholder

        if options['translate'] and field.type in ('char', 'text'):
            name = "%s,%s" % (record._name, field_name)
            domain = [('name', '=', name), ('res_id', '=', record.id), ('type', '=', 'model'), ('lang', '=', options.get('lang'))]
            translation = record.env['ir.translation'].search(domain, limit=1)
            attrs['data-oe-translation-state'] = translation and translation.state or 'to_translate'

        return attrs

    def value_from_string(self, value):
        return value

    @api.model
    def from_html(self, model, field, element):
        return self.value_from_string(element.text_content().strip())


class Integer(models.AbstractModel):
    _name = 'ir.qweb.field.integer'
    _inherit = 'ir.qweb.field.integer'

    value_from_string = int


class Float(models.AbstractModel):
    _name = 'ir.qweb.field.float'
    _inherit = 'ir.qweb.field.float'

    @api.model
    def from_html(self, model, field, element):
        lang = self.user_lang()
        value = element.text_content().strip()
        return float(value.replace(lang.thousands_sep, '')
                          .replace(lang.decimal_point, '.'))


class ManyToOne(models.AbstractModel):
    _name = 'ir.qweb.field.many2one'
    _inherit = 'ir.qweb.field.many2one'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(ManyToOne, self).attributes(record, field_name, options, values)
        many2one = getattr(record, field_name)
        if many2one:
            attrs['data-oe-many2one-id'] = many2one.id
            attrs['data-oe-many2one-model'] = many2one._name
        return attrs

    @api.model
    def from_html(self, model, field, element):
        Model = self.env[element.get('data-oe-model')]
        id = int(element.get('data-oe-id'))
        M2O = self.env[field.comodel_name]
        field_name = element.get('data-oe-field')
        many2one_id = int(element.get('data-oe-many2one-id'))
        record = many2one_id and M2O.browse(many2one_id)
        if record and record.exists():
            # save the new id of the many2one
            Model.browse(id).write({field_name: many2one_id})

        # not necessary, but might as well be explicit about it
        return None


class Contact(models.AbstractModel):
    _name = 'ir.qweb.field.contact'
    _inherit = 'ir.qweb.field.contact'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(Contact, self).attributes(record, field_name, options, values)
        attrs['data-oe-contact-options'] = json.dumps(options)
        return attrs

    # helper to call the rendering of contact field
    @api.model
    def get_record_to_html(self, ids, options=None):
        node = self.record_to_html(
            self.env['res.partner'].browse(ids[0]),
            'self',
            options=options,
        )
        return node


class Date(models.AbstractModel):
    _name = 'ir.qweb.field.date'
    _inherit = 'ir.qweb.field.date'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(Date, self).attributes(record, field_name, options, values)
        attrs['data-oe-original'] = record[field_name]
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        if not value:
            return False

        return value


class DateTime(models.AbstractModel):
    _name = 'ir.qweb.field.datetime'
    _inherit = 'ir.qweb.field.datetime'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(DateTime, self).attributes(record, field_name, options, values)
        value = record[field_name]
        if isinstance(value, basestring):
            value = fields.Datetime.from_string(value)
        if value:
            # convert from UTC (server timezone) to user timezone
            value = fields.Datetime.context_timestamp(self, timestamp=value)
            value = fields.Datetime.to_string(value)
        attrs['data-oe-original'] = value
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        if not value:
            return False

        # parse from string to datetime
        dt = parser.parse(value)

        # convert back from user's timezone to UTC
        tz_name = self.env.context.get('tz') or self.env.user.tz
        if tz_name:
            try:
                user_tz = pytz.timezone(tz_name)
                utc = pytz.utc

                dt = user_tz.localize(dt).astimezone(utc)
            except Exception:
                logger.warn(
                    "Failed to convert the value for a field of the model"
                    " %s back from the user's timezone (%s) to UTC",
                    model, tz_name,
                    exc_info=True)

        # format back to string
        return fields.Datetime.to_string(dt)


class Text(models.AbstractModel):
    _name = 'ir.qweb.field.text'
    _inherit = 'ir.qweb.field.text'

    @api.model
    def from_html(self, model, field, element):
        return html_to_text(element)


class Selection(models.AbstractModel):
    _name = 'ir.qweb.field.selection'
    _inherit = 'ir.qweb.field.selection'

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        selection = field.get_description(self.env)['selection']
        for k, v in selection:
            if isinstance(v, str):
                v = ustr(v)
            if value == v:
                return k

        raise ValueError(u"No value found for label %s in selection %s" % (
                         value, selection))


class HTML(models.AbstractModel):
    _name = 'ir.qweb.field.html'
    _inherit = 'ir.qweb.field.html'

    @api.model
    def from_html(self, model, field, element):
        content = []
        if element.text:
            content.append(element.text)
        content.extend(html.tostring(child)
                       for child in element.iterchildren(tag=etree.Element))
        return '\n'.join(content)


class Image(models.AbstractModel):
    """
    Widget options:

    ``class``
        set as attribute on the generated <img> tag
    """
    _name = 'ir.qweb.field.image'
    _inherit = 'ir.qweb.field.image'

    @api.model
    def record_to_html(self, record, field_name, options):
        assert options['tagName'] != 'img',\
            "Oddly enough, the root tag of an image field can not be img. " \
            "That is because the image goes into the tag, or it gets the " \
            "hose again."

        aclasses = ['img', 'img-responsive'] + options.get('class', '').split()
        classes = ' '.join(itertools.imap(escape, aclasses))

        max_size = None
        if options.get('resize'):
            max_size = options.get('resize')
        else:
            max_width, max_height = options.get('max_width', 0), options.get('max_height', 0)
            if max_width or max_height:
                max_size = '%sx%s' % (max_width, max_height)

        sha = hashlib.sha1(getattr(record, '__last_update')).hexdigest()[0:7]
        max_size = '' if max_size is None else '/%s' % max_size
        src = '/web/image/%s/%s/%s%s?unique=%s' % (record._name, record.id, field_name, max_size, sha)

        alt = None
        if options.get('alt-field') and getattr(record, options['alt-field'], None):
            alt = escape(record[options['alt-field']])
        elif options.get('alt'):
            alt = options['alt']

        img = '<img class="%s" src="%s" style="%s"%s/>' % \
            (classes, src, options.get('style', ''), ' alt="%s"' % alt if alt else '')
        return ir_qweb.unicodifier(img)

    local_url_re = re.compile(r'^/(?P<module>[^]]+)/static/(?P<rest>.+)$')

    @api.model
    def from_html(self, model, field, element):
        url = element.find('img').get('src')

        url_object = urlparse.urlsplit(url)
        if url_object.path.startswith('/web/image'):
            # url might be /web/image/<model>/<id>[_<checksum>]/<field>[/<width>x<height>]
            fragments = url_object.path.split('/')
            query = dict(urlparse.parse_qsl(url_object.query))
            if fragments[3].isdigit():
                model = 'ir.attachment'
                oid = fragments[3]
                field = 'datas'
            else:
                model = query.get('model', fragments[3])
                oid = query.get('id', fragments[4].split('_')[0])
                field = query.get('field', fragments[5])
            item = self.env[model].browse(int(oid))
            return item[field]

        if self.local_url_re.match(url_object.path):
            return self.load_local_url(url)

        return self.load_remote_url(url)

    def load_local_url(self, url):
        match = self.local_url_re.match(urlparse.urlsplit(url).path)

        rest = match.group('rest')
        for sep in os.sep, os.altsep:
            if sep and sep != '/':
                rest.replace(sep, '/')

        path = odoo.modules.get_module_resource(
            match.group('module'), 'static', *(rest.split('/')))

        if not path:
            return None

        try:
            with open(path, 'rb') as f:
                # force complete image load to ensure it's valid image data
                image = I.open(f)
                image.load()
                f.seek(0)
                return f.read().encode('base64')
        except Exception:
            logger.exception("Failed to load local image %r", url)
            return None

    def load_remote_url(self, url):
        try:
            # should probably remove remote URLs entirely:
            # * in fields, downloading them without blowing up the server is a
            #   challenge
            # * in views, may trigger mixed content warnings if HTTPS CMS
            #   linking to HTTP images
            # implement drag & drop image upload to mitigate?

            req = urllib2.urlopen(url, timeout=REMOTE_CONNECTION_TIMEOUT)
            # PIL needs a seekable file-like image, urllib result is not seekable
            image = I.open(cStringIO.StringIO(req.read()))
            # force a complete load of the image data to validate it
            image.load()
        except Exception:
            logger.exception("Failed to load remote image %r", url)
            return None

        # don't use original data in case weird stuff was smuggled in, with
        # luck PIL will remove some of it?
        out = cStringIO.StringIO()
        image.save(out, image.format)
        return out.getvalue().encode('base64')


class Monetary(models.AbstractModel):
    _name = 'ir.qweb.field.monetary'
    _inherit = 'ir.qweb.field.monetary'

    @api.model
    def from_html(self, model, field, element):
        lang = self.user_lang()

        value = element.find('span').text.strip()

        return float(value.replace(lang.thousands_sep, '')
                          .replace(lang.decimal_point, '.'))


class Duration(models.AbstractModel):
    _name = 'ir.qweb.field.duration'
    _inherit = 'ir.qweb.field.duration'

    @api.model
    def attributes(self, record, field_name, options, values):
        attrs = super(Duration, self).attributes(record, field_name, options, values)
        attrs['data-oe-original'] = record[field_name]
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()

        # non-localized value
        return float(value)


class RelativeDatetime(models.AbstractModel):
    _name = 'ir.qweb.field.relative'
    _inherit = 'ir.qweb.field.relative'

    # get formatting from ir.qweb.field.relative but edition/save from datetime


class QwebView(models.AbstractModel):
    _name = 'ir.qweb.field.qweb'
    _inherit = 'ir.qweb.field.qweb'


def html_to_text(element):
    """ Converts HTML content with HTML-specified line breaks (br, p, div, ...)
    in roughly equivalent textual content.

    Used to replace and fixup the roundtripping of text and m2o: when using
    libxml 2.8.0 (but not 2.9.1) and parsing HTML with lxml.html.fromstring
    whitespace text nodes (text nodes composed *solely* of whitespace) are
    stripped out with no recourse, and fundamentally relying on newlines
    being in the text (e.g. inserted during user edition) is probably poor form
    anyway.

    -> this utility function collapses whitespace sequences and replaces
       nodes by roughly corresponding linebreaks
       * p are pre-and post-fixed by 2 newlines
       * br are replaced by a single newline
       * block-level elements not already mentioned are pre- and post-fixed by
         a single newline

    ought be somewhat similar (but much less high-tech) to aaronsw's html2text.
    the latter produces full-blown markdown, our text -> html converter only
    replaces newlines by <br> elements at this point so we're reverting that,
    and a few more newline-ish elements in case the user tried to add
    newlines/paragraphs into the text field

    :param element: lxml.html content
    :returns: corresponding pure-text output
    """

    # output is a list of str | int. Integers are padding requests (in minimum
    # number of newlines). When multiple padding requests, fold them into the
    # biggest one
    output = []
    _wrap(element, output)

    # remove any leading or tailing whitespace, replace sequences of
    # (whitespace)\n(whitespace) by a single newline, where (whitespace) is a
    # non-newline whitespace in this case
    return re.sub(
        r'[ \t\r\f]*\n[ \t\r\f]*',
        '\n',
        ''.join(_realize_padding(output)).strip())

_PADDED_BLOCK = set('p h1 h2 h3 h4 h5 h6'.split())
# https://developer.mozilla.org/en-US/docs/HTML/Block-level_elements minus p
_MISC_BLOCK = set((
    'address article aside audio blockquote canvas dd dl div figcaption figure'
    ' footer form header hgroup hr ol output pre section tfoot ul video'
).split())


def _collapse_whitespace(text):
    """ Collapses sequences of whitespace characters in ``text`` to a single
    space
    """
    return re.sub('\s+', ' ', text)


def _realize_padding(it):
    """ Fold and convert padding requests: integers in the output sequence are
    requests for at least n newlines of padding. Runs thereof can be collapsed
    into the largest requests and converted to newlines.
    """
    padding = None
    for item in it:
        if isinstance(item, int):
            padding = max(padding, item)
            continue

        if padding:
            yield '\n' * padding
            padding = None

        yield item
    # leftover padding irrelevant as the output will be stripped


def _wrap(element, output, wrapper=u''):
    """ Recursively extracts text from ``element`` (via _element_to_text), and
    wraps it all in ``wrapper``. Extracted text is added to ``output``

    :type wrapper: basestring | int
    """
    output.append(wrapper)
    if element.text:
        output.append(_collapse_whitespace(element.text))
    for child in element:
        _element_to_text(child, output)
    output.append(wrapper)


def _element_to_text(e, output):
    if e.tag == 'br':
        output.append(u'\n')
    elif e.tag in _PADDED_BLOCK:
        _wrap(e, output, 2)
    elif e.tag in _MISC_BLOCK:
        _wrap(e, output, 1)
    else:
        # inline
        _wrap(e, output)

    if e.tail:
        output.append(_collapse_whitespace(e.tail))
