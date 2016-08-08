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
            if operation != 'checkinvoice':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('checkinvoice', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class ResPartner(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'res.partner' # TODO change or ... not...
  
    def dummy_button(self, cr, uid, ids, context=None):
        ''' For show an icon as a button
        '''
        return True

    # Button:    
    def xmlrpc_export_checkinvoice(self, cr, uid, ids, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        # Utility:
        def get_float(value):
            ''' Get value from file
            '''
            return float(value.strip().replace(',', '.') or '0')
        
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # Pool used:
        invoice_pool = self.pool.get('account.invoice')
        parameter = {}
        parameter['input_file_string'] = ''
        f_out = open('/home/thebrush/Scrivania/fatture_check.csv', 'w')

        result_string_file = ''
        # TODO remove after debug:
        for row in open('/home/thebrush/Scrivania/fattureGPB.csv'):
            result_string_file += row            
        #res = self.pool.get('xmlrpc.operation').execute_operation(
        #    cr, uid, 'checkinvoice', parameter=parameter, context=context)            
        #result_string_file = res.get('result_string_file', False)
                
        if result_string_file:
            # -----------------------------------------------------------------
            # Read invoice data from file:
            # -----------------------------------------------------------------
            acc_invoice = {}
            diff = 0.00001 # min diff for consider equal
            year = '2016' # TODO change
            for line in result_string_file.split('\n'):            
                if not line.strip():
                    continue # jump empty line
                
                # -------------------------------------------------------------
                # Parser the line:
                # -------------------------------------------------------------
                line = line.split(';')
                
                doc = line[0].strip()
                series = line[1].strip()
                number = int(line[2].strip())
                invoice = '%s/%s/%s/%04d' % (doc, series, year, number)
                partner_code = line[3].strip()
                amount = get_float(line[4])
                vat = get_float(line[5])
                bank_expense = get_float(line[6])
                total = get_float(line[7])
                approx = get_float(line[8])
                pay_code = line[9].strip()
                agent_code = line[10].strip()
                
                acc_invoice[invoice] = (
                    amount, # 0
                    vat, # 1
                    total, # 2 
                    approx, # 3 
                    bank_expense, # 4
                    pay_code, # 5
                    agent_code, # 6
                    )

            # --------------------------
            # Compare with invoice ODOO:
            # --------------------------
            # Control list:
            error = []
            
            invoice_ids = invoice_pool.search(cr, uid, [
                #('state', 'in', ('open', 'paid'))
                ], context=context)
            
            f_out.write(
                'Number;Status;Imp. (ODOO);Imp. (Mx);Tax (ODOO);Tax (Mx);' + \
                'Total (ODOO);Total (Mx);Approx (Mx);' + \
                'Bank expence (Mx);Pay (ODOO);Pay(Mx);Agent (ODOO);' + \
                'Agent(Mx)')
            for invoice in invoice_pool.browse(
                    cr, uid, invoice_ids, context=context):                    
                number = invoice.number # TODO parse!
                untaxed = invoice.amount_untaxed or 0.0
                tax = invoice.amount_tax or 0.0
                total = invoice.amount_total or 0.0
                partner_code = invoice.partner_id.sql_customer_code
                pay_code = '%s' % (invoice.payment_term.import_id or '')
                agent_code = (
                    invoice.mx_agent_id.sql_agent_code or \
                    invoice.mx_agent_id.sql_supplier_code or \
                    #invoice.partner_id.sql_agent_code or \
                    #invoice.partner_id.sql_customer_code or \
                    ''
                    )
                state = invoice.state                
                
                # -------------------------------------------------------------
                # Check elements:
                # -------------------------------------------------------------
                row = acc_invoice.get(number, ())
                
                if state not in ('open', 'paid'): # State check for confirmed
                    status = 'Status'

                if number not in acc_invoice: # Check presence:
                    status = 'No invoice'

                elif abs(untaxed - row[0]) > diff or abs(tax - row[1]) > diff \
                        or abs(total - row[2]) > diff:
                    # Difference on totals:
                    status = 'Total'
                    
                elif pay_code != row[5]: # Agent test
                    status = 'Payment'    

                elif agent_code != row[6]: # Agent test
                    status = 'Agent'
                
                else:
                    status = ''    
                
                if row:
                    f_out.write(
                        '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % (
                            number,
                            status,
                            
                            untaxed, # ODOO
                            row[0], # Accounting
                            
                            tax, # ODOO
                            row[1], # Accounting
                            
                            total, # ODOO
                            row[2], # Accounting
                            
                            row[3], # Approx only account
                            row[4], # Bank expence
                           
                            pay_code, # ODOO
                            row[5], # Pay
                            
                            agent_code, # ODOO
                            row[6], # Agent                            
                            ))
                            
                else: # row not present:
                    f_out.write('%s;%s;\n' % (
                        number,
                        status,
                        ))
            return True

        else: # raise error passed:
            raise osv.except_osv(
                _('Sync error:'), 
                _('Returned data: %s') % res,
                )                    
            return False
    
    _columns = {
        'xmlrpc_sync': fields.boolean('XMLRPC syncronized'),        
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
