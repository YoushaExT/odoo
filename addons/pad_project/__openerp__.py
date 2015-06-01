# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Pad on tasks',
    'version': '1.0',
    'category': 'Project Management',
    'description': """
This module adds a PAD in all project kanban views.
===================================================
    """,
    'author': 'OpenERP SA',
    'website': 'https://www.odoo.com/page/project-management',
    'depends': ['project', 'pad'],
    'data': ['project_task.xml'],
    'demo': [],
    'installable': True,
    'auto_install': True,
}
