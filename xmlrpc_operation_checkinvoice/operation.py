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
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # Pool used:
        invoice_pool = self.pool.get('account.invoice')
        parameter = {}
        parameter['input_file_string'] = ''

        res =  self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'checkinvoice', parameter=parameter, context=context)
            
        result_string_file = res.get('result_string_file', False)
        if result_string_file:
            # -----------------------------------------------------------------
            # Read invoice data from file:
            # -----------------------------------------------------------------
            acc_invoice = {}
            import pdb; pdb.set_trace()            
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
                number = line[2].strip()                
                invoice = '%s/%s/%s/%04d' % (doc, series, year, number)

                partner_code = float(line[3].strip())                
                amount = float(line[4].strip().replace(',', '.') or '0')
                vat = float(line[5].strip().replace(',', '.') or '0')
                total = float(line[6].strip().replace(',', '.') or '0')
                approx = float(line[7].strip() or '0')
                acc_invoice[invoice] = (amount, vat, total, approx)

            # --------------------------
            # Compare with invoice ODOO:
            # --------------------------
            # Control list:
            error = []
            
            invoice_ids = invoice_pool.search(cr, uid, [], context=context)
            for invoice in invoice_pool.browse(
                    cr, uid, invoice_ids, context=context):
                name = invoice.name # TODO parse!
                untaxed = invoice.amount_untaxed
                tax = invoice.amount_tax
                if name not in acc_invoice:
                    error += '%s not present in account\n' % name
                    continue
                if untaxed != acc_invoice[name][0] or \
                        tax != acc_invoice[name][0]:
                    error += '%s. difference: [%s - %s] [%s - %s]\n' % (
                        name,
                        'TODO', # TODO
                        'TODO', # TODO
                        'TODO', # TODO
                        'TODO', # TODO
                        )

                    invoice_different.append(name) # TODO better data!
                    
            # Compare with invoice in odoo
            #if len(res) != 3:
            #    raise osv.except_osv(
            #        _('XMLRPC sync error'), 
            #        _('Error reading result operation!'))
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
