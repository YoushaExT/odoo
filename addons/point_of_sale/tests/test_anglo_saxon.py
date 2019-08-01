# -*- coding: utf-8 -*-

import openerp
import time
from openerp import fields

from openerp.tests import common


class TestAngloSaxonCommon(common.TransactionCase):

    def setUp(self):
        super(TestAngloSaxonCommon, self).setUp()
        self.PosMakePayment = self.env['pos.make.payment']
        self.PosOrder = self.env['pos.order']
        self.Statement = self.env['account.bank.statement']
        self.company = self.env.ref('base.main_company')
        self.warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.product = self.env.ref('product.product_product_3')
        self.partner = self.env.ref('base.res_partner_1')
        self.category = self.env.ref('product.product_category_1')
        self.category = self.category.copy({'name': 'New category','property_valuation': 'real_time'})
        account_type_rcv = self.env.ref('account.data_account_type_receivable')
        account_type_inc = self.env.ref('account.data_account_type_revenue')
        account_type_exp = self.env.ref('account.data_account_type_expenses')
        self.account = self.env['account.account'].create({'name': 'Receivable', 'code': 'RCV00' , 'user_type_id': account_type_rcv.id, 'reconcile': True})
        account_expense = self.env['account.account'].create({'name': 'Expense', 'code': 'EXP00' , 'user_type_id': account_type_exp.id, 'reconcile': True})
        account_income = self.env['account.account'].create({'name': 'Income', 'code': 'INC00' , 'user_type_id': account_type_inc.id, 'reconcile': True})
        account_output = self.env['account.account'].create({'name': 'Output', 'code': 'OUT00' , 'user_type_id': account_type_exp.id, 'reconcile': True})
        account_valuation = self.env['account.account'].create({'name': 'Valuation', 'code': 'STV00', 'user_type_id': account_type_exp.id, 'reconcile': True})
        self.partner.property_account_receivable_id = self.account
        self.category.property_account_income_categ_id = account_income
        self.category.property_account_expense_categ_id = account_expense
        self.category.property_stock_account_input_categ_id = self.account
        self.category.property_stock_account_output_categ_id = account_output
        self.category.property_stock_valuation_account_id = account_valuation
        self.category.property_stock_journal = self.env['account.journal'].create({'name': 'Stock journal', 'type': 'sale', 'code': 'STK00'})
        self.pos_config = self.env.ref('point_of_sale.pos_config_main')
        self.pos_config = self.pos_config.copy({'name': 'New POS config'})
        self.product = self.product.copy({'name': 'New product','standard_price': 100})
        self.company.anglo_saxon_accounting = True
        self.product.categ_id = self.category
        self.product.property_account_expense_id = account_expense
        self.product.property_account_income_id = account_income
        sale_journal = self.env['account.journal'].create({'name': 'POS journal', 'type': 'sale', 'code': 'POS00'})
        self.pos_config.journal_id = sale_journal
        self.cash_journal = self.env['account.journal'].create({'name': 'CASH journal', 'type': 'cash', 'code': 'CSH00'})
        self.sale_journal = self.env['account.journal'].create({'name': 'SALE journal', 'type': 'sale', 'code': 'INV00'})
        self.pos_config.invoice_journal_id = self.sale_journal
        self.pos_config.journal_ids = [self.cash_journal.id]


class TestAngloSaxonFlow(TestAngloSaxonCommon):

    def test_create_account_move_line(self):
        # This test will check that the correct journal entries are created when a product in real time valuation
        # is sold in a company using anglo-saxon
        self.pos_config.open_session_cb()
        self.pos_config.current_session_id.write({'journal_ids': [(6, 0, [self.cash_journal.id])]})
        self.cash_journal.loss_account_id = self.account
        self.pos_statement = self.Statement.create({
            'balance_start': 0.0,
            'balance_end_real': 0.0,
            'date': time.strftime('%Y-%m-%d'),
            'journal_id': self.cash_journal.id,
            'company_id': self.company.id,
            'name': 'pos session test',
        })
        self.pos_config.current_session_id.write({'statement_ids': [(6, 0, [self.pos_statement.id])]})

        # I create a PoS order with 1 unit of New product at 450 EUR
        self.pos_order_pos0 = self.PosOrder.create({
            'company_id': self.company.id,
            'partner_id': self.partner.id,
            'pricelist_id': self.company.partner_id.property_product_pricelist.id,
            'session_id': self.pos_config.current_session_id.id,
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.product.id,
                'price_unit': 450,
                'discount': 0.0,
                'qty': 1.0,
                'price_subtotal': 450,
                'price_subtotal_incl': 450,
            })],
            'amount_total': 450,
            'amount_tax': 0,
            'amount_paid': 0,
            'amount_return': 0,
        })

        # I make a payment to fully pay the order
        context_make_payment = {"active_ids": [self.pos_order_pos0.id], "active_id": self.pos_order_pos0.id}
        self.pos_make_payment_0 = self.PosMakePayment.with_context(context_make_payment).create({
            'amount': 450.0,
            'journal_id': self.cash_journal.id,
        })

        # I click on the validate button to register the payment.
        context_payment = {'active_id': self.pos_order_pos0.id}
        self.pos_make_payment_0.with_context(context_payment).check()

        # I check that the order is marked as paid
        self.assertEqual(self.pos_order_pos0.state, 'paid', 'Order should be in paid state.')
        self.assertEqual(self.pos_order_pos0.amount_paid, 450, 'Amount paid for the order should be updated.')

        # I close the current session to generate the journal entries
        current_session_id = self.pos_config.current_session_id
        current_session_id._check_pos_session_balance()
        current_session_id.action_pos_session_close()
        self.assertEqual(current_session_id.state, 'closed', 'Check that session is closed')

        # I test that the generated journal entries are correct.
        account_output = self.category.property_stock_account_output_categ_id
        expense_account = self.category.property_account_expense_categ_id
        aml = self.pos_order_pos0.account_move.line_ids
        aml_output = aml.filtered(lambda l: l.account_id.id == account_output.id)
        aml_expense = aml.filtered(lambda l: l.account_id.id == expense_account.id)
        self.assertEqual(aml_output.credit, self.product.standard_price, "Cost of Good Sold entry missing or mismatching")
        self.assertEqual(aml_expense.debit, self.product.standard_price, "Cost of Good Sold entry missing or mismatching")

    def _prepare_pos_order(self):
        """ Set the cost method of `self.product` as FIFO. Receive 5@5 and 5@1 and
        create a `pos.order` record selling 7 units @ 450.
        """
        # check fifo Costing Method of product.category
        self.product.categ_id.property_cost_method = 'fifo'
        self.product.standard_price = 5.0
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'inventory_quantity': 5.0,
            'location_id': self.warehouse.lot_stock_id.id,
        })
        self.product.standard_price = 1.0
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'inventory_quantity': 10.0,
            'location_id': self.warehouse.lot_stock_id.id,
        })
        self.assertEqual(self.product.value_svl, 30, "Value should be (5*5 + 5*1) = 30")
        self.assertEqual(self.product.quantity_svl, 10)

        self.pos_config.open_session_cb()
        self.pos_config.module_account = True

        pos_order_values = {
            'company_id': self.company.id,
            'partner_id': self.partner.id,
            'pricelist_id': self.company.partner_id.property_product_pricelist.id,
            'session_id': self.pos_config.current_session_id.id,
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.product.id,
                'price_unit': 450,
                'discount': 0.0,
                'qty': 7.0,
                'price_subtotal': 7 * 450,
                'price_subtotal_incl': 7 * 450,
            })],
            'amount_total': 7 * 450,
            'amount_tax': 0,
            'amount_paid': 0,
            'amount_return': 0,
        }

        return self.PosOrder.create(pos_order_values)

    def test_fifo_valuation_no_invoice(self):
        """Register a payment and validate a session after selling a fifo
        product without making an invoice for the customer"""
        pos_order_pos0 = self._prepare_pos_order()
        context_make_payment = {"active_ids": [pos_order_pos0.id], "active_id": pos_order_pos0.id}
        self.pos_make_payment_0 = self.PosMakePayment.with_context(context_make_payment).create({
            'amount': 7 * 450.0,
        })

        # register the payment
        context_payment = {'active_id': pos_order_pos0.id}
        self.pos_make_payment_0.with_context(context_payment).check()

        # validate the session
        current_session_id = self.pos_config.current_session_id
        current_session_id.action_pos_session_validate()

        # check the anglo saxon move lines
        line = pos_order_pos0.account_move.line_ids.filtered(lambda l: l.debit and l.account_id == self.category.property_account_expense_categ_id)
        self.assertEqual(pos_order_pos0.account_move.journal_id, self.pos_config.journal_id)
        self.assertEqual(line.debit, 27, 'As it is a fifo product, the move\'s value should be 5*5 + 2*1')

    def test_fifo_valuation_with_invoice(self):
        """Register a payment and validate a session after selling a fifo
        product and make an invoice for the customer"""
        pos_order_pos0 = self._prepare_pos_order()
        context_make_payment = {"active_ids": [pos_order_pos0.id], "active_id": pos_order_pos0.id}
        self.pos_make_payment_0 = self.PosMakePayment.with_context(context_make_payment).create({
            'amount': 7 * 450.0,
            'journal_id': self.cash_journal.id,
        })

        # register the payment
        context_payment = {'active_id': pos_order_pos0.id}
        self.pos_make_payment_0.with_context(context_payment).check()

        # Create the customer invoice
        pos_order_pos0.action_pos_order_invoice()
        pos_order_pos0.account_move.post()

        # validate the session
        current_session_id = self.pos_config.current_session_id
        current_session_id.action_pos_session_validate()

        # check the anglo saxon move lines
        line = pos_order_pos0.account_move.line_ids.filtered(lambda l: l.debit and l.account_id == self.category.property_account_expense_categ_id)
        self.assertEqual(pos_order_pos0.account_move.journal_id, self.pos_config.invoice_journal_id)
        self.assertEqual(line.debit, 27, 'As it is a fifo product, the move\'s value should be 5*5 + 2*1')
