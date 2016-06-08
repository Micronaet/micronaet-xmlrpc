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
            if operation != 'invoice':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('invoice', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class AccountInvoice(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'account.invoice'
  
    def dummy_button(self, cr, uid, ids, context=None):
        ''' For show an icon as a button
        '''
        return True
        
    def reset_xmlrpc_export_invoice(self, cr, uid, ids, context=None):
        ''' Remove sync status
        '''
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!
        _logger.warning('Reset sync invoice: %s' % ids[0])
        return self.write(cr, uid, ids, {
            'xmlrpc_sync': False}, context=context)

    def xmlrpc_export_invoice(self, cr, uid, ids, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        def clean_description(value):
            ''' Remove \n and \t and return first 40 char
            ''' 
            value = value.replace('\n', ' ')            
            value = value.replace('\t', ' ') 
            return value[:40]
            
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # TODO use with validate trigger for get the number
        parameter = {}
        
        # Generate string for export file:
        mask = '%s%s%s%s' % ( #3 block for readability:
            '%-2s%-2s%-6s%-8s%-2s%-8s%-8s', #header
            '%-1s%-16s%-60s%-2s%10.2f%10.3f%-5s%-5s%-50s%-10s%-8s%1s', #row
            '%-3s', #foot
            '\r\n', # Win CR
            )

        parameter['input_file_string'] = ''
        for invoice in self.browse(cr, uid, ids, context=context):
            if not invoice.number:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Invoice must be validated!'))
                
            for line in invoice.invoice_line:
                try: # Module: invoice_payment_cost (not in dep.)
                    refund_line = 'S' if line.refund_line else ' '
                except:
                    refund_line = ' '    
                parameter['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(
                        mask % (                        
                            # -------------------------------------------------
                            #                    Header:
                            # -------------------------------------------------
                            # Doc (2)
                            invoice.journal_id.account_code,
                            # Serie (2)
                            invoice.journal_id.account_serie,
                            # N.(6N) # val.
                            int(invoice.number.split('/')[-1]), 
                            # Date (8)
                            '%s%s%s' % (
                                invoice.date_invoice[:4], 
                                invoice.date_invoice[5:7], 
                                invoice.date_invoice[8:10], 
                                ),
                            # Transport reason (2)    
                            invoice.transportation_reason_id.import_id or '', 
                            # Customer code (8)
                            invoice.partner_id.sql_customer_code or '', 
                            # Agent code (8)
                            invoice.mx_agent_id.sql_agent_code or \
                                invoice.mx_agent_id.sql_supplier_code or '',

                            # -------------------------------------------------
                            #                    Detail:
                            # -------------------------------------------------
                            # Tipo di riga 1 (D, R, T)
                            'R',
                            # Code (16)
                            line.product_id.default_code or '', 
                            # Description (60)
                            clean_description(
                                line.name if line.use_text_description \
                                    else line.product_id.name),
                            # UOM (2)
                            line.product_id.uom_id.account_ref or '',
                            # Q. 10N (2 dec.)
                            line.quantity, 
                            # Price 10N (3 dec.)
                            line.price_unit, 
                            # Tax (5)
                            line.invoice_line_tax_id[0].account_ref \
                                if line.invoice_line_tax_id else '', 
                            # Provv. (5)
                            0, 
                            # Discount (50)
                            line.multi_discount_rates or '',
                            # Discount numeric (10)
                            line.discount or '',
                            # Account (8)
                            line.account_id.account_ref or '', 
                            # Refund (1)
                            refund_line,

                            # -------------------------------------------------
                            #                     Foot:
                            # -------------------------------------------------
                            # Codice Pagamento 3
                            invoice.payment_term.import_id \
                                if invoice.payment_term else '', 
                            # TODO bank
                            ))

        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'invoice', parameter=parameter, context=context)
            
        result_string_file = res.get('result_string_file', False)
        if result_string_file:
            if result_string_file.startswith('OK'):
                # TODO test if number passed if for correct invoice number!
                self.write(cr, uid, ids, {
                    'xmlrpc_sync': True,
                    }, context=context)
                return True
        # TODO write better error
        raise osv.except_osv(
            _('Sync error:'), 
            _('Cannot sync with accounting! (return esit not present'),
            )
        return False
    
    _columns = {
        'xmlrpc_sync': fields.boolean('XMLRPC syncronized'),        
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
