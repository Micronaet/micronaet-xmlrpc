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
import erpeek # for request VS ODOO

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
odoo_db = config.get('ODOO', 'db')
odoo_user = config.get('ODOO', 'user')
odoo_password = config.get('ODOO', 'password')


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
def execute(operation, parameter=None):
    ''' Execute method for call function (saved in ODOO)
        operation: name of operation (searched in odoo xmlrpc.operation obj
        parameter: dict with extra parameter
            > input_file_string: text of input file
            
        @return: dict with parameter:
            error: if there's an error during operation
            result_string_file: output file returned as a string
    '''
    # Setup dict:
    parameter = parameter or {}
    res = {}

    # ---------------------------------------------------------------------
    #                 Read operation in ODOO (no cases here)
    # ---------------------------------------------------------------------
    erp = erppeek.Client(
        'http://%s:%s' % (odoo_host, odoo_port),
        db=odoo_db, user=odoo_user, password=odoo_password)
    
    operation_pool = erp.XmlrpcOperation
    context = operation_pool.read_parameter(operation) 
    # Read parameters:
    #   > shell_command
    #   > input_filename
    #   > result_filename
    
    if not context:
        res['error'] = 'No input context (check operation parameter in ODOO)!'
        return res

    # ---------------------------------------------------------------------
    #                         Execute operation: 
    # ---------------------------------------------------------------------
    # Create input file with string passed:
    try:
        # Read parameters:
        input_file_string = parameter.get('input_file_string', False)
        input_filename = context.get('input_filename', False)
        
        # Check if it's present:
        if input_file_string and input_filename:
           input_file = open(input_filename, 'w')
           input_file.write(input_file_string) # TODO \r problems?!?
           input_file.close()
    except:
        res['error'] = 'Error creating input file'
        return res
    
    # Execute shell script:
    try:
        os.system(context.get('shell_command')) # Launch sprix
    except:
        res['error'] = 'Error launch shell command'
        return res

    # Read result:
    try:
        result_filename = context.get('result_filename', False)
        if result_filename:
           res['result_string_file'] = ''
           res_file = open(result_filename, 'r')
        
            for line in res_file:
                res['result_string_file'] += '%s\n' % line

            res_file.close()
            os.remove(result_filename) # TODO history?
    except:
        res['error'] = 'Error reading result file'
        return res

    # ---------------------------------------------------------------------
    #                           Return result:
    # ---------------------------------------------------------------------
    return res

# -----------------------------------------------------------------------------
#                  Register Function in XML-RPC server:
# -----------------------------------------------------------------------------
server.register_function(execute, 'execute')

# -----------------------------------------------------------------------------
#                       Run the server's main loop:
# -----------------------------------------------------------------------------
server.serve_forever()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

