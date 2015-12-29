# -*- coding: utf-8 -*-
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
import os
import sys
import logging
import openerp
import xmlrpclib
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class XmlrpcOperation(orm.Model):
    ''' Model name: XmlrpcOperation
    '''    
    _inherit = 'xmlrpc.operation'

    # ------------------
    # Override function:
    # ------------------
    def execute_operation(self, cr, uid, operation, parameter, context=None):
        ''' Virtual function that will be overrided
            operation: in this module is 'invoice'
            context: xmlrpc context dict
        '''
        try:
            import pdb; pdb.set_trace()
            if operation != 'invoice':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('invoice', parameter)
            if res['error']:
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))

        return True
    
class AccountInvoice(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'account.invoice'

    def xmlrpc_export_invoice(self, cr, uid, ids, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        xmlrpc_ctx = {}
        
        # Generate string for export file:
        #                                |                                     | 
        mask = '%2s%2s%6s%8s%2s%8s%8s%60s%1s%15s%60s%2s%10.2f%10.3f%5s%5s%50s%8s%3s%40s\r\n'
        xmlrpc_ctx['input_file_string'] = ''
        for invoice in self.browse(cr, uid, ids, context=context):
            for line in invoice.invoice_line:
                xmlrpc_ctx['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(
                        mask % (                        
                            # -------
                            # Header:
                            # -------
                            'FT', # TODO # Sigla documento 2
                            '1', # TODO #Serie documento 2
                            invoice.name, # TODO clean Numero documento 6N
                            invoice.date_invoice, #Data documento 8
                            '', # TODO # Causale 2 # 99 different
                            invoice.partner_id.sql_customer_code, # Codice cliente 8
                            '', # TODO #Codice Agente 8
                            '', # TODO #[Descrizione agente 60] ????

                            # -------
                            # Detail:
                            # -------
                            'R', # Tipo di riga 1 (D, R, T)
                            line.product_id.default_code, #Codice articolo 15
                            line.product_id.name, #Descrizione articolo 60
                            line.product_id.uom_id.name,  # TODO #Unità di misura 2
                            line.quantity, #Quantità 10N(2 decimali)
                            line.price_unit, #Prezzo netto 10N(3 decimali)
                            line.invoice_line_tax_id[0].name,  # TODO #Aliquota 5
                            0, # Provvigione 5
                            line.discount, #Sconto 50
                            '', # Contropartita 8

                            # -----
                            # Foot:
                            # -----
                            invoice.payment_term.import_id, # Codice Pagamento 3
                            invoice.payment_term.name, # Descrizione pagamento 40
                            ))

        self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'invoice', parameter=xmlrpc_ctx, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
