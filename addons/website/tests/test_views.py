# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

import unittest
from lxml import etree as ET, html
from lxml.html import builder as h

from odoo.tests import common, HttpCase


def attrs(**kwargs):
    return {'data-oe-%s' % key: str(value) for key, value in kwargs.items()}


class TestViewSaving(common.TransactionCase):

    def eq(self, a, b):
        self.assertEqual(a.tag, b.tag)
        self.assertEqual(a.attrib, b.attrib)
        self.assertEqual((a.text or '').strip(), (b.text or '').strip())
        self.assertEqual((a.tail or '').strip(), (b.tail or '').strip())
        for ca, cb in zip_longest(a, b):
            self.eq(ca, cb)

    def setUp(self):
        super(TestViewSaving, self).setUp()
        self.arch = h.DIV(
            h.DIV(
                h.H3("Column 1"),
                h.UL(
                    h.LI("Item 1"),
                    h.LI("Item 2"),
                    h.LI("Item 3"))),
            h.DIV(
                h.H3("Column 2"),
                h.UL(
                    h.LI("Item 1"),
                    h.LI(h.SPAN("My Company", attrs(model='res.company', id=1, field='name', type='char'))),
                    h.LI(h.SPAN("+00 00 000 00 0 000", attrs(model='res.company', id=1, field='phone', type='char')))
                ))
        )
        self.view_id = self.env['ir.ui.view'].create({
            'name': "Test View",
            'type': 'qweb',
            'arch': ET.tostring(self.arch, encoding='unicode')
        })

    def test_embedded_extraction(self):
        fields = self.env['ir.ui.view'].extract_embedded_fields(self.arch)

        expect = [
            h.SPAN("My Company", attrs(model='res.company', id=1, field='name', type='char')),
            h.SPAN("+00 00 000 00 0 000", attrs(model='res.company', id=1, field='phone', type='char')),
        ]
        for actual, expected in zip_longest(fields, expect):
            self.eq(actual, expected)

    def test_embedded_save(self):
        embedded = h.SPAN("+00 00 000 00 0 000", attrs(
            model='res.company', id=1, field='phone', type='char'))

        self.env['ir.ui.view'].save_embedded_field(embedded)

        company = self.env['res.company'].browse(1)
        self.assertEqual(company.phone, "+00 00 000 00 0 000")

    @unittest.skip("save conflict for embedded (saved by third party or previous version in page) not implemented")
    def test_embedded_conflict(self):
        e1 = h.SPAN("My Company", attrs(model='res.company', id=1, field='name'))
        e2 = h.SPAN("Leeroy Jenkins", attrs(model='res.company', id=1, field='name'))

        View = self.env['ir.ui.view']

        View.save_embedded_field(e1)
        # FIXME: more precise exception
        with self.assertRaises(Exception):
            View.save_embedded_field(e2)

    def test_embedded_to_field_ref(self):
        View = self.env['ir.ui.view']
        embedded = h.SPAN("My Company", attrs(expression="bob"))
        self.eq(
            View.to_field_ref(embedded),
            h.SPAN({'t-field': 'bob'})
        )

    def test_to_field_ref_keep_attributes(self):
        View = self.env['ir.ui.view']

        att = attrs(expression="bob", model="res.company", id=1, field="name")
        att['id'] = "whop"
        att['class'] = "foo bar"
        embedded = h.SPAN("My Company", att)

        self.eq(View.to_field_ref(embedded), h.SPAN({'t-field': 'bob', 'class': 'foo bar', 'id': 'whop'}))

    def test_replace_arch(self):
        replacement = h.P("Wheee")

        result = self.view_id.replace_arch_section(None, replacement)

        self.eq(result, h.DIV("Wheee"))

    def test_replace_arch_2(self):
        replacement = h.DIV(h.P("Wheee"))

        result = self.view_id.replace_arch_section(None, replacement)

        self.eq(result, replacement)

    def test_fixup_arch(self):
        replacement = h.H1("I am the greatest title alive!")

        result = self.view_id.replace_arch_section('/div/div[1]/h3', replacement)

        self.eq(result, h.DIV(
            h.DIV(
                h.H3("I am the greatest title alive!"),
                h.UL(
                    h.LI("Item 1"),
                    h.LI("Item 2"),
                    h.LI("Item 3"))),
            h.DIV(
                h.H3("Column 2"),
                h.UL(
                    h.LI("Item 1"),
                    h.LI(h.SPAN("My Company", attrs(model='res.company', id=1, field='name', type='char'))),
                    h.LI(h.SPAN("+00 00 000 00 0 000", attrs(model='res.company', id=1, field='phone', type='char')))
                ))
        ))

    def test_multiple_xpath_matches(self):
        with self.assertRaises(ValueError):
            self.view_id.replace_arch_section('/div/div/h3', h.H6("Lol nope"))

    def test_save(self):
        Company = self.env['res.company']

        # create an xmlid for the view
        imd = self.env['ir.model.data'].create({
            'module': 'website',
            'name': 'test_view',
            'model': self.view_id._name,
            'res_id': self.view_id.id,
        })
        self.assertEqual(self.view_id.model_data_id, imd)
        self.assertFalse(imd.noupdate)

        replacement = ET.tostring(h.DIV(
            h.H3("Column 2"),
            h.UL(
                h.LI("wob wob wob"),
                h.LI(h.SPAN("Acme Corporation", attrs(model='res.company', id=1, field='name', expression="bob", type='char'))),
                h.LI(h.SPAN("+12 3456789", attrs(model='res.company', id=1, field='phone', expression="edmund", type='char'))),
            )
        ), encoding='unicode')
        self.view_id.save(value=replacement, xpath='/div/div[2]')

        # the xml_id of the view should be flagged as 'noupdate'
        self.assertTrue(imd.noupdate)

        company = Company.browse(1)
        self.assertEqual(company.name, "Acme Corporation")
        self.assertEqual(company.phone, "+12 3456789")
        self.eq(
            ET.fromstring(self.view_id.arch),
            h.DIV(
                h.DIV(
                    h.H3("Column 1"),
                    h.UL(
                        h.LI("Item 1"),
                        h.LI("Item 2"),
                        h.LI("Item 3"))),
                h.DIV(
                    h.H3("Column 2"),
                    h.UL(
                        h.LI("wob wob wob"),
                        h.LI(h.SPAN({'t-field': "bob"})),
                        h.LI(h.SPAN({'t-field': "edmund"}))
                    ))
            )
        )

    def test_save_escaped_text(self):
        """ Test saving html special chars in text nodes """
        view = self.env['ir.ui.view'].create({
            'arch': u'<t t-name="dummy"><p><h1>hello world</h1></p></t>',
            'type': 'qweb'
        })
        # script and style text nodes should not escaped client side
        replacement = u'<script>1 && "hello & world"</script>'
        view.save(replacement, xpath='/t/p/h1')
        self.assertIn(
            replacement.replace(u'&', u'&amp;'),
            view.arch,
            'inline script should be escaped server side'
        )
        self.assertIn(
            replacement,
            view.render().decode('utf-8'),
            'inline script should not be escaped when rendering'
        )
        # common text nodes should be be escaped client side
        replacement = u'world &amp;amp; &amp;lt;b&amp;gt;cie'
        view.save(replacement, xpath='/t/p')
        self.assertIn(replacement, view.arch, 'common text node should not be escaped server side')
        self.assertIn(
            replacement,
            view.render().decode('utf-8').replace(u'&', u'&amp;'),
            'text node characters wrongly unescaped when rendering'
        )

    def test_save_only_embedded(self):
        Company = self.env['res.company']
        company_id = 1
        company = Company.browse(company_id)
        company.write({'name': "Foo Corporation"})

        node = html.tostring(h.SPAN(
            "Acme Corporation",
            attrs(model='res.company', id=company_id, field="name", expression='bob', type='char')),
            encoding='unicode')
        View = self.env['ir.ui.view']
        View.browse(company_id).save(value=node)
        self.assertEqual(company.name, "Acme Corporation")

    def test_field_tail(self):
        replacement = ET.tostring(
            h.LI(h.SPAN("+12 3456789", attrs(
                        model='res.company', id=1, type='char',
                        field='phone', expression="edmund")),
                 "whop whop"
                 ), encoding="utf-8")
        self.view_id.save(value=replacement, xpath='/div/div[2]/ul/li[3]')

        self.eq(
            ET.fromstring(self.view_id.arch.encode('utf-8')),
            h.DIV(
                h.DIV(
                    h.H3("Column 1"),
                    h.UL(
                        h.LI("Item 1"),
                        h.LI("Item 2"),
                        h.LI("Item 3"))),
                h.DIV(
                    h.H3("Column 2"),
                    h.UL(
                        h.LI("Item 1"),
                        h.LI(h.SPAN("My Company", attrs(model='res.company', id=1, field='name', type='char'))),
                        h.LI(h.SPAN({'t-field': "edmund"}), "whop whop"),
                    ))
            )
        )


class TestCowViewSaving(common.TransactionCase):
    def setUp(self):
        super(TestCowViewSaving, self).setUp()
        View = self.env['ir.ui.view']

        self.base_view = View.create({
            'name': 'Base',
            'type': 'qweb',
            'arch': '<div>base content</div>',
            'key': 'website.base_view',
        }).with_context(load_all_views=True)

        self.inherit_view = View.create({
            'name': 'Extension',
            'mode': 'extension',
            'inherit_id': self.base_view.id,
            'arch': '<div position="inside">, extended content</div>',
            'key': 'website.extension_view',
        })

    def test_cow_on_base_after_extension(self):
        View = self.env['ir.ui.view']
        self.inherit_view.with_context(website_id=1).write({'name': 'Extension Specific'})
        v1 = self.base_view
        v2 = self.inherit_view
        v3 = View.search([('website_id', '=', 1), ('name', '=', 'Extension Specific')])
        v4 = self.inherit_view.copy({'name': 'Second Extension'})
        v5 = self.inherit_view.copy({'name': 'Third Extension (Specific)'})
        v5.write({'website_id': 1})

        # id | name                        | website_id | inherit  | key
        # ------------------------------------------------------------------------
        # 1  | Base                        |     /      |     /    |  website.base_view
        # 2  | Extension                   |     /      |     1    |  website.extension_view
        # 3  | Extension Specific          |     1      |     1    |  website.extension_view
        # 4  | Second Extension            |     /      |     1    |  website.extension_view_a5f579d5 (generated hash)
        # 5  | Third Extension (Specific)  |     1      |     1    |  website.extension_view_5gr87e6c (another generated hash)

        self.assertEqual(v2.key == v3.key, True, "Making specific a generic inherited view should copy it's key (just change the website_id)")
        self.assertEqual(v3.key != v4.key != v5.key, True, "Copying a view should generate a new key for the new view (not the case when triggering COW)")
        self.assertEqual('website.extension_view' in v3.key and 'website.extension_view' in v4.key and 'website.extension_view' in v5.key, True, "The copied views should have the key from the view it was copied from but with an unique suffix")

        total_views = View.search_count([])
        v1.with_context(website_id=1).write({'name': 'Base Specific'})

        # id | name                        | website_id | inherit  | key
        # ------------------------------------------------------------------------
        # 1  | Base                        |     /      |     /    |  website.base_view
        # 2  | Extension                   |     /      |     1    |  website.extension_view
        # 3 - DELETED
        # 4  | Second Extension            |     /      |     1    |  website.extension_view_a5f579d5
        # 5 - DELETED
        # 6  | Base Specific               |     1      |     /    |  website.base_view
        # 7  | Extension Specific          |     1      |     6    |  website.extension_view
        # 8  | Second Extension            |     1      |     6    |  website.extension_view_a5f579d5
        # 9  | Third Extension (Specific)  |     1      |     6    |  website.extension_view_5gr87e6c

        v6 = View.search([('website_id', '=', 1), ('name', '=', 'Base Specific')])
        v7 = View.search([('website_id', '=', 1), ('name', '=', 'Extension Specific')])
        v8 = View.search([('website_id', '=', 1), ('name', '=', 'Second Extension')])
        v9 = View.search([('website_id', '=', 1), ('name', '=', 'Third Extension (Specific)')])

        self.assertEqual(total_views + 4 - 2, View.search_count([]), "It should have duplicated the view tree with a website_id, taking only most specific (only specific `b` key), and removing website_specific from generic tree")
        self.assertEqual(len((v3 + v5).exists()), 0, "v3 and v5 should have been deleted as they were already specific and copied to the new specific base")
        # Check generic tree
        self.assertEqual((v1 + v2 + v4).mapped('website_id').ids, [])
        self.assertEqual((v2 + v4).mapped('inherit_id'), v1)
        # Check specific tree
        self.assertEqual((v6 + v7 + v8 + v9).mapped('website_id').ids, [1])
        self.assertEqual((v7 + v8 + v9).mapped('inherit_id'), v6)
        # Check key
        self.assertEqual(v6.key == v1.key, True)
        self.assertEqual(v7.key == v2.key, True)
        self.assertEqual(v4.key == v8.key, True)
        self.assertEqual(View.search_count([('key', '=', v9.key)]), 1)

    def test_cow_leaf(self):
        View = self.env['ir.ui.view']

        # edit on backend, regular write
        self.inherit_view.write({'arch': '<div position="replace"><div>modified content</div></div>'})
        self.assertEqual(View.search_count([('key', '=', 'website.base_view')]), 1)
        self.assertEqual(View.search_count([('key', '=', 'website.extension_view')]), 1)

        arch = self.base_view.read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>modified content</div>')

        # edit on frontend, copy just the leaf
        self.inherit_view.with_context(website_id=1).write({'arch': '<div position="replace"><div>website 1 content</div></div>'})
        inherit_views = View.search([('key', '=', 'website.extension_view')])
        self.assertEqual(View.search_count([('key', '=', 'website.base_view')]), 1)
        self.assertEqual(len(inherit_views), 2)
        self.assertEqual(len(inherit_views.filtered(lambda v: v.website_id.id == 1)), 1)

        # read in backend should be unaffected
        arch = self.base_view.read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>modified content</div>')
        # read on website should reflect change
        arch = self.base_view.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>website 1 content</div>')

        # website-specific inactive view should take preference over active generic one when viewing the website
        # this is necessary to make customize_show=True templates work correctly
        inherit_views.filtered(lambda v: v.website_id.id == 1).write({'active': False})
        arch = self.base_view.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>base content</div>')

    def test_cow_root(self):
        View = self.env['ir.ui.view']

        # edit on backend, regular write
        self.base_view.write({'arch': '<div>modified base content</div>'})
        self.assertEqual(View.search_count([('key', '=', 'website.base_view')]), 1)
        self.assertEqual(View.search_count([('key', '=', 'website.extension_view')]), 1)

        # edit on frontend, copy the entire tree
        self.base_view.with_context(website_id=1).write({'arch': '<div>website 1 content</div>'})

        generic_base_view = View.search([('key', '=', 'website.base_view'), ('website_id', '=', False)])
        website_specific_base_view = View.search([('key', '=', 'website.base_view'), ('website_id', '=', 1)])
        self.assertEqual(len(generic_base_view), 1)
        self.assertEqual(len(website_specific_base_view), 1)

        inherit_views = View.search([('key', '=', 'website.extension_view')])
        self.assertEqual(len(inherit_views), 2)
        self.assertEqual(len(inherit_views.filtered(lambda v: v.website_id.id == 1)), 1)

        arch = generic_base_view.with_context(load_all_views=True).read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>modified base content, extended content</div>')

        arch = website_specific_base_view.with_context(load_all_views=True, website_id=1).read_combined(['arch'])['arch']
        self.assertEqual(arch, '<div>website 1 content, extended content</div>')

    # # As there is a new SQL constraint that prevent QWeb views to have an empty `key`, this test won't work
    # def test_cow_view_without_key(self):
    #     # Remove key for this test
    #     self.base_view.key = False
    #
    #     View = self.env['ir.ui.view']
    #
    #     # edit on backend, regular write
    #     self.base_view.write({'arch': '<div>modified base content</div>'})
    #     self.assertEqual(self.base_view.key, False, "Writing on a keyless view should not set a key on it if there is no website in context")
    #
    #     # edit on frontend, copy just the leaf
    #     self.base_view.with_context(website_id=1).write({'arch': '<div position="replace"><div>website 1 content</div></div>'})
    #     self.assertEqual('website.key_' in self.base_view.key, True, "Writing on a keyless view should set a key on it if there is a website in context")
    #     total_views_with_key = View.search_count([('key', '=', self.base_view.key)])
    #     self.assertEqual(total_views_with_key, 2, "It should have set the key on generic view then copy to specific view (with they key)")

    def test_cow_generic_view_with_already_existing_specific(self):
        """ Writing on a generic view should check if a website specific view already exists
            (The flow of this test will happen when editing a generic view in the front end and changing more than one element)
        """
        # 1. Test with calling write directly
        View = self.env['ir.ui.view']

        base_view = View.create({
            'name': 'Base',
            'type': 'qweb',
            'arch': '<div>content</div>',
        })

        total_views = View.with_context(active_test=False).search_count([])
        base_view.with_context(website_id=1).write({'name': 'New Name'})  # This will not write on `base_view` but will copy it to a specific view on which the `name` change will be applied
        specific_view = View.search([['name', '=', 'New Name'], ['website_id', '=', 1]])
        base_view.with_context(website_id=1).write({'name': 'Another New Name'})
        specific_view.active = False
        base_view.with_context(website_id=1).write({'name': 'Yet Another New Name'})
        self.assertEqual(total_views + 1, View.with_context(active_test=False).search_count([]), "Subsequent writes should have written on the view copied during first write")

        # 2. Test with calling save() from ir.ui.view
        view_arch = '''<t name="Second View" t-name="website.second_view">
                          <t t-call="website.layout">
                            <div id="wrap">
                              <div class="editable_part"/>
                              <div class="container">
                                  <h1>Second View</h1>
                              </div>
                              <div class="editable_part"/>
                            </div>
                          </t>
                       </t>'''
        second_view = View.create({
            'name': 'Base',
            'type': 'qweb',
            'arch': view_arch,
        })

        total_views = View.with_context(active_test=False).search_count([])
        second_view.with_context(website_id=1).save('<div class="editable_part" data-oe-id="%s" data-oe-xpath="/t[1]/t[1]/div[1]/div[1]" data-oe-field="arch" data-oe-model="ir.ui.view">First editable_part</div>' % second_view.id, "/t[1]/t[1]/div[1]/div[1]")
        second_view.with_context(website_id=1).save('<div class="editable_part" data-oe-id="%s" data-oe-xpath="/t[1]/t[1]/div[1]/div[3]" data-oe-field="arch" data-oe-model="ir.ui.view">Second editable_part</div>' % second_view.id, "/t[1]/t[1]/div[1]/div[3]")
        self.assertEqual(total_views + 1, View.with_context(active_test=False).search_count([]), "Second save should have written on the view copied during first save")

        total_specific_view = View.with_context(active_test=False).search_count([('arch_db', 'like', 'First editable_part'), ('arch_db', 'like', 'Second editable_part')])
        self.assertEqual(total_specific_view, 1, "both editable_part should have been replaced on a created specific view")

    def test_cow_complete_flow(self):
        View = self.env['ir.ui.view']
        total_views = View.search_count([])

        self.base_view.write({'arch': '<div>Hi</div>'})
        self.inherit_view.write({'arch': '<div position="inside"> World</div>'})

        # id | name      | content | website_id | inherit  | key
        # -------------------------------------------------------
        # 1  | Base      |  Hi     |     /      |     /    |  website.base_view
        # 2  | Extension |  World  |     /      |     1    |  website.extension_view

        arch = self.base_view.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual('Hi World' in arch, True)

        self.base_view.write({'arch': '<div>Hello</div>'})

        # id | name      | content | website_id | inherit  | key
        # -------------------------------------------------------
        # 1  | Base      |  Hello  |     /      |     /    |  website.base_view
        # 2  | Extension |  World  |     /      |     1    |  website.extension_view

        arch = self.base_view.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual('Hello World' in arch, True)

        self.base_view.with_context(website_id=1).write({'arch': '<div>Bye</div>'})

        # id | name      | content | website_id | inherit  | key
        # -------------------------------------------------------
        # 1  | Base      |  Hello  |     /      |     /    |  website.base_view
        # 3  | Base      |  Bye    |     1      |     /    |  website.base_view
        # 2  | Extension |  World  |     /      |     1    |  website.extension_view
        # 4  | Extension |  World  |     1      |     3    |  website.extension_view

        base_specific = View.search([('key', '=', self.base_view.key), ('website_id', '=', 1)]).with_context(load_all_views=True)
        extend_specific = View.search([('key', '=', self.inherit_view.key), ('website_id', '=', 1)])
        self.assertEqual(total_views + 2, View.search_count([]), "Should have copied Base & Extension with a website_id")
        self.assertEqual(self.base_view.key, base_specific.key)
        self.assertEqual(self.inherit_view.key, extend_specific.key)

        extend_specific.write({'arch': '<div position="inside"> All</div>'})

        # id | name      | content | website_id | inherit  | key
        # -------------------------------------------------------
        # 1  | Base      |  Hello  |     /      |     /    |  website.base_view
        # 3  | Base      |  Bye    |     1      |     /    |  website.base_view
        # 2  | Extension |  World  |     /      |     1    |  website.extension_view
        # 4  | Extension |  All    |     1      |     3    |  website.extension_view

        arch = base_specific.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual('Bye All' in arch, True)

        self.inherit_view.with_context(website_id=1).write({'arch': '<div position="inside"> Nobody</div>'})

        # id | name      | content | website_id | inherit  | key
        # -------------------------------------------------------
        # 1  | Base      |  Hello  |     /      |     /    |  website.base_view
        # 3  | Base      |  Bye    |     1      |     /    |  website.base_view
        # 2  | Extension |  World  |     /      |     1    |  website.extension_view
        # 4  | Extension |  Nobody |     1      |     3    |  website.extension_view

        arch = base_specific.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual('Bye Nobody' in arch, True, "Write on generic `inherit_view` should have been diverted to already existing specific view")

        base_arch = self.base_view.read_combined(['arch'])['arch']
        base_arch_w1 = self.base_view.with_context(website_id=1).read_combined(['arch'])['arch']
        self.assertEqual('Hello World' in base_arch, True)
        self.assertEqual(base_arch, base_arch_w1, "Reading a top level view with or without a website_id in the context should render that exact view..")  # ..even if there is a specific view for that one, as read_combined is supposed to render specific inherited view over generic but not specific top level instead of generic top level

    def test_cow_cross_inherit(self):
        View = self.env['ir.ui.view']
        total_views = View.search_count([])

        main_view = View.create({
            'name': 'Main View',
            'type': 'qweb',
            'arch': '<body>GENERIC<div>A</div></body>',
            'key': 'website.main_view',
        }).with_context(load_all_views=True)

        View.create({
            'name': 'Child View',
            'mode': 'extension',
            'inherit_id': main_view.id,
            'arch': '<xpath expr="//div" position="replace"><div>VIEW<p>B</p></div></xpath>',
            'key': 'website.child_view',
        })

        child_view_2 = View.with_context(load_all_views=True).create({
            'name': 'Child View 2',
            'mode': 'extension',
            'inherit_id': main_view.id,
            'arch': '<xpath expr="//p" position="replace"><span>C</span></xpath>',
            'key': 'website.child_view_2',
        })

        # These line doing `write()` are the real tests, it should not be changed and should not crash on xpath.
        child_view_2.with_context(website_id=1).write({'arch': '<xpath expr="//p" position="replace"><span>D</span></xpath>'})
        self.assertEqual(total_views + 3 + 1, View.search_count([]), "It should have created the 3 initial generic views and created a child_view_2 specific view")
        main_view.with_context(website_id=1).write({'arch': '<body>SPECIFIC<div>Z</div></body>'})
        self.assertEqual(total_views + 3 + 3, View.search_count([]), "It should have duplicated the Main View tree as a specific tree and then removed the specific view from the generic tree as no more needed")

        generic_view = View.with_context(website_id=None).get_view_id('website.main_view')
        specific_view = View.with_context(website_id=1).get_view_id('website.main_view')
        generic_view_arch = View.browse(generic_view).with_context(load_all_views=True).read_combined(['arch'])['arch']
        specific_view_arch = View.browse(specific_view).with_context(load_all_views=True, website_id=1).read_combined(['arch'])['arch']
        self.assertEqual(generic_view_arch, '<body>GENERIC<div>VIEW<span>C</span></div></body>')
        self.assertEqual(specific_view_arch, '<body>SPECIFIC<div>VIEW<span>D</span></div></body>', "Writing on top level view hierarchy with a website in context should write on the view and clone it's inherited views")

    def test_multi_website_view_obj_active(self):
        ''' With the following structure:
            * A generic active parent view
            * A generic active child view, that is inactive on website 1
            The methods to retrieve views should return the specific inactive
            child over the generic active one.
        '''
        View = self.env['ir.ui.view']
        self.inherit_view.with_context(website_id=1).write({'active': False})

        # Test _view_obj() return the inactive specific over active generic
        inherit_view = View._view_obj(self.inherit_view.key)
        self.assertEqual(inherit_view.active, True, "_view_obj should return the generic one")
        inherit_view = View.with_context(website_id=1)._view_obj(self.inherit_view.key)
        self.assertEqual(inherit_view.active, False, "_view_obj should return the specific one")

        # Test get_related_views() return the inactive specific over active generic
        # Note that we cannot test get_related_views without a website in context as it will fallback on a website with get_current_website()
        views = View.with_context(website_id=1).get_related_views(self.base_view.key)
        self.assertEqual(views.mapped('active'), [True, False], "get_related_views should return the specific child")

        # Test filter_duplicate() return the inactive specific over active generic
        view = View.with_context(active_test=False).search([('key', '=', self.inherit_view.key)]).filter_duplicate()
        self.assertEqual(view.active, True, "filter_duplicate should return the generic one")
        view = View.with_context(active_test=False, website_id=1).search([('key', '=', self.inherit_view.key)]).filter_duplicate()
        self.assertEqual(view.active, False, "filter_duplicate should return the specific one")

    def test_get_related_views_tree(self):
        View = self.env['ir.ui.view']

        self.base_view.write({'name': 'B', 'key': 'B'})
        self.inherit_view.write({'name': 'I', 'key': 'I'})
        View.create({
            'name': 'II',
            'mode': 'extension',
            'inherit_id': self.inherit_view.id,
            'arch': '<div position="inside">, sub ext</div>',
            'key': 'II',
        })
        self.inherit_view.with_context(website_id=1).write({'name': 'Extension'})  # Trigger cow on hierarchy
        View.create({
            'name': 'II2',
            'mode': 'extension',
            'inherit_id': self.inherit_view.id,
            'arch': '<div position="inside">, sub sibling specific</div>',
            'key': 'II2',
        })

        #       B
        #      / \
        #     /   \
        #    I     I'
        #   / \     |
        # II  II2   II'

        views = View.with_context(website_id=1).get_related_views('B')
        self.assertEqual(views.mapped('key'), ['B', 'I', 'II'], "Should only return the specific tree")

    def test_cow_inherit_children_order(self):
        """ COW method should loop on inherit_children_ids in correct order
            when copying them on the new specific tree.
            Correct order is the same as the one when applying view arch:
            PRIORITY, ID
            And not the default one from ir.ui.view (NAME, PRIORIRTY, ID).
        """
        self.inherit_view.copy({
            'name': 'alphabetically before "Extension"',
            'key': '_test.alphabetically_first',
            'arch': '<div position="replace"><p>COMPARE</p></div>',
        })
        # Next line should not crash, COW loop on inherit_children_ids should be sorted correctly
        self.base_view.with_context(website_id=1).write({'name': 'Product (W1)'})


class Crawler(HttpCase):
    def setUp(self):
        super(Crawler, self).setUp()
        View = self.env['ir.ui.view']

        self.base_view = View.create({
            'name': 'Base',
            'type': 'qweb',
            'arch': '<div>base content</div>',
            'key': 'website.base_view',
        }).with_context(load_all_views=True)

        self.inherit_view = View.create({
            'name': 'Extension',
            'mode': 'extension',
            'inherit_id': self.base_view.id,
            'arch': '<div position="inside">, extended content</div>',
            'key': 'website.extension_view',
        })

    def test_get_switchable_related_views(self):
        View = self.env['ir.ui.view']
        Website = self.env['website']

        # Set up
        website_1 = Website.create({'name': 'Website 1'})  # will have specific views
        website_2 = Website.create({'name': 'Website 2'})  # will use generic views

        self.base_view.write({'name': 'Main Frontend Layout', 'key': '_portal.frontend_layout'})
        event_main_view = self.base_view.copy({
            'name': 'Events',
            'key': '_website_event.index',
            'arch': '<t t-call="_website.layout"><div>Arch is not important in this test</div></t>',
        })
        self.inherit_view.write({'name': 'Main layout', 'key': '_website.layout'})

        self.inherit_view.copy({'name': 'Show Sign In', 'customize_show': True, 'key': '_portal.portal_show_sign_in'})
        view_logo = self.inherit_view.copy({
            'name': 'Show Logo',
            'inherit_id': self.inherit_view.id,
            'customize_show': True,
            'key': '_website.layout_logo_show',
        })
        view_logo.copy({'name': 'Affix Top Menu', 'key': '_website.affix_top_menu'})

        event_child_view = self.inherit_view.copy({
            'name': 'Filters',
            'customize_show': True,
            'inherit_id': event_main_view.id,
            'key': '_website_event.event_left_column',
            'priority': 30,
        })
        view_photos = event_child_view.copy({'name': 'Photos', 'key': '_website_event.event_right_photos'})
        event_child_view.copy({'name': 'Quotes', 'key': '_website_event.event_right_quotes', 'priority': 30})

        event_child_view.copy({'name': 'Filter by Category', 'inherit_id': event_child_view.id, 'key': '_website_event.event_category'})
        event_child_view.copy({'name': 'Filter by Country', 'inherit_id': event_child_view.id, 'key': '_website_event.event_location'})

        # Customize
        #   | Main Frontend Layout
        #       | Show Sign In
        #   | Main Layout
        #       | Affix Top Menu
        #       | Show Logo
        #   | Events
        #       | Filters
        #       | Photos
        #       | Quotes
        #   | Filters
        #       | Filter By Category
        #       | Filter By Country

        self.authenticate("admin", "admin")
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Simulate website 2 (that use only generic views)
        url = base_url + '/website/force_website'
        json = {'params': {'website_id': website_2.id}}
        self.opener.post(url=url, json=json)

        # Test controller
        url = base_url + '/website/get_switchable_related_views'
        json = {'params': {'key': '_website_event.index'}}
        response = self.opener.post(url=url, json=json)
        res = response.json()['result']

        self.assertEqual(
            [v['name'] for v in res],
            ['Show Sign In', 'Affix Top Menu', 'Show Logo', 'Filters', 'Photos', 'Quotes', 'Filter by Category', 'Filter by Country'],
            "Sequence should not be taken into account for customize menu",
        )
        self.assertEqual(
            [v['inherit_id'][1] for v in res],
            ['Main Frontend Layout', 'Main layout', 'Main layout', 'Events', 'Events', 'Events', 'Filters', 'Filters'],
            "Sequence should not be taken into account for customize menu (Checking Customize headers)",
        )

        # Trigger COW
        view_logo.with_context(website_id=website_1.id).write({'arch': '<div position="inside">, trigger COW, arch is not relevant in this test</div>'})
        # This would wrongly become:

        # Customize
        #   | Main Frontend Layout
        #       | Show Sign In
        #   | Main Layout
        #       | Affix Top Menu
        #       | Show Logo <==== Was above "Affix Top Menu"
        #   | Events
        #       | Filters
        #       | Photos
        #       | Quotes
        #   | Filters
        #       | Filter By Category
        #       | Filter By Country

        # Simulate website 1 (that has specific views)
        url = base_url + '/website/force_website'
        json = {'params': {'website_id': website_1.id}}
        self.opener.post(url=url, json=json)

        # Test controller
        url = base_url + '/website/get_switchable_related_views'
        json = {'params': {'key': '_website_event.index'}}
        response = self.opener.post(url=url, json=json)
        res = response.json()['result']
        self.assertEqual(
            [v['name'] for v in res],
            ['Show Sign In', 'Affix Top Menu', 'Show Logo', 'Filters', 'Photos', 'Quotes', 'Filter by Category', 'Filter by Country'],
            "multi-website COW should not impact customize views order (COW view will have a bigger ID and should not be last)",
        )
        self.assertEqual(
            [v['inherit_id'][1] for v in res],
            ['Main Frontend Layout', 'Main layout', 'Main layout', 'Events', 'Events', 'Events', 'Filters', 'Filters'],
            "multi-website COW should not impact customize views menu header position or split (COW view will have a bigger ID and should not be last)",
        )

        # Trigger COW
        view_photos.with_context(website_id=website_1.id).write({'arch': '<div position="inside">, trigger COW, arch is not relevant in this test</div>'})
        # This would wrongly become:

        # Customize
        #   | Main Frontend Layout
        #       | Show Sign In
        #   | Main Layout
        #       | Affix Top Menu
        #       | Show Logo
        #   | Events
        #       | Filters
        #       | Quotes
        #   | Filters
        #       | Filter By Category
        #       | Filter By Country
        #   | Events     <==== JS code creates a new Events header as the Event's children views are not one after the other anymore..
        #       | Photos <==== .. since Photos got duplicated and now have a bigger ID that others

        # Test controller
        url = base_url + '/website/get_switchable_related_views'
        json = {'params': {'key': '_website_event.index'}}
        response = self.opener.post(url=url, json=json)
        res = response.json()['result']
        self.assertEqual(
            [v['name'] for v in res],
            ['Show Sign In', 'Affix Top Menu', 'Show Logo', 'Filters', 'Photos', 'Quotes', 'Filter by Category', 'Filter by Country'],
            "multi-website COW should not impact customize views order (COW view will have a bigger ID and should not be last) (2)",
        )
        self.assertEqual(
            [v['inherit_id'][1] for v in res],
            ['Main Frontend Layout', 'Main layout', 'Main layout', 'Events', 'Events', 'Events', 'Filters', 'Filters'],
            "multi-website COW should not impact customize views menu header position or split (COW view will have a bigger ID and should not be last) (2)",
        )
