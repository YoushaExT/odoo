# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, SavepointCase
from odoo.tools import mute_logger


class TestXMLID(TransactionCase):
    def get_data(self, xml_id):
        """ Return the 'ir.model.data' record corresponding to ``xml_id``. """
        module, suffix = xml_id.split('.', 1)
        domain = [('module', '=', module), ('name', '=', suffix)]
        return self.env['ir.model.data'].search(domain)

    def test_create(self):
        model = self.env['res.partner.category']
        xml_id = 'test_convert.category_foo'

        # create category (flag 'noupdate' should be False by default)
        data = dict(xml_id=xml_id, values={'name': 'Foo'})
        category = model._load_records([data])
        self.assertEqual(category, self.env.ref(xml_id, raise_if_not_found=False))
        self.assertEqual(category.name, 'Foo')
        self.assertEqual(self.get_data(xml_id).noupdate, False)

        # update category
        data = dict(xml_id=xml_id, values={'name': 'Bar'})
        category1 = model._load_records([data], update=True)
        self.assertEqual(category, category1)
        self.assertEqual(category.name, 'Bar')
        self.assertEqual(self.get_data(xml_id).noupdate, False)

        # update category
        data = dict(xml_id=xml_id, values={'name': 'Baz'}, noupdate=True)
        category2 = model._load_records([data], update=True)
        self.assertEqual(category, category2)
        self.assertEqual(category.name, 'Baz')
        self.assertEqual(self.get_data(xml_id).noupdate, False)

    def test_create_noupdate(self):
        model = self.env['res.partner.category']
        xml_id = 'test_convert.category_foo'

        # create category
        data = dict(xml_id=xml_id, values={'name': 'Foo'}, noupdate=True)
        category = model._load_records([data])
        self.assertEqual(category, self.env.ref(xml_id, raise_if_not_found=False))
        self.assertEqual(category.name, 'Foo')
        self.assertEqual(self.get_data(xml_id).noupdate, True)

        # update category
        data = dict(xml_id=xml_id, values={'name': 'Bar'}, noupdate=False)
        category1 = model._load_records([data], update=True)
        self.assertEqual(category, category1)
        self.assertEqual(category.name, 'Foo')
        self.assertEqual(self.get_data(xml_id).noupdate, True)

        # update category
        data = dict(xml_id=xml_id, values={'name': 'Baz'}, noupdate=True)
        category2 = model._load_records([data], update=True)
        self.assertEqual(category, category2)
        self.assertEqual(category.name, 'Foo')
        self.assertEqual(self.get_data(xml_id).noupdate, True)

    def test_create_noupdate_multi(self):
        model = self.env['res.partner.category']
        data_list = [
            dict(xml_id='test_convert.category_foo', values={'name': 'Foo'}, noupdate=True),
            dict(xml_id='test_convert.category_bar', values={'name': 'Bar'}, noupdate=True),
        ]

        # create category
        categories = model._load_records(data_list)
        foo = self.env.ref('test_convert.category_foo')
        bar = self.env.ref('test_convert.category_bar')
        self.assertEqual(categories, foo + bar)
        self.assertEqual(foo.name, 'Foo')
        self.assertEqual(bar.name, 'Bar')

        # check data
        self.assertEqual(self.get_data('test_convert.category_foo').noupdate, True)
        self.assertEqual(self.get_data('test_convert.category_bar').noupdate, True)

    def test_create_order(self):
        model = self.env['res.partner.category']
        data_list = [
            dict(xml_id='test_convert.category_foo', values={'name': 'Foo'}),
            dict(xml_id='test_convert.category_bar', values={'name': 'Bar'}, noupdate=True),
            dict(xml_id='test_convert.category_baz', values={'name': 'Baz'}),
        ]

        # create categories
        foo = model._load_records([data_list[0]])
        bar = model._load_records([data_list[1]])
        baz = model._load_records([data_list[2]])
        self.assertEqual(foo.name, 'Foo')
        self.assertEqual(bar.name, 'Bar')
        self.assertEqual(baz.name, 'Baz')

        # update them, and check the order of result
        for data in data_list:
            data['values']['name'] += 'X'
        cats = model._load_records(data_list, update=True)
        self.assertEqual(list(cats), [foo, bar, baz])
        self.assertEqual(foo.name, 'FooX')
        self.assertEqual(bar.name, 'Bar')
        self.assertEqual(baz.name, 'BazX')

    def test_create_inherits(self):
        model = self.env['res.users']
        xml_id = 'test_convert.user_foo'
        par_xml_id = xml_id + '_res_partner'

        # create user
        user = model._load_records([dict(xml_id=xml_id, values={'name': 'Foo', 'login': 'foo'})])
        self.assertEqual(user, self.env.ref(xml_id, raise_if_not_found=False))
        self.assertEqual(user.partner_id, self.env.ref(par_xml_id, raise_if_not_found=False))
        self.assertEqual(user.name, 'Foo')
        self.assertEqual(user.login, 'foo')

    def test_recreate(self):
        model = self.env['res.partner.category']
        xml_id = 'test_convert.category_foo'
        data = dict(xml_id=xml_id, values={'name': 'Foo'})

        # create category
        category = model._load_records([data])
        self.assertEqual(category, self.env.ref(xml_id, raise_if_not_found=False))
        self.assertEqual(category.name, 'Foo')

        # suppress category
        category.unlink()
        self.assertFalse(self.env.ref(xml_id, raise_if_not_found=False))

        # update category, this should recreate it
        category = model._load_records([data], update=True)
        self.assertEqual(category, self.env.ref(xml_id, raise_if_not_found=False))
        self.assertEqual(category.name, 'Foo')

    def test_create_xmlids(self):
        # create users and assign them xml ids
        foo, bar = self.env['res.users'].create([
            {'name': 'Foo', 'login': 'foo'},
            {'name': 'Bar', 'login': 'bar'},
        ])
        self.env['ir.model.data']._update_xmlids([
            dict(xml_id='test_convert.foo', record=foo, noupdate=True),
            dict(xml_id='test_convert.bar', record=bar, noupdate=True),
        ])

        self.assertEqual(foo, self.env.ref('test_convert.foo', raise_if_not_found=False))
        self.assertEqual(bar, self.env.ref('test_convert.bar', raise_if_not_found=False))

        self.assertEqual(foo.partner_id, self.env.ref('test_convert.foo_res_partner', raise_if_not_found=False))
        self.assertEqual(bar.partner_id, self.env.ref('test_convert.bar_res_partner', raise_if_not_found=False))

        self.assertEqual(self.get_data('test_convert.foo').noupdate, True)
        self.assertEqual(self.get_data('test_convert.bar').noupdate, True)

    @mute_logger('odoo.sql_db', 'odoo.addons.base.models.ir_model')
    def test_create_external_id_with_space(self):
        model = self.env['res.partner.category']
        data_list = [{
            'xml_id': 'test_convert.category_with space',
            'values': {'name': 'Bar'},
        }]
        with self.assertRaisesRegex(IntegrityError, 'ir_model_data_name_nospaces'):
            model._load_records(data_list)


class TestIrModel(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The test mode is necessary in this case.  After each test, we call
        # registry.reset_changes(), which opens a new cursor to retrieve custom
        # models and fields.  A regular cursor would correspond to the state of
        # the database before setUpClass(), which is not correct.  Instead, a
        # test cursor will correspond to the state of the database of cls.cr at
        # that point, i.e., before the call to setUp().
        cls.registry.enter_test_mode(cls.cr)
        cls.addClassCleanup(cls.registry.leave_test_mode)

        # model and records for bananas
        cls.bananas_model = cls.env['ir.model'].create({
            'name': 'Bananas',
            'model': 'x_bananas',
            'field_id': [
                (0, 0, {'name': 'x_name', 'ttype': 'char', 'field_description': 'Name'}),
                (0, 0, {'name': 'x_length', 'ttype': 'float', 'field_description': 'Length'}),
                (0, 0, {'name': 'x_color', 'ttype': 'integer', 'field_description': 'Color'}),
            ]
        })
        # add non-stored field that is not valid in order
        cls.env['ir.model.fields'].create({
            'name': 'x_is_yellow',
            'field_description': 'Is the banana yellow?',
            'ttype': 'boolean',
            'model_id': cls.bananas_model.id,
            'store': False,
            'depends': 'x_color',
            'compute': "for banana in self:\n    banana['x_is_yellow'] = banana.x_color == 9"
        })
        cls.env['x_bananas'].create([{
            'x_name': 'Banana #1',
            'x_length': 3.14159,
            'x_color': 9,
        }, {
            'x_name': 'Banana #2',
            'x_length': 0,
            'x_color': 6,
        }, {
            'x_name': 'Banana #3',
            'x_length': 10,
            'x_color': 6,
        }])

    def setUp(self):
        # this cleanup is necessary after each test, and must be done last
        self.addCleanup(self.registry.reset_changes)
        super().setUp()

    def test_model_order_constraint(self):
        """Check that the order constraint is properly enforced."""
        VALID_ORDERS = ['id', 'id desc', 'id asc, x_length', 'x_color, x_length, create_uid']
        for order in VALID_ORDERS:
            self.bananas_model.order = order

        INVALID_ORDERS = ['', 'x_wat', 'id esc', 'create_uid,', 'id, x_is_yellow']
        for order in INVALID_ORDERS:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.bananas_model.order = order

        # check that the constraint is checked at model creation
        fields_value = [
            (0, 0, {'name': 'x_name', 'ttype': 'char', 'field_description': 'Name'}),
            (0, 0, {'name': 'x_length', 'ttype': 'float', 'field_description': 'Length'}),
            (0, 0, {'name': 'x_color', 'ttype': 'integer', 'field_description': 'Color'}),
        ]
        self.env['ir.model'].create({
            'name': 'MegaBananas',
            'model': 'x_mega_bananas',
            'order': 'x_name asc, id desc',         # valid order
            'field_id': fields_value,
        })
        with self.assertRaises(ValidationError):
            self.env['ir.model'].create({
                'name': 'GigaBananas',
                'model': 'x_giga_bananas',
                'order': 'x_name asc, x_wat',       # invalid order
                'field_id': fields_value,
            })

    def test_model_order_search(self):
        """Check that custom orders are applied when querying a model."""
        ORDERS = {
            'id asc': ['Banana #1', 'Banana #2', 'Banana #3'],
            'id desc': ['Banana #3', 'Banana #2', 'Banana #1'],
            'x_color asc, id asc': ['Banana #2', 'Banana #3', 'Banana #1'],
            'x_color asc, id desc': ['Banana #3', 'Banana #2', 'Banana #1'],
            'x_length asc, id': ['Banana #2', 'Banana #1', 'Banana #3'],
        }
        for order, names in ORDERS.items():
            self.bananas_model.order = order
            self.assertEqual(self.env['x_bananas']._order, order)

            bananas = self.env['x_bananas'].search([])
            self.assertEqual(bananas.mapped('x_name'), names, 'failed to order by %s' % order)
