# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api
from openerp.osv import fields,osv
from openerp.tools.translate import _

WARNING_MESSAGE = [
                   ('no-message','No Message'),
                   ('warning','Warning'),
                   ('block','Blocking Message')
                   ]

WARNING_HELP = _('Selecting the "Warning" option will notify user with the message, Selecting "Blocking Message" will throw an exception with the message and block the flow. The Message has to be written in the next field.')

class res_partner(osv.osv):
    _inherit = 'res.partner'
    _columns = {
        'sale_warn' : fields.selection(WARNING_MESSAGE, 'Sales Order', help=WARNING_HELP, required=True),
        'sale_warn_msg' : fields.text('Message for Sales Order'),
        'purchase_warn' : fields.selection(WARNING_MESSAGE, 'Purchase Order', help=WARNING_HELP, required=True),
        'purchase_warn_msg' : fields.text('Message for Purchase Order'),
        'picking_warn' : fields.selection(WARNING_MESSAGE, 'Stock Picking', help=WARNING_HELP, required=True),
        'picking_warn_msg' : fields.text('Message for Stock Picking'),
        'invoice_warn' : fields.selection(WARNING_MESSAGE, 'Invoice', help=WARNING_HELP, required=True),
        'invoice_warn_msg' : fields.text('Message for Invoice'),
    }
    _defaults = {
         'sale_warn' : 'no-message',
         'purchase_warn' : 'no-message',
         'picking_warn' : 'no-message',
         'invoice_warn' : 'no-message',
    }



class sale_order(osv.osv):
    _inherit = 'sale.order'
    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        if not part:
            return {'value':{'partner_invoice_id': False, 'partner_shipping_id':False, 'payment_term_id' : False}}
        warning = {}
        title = False
        message = False
        partner = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        if partner.sale_warn != 'no-message':
            title =  _("Warning for %s") % partner.name
            message = partner.sale_warn_msg
            warning = {
                    'title': title,
                    'message': message,
            }
            if partner.sale_warn == 'block':
                return {'value': {'partner_id': False, 'partner_invoice_id': False, 'partner_shipping_id':False, 'pricelist_id' : False}, 'warning': warning}

        result =  super(sale_order, self).onchange_partner_id(cr, uid, ids, part, context=context)

        if result.get('warning',False):
            warning['title'] = title and title +' & '+ result['warning']['title'] or result['warning']['title']
            warning['message'] = message and message + ' ' + result['warning']['message'] or result['warning']['message']

        if warning:
            result['warning'] = warning
        return result


class purchase_order(osv.osv):
    _inherit = 'purchase.order'
    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        if not part:
            return {'value':{'partner_address_id': False}}
        warning = {}
        title = False
        message = False
        partner = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        if partner.purchase_warn != 'no-message':
            title = _("Warning for %s") % partner.name
            message = partner.purchase_warn_msg
            warning = {
                'title': title,
                'message': message
                }
            if partner.purchase_warn == 'block':
                return {'value': {'partner_id': False}, 'warning': warning}

        result =  super(purchase_order, self).onchange_partner_id(cr, uid, ids, part, context=context)

        if result.get('warning',False):
            warning['title'] = title and title +' & '+ result['warning']['title'] or result['warning']['title']
            warning['message'] = message and message + ' ' + result['warning']['message'] or result['warning']['message']

        if warning:
            result['warning'] = warning
        return result



class account_invoice(osv.osv):
    _inherit = 'account.invoice'

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        result =  super(account_invoice, self)._onchange_partner_id()
        res = {}
        if not self.partner_id:
            self.account_id = False
            self.payment_term_id = False
            return result

        if self.partner_id.invoice_warn != 'no-message':
            res['warning'] = {
                'title': _("Warning for %s") % self.partner_id.name,
                'message': self.partner_id.invoice_warn_msg
                }

            if self.partner_id.invoice_warn == 'block':
                self.partner_id = False

            return res
        return result


class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def onchange_partner_id(self, cr, uid, ids, partner_id=None, context=None):
        if not partner_id:
            return {}
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context=context)
        warning = {}
        title = False
        message = False
        if partner.picking_warn != 'no-message':
            title = _("Warning for %s") % partner.name
            message = partner.picking_warn_msg
            warning = {
                'title': title,
                'message': message
            }
            if partner.picking_warn == 'block':
                return {'value': {'partner_id': False}, 'warning': warning}

        result = {'value': {}}

        if warning:
            result['warning'] = warning
        return result

class product_product(osv.osv):
    _inherit = 'product.template'
    _columns = {
         'sale_line_warn' : fields.selection(WARNING_MESSAGE,'Sales Order Line', help=WARNING_HELP, required=True),
         'sale_line_warn_msg' : fields.text('Message for Sales Order Line'),
         'purchase_line_warn' : fields.selection(WARNING_MESSAGE,'Purchase Order Line', help=WARNING_HELP, required=True),
         'purchase_line_warn_msg' : fields.text('Message for Purchase Order Line'),
     }

    _defaults = {
         'sale_line_warn' : 'no-message',
         'purchase_line_warn' : 'no-message',
    }


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    def product_id_change_with_wh(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False,
            fiscal_position_id=False, flag=False, warehouse_id=False, context=None):
        warning = {}
        if not product:
            return {'value': {'th_weight' : 0, 'product_packaging': False,
                'product_uos_qty': qty}, 'domain': {'product_uom': [],
                   'product_uos': []}}
        product_obj = self.pool.get('product.product')
        product_info = product_obj.browse(cr, uid, product)
        title = False
        message = False

        if product_info.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product_info.name
            message = product_info.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            if product_info.sale_line_warn == 'block':
                return {'value': {'product_id': False}, 'warning': warning}

        result =  super(sale_order_line, self).product_id_change_with_wh( cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging, fiscal_position_id, flag, warehouse_id=warehouse_id, context=context)

        if result.get('warning',False):
            warning['title'] = title and title +' & '+result['warning']['title'] or result['warning']['title']
            warning['message'] = message and message +'\n\n'+result['warning']['message'] or result['warning']['message']

        if warning:
            result['warning'] = warning
        return result


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'
    def onchange_product_id(self,cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, state='draft', replace=True, context=None):
        warning = {}
        if not product:
            return {'value': {'price_unit': price_unit or 0.0, 'name': name or '', 'product_uom' : uom or False}, 'domain':{'product_uom':[]}}
        product_obj = self.pool.get('product.product')
        product_info = product_obj.browse(cr, uid, product)
        title = False
        message = False

        if product_info.purchase_line_warn != 'no-message':
            title = _("Warning for %s") % product_info.name
            message = product_info.purchase_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            if product_info.purchase_line_warn == 'block':
                return {'value': {'product_id': False}, 'warning': warning}

        result =  super(purchase_order_line, self).onchange_product_id(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=date_order, fiscal_position_id=fiscal_position_id, date_planned=date_planned,
            name=name, price_unit=price_unit, state=state, replace=replace, context=context)

        if result.get('warning',False):
            warning['title'] = title and title +' & '+result['warning']['title'] or result['warning']['title']
            warning['message'] = message and message +'\n\n'+result['warning']['message'] or result['warning']['message']

        if warning:
            result['warning'] = warning
        return result
