##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
    'name' : 'Authentication via LDAP',
    'version' : '1.0',
    'depends' : ['base'],
    'images' : ['images/ldap_configuration.jpeg'],
    'author' : 'OpenERP SA',
    #'description': < auto-loaded from README file
    'website' : 'https://www.odoo.com',
    'category' : 'Authentication',
    'data' : [
        'users_ldap_view.xml',
        'user_ldap_installer.xml',
        'security/ir.model.access.csv',
    ],
    'auto_install': False,
    'installable': True,
    'external_dependencies' : {
        'python' : ['ldap'],
    }
}
