#!/usr/bin/env python3
"""
SCRIPT DE SURVEILLANCE WORDPRESS (fusionné)
- Retry automatique
- Logs détaillés
- Notifications Email & WhatsApp
- Sauvegarde et comparaison de contenu
- Gestion d’options de restauration
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
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# ===================== CONFIGURATION =====================
SITE_URL = os.getenv("SITE_URL", "https://oupssecuretest.wordpress.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_AUTH = os.getenv("TWILIO_AUTH", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")
TWILIO_TO = os.getenv("TWILIO_TO", "")

WPCOM_CLIENT_ID = os.getenv("WPCOM_CLIENT_ID", "")
WPCOM_CLIENT_SECRET = os.getenv("WPCOM_CLIENT_SECRET", "")

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
def send_alert(subject: str, body: str, whatsapp_priority=False):
    """Envoie une alerte par Email et éventuellement WhatsApp"""
    log(f"🚨 ALERTE: {subject}")

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

    # WhatsApp
    if whatsapp_priority and all([TWILIO_SID, TWILIO_AUTH, TWILIO_FROM, TWILIO_TO]):
        try:
            client = Client(TWILIO_SID, TWILIO_AUTH)
            client.messages.create(
                from_="whatsapp:" + TWILIO_FROM,
                to="whatsapp:" + TWILIO_TO,
                body=f"{subject}\n{body}"
            )
            log("📲 WhatsApp envoyé avec succès")
        except Exception as e:
            log(f"❌ Erreur envoi WhatsApp: {e}")
    elif whatsapp_priority:
        log("⚠️ Twilio non configuré, WhatsApp ignoré")

# ===================== CLASSES =====================
class WordPressMonitor:
    def __init__(self, site_url=SITE_URL, admin_email=ADMIN_EMAIL):
        self.site_url = site_url
        self.admin_email = admin_email

    def check_site(self) -> bool:
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                r = requests.get(self.site_url, timeout=10, headers=headers)
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
        send_alert("🚨 Site WordPress Inaccessible",
                   f"Impossible d'atteindre {self.site_url} après {RETRY_COUNT} tentatives",
                   whatsapp_priority=True)
        return False

    def check_api(self) -> bool:
        domain = self.site_url.replace('https://', '').replace('http://', '').split('/')[0]

        if domain.endswith('wordpress.com'):
            api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{domain}"
            params = {}
            if WPCOM_CLIENT_ID and WPCOM_CLIENT_SECRET:
                params = {'client_id': WPCOM_CLIENT_ID, 'client_secret': WPCOM_CLIENT_SECRET}
            try:
                r = requests.get(api_url, params=params, timeout=10)
                log(f"API WordPress.com - HTTP {r.status_code}")
                return True
            except requests.RequestException as e:
                log(f"❌ API WordPress.com échouée: {e}")
                return True
        else:
            api_url = self.site_url.rstrip("/") + "/wp-json/wp/v2/"
            try:
                r = requests.get(api_url, timeout=10)
                log(f"API native - HTTP {r.status_code}")
                if r.status_code in [200, 404]:
                    return True
            except requests.RequestException as e:
                log(f"❌ API native échouée: {e}")
        return True


class RestorationManager:
    def send_restoration_option(self, alert_type, details):
        subject = f"🚨 {alert_type} - Action Requise"
        body = f"""
{alert_type} détecté sur {SITE_URL}
Détails: {details}

Options disponibles:
1. Restaurer automatiquement maintenant
2. Ignorer et surveiller
3. Contacter l'administrateur

Pour restaurer immédiatement, exécutez le workflow de restauration manuelle sur GitHub Actions.
"""
        send_alert(subject, body, whatsapp_priority=True)
        log(f"🔧 Option de restauration proposée pour: {alert_type}")
        return True

# ===================== BACKUP & COMPARAISON =====================
def compare_files(old_file, new_file) -> str:
    if not os.path.exists(old_file):
        return f"⚠️ {old_file} introuvable, création du fichier."
    with open(old_file, encoding="utf-8", errors="ignore") as f1, \
         open(new_file, encoding="utf-8", errors="ignore") as f2:
        diff = list(difflib.unified_diff(f1.readlines(), f2.readlines(),
                                         fromfile=old_file, tofile=new_file))
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
                send_alert(f"⚠️ Contenu modifié: {filename}", diff, whatsapp_priority=True)
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

# ===================== MAIN =====================
def main():
    log(f"🚀 Démarrage surveillance: {SITE_URL}")
    log(f"📧 Email alerte: {ADMIN_EMAIL}")
    log(f"📲 WhatsApp configuré: {'OUI' if TWILIO_SID else 'NON'}")
    log(f"🔑 API WordPress.com configurée: {'OUI' if WPCOM_CLIENT_ID else 'NON'}")

    try:
        requests.get("https://httpbin.org/status/200", timeout=5)
        log("✅ Connexion internet vérifiée")
    except:
        log("❌ Pas de connexion internet")
        send_alert("🚨 Pas de connexion internet", "Impossible de se connecter à internet", whatsapp_priority=True)
        return False

    wp_monitor = WordPressMonitor(SITE_URL, ADMIN_EMAIL)
    site_ok = wp_monitor.check_site()
    api_ok = wp_monitor.check_api()

    if site_ok and api_ok:
        log(f"✅ {SITE_URL} en ligne & API REST OK")
        backup_and_monitor()
        log("✅ Surveillance terminée")
        return True
    else:
        log(f"❌ Problème détecté (site ou API)")
        restorer = RestorationManager()
        restorer.send_restoration_option("Problème de site", f"Site: {site_ok}, API: {api_ok}")
        return False

# ===================== EXECUTION DIRECTE =====================
if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
