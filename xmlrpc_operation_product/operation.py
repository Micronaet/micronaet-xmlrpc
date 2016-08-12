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
            operation: in this module is 'product'
            context: xmlrpc context dict
        '''
        try:
            if operation != 'product':
                # Super call for other cases:
                return super(XmlrpcOperation, self).execute_operation(
                    cr, uid, operation, parameter, context=context)
                    
            server_pool = self.pool.get('xmlrpc.server')
            xmlrpc_server = server_pool.get_xmlrpc_server(
                cr, uid, context=context)
            res = xmlrpc_server.execute('product', parameter)
            if res.get('error', False):
                _logger.error(res['error'])
                # TODO raise
            # TODO confirm export!    
        except:    
            _logger.error(sys.exc_info())
            raise osv.except_osv(
                _('Connect error:'), _('XMLRPC connecting server'))
        return res
    
class ProductProduct(orm.Model):
    ''' Add export function to invoice obj
    '''    
    _inherit = 'product.product'
  
    def dummy_button(self, cr, uid, ids, context=None):
        ''' For show an icon as a button
        '''
        return True
        
    def xmlrpc_export_product(self, cr, uid, ids, context=None):
        ''' Export current invoice 
            # TODO manage list of invoices?
        '''
        assert len(ids) == 1, 'No multi product export for now' # TODO 
        context = context or {}

        _logger.info('Start XMLRPC sync for product')
        sync_type = context.get('sync_type', False) 
        if not sync_type:
            raise osv.except_osv(
                _('XMLRPC sync error'), 
                _('Error on button sync product'))

        parameter = {}
        
        # Generate string for export file:        
        mask = '%-60s\n' # Win CR # TODO
        
        parameter['input_file_string'] = ''        
        product = self.browse(cr, uid, ids, context=context)

        # ---------------------------------------------------------------------
        #                     Check manatory parameters:
        # ---------------------------------------------------------------------
        # yet sync
        if product.xmlrpc_sync:
            raise osv.except_osv(
                _('XMLRPC sync error'), 
                _('Product yet sync!'))
        # TODO other check for product manatory fields?

        # ------------------
        # Create parameters:
        # ------------------
        parameter['input_file_string'] += self.pool.get(
            'xmlrpc.server').clean_as_ascii(
                mask % (                   
                    # Anagraphic data:
                    product.name[:60],
                    # TODO
                    ))

        _logger.info('Data: %s' % (parameter, ))
        res = self.pool.get('xmlrpc.operation').execute_operation(
            cr, uid, 'product', parameter=parameter, context=context)
        result_string_file = res.get('result_string_file', False)
        if not result_string_file:
            raise osv.except_osv(
                _('Sync error:'), 
                _('Cannot sync with accounting! (return esit not present)'),
                )
        
        if result_string_file.startswith('OK'):
            message = 'Product sync in accounting'
            self.message_post(cr, uid, ids, message, context=context)
            # TODO send email to accounting people    
            #post_vars = {'subject': "Message subject",
            #             'body': "Message body",
            #             'partner_ids': [(4, 3)],}
            # Where "4" adds the ID to the list 
            # of followers and "3" is the partner ID 
            #thread_pool = self.pool.get('mail.thread')
            #thread_pool.message_post(
            #        cr, uid, False,
            #        type="notification",
            #        subtype="mt_comment",
            #        context=context,
            #        **post_vars)
            return True # END PROCEDURE!
        else: # raise error passed:
            raise osv.except_osv(
                _('Sync error:'), 
                _('Returned data: %s') % res,
                )
    
    _columns = {
        'xmlrpc_sync': fields.boolean('XMLRPC syncronized'), # TODO remove
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
