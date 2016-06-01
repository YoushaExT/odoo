# -*- coding: utf-8 -*-

import odoo
from odoo import fields
from odoo.addons.payment.tests.common import PaymentAcquirerCommon
from odoo.tools import mute_logger


@odoo.tests.common.at_install(True)
@odoo.tests.common.post_install(True)
class StripeCommon(PaymentAcquirerCommon):

    def setUp(self):
        super(StripeCommon, self).setUp()
        self.currency_euro = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)
        # get the stripe account
        self.stripe_id = self.env.ref('payment.payment_acquirer_stripe').id


@odoo.tests.common.at_install(True)
@odoo.tests.common.post_install(True)
class StripeTest(StripeCommon):

    def test_10_stripe_s2s(self):
        stripe = self.env['payment.acquirer'].browse(self.stripe_id)
        self.assertEqual(stripe.environment, 'test', 'test without test environment')

        # Add Stripe credentials
        stripe.write({
            'stripe_secret_key': 'sk_test_bldAlqh1U24L5HtRF9mBFpK7',
            'stripe_publishable_key': 'pk_test_0TKSyYSZS9AcS4keZ2cxQQCW',
        })

        # Create payment meethod for Stripe
        payment_token = self.env['payment.token'].create({
            'acquirer_id': self.stripe_id,
            'partner_id': self.buyer_id,
            'cc_number': '4242424242424242',
            'cc_expiry': '02 / 26',
            'cc_brand': 'visa',
            'cvc': '111',
            'cc_holder_name': 'Johndoe',
        })

        # Create transaction
        tx = self.env['payment.transaction'].create({
            'reference': 'test_ref_%s' % fields.date.today(),
            'currency_id': self.currency_euro.id,
            'acquirer_id': self.stripe_id,
            'partner_id': self.buyer_id,
            'payment_token_id': payment_token.id,
            'type': 'server2server',
            'amount': 115.0
        })
        tx.stripe_s2s_do_transaction()

        # Check state
        self.assertEqual(tx.state, 'done', 'Stripe: Transcation has been discarded.')

    def test_20_stripe_form_render(self):
        stripe = self.env['payment.acquirer'].browse(self.stripe_id)
        self.assertEqual(stripe.environment, 'test', 'test without test environment')

        # ----------------------------------------
        # Test: button direct rendering
        # ----------------------------------------
        form_values = {
            'amount': 320.0,
            'currency': 'EUR',
            'address_line1': 'Huge Street 2/543',
            'address_city': 'Sin City',
            'address_country': 'Belgium',
            'email': 'norbert.buyer@example.com',
            'address_zip': '1000',
            'name': 'Norbert Buyer',
            'phone': '0032 12 34 56 78'
        }

        # render the button
        res = stripe.render('SO404', 320.0, self.currency_euro.id, values=self.buyer_values)
        post_url = "https://checkout.stripe.com/checkout.js"
        email = "norbert.buyer@example.com"
        # check form result
        if "https://checkout.stripe.com/checkout.js" in res[0]:
            self.assertEqual(post_url, 'https://checkout.stripe.com/checkout.js', 'Stripe: wrong form POST url')
        # Generated and received
        if email in res[0]:
            self.assertEqual(
                email, form_values.get('email'),
                'Stripe: wrong value for input %s: received %s instead of %s' % (email, email, form_values.get('email'))
            )

    def test_30_stripe_form_management(self):
        stripe = self.env['payment.acquirer'].browse(self.stripe_id)
        self.assertEqual(stripe.environment, 'test', 'test without test environment')

        # typical data posted by Stripe after client has successfully paid
        stripe_post_data = {
            u'amount': 4700,
            u'amount_refunded': 0,
            u'application_fee': None,
            u'balance_transaction': u'txn_172xfnGMfVJxozLwssrsQZyT',
            u'captured': True,
            u'created': 1446529775,
            u'currency': u'eur',
            u'customer': None,
            u'description': None,
            u'destination': None,
            u'dispute': None,
            u'failure_code': None,
            u'failure_message': None,
            u'fraud_details': {},
            u'id': u'ch_172xfnGMfVJxozLwEjSfpfxD',
            u'invoice': None,
            u'livemode': False,
            u'metadata': {u'reference': u'SO100'},
            u'object': u'charge',
            u'paid': True,
            u'receipt_email': None,
            u'receipt_number': None,
            u'refunded': False,
            u'refunds': {u'data': [],
                         u'has_more': False,
                         u'object': u'list',
                         u'total_count': 0,
                         u'url': u'/v1/charges/ch_172xfnGMfVJxozLwEjSfpfxD/refunds'},
            u'shipping': None,
            u'source': {u'address_city': None,
                        u'address_country': None,
                        u'address_line1': None,
                        u'address_line1_check': None,
                        u'address_line2': None,
                        u'address_state': None,
                        u'address_zip': None,
                        u'address_zip_check': None,
                        u'brand': u'Visa',
                        u'country': u'US',
                        u'customer': None,
                        u'cvc_check': u'pass',
                        u'dynamic_last4': None,
                        u'exp_month': 2,
                        u'exp_year': 2022,
                        u'fingerprint': u'9tJA9bUEuvEb3Ell',
                        u'funding': u'credit',
                        u'id': u'card_172xfjGMfVJxozLw1QO6gYNM',
                        u'last4': u'4242',
                        u'metadata': {},
                        u'name': u'norbert.buyer@example.com',
                        u'object': u'card',
                        u'tokenization_method': None},
            u'statement_descriptor': None,
            u'status': u'succeeded'}

        tx = self.env['payment.transaction'].create({
            'amount': 4700,
            'acquirer_id': self.stripe_id,
            'currency_id': self.currency_euro.id,
            'reference': 'SO100',
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france_id})

        # validate it
        tx.form_feedback(stripe_post_data, 'stripe')
        self.assertEqual(tx.state, 'done', 'Stripe: validation did not put tx into done state')
        self.assertEqual(tx.acquirer_reference, stripe_post_data.get('id'), 'Stripe: validation did not update tx id')
        # reset tx
        tx.write({'state': 'draft', 'date_validate': False, 'acquirer_reference': False})
        # simulate an error
        stripe_post_data['status'] = 'error'
        stripe_post_data.update({u'error': {u'message': u"Your card's expiration year is invalid.", u'code': u'invalid_expiry_year', u'type': u'card_error', u'param': u'exp_year'}})
        with mute_logger('openerp.addons.payment_stripe.models.payment_transaction'):
            tx.form_feedback(stripe_post_data, 'stripe')
        # check state
        self.assertEqual(tx.state, 'error', 'Stipe: erroneous validation did not put tx into error state')
