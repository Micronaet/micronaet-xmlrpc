#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import sys
import ConfigParser
import erppeek
import smtplib, ssl
from datetime import datetime
from email.MIMEMultipart import MIMEMultipart
from email.mime.text import MIMEText

config_folder = './config'
log_folder = './log'
pidfile = '/tmp/invoicepa_daemon.pid'
log_exec_file = './log/execution.log'


# -----------------------------------------------------------------------------
# Function:
# -----------------------------------------------------------------------------
def write_log(log_f, message, mode='info'):
    """ Log on file
    """
    log_f.write('%s - [%s] %s\n' % (
        datetime.now(),
        mode.upper(),
        message,
    ))


# -----------------------------------------------------------------------------
# Check multi execution:
# -----------------------------------------------------------------------------
log_exec_f = open(log_exec_file, 'a')

# A. Check if yet running:
pid = str(os.getpid())
if os.path.isfile(pidfile):
    message = '\n[%s] Invoice Daemon already running [%s]\n' % (pid, pidfile)
    write_log(
        log_exec_f, message, 'error')
    print(message)
    sys.exit()
else:
    write_log(log_exec_f, '[%s] Invoice Daemon running [%s]' % (pid, pidfile))

# B. Create PID file:
pid_f = open(pidfile, 'w')
pid_f.write(pid)
pid_f.close()

# -----------------------------------------------------------------------------
# Script:
# -----------------------------------------------------------------------------
try:
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

            # -----------------------------------------------------------------
            # Log file:
            # -----------------------------------------------------------------
            log_file = os.path.join(log_folder, '%s.log' % dbname)
            log_f = open(log_file, 'a')
            write_log(log_f, 'Inizio importazione')

            # -----------------------------------------------------------------
            # Connect to ODOO:
            # -----------------------------------------------------------------
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

            # -----------------------------------------------------------------
            # SMTP:
            # -----------------------------------------------------------------
            # Create a secure SSL context
            context = ssl.create_default_context()
            
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

            if odoo_mailer.smtp_encryption == 'ssl':
                smtp_server = smtplib.SMTP_SSL(
                    odoo_mailer.smtp_host,
                    odoo_mailer.smtp_port,
                )
            elif odoo_mailer.smtp_encryption == 'starttls':
                import pdb; pdb.set_trace()
                smtp_server = smtplib.SMTP(smtp_server,port)
                smtp_server.ehlo() # Can be omitted
                smtp_server.starttls(context=context) # Secure the connection
                ssmtp_servererver.ehlo() # Can be omitted
            else:
                print('[ERR] %s. Connect only SMTP SSL server!' % dbname)
                break
            smtp_server.login(odoo_mailer.smtp_user, odoo_mailer.smtp_pass)

            # -----------------------------------------------------------------
            # Import invoice:
            # -----------------------------------------------------------------
            while True:  # Read every time for the undo process in ODOO
                error_comment = ''
                invoice_ids = invoice_pool.search([
                    ('xmlrpc_scheduled', '=', True),
                    ('xmlrpc_sync', '=', False),
                    ('id', 'not in', error),
                    ])

                if not invoice_ids:
                    print('[WARN] %s. No invoice scheduled' % dbname)
                    break

                invoice_id = invoice_ids[-1]  # Always the last
                invoice = invoice_pool.browse(invoice_id)
                number = invoice.number
                partner = invoice.partner_id
                destination = invoice.destination_partner_id

                # Before check:
                try:
                    if not partner.sql_customer_code:
                        error_comment = \
                            'Fattura senza il codice cliente Mexal %s' % \
                            number
                        email_text.append(error_comment)
                    elif destination and not destination.sql_destination_code:
                        error_comment = \
                            'Fattura senza il codice destinazione Mexal %s' % \
                            number
                        email_text.append(error_comment)
                    elif not invoice_pool.xmlrpc_export_invoice([invoice_id]):
                        error_comment = 'Invoice %s not imported (managed)' % \
                            number
                except:
                    print('%s' % (sys.exc_info(), ))
                    error_comment = 'Invoice %s not imported (unmanaged)' % \
                        number

                if error_comment:
                    print('[ERROR] %s. %s' % (dbname, error_comment))
                    error.append(invoice_id)
                    email_text.append('Fattura non importata: %s' % number)
                    write_log(
                        log_f, 'Non importata la fattura: %s' % number,
                        'error')
                else:
                    print('[INFO] %s Invoice %s imported' % (dbname, number))
                    email_text.append('Fattura importata: %s' % number)
                    write_log(log_f, 'Importata la fattura: %s' % number)

            if email_text:  # Every database:
                recipients = recipients.replace(' ', '')
                for to in recipients.split(','):
                    print('Sending mail to: %s ...' % to)
                    msg = MIMEMultipart()
                    msg['Subject'] = \
                        'Importazione automatica fatture: %s' % dbname
                    msg['From'] = odoo_mailer.smtp_user
                    msg['To'] = recipients
                    msg.attach(MIMEText('<br/>\n'.join(email_text), 'html'))

                    # Send mail:
                    smtp_server.sendmail(
                        odoo_mailer.smtp_user, to, msg.as_string())
                write_log(log_f, 'Invio mail: %s' % (to, ))
                smtp_server.quit()
            write_log(log_f, 'Fine importazione\n')
            log_f.close()
        break  # No more config file read
finally:
    os.unlink(pidfile)
    write_log(log_exec_f, '[%s] Invoice Daemon stopped [%s]\n' % (pid, pidfile))
    log_exec_f.close()
