# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons import decimal_precision as dp


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    @api.one
    @api.depends('quant_ids')
    def _compute_weight(self):
        weight = 0.0
        if self.env.context.get('picking_id'):
            current_picking_move_line_ids = self.env['stock.move.line'].search([('result_package_id', '=', self.id), ('picking_id', '=', self.env.context['picking_id'])])
            for ml in current_picking_move_line_ids:
                weight += ml.product_uom_id._compute_quantity(ml.qty_done,ml.product_id.uom_id) * ml.product_id.weight
        else:
            for quant in self.quant_ids:
                weight += quant.quantity * quant.product_id.weight
        self.weight = weight

    def _get_default_weight_uom(self):
        return self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    def _compute_weight_uom_name(self):
        for package in self:
            package.weight_uom_name = self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    weight = fields.Float(compute='_compute_weight', help="Total weight of all the products contained in the package.")
    weight_uom_name = fields.Char(string='Weight unit of measure label', compute='_compute_weight_uom_name', readonly=True, default=_get_default_weight_uom)
    shipping_weight = fields.Float(string='Shipping Weight', help="Total weight of the package.")


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    @api.one
    @api.depends('move_line_ids')
    def _compute_packages(self):
        self.ensure_one()
        packs = set()
        for move_line in self.move_line_ids:
            if move_line.result_package_id:
                packs.add(move_line.result_package_id.id)
        self.package_ids = list(packs)

    @api.one
    @api.depends('move_line_ids')
    def _compute_bulk_weight(self):
        weight = 0.0
        for move_line in self.move_line_ids:
            if move_line.product_id and not move_line.result_package_id:
                weight += move_line.product_uom_id._compute_quantity(move_line.qty_done, move_line.product_id.uom_id) * move_line.product_id.weight
        self.weight_bulk = weight

    @api.one
    @api.depends('package_ids', 'weight_bulk')
    def _compute_shipping_weight(self):
        self.shipping_weight = self.weight_bulk + sum([pack.shipping_weight for pack in self.package_ids])

    def _get_default_weight_uom(self):
        return self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    def _compute_weight_uom_name(self):
        for package in self:
            package.weight_uom_name = self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    carrier_price = fields.Float(string="Shipping Cost")
    delivery_type = fields.Selection(related='carrier_id.delivery_type', readonly=True)
    carrier_id = fields.Many2one("delivery.carrier", string="Carrier")
    volume = fields.Float(copy=False)
    weight = fields.Float(compute='_cal_weight', digits=dp.get_precision('Stock Weight'), store=True, help="Total weight of the products in the picking.")
    carrier_tracking_ref = fields.Char(string='Tracking Reference', copy=False)
    carrier_tracking_url = fields.Char(string='Tracking URL', compute='_compute_carrier_tracking_url')
    weight_uom_name = fields.Char(string='Weight unit of measure label', compute='_compute_weight_uom_name', readonly=True, default=_get_default_weight_uom)
    package_ids = fields.Many2many('stock.quant.package', compute='_compute_packages', string='Packages')
    weight_bulk = fields.Float('Bulk Weight', compute='_compute_bulk_weight')
    shipping_weight = fields.Float("Weight for Shipping", compute='_compute_shipping_weight', help="Total weight of the packages and products which are not in a package. That's the weight used to compute the cost of the shipping.")
    is_return_picking = fields.Boolean(compute='_compute_return_picking')
    return_label_ids = fields.One2many('ir.attachment', compute='_compute_return_label')

    @api.depends('carrier_id', 'carrier_tracking_ref')
    def _compute_carrier_tracking_url(self):
        for picking in self:
            picking.carrier_tracking_url = picking.carrier_id.get_tracking_link(picking) if picking.carrier_id and picking.carrier_tracking_ref else False

    @api.depends('carrier_id', 'move_ids_without_package')
    def _compute_return_picking(self):
        for picking in self:
            if picking.carrier_id and picking.carrier_id.can_generate_return:
                picking.is_return_picking = any(m.origin_returned_move_id for m in picking.move_ids_without_package)
            else:
                picking.is_return_picking = False

    def _compute_return_label(self):
        for picking in self:
            picking.return_label_ids = self.env['ir.attachment'].search([('res_model', '=', 'stock.picking'), ('res_id', '=', picking.id), ('name', 'ilike', 'ReturnLabel')])

    @api.depends('move_lines')
    def _cal_weight(self):
        for picking in self:
            picking.weight = sum(move.weight for move in picking.move_lines if move.state != 'cancel')

    @api.multi
    def action_done(self):
        res = super(StockPicking, self).action_done()
        for pick in self:
            if pick.carrier_id:
                if pick.carrier_id.integration_level == 'rate_and_ship' and pick.picking_type_code != 'incoming':
                    pick.send_to_shipper()
                pick._add_delivery_cost_to_so()
        return res

    @api.multi
    def _pre_put_in_pack_hook(self, move_line_ids):
        res = super(StockPicking, self)._pre_put_in_pack_hook(move_line_ids)
        if not res:
            if self.carrier_id:
                return self._set_delivery_packaging()
        else:
            return res

    def _set_delivery_packaging(self):
        """ This method returns an action allowing to set the product packaging and the shipping weight
         on the stock.quant.package.
        """
        self.ensure_one()
        view_id = self.env.ref('delivery.choose_delivery_package_view_form').id
        return {
            'name': _('Package Details'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.package',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': dict(
                self.env.context,
                current_package_carrier_type=self.carrier_id.delivery_type,
                default_picking_id=self.id
            ),
        }

    @api.multi
    def action_send_confirmation_email(self):
        self.ensure_one()
        delivery_template_id = self.env.ref('delivery.mail_template_data_delivery_confirmation').id
        compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        ctx = dict(
            default_composition_mode='comment',
            default_res_id=self.id,
            default_model='stock.picking',
            default_use_template=bool(delivery_template_id),
            default_template_id=delivery_template_id,
            custom_layout='mail.mail_notification_light'
        )
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def send_to_shipper(self):
        self.ensure_one()
        res = self.carrier_id.send_shipping(self)[0]
        if self.carrier_id.free_over and self.sale_id and self.sale_id._compute_amount_total_without_delivery() >= self.carrier_id.amount:
            res['exact_price'] = 0.0
        self.carrier_price = res['exact_price']
        if res['tracking_number']:
            self.carrier_tracking_ref = res['tracking_number']
        order_currency = self.sale_id.currency_id or self.company_id.currency_id
        msg = _("Shipment sent to carrier %s for shipping with tracking number %s<br/>Cost: %.2f %s") % (self.carrier_id.name, self.carrier_tracking_ref, self.carrier_price, order_currency.name)
        self.message_post(body=msg)

    def _get_new_delivery_price(self):
        if self.carrier_id.integration_level != 'rate_and_ship':
            res = self.carrier_id.rate_shipment(self.sale_id)
            if res['success']:
                self.carrier_price = res['price']
            else:
                raise UserError(_("Unable to update the delivery price because of: ") + res['error_message'])

    @api.multi
    def print_return_label(self):
        self.ensure_one()
        res = self.carrier_id.get_return_label(self)

    @api.multi
    def _add_delivery_cost_to_so(self):
        self.ensure_one()
        sale_order = self.sale_id
        # if there isn't a delivery line on the SO yet
        if sale_order.invoice_shipping_on_delivery:
            self._get_new_delivery_price()  # fill `self.carrier_price` if needed
            sale_order._create_delivery_line(self.carrier_id, self.carrier_price, price_unit_in_description=False)
        else:
            # we only want to update the price of the delivery line if the invoice
            # policy is 'Real' but we chose not to if the user updated it in the meantime
            delivery_line = sale_order.order_line.filtered(lambda line: line.is_delivery)
            if self.carrier_id.invoice_policy == 'real' and delivery_line.currency_id.is_zero(delivery_line.price_unit):
                self._get_new_delivery_price()
                delivery_line.write({
                    'price_unit': self.carrier_price,
                    # remove the estimated price from the description
                    'name': sale_order.carrier_id.with_context(lang=self.partner_id.lang).name,
                })

    @api.multi
    def open_website_url(self):
        self.ensure_one()
        if not self.carrier_tracking_url:
            raise UserError(_("Your delivery method has no redirect on courier provider's website to track this order."))

        carrier_trackers = []
        try:
            carrier_trackers = json.loads(self.carrier_tracking_url)
        except ValueError:
            carrier_trackers = self.carrier_tracking_url
        else:
            msg = "Tracking links for shipment: <br/>"
            for tracker in carrier_trackers:
                msg += '<a href=' + tracker[1] + '>' + tracker[0] + '</a><br/>'
            self.message_post(body=msg)
            return self.env.ref('delivery.act_delivery_trackers_url').read()[0]

        client_action = {
            'type': 'ir.actions.act_url',
            'name': "Shipment Tracking Page",
            'target': 'new',
            'url': self.carrier_tracking_url,
        }
        return client_action

    @api.one
    def cancel_shipment(self):
        self.carrier_id.cancel_shipment(self)
        msg = "Shipment %s cancelled" % self.carrier_tracking_ref
        self.message_post(body=msg)
        self.carrier_tracking_ref = False

    @api.multi
    def check_packages_are_identical(self):
        '''Some shippers require identical packages in the same shipment. This utility checks it.'''
        self.ensure_one()
        if self.package_ids:
            packages = [p.packaging_id for p in self.package_ids]
            if len(set(packages)) != 1:
                package_names = ', '.join([str(p.name) for p in packages])
                raise UserError(_('You are shipping different packaging types in the same shipment.\nPackaging Types: %s' % package_names))
        return True


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.multi
    def _create_returns(self):
        # Prevent copy of the carrier and carrier price when generating return picking
        # (we have no integration of returns for now)
        new_picking, pick_type_id = super(StockReturnPicking, self)._create_returns()
        picking = self.env['stock.picking'].browse(new_picking)
        picking.write({'carrier_id': False,
                       'carrier_price': 0.0})
        return new_picking, pick_type_id
