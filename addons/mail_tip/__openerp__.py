##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 OpenERP SA (<http://openerp.com>).
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
    'name': 'Mail Tips',
    'category': 'Usability',
    'description': """
OpenERP link module for web tips.
=================================

""",
    'version': '0.1',
    'author': 'OpenERP SA',
    'depends': ['web_tip', 'mail'],
    'data': [
        'views/mail_tip.xml',
    ],
    'auto_install': True
}
