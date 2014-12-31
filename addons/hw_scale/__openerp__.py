# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'Weighting Scale Hardware Driver',
    'version': '1.0',
    'category': 'Hardware Drivers',
    'sequence': 6,
    'summary': 'Hardware Driver for Weighting Scales',
    'website': 'https://www.odoo.com/page/point-of-sale',
    'description': """
Weighting Scale Hardware Driver
================================

This module allows the point of sale to connect to a scale using a USB HSM Serial Scale Interface,
such as the Mettler Toledo Ariva.

""",
    'author': 'OpenERP SA',
    'depends': ['hw_proxy'],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
}
