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

# TODO log operations!!
class XmlrpcServer(orm.Model):
    ''' Model name: XmlrpcServer
    '''    
    _name = 'xmlrpc.server'
    _description = 'XMLRPC Server'
    
    def clean_as_ascii(self, value):
        ''' Procedure for clean not ascii char in string
        '''
        res = ''
        for c in value:
            if ord(c) <127:
                res += c
            else:
                res += '#'           
        return res
        
    def get_xmlrpc_server(self, cr, uid, context=None):
        ''' Connect with server and return obj
        '''
        server_ids = self.search(cr, uid, [], context=context)
        if not server_ids:
            return False
        
        server_proxy = self.browse(cr, uid, server_ids, context=context)[0]
        
        try:
            xmlrpc_server = 'http://%s:%s' % (
                server_proxy.host, server_proxy.port)
        except:
            return False
        return xmlrpclib.ServerProxy(xmlrpc_server)

    def get_default_company(self, cr, uid, context=None): 
        ''' If only one use that
        '''
        try:
            company_ids = self.pool.get('res.company').search(
                cr, uid, [], context=context)            
            if len(company_ids) == 1:
                return company_ids[0]
        except:    
            pass
        return False    
        
    _columns = {
        'name': fields.char('Operation', size=64, required=True),
        'host': fields.char('Input filename', size=100, required=True),
        'port': fields.integer('Port', required=True),
        # TODO authentication?

        'company_id': fields.many2one('res.company', 'Company', required=True),         
        'note': fields.text('Note'),
        }

    _defaults = {
        'host': lambda *x: 'localhost',
        'port': lambda *x: 8069,
        'company_id': lambda s, cr, uid, ctx: s.get_default_company(
            cr, uid, ctx),
        }    

class XmlrpcOperation(orm.Model):
    ''' Model name: XmlrpcOperation
    '''    
    _name = 'xmlrpc.operation'
    _description = 'XMLRPC Operation'
    
    def execute_operation(self, cr, uid, operation, parameter, context=None):
        ''' Virtual function that will be overrided
        '''
        return True
        
    _columns = {
        'demo': fields.boolean('Demo mode'),
        'name': fields.char('Operation', size=64, required=True),
        #'operation': fields.char('ID Operation', size=64, required=True),
        'shell_command': fields.char('Shell command', size=120),
        'input_filename': fields.char('Input filename', size=100),
        'input_path': fields.char('Input path', size=180),
        'result_filename': fields.char('Result filename', size=100),
        'result_path': fields.char('Result path', size=180),
        'note': fields.text('Note'),
        }        
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
