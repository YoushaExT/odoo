# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Manufacturing',
    'version': '2.0',
    'website': 'https://www.odoo.com/page/manufacturing',
    'category': 'Manufacturing',
    'sequence': 14,
    'summary': 'Manufacturing Orders, Bill of Materials, Routings',
    'depends': ['product', 'stock', 'resource'],
    'description': "",
    'data': [
        'security/mrp_security.xml',
        'security/ir.model.access.csv',
        'data/mrp_data.xml',
        'wizard/mrp_product_produce_views.xml',
        'wizard/change_production_qty_views.xml',
        'wizard/mrp_workcenter_block_view.xml',
        'wizard/stock_warn_insufficient_qty_views.xml',
        'views/mrp_views_menus.xml',
        'views/stock_move_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_routing_views.xml',
        'views/mrp_bom_views.xml',
        'views/procurement_views.xml',
        'views/product_views.xml',
        'views/stock_warehouse_views.xml',
        'views/stock_picking_views.xml',
        'views/mrp_unbuild_views.xml',
        'views/ir_attachment_view.xml',
        'views/res_config_settings_views.xml',
        'views/mrp_templates.xml',
        'views/stock_scrap_views.xml',
        'report/mrp_report_views_main.xml',
        'report/mrp_report_bom_structure.xml',
        'report/mrp_production_templates.xml',
    ],
    'qweb': ['static/src/xml/mrp.xml'],
    'demo': [
        'data/mrp_demo.xml',
    ],
    'test': [],
    'application': True,
}
