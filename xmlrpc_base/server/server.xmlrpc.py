#!/usr/bin/python
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
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import ConfigParser

# -----------------------------------------------------------------------------
#                                Parameters
# -----------------------------------------------------------------------------

config = ConfigParser.ConfigParser()
config.read(['./openerp.cfg'])

# XMLRPC server:
xmlrpc_host = config.get('XMLRPC', 'host') 
xmlrpc_port = eval(config.get('XMLRPC', 'port'))

# XMLRPC server:
odoo_host = config.get('ODOO', 'host') 
odoo_port = eval(config.get('ODOO', 'port'))
odoo_user = config.get('ODOO', 'user')
odoo_login = config.get('ODOO', 'login')

# TODO read parameter for operation from ODOO
# Parameters calculated:
# Transit files:
#file_cl = r'%s\production\%s' % (path, 'esito_cl.txt')

# Files for stock movement:
#file_move = r'%s\production\%s' % (path, 'move.txt')
# Note: result file are the same with 'esito_' before file name

#sprix_command = r'%s\mxdesk.exe -command=mxrs.exe
# -login=openerp -t0 -x2 win32g -p#%s -a%s -k%s:%s' % (
#    path, '%s', company_code, mx_user, mx_login)

# -----------------------------------------------------------------------------
#                         Restrict to a particular path
# -----------------------------------------------------------------------------
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# -----------------------------------------------------------------------------
#                                Create server
# -----------------------------------------------------------------------------
server = SimpleXMLRPCServer(
    (xmlrpc_host, xmlrpc_port), requestHandler=RequestHandler)
server.register_introspection_functions()

# -----------------------------------------------------------------------------
#                                 Functions
# -----------------------------------------------------------------------------
def execute(operation, context=None):
    ''' Execute method for call function (saved in ODOO)
    '''
    if context is None:
        context = {}

    # --------
    # Utility:
    # --------
    def read_result(transit_file, is_list=False):
        ''' Read result files
        '''
        try:
            res = ''
            res_file = open(transit_file, 'r')
            
            for item in res_file:
                res += res_file.read().strip()

            res_file.close()
            os.remove(transit_file)    
            return res                
        except:
            return False # for all errors    
        
    # -------------------------------------------------------------------------
    #                        Cases (operations):
    # -------------------------------------------------------------------------    
    # TODO read operation from ODOO
    
    if operation.upper() == 'CL': 
        # Call sprix for create CL:
        try:
            os.system('')#sprix_command % sprix_cl)            
        except:
            return '#Error launching importation CL command' # on error    
        
        # get result of operation:
        #return get_res(file_cl) 
    return False # error

# -----------------------------------------------------------------------------
#                  Register Function in XML-RPC server:
# -----------------------------------------------------------------------------
server.register_function(execute, 'execute')

# -----------------------------------------------------------------------------
#                       Run the server's main loop:
# -----------------------------------------------------------------------------
server.serve_forever()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

