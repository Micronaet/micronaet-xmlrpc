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
  
    def _xmlrpc_clean_description(self, value, cut):
        ''' Remove \n and \t and return first 60 char
        ''' 
        value = value.replace('\n', ' ')            
        value = value.replace('\r', '')
        value = value.replace('\t', ' ')
        if cut:
            return value[:cut]
        else:
            return value    

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
        def get_comment_line(self, parameter, value):
            ''' Split line in comment line max 60 char
            '''
            value = (value or '').strip()
            
            while value: # Split in 60 char:
                # TODO change filler space
                parameter['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(
                        '%36sD%16s%-60s%1242s\r\n' % (
                            '',
                            '',
                            self._xmlrpc_clean_description(
                                value, 60),# Remove \n 
                            '',
                            ))
                value = value[60:]
            return True

        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # TODO use with validate trigger for get the number
        parameter = {}

        # ---------------------------------------------------------------------        
        # Access company record for extra parameters:
        # ---------------------------------------------------------------------        
        picking_pool = self.pool.get('stock.picking')
        product_pool = self.pool.get('product.product')
        company_pool = self.pool.get('res.company')
        
        company_ids = company_pool.search(cr, uid, [], context=context)
        company = company_pool.browse(cr, uid, company_ids, context=context)[0]
        
        # Generate string for export file:
        mask = '%s%s%s%s%s' % ( #3 block for readability:
            '%-2s%-2s%-6s%-8s%-2s%-8s%-8s', #header
            '%-1s%-16s%-60s%-2s%10.2f%10.3f%-5s%-5s%-50s%-10s%-8s%1s%-8s', #row
            '%-220s%-220s%-220s%-220s%-220s%-20s%-10s', # Fattura PA
            '%-3s', #foot
            '\r\n', # Win CR
            )

        parameter['input_file_string'] = ''
        last_picking = False # Last picking for reference:
        for invoice in self.browse(cr, uid, ids, context=context):
            if not invoice.number:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Invoice must be validated!'))
    
            # -----------------------------------------------------------------                
            # Note pre document:
            # -----------------------------------------------------------------                
            if invoice.text_note_pre:
                get_comment_line(self, parameter, invoice.text_note_pre)

            ddt_number = ddt_date = ''
            for line in invoice.invoice_line:
                # -----------------------------------------------------------------                
                # Order, Partner order, DDT reference:
                # -----------------------------------------------------------------                
                picking = line.generator_move_id.picking_id
                if picking and (not last_picking or last_picking != picking):
                    last_picking = picking # Save for not print again
                    get_comment_line(self, parameter,
                        picking_pool.write_reference_from_picking(picking))
                    ddt_number = picking.ddt_id.name[:20]
                    ddt_date = picking.ddt_id.date[:10]
                
                try: # Module: invoice_payment_cost (not in dep.)
                    refund_line = 'S' if line.refund_line else ' '
                except:
                    refund_line = ' '
                    
                if invoice.mx_agent_id: # Agent set up in document
                    agent_code = invoice.mx_agent_id.sql_agent_code or \
                        invoice.mx_agent_id.sql_supplier_code or ''
                else: # use partner one's
                    agent_code = invoice.partner_id.agent_id.sql_agent_code \
                         or invoice.partner_id.agent_id.sql_supplier_code or ''

                # -----------------------------------------------------------------                
                # Note pre line:
                # -----------------------------------------------------------------                
                if line.text_note_pre:
                    get_comment_line(self, parameter, line.text_note_pre)
                
                # -------------------------------------------------------------
                # Fattura PA extra fields:
                # -------------------------------------------------------------
                product = line.product_id
                # Extra data for Fattura PA:
                # 1. Description long:
                if line.use_text_description:
                    description = line.name or ''  
                else:
                    description = product.name or ''
                
                # 2. Color:
                colour = (product.colour or '').strip()[:220]
                
                # 3. FSC Certified:
                if product.fsc_certified_id and company.fsc_certified and \
                        company.fsc_from_date<= invoice.date_invoice:
                    fsc = product.fsc_certified_id.text or ''
                else:
                    fsc = ''

                # 4. PEFC Certified:
                if product.pefc_certified_id and company.pefc_certified and \
                        company.pefc_from_date<= o.date_invoice:
                    pefc = product.pefc_certified_id.text or ''
                else:
                    pefc = ''

                # 5. Partic:
                if invoice.partner_id.use_partic:
                    partic = product_pool._xmlrpc_get_partic_description(
                        cr, uid, product.id, invoice.partner_id.id, 
                        context=context)
                else:
                    partic = ''
                
                # -------------------------------------------------------------
                
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
                            agent_code,

                            # -------------------------------------------------
                            #                    Detail:
                            # -------------------------------------------------
                            # Tipo di riga 1 (D, R, T)
                            'R',
                            # Code (16)
                            product.default_code or '', 
                            # Description (60)
                            self._xmlrpc_clean_description(description, 60),
                            # UOM (2)
                            product.uom_id.account_ref or '',
                            # Q. 10N (2 dec.)
                            line.quantity, 
                            # Price 10N (3 dec.)
                            line.price_unit, 
                            # Tax (5)
                            line.invoice_line_tax_id[0].account_ref \
                                if line.invoice_line_tax_id else '', 
                            # Provv. (5)
                            0, 
                            
                            # Previous block discount:
                            # Discount (50)
                            line.multi_discount_rates or '',
                            # Discount numeric (10)
                            ('%s' % (line.discount or '')).replace('.', ','),

                            # Account (8)
                            line.account_id.account_ref or '', 
                            # Refund (1)
                            refund_line,
                            (product.duty_code or '')[:8], # Duty (8) 

                            # -------------------------------------------------
                            # Extra data for Fattura PA
                            # -------------------------------------------------
                            # TODO
                            self._xmlrpc_clean_description(description, 220),
                            self._xmlrpc_clean_description(colour, 220),
                            self._xmlrpc_clean_description(fsc, 220),
                            self._xmlrpc_clean_description(pefc, 220),
                            self._xmlrpc_clean_description(partic, 220),
                            ddt_number,
                            ddt_date,

                            # -------------------------------------------------
                            #                     Foot:
                            # -------------------------------------------------
                            # Codice Pagamento 3
                            invoice.payment_term.import_id \
                                if invoice.payment_term else '', 
                            # TODO bank
                            ))

                # -----------------------------------------------------------------                
                # Note pre line:
                # -----------------------------------------------------------------                
                if line.text_note_post:
                    get_comment_line(self, parameter, line.text_note_post)

            # -----------------------------------------------------------------                
            # Note post document:
            # -----------------------------------------------------------------                
            if invoice.text_note_post:
                get_comment_line(self, parameter, invoice.text_note_post)

        #open('/home/thebrush/prova.csv', 'w').write(
        #    parameter['input_file_string'])
        #return False
        
        
        
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
            else:    
                raise osv.except_osv(
                    _('Error import invoice:'), 
                    _('Comment: %s' % result_string_file),
                    )
            
        # TODO write better error
        raise osv.except_osv(
            _('Sync error:'), 
            _('Cannot sync with accounting! (return esit not present'),
            )
        return False
    
    _columns = {
        'xmlrpc_sync': fields.boolean('XMLRPC syncronized'),        
        'xmlrpc_note': fields.text('XMLRPC note'),        
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
