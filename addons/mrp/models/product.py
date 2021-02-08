# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import api, fields, models
from odoo.tools.float_utils import float_round, float_is_zero


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bom_line_ids = fields.One2many('mrp.bom.line', 'product_tmpl_id', 'BoM Components')
    bom_ids = fields.One2many('mrp.bom', 'product_tmpl_id', 'Bill of Materials')
    bom_count = fields.Integer('# Bill of Material',
        compute='_compute_bom_count', compute_sudo=False)
    used_in_bom_count = fields.Integer('# of BoM Where is Used',
        compute='_compute_used_in_bom_count', compute_sudo=False)
    mrp_product_qty = fields.Float('Manufactured',
        compute='_compute_mrp_product_qty', compute_sudo=False)
    produce_delay = fields.Float(
        'Manufacturing Lead Time', default=0.0,
        help="Average lead time in days to manufacture this product. In the case of multi-level BOM, the manufacturing lead times of the components will be added.")

    def _compute_bom_count(self):
        for product in self:
            product.bom_count = self.env['mrp.bom'].search_count([('product_tmpl_id', '=', product.id)])

    def _compute_used_in_bom_count(self):
        for template in self:
            template.used_in_bom_count = self.env['mrp.bom'].search_count(
                [('bom_line_ids.product_id', 'in', template.product_variant_ids.ids)])

    def write(self, values):
        if 'active' in values:
            self.filtered(lambda p: p.active != values['active']).with_context(active_test=False).bom_ids.write({
                'active': values['active']
            })
        return super().write(values)

    def action_used_in_bom(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_bom_form_action")
        action['domain'] = [('bom_line_ids.product_id', 'in', self.product_variant_ids.ids)]
        return action

    def _compute_mrp_product_qty(self):
        for template in self:
            template.mrp_product_qty = float_round(sum(template.mapped('product_variant_ids').mapped('mrp_product_qty')), precision_rounding=template.uom_id.rounding)

    def action_view_mos(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_production_report")
        action['domain'] = [('state', '=', 'done'), ('product_tmpl_id', 'in', self.ids)]
        action['context'] = {
            'graph_measure': 'product_uom_qty',
            'time_ranges': {'field': 'date_planned_start', 'range': 'last_365_days'}
        }
        return action


class ProductProduct(models.Model):
    _inherit = "product.product"

    variant_bom_ids = fields.One2many('mrp.bom', 'product_id', 'BOM Product Variants')
    bom_line_ids = fields.One2many('mrp.bom.line', 'product_id', 'BoM Components')
    bom_count = fields.Integer('# Bill of Material',
        compute='_compute_bom_count', compute_sudo=False)
    used_in_bom_count = fields.Integer('# BoM Where Used',
        compute='_compute_used_in_bom_count', compute_sudo=False)
    mrp_product_qty = fields.Float('Manufactured',
        compute='_compute_mrp_product_qty', compute_sudo=False)

    def _compute_bom_count(self):
        for product in self:
            product.bom_count = self.env['mrp.bom'].search_count(['|', ('product_id', '=', product.id), '&', ('product_id', '=', False), ('product_tmpl_id', '=', product.product_tmpl_id.id)])

    def _compute_used_in_bom_count(self):
        for product in self:
            product.used_in_bom_count = self.env['mrp.bom'].search_count([('bom_line_ids.product_id', '=', product.id)])

    def write(self, values):
        if 'active' in values:
            self.filtered(lambda p: p.active != values['active']).with_context(active_test=False).variant_bom_ids.write({
                'active': values['active']
            })
        return super().write(values)

    def get_components(self):
        """ Return the components list ids in case of kit product.
        Return the product itself otherwise"""
        self.ensure_one()
        bom_kit = self.env['mrp.bom']._bom_find(product=self, bom_type='phantom')
        if bom_kit:
            boms, bom_sub_lines = bom_kit.explode(self, 1)
            return [bom_line.product_id.id for bom_line, data in bom_sub_lines if bom_line.product_id.type == 'product']
        else:
            return super(ProductProduct, self).get_components()

    def action_used_in_bom(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_bom_form_action")
        action['domain'] = [('bom_line_ids.product_id', '=', self.id)]
        return action

    def _compute_mrp_product_qty(self):
        date_from = fields.Datetime.to_string(fields.datetime.now() - timedelta(days=365))
        #TODO: state = done?
        domain = [('state', '=', 'done'), ('product_id', 'in', self.ids), ('date_planned_start', '>', date_from)]
        read_group_res = self.env['mrp.production'].read_group(domain, ['product_id', 'product_uom_qty'], ['product_id'])
        mapped_data = dict([(data['product_id'][0], data['product_uom_qty']) for data in read_group_res])
        for product in self:
            if not product.id:
                product.mrp_product_qty = 0.0
                continue
            product.mrp_product_qty = float_round(mapped_data.get(product.id, 0), precision_rounding=product.uom_id.rounding)

    def _compute_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
        """ When the product is a kit, this override computes the fields :
         - 'virtual_available'
         - 'qty_available'
         - 'incoming_qty'
         - 'outgoing_qty'
         - 'free_qty'

        This override is used to get the correct quantities of products
        with 'phantom' as BoM type.
        """
        bom_kits = {
            product: bom
            for product in self
            for bom in (self.env['mrp.bom']._bom_find(product=product, bom_type='phantom'),)
            if bom
        }
        kits = self.filtered(lambda p: bom_kits.get(p))
        res = super(ProductProduct, self - kits)._compute_quantities_dict(lot_id, owner_id, package_id, from_date=from_date, to_date=to_date)
        for product in bom_kits:
            boms, bom_sub_lines = bom_kits[product].explode(product, 1)
            ratios_virtual_available = []
            ratios_qty_available = []
            ratios_incoming_qty = []
            ratios_outgoing_qty = []
            ratios_free_qty = []
            for bom_line, bom_line_data in bom_sub_lines:
                component = bom_line.product_id
                if component.type != 'product' or float_is_zero(bom_line_data['qty'], precision_rounding=bom_line.product_uom_id.rounding):
                    # As BoMs allow components with 0 qty, a.k.a. optionnal components, we simply skip those
                    # to avoid a division by zero. The same logic is applied to non-storable products as those
                    # products have 0 qty available.
                    continue
                uom_qty_per_kit = bom_line_data['qty'] / bom_line_data['original_qty']
                qty_per_kit = bom_line.product_uom_id._compute_quantity(uom_qty_per_kit, bom_line.product_id.uom_id, raise_if_failure=False)
                if not qty_per_kit:
                    continue
                component_res = res.get(component.id, {
                    "virtual_available": component.virtual_available,
                    "qty_available": component.qty_available,
                    "incoming_qty": component.incoming_qty,
                    "outgoing_qty": component.outgoing_qty,
                    "free_qty": component.free_qty,
                })
                ratios_virtual_available.append(component_res["virtual_available"] / qty_per_kit)
                ratios_qty_available.append(component_res["qty_available"] / qty_per_kit)
                ratios_incoming_qty.append(component_res["incoming_qty"] / qty_per_kit)
                ratios_outgoing_qty.append(component_res["outgoing_qty"] / qty_per_kit)
                ratios_free_qty.append(component_res["free_qty"] / qty_per_kit)
            if bom_sub_lines and ratios_virtual_available:  # Guard against all cnsumable bom: at least one ratio should be present.
                res[product.id] = {
                    'virtual_available': min(ratios_virtual_available) // 1,
                    'qty_available': min(ratios_qty_available) // 1,
                    'incoming_qty': min(ratios_incoming_qty) // 1,
                    'outgoing_qty': min(ratios_outgoing_qty) // 1,
                    'free_qty': min(ratios_free_qty) // 1,
                }
            else:
                res[product.id] = {
                    'virtual_available': 0,
                    'qty_available': 0,
                    'incoming_qty': 0,
                    'outgoing_qty': 0,
                    'free_qty': 0,
                }

        return res

    def action_view_bom(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.product_open_bom")
        template_ids = self.mapped('product_tmpl_id').ids
        # bom specific to this variant or global to template
        action['context'] = {
            'default_product_tmpl_id': template_ids[0],
            'default_product_id': self.ids[0],
        }
        action['domain'] = ['|', ('product_id', 'in', self.ids), '&', ('product_id', '=', False), ('product_tmpl_id', 'in', template_ids)]
        return action

    def action_view_mos(self):
        action = self.product_tmpl_id.action_view_mos()
        action['domain'] = [('state', '=', 'done'), ('product_id', 'in', self.ids)]
        return action

    def action_open_quants(self):
        bom_kits = {}
        for product in self:
            bom = self.env['mrp.bom']._bom_find(product=product, bom_type='phantom')
            if bom:
                bom_kits[product] = bom
        components = self - self.env['product.product'].concat(*list(bom_kits.keys()))
        for product in bom_kits:
            boms, bom_sub_lines = bom_kits[product].explode(product, 1)
            components |= self.env['product.product'].concat(*[l[0].product_id for l in bom_sub_lines])
        res = super(ProductProduct, components).action_open_quants()
        if bom_kits:
            res['context']['single_product'] = False
        return res
