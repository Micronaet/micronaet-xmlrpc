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
            if operation != 'partner':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('partner', parameter)
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
    _inherit = 'res.partner'
  
    def dummy_button(self, cr, uid, ids, context=None):
        ''' For show an icon as a button
        '''
        return True
        
    def xmlrpc_export_partner(self, cr, uid, ids, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!

        # TODO use with validate trigger for get the number
        parameter = {}
        
        # Generate string for export file:
        mask = '%1s%1s%1s%-60s%-15s%-40s%-5s%-40s%-4s%-40s%-40s%-40s%-40s%-40s%-40s%-40s\r\n' # Win CR
        parameter['input_file_string'] = ''
        
        for partner in self.browse(cr, uid, ids, context=context):
            # --------------------------
            # Check manatory parameters:
            # --------------------------
            # yet sync
            if partner.xmlrpc_sync:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Partner yet sync!'))

            # company or address
            if not partner.is_company and not partner.is_address:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Partner need to be company or address'))
            
            # there's SQL code
            if partner.sql_customer_code or \
                    partner.sql_supplier_code or \
                    partner.sql_destination_code:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Partner with sync code, need empty (SQL)!'))

            # Vat not present
            if not partner.vat:
                raise osv.except_osv(
                    _('XMLRPC sync error'), 
                    _('Partner mandatory field not present: vat!'))
            
            # TODO check multi vat on database:


            # ------------------
            # Create parameters:
            # ------------------
            parameter['input_file_string'] += self.pool.get(
                'xmlrpc.server').clean_as_ascii(
                    mask % (                        
                        'X' if partner.customer else '',
                        'X' if partner.supplier else '',
                        'X' if partner.is_address else '', # TODO destination
                        partner.name[:60],
                        partner.vat,                            
                        ('%s %s' % (partner.street, partner.street2))[:40],
                        partner.zip[:5],
                        partner.city[:40],
                        (partner.state_id.code or '')[:4],
                        (partner.country_id.name or '')[:40],                        
                        partner.website[:40],
                        partner.phone[:40],
                        partner.mobile[:40],
                        partner.fax[:40],
                        partner.email[:40],
                        partner.discount_rates[:40],
                        ))

        res =  self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'partner', parameter=parameter, context=context)
            
        result_string_file = res.get('result_string_file', False)
        if result_string_file:
            if result_string_file.startswith('OK'):
                res = result_string_file.split(';')
                if len(res) != 3:
                    raise osv.except_osv(
                        _('XMLRPC sync error'), 
                        _('Error reading result operation!'))

                self.write(cr, uid, ids[0], {
                    'xmlrpc_sync': True,
                    'sql_customer_code': res[0],
                    'sql_supplier_code': res[1],
                    'sql_destination_code': res[2],
                    }, context=context)                    
                # TODO send email to accounting people    
                #user = self.pool.get("res.users").browse(cr, uid, 1)
                #user.message_post(context=context, body="Hi, this message is showing up in the wrong place")

                #post_vars = {'subject': "Message subject",
                #             'body': "Message body",
                #             'partner_ids': [(4, 3)],} # Where "4" adds the ID to the list 
                                                       # of followers and "3" is the partner ID 
                #thread_pool = self.pool.get('mail.thread')
                #thread_pool.message_post(
                #        cr, uid, False,
                #        type="notification",
                #        subtype="mt_comment",
                #        context=context,
                #        **post_vars)

                return True

            else: # raise error passed:
                raise osv.except_osv(
                    _('Sync error:'), 
                    _('Returned data: %s') % res,
                    )
                    
        # TODO write better error
        raise osv.except_osv(
            _('Sync error:'), 
            _('Cannot sync with accounting! (return esit not present)'),
            )
        return False
    
    _columns = {
        'xmlrpc_sync': fields.boolean('XMLRPC syncronized'),        
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
