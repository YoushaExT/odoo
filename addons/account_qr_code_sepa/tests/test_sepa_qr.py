# -*- coding:utf-8 -*-

from odoo.exceptions import UserError
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

class TestSEPAQRCode(AccountTestInvoicingCommon):
    """ Tests the generation of Swiss QR-codes on invoices
    """

    @classmethod
    def setUpClass(cls):
        super(TestSEPAQRCode, cls).setUpClass()

        cls.company_data['company'].qr_code = True
        cls.acc_sepa_iban = cls.env['res.partner.bank'].create({
            'acc_number': 'BE15001559627230',
            'partner_id': cls.company_data['company'].partner_id.id,
        })

        cls.acc_non_sepa_iban = cls.env['res.partner.bank'].create({
            'acc_number': 'SA4420000001234567891234',
            'partner_id': cls.company_data['company'].partner_id.id,
        })

        cls.sepa_qr_invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner_a.id,
            'currency_id': cls.env.ref('base.EUR').id,
            'invoice_partner_bank_id': cls.acc_sepa_iban.id,
            'company_id': cls.company_data['company'].id,
            'invoice_line_ids': [
                (0, 0, {'quantity': 1, 'price_unit': 100})
            ],
        })

    def test_sepa_qr_code_generation(self):
        """ Check different cases of SEPA QR-code generation, when qr_method is
        specified beforehand.
        """
        self.sepa_qr_invoice.qr_code_method = 'sct_qr'

        # Using a SEPA IBAN should work
        self.sepa_qr_invoice.generate_qr_code()

        # Using a non-SEPA IBAN shouldn't
        self.sepa_qr_invoice.invoice_partner_bank_id = self.acc_non_sepa_iban
        with self.assertRaises(UserError, msg="It shouldn't be possible to generate a SEPA QR-code for IBAN of countries outside SEPA zone."):
            self.sepa_qr_invoice.generate_qr_code()

        # Changing the currency should break it as well
        self.sepa_qr_invoice.invoice_partner_bank_id = self.acc_sepa_iban
        self.sepa_qr_invoice.currency_id = self.env.ref('base.USD').id
        with self.assertRaises(UserError, msg="It shouldn't be possible to generate a SEPA QR-code for another currency as EUR."):
            self.sepa_qr_invoice.generate_qr_code()

    def test_sepa_qr_code_detection(self):
        """ Checks SEPA QR-code auto-detection when no specific QR-method
        is given to the invoice.
        """
        self.sepa_qr_invoice.generate_qr_code()
        self.assertEqual(self.sepa_qr_invoice.qr_code_method, 'sct_qr', "SEPA QR-code generator should have been chosen for this invoice.")

