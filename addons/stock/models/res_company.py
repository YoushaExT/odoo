# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Company(models.Model):
    _inherit = "res.company"

    propagation_minimum_delta = fields.Integer('Minimum Delta for Propagation of a Date Change on moves linked together', default=1)
    internal_transit_location_id = fields.Many2one(
        'stock.location', 'Internal Transit Location', on_delete="restrict",
        help="Technical field used for resupply routes between warehouses that belong to this company")

    def create_transit_location(self):
        '''Create a transit location with company_id being the given company_id. This is needed
           in case of resuply routes between warehouses belonging to the same company, because
           we don't want to create accounting entries at that time.
        '''
        parent_location = self.env.ref('stock.stock_location_locations', raise_if_not_found=False)
        for company in self:
            location = self.env['stock.location'].create({
                'name': _('%s: Transit Location') % company.name,
                'usage': 'transit',
                'location_id': parent_location and parent_location.id or False,
            })
            location.sudo().write({'company_id': company.id})
            company.write({'internal_transit_location_id': location.id})

            warehouses = self.env['stock.warehouse'].search([('partner_id', '=', company.partner_id.id)])
            warehouses.mapped('partner_id').with_context(force_company=company.id).write({
                'property_stock_customer': location.id,
                'property_stock_supplier': location.id,
            })

    def _create_inventory_loss_location(self):
        parent_location = self.env.ref('stock.stock_location_locations_virtual', raise_if_not_found=False)
        inventory_loss_product_template_field = self.env['ir.model.fields'].search([('model','=','product.template'),('name','=','property_stock_inventory')])
        for company in self:
            inventory_loss_location = self.env['stock.location'].create({
                'name': '%s: Inventory adjustment' % company.name,
                'usage': 'inventory',
                'location_id': parent_location.id,
                'company_id': company.id,
            })
            self.env['ir.property'].create({
                'name': 'property_stock_inventory_%s' % company.name,
                'fields_id': inventory_loss_product_template_field.id,
                'company_id': company.id,
                'value': 'stock.location,%d' % inventory_loss_location.id,
            })

    @api.model
    def create_missing_inventory_loss_location(self):
        company_ids  = self.env['res.company'].search([])
        inventory_loss_product_template_field = self.env['ir.model.fields'].search([('model','=','product.template'),('name','=','property_stock_inventory')])
        companies_having_property = self.env['ir.property'].search([('fields_id', '=', inventory_loss_product_template_field.id)]).mapped('company_id')
        company_without_property = company_ids - companies_having_property
        for company in company_without_property:
            company._create_inventory_loss_location()

    @api.model
    def create(self, vals):
        company = super(Company, self).create(vals)

        company.create_transit_location()
        company.sudo()._create_inventory_loss_location()
        # mutli-company rules prevents creating warehouse and sub-locations
        self.env['stock.warehouse'].check_access_rights('create')
        self.env['stock.warehouse'].sudo().create({'name': company.name, 'code': company.name[:5], 'company_id': company.id, 'partner_id': company.partner_id.id})
        return company
