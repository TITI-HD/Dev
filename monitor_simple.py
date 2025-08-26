#!/usr/bin/env python3
"""
SCRIPT DE SURVEILLANCE WORDPRESS SIMPLIFIÉ
"""

import os
import smtplib
import requests
from datetime import datetime
from time import sleep

# ===================== CONFIGURATION =====================
SITE_URL = os.getenv("SITE_URL", "https://oupssecuretest.wordpress.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "kvjg gmnm wuzb hvnf")

RETRY_COUNT = 3
RETRY_DELAY = 5
LOG_FILE = "monitor.log"

# ===================== LOGGING =====================
def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8", errors="ignore") as f:
        f.write(line + "\n")

# ===================== ALERTES =====================
def send_alert(subject: str, body: str):
    """Envoie une alerte par Email"""
    log(f"🚨 ALERTE: {subject}")

    # Email
    try:
        msg = f"Subject: {subject}\n\n{body}"
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ADMIN_EMAIL, msg)
        log("📧 Email envoyé avec succès")
    except Exception as e:
        log(f"❌ Erreur envoi email: {e}")

# ===================== CHECK SITE =====================
def check_site(url: str) -> bool:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(url, timeout=10, headers=headers)
            log(f"Tentative {attempt} - HTTP {r.status_code}")
            
            if r.status_code == 200:
                return True
            else:
                log(f"⚠️ Code HTTP: {r.status_code}")
                return False
                
        except requests.RequestException as e:
            log(f"❌ Tentative {attempt} échouée: {e}")
        
        sleep(RETRY_DELAY)
    
    send_alert("🚨 Site WordPress Inaccessible", 
               f"Impossible d'atteindre {url} après {RETRY_COUNT} tentatives")
    return False

# ===================== CHECK API =====================
def check_api() -> bool:
    domain = "oupssecuretest.wordpress.com"
    api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{domain}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.get(api_url, timeout=10, headers=headers)
            log(f"Tentative API {attempt} - HTTP {r.status_code}")
            
            if r.status_code == 200:
                return True
            else:
                log(f"⚠️ Code API HTTP: {r.status_code}")
                
        except requests.RequestException as e:
            log(f"❌ API tentative {attempt} échouée: {e}")
        
        sleep(RETRY_DELAY)
    
    send_alert("🚨 API REST Inaccessible", 
               f"Impossible d'atteindre l'API après {RETRY_COUNT} tentatives")
    return False

# ===================== MAIN =====================
def main():
    log(f"🚀 Démarrage surveillance: {SITE_URL}")
    log(f"📧 Email alerte: {ADMIN_EMAIL}")

    site_ok = check_site(SITE_URL)
    api_ok = check_api()

    if site_ok and api_ok:
        log(f"✅ {SITE_URL} en ligne & API REST OK")
        return True
    else:
        log(f"❌ Problème détecté (site ou API)")
        return False

# ===================== EXECUTION DIRECTE =====================
if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)