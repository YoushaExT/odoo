# -*- coding: utf-8 -*-
# pylint: disable=bad-whitespace
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo import fields, Command


@tagged('post_install', '-at_install')
class TestAccountMoveInRefundOnchanges(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.invoice = cls.init_invoice('in_refund', products=cls.product_a+cls.product_b)

        cls.product_line_vals_1 = {
            'name': cls.product_a.name,
            'product_id': cls.product_a.id,
            'account_id': cls.product_a.property_account_expense_id.id,
            'partner_id': cls.partner_a.id,
            'product_uom_id': cls.product_a.uom_id.id,
            'quantity': 1.0,
            'discount': 0.0,
            'price_unit': 800.0,
            'price_subtotal': 800.0,
            'price_total': 920.0,
            'tax_ids': cls.product_a.supplier_taxes_id.ids,
            'tax_line_id': False,
            'currency_id': cls.company_data['currency'].id,
            'amount_currency': -800.0,
            'debit': 0.0,
            'credit': 800.0,
            'date_maturity': False,
        }
        cls.product_line_vals_2 = {
            'name': cls.product_b.name,
            'product_id': cls.product_b.id,
            'account_id': cls.product_b.property_account_expense_id.id,
            'partner_id': cls.partner_a.id,
            'product_uom_id': cls.product_b.uom_id.id,
            'quantity': 1.0,
            'discount': 0.0,
            'price_unit': 160.0,
            'price_subtotal': 160.0,
            'price_total': 208.0,
            'tax_ids': cls.product_b.supplier_taxes_id.ids,
            'tax_line_id': False,
            'currency_id': cls.company_data['currency'].id,
            'amount_currency': -160.0,
            'debit': 0.0,
            'credit': 160.0,
            'date_maturity': False,
        }
        cls.tax_line_vals_1 = {
            'name': cls.tax_purchase_a.name,
            'product_id': False,
            'account_id': cls.company_data['default_account_tax_purchase'].id,
            'partner_id': cls.partner_a.id,
            'product_uom_id': False,
            'quantity': 1.0,
            'discount': 0.0,
            'price_unit': 144.0,
            'price_subtotal': 144.0,
            'price_total': 144.0,
            'tax_ids': [],
            'tax_line_id': cls.tax_purchase_a.id,
            'currency_id': cls.company_data['currency'].id,
            'amount_currency': -144.0,
            'debit': 0.0,
            'credit': 144.0,
            'date_maturity': False,
        }
        cls.tax_line_vals_2 = {
            'name': cls.tax_purchase_b.name,
            'product_id': False,
            'account_id': cls.company_data['default_account_tax_purchase'].id,
            'partner_id': cls.partner_a.id,
            'product_uom_id': False,
            'quantity': 1.0,
            'discount': 0.0,
            'price_unit': 24.0,
            'price_subtotal': 24.0,
            'price_total': 24.0,
            'tax_ids': [],
            'tax_line_id': cls.tax_purchase_b.id,
            'currency_id': cls.company_data['currency'].id,
            'amount_currency': -24.0,
            'debit': 0.0,
            'credit': 24.0,
            'date_maturity': False,
        }
        cls.term_line_vals_1 = {
            'name': '',
            'product_id': False,
            'account_id': cls.company_data['default_account_payable'].id,
            'partner_id': cls.partner_a.id,
            'product_uom_id': False,
            'quantity': 1.0,
            'discount': 0.0,
            'price_unit': -1128.0,
            'price_subtotal': -1128.0,
            'price_total': -1128.0,
            'tax_ids': [],
            'tax_line_id': False,
            'currency_id': cls.company_data['currency'].id,
            'amount_currency': 1128.0,
            'debit': 1128.0,
            'credit': 0.0,
            'date_maturity': fields.Date.from_string('2019-01-01'),
        }
        cls.move_vals = {
            'partner_id': cls.partner_a.id,
            'currency_id': cls.company_data['currency'].id,
            'journal_id': cls.company_data['default_journal_purchase'].id,
            'date': fields.Date.from_string('2019-01-01'),
            'fiscal_position_id': False,
            'payment_reference': '',
            'invoice_payment_term_id': cls.pay_terms_a.id,
            'amount_untaxed': 960.0,
            'amount_tax': 168.0,
            'amount_total': 1128.0,
        }

    def setUp(self):
        super(TestAccountMoveInRefundOnchanges, self).setUp()
        self.assertInvoiceValues(self.invoice, [
            self.product_line_vals_1,
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            self.term_line_vals_1,
        ], self.move_vals)

    def test_in_refund_line_onchange_product_1(self):
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.product_id = self.product_b
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'name': self.product_b.name,
                'product_id': self.product_b.id,
                'product_uom_id': self.product_b.uom_id.id,
                'account_id': self.product_b.property_account_expense_id.id,
                'price_unit': 160.0,
                'price_subtotal': 160.0,
                'price_total': 208.0,
                'tax_ids': self.product_b.supplier_taxes_id.ids,
                'amount_currency': -160.0,
                'credit': 160.0,
            },
            self.product_line_vals_2,
            {
                **self.tax_line_vals_1,
                'price_unit': 48.0,
                'price_subtotal': 48.0,
                'price_total': 48.0,
                'amount_currency': -48.0,
                'credit': 48.0,
            },
            {
                **self.tax_line_vals_2,
                'price_unit': 48.0,
                'price_subtotal': 48.0,
                'price_total': 48.0,
                'amount_currency': -48.0,
                'credit': 48.0,
            },
            {
                **self.term_line_vals_1,
                'price_unit': -416.0,
                'price_subtotal': -416.0,
                'price_total': -416.0,
                'amount_currency': 416.0,
                'debit': 416.0,
            },
        ], {
            **self.move_vals,
            'amount_untaxed': 320.0,
            'amount_tax': 96.0,
            'amount_total': 416.0,
        })

    def test_in_refund_line_onchange_business_fields_1(self):
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            # Current price_unit is 800.
            # We set quantity = 4, discount = 50%, price_unit = 400. The debit/credit fields don't change because (4 * 400) * 0.5 = 800.
            line_form.quantity = 4
            line_form.discount = 50
            line_form.price_unit = 400
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'quantity': 4,
                'discount': 50.0,
                'price_unit': 400.0,
            },
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            self.term_line_vals_1,
        ], self.move_vals)

        move_form = Form(self.invoice)
        with move_form.line_ids.edit(2) as line_form:
            # Reset field except the discount that becomes 100%.
            # /!\ The modification is made on the accounting tab.
            line_form.quantity = 1
            line_form.discount = 100
            line_form.price_unit = 800
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'discount': 100.0,
                'price_subtotal': 0.0,
                'price_total': 0.0,
                'amount_currency': 0.0,
                'credit': 0.0,
            },
            self.product_line_vals_2,
            {
                **self.tax_line_vals_1,
                'price_unit': 24.0,
                'price_subtotal': 24.0,
                'price_total': 24.0,
                'amount_currency': -24.0,
                'credit': 24.0,
            },
            self.tax_line_vals_2,
            {
                **self.term_line_vals_1,
                'price_unit': -208.0,
                'price_subtotal': -208.0,
                'price_total': -208.0,
                'amount_currency': 208.0,
                'debit': 208.0,
            },
        ], {
            **self.move_vals,
            'amount_untaxed': 160.0,
            'amount_tax': 48.0,
            'amount_total': 208.0,
        })

    def test_in_refund_line_onchange_accounting_fields_1(self):
        move_form = Form(self.invoice)
        with move_form.line_ids.edit(2) as line_form:
            # Custom credit on the first product line.
            line_form.credit = 3000
        with move_form.line_ids.edit(3) as line_form:
            # Custom debit on the second product line. Credit should be reset by onchange.
            # /!\ It's a negative line.
            line_form.debit = 500
        with move_form.line_ids.edit(0) as line_form:
            # Custom credit on the first tax line.
            line_form.credit = 800
        with move_form.line_ids.edit(4) as line_form:
            # Custom credit on the second tax line.
            line_form.credit = 250
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'price_unit': 3000.0,
                'price_subtotal': 3000.0,
                'price_total': 3450.0,
                'amount_currency': -3000.0,
                'credit': 3000.0,
            },
            {
                **self.product_line_vals_2,
                'price_unit': -500.0,
                'price_subtotal': -500.0,
                'price_total': -650.0,
                'amount_currency': 500.0,
                'debit': 500.0,
                'credit': 0.0,
            },
            {
                **self.tax_line_vals_1,
                'price_unit': 800.0,
                'price_subtotal': 800.0,
                'price_total': 800.0,
                'amount_currency': -800.0,
                'credit': 800.0,
            },
            {
                **self.tax_line_vals_2,
                'price_unit': 250.0,
                'price_subtotal': 250.0,
                'price_total': 250.0,
                'amount_currency': -250.0,
                'credit': 250.0,
            },
            {
                **self.term_line_vals_1,
                'price_unit': -3550.0,
                'price_subtotal': -3550.0,
                'price_total': -3550.0,
                'amount_currency': 3550.0,
                'debit': 3550.0,
            },
        ], {
            **self.move_vals,
            'amount_untaxed': 2500.0,
            'amount_tax': 1050.0,
            'amount_total': 3550.0,
        })

    def test_in_refund_line_onchange_partner_1(self):
        move_form = Form(self.invoice)
        move_form.partner_id = self.partner_b
        move_form.payment_reference = 'turlututu'
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'partner_id': self.partner_b.id,
            },
            {
                **self.product_line_vals_2,
                'partner_id': self.partner_b.id,
            },
            {
                **self.tax_line_vals_1,
                'partner_id': self.partner_b.id,
            },
            {
                **self.tax_line_vals_2,
                'partner_id': self.partner_b.id,
            },
            {
                **self.term_line_vals_1,
                'name': 'turlututu',
                'partner_id': self.partner_b.id,
                'account_id': self.partner_b.property_account_payable_id.id,
                'price_unit': -338.4,
                'price_subtotal': -338.4,
                'price_total': -338.4,
                'amount_currency': 338.4,
                'debit': 338.4,
            },
            {
                **self.term_line_vals_1,
                'name': 'turlututu',
                'partner_id': self.partner_b.id,
                'account_id': self.partner_b.property_account_payable_id.id,
                'price_unit': -789.6,
                'price_subtotal': -789.6,
                'price_total': -789.6,
                'amount_currency': 789.6,
                'debit': 789.6,
                'date_maturity': fields.Date.from_string('2019-02-28'),
            },
        ], {
            **self.move_vals,
            'partner_id': self.partner_b.id,
            'payment_reference': 'turlututu',
            'fiscal_position_id': self.fiscal_pos_a.id,
            'invoice_payment_term_id': self.pay_terms_b.id,
            'amount_untaxed': 960.0,
            'amount_tax': 168.0,
            'amount_total': 1128.0,
        })

        # Remove lines and recreate them to apply the fiscal position.
        move_form = Form(self.invoice)
        move_form.invoice_line_ids.remove(0)
        move_form.invoice_line_ids.remove(0)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product_a
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product_b
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'account_id': self.product_b.property_account_expense_id.id,
                'partner_id': self.partner_b.id,
                'tax_ids': self.tax_purchase_b.ids,
            },
            {
                **self.product_line_vals_2,
                'partner_id': self.partner_b.id,
                'price_total': 184.0,
                'tax_ids': self.tax_purchase_b.ids,
            },
            {
                **self.tax_line_vals_1,
                'name': self.tax_purchase_b.name,
                'partner_id': self.partner_b.id,
                'tax_line_id': self.tax_purchase_b.id,
            },
            {
                **self.term_line_vals_1,
                'name': 'turlututu',
                'account_id': self.partner_b.property_account_payable_id.id,
                'partner_id': self.partner_b.id,
                'price_unit': -331.2,
                'price_subtotal': -331.2,
                'price_total': -331.2,
                'amount_currency': 331.2,
                'debit': 331.2,
            },
            {
                **self.term_line_vals_1,
                'name': 'turlututu',
                'account_id': self.partner_b.property_account_payable_id.id,
                'partner_id': self.partner_b.id,
                'price_unit': -772.8,
                'price_subtotal': -772.8,
                'price_total': -772.8,
                'amount_currency': 772.8,
                'debit': 772.8,
                'date_maturity': fields.Date.from_string('2019-02-28'),
            },
        ], {
            **self.move_vals,
            'partner_id': self.partner_b.id,
            'payment_reference': 'turlututu',
            'fiscal_position_id': self.fiscal_pos_a.id,
            'invoice_payment_term_id': self.pay_terms_b.id,
            'amount_untaxed': 960.0,
            'amount_tax': 144.0,
            'amount_total': 1104.0,
        })

    def test_in_refund_line_onchange_taxes_1(self):
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.price_unit = 960
            line_form.tax_ids.add(self.tax_armageddon)
        move_form.save()

        child_tax_1 = self.tax_armageddon.children_tax_ids[0]
        child_tax_2 = self.tax_armageddon.children_tax_ids[1]

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'price_unit': 960.0,
                'price_subtotal': 800.0,
                'price_total': 1176.0,
                'tax_ids': (self.tax_purchase_a + self.tax_armageddon).ids,
            },
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            {
                'name': child_tax_1.name,
                'product_id': False,
                'account_id': self.company_data['default_account_expense'].id,
                'partner_id': self.partner_a.id,
                'product_uom_id': False,
                'quantity': 1.0,
                'discount': 0.0,
                'price_unit': 96.0,
                'price_subtotal': 96.0,
                'price_total': 105.6,
                'tax_ids': child_tax_2.ids,
                'tax_line_id': child_tax_1.id,
                'currency_id': self.company_data['currency'].id,
                'amount_currency': -96.0,
                'debit': 0.0,
                'credit': 96.0,
                'date_maturity': False,
            },
            {
                'name': child_tax_1.name,
                'product_id': False,
                'account_id': self.company_data['default_account_tax_sale'].id,
                'partner_id': self.partner_a.id,
                'product_uom_id': False,
                'quantity': 1.0,
                'discount': 0.0,
                'price_unit': 64.0,
                'price_subtotal': 64.0,
                'price_total': 70.4,
                'tax_ids': child_tax_2.ids,
                'tax_line_id': child_tax_1.id,
                'currency_id': self.company_data['currency'].id,
                'amount_currency': -64.0,
                'debit': 0.0,
                'credit': 64.0,
                'date_maturity': False,
            },
            {
                'name': child_tax_2.name,
                'product_id': False,
                'account_id': child_tax_2.cash_basis_transition_account_id.id,
                'partner_id': self.partner_a.id,
                'product_uom_id': False,
                'quantity': 1.0,
                'discount': 0.0,
                'price_unit': 96.0,
                'price_subtotal': 96.0,
                'price_total': 96.0,
                'tax_ids': [],
                'tax_line_id': child_tax_2.id,
                'currency_id': self.company_data['currency'].id,
                'amount_currency': -96.0,
                'debit': 0.0,
                'credit': 96.0,
                'date_maturity': False,
            },
            {
                **self.term_line_vals_1,
                'price_unit': -1384.0,
                'price_subtotal': -1384.0,
                'price_total': -1384.0,
                'amount_currency': 1384.0,
                'debit': 1384.0,
            },
        ], {
            **self.move_vals,
            'amount_untaxed': 960.0,
            'amount_tax': 424.0,
            'amount_total': 1384.0,
        })

    def test_in_refund_line_onchange_cash_rounding_1(self):
        move_form = Form(self.invoice)
        # Add a cash rounding having 'add_invoice_line'.
        move_form.invoice_cash_rounding_id = self.cash_rounding_a
        move_form.save()

        # The cash rounding does nothing as the total is already rounded.
        self.assertInvoiceValues(self.invoice, [
            self.product_line_vals_1,
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            self.term_line_vals_1,
        ], self.move_vals)

        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.price_unit = 799.99
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                'name': 'add_invoice_line',
                'product_id': False,
                'account_id': self.cash_rounding_a.profit_account_id.id,
                'partner_id': self.partner_a.id,
                'product_uom_id': False,
                'quantity': 1.0,
                'discount': 0.0,
                'price_unit': 0.01,
                'price_subtotal': 0.01,
                'price_total': 0.01,
                'tax_ids': [],
                'tax_line_id': False,
                'currency_id': self.company_data['currency'].id,
                'amount_currency': -0.01,
                'debit': 0.0,
                'credit': 0.01,
                'date_maturity': False,
            },
            {
                **self.product_line_vals_1,
                'price_unit': 799.99,
                'price_subtotal': 799.99,
                'price_total': 919.99,
                'amount_currency': -799.99,
                'credit': 799.99,
            },
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            self.term_line_vals_1,
        ], self.move_vals)

        move_form = Form(self.invoice)
        # Change the cash rounding to one having 'biggest_tax'.
        move_form.invoice_cash_rounding_id = self.cash_rounding_b
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'price_unit': 799.99,
                'price_subtotal': 799.99,
                'price_total': 919.99,
                'amount_currency': -799.99,
                'credit': 799.99,
            },
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            {
                'name': '%s (rounding)' % self.tax_purchase_a.name,
                'product_id': False,
                'account_id': self.company_data['default_account_tax_purchase'].id,
                'partner_id': self.partner_a.id,
                'product_uom_id': False,
                'quantity': 1.0,
                'discount': 0.0,
                'price_unit': -0.04,
                'price_subtotal': -0.04,
                'price_total': -0.04,
                'tax_ids': [],
                'tax_line_id': self.tax_purchase_a.id,
                'currency_id': self.company_data['currency'].id,
                'amount_currency': 0.04,
                'debit': 0.04,
                'credit': 0.0,
                'date_maturity': False,
            },
            {
                **self.term_line_vals_1,
                'price_unit': -1127.95,
                'price_subtotal': -1127.95,
                'price_total': -1127.95,
                'amount_currency': 1127.95,
                'debit': 1127.95,
            },
        ], {
            **self.move_vals,
            'amount_untaxed': 959.99,
            'amount_tax': 167.96,
            'amount_total': 1127.95,
        })

    def test_in_refund_line_onchange_currency_1(self):
        move_form = Form(self.invoice)
        move_form.currency_id = self.currency_data['currency']
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -800.0,
                'credit': 400.0,
            },
            {
                **self.product_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -160.0,
                'credit': 80.0,
            },
            {
                **self.tax_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -144.0,
                'credit': 72.0,
            },
            {
                **self.tax_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.0,
                'credit': 12.0,
            },
            {
                **self.term_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': 1128.0,
                'debit': 564.0,
            },
        ], {
            **self.move_vals,
            'currency_id': self.currency_data['currency'].id,
        })

        move_form = Form(self.invoice)
        # Change the date to get another rate: 1/3 instead of 1/2.
        move_form.date = fields.Date.from_string('2016-01-01')
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -800.0,
                'credit': 266.67,
            },
            {
                **self.product_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -160.0,
                'credit': 53.33,
            },
            {
                **self.tax_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -144.0,
                'credit': 48.0,
            },
            {
                **self.tax_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.0,
                'credit': 8.0,
            },
            {
                **self.term_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': 1128.0,
                'debit': 376.0,
            },
        ], {
            **self.move_vals,
            'currency_id': self.currency_data['currency'].id,
            'date': fields.Date.from_string('2016-01-01'),
        })

        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            # 0.045 * 0.1 = 0.0045. As the foreign currency has a 0.001 rounding,
            # the result should be 0.005 after rounding.
            line_form.quantity = 0.1
            line_form.price_unit = 0.045
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'quantity': 0.1,
                'price_unit': 0.05,
                'price_subtotal': 0.005,
                'price_total': 0.006,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -0.005,
                'credit': 0.0,
            },
            {
                **self.product_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -160.0,
                'credit': 53.33,
            },
            {
                **self.tax_line_vals_1,
                'price_unit': 24.0,
                'price_subtotal': 24.001,
                'price_total': 24.001,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.001,
                'credit': 8.0,
            },
            {
                **self.tax_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.0,
                'credit': 8.0,
            },
            {
                **self.term_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'price_unit': -208.01,
                'price_subtotal': -208.006,
                'price_total': -208.006,
                'amount_currency': 208.006,
                'debit': 69.33,
            },
        ], {
            **self.move_vals,
            'currency_id': self.currency_data['currency'].id,
            'date': fields.Date.from_string('2016-01-01'),
            'amount_untaxed': 160.005,
            'amount_tax': 48.001,
            'amount_total': 208.006,
        })

        # Exit the multi-currencies.
        move_form = Form(self.invoice)
        move_form.currency_id = self.company_data['currency']
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            {
                **self.product_line_vals_1,
                'quantity': 0.1,
                'price_unit': 0.05,
                'price_subtotal': 0.01,
                'price_total': 0.01,
                'amount_currency': -0.01,
                'credit': 0.01,
            },
            self.product_line_vals_2,
            {
                **self.tax_line_vals_1,
                'price_unit': 24.0,
                'price_subtotal': 24.0,
                'price_total': 24.0,
                'amount_currency': -24.0,
                'credit': 24.0,
            },
            self.tax_line_vals_2,
            {
                **self.term_line_vals_1,
                'price_unit': -208.01,
                'price_subtotal': -208.01,
                'price_total': -208.01,
                'amount_currency': 208.01,
                'debit': 208.01,
            },
        ], {
            **self.move_vals,
            'currency_id': self.company_data['currency'].id,
            'date': fields.Date.from_string('2016-01-01'),
            'amount_untaxed': 160.01,
            'amount_tax': 48.0,
            'amount_total': 208.01,
        })

    def test_in_refund_onchange_past_invoice_1(self):
        copy_invoice = self.invoice.copy()

        move_form = Form(self.invoice)
        move_form.invoice_line_ids.remove(0)
        move_form.invoice_line_ids.remove(0)
        move_form.invoice_vendor_bill_id = copy_invoice
        move_form.save()

        self.assertInvoiceValues(self.invoice, [
            self.product_line_vals_1,
            self.product_line_vals_2,
            self.tax_line_vals_1,
            self.tax_line_vals_2,
            self.term_line_vals_1,
        ], self.move_vals)

    def test_in_refund_create_1(self):
        # Test creating an account_move with the least information.
        move = self.env['account.move'].create({
            'move_type': 'in_refund',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.from_string('2019-01-01'),
            'currency_id': self.currency_data['currency'].id,
            'invoice_payment_term_id': self.pay_terms_a.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_line_vals_1['product_id'],
                    'product_uom_id': self.product_line_vals_1['product_uom_id'],
                    'price_unit': self.product_line_vals_1['price_unit'],
                    'tax_ids': [Command.set(self.product_line_vals_1['tax_ids'])],
                }),
                Command.create({
                    'product_id': self.product_line_vals_2['product_id'],
                    'product_uom_id': self.product_line_vals_2['product_uom_id'],
                    'price_unit': self.product_line_vals_2['price_unit'],
                    'tax_ids': [Command.set(self.product_line_vals_2['tax_ids'])],
                }),
            ],
        })

        self.assertInvoiceValues(move, [
            {
                **self.product_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -800.0,
                'credit': 400.0,
            },
            {
                **self.product_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -160.0,
                'credit': 80.0,
            },
            {
                **self.tax_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -144.0,
                'credit': 72.0,
            },
            {
                **self.tax_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.0,
                'credit': 12.0,
            },
            {
                **self.term_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': 1128.0,
                'debit': 564.0,
            },
        ], {
            **self.move_vals,
            'currency_id': self.currency_data['currency'].id,
        })

    def test_in_refund_write_1(self):
        # Test creating an account_move with the least information.
        move = self.env['account.move'].create({
            'move_type': 'in_refund',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.from_string('2019-01-01'),
            'currency_id': self.currency_data['currency'].id,
            'invoice_payment_term_id': self.pay_terms_a.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_line_vals_1['product_id'],
                    'product_uom_id': self.product_line_vals_1['product_uom_id'],
                    'price_unit': self.product_line_vals_1['price_unit'],
                    'tax_ids': [Command.set(self.product_line_vals_1['tax_ids'])],
                }),
            ],
        })
        move.write({
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product_line_vals_2['product_id'],
                    'product_uom_id': self.product_line_vals_2['product_uom_id'],
                    'price_unit': self.product_line_vals_2['price_unit'],
                    'tax_ids': [Command.set(self.product_line_vals_2['tax_ids'])],
                }),
            ],
        })

        self.assertInvoiceValues(move, [
            {
                **self.product_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -800.0,
                'credit': 400.0,
            },
            {
                **self.product_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -160.0,
                'credit': 80.0,
            },
            {
                **self.tax_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -144.0,
                'credit': 72.0,
            },
            {
                **self.tax_line_vals_2,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': -24.0,
                'credit': 12.0,
            },
            {
                **self.term_line_vals_1,
                'currency_id': self.currency_data['currency'].id,
                'amount_currency': 1128.0,
                'debit': 564.0,
            },
        ], {
            **self.move_vals,
            'currency_id': self.currency_data['currency'].id,
        })
