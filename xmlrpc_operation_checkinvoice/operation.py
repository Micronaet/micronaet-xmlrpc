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
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
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

class AccountInvoice(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'account.invoice'
  
    def dummy_button(self, cr, uid, ids, context=None):
        ''' For show an icon as a button
        '''
        return True

    def send_mail_checkinvoice_info(self, cr, uid, body, context=None):
        ''' Send mail message with body element passed
        '''
        # Pool used:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')

        group_id = model_pool.get_object_reference(
            cr, uid, 'xmlrpc_operation_checkinvoice', 'group_checkinvoice')[1]
    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
        
        thread_pool.message_post(
            cr, uid, False, body=body, partner_ids=[(6, 0, partner_ids)],
            subject='Check invoice mail database %s:' % cr.dbname, 
            #type='email',
            context=context)
        return
        
    # -------------------------------------------------------------------------
    #                            Scheduled event:
    # -------------------------------------------------------------------------
    def xmlrpc_export_checkinvoice(self, cr, uid, #year='2016', 
            diff= 0.000001, only_error=True, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        # ---------------------------------------------------------------------
        #                            Utility:
        # ---------------------------------------------------------------------
        def get_float(value):
            ''' Get value from file
            '''
            return float(value.strip().replace(',', '.') or '0')

        def get_date(value):
            ''' Get value from file
            '''
            if value:
                return '%s-%s-%s' % (value[:4], value[4:6], value[6:8])
            else:
                return False    
        
        def get_invoice_year(year, invoice_date, period_check):
            ''' For company 1 the invoice period from 01/09/2017 start from 
                this date so invoice will be: 2017S till 31/08/2017
                else nothing happend
                period_check for this case is '09' else '01'
                2 company: period check 01 and period check 09
                    for period check 09 use S in invoice in range:
                        01/09/2017 - 31/12/2017 after is normal year as before
            '''
            if period_check == '01' or invoice_date < '2017-09-01' \
                    or invoice_date > '2017-12-31':
                _logger.info('No S: %s, %s, %s' % (
                    year, invoice_date, period_check))
                return year # normal management

            # case '09' and date >= start period 2017-01-01
            if invoice_date[5:7] <= '12': # 09 >> 12 (current year)
                year = '%sS' % year
            else: # 01 > 09 (use last year)
                year = '%sS' % (int(year) - 1, ) 
            _logger.info('Yes S: %s, %s, %s' % (
                year, invoice_date, period_check))
            return year      
        # ---------------------------------------------------------------------
        #                            Procedure:
        # ---------------------------------------------------------------------
        # Pool used:
        parameter = {}
        parameter['input_file_string'] = ''
        filepath = '/home/administrator/photo/xls/check' # TODO parametrize
        f_out = open(
            os.path.join(filepath, '%s_invoice_check_%s.csv' % (
                cr.dbname,
                'error' if only_error else 'all',
                )), 'w')

        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'checkinvoice', parameter=parameter, context=context)
        result_string_file = res.get('result_string_file', False)
                
        if not result_string_file:
            raise osv.except_osv(
                _('Sync error:'), 
                _('Returned data: %s') % res,
                )                    
            return False

        # ---------------------------------------------------------------------
        # Read invoice data from file:
        # ---------------------------------------------------------------------
        acc_invoice = {}
        for line in result_string_file.split('\n'):
            if not line.strip():
                continue # jump empty line

            # Parser the line:
            line = line.split(';')
            
            doc = line[0].strip()
            series = line[1].strip()
            number = int(line[2].strip())
            partner_code = line[3].strip()
            amount = get_float(line[4])
            vat = get_float(line[5])
            #bank_expence = get_float(line[6])
            total = get_float(line[6])
            approx = get_float(line[7])
            pay_code = line[8].strip()
            agent_code = line[9].strip()
            partner_code = line[10].strip()
            year = line[11].strip()            
            # Manage fiscal year:
            invoice_date = get_date(line[12])
            period_check = line[13].strip()
            difference_total = get_float(line[14])
                        
            year = get_invoice_year(year, invoice_date, period_check)

            invoice = '%s/%s/%s/%04d' % (doc, series, year, number)
            if doc == 'NC':
                vat = -(vat)
                amount = -(amount)
                total = -(total)
                
            acc_invoice[invoice] = (
                amount, vat, total, approx, pay_code, 
                agent_code, partner_code,
                difference_total,
                )

        # ---------------------------------------------------------------------
        # Compare with invoice ODOO:
        # ---------------------------------------------------------------------
        # Control list:
        error = []
        
        invoice_ids = self.search(cr, uid, [
            ('type', 'in', ('out_invoice', 'out_refund')),
            # TODO check state? 
            ], context=context)
        
        header = 'Number|ID|Date|Status|Approx (Mx)|Imp. (ODOO)|Imp. (Mx)|' + \
            'Tax (ODOO)|Tax (Mx)|' + \
            'Total (ODOO)|Total (Mx)|' + \
            'Pay (ODOO)|Pay(Mx)|Partner (ODOO)|Partner (Mx)|' + \
            'Agent (ODOO)|Agent(Mx)|No tax|Diff. (Cont./Mag.)|Note\n'
                    
        # Normal row:    
        mask = '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\n'
        
        # No row:
        mask_no = '%s|%s|%s|%s\n'
            
        f_out.write(header)
        body_html = _('''            
            <p><b>Status database %s</b></p>
            <p>
                <table class="oe_list_content">
                    <tr><td class="oe_list_field_cell">%s</td></tr>
                    %s
                </table>
            </p>
            ''') % (
                cr.dbname,
                header.replace('|', '</td><td class="oe_list_field_cell">'),
                '%s',
                )
        body = ''
        
        for invoice in self.browse(
                cr, uid, invoice_ids, context=context):
            number = invoice.number or '' # TODO parse!

            untaxed = invoice.amount_untaxed or 0.0
            tax = invoice.amount_tax or 0.0
            total = invoice.amount_total or 0.0
            if invoice.type == 'out_refund':
                #if not number: # TODO
                # XXX error if not number:    
                number = number.replace('FT', 'NC')
                untaxed = -(untaxed)
                tax = -(tax)
                total = -(total)

            # From Account:
            if number in acc_invoice:
                row = acc_invoice[number]
                approx = row[3]
                if approx and invoice.type == 'out_refund': # NC
                    approx = -(approx)
            else:    
                approx = 0.0        
                row = ()

            partner_code = invoice.partner_id.sql_customer_code
            pay_code = '%s' % (invoice.payment_term.import_id or '')
            partner_code = invoice.partner_id.sql_customer_code or ''
            # TODO 2 test need to be eliminated and put in nc agent
            # Use a list of code (depend of what is used)
            agent_code = (
                invoice.mx_agent_id.sql_customer_code or '',
                invoice.mx_agent_id.sql_supplier_code or '',
                invoice.mx_agent_id.sql_agent_code or '',
                )
            agent_code_partner = (
                invoice.partner_id.agent_id.sql_customer_code or '',
                invoice.partner_id.agent_id.sql_supplier_code or '',
                invoice.partner_id.agent_id.sql_agent_code or '',
                )
            no_tax = self.check_invoice(invoice.invoice_line)
            state = invoice.state
            
            # -----------------------------------------------------------------
            # Check elements:
            # -----------------------------------------------------------------               
            status = ''
            
            # Isolated control:
            if no_tax: # Line tax
                status += _('(Tax line)')

            # Exclusive control:
            if state not in ('open', 'paid'): 
                # State check for confirmed (no other check)
                status += _('(Status: %s)') % state
            elif number not in acc_invoice: 
                # Check presence (no other check):
                status += _('(No invoice)')
            else:
                # Total control:
                if approx:
                    # With approx:
                    if abs(row[2] - approx - total) > diff:
                        status = _('(Total approx)')
                    elif abs(tax - row[1]) > diff:
                        status = _('(Total approx but VAT)')
                        
                elif abs(untaxed - row[0]) > diff or abs(tax - row[1]) > diff \
                        or abs(total - row[2]) > diff:
                    # Without approx:    
                    status = _('(Total)')
                
                # Add in controls:    
                if pay_code != row[4]: 
                    # Agent test
                    status += _('(Payment)')

                if partner_code != row[6]: 
                    # Partner test
                    status += _('(Partner)')
                
                # Agent check:
                if not row[5] and not invoice.mx_agent_id: 
                    pass # ok no agent
                else:    
                    if row[5] in agent_code:
                        pass # Agent present
                    elif row[5] in agent_code_partner:
                        # Agent test
                        status += _('(Agent inv.)')
                    else:
                        status += _('(Agent)')
                        
                # Difference account - stock in accounting prog.        
                if row[7]: 
                    status += _('(Diff. cont/mag.)')

            if only_error and not status:
                continue # no error so jump write
                
            if row:
                row_item = mask % (
                    # Header data:
                    number, invoice.id, invoice.date_invoice,
                    status, approx,
                    # Check data:
                    untaxed, row[0],
                    tax, row[1],
                    total, row[2],              
                    pay_code, row[4],
                    partner_code, row[6],
                    filter(None, agent_code + agent_code_partner), row[5],
                    no_tax, row[7],
                    invoice.xmlrpc_note or '',
                    )                        
            else: 
                # Not present:
                row_item = mask_no % (
                    number, invoice.id, invoice.date_invoice, status)

            body += '<tr><td class="oe_list_field_cell">%s</td></tr>' % (
                row_item.replace('|', '</td><td class="oe_list_field_cell">'))
            f_out.write(row_item)
        f_out.close()

        # For problem of concurrent write:
        cr._cnx.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
        body_html = body_html % body
        self.send_mail_checkinvoice_info(cr, uid, body_html, context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
