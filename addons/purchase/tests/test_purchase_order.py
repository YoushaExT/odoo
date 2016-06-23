# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import fields
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.addons.account.tests.account_test_classes import AccountingTestCase


class TestPurchaseOrder(AccountingTestCase):

    def setUp(self):
        super(TestPurchaseOrder, self).setUp()
        # Useful models
        self.PurchaseOrder = self.env['purchase.order']
        self.PurchaseOrderLine = self.env['purchase.order.line']
        self.AccountInvoice = self.env['account.invoice']
        self.AccountInvoiceLine = self.env['account.invoice.line']

        self.partner_id = self.env.ref('base.res_partner_1')
        self.partner_id_1 = self.env.ref('base.res_partner_3')
        self.product_id_1 = self.env.ref('product.product_product_8')
        self.product_id_2 = self.env.ref('product.product_product_11')

    def test_00_purchase_order_flow(self):
        # Ensure product_id_2 doesn't have res_partner_1 as supplier
        if self.partner_id in self.product_id_2.seller_ids.mapped('name'):
            id_to_remove = self.product_id_2.seller_ids.filtered(lambda r: r.name == self.partner_id).ids[0] if self.product_id_2.seller_ids.filtered(lambda r: r.name == self.partner_id) else False
            if id_to_remove:
                self.product_id_2.write({
                    'seller_ids': [(2, id_to_remove, False)],
                })
        self.assertFalse(self.product_id_2.seller_ids.filtered(lambda r: r.name == self.partner_id), 'Purchase: the partner should not be in the list of the product suppliers')

        po_vals = {
            'partner_id': self.partner_id.id,
            'order_line': [
                (0, 0, {
                    'name': self.product_id_1.name,
                    'product_id': self.product_id_1.id,
                    'product_qty': 5.0,
                    'product_uom': self.product_id_1.uom_po_id.id,
                    'price_unit': 500.0,
                    'date_planned': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                }),
                (0, 0, {
                    'name': self.product_id_2.name,
                    'product_id': self.product_id_2.id,
                    'product_qty': 5.0,
                    'product_uom': self.product_id_2.uom_po_id.id,
                    'price_unit': 250.0,
                    'date_planned': datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                })],
        }
        self.po = self.PurchaseOrder.create(po_vals)
        self.assertTrue(self.po, 'Purchase: no purchase order created')
        self.assertEqual(self.po.invoice_status, 'no', 'Purchase: PO invoice_status should be "Not purchased"')
        self.assertEqual(self.po.order_line.mapped('qty_received'), [0.0, 0.0], 'Purchase: no product should be received"')
        self.assertEqual(self.po.order_line.mapped('qty_invoiced'), [0.0, 0.0], 'Purchase: no product should be invoiced"')

        self.po.button_confirm()
        self.assertEqual(self.po.state, 'purchase', 'Purchase: PO state should be "Purchase"')
        self.assertEqual(self.po.invoice_status, 'to invoice', 'Purchase: PO invoice_status should be "Waiting Invoices"')

        self.assertTrue(self.product_id_2.seller_ids.filtered(lambda r: r.name == self.partner_id), 'Purchase: the partner should be in the list of the product suppliers')

        seller = self.product_id_2._select_seller(partner_id=self.partner_id, quantity=2.0, date=self.po.date_planned, uom_id=self.product_id_2.uom_po_id)
        price_unit = seller.price if seller else 0.0
        if price_unit and seller and self.po.currency_id and seller.currency_id != self.po.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.po.currency_id)
        self.assertEqual(price_unit, 250.0, 'Purchase: the price of the product for the supplier should be 250.0.')

        self.assertEqual(self.po.picking_count, 1, 'Purchase: one picking should be created"')
        self.picking = self.po.picking_ids[0]
        self.picking.force_assign()
        self.picking.pack_operation_product_ids.write({'qty_done': 5.0})
        self.picking.do_new_transfer()
        self.assertEqual(self.po.order_line.mapped('qty_received'), [5.0, 5.0], 'Purchase: all products should be received"')

        self.invoice = self.AccountInvoice.create({
            'partner_id': self.partner_id.id,
            'purchase_id': self.po.id,
            'account_id': self.partner_id.property_account_payable_id.id,
        })
        self.invoice.purchase_order_change()
        self.assertEqual(self.po.order_line.mapped('qty_invoiced'), [5.0, 5.0], 'Purchase: all products should be invoiced"')

    def test_01_vendor_price(self):
        #Case1: We find a vendor for the product variant and take the variant vendor price.
        #Add the vendors in product variants.
        self.product_id_1.write({'product_seller_ids': [(0, 0, {'name': self.partner_id.id, 'min_qty': 5.0, 'price': 500.0})]})

        #Lets create a purchase order to test the vendor price.
        self.po1 = self.PurchaseOrder.create({'partner_id': self.partner_id.id})

        #Call the 'onchange_product_id' to get the price from vendor.
        po_line_1 = self.PurchaseOrderLine.new({
            'name': self.product_id_1.name,
            'product_id': self.product_id_1.id,
            'order_id': self.po1.id,
            'product_uom': self.product_id_1.uom_po_id.id,
            'date_planned': fields.Datetime.now(),
        })
        po_line_1.onchange_product_id()
        line_dict_1 = po_line_1._convert_to_write({key: po_line_1[key] for key in po_line_1._cache})
        self.order_line1 = self.PurchaseOrderLine.create(line_dict_1)

        self.assertEqual(self.order_line1.product_qty, 5.0, 'Purchase: the minimal quantity of the product for the supplier should be 5.0.')
        self.assertEqual(self.order_line1.price_unit, 500.0, 'Purchase: the price of the product for the supplier should be 500.0.')

        #Case2: When we don't find a vendor for the product variant, we take the price from product template.
        #Add the vendors in product variants and product template.
        self.product_id_1.write({
            'product_seller_ids': [(0, 0, {
                'name': self.partner_id.id,
                'min_qty': 10,
                'price': 100})],
            'seller_ids': [(0, 0, {
                'name': self.partner_id_1.id,
                'min_qty': 4,
                'price': 150})]
        })

        #Lets create a purchase order to test the vendor price.
        self.po2 = self.PurchaseOrder.create({'partner_id': self.partner_id_1.id})

        #Call the 'onchange_product_id' to get the price from vendor.
        po_line_2 = self.PurchaseOrderLine.new({
            'name': self.product_id_1.name,
            'product_id': self.product_id_1.id,
            'order_id': self.po2.id,
            'product_uom': self.product_id_1.uom_po_id.id,
            'date_planned': fields.Datetime.now(),
        })
        po_line_2.onchange_product_id()
        line_dict_2 = po_line_2._convert_to_write(po_line_2._cache)
        self.order_line2 = self.PurchaseOrderLine.create(line_dict_2)

        self.assertEqual(self.order_line2.product_qty, 4.0, 'Purchase: the minimal quantity of the product for the supplier should be 4.0.')
        self.assertEqual(self.order_line2.price_unit, 150.0, 'Purchase: the price of the product for the supplier should be 150.0.')
