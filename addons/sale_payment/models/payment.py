# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo import api, fields, models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # link with the sales order
    # YTI FIXME: The auto_join seems useless
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', auto_join=True)

    # --------------------------------------------------
    # Sale management
    # --------------------------------------------------

    @api.model
    def form_feedback(self, data, acquirer_name):
        """ Override to confirm the sales order, if defined, and if the transaction
        is done. """
        tx = None
        res = super(PaymentTransaction, self).form_feedback(data, acquirer_name)

        # fetch the tx
        tx_find_method_name = '_%s_form_get_tx_from_data' % acquirer_name
        if hasattr(self, tx_find_method_name):
            tx = getattr(self, tx_find_method_name)(data)
        _logger.info('<%s> transaction processed: tx ref:%s, tx amount: %s', acquirer_name, tx.reference if tx else 'n/a', tx.amount if tx else 'n/a')

        if tx:
            # Auto-confirm SO if necessary
            tx._confirm_so()

        return res

    def _confirm_so(self):
        for tx in self:
            # check tx state, confirm the potential SO
            if not tx.sale_order_id or tx.sale_order_id.state not in ['draft', 'sent']:
                # _logger.warning('<%s> transaction incorrect sale order %s (ID %s, state %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id, tx.sale_order_id.state)
                continue
            if not float_compare(tx.amount, tx.sale_order_id.amount_total, 2) == 0:
                _logger.warning('<%s> transaction MISMATCH for order %s (ID %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id)
                continue
            try:
                if tx.state == 'authorized' and tx.acquirer_id.capture_manually:
                    _logger.info('<%s> transaction authorized, auto-confirming order %s (ID %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id)
                    tx.sale_order_id.with_context(send_email=True).action_confirm()

                if tx.state == 'done':
                    _logger.info('<%s> transaction completed, auto-confirming order %s (ID %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id)
                    tx.sale_order_id.with_context(send_email=True).action_confirm()
                    tx._generate_and_pay_invoice()
                elif tx.state not in ['cancel', 'error'] and tx.sale_order_id.state == 'draft':
                    _logger.info('<%s> transaction pending/to confirm manually, sending quote email for order %s (ID %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id)
                    tx.sale_order_id.force_quotation_send()
                else:
                    _logger.warning('<%s> transaction MISMATCH for order %s (ID %s)', tx.acquirer_id.provider, tx.sale_order_id.name, tx.sale_order_id.id)
            except Exception:
                _logger.exception('Fail to confirm the order or send the confirmation email%s', tx and ' for the transaction %s' % tx.reference or '')

    def _generate_and_pay_invoice(self):
        self.sale_order_id._force_lines_to_invoice_policy_order()

        # force company to ensure journals/accounts etc. are correct
        # company_id needed for default_get on account.journal
        # force_company needed for company_dependent fields
        ctx_company = {'company_id': self.sale_order_id.company_id.id,
                       'force_company': self.sale_order_id.company_id.id}
        created_invoice = self.sale_order_id.with_context(**ctx_company).action_invoice_create()
        created_invoice = self.env['account.invoice'].browse(created_invoice).with_context(**ctx_company)

        if created_invoice:
            _logger.info('<%s> transaction completed, auto-generated invoice %s (ID %s) for %s (ID %s)',
                         self.acquirer_id.provider, created_invoice.name, created_invoice.id, self.sale_order_id.name, self.sale_order_id.id)

            created_invoice.action_invoice_open()
            if not self.acquirer_id.journal_id:
                default_journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
                if not default_journal:
                    _logger.warning('<%s> transaction completed, could not auto-generate payment for %s (ID %s) (no journal set on acquirer)',
                                    self.acquirer_id.provider, self.sale_order_id.name, self.sale_order_id.id)
                self.acquirer_id.journal_id = default_journal
                created_invoice.pay_and_reconcile(self.acquirer_id.journal_id, pay_amount=created_invoice.amount_total)
                if created_invoice.payment_ids:
                    created_invoice.payment_ids[0].payment_transaction_id = self
        else:
            _logger.warning('<%s> transaction completed, could not auto-generate invoice for %s (ID %s)',
                            self.acquirer_id.provider, self.sale_order_id.name, self.sale_order_id.id)
