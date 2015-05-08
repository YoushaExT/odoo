# -*- coding: utf-8 -*-
import random
import openerp

from openerp import SUPERUSER_ID, tools
from openerp.osv import osv, orm, fields
from openerp.addons.web.http import request
from openerp.tools.translate import _


class sale_order(osv.Model):
    _inherit = "sale.order"

    def _cart_info(self, cr, uid, ids, field_name, arg, context=None):
        res = dict()
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'cart_quantity': int(sum(l.product_uom_qty for l in (order.website_order_line or []))),
                'only_services': all(l.product_id and l.product_id.type == 'service' for l in order.website_order_line)
            }
        return res

    _columns = {
        'website_order_line': fields.one2many(
            'sale.order.line', 'order_id',
            string='Order Lines displayed on Website', readonly=True,
            help='Order Lines to be displayed on the website. They should not be used for computation purpose.',
        ),
        'cart_quantity': fields.function(_cart_info, type='integer', string='Cart Quantity', multi='_cart_info'),
        'payment_acquirer_id': fields.many2one('payment.acquirer', 'Payment Acquirer', on_delete='set null', copy=False),
        'payment_tx_id': fields.many2one('payment.transaction', 'Transaction', on_delete='set null', copy=False),
        'only_services': fields.function(_cart_info, type='boolean', string='Only Services', multi='_cart_info'),
    }

    def _get_errors(self, cr, uid, order, context=None):
        return []

    def _get_website_data(self, cr, uid, order, context):
        return {
            'partner': order.partner_id.id,
            'order': order
        }

    def _cart_find_product_line(self, cr, uid, ids, product_id=None, line_id=None, context=None, **kwargs):
        for so in self.browse(cr, uid, ids, context=context):
            domain = [('order_id', '=', so.id), ('product_id', '=', product_id)]
            if line_id:
                domain += [('id', '=', line_id)]
            return self.pool.get('sale.order.line').search(cr, SUPERUSER_ID, domain, context=context)

    def _website_product_id_change(self, cr, uid, ids, order_id, product_id, qty=0, line_id=None, context=None):
        so = self.pool.get('sale.order').browse(cr, uid, order_id, context=context)

        values = self.pool.get('sale.order.line').product_id_change(
            cr, SUPERUSER_ID, [],
            pricelist=so.pricelist_id.id,
            product=product_id,
            partner_id=so.partner_id.id,
            fiscal_position_id=so.fiscal_position_id.id,
            qty=qty,
            context=context
        )['value']

        if line_id:
            line = self.pool.get('sale.order.line').browse(cr, SUPERUSER_ID, line_id, context=context)
            values['name'] = line.name
        else:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            values['name'] = product.display_name
            if product.description_sale:
                values['name'] += '\n'+product.description_sale

        values['product_id'] = product_id
        values['order_id'] = order_id
        if values.get('tax_id') is not None:
            values['tax_id'] = [(6, 0, values['tax_id'])]
        return values

    def _cart_update(self, cr, uid, ids, product_id=None, line_id=None, add_qty=0, set_qty=0, context=None, **kwargs):
        """ Add or set product quantity, add_qty can be negative """
        sol = self.pool.get('sale.order.line')

        quantity = 0
        for so in self.browse(cr, uid, ids, context=context):
            if line_id is not False:
                line_ids = so._cart_find_product_line(product_id, line_id, context=context, **kwargs)
                if line_ids:
                    line_id = line_ids[0]

            # Create line if no line with product_id can be located
            if not line_id:
                values = self._website_product_id_change(cr, uid, ids, so.id, product_id, qty=1, context=context)
                line_id = sol.create(cr, SUPERUSER_ID, values, context=context)
                if add_qty:
                    add_qty -= 1

            # compute new quantity
            if set_qty:
                quantity = set_qty
            elif add_qty is not None:
                quantity = sol.browse(cr, SUPERUSER_ID, line_id, context=context).product_uom_qty + (add_qty or 0)

            # Remove zero of negative lines
            if quantity <= 0:
                sol.unlink(cr, SUPERUSER_ID, [line_id], context=context)
            else:
                # update line
                values = self._website_product_id_change(cr, uid, ids, so.id, product_id, qty=quantity, line_id=line_id, context=context)
                values['product_uom_qty'] = quantity
                sol.write(cr, SUPERUSER_ID, [line_id], values, context=context)

        return {'line_id': line_id, 'quantity': quantity}

    def _cart_accessories(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            s = set(j.id for l in (order.website_order_line or []) for j in (l.product_id.accessory_product_ids or []))
            s -= set(l.product_id.id for l in order.order_line)
            product_ids = random.sample(s, min(len(s), 3))
            return self.pool['product.product'].browse(cr, uid, product_ids, context=context)


class website(orm.Model):
    _inherit = 'website'

    _columns = {
        'pricelist_id': fields.related(
            'user_id', 'partner_id', 'property_product_pricelist',
            type='many2one', relation='product.pricelist', string='Default Pricelist'),
        'currency_id': fields.related(
            'pricelist_id', 'currency_id',
            type='many2one', relation='res.currency', string='Default Currency'),
        'salesperson_id': fields.many2one('res.users', 'Salesperson'),
        'salesteam_id': fields.many2one('crm.team', 'Sales Team'),
        'website_pricelist_ids': fields.one2many('website_pricelist', 'website_id',
                                                 string='Price list available for this Ecommerce/Website'),
    }

    @tools.ormcache()
    # No context, else no cache
    def _get_pl(self, cr, uid, country_code, show_visible, website_pl, current_pl, all_pl):
        """ Return the list of pricelists that can be used on website for the current user.

        :param str country_code: code iso or False, If set, we search only price list available for this country
        :param bool show_visible: if True, we don't display pricelist where selectable is False (Eg: Code promo)
        :param int website_pl: The default pricelist used on this website
        :param int current_pl: The current pricelist used on the website
                               (If not selectable but the current pricelist we had this pricelist anyway)
        :param list all_pl: List of all pricelist available for this website

        :returns: list of pricelist
        """
        pcs = []

        if country_code:
            groups = self.pool['res.country.group'].search(cr, uid, [('country_ids.code', '=', country_code)])
            for cgroup in self.pool['res.country.group'].browse(cr, uid, groups):
                for pll in cgroup.website_pricelist_ids:
                    if not show_visible or pll.selectable or pll.pricelist_id.id == current_pl:
                        pcs.append(pll.pricelist_id)

        if not pcs:  # no pricelist for this country, or no GeoIP
            pcs = [pll.pricelist_id for pll in all_pl
                   if not show_visible or pll.selectable or pll.pricelist_id.id == current_pl]

        partner = self.pool['res.users'].browse(cr, SUPERUSER_ID, uid).partner_id
        if not pcs or partner.property_product_pricelist.id != website_pl:
            pcs.append(partner.property_product_pricelist)
        pcs = list(set(pcs))  # remove duplicate
        pcs.sort(key=lambda x: x.name)  # sort by name
        return pcs

    def get_pricelist_available(self, cr, uid, show_visible=False, context=None):
        """ Return the list of pricelists that can be used on website for the current user.
        Country restrictions will be detected with GeoIP (if installed).

        :param str country_code: code iso or False, If set, we search only price list available for this country
        :param bool show_visible: if True, we don't display pricelist where selectable is False (Eg: Code promo)

        :returns: list of pricelist
        """
        isocountry = request.session.geoip and request.session.geoip.get('country_code') or False
        return self._get_pl(
                cr,
                uid,
                isocountry,
                show_visible,
                request.website.pricelist_id.id,
                request.session.get('website_sale_current_pl'),
                request.website.website_pricelist_ids
        )

    def is_pricelist_available(self, cr, uid, pl_id, context=None):
        """ Return a boolean to specify if a specific pricelist can be manually set on the website.
        Warning: It check only if pricelist is in the 'selectable' pricelists or the current pricelist.

        :param int pl_id: The pricelist id to check

        :returns: Boolean, True if valid / available
        """
        return pl_id in [ppl.id for ppl in self.get_pricelist_available(cr, uid, show_visible=False, context=context)]

    def get_current_pricelist(self, cr, uid, context=None):
        """
        :returns: The current pricelist record
        """
        pl_id = request.session.get('website_sale_current_pl')
        if pl_id:
            return self.pool['product.pricelist'].browse(cr, uid, [pl_id], context=context)[0]
        else:
            pl = self.pool['res.users'].browse(cr, SUPERUSER_ID, uid, context=context).partner_id.property_product_pricelist
            request.session['website_sale_current_pl'] = pl.id
            return pl

    def sale_product_domain(self, cr, uid, ids, context=None):
        return [("sale_ok", "=", True)]

    def get_partner(self, cr, uid):
        return self.pool['res.users'].browse(cr, SUPERUSER_ID, uid).partner_id

    def sale_get_order(self, cr, uid, ids, force_create=False, code=None, update_pricelist=False, force_pricelist=False, context=None):
        """ Return the current sale order after mofications specified by params.

        :param bool force_create: Create sale order if not already existing
        :param str code: Code to force a pricelist (promo code)
                         If empty, it's a special case to reset the pricelist with the first available else the default.
        :param bool update_pricelist: Force to recompute all the lines from sale order to adapt the price with the current pricelist.
        :param int force_pricelist: pricelist_id - if set,  we change the pricelist with this one

        :returns: browse record for the current sale order
        """
        partner = self.get_partner(cr, uid)
        sale_order_obj = self.pool['sale.order']
        sale_order_id = request.session.get('sale_order_id') or (partner.last_website_so_id.id if partner.last_website_so_id and partner.last_website_so_id.state == 'draft' else False)

        sale_order = None
        pricelist_id = request.session.get('website_sale_current_pl')

        if force_pricelist and self.pool['product.pricelist'].search_count(cr, uid, [('id', '=', force_pricelist)], context=context):
            pricelist_id = force_pricelist
            request.session['website_sale_current_pl'] = pricelist_id
            update_pricelist = True

        # create so if needed
        if not sale_order_id and (force_create or code):
            # TODO cache partner_id session
            user_obj = self.pool['res.users']
            affiliate_id = request.session.get('affiliate_id')
            salesperson_id = affiliate_id if user_obj.exists(cr, SUPERUSER_ID, affiliate_id, context=context) else request.website.salesperson_id.id
            for w in self.browse(cr, uid, ids):
                values = {
                    'partner_id': partner.id,
                    'pricelist_id': pricelist_id,
                    'team_id': w.salesteam_id.id,
                }
                sale_order_id = sale_order_obj.create(cr, SUPERUSER_ID, values, context=context)
                values = sale_order_obj.onchange_partner_id(cr, SUPERUSER_ID, [], partner.id, context=context)['value']
                values.update({'user_id': salesperson_id or w.salesperson_id.id})

                sale_order_obj.write(cr, SUPERUSER_ID, [sale_order_id], values, context=context)
                request.session['sale_order_id'] = sale_order_id

                if request.website.partner_id.id != partner.id:
                    self.pool['res.partner'].write(cr, SUPERUSER_ID, partner.id, {'last_website_so_id': sale_order_id})

        if sale_order_id:
            sale_order = sale_order_obj.browse(cr, SUPERUSER_ID, sale_order_id, context=context)
            if not sale_order.exists():
                request.session['sale_order_id'] = None
                return None

            # check for change of pricelist with a coupon
            pricelist_id = pricelist_id or partner.property_product_pricelist.id

            # check for change of partner_id ie after signup
            if sale_order.partner_id.id != partner.id and request.website.partner_id.id != partner.id:
                flag_pricelist = False
                if pricelist_id != sale_order.pricelist_id.id:
                    flag_pricelist = True
                fiscal_position = sale_order.fiscal_position_id and sale_order.fiscal_position_id.id or False

                values = sale_order_obj.onchange_partner_id(cr, SUPERUSER_ID, [sale_order_id], partner.id, context=context)['value']
                if values.get('pricelist_id'):
                    if values['pricelist_id'] != pricelist_id:
                        values['pricelist_id'] = pricelist_id
                        update_pricelist = True

                if values.get('fiscal_position_id'):
                    order_lines = map(int, sale_order.order_line)
                    values.update(sale_order_obj.onchange_fiscal_position(
                        cr, SUPERUSER_ID, [],
                        values['fiscal_position_id'], [[6, 0, order_lines]], context=context)['value'])

                values['partner_id'] = partner.id
                sale_order_obj.write(cr, SUPERUSER_ID, [sale_order_id], values, context=context)

                if flag_pricelist or values.get('fiscal_position_id') != fiscal_position:
                    update_pricelist = True

            if (code and code != sale_order.pricelist_id.code) or \
               (code is not None and code == '' and request.session.get('sale_order_code_pricelist_id') and request.session.get('sale_order_code_pricelist_id') != ''): # empty code so reset
                pricelist_ids = self.pool['product.pricelist'].search(cr, uid, [('code', '=', code)], limit=1, context=context)
                if pricelist_ids:
                    pricelist_id = pricelist_ids[0]
                    request.session['sale_order_code_pricelist_id'] = pricelist_id
                    request.session['website_sale_current_pl'] = pricelist_id
                    update_pricelist = True
                elif code == '' and request.session['website_sale_current_pl'] == request.session['sale_order_code_pricelist_id']:
                    request.session['website_sale_current_pl'] = partner.property_product_pricelist.id
                    request.session['sale_order_code_pricelist_id'] = False
                    update_pricelist = True

            # update the pricelist
            if update_pricelist:
                values = {'pricelist_id': pricelist_id}
                values.update(sale_order.onchange_pricelist_id(pricelist_id, None)['value'])
                sale_order.write(values)
                for line in sale_order.order_line:
                    sale_order._cart_update(product_id=line.product_id.id, line_id=line.id, add_qty=0)

            # update browse record
            if (code and code != sale_order.pricelist_id.code) or sale_order.partner_id.id != partner.id or force_pricelist:
                sale_order = sale_order_obj.browse(cr, SUPERUSER_ID, sale_order.id, context=context)

        return sale_order

    def sale_get_transaction(self, cr, uid, ids, context=None):
        transaction_obj = self.pool.get('payment.transaction')
        tx_id = request.session.get('sale_transaction_id')
        if tx_id:
            tx_ids = transaction_obj.search(cr, SUPERUSER_ID, [('id', '=', tx_id), ('state', 'not in', ['cancel'])], context=context)
            if tx_ids:
                return transaction_obj.browse(cr, SUPERUSER_ID, tx_ids[0], context=context)
            else:
                request.session['sale_transaction_id'] = False
        return False

    def sale_reset(self, cr, uid, ids, context=None):
        request.session.update({
            'sale_order_id': False,
            'sale_transaction_id': False,
            'sale_order_code_pricelist_id': False,
            'website_sale_current_pl': False,
        })


class website_pricelist(osv.Model):
    _name = 'website_pricelist'
    _description = 'Website Pricelist'

    def _get_display_name(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for o in self.browse(cr, uid, ids, context=context):
            result[o.id] = _("Website Pricelist for %s") % o.pricelist_id.name
        return result

    _columns = {
        'name': fields.function(_get_display_name, string='Pricelist Name', type="char"),
        'website_id': fields.many2one('website', string="Website", required=True),
        'selectable': fields.boolean('Selectable', help="Allow the end user to choose this price list"),
        'pricelist_id': fields.many2one('product.pricelist', string='Pricelist'),
        'country_group_ids': fields.many2many('res.country.group', 'res_country_group_website_pricelist_rel',
                                              'website_pricelist_id', 'res_country_group_id', string='Country Groups'),
    }

    # _get_pl is cached to avoid to recompute at each request the list of pricelists availables.
    # So, we need to invalidate the cache when we change the config of website price list to force to recompute.
    def clear_cache(self):
        self.pool['website']._get_pl.clear_cache(self.pool['website'])

    def create(self, cr, uid, data, context=None):
        res = super(website_pricelist, self).create(cr, uid, data, context=context)
        self.clear_cache()
        return res

    def write(self, cr, uid, ids, data, context=None):
        res = super(website_pricelist, self).write(cr, uid, ids, data, context=context)
        self.clear_cache()
        return res

    def unlink(self, cr, uid, ids, context=None):
        res = super(website_pricelist, self).unlink(cr, uid, ids, context=context)
        self.clear_cache()
        return res


class CountryGroup(osv.Model):
    _inherit = 'res.country.group'
    _columns = {
        'website_pricelist_ids': fields.many2many('website_pricelist', 'res_country_group_website_pricelist_rel',
                                                  'res_country_group_id', 'website_pricelist_id', string='Website Price Lists'),
    }


class res_partner(openerp.models.Model):
    _inherit = 'res.partner'

    last_website_so_id = openerp.fields.Many2one('sale.order', 'Last Online Sale Order')
