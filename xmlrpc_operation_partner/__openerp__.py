###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

{
    'name': 'XMLRPC Operation Partner',
    'version': '0.1',
    'category': 'ETL',
    'description': '''        
        XMLRPC Import partner
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'xmlrpc_base',
        'sql_partner', # for fields to update
        'l10n_it_private', # private info
        'mx_partner_zone', # zone
        # 'l10n_it_iban_cin'
        'base_accounting_program', # for type_id field
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        #'operation.xml',        
        'partner_view.xml',
        'data/operation.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
