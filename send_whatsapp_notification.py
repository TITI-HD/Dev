#!/usr/bin/env python3
"""
SCRIPT COMPLET DE SURVEILLANCE WORDPRESS (LOOP AUTOMATIQUE)
- Boucle toutes les 30 minutes
- Retry automatique (3 tentatives)
- Logs détaillés (HTTP status, headers)
- Alertes Email & WhatsApp pour chaque tentative et modification
- Sauvegarde et comparaison contenu (homepage, RSS, commentaires)
- Historique log dans monitor.log
"""

import os
import smtplib
import requests
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from time import sleep
from twilio.rest import Client

# ===============================
# 🔧 CONFIGURATION
# ===============================
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")
SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "yjrg wrxu cgmt erpw")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
ALERT_PHONE_NUMBER = os.environ.get("ALERT_PHONE_NUMBER", "")
BACKUP_DIR = "backups"
LOG_FILE = "monitor.log"
RETRY_COUNT = 3
RETRY_DELAY = 5  # secondes
LOOP_INTERVAL = 1800  # 30 minutes

# Validation port SMTP
try:
    SMTP_PORT = int(SMTP_PORT) if SMTP_PORT and SMTP_PORT.strip() else 587
except ValueError:
    SMTP_PORT = 587

# ===============================
# 📜 UTILITAIRES LOG
# ===============================
def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ===============================
# 📱 Notification WhatsApp
# ===============================
def send_whatsapp_notification(message: str):
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, ALERT_PHONE_NUMBER]):
        log("⚠️ Twilio non configuré, WhatsApp ignoré")
        return False
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
            body=message,
            to=f'whatsapp:{ALERT_PHONE_NUMBER}'
        )
        log(f"✅ WhatsApp envoyé: {msg.sid}")
        return True
    except Exception as e:
        log(f"❌ Erreur WhatsApp: {e}")
        return False

# ===============================
# 📧 Notification Email
# ===============================
def send_alert(subject: str, message: str, whatsapp_priority: bool = False):
    if all([SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_EMAIL]):
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_USER
            msg["To"] = ALERT_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
            log(f"✅ Email envoyé à {ALERT_EMAIL} - {subject}")
        except Exception as e:
            log(f"❌ Erreur Email: {e}")
    else:
        log("⚠️ SMTP non configuré, Email ignoré")

    if whatsapp_priority:
        send_whatsapp_notification(f"🚨 {subject}\n{message[:500]}...")

# ===============================
# 🔍 Vérification site et API avec retries
# ===============================
def check_site(url: str) -> bool:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(url, timeout=10)
            log(f"Tentative {attempt} - HTTP {r.status_code}, Headers={dict(r.headers)}")
            send_alert(f"Tentative {attempt} - Vérif Site", f"Status HTTP: {r.status_code}")
            if r.status_code == 200:
                return True
        except requests.RequestException as e:
            log(f"❌ Tentative {attempt} échouée: {e}")
            send_alert(f"Tentative {attempt} - Vérif Site échouée", f"Erreur: {e}")
        sleep(RETRY_DELAY)
    send_alert("🚨 Site WordPress Inaccessible", f"Impossible d'atteindre {url} après {RETRY_COUNT} tentatives", whatsapp_priority=True)
    return False

def check_api(url: str) -> bool:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(url.rstrip("/") + "/wp-json/", timeout=10)
            log(f"Tentative API {attempt} - HTTP {r.status_code}")
            send_alert(f"Tentative {attempt} - Vérif API", f"Status HTTP: {r.status_code}")
            if r.status_code == 200:
                return True
        except requests.RequestException as e:
            log(f"❌ API tentative {attempt} échouée: {e}")
            send_alert(f"Tentative {attempt} - Vérif API échouée", f"Erreur: {e}")
        sleep(RETRY_DELAY)
    send_alert("🚨 API REST Inaccessible", f"Impossible d'atteindre {url}/wp-json/ après {RETRY_COUNT} tentatives", whatsapp_priority=True)
    return False

# ===============================
# 💾 Sauvegarde et comparaison
# ===============================
def save_content(url, filename):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text
    except Exception as e:
        send_alert("🚨 Erreur sauvegarde", f"{url}: {e}", whatsapp_priority=True)
        return None

def compare_files(old_file, new_file):
    if not os.path.exists(old_file):
        return ""
    with open(old_file, encoding="utf-8") as f1, open(new_file, encoding="utf-8") as f2:
        diff = difflib.unified_diff(f1.readlines(), f2.readlines())
    return "".join(diff)

def backup_and_monitor():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    homepage_file = os.path.join(BACKUP_DIR, f"homepage_{date_str}.html")
    rss_file = os.path.join(BACKUP_DIR, f"rss_{date_str}.xml")
    comments_file = os.path.join(BACKUP_DIR, f"comments_{date_str}.xml")

    homepage = save_content(SITE_URL, homepage_file)
    rss = save_content(f"{SITE_URL}/feed", rss_file)
    comments = save_content(f"{SITE_URL}/comments/feed", comments_file)

    # Homepage diff
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("homepage_")])
    if len(files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, files[-2]), homepage_file)
        if diff:
            send_alert("📝 Changement Page d'Accueil", f"Modifications détectées:\n{diff[:1500]}")

    # RSS diff
    rss_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("rss_")])
    if len(rss_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, rss_files[-2]), rss_file)
        if diff:
            send_alert("🆕 Nouvel Article", f"Diff RSS:\n{diff[:1000]}", whatsapp_priority=True)

    # Comments diff
    comments_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("comments_")])
    if len(comments_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, comments_files[-2]), comments_file)
        if diff:
            send_alert("💬 Nouveau Commentaire", f"Diff Commentaires:\n{diff[:800]}")

# ===============================
# 🚀 Fonction principale
# ===============================
def main_loop():
    while True:
        log(f"🔍 Démarrage surveillance: {SITE_URL}")
        log(f"📧 Email alerte: {ALERT_EMAIL}")
        log(f"📱 WhatsApp configuré: {'OUI' if TWILIO_ACCOUNT_SID else 'NON'}")

        site_ok = check_site(SITE_URL)
        api_ok = check_api(SITE_URL)

        if site_ok and api_ok:
            log(f"✅ {SITE_URL} en ligne & API REST OK")
            backup_and_monitor()
            log("✅ Surveillance cycle terminée")
        else:
            log(f"❌ {SITE_URL} ou API REST inaccessible")

        log(f"⏱ Prochain cycle dans {LOOP_INTERVAL//60} minutes...\n")
        sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    main_loop()
