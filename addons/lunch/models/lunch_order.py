# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict

import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons import decimal_precision as dp


class LunchOrder(models.Model):
    """
    A lunch order contains one or more lunch order line(s). It is associated to a user for a given
    date. When creating a lunch order, applicable lunch alerts are displayed.
    """
    _name = 'lunch.order'
    _description = 'Lunch Order'
    _order = 'date desc'

    def _default_previous_order_ids(self):
        prev_order = self.env['lunch.order.line'].search([('user_id', '=', self.env.uid), ('product_id.active', '!=', False)], limit=20, order='id desc')
        # If we return return prev_order.ids, we will have duplicates (identical orders).
        # Therefore, this following part removes duplicates based on product_id and note.
        return list({
            (order.product_id, order.note): order.id
            for order in prev_order
        }.values())

    user_id = fields.Many2one('res.users', 'User', readonly=True,
                              states={'new': [('readonly', False)]},
                              default=lambda self: self.env.uid)
    date = fields.Date('Date', required=True, readonly=True,
                       states={'new': [('readonly', False)]},
                       default=fields.Date.context_today)
    order_line_ids = fields.One2many('lunch.order.line', 'order_id', 'Products',
                                     readonly=True, copy=True,
                                     states={'new': [('readonly', False)], False: [('readonly', False)]})
    total = fields.Float(compute='_compute_total', string="Total", store=True)
    state = fields.Selection([('new', 'New'),
                              ('confirmed', 'Received'),
                              ('cancelled', 'Cancelled')],
                             'Status', readonly=True, index=True, copy=False,
                             compute='_compute_order_state', store=True)
    alerts = fields.Text(compute='_compute_alerts_get', string="Alerts")
    company_id = fields.Many2one('res.company', related='user_id.company_id', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    cash_move_balance = fields.Monetary(compute='_compute_cash_move_balance', multi='cash_move_balance')
    balance_visible = fields.Boolean(compute='_compute_cash_move_balance', multi='cash_move_balance')
    previous_order_ids = fields.Many2many('lunch.order.line', compute='_compute_previous_order')
    previous_order_widget = fields.Text(compute='_compute_previous_order')

    @api.one
    @api.depends('order_line_ids')
    def _compute_total(self):
        """
        get and sum the order lines' price
        """
        self.total = sum(
            orderline.price for orderline in self.order_line_ids)

    @api.multi
    def name_get(self):
        return [(order.id, '%s %s' % (_('Lunch Order'), '#%d' % order.id)) for order in self]

    @api.depends('state')
    def _compute_alerts_get(self):
        """
        get the alerts to display on the order form
        """
        alert_msg = [alert.message
                     for alert in self.env['lunch.alert'].search([])
                     if alert.display]

        if self.state == 'new':
            self.alerts = alert_msg and '\n'.join(alert_msg) or False

    @api.multi
    @api.depends('user_id', 'state')
    def _compute_previous_order(self):
        self.ensure_one()
        self.previous_order_widget = json.dumps(False)

        prev_order = self.env['lunch.order.line'].search([('user_id', '=', self.env.uid), ('product_id.active', '!=', False)], limit=20, order='date desc, id desc')
        # If we use prev_order.ids, we will have duplicates (identical orders).
        # Therefore, this following part removes duplicates based on product_id and note.
        self.previous_order_ids = list({
            (order.product_id, order.note): order.id
            for order in prev_order
        }.values())

        if self.previous_order_ids:
            lunch_data = {}
            for line in self.previous_order_ids:
                lunch_data[line.id] = {
                    'line_id': line.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.name,
                    'supplier': line.supplier.name,
                    'note': line.note,
                    'price': line.price,
                    'date': fields.Date.to_string(line.date),
                    'currency_id': line.currency_id.id,
                }
            # sort the old lunch orders by (date, id)
            lunch_data = OrderedDict(sorted(lunch_data.items(), key=lambda t: (t[1]['date'], t[0]), reverse=True))
            self.previous_order_widget = json.dumps(lunch_data)

    @api.one
    @api.depends('user_id')
    def _compute_cash_move_balance(self):
        domain = [('user_id', '=', self.user_id.id)]
        lunch_cash = self.env['lunch.cashmove'].read_group(domain, ['amount', 'user_id'], ['user_id'])
        if len(lunch_cash):
            self.cash_move_balance = lunch_cash[0]['amount']
        self.balance_visible = (self.user_id == self.env.user) or self.user_has_groups('lunch.group_lunch_manager')

    @api.one
    @api.constrains('date')
    def _check_date(self):
        """
        Prevents the user to create an order in the past
        """
        date_order = self.date
        date_today = fields.Date.context_today(self)
        if date_order < date_today:
            raise ValidationError(_('The date of your order is in the past.'))

    @api.one
    @api.depends('order_line_ids.state')
    def _compute_order_state(self):
        """
        Update the state of lunch.order based on its orderlines. Here is the logic:
        - if at least one order line is cancelled, the order is set as cancelled
        - if no line is cancelled but at least one line is not confirmed, the order is set as new
        - if all lines are confirmed, the order is set as confirmed
        """
        if not self.order_line_ids:
            self.state = 'new'
        else:
            isConfirmed = True
            for orderline in self.order_line_ids:
                if orderline.state == 'cancelled':
                    self.state = 'cancelled'
                    return
                elif orderline.state == 'confirmed':
                    continue
                else:
                    isConfirmed = False

            if isConfirmed:
                self.state = 'confirmed'
            else:
                self.state = 'new'
        return


class LunchOrderLine(models.Model):
    _name = 'lunch.order.line'
    _description = 'Lunch Order Line'
    _order = 'date desc, id desc'

    name = fields.Char(related='product_id.name', string="Product Name", readonly=True)
    order_id = fields.Many2one('lunch.order', 'Order', ondelete='cascade', required=True)
    product_id = fields.Many2one('lunch.product', 'Product', required=True,
                                 domain=[('available', '=', True)])
    category_id = fields.Many2one('lunch.product.category', string='Product Category',
                                  related='product_id.category_id', readonly=True, store=True)
    date = fields.Date(string='Date', related='order_id.date', readonly=True, store=True)
    supplier = fields.Many2one('res.partner', string='Vendor', related='product_id.supplier',
                               readonly=True, store=True)
    user_id = fields.Many2one('res.users', string='User', related='order_id.user_id',
                              readonly=True, store=True)
    note = fields.Text('Note')
    price = fields.Float(related='product_id.price', readonly=True, store=True,
                         digits=dp.get_precision('Account'))
    state = fields.Selection([('new', 'New'),
                              ('confirmed', 'Received'),
                              ('ordered', 'Ordered'),
                              ('cancelled', 'Cancelled')],
                             'Status', readonly=True, index=True, default='new')
    cashmove = fields.One2many('lunch.cashmove', 'order_id', 'Cash Move')
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id', readonly=False)

    def _check_supplier_availibility(self):
        products = self.mapped('product_id')
        if not all(product.available for product in products):
            supplier_name = ", ".join(product.supplier.display_name for product in products if not product.available)
            raise ValidationError(_("Vendor(s) '%s' is not available today") % supplier_name)

    @api.model
    def create(self, vals):
        """ Override as an onchange would not apply if using the history buttons """
        res = super(LunchOrderLine, self).create(vals)
        res.with_context(lunch_date=res.order_id.date)._check_supplier_availibility()
        return res

    @api.model
    def write(self, vals):
        """ Override as an onchange would not apply if using the history buttons """
        res = super(LunchOrderLine, self).write(vals)
        if vals.get('product_id'):
            for line in self:
                line.with_context(lunch_date=line.order_id.date)._check_supplier_availibility()
        return res

    def order(self):
        """
        The order_line is ordered to the vendor but isn't received yet
        """
        if self.user_has_groups("lunch.group_lunch_manager"):
            self.write({'state': 'ordered'})

            order = {
                'supplier': False,
                'company': False,
                'currency': False,
            }
            group_lines = {}
            for line in self:
                if not line.supplier:
                    # do not send emails for products with no suppliers
                    continue

                if order['supplier'] and line.supplier != order['supplier']:
                    raise ValidationError(_("Validate order for one supplier at a time to send emails (mixed orders from %s and %s)") % (
                                            order['supplier'].display_name, line.supplier.display_name))
                order['supplier'] = line.supplier

                if order['company'] and line.order_id.company_id != order['company']:
                    raise ValidationError(_("Validate order for one company at a time to send emails (mixed orders from %s and %s)") % (
                                            order['company'].name, line.order_id.company_id.name))
                order['company'] = line.order_id.company_id

                if order['currency'] and line.currency_id != order['currency']:
                    raise ValidationError(_("Validate order for one currency at a time to send emails (mixed orders from %s and %s)") % (
                                            order['currency'].name, line.currency_id.name))
                order['currency'] = line.currency_id

                # group the order by products and note
                key = (line.product_id, line.note)
                group_lines.setdefault(key, 0)
                group_lines[key] += 1

            order['company_name'] = order['company'].name
            order['currency_id'] = order['currency'].id
            order['supplier_id'] = order['supplier'].id
            order['supplier_name'] = order['supplier'].name
            order['supplier_email'] = order['supplier'].email_formatted

            lines = []
            # sort by product name, note
            for product, note in sorted(group_lines, key=lambda k: (k[0].name, bool(k[1]))):
                quantity = group_lines[(product, note)]
                lines.append({
                    'product': product.name,
                    'note': note or '',
                    'quantity': quantity,
                    'price': product.price * quantity,
                })

            order['amount_total'] = sum(l['price'] for l in lines)

            template = self.env.ref('lunch.lunch_order_mail_supplier', raise_if_not_found=False)
            ctx = dict(
                default_composition_mode='mass_mail',
                default_use_template=bool(template),
                default_template_id=template.id,
                default_lang=order['supplier'].lang or self.env.user.lang,
                order=order,
                lines=lines,
            )
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'target': 'new',
                'context': ctx,
            }

        else:
            raise AccessError(_("Only your lunch manager processes the orders."))

    @api.one
    def confirm(self):
        """
        confirm one or more order line, update order status and create new cashmove
        """
        if self.user_has_groups("lunch.group_lunch_manager"):
            if self.state != 'confirmed':
                values = {
                    'user_id': self.user_id.id,
                    'amount': -self.price,
                    'description': self.product_id.name,
                    'order_id': self.id,
                    'state': 'order',
                    'date': self.date,
                }
                self.env['lunch.cashmove'].create(values)
                self.state = 'confirmed'
        else:
            raise AccessError(_("Only your lunch manager sets the orders as received."))

    @api.one
    def cancel(self):
        """
        cancel one or more order.line, update order status and unlink existing cashmoves
        """
        if self.user_has_groups("lunch.group_lunch_manager"):
            self.state = 'cancelled'
            self.cashmove.unlink()
        else:
            raise AccessError(_("Only your lunch manager cancels the orders."))
