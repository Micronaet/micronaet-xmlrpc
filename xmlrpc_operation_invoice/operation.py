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
    """ Model name: XmlrpcOperation
    """
    _inherit = 'xmlrpc.operation'

    # ------------------
    # Override function:
    # ------------------
    def execute_operation(self, cr, uid, operation, parameter, context=None):
        """ Virtual function that will be overrided
            operation: in this module is 'invoice'
            context: xmlrpc context dict
        """
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
    """ Add export function to invoice obj
    """
    _inherit = 'account.invoice'

    def xmlrpc_export_scheduled(self, cr, uid, ids, context=None):
        """ Schedule for import
        """
        return self.write(cr, uid, ids, {
            'xmlrpc_scheduled': True,
            }, context=context)

    def xmlrpc_export_unscheduled(self, cr, uid, ids, context=None):
        """ Schedule for import
        """
        return self.write(cr, uid, ids, {
            'xmlrpc_scheduled': False,
            }, context=context)

    def _xmlrpc_clean_description(self, value, cut):
        """ Remove \n and \t and return first 'cut' char
        """
        value = value.replace('\n', ' ')
        value = value.replace('\r', '')
        value = value.replace('\t', ' ')
        if cut:
            return value[:cut]
        else:
            return value

    def dummy_button(self, cr, uid, ids, context=None):
        """ For show an icon as a button
        """
        return True

    def reset_xmlrpc_export_invoice(self, cr, uid, ids, context=None):
        """ Remove sync status
        """
        assert len(ids) == 1, 'No multi export for now' # TODO remove!!!
        _logger.warning('Reset sync invoice: %s' % ids[0])
        return self.write(cr, uid, ids, {
            'xmlrpc_sync': False}, context=context)

    def xmlrpc_export_invoice(self, cr, uid, ids, context=None):
        """ Export current invoice
            # TODO manage list of invoices?
        """
        def get_comment_line(self, parameter, value):
            """ Split line in comment line max 60 char
            """
            value = (value or u'').strip()

            # -----------------------------------------------------------------
            # Replace some not ASCII char:
            # -----------------------------------------------------------------
            value = value.replace(u'€', u'EUR ')
            value = value.replace(u'  ', u' ')
            value = value.replace(u'®', u' (R)')
            value = value.replace(u'™', u' TM')

            while value: # Split in 60 char:
                # TODO change filler space
                parameter['input_file_string'] += self.pool.get(
                    'xmlrpc.server').clean_as_ascii(
                        '%44sD%16s%-60s%235s\r\n' % (
                            '',
                            '',
                            self._xmlrpc_clean_description(
                                value, 60),  # Remove \n
                            '',
                            ))
                value = value[60:]
            return True

        # ---------------------------------------------------------------------
        # Start procedure:
        # ---------------------------------------------------------------------
        if context is None:
            context = {}
        start_hour_default = '08:00'  # Always 8

        assert len(ids) == 1, 'No multi export for now'  # TODO remove!!!

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
        mask = '%s%s%s%s%s' % (  # 3 block for readability:
            '%-2s%-2s%-6s%-8s%-2s%-8s%-8s%-8s', # header
            '%-1s%-16s%-60s%-2s%10.2f%10.3f%-5s%-5s%-50s%-10s%-8s%1s%-8s%-8s', # row
            '%-2s%-20s%-10s%-8s%-24s%-1s%-16s%-1s%-10s%-10s',  # Fattura PA
            '%-3s%-13s',  # foot
            '\r\n',  # Win CR
            )

        parameter['input_file_string'] = ''
        last_picking = False  # Last picking for reference:

        for invoice_temp in self.browse(cr, uid, ids, context=context):
            # Reload invoice with partner lang:
            context['lang'] = invoice_temp.partner_id.lang or 'it_IT'
            invoice = self.browse(cr, uid, invoice_temp.id, context=context)

            partner = invoice.partner_id
            if not invoice.number:
                raise osv.except_osv(
                    _('XMLRPC sync error'),
                    _('Invoice must be validated!'))

            # -----------------------------------------------------------------
            # Note pre document:
            # -----------------------------------------------------------------
            if invoice.text_note_pre:
                get_comment_line(self, parameter, invoice.text_note_pre)

            ddt_number = ddt_date = ddt_destination = ''
            i_ddt = 0
            last_ddt = False
            previous_picking = False
            for line in invoice.invoice_line:
                # -------------------------------------------------------------
                # Order, Partner order, DDT reference:
                # -------------------------------------------------------------
                # destination (if not present DDT used invoice code):
                ddt_destination = invoice.partner_id.sql_destination_code or ''

                picking = line.generator_move_id.picking_id

                if picking and (not last_picking or last_picking != picking):
                    last_picking = picking # Save for not print again
                    # get_comment_line(self, parameter,
                    #    picking_pool.write_reference_from_picking(picking))
                    if picking.ddt_id: # If DDT is present
                        ddt = picking.ddt_id
                        ddt_number_block = ddt.name.split('/')
                        ddt_number = '%s-%s' % (
                            ddt_number_block[1], ddt_number_block[-1])
                        ddt_destination = \
                            ddt.destination_partner_id.sql_destination_code
                        ddt_date = ddt.date[:10]

                        # If DDT Block print ID:
                        if not last_ddt or ddt_number != last_ddt:
                            i_ddt += 1
                            last_ddt = ddt_number

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

                # -------------------------------------------------------------
                # Note pre line:
                # -------------------------------------------------------------
                if line.text_note_pre:
                    for block in line.text_note_pre.split('\n'):
                        get_comment_line(self, parameter, block)

                # -------------------------------------------------------------
                # Fattura PA "long" fields:
                # -------------------------------------------------------------
                product = line.product_id

                # Description:
                if line.use_text_description:
                    description = line.name or ''
                else:
                    description = product.name or ''

                # -------------------------------------------------------------
                # Invoice field "needed" Fattura PA:
                # -------------------------------------------------------------
                goods_description = \
                    invoice.goods_description_id.account_ref or ''
                carriage_condition = \
                    invoice.carriage_condition_id.account_ref or ''
                transportation_reason = \
                    invoice.transportation_reason_id.account_ref or ''
                transportation_method = \
                    invoice.transportation_method_id.account_ref or ''
                carrier_code = \
                    invoice.default_carrier_id.partner_id.sql_supplier_code \
                        or ''
                parcels = '%s' % invoice.parcels

                # TODO check error:
                # Direct invoice: goods, carriage, transportation, method
                if invoice.default_carrier_id and not carrier_code:
                    raise osv.except_osv(
                        _('XMLRPC error'),
                        _('Carrier need Account code!'))

                # -------------------------------------------------------------
                # LAST BLOCK: Reference for order / DDT yet writed:
                # -------------------------------------------------------------
                if not previous_picking and picking:
                    previous_picking = picking

                if previous_picking != picking:
                    get_comment_line(
                        self, parameter,
                        picking_pool.write_reference_from_picking(picking))
                    previous_picking = picking

                # Start transport:
                start_transport = invoice.start_transport or ''
                if start_transport:
                    start_transport = start_transport[:10].replace(
                        ' ', '').replace('-', '').replace('/', '')
                    start_transport += start_hour_default

                # -------------------------------------------------------------
                #                         DATA LINE:
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
                            # Destination code (8)
                            invoice.destination_partner_id.sql_destination_code or '',
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
                            ('%s' % (product.weight_net or '')).replace(
                                '.', ',')[:8],

                            # -------------------------------------------------
                            # Extra data for Fattura PA
                            # -------------------------------------------------
                            i_ddt,
                            ddt_number,
                            ddt_date.replace('-', ''),
                            ddt_destination,  # or invoice if DDT not present

                            # -------------------------------------------------
                            # Extra data for invoice:
                            # -------------------------------------------------
                            goods_description,
                            carriage_condition,
                            transportation_reason,
                            transportation_method,
                            carrier_code,
                            parcels,

                            # -------------------------------------------------
                            #                     Foot:
                            # -------------------------------------------------
                            # Codice Pagamento 3
                            invoice.payment_term.import_id \
                                if invoice.payment_term else '',
                            start_transport,

                            # TODO bank
                            ))

                # -------------------------------------------------------------
                # Fattura PA "long" fields:
                # -------------------------------------------------------------
                product = line.product_id
                # Extra data for Fattura PA:

                # 1. Description long:
                if len(description) > 60:
                    get_comment_line(self, parameter,
                        self._xmlrpc_clean_description(description[60:], 220))

                # 2. Color:
                get_comment_line(self, parameter,
                    self._xmlrpc_clean_description(product.colour or '', 220))

                # 3. FSC Certified:
                if product.fsc_certified_id and company.fsc_certified and \
                        company.fsc_from_date<= invoice.date_invoice:
                    get_comment_line(self, parameter,
                        self._xmlrpc_clean_description(
                            product.fsc_certified_id.text or '', 220))

                # 4. PEFC Certified:
                if product.pefc_certified_id and company.pefc_certified and \
                        company.pefc_from_date<= invoice.date_invoice:
                    get_comment_line(self, parameter,
                        self._xmlrpc_clean_description(
                            product.pefc_certified_id.text or '', 220))

                # 5. Partic:
                if invoice.partner_id.use_partic:
                    partic = product_pool._xmlrpc_get_partic_description(
                        cr, uid, product.id, invoice.partner_id.id,
                        context=context)
                    get_comment_line(self, parameter,
                        self._xmlrpc_clean_description(partic, 220))

                # -------------------------------------------------------------
                # Note post line:
                # -------------------------------------------------------------
                if line.text_note_post:
                    get_comment_line(self, parameter, line.text_note_post)

            # -----------------------------------------------------------------
            # End document dat
            # -----------------------------------------------------------------
            # BEFORE ALL:
            if previous_picking:  # Always write last line comment:
                get_comment_line(self, parameter,
                    picking_pool.write_reference_from_picking(picking))

            # A. End note comment:
            if invoice.text_note_post:
                text = invoice.text_note_post
                for block in text.split('\n'):
                    get_comment_line(self, parameter, block)

            # B. Text note for account position
            text = partner.property_account_position.text_note_invoice or ''
            if text:
                text = picking_pool._parser_template_substitute(invoice, text)
                for block in text.split('\n'):
                    get_comment_line(self, parameter, block)

            # C. Text comment for account position
            text = partner.property_account_position.text_comment_invoice or ''
            if text:
                text = picking_pool._parser_template_substitute(invoice, text)
                for block in text.split('\n'):
                    get_comment_line(self, parameter, block)

            # D. FSC PEFC Certified:
            try:
                if company.fsc_certified or company.pefc_certified:
                    text = company.xfc_document_note
                    for block in text.split('\n'):
                        get_comment_line(self, parameter, block)
            except:
                pass # no FSC Management

            # E. Split payment:
            try:
                if partner.split_payment:
                    text = \
                        'Operazione soggetta alla scissione dei pagamenti. ' +\
                        'Art. 17 ter DPR633/72'
                    get_comment_line(self, parameter, text)
            except:
                pass # no Split Payment Management

            # F. Force vector
            try:
                if invoice.force_vector:
                    text = 'Vettore:\n%s' % invoice.force_vector.strip()
                    for block in text.split('\n'):
                        get_comment_line(self, parameter, block)
            except:
                pass # Error do nothing

            # G. Private partner:
            #try:
            #    if partner.is_private:
            #        text = "COPIA, IL DOCUMENTO FISCALMENTE VALIDO E' " + \
            #            "ESCLUSIVAMENTE QUELLO DISPONIBILE NELL'AREA " + \
            #            "RISERVATA DELL'AGENZIA DELLE ENTRATE"
            #        get_comment_line(self, parameter, text)
            #except:
            #    pass # no Partner private

            # H. Force vector
            try:
                privacy_policy = (
                    invoice.company_id.privacy_policy or '').strip()
                if privacy_policy:
                    text = 'Privacy: %s' % privacy_policy
                    for block in text.split('\n'):
                        get_comment_line(self, parameter, block)
            except:
                pass # Error do nothing

        # XXX Remove used for extract file:
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
                    'xmlrpc_scheduled': False,
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
        'xmlrpc_scheduled': fields.boolean(
            'XMLRPC Schedulata',
            help='Schedulata per importazione automatica'),
        'xmlrpc_note': fields.text('XMLRPC note'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
