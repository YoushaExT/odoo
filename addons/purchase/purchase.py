# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import api, fields, models, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _
from openerp.tools.float_utils import float_is_zero, float_compare
import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError

class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Purchase Order"
    _order = 'date_order desc, id desc'

    @api.depends('order_line.product_qty', 'order_line.price_unit', 'order_line.taxes_id')
    def _amount_all(self):
        amount_untaxed = amount_tax = 0.0
        for line in self.order_line:
            amount_untaxed += line.price_subtotal
            amount_tax += line.price_tax
        self.update({
            'amount_untaxed': self.currency_id.round(amount_untaxed),
            'amount_tax': self.currency_id.round(amount_tax),
            'amount_total': amount_untaxed + amount_tax,
        })

    @api.multi
    def _inverse_date_planned(self):
        for order in self:
            order.order_line.write({'date_planned': self.date_planned})

    @api.depends('order_line.date_planned')
    def _compute_date_planned(self):
        for order in self:
            min_date = False
            for line in order.order_line:
                if not min_date or line.date_planned < min_date:
                    min_date = line.date_planned
            if min_date:
                order.date_planned = min_date

    @api.depends('state', 'order_line.qty_invoiced', 'order_line.product_qty')
    def _get_invoiced(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state != 'purchase':
                order.invoice_status = 'no'
                continue

            if any(float_compare(line.qty_invoiced, line.product_qty, precision_digits=precision) == -1 for line in order.order_line):
                order.invoice_status = 'to invoice'
            elif all(float_compare(line.qty_invoiced, line.product_qty, precision_digits=precision) >= 0 for line in order.order_line):
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    @api.depends('order_line.invoice_lines.invoice_id.state')
    def _compute_invoice(self):
        for order in self:
            invoices = self.env['account.invoice']
            for line in order.order_line:
                invoices |= line.invoice_lines.mapped('invoice_id')
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
        if not types:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[0].id if types else False

    @api.depends('order_line.move_ids.picking_id')
    def _compute_picking(self):
        for order in self:
            pickings = self.env['stock.picking']
            for line in order.order_line:
                moves = line.move_ids.filtered(lambda r: r.state != 'cancel')
                pickings |= moves.mapped('picking_id')
            order.picking_ids = pickings
            order.picking_count = len(pickings)

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    name = fields.Char('Order Reference', required=True, select=True, copy=False, default='New')
    origin = fields.Char('Source Document', copy=False,\
        help="Reference of the document that generated this purchase order "
             "request (e.g. a sale order or an internal procurement request)")
    partner_ref = fields.Char('Vendor Reference', copy=False,\
        help="Reference of the sales order or bid sent by the vendor. "
             "It's used to do the matching when you receive the "
             "products as this reference is usually written on the "
             "delivery order sent by your vendor.")
    date_order = fields.Datetime('Order Date', required=True, states=READONLY_STATES, select=True, copy=False, default=fields.Date.context_today,\
        help="Depicts the date where the Quotation should be validated and converted into a purchase order.")
    date_approve = fields.Date('Approval Date', readonly=1, select=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, states=READONLY_STATES, change_default=True, track_visibility='always')
    dest_address_id = fields.Many2one('res.partner', string='Drop Ship Address', states=READONLY_STATES,\
        help="Put an address if you want to deliver directly from the vendor to the customer. "\
             "Otherwise, keep empty to deliver to your own company.")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, states=READONLY_STATES,\
        default=lambda self: self.env.user.company_id.currency_id.id)
    state = fields.Selection([
        ('draft', 'Draft RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, select=True, copy=False, default='draft')
    order_line = fields.One2many('purchase.order.line', 'order_id', string='Order Lines', states=READONLY_STATES, copy=True)
    notes = fields.Text('Terms and Conditions')

    invoice_count = fields.Integer(compute="_compute_invoice", string='# of Invoices', copy=False, default=0)
    invoice_ids = fields.Many2many('account.invoice', compute="_compute_invoice", string='Invoices', copy=False)
    invoice_status = fields.Selection([
        ('no', 'Not purchased'),
        ('to invoice', 'Waiting Invoices'),
        ('invoiced', 'Invoice Received'),
        ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True, copy=False, default='no')

    picking_count = fields.Integer(compute='_compute_picking', string='Receptions', default=0)
    picking_ids = fields.One2many('stock.picking', compute='_compute_picking', string='Receptions', copy=False)

    date_planned = fields.Datetime(string='Scheduled Date', compute='_compute_date_planned', inverse='_inverse_date_planned', required=True, select=True, oldname='minimum_planned_date')

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')

    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position')
    payment_term_id = fields.Many2one('account.payment.term', 'Payment Term')
    incoterm_id = fields.Many2one('stock.incoterms', 'Incoterm', help="International Commercial Terms are a series of predefined commercial terms used in international transactions.")

    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')
    create_uid = fields.Many2one('res.users', 'Responsible')
    company_id = fields.Many2one('res.company', 'Company', required=True, select=1, states=READONLY_STATES, default=lambda self: self.env.user.company_id.id)

    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', states=READONLY_STATES, required=True, default=_default_picking_type,\
        help="This will determine picking type of incoming shipment")
    group_id = fields.Many2one('procurement.group', string="Procurement Group")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order') or '/'
        return super(PurchaseOrder, self).create(vals)

    @api.multi
    def unlink(self):
        for order in self:
            if order.state not in ['draft', 'cancel']:
                raise UserError(_('In order to delete a purchase order, you must cancel it first.'))
        return super(PurchaseOrder, self).unlink()

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'approved':
            return 'purchase.mt_rfq_approved'
        elif 'state' in init_values and self.state == 'confirmed':
            return 'purchase.mt_rfq_confirmed'
        elif 'state' in init_values and self.state == 'done':
            return 'purchase.mt_rfq_done'
        return super(PurchaseOrder, self)._track_subtype(init_values)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.fiscal_position_id = False
            self.payment_term_id = False
            self.currency_id = False
        else:
            self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id)
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
            self.currency_id = self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id
        return {}

    @api.multi
    def action_rfq_send(self):
        '''
        This function opens a window to compose an email, with the edi purchase template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            if self.env.context.get('send_rfq', False):
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase')[1]
            else:
                template_id = ir_model_data.get_object_reference('purchase', 'email_template_edi_purchase_done')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'purchase.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        })
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def print_quotation(self):
        self.write({'state': "sent"})
        return self.env['report'].get_action(self, 'purchase.report_purchasequotation')

    @api.multi
    def button_approve(self):
        self.write({'state': 'purchase'})
        self._action_picking_create()
        return {}

    @api.multi
    def button_draft(self):
        self.write({'state': 'draft'})
        return {}

    @api.multi
    def button_confirm(self):
        return self.button_approve()

    @api.multi
    def button_cancel(self):
        for order in self:
            for pick in order.picking_ids:
                if pick.state == 'done':
                    raise UserError(_('Unable to cancel purchase order %s as some receptions have already been done.') % (order.name))
            for inv in order.invoice_ids:
                if inv and inv.state not in ('cancel', 'draft'):
                    raise UserError(_("Unable to cancel this purchase order.i You must first cancel related vendor bills."))

            if not self.env.context.get('cancel_procurement'):
                procurements = order.order_line.mapped('procurement_ids')
                procurements.filtered(lambda r: r.state not in ('cancel', 'exception') and r.rule_id.propagate).write({'state': 'cancel'})
                procurements.filtered(lambda r: r.state not in ('cancel', 'exception') and not r.rule_id.propagate).write({'state': 'exception'})
                moves = procurements.filtered(lambda r: r.rule_id.propagate).mapped('move_dest_id')
                moves.filtered(lambda r: r.state != 'cancel').action_cancel()

        self.write({'state': 'cancel'})

    @api.multi
    def button_done(self):
        self.write({'state': 'done'})

    @api.multi
    def _get_destination_location(self):
        self.ensure_one()
        if self.dest_address_id:
            return self.dest_address_id.property_stock_customer.id
        return self.picking_type_id.default_location_dest_id.id

    @api.model
    def _create_picking(self):
        if not self.group_id:
            self.group_id = self.group_id.create({
                'name': self.name,
                'partner_id': self.partner_id.id
            })
        return self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'date': self.date_order,
            'origin': self.name,
            'location_dest_id': self._get_destination_location(),
            'location_id': self.partner_id.property_stock_supplier.id
        })

    @api.multi
    def _action_picking_create(self):
        for order in self:
            ptypes = order.order_line.mapped('product_id.type')
            if ('product' in ptypes) or ('consu' in ptypes):
                picking = order._create_picking()
                moves = order.order_line._create_stock_moves(picking)
                moves.action_confirm()
                moves.force_assign()
        return True


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _description = 'Purchase Order Line'

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            taxes = line.taxes_id.compute_all(line.price_unit, line.order_id.currency_id, line.product_qty, product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('invoice_lines.invoice_id.state')
    def _compute_qty_invoiced(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                qty += inv_line.uom_id._compute_qty_obj(inv_line.uom_id, inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty

    @api.depends('move_ids.state')
    def _compute_qty_received(self):
        for line in self:
            if line.order_id.state not in ['purchase', 'done']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            total = 0.0
            for move in line.move_ids:
                if move.state == 'done':
                    total += move.product_qty
            line.qty_received = total

    name = fields.Text(string='Description', required=True)
    product_qty = fields.Float(string='Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True, default=0.0)
    date_planned = fields.Datetime(string='Scheduled Date', required=True, select=True)
    taxes_id = fields.Many2many('account.tax', string='Taxes')
    product_uom = fields.Many2one('product.uom', string='Product Unit of Measure', required=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)], change_default=True, required=True)
    move_ids = fields.One2many('stock.move', 'purchase_line_id', string='Reservation', readonly=True, ondelete='set null', copy=False)
    price_unit = fields.Float(string='Unit Price', required=True, digits_compute=dp.get_precision('Product Price'))

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Monetary(compute='_compute_amount', string='Tax', store=True)

    order_id = fields.Many2one('purchase.order', string='Order Reference', select=True, required=True, ondelete='cascade')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True, readonly=True)

    invoice_lines = fields.One2many('account.invoice.line', 'purchase_line_id', string="Invoice Lines", readonly=True, copy=False)

    # Replace by invoiced Qty
    qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty", store=True)
    qty_received = fields.Float(compute='_compute_qty_received', string="Received Qty", store=True)

    partner_id = fields.Many2one('res.partner', related='order_id.partner_id', string='Partner', readonly=True, store=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    date_order = fields.Datetime(related='order_id.date_order', string='Order Date', readonly=True)
    procurement_ids = fields.One2many('procurement.order', 'purchase_line_id', string='Associated Procurements', copy=False)

    @api.multi
    def _create_stock_moves(self, picking):
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            order = line.order_id
            price_unit = line.price_unit
            if line.product_uom.id != line.product_id.uom_id.id:
                price_unit *= line.product_uom.factor / line.product_id.uom_id.factor
            if order.currency_id != order.company_id.currency_id:
                price_unit = order.currency_id.compute(price_unit, order.company_id.currency_id, round=False)

            template = {
                'name': line.name or '',
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'date': line.order_id.date_order,
                'date_expected': line.date_planned,
                'location_id': line.order_id.partner_id.property_stock_supplier.id,
                'location_dest_id': line.order_id._get_destination_location(),
                'picking_id': picking.id,
                'partner_id': line.order_id.dest_address_id.id,
                'move_dest_id': False,
                'state': 'draft',
                'purchase_line_id': line.id,
                'company_id': line.order_id.company_id.id,
                'price_unit': price_unit,
                'picking_type_id': line.order_id.picking_type_id.id,
                'group_id': line.order_id.group_id.id,
                'procurement_id': False,
                'origin': line.order_id.name,
                'route_ids': line.order_id.picking_type_id.warehouse_id and [(6, 0, [x.id for x in line.order_id.picking_type_id.warehouse_id.route_ids])] or [],
                'warehouse_id':line.order_id.picking_type_id.warehouse_id.id,
            }

            # Fullfill all related procurements with this po line
            diff_quantity = line.product_qty
            for procurement in line.procurement_ids:
                procurement_qty = procurement.product_uom._compute_qty_obj(procurement.product_uom, procurement.product_qty, line.product_uom)
                tmp = template.copy()
                tmp.update({
                    'product_uom_qty': min(procurement_qty, diff_quantity),
                    'move_dest_id': procurement.move_dest_id.id,  #move destination is same as procurement destination
                    'procurement_id': procurement.id,
                    'propagate': procurement.rule_id.propagate,
                })
                done += moves.create(tmp)
                diff_quantity -= min(procurement_qty, diff_quantity)
            if float_compare(diff_quantity, 0.0, precision_rounding=line.product_uom.rounding) > 0:
                template['product_uom_qty'] = diff_quantity
                done += moves.create(template)
        return done

    @api.multi
    def unlink(self):
        for line in self:
            if line.order_id.state in ['approved', 'done']:
                raise UserError(_('Cannot delete a purchase order line which is in state \'%s\'.') %(line.state,))
            line.procurement_ids.message_post(body=_('Purchase order line deleted.'))
            line.procurement_ids.write({'state': 'exception'})
        return super(PurchaseOrderLine, self).unlink()

    @api.model
    def _get_date_planned(self, product, po=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.

           :param browse_record | False product: product.product, used to
               determine delivery delay thanks to the selected seller field (if False, default delay = 0)
           :param browse_record | False po: purchase.order, necessary only if
               the PO line is not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        supplier_delay = int(product.seller_delay) if product else 0
        if po:
            date_order = po.date_order
        else:
            date_order = self.order_id.date_order
        if date_order:
            return datetime.strptime(date_order, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=supplier_delay)
        else:
            return datetime.today() + relativedelta(days=supplier_delay)

    @api.onchange('product_id', 'product_qty', 'product_uom')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return {}

        if self.product_id.uom_id.category_id.id != self.product_uom.category_id.id:
            self.product_uom = self.product_id.uom_po_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        res = self._get_name_price_quantity_date(
            self.product_id,
            self.partner_id,
            datetime.strptime(self.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT) if self.order_id.date_order else datetime.today(),
            self.product_qty,
            self.product_uom,
            self.order_id.currency_id)

        self.name = res['name']
        self.product_qty = res['quantity'] if not res['quantity'] else max(self.product_qty, res['quantity'])
        self.price_unit = res['price_unit']
        self.date_planned = res['date_planned']

        taxes = self.product_id.supplier_taxes_id
        fpos = self.order_id.fiscal_position_id
        if fpos:
            self.taxes_id = fpos.map_tax(taxes)

        result['value'] = {
            'name': self.name,
            'product_uom': self.product_uom.id,
            'product_qty': self.product_qty,
            'date_planned': self.date_planned,
            'taxes_id': self.taxes_id.ids,
        }

        return result

    @api.model
    def _get_name_price_quantity_date(self, product_id, partner_id, date, quantity, product_uom, currency_id, order_id=False):
        """Return the name of the product, the seller quantity, the unit price and
           the date planned of a given product.

           :param browse_record product_id: product.product, for which we want to
                get the information
           :param str lang: language in which we want the product name
           :param browse_record partner_id: res.partner, supplier of the product
           :param str date: order date
           :param float quantity: quantity of product in product_uom UoM
           :param browse_record product_uom: product.uom, product_uom UoM in which is
                expressed the quantity
           :param browse_record currency_id: res.currency, currency in which we want the price
           :param browse_record | False order_id: purchase.order, purchase order in case we
                try to get the data for a PO line not yet attached to a PO.
           :rtype: dict
           :return: name, seller quantity, seller price, date planned
        """
        # Switch quantity in uom_id
        quantity_uom_id = quantity
        if quantity_uom_id and product_id.uom_id != product_uom:
            quantity_uom_id = product_uom._compute_qty_obj(product_uom, quantity_uom_id, product_id.uom_id)

        product = product_id.with_context({
            'lang': partner_id.lang,
            'partner_id': partner_id.id,
            'date': date,
            'quantity': quantity_uom_id,
        })

        # Switch quantity back in product_uom
        quantity = max(quantity_uom_id, product.seller_qty)
        if quantity and product_id.uom_id != product_uom:
            quantity = product_id.uom_id._compute_qty_obj(product_id.uom_id, quantity, product_uom)

        price_unit = product.seller_price
        if price_unit and partner_id.currency_id != currency_id:
            price_unit = partner_id.currency_id.compute(price_unit, currency_id)

        date_planned = self._get_date_planned(product, po=order_id).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        name = product.display_name
        if product.description_purchase:
            name += '\n' + product.description_purchase

        return {
            'name': name,
            'quantity': quantity,
            'price_unit': price_unit,
            'date_planned': date_planned,
        }


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'
    @api.model
    def _get_action(self):
        return [('buy', _('Buy'))] + super(ProcurementRule, self)._get_action()


class ProcurementOrder(models.Model):
    _inherit = 'procurement.order'

    purchase_line_id = fields.Many2one('purchase.order.line', string='Purchase Order Line')
    purchase_id = fields.Many2one(related='purchase_line_id.order_id', string='Purchase Order')

    @api.multi
    def propagate_cancels(self):
        result = super(ProcurementOrder, self).propagate_cancels()
        for procurement in self:
            if procurement.rule_id.action == 'buy' and procurement.purchase_line_id:
                if procurement.purchase_line_id.order_id.state not in ('draft', 'cancel', 'sent', 'to validate'):
                    raise UserError(
                        _('Can not cancel a procurement related to a purchase order. Please cancel the purchase order first.'))
            if procurement.purchase_line_id:
                price_unit = 0.0
                product_qty = 0.0
                others_procs = procurement.purchase_line_id.procurement_ids.filtered(lambda r: r != procurement)
                for other_proc in others_procs:
                    if other_proc.state not in ['cancel', 'draft']:
                        product_qty += other_proc.product_uom._compute_qty_obj(other_proc.product_uom, other_proc.product_qty, procurement.purchase_line_id.product_uom)

                precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
                if not float_is_zero(product_qty, precision_digits=precision):
                    res = self.env['purchase.order.line']._get_name_price_quantity_date(
                        procurement.product_id,
                        procurement.purchase_line_id.partner_id,
                        datetime.strptime(procurement.purchase_line_id.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT),
                        product_qty,
                        procurement.product_uom,
                        procurement.purchase_line_id.order_id.currency_id)

                    product_qty = res['quantity']
                    price_unit = res['price_unit']

                procurement.purchase_line_id.product_qty = product_qty
                procurement.purchase_line_id.price_unit = price_unit

        return result

    @api.model
    def _run(self, procurement):
        if procurement.rule_id and procurement.rule_id.action == 'buy':
            return procurement.make_po()
        return super(ProcurementOrder, self)._run(procurement)

    @api.model
    def _check(self, procurement):
        if procurement.purchase_line_id:
            if not procurement.move_ids:
                return False
            return all(move.state == 'done' for move in procurement.move_ids)
        return super(ProcurementOrder, self)._check(procurement)

    @api.v8
    def _get_purchase_schedule_date(self):
        procurement_date_planned = datetime.strptime(self.date_planned, DEFAULT_SERVER_DATETIME_FORMAT)
        schedule_date = (procurement_date_planned - relativedelta(days=self.company_id.po_lead))
        return schedule_date

    @api.v7
    def _get_purchase_schedule_date(self, procurement):
        """Return the datetime value to use as Schedule Date (``date_planned``) for the
           Purchase Order Lines created to satisfy the given procurement.

           :param browse_record procurement: the procurement for which a PO will be created.
           :rtype: datetime
           :return: the desired Schedule Date for the PO lines
        """
        procurement_date_planned = datetime.strptime(procurement.date_planned, DEFAULT_SERVER_DATETIME_FORMAT)
        schedule_date = (procurement_date_planned - relativedelta(days=procurement.company_id.po_lead))
        return schedule_date

    @api.v8
    def _get_purchase_order_date(self, schedule_date):
        self.ensure_one()
        seller_delay = int(self.product_id.seller_delay)
        return schedule_date - relativedelta(days=seller_delay)

    @api.v7
    def _get_purchase_order_date(self, cr, uid, procurement, company, schedule_date, context=None):
        """Return the datetime value to use as Order Date (``date_order``) for the
           Purchase Order created to satisfy the given procurement.

           :param browse_record procurement: the procurement for which a PO will be created.
           :param browse_report company: the company to which the new PO will belong to.
           :param datetime schedule_date: desired Scheduled Date for the Purchase Order lines.
           :rtype: datetime
           :return: the desired Order Date for the PO
        """
        seller_delay = int(procurement.product_id.seller_delay)
        return schedule_date - relativedelta(days=seller_delay)

    @api.multi
    def _prepare_purchase_order_line(self, po, supplier):
        self.ensure_one()

        res = self.env['purchase.order.line']._get_name_price_quantity_date(
            self.product_id,
            supplier.name,
            datetime.strptime(po.date_order, DEFAULT_SERVER_DATETIME_FORMAT),
            self.product_qty,
            self.product_uom,
            po.currency_id,
            order_id=po)

        name = res['name']
        product_qty = res['quantity']
        price_unit = res['price_unit']
        date_planned = res['date_planned']

        taxes = self.product_id.supplier_taxes_id
        fpos = po.fiscal_position_id
        taxes_id = fpos.map_tax(taxes) if fpos else []

        return {
            'name': name,
            'product_qty': product_qty,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom.id,
            'price_unit': price_unit,
            'date_planned': date_planned,
            'taxes_id': [(6, 0, taxes_id)],
            'procurement_ids': [(4, self.id)],
            'order_id': po.id,
        }

    @api.multi
    def _prepare_purchase_order(self, partner):
        self.ensure_one()
        schedule_date = self._get_purchase_schedule_date()
        purchase_date = self._get_purchase_order_date(schedule_date)
        fpos = self.env['account.fiscal.position'].get_fiscal_position(partner.id)

        gpo = self.rule_id.group_propagation_option
        group = (gpo == 'fixed' and self.rule_id.group_id.id) or \
                (gpo == 'propagate' and self.group_id.id) or False

        return {
            'partner_id': partner.id,
            'picking_type_id': self.rule_id.picking_type_id.id,
            'company_id': self.company_id.id,
            'dest_address_id': self.partner_dest_id.id,
            'origin': self.origin,
            'payment_term_id': partner.property_supplier_payment_term_id.id,
            'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'fiscal_position_id': fpos,
            'group_id': group
        }

    @api.multi
    def make_po(self):
        cache = {}
        res = []
        for procurement in self:
            if not procurement.product_id.seller_ids:
                self.message_post([procurement.id],\
                    _('No vendor associated to product %s. Please set one to fix this procurement.') % (procurement.product_id.name))
                continue
            supplier = procurement.product_id.seller_ids[0]
            partner = supplier.name
            domain = (
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft'),
                ('picking_type_id', '=', procurement.rule_id.picking_type_id.id),
                ('company_id', '=', procurement.company_id.id),
                ('dest_address_id', '=', procurement.partner_dest_id.id))

            if domain in cache:
                po = cache[domain]
            else:
                po = self.env['purchase.order'].search([dom for dom in domain])
                po = po[0] if po else False
                cache[domain] = po
            if not po:
                vals = procurement._prepare_purchase_order(partner)
                po = self.env['purchase.order'].create(vals)
                cache[domain] = po
            res += po.ids

            # Create Line
            po_line = False
            for line in po.order_line:
                if line.product_id == procurement.product_id and line.product_uom == procurement.product_uom:
                    res = self.env['purchase.order.line']._get_name_price_quantity_date(
                        self.product_id,
                        partner,
                        datetime.strptime(po.date_order, DEFAULT_SERVER_DATETIME_FORMAT),
                        line.product_qty + procurement.product_qty,
                        self.product_uom,
                        po.currency_id)

                    po_line = line.write({
                        'product_qty': res['quantity'],
                        'price_unit': res['price_unit'],
                        'procurement_ids': [(4, procurement.id)]
                    })
            if not po_line:
                vals = procurement._prepare_purchase_order_line(po, supplier)
                self.env['purchase.order.line'].create(vals)
        return res


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    @api.model
    def _get_buy_route(self):
        buy_route = self.env.ref('purchase.route_warehouse0_buy')
        if buy_route:
            return buy_route.ids
        return []

    @api.multi
    def _purchase_count(self):
        for template in self:
            template.purchase_count = sum([p.purchase_count for p in template.product_variant_ids])
        return True

    property_account_creditor_price_difference = fields.Many2one('account.account', string="Price Difference Account",\
        help="This account will be used to value price difference between purchase price and cost price.")
    purchase_ok = fields.Boolean('Can be Purchased', default=True)
    purchase_count = fields.Integer(compute='_purchase_count', string='# Purchases')
    purchase_method = fields.Selection([
        ('purchase', 'On purchased quantities'),
        ('receive', 'On received quantities'),
        ], string="Control Purchase Bills", default="receive")
    route_ids = fields.Many2many(default=lambda self: self._get_buy_route())


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = 'product.product'

    @api.multi
    def _purchase_count(self):
        domain = [
            ('state', 'in', ['confirmed', 'approved', 'done']),
            ('product_id', 'in', self.mapped('id')),
        ]
        r = {}
        for group in self.env['purchase.report'].read_group(domain, ['product_id', 'quantity'], ['product_id']):
            r[group['product_id'][0]] = group['quantity']
        for product in self:
            product.purchase_count = r.get(product.id, 0)
        return True

    purchase_count = fields.Integer(compute='_purchase_count', string='# Purchases')

class ProductCategory(models.Model):
    _inherit = "product.category"

    property_account_creditor_price_difference_categ = fields.Many2one(
        'account.account', string="Price Difference Account",
        company_dependent=True,
        help="This account will be used to value price difference between purchase price and accounting cost.")


class MailComposeMessage(models.Model):
    _inherit = 'mail.compose.message'

    @api.multi
    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'purchase.order' and self._context.get('default_res_id'):
            order = self.env['purchase.order'].browse([self._context['default_res_id']])
            if order.state == 'draft':
                order.state = 'sent'
        return super(MailComposeMessage, self.with_context(mail_post_autofollow=True)).send_mail()
