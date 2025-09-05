# send_alert_email.py
import smtplib
import argparse
from email.mime.text import MIMEText

parser = argparse.ArgumentParser()
parser.add_argument('--to', required=True)
parser.add_argument('--subject', required=True)
parser.add_argument('--smtp-server', required=True)
parser.add_argument('--smtp-port', type=int, required=True)
parser.add_argument('--smtp-user', required=True)
parser.add_argument('--smtp-pass', required=True)
args = parser.parse_args()

msg = MIMEText("Échec de la sauvegarde WordPress.")
msg["Subject"] = args.subject
msg["From"] = args.smtp_user
msg["To"] = args.to

with smtplib.SMTP(args.smtp_server, args.smtp_port) as server:
    server.starttls()
    server.login(args.smtp_user, args.smtp_pass)
    server.send_message(msg)
