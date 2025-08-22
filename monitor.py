#!/usr/bin/env python3
"""
Script de surveillance pour WordPress.com
"""

import os
import requests
import smtplib
from twilio.rest import Client
from datetime import datetime

# Configuration
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")

def check_site_availability(url):
    """Vérifie si le site est accessible"""
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_email_alert(subject, message):
    """Envoie une alerte par email"""
    try:
        # Configuration SMTP
        server = smtplib.SMTP(os.environ.get('SMTP_SERVER'), os.environ.get('SMTP_PORT'))
        server.starttls()
        server.login(os.environ.get('SMTP_USER'), os.environ.get('SMTP_PASS'))
        
        # Envoi du message
        email_message = f"Subject: {subject}\n\n{message}"
        server.sendmail(os.environ.get('SMTP_USER'), os.environ.get('ALERT_EMAIL'), email_message)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False

def send_whatsapp_alert(message):
    """Envoie une alerte WhatsApp"""
    try:
        client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
        message = client.messages.create(
            body=message,
            from_=os.environ.get('TWILIO_WHATSAPP_FROM'),
            to=os.environ.get('TWILIO_WHATSAPP_TO')
        )
        return True
    except Exception as e:
        print(f"❌ Erreur envoi WhatsApp: {e}")
        return False

def main():
    """Fonction principale de surveillance"""
    print("👀 Démarrage de la surveillance...")
    
    # Vérifier la disponibilité du site
    is_available = check_site_availability(SITE_URL)
    
    if is_available:
        print("✅ Site accessible")
    else:
        print("❌ Site inaccessible")
        # Envoyer des alertes
        alert_message = f"🚨 Site {SITE_URL} inaccessible à {datetime.now()}"
        
        # Envoyer email si configuré
        if all(key in os.environ for key in ['SMTP_SERVER', 'SMTP_USER', 'SMTP_PASS', 'ALERT_EMAIL']):
            send_email_alert("Alerte de surveillance WordPress", alert_message)
        
        # Envoyer WhatsApp si configuré
        if all(key in os.environ for key in ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_FROM', 'TWILIO_WHATSAPP_TO']):
            send_whatsapp_alert(alert_message)
    
import time

while True:
    # Votre code de monitoring ici
    print("🔍 Vérification du site...")
    # ... code existant ...
    print("✅ Site accessible - Prochaine vérification dans 5 minutes")
    time.sleep(300)  # 300 secondes = 5 minutes

if __name__ == "__main__":
    main()