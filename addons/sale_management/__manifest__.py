# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sales',
    'version': '1.0',
    'category': 'Sales',
    'sequence': 15,
    'summary': 'Send quotations, follow orders, create invoices',
    'description': """
Manage sales quotations and orders
==================================

This application allows you to manage your sales goals in an effective and efficient manner by keeping track of all sales orders and history.

It handles the full sales workflow:

* **Quotation** -> **Sales order** -> **Invoice**

Preferences (only with Warehouse Management installed)
------------------------------------------------------

If you also installed the Warehouse Management, you can deal with the following preferences:

* Shipping: Choice of delivery at once or partial delivery
* Invoicing: choose how invoices will be paid
* Incoterms: International Commercial terms

You can choose flexible invoicing methods:

* *On Demand*: Invoices are created manually from Sales Orders when needed
* *On Delivery Order*: Invoices are generated from picking (delivery)
* *Before Delivery*: A Draft invoice is created and must be paid before delivery

With this module you can personnalize the sales order and invoice report with
categories, subtotals or page-breaks.

The Dashboard for the Sales Manager will include
------------------------------------------------
* My Quotations
* Monthly Turnover (Graph)
    """,
    'website': 'https://www.odoo.com/page/sales',
    'depends': ['sale', 'account', 'digest'],
    'data': [
        'data/digest_data.xml',
        'views/sale_management_views.xml',
        'views/sale_management_templates.xml',
        'views/digest_views.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
    'post_init_hook': 'post_init_hook',
}
