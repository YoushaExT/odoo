# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning
from dateutil.relativedelta import relativedelta
from lxml import etree
import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = 'account.move'

    @api.model
    def _l10n_ar_get_document_number_parts(self, document_number, document_type_code):
        # import shipments
        if document_type_code in ['66', '67']:
            pos = invoice_number = '0'
        else:
            pos, invoice_number = document_number.split('-')
        return {'invoice_number': int(invoice_number), 'point_of_sale': int(pos)}

    l10n_ar_afip_responsibility_type_id = fields.Many2one(
        'l10n_ar.afip.responsibility.type', string='AFIP Responsibility Type', help='Defined by AFIP to'
        ' identify the type of responsibilities that a person or a legal entity could have and that impacts in the'
        ' type of operations and requirements they need.')

    l10n_ar_currency_rate = fields.Float(copy=False, digits=(16, 4), readonly=True, string="Currency Rate")

    # Mostly used on reports
    l10n_ar_afip_concept = fields.Selection(
        compute='_compute_l10n_ar_afip_concept', selection='_get_afip_invoice_concepts', string="AFIP Concept",
        help="A concept is suggested regarding the type of the products on the invoice but it is allowed to force a"
        " different type if required.")
    l10n_ar_afip_service_start = fields.Date(string='AFIP Service Start Date', readonly=True, states={'draft': [('readonly', False)]})
    l10n_ar_afip_service_end = fields.Date(string='AFIP Service End Date', readonly=True, states={'draft': [('readonly', False)]})

    def _get_afip_invoice_concepts(self):
        """ Return the list of values of the selection field. """
        return [('1', 'Products / Definitive export of goods'), ('2', 'Services'), ('3', 'Products and Services'),
                ('4', '4-Other (export)')]

    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id', 'invoice_line_ids.product_id.type', 'journal_id')
    def _compute_l10n_ar_afip_concept(self):
        recs_afip = self.filtered(lambda x: x.company_id.country_id == self.env.ref('base.ar') and x.l10n_latam_use_documents)
        for rec in recs_afip:
            rec.l10n_ar_afip_concept = rec._get_concept()
        remaining = self - recs_afip
        remaining.l10n_ar_afip_concept = ''

    def _get_concept(self):
        """ Method to get the concept of the invoice considering the type of the products on the invoice """
        self.ensure_one()
        invoice_lines = self.invoice_line_ids.filtered(lambda x: not x.display_type)
        product_types = set([x.product_id.type for x in invoice_lines if x.product_id])
        consumable = set(['consu', 'product'])
        service = set(['service'])
        mixed = set(['consu', 'service', 'product'])
        # on expo invoice you can mix services and products
        expo_invoice = self.l10n_latam_document_type_id.code in ['19', '20', '21']

        # Default value "product"
        afip_concept = '1'
        if product_types == service:
            afip_concept = '2'
        elif product_types - consumable and product_types - service and not expo_invoice:
            afip_concept = '3'
        return afip_concept

    def _get_l10n_latam_documents_domain(self):
        self.ensure_one()
        domain = super()._get_l10n_latam_documents_domain()
        if self.journal_id.company_id.country_id == self.env.ref('base.ar'):
            letters = self.journal_id._get_journal_letter(counterpart_partner=self.partner_id.commercial_partner_id)
            domain += ['|', ('l10n_ar_letter', '=', False), ('l10n_ar_letter', 'in', letters)]
            codes = self.journal_id._get_journal_codes()
            if codes:
                domain.append(('code', 'in', codes))
            if self.move_type == 'in_refund':
                domain = ['|', ('code', 'in', ['99'])] + domain
        return domain

    def _check_argentinian_invoice_taxes(self):

        # check vat on companies thats has it (Responsable inscripto)
        for inv in self.filtered(lambda x: x.company_id.l10n_ar_company_requires_vat):
            purchase_aliquots = 'not_zero'
            # we require a single vat on each invoice line except from some purchase documents
            if inv.move_type in ['in_invoice', 'in_refund'] and inv.l10n_latam_document_type_id.purchase_aliquots == 'zero':
                purchase_aliquots = 'zero'
            for line in inv.mapped('invoice_line_ids').filtered(lambda x: x.display_type not in ('line_section', 'line_note')):
                vat_taxes = line.tax_ids.filtered(lambda x: x.tax_group_id.l10n_ar_vat_afip_code)
                if len(vat_taxes) != 1:
                    raise UserError(_('There must be one and only one VAT tax per line. Check line "%s"') % line.name)
                elif purchase_aliquots == 'zero' and vat_taxes.tax_group_id.l10n_ar_vat_afip_code != '0':
                    raise UserError(_('On invoice id "%s" you must use VAT Not Applicable on every line.')  % inv.id)
                elif purchase_aliquots == 'not_zero' and vat_taxes.tax_group_id.l10n_ar_vat_afip_code == '0':
                    raise UserError(_('On invoice id "%s" you must use VAT taxes different than VAT Not Applicable.')  % inv.id)

    def _set_afip_service_dates(self):
        for rec in self.filtered(lambda m: m.invoice_date and m.l10n_ar_afip_concept in ['2', '3', '4']):
            if not rec.l10n_ar_afip_service_start:
                rec.l10n_ar_afip_service_start = rec.invoice_date + relativedelta(day=1)
            if not rec.l10n_ar_afip_service_end:
                rec.l10n_ar_afip_service_end = rec.invoice_date + relativedelta(day=1, days=-1, months=+1)

    @api.onchange('partner_id')
    def _onchange_afip_responsibility(self):
        if self.company_id.country_id == self.env.ref('base.ar') and self.l10n_latam_use_documents and self.partner_id \
           and not self.partner_id.l10n_ar_afip_responsibility_type_id:
            return {'warning': {
                'title': _('Missing Partner Configuration'),
                'message': _('Please configure the AFIP Responsibility for "%s" in order to continue') % (
                    self.partner_id.name)}}

    @api.onchange('partner_id')
    def _onchange_partner_journal(self):
        """ This method is used when the invoice is created from the sale or subscription """
        expo_journals = ['FEERCEL', 'FEEWS', 'FEERCELP']
        for rec in self.filtered(lambda x: x.company_id.country_id == self.env.ref('base.ar') and x.journal_id.type == 'sale'
                                 and x.l10n_latam_use_documents and x.partner_id.l10n_ar_afip_responsibility_type_id):
            res_code = rec.partner_id.l10n_ar_afip_responsibility_type_id.code
            domain = [('company_id', '=', rec.company_id.id), ('l10n_latam_use_documents', '=', True), ('type', '=', 'sale')]
            journal = self.env['account.journal']
            partner_type = journal_type = False
            if res_code in ['9', '10'] and rec.journal_id.l10n_ar_afip_pos_system not in expo_journals:
                # if partner is foregin and journal is not of expo, we try to change to expo journal
                journal = journal.search(domain + [('l10n_ar_afip_pos_system', 'in', expo_journals)], limit=1)
                partner_type, journal_type = (_('foreign partner'), _('exportation'))
            elif res_code not in ['9', '10'] and rec.journal_id.l10n_ar_afip_pos_system in expo_journals:
                # if partner is NOT foregin and journal is for expo, we try to change to local journal
                journal = journal.search(domain + [('l10n_ar_afip_pos_system', 'not in', expo_journals)], limit=1)
                partner_type, journal_type = (_('domestic partner'), _('domestic market'))
            if journal:
                rec.journal_id = journal.id
            elif partner_type and journal_type:
                # Throw an error to user in order to proper configure the journal for the type of operation
                action = self.env.ref('account.action_account_journal_form')
                msg = _('You are trying to create an invoice for %s but you dont have an %s journal') % (
                    partner_type, journal_type)
                raise RedirectWarning(msg, action.id, _('Go to Journals'))

    def post(self):
        ar_invoices = self.filtered(lambda x: x.company_id.country_id == self.env.ref('base.ar') and x.l10n_latam_use_documents)
        for rec in ar_invoices:
            rec.l10n_ar_afip_responsibility_type_id = rec.commercial_partner_id.l10n_ar_afip_responsibility_type_id.id
            if rec.company_id.currency_id == rec.currency_id:
                l10n_ar_currency_rate = 1.0
            else:
                l10n_ar_currency_rate = rec.currency_id._convert(
                    1.0, rec.company_id.currency_id, rec.company_id, rec.invoice_date or fields.Date.today(), round=False)
            rec.l10n_ar_currency_rate = l10n_ar_currency_rate

        # We make validations here and not with a constraint because we want validation before sending electronic
        # data on l10n_ar_edi
        ar_invoices._check_argentinian_invoice_taxes()
        res = super().post()
        self._set_afip_service_dates()
        return res

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if not default_values_list:
            default_values_list = [{} for move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.update({
                'l10n_ar_afip_service_start': move.l10n_ar_afip_service_start,
                'l10n_ar_afip_service_end': move.l10n_ar_afip_service_end,
            })
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    @api.onchange('l10n_latam_document_type_id', 'l10n_latam_document_number')
    def _inverse_l10n_latam_document_number(self):
        super()._inverse_l10n_latam_document_number()

        # Avoid that user change the POS number (x.l10n_latam_document_number), Rhe POS number configure in journal it
        # will always be used
        to_review = self.filtered(
            lambda x: x.journal_id.type == 'sale' and x.l10n_latam_document_type_id and x.l10n_latam_document_number and
            (x.l10n_latam_manual_document_number or not x.highest_name))
        for rec in to_review:
            number = rec.l10n_latam_document_type_id._format_document_number(rec.l10n_latam_document_number)
            current_pos = int(number.split("-")[0])
            if current_pos != rec.journal_id.l10n_ar_afip_pos_number:
                raise UserError(_('Can not change the POS number, you can only change the first number for document'
                                  ' type that you are creating in odoo'))

    def _get_formatted_sequence(self, number=0):
        return "%s %05d-%08d" % (self.l10n_latam_document_type_id.doc_code_prefix,
                                 self.journal_id.l10n_ar_afip_pos_number, number)

    def _get_starting_sequence(self):
        """ If use documents then will create a new starting sequence using the document type code prefix and the
        journal document number with a 8 padding number """
        if self.journal_id.l10n_latam_use_documents and self.env.company.country_id == self.env.ref('base.ar'):
            if self.l10n_latam_document_type_id:
                return self._get_formatted_sequence()
        return super()._get_starting_sequence()

    def _get_last_sequence_domain(self, relaxed=False):
        where_string, param = super(AccountMove, self)._get_last_sequence_domain(relaxed)
        if self.company_id.country_id == self.env.ref('base.ar') and self.l10n_latam_use_documents:
            if not self.journal_id.l10n_ar_share_sequences:
                where_string += " AND l10n_latam_document_type_id = %(l10n_latam_document_type_id)s"
                param['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id or 0
            elif self.journal_id.l10n_ar_share_sequences:
                where_string += " AND l10n_latam_document_type_id in %(l10n_latam_document_type_ids)s"
                param['l10n_latam_document_type_ids'] = tuple(self.l10n_latam_document_type_id.search(
                    [('l10n_ar_letter', '=', self.l10n_latam_document_type_id.l10n_ar_letter)]).ids)
        return where_string, param
