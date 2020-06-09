#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# use: partner.py file_csv_to_import

# Modules required:
import os
import sys
import ConfigParser
import erppeek
import smtplib
from email.MIMEMultipart import MIMEMultipart
# from email.MIMEBase import MIMEBase
from email.mime.text import MIMEText
# from email import Encoders

config_folder = './config'
for root, folders, files in os.walk(config_folder):
    for cfg_file in files:
        if not cfg_file.endswith('cfg'):
            print('No config file: %s' % cfg_file)
            continue

        error = []  # reset for every database
        email_text = []  # List of importation

        config = ConfigParser.ConfigParser()
        config.read([os.path.join(root, cfg_file)])
        dbname = config.get('dbaccess', 'dbname')
        user = config.get('dbaccess', 'user')
        pwd = config.get('dbaccess', 'pwd')
        server = config.get('dbaccess', 'server')
        port = config.get('dbaccess', 'port')

        recipients = config.get('SMTP', 'recipients')

        # ---------------------------------------------------------------------
        # Connect to ODOO:
        # ---------------------------------------------------------------------
        import pdb;

        pdb.set_trace()
        odoo = erppeek.Client(
            'http://%s:%s' % (
                server, port),
            db=dbname,
            user=user,
            password=pwd,
            )

        # Pool used:
        invoice_pool = odoo.model('account.invoice')
        mailer = odoo.model('ir.mail_server')
        group = odoo.model('res.groups')

        # ---------------------------------------------------------------------
        # SMTP:
        # ---------------------------------------------------------------------
        mailer_ids = mailer.search([])
        if not mailer_ids:
            print('[ERR] No mail server configured in ODOO %s' % dbname)
            break

        odoo_mailer = mailer.browse(mailer_ids)[0]
        print('[INFO] Sending using "%s" connection [%s:%s]' % (
            odoo_mailer.name,
            odoo_mailer.smtp_host,
            odoo_mailer.smtp_port,
            ))

        if odoo_mailer.smtp_encryption in ('ssl', 'starttls'):
            smtp_server = smtplib.SMTP_SSL(
                odoo_mailer.smtp_host,
                odoo_mailer.smtp_port,
            )
        else:
            print('[ERR] %s. Connect only SMTP SSL server!' % dbname)
            break
            # server_smtp.start() # TODO Check
        smtp_server.login(odoo_mailer.smtp_user, odoo_mailer.smtp_pass)

        # ---------------------------------------------------------------------
        # Import invoice:
        # ---------------------------------------------------------------------
        import pdb; pdb.set_trace()
        while True:  # Read every time for the undo process in ODOO
            error_comment = ''
            invoice_ids = invoice_pool.search([
                ('xmlrpc_scheduled', '=', True),
                ('xmlrpc_sync', '=', False),
                ('id', 'not in', error),
                ])

            if not invoice_ids:
                print('[WARNING] %s. No invoice scheduled for import' % dbname)
                break

            invoice_id = invoice_ids[-1]  # Always the last
            invoice = invoice_pool.browse(invoice_id)
            number = invoice.number
            try:
                if not invoice_pool.xmlrpc_export_invoice([invoice_id]):
                    error_comment = 'Invoice %s not imported (managed)' % \
                        number
            except:
                print('%s' % (sys.exc_info(),))
                error_comment = 'Invoice %s not imported (unmanaged)' % \
                    number

            if error_comment:
                print('[ERROR] %s. %s' % (dbname, error_comment))
                error.append(invoice_id)
                email_text.append('Fattura non importata: %s' % number)
                # TODO sent mail?
            else:
                print('[INFO] %s Invoice %s imported' % (dbname, number))
                email_text.append('Fattura importata: %s' % number)

        if email_text:  # Every database:
            # TODO sent mail imported invoice
            recipients = recipients.replace(' ', '')
            for to in recipients.split(','):
                print('Senting mail to: %s ...' % to)
                msg = MIMEMultipart()
                msg['Subject'] = 'Importazione automatica fatture: %s' % dbname
                msg['From'] = odoo_mailer.smtp_user
                msg['To'] = recipients
                msg.attach(MIMEText('<br/>\n'.join(email_text), 'html'))

                # Send mail:
                smtp_server.sendmail(
                    odoo_mailer.smtp_user, to, msg.as_string())

            smtp_server.quit()
    break  # No more config file read
