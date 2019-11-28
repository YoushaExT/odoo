# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo.tests.common import Form, TransactionCase
from odoo.tools import mute_logger


class TestProcRule(TransactionCase):

    def setUp(self):
        super(TestProcRule, self).setUp()

        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.product = self.env['product.product'].create({
            'name': 'Desk Combination',
            'type': 'consu',
        })
        self.partner = self.env['res.partner'].create({'name': 'Partner'})

    def test_proc_rule(self):
        # Create a product route containing a stock rule that will
        # generate a move from Stock for every procurement created in Output
        product_route = self.env['stock.location.route'].create({
            'name': 'Stock -> output route',
            'product_selectable': True,
            'rule_ids': [(0, 0, {
                'name': 'Stock -> output rule',
                'action': 'pull',
                'picking_type_id': self.ref('stock.picking_type_internal'),
                'location_src_id': self.ref('stock.stock_location_stock'),
                'location_id': self.ref('stock.stock_location_output'),
            })],
        })

        # Set this route on `product.product_product_3`
        self.product.write({
            'route_ids': [(4, product_route.id)]})

        # Create Delivery Order of 10 `product.product_product_3` from Output -> Customer
        product = self.product
        vals = {
            'name': 'Delivery order for procurement',
            'partner_id': self.partner.id,
            'picking_type_id': self.ref('stock.picking_type_out'),
            'location_id': self.ref('stock.stock_location_output'),
            'location_dest_id': self.ref('stock.stock_location_customers'),
            'move_lines': [(0, 0, {
                'name': '/',
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': 10.00,
                'procure_method': 'make_to_order',
            })],
        }
        pick_output = self.env['stock.picking'].create(vals)
        pick_output.move_lines.onchange_product_id()

        # Confirm delivery order.
        pick_output.action_confirm()

        # I run the scheduler.
        # Note: If purchase if already installed, the method _run_buy will be called due
        # to the purchase demo data. As we update the stock module to run this test, the
        # method won't be an attribute of stock.procurement at this moment. For that reason
        # we mute the logger when running the scheduler.
        with mute_logger('odoo.addons.stock.models.procurement'):
            self.env['procurement.group'].run_scheduler()

        # Check that a picking was created from stock to output.
        moves = self.env['stock.move'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', self.ref('stock.stock_location_stock')),
            ('location_dest_id', '=', self.ref('stock.stock_location_output')),
            ('move_dest_ids', 'in', [pick_output.move_lines[0].id])
        ])
        self.assertEqual(len(moves.ids), 1, "It should have created a picking from Stock to Output with the original picking as destination")

    def test_rule_propagate_1(self):
        move_dest = self.env['stock.move'].create({
            'name': 'move_dest',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.ref('stock.stock_location_output'),
            'location_dest_id': self.ref('stock.stock_location_customers'),
        })

        move_orig = self.env['stock.move'].create({
            'name': 'move_orig',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'move_dest_ids': [(4, move_dest.id)],
            'propagate_date': True,
            'propagate_date_minimum_delta': 5,
            'location_id': self.ref('stock.stock_location_stock'),
            'location_dest_id': self.ref('stock.stock_location_output'),
        })

        move_dest_initial_date = move_dest.date_expected

        # change above the minimum delta
        move_orig.date_expected += timedelta(days=6)
        self.assertAlmostEqual(move_dest.date_expected, move_dest_initial_date + timedelta(days=6), delta=timedelta(seconds=10), msg='date should be propagated as the minimum delta is below')

        # change below the minimum delta
        move_dest_initial_date = move_dest.date_expected
        move_orig.date_expected += timedelta(days=4)

        self.assertAlmostEqual(move_dest.date_expected, move_dest_initial_date, delta=timedelta(seconds=10), msg='date should not be propagated as the minimum delta is above')

    def test_rule_propagate_2(self):
        move_dest = self.env['stock.move'].create({
            'name': 'move_dest',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.ref('stock.stock_location_output'),
            'location_dest_id': self.ref('stock.stock_location_customers'),
        })

        move_orig = self.env['stock.move'].create({
            'name': 'move_orig',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'move_dest_ids': [(4, move_dest.id)],
            'propagate_date': False,
            'propagate_date_minimum_delta': 5,
            'location_id': self.ref('stock.stock_location_stock'),
            'location_dest_id': self.ref('stock.stock_location_output'),
        })

        move_dest_initial_date = move_dest.date_expected

        # change below the minimum delta
        move_orig.date_expected += timedelta(days=4)
        self.assertAlmostEqual(move_dest.date_expected, move_dest_initial_date, delta=timedelta(seconds=10), msg='date should not be propagated')

        # change above the minimum delta
        move_orig.date_expected += timedelta(days=2)
        self.assertAlmostEqual(move_dest.date_expected, move_dest_initial_date, delta=timedelta(seconds=10), msg='date should not be propagated')

    def test_rule_propagate_3(self):
        move_dest = self.env['stock.move'].create({
            'name': 'move_dest',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.ref('stock.stock_location_output'),
            'location_dest_id': self.ref('stock.stock_location_customers'),
        })

        move_orig = self.env['stock.move'].create({
            'name': 'move_orig',
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'move_dest_ids': [(4, move_dest.id)],
            'propagate_date': True,
            'propagate_date_minimum_delta': 5,
            'location_id': self.ref('stock.stock_location_stock'),
            'location_dest_id': self.ref('stock.stock_location_output'),
            'quantity_done': 10,
        })
        move_orig.date_expected -= timedelta(days=6)
        move_dest_initial_date = move_dest.date_expected
        move_orig_initial_date = move_orig.date_expected
        move_orig._action_done()
        self.assertAlmostEqual(move_orig.date_expected, move_orig_initial_date, delta=timedelta(seconds=10), msg='schedule date should not be impacted by action_done')
        self.assertAlmostEqual(move_orig.date, datetime.now(), delta=timedelta(seconds=10), msg='date should be now')
        self.assertAlmostEqual(move_dest.date_expected, move_dest_initial_date + timedelta(days=6), delta=timedelta(seconds=10), msg='date should be propagated')

    def test_reordering_rule_1(self):
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        orderpoint_form = Form(self.env['stock.warehouse.orderpoint'])
        orderpoint_form.product_id = self.product
        orderpoint_form.location_id = warehouse.lot_stock_id
        orderpoint_form.product_min_qty = 0.0
        orderpoint_form.product_max_qty = 5.0
        orderpoint_form.save()

        self.env['stock.rule'].create({
            'name': 'Rule Supplier',
            'route_id': warehouse.reception_route_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_src_id': self.env.ref('stock.stock_location_suppliers').id,
            'action': 'pull',
            'delay': 9.0,
            'procure_method': 'make_to_stock',
            'picking_type_id': warehouse.in_type_id.id,
        })

        delivery_move = self.env['stock.move'].create({
            'name': 'Delivery',
            'date_expected': datetime.today() + timedelta(days=5),
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': 12.0,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': self.ref('stock.stock_location_customers'),
        })
        delivery_move._action_confirm()
        self.env['procurement.group'].run_scheduler()

        receipt_move = self.env['stock.move'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', self.env.ref('stock.stock_location_suppliers').id)
        ])
        self.assertTrue(receipt_move)
        self.assertEqual(receipt_move.date_expected.date(), date.today())
        self.assertEqual(receipt_move.product_uom_qty, 17.0)


class TestProcRuleLoad(TransactionCase):
    def setUp(cls):
        super(TestProcRuleLoad, cls).setUp()
        cls.skipTest("Performance test, too heavy to run.")

    def test_orderpoint_1(self):
        """ Try 500 products with a 1000 RR(stock -> shelf1 and stock -> shelf2)
        Also randomly include 4 miss configuration.
        """
        warehouse = self.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TWH'
        })
        warehouse.reception_steps = 'three_steps'
        supplier_loc = self.env.ref('stock.stock_location_suppliers')
        stock_loc = warehouse.lot_stock_id
        shelf1 = self.env['stock.location'].create({
            'location_id': stock_loc.id,
            'usage': 'internal',
            'name': 'shelf1'
        })
        shelf2 = self.env['stock.location'].create({
            'location_id': stock_loc.id,
            'usage': 'internal',
            'name': 'shelf2'
        })

        products = self.env['product.product'].create([{'name': i, 'type': 'product'} for i in range(500)])
        self.env['stock.warehouse.orderpoint'].create([{
            'product_id': products[i // 2].id,
            'location_id': (i % 2 == 0) and shelf1.id or shelf2.id,
            'warehouse_id': warehouse.id,
            'product_min_qty': 5,
            'product_max_qty': 10,
        } for i in range(1000)])

        self.env['stock.rule'].create({
            'name': 'Rule Shelf1',
            'route_id': warehouse.reception_route_id.id,
            'location_id': shelf1.id,
            'location_src_id': stock_loc.id,
            'action': 'pull',
            'procure_method': 'make_to_order',
            'picking_type_id': warehouse.int_type_id.id,
        })
        self.env['stock.rule'].create({
            'name': 'Rule Shelf2',
            'route_id': warehouse.reception_route_id.id,
            'location_id': shelf2.id,
            'location_src_id': stock_loc.id,
            'action': 'pull',
            'procure_method': 'make_to_order',
            'picking_type_id': warehouse.int_type_id.id,
        })
        self.env['stock.rule'].create({
            'name': 'Rule Supplier',
            'route_id': warehouse.reception_route_id.id,
            'location_id': warehouse.wh_input_stock_loc_id.id,
            'location_src_id': supplier_loc.id,
            'action': 'pull',
            'procure_method': 'make_to_stock',
            'picking_type_id': warehouse.in_type_id.id,
        })

        wrong_route = self.env['stock.location.route'].create({
            'name': 'Wrong Route',
        })
        self.env['stock.rule'].create({
            'name': 'Trap Rule',
            'route_id': wrong_route.id,
            'location_id': warehouse.wh_input_stock_loc_id.id,
            'location_src_id': supplier_loc.id,
            'action': 'pull',
            'procure_method': 'make_to_order',
            'picking_type_id': warehouse.in_type_id.id,
        })
        (products[50] | products[99] | products[150] | products[199]).write({
            'route_ids': [(4, wrong_route.id)]
        })
        self.env['procurement.group'].run_scheduler()
        self.assertTrue(self.env['stock.move'].search([('product_id', 'in', products.ids)]))
        for index in [50, 99, 150, 199]:
            self.assertTrue(self.env['mail.activity'].search([
                ('res_id', '=', products[index].product_tmpl_id.id),
                ('res_model_id', '=', self.env.ref('product.model_product_template').id)
            ]))
