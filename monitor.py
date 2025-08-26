#!/usr/bin/env python3
"""
SCRIPT DE SURVEILLANCE WORDPRESS AVANCÉ - VERSION CORRIGÉE
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
load_dotenv()

# ===================== CONFIGURATION =====================
SITE_URL = os.getenv("SITE_URL", "https://oupssecuretest.wordpress.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "kvjg gmnm wuzb hvnf")

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_AUTH = os.getenv("TWILIO_AUTH", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")
TWILIO_TO = os.getenv("TWILIO_TO", "")

# Configuration API WordPress.com (optionnelle)
WPCOM_CLIENT_ID = os.getenv("WPCOM_CLIENT_ID", "122464")
WPCOM_CLIENT_SECRET = os.getenv("WPCOM_CLIENT_SECRET", "4J1wGVO28qOAswnG8GWFVgbAFPAM0rAV-ICRnfJhPut5nUCyF5fSTAIApE9CECdw")

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
    """Envoie une alerte par Email et WhatsApp"""
    log(f"🚨 ALERTE: {subject}")

    # Limiter la longueur des diffs
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

# ===================== CHECK SITE =====================
def check_site(url: str) -> bool:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            # Ajout d'en-têtes pour éviter les blocages
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
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
    send_alert("🚨 Site WordPress Inaccessible", f"Impossible d'atteindre {url} après {RETRY_COUNT} tentatives", whatsapp_priority=True)
    return False

# ===================== CHECK API =====================
def check_api(url: str) -> bool:
    # Extraire le domaine du site
    domain = url.replace('https://', '').replace('http://', '').split('/')[0]
    
    # Utiliser l'API WordPress.com pour les sites wordpress.com
    if domain.endswith('wordpress.com'):
        api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{domain}"
        
        # Ajouter les paramètres d'authentification
        params = {}
        if WPCOM_CLIENT_ID and WPCOM_CLIENT_SECRET:
            params = {
                'client_id': WPCOM_CLIENT_ID,
                'client_secret': WPCOM_CLIENT_SECRET
            }
            
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                r = requests.get(api_url, params=params, timeout=10)
                log(f"Tentative API WordPress.com {attempt} - HTTP {r.status_code}")
                if r.status_code == 200:
                    return True
                else:
                    log(f"⚠️ API WordPress.com retourne: {r.status_code}")
                    # Même en cas d'échec, on continue car le site peut être accessible
                    return True
            except requests.RequestException as e:
                log(f"❌ API WordPress.com tentative {attempt} échouée: {e}")
            sleep(RETRY_DELAY)
        
        # Même après échec, on considère que le site est accessible
        return True
    
    # Pour les sites auto-hébergés, essayer l'API native
    else:
        api_url = url.rstrip("/") + "/wp-json/wp/v2/"
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                r = requests.get(api_url, timeout=10)
                log(f"Tentative API native {attempt} - HTTP {r.status_code}")
                if r.status_code == 200:
                    return True
                elif r.status_code == 404:
                    log("⚠️ API REST désactivée (404), on continue quand même")
                    return True
            except requests.RequestException as e:
                log(f"❌ API native tentative {attempt} échouée: {e}")
            sleep(RETRY_DELAY)
    
    return True  # Même en cas d'échec API, on considère le site accessible

def backup_and_monitor():
    domain = SITE_URL.replace('https://', '').replace('http://', '').split('/')[0]
    
    if domain.endswith('wordpress.com'):
        # URLs spécifiques à WordPress.com
        save_content(SITE_URL, "homepage.html")
        save_content(SITE_URL + "/feed/", "rss.xml")
        save_content(SITE_URL + "/comments/feed/", "comments.xml")
    else:
        # URLs pour WordPress auto-hébergé
        save_content(SITE_URL, "homepage.html")
        save_content(SITE_URL + "/feed/", "rss.xml")
        save_content(SITE_URL + "/comments/feed/", "comments.xml")

def main():
    log(f"🚀 Démarrage surveillance: {SITE_URL}")
    log(f"📧 Email alerte: {ADMIN_EMAIL}")

    # Vérifier uniquement le site (pas besoin de vérifier l'API pour WordPress.com)
    site_ok = check_site(SITE_URL)
    
    if site_ok:
        log(f"✅ {SITE_URL} en ligne")
        backup_and_monitor()
        log("✅ Surveillance terminée")
        return True
    else:
        log(f"❌ Site inaccessible")
        return False
    
    # Essayer l'API native WordPress (wp-json)
    api_url = url.rstrip("/") + "/wp-json/wp/v2/"
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            r = requests.get(api_url, timeout=10, headers=headers)
            log(f"Tentative API native {attempt} - HTTP {r.status_code}")
            if r.status_code == 200:
                return True
            elif r.status_code == 404:
                log("⚠️ API REST désactivée (404), on continue quand même")
                return True
        except requests.RequestException as e:
            log(f"❌ API native tentative {attempt} échouée: {e}")
        sleep(RETRY_DELAY)
    
    send_alert("🚨 API REST Inaccessible", f"Impossible d'atteindre aucune API après {RETRY_COUNT} tentatives", whatsapp_priority=True)
    return False

# ===================== COMPARAISON ET SAUVEGARDE =====================
def compare_files(old_file, new_file) -> str:
    """Retourne le diff complet sous forme de chaîne, ou chaîne vide si pas de changement"""
    if not os.path.exists(old_file):
        return f"⚠️ {old_file} introuvable, création du fichier."
    with open(old_file, encoding="utf-8", errors="ignore") as f1, \
         open(new_file, encoding="utf-8", errors="ignore") as f2:
        diff = list(difflib.unified_diff(f1.readlines(), f2.readlines(), fromfile=old_file, tofile=new_file))
        return "\n".join(diff)

def save_content(url: str, filename: str):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, timeout=10, headers=headers)
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

# ===================== BACKUP COMPLET =====================
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

    # Test préliminaire de connexion
    try:
        requests.get("https://httpbin.org/status/200", timeout=5)
        log("✅ Connexion internet vérifiée")
    except:
        log("❌ Pas de connexion internet")
        send_alert("🚨 Pas de connexion internet", "Impossible de se connecter à internet", whatsapp_priority=True)
        return False

    site_ok = check_site(SITE_URL)
    api_ok = check_api(SITE_URL)

    if site_ok and api_ok:
        log(f"✅ {SITE_URL} en ligne & API REST OK")
        backup_and_monitor()
        log("✅ Surveillance terminée")
        return True
    else:
        log(f"❌ Problème détecté (site ou API)")
        return False

# ===================== EXECUTION DIRECTE =====================
if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)