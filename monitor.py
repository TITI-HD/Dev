#!/usr/bin/env python3
"""
SCRIPT DE SURVEILLANCE WORDPRESS - VERSION NETTOYÉE SANS WHATSAPP
"""

import os
import smtplib
import requests
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# ===================== CONFIGURATION =====================
SITE_URL = os.getenv("SITE_URL", "https://oupssecuretest.wordpress.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")

RETRY_COUNT = 3
RETRY_DELAY = 5
LOG_FILE = "monitor.log"
BACKUP_DIR = "backups"
MAX_DIFF_LENGTH = 1500

# ===================== LOGGING =====================
def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as f:
        f.write(line + "\n")

# ===================== ALERTES =====================
def send_alert(subject: str, body: str):
    """Envoie une alerte par Email uniquement"""
    log(f"🚨 ALERTE: {subject}")

    # Limiter la longueur du contenu
    if len(body) > MAX_DIFF_LENGTH:
        body = body[:MAX_DIFF_LENGTH] + "\n... [diff tronqué]"

    # Email
    if all([SMTP_SERVER, SMTP_USER, SMTP_PASS, ADMIN_EMAIL]):
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_USER
            msg["To"] = ADMIN_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ADMIN_EMAIL, msg.as_string())
            log("📧 Email envoyé avec succès")
        except Exception as e:
            log(f"❌ Erreur envoi email: {e}")
    else:
        log("⚠️ SMTP non configuré, Email ignoré")

# ===================== WRAPPER POUR TEST =====================
def send_whatsapp_notification(message: str):
    """
    Wrapper pour tests unitaires existants.
    Supprime la logique WhatsApp, ne fait qu'envoyer un email.
    """
    send_alert("Notification WhatsApp (wrapper)", message)

# ===================== CHECK SITE =====================
def check_site(url: str) -> bool:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, timeout=10, headers=headers)
            log(f"Tentative {attempt} - HTTP {r.status_code}")
            if r.status_code == 200:
                return True
            elif 500 <= r.status_code < 600:
                log(f"⚠️ Erreur serveur (5xx): {r.status_code}")
                return False
            else:
                log(f"⚠️ Code HTTP inattendu: {r.status_code}")
                return False
        except requests.RequestException as e:
            log(f"❌ Tentative {attempt} échouée: {e}")
        sleep(RETRY_DELAY)
    send_alert("🚨 Site WordPress Inaccessible", f"Impossible d'atteindre {url} après {RETRY_COUNT} tentatives")
    return False

# ===================== COMPARAISON & SAUVEGARDE =====================
def compare_files(old_file, new_file) -> str:
    if not os.path.exists(old_file):
        return f"⚠️ {old_file} introuvable, création du fichier."
    with open(old_file, encoding="utf-8", errors="ignore") as f1, \
         open(new_file, encoding="utf-8", errors="ignore") as f2:
        diff = list(difflib.unified_diff(f1.readlines(), f2.readlines(), fromfile=old_file, tofile=new_file))
        return "\n".join(diff)

def save_content(url: str, filename: str):
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            new_file = os.path.join(BACKUP_DIR, filename + ".new")
            with open(new_file, "w", encoding="utf-8", errors="ignore") as f:
                f.write(r.text)
            old_file_path = os.path.join(BACKUP_DIR, filename)
            diff = compare_files(old_file_path, new_file)
            if diff:
                send_alert(f"⚠️ Contenu modifié: {filename}", diff)
            os.replace(new_file, old_file_path)
            log(f"✅ Sauvegarde réussie: {filename}")
        else:
            log(f"❌ Erreur HTTP {r.status_code} sur {url}")
    except Exception as e:
        log(f"❌ Erreur sauvegarde {url}: {e}")

def backup_and_monitor():
    save_content(SITE_URL, "homepage.html")
    save_content(SITE_URL + "/feed/", "rss.xml")
    save_content(SITE_URL + "/comments/feed/", "comments.xml")

# ===================== RESTAURATION =====================
def send_restoration_option(alert_type, details):
    subject = f"🚨 {alert_type} - Action Requise"
    body = f"""
{alert_type} détecté sur {SITE_URL}
Détails: {details}

Options disponibles:
1. Restaurer automatiquement maintenant
2. Ignorer et surveiller
3. Contacter l'administrateur
"""
    send_alert(subject, body)
    log(f"🔧 Option de restauration proposée pour: {alert_type}")

# ===================== MAIN =====================
def main():
    log(f"🚀 Démarrage surveillance: {SITE_URL}")
    log(f"📧 Email alerte: {ADMIN_EMAIL}")

    try:
        requests.get("https://httpbin.org/status/200", timeout=5)
        log("✅ Connexion internet vérifiée")
    except:
        log("❌ Pas de connexion internet")
        send_alert("🚨 Pas de connexion internet", "Impossible de se connecter à internet")
        return False

    site_ok = check_site(SITE_URL)
    if site_ok:
        log(f"✅ {SITE_URL} en ligne")
        backup_and_monitor()
        log("✅ Surveillance terminée")
        return True
    else:
        log(f"❌ Problème détecté (site)")
        send_restoration_option("Problème de site", f"Site: {site_ok}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
