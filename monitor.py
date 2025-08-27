#!/usr/bin/env python3
"""
Script principal de surveillance WordPress
Inclut la vérification de disponibilité, d'intégrité et de sécurité
Appelle également la sauvegarde depuis backup.py
"""

import os
import sys
import smtplib
import requests
import hashlib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Dict

# Import de backup.py
try:
    from backup import backup_wordpress_content
except ImportError:
    print("[ERREUR IMPORT] Impossible d'importer backup_wordpress_content depuis backup.py")
    sys.exit(1)

# === Configuration ===
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "yizn odfb xlhz mygy")

MONITOR_DIR = "monitor_data"
Path(MONITOR_DIR).mkdir(exist_ok=True)

# === Logging ===
def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(os.path.join(MONITOR_DIR, "monitor.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

# === Utilitaires ===
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def send_alert(subject: str, body: str) -> bool:
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_EMAIL]):
        log("ATTENTION: Configuration SMTP incomplète.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        log("SUCCES: Alerte envoyée")
        return True
    except Exception as e:
        log(f"ERREUR envoi alerte : {e}")
        return False

# === Vérifications ===
def check_site_availability() -> Dict:
    log("Vérification de disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        log("Site accessible." if results['available'] else f"Site retourne HTTP {resp.status_code}")
    except Exception as e:
        results['error'] = str(e)
        log(f"ERREUR accès site : {e}")
    return results

def check_content_integrity() -> Dict:
    log("Vérification d'intégrité...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [
        (SITE_URL, "homepage"),
        (SITE_URL + "/feed/", "rss"),
        (SITE_URL + "/comments/feed/", "comments")
    ]
    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                current_hash = compute_hash(response.text)
                ref_file = os.path.join(MONITOR_DIR, f"{name}.ref")
                if os.path.exists(ref_file):
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        old_hash = f.read().strip()
                    if current_hash != old_hash:
                        results['changed'] = True
                        results['changes'].append({'endpoint': name, 'url': url})
                        log(f"Changement détecté : {name}")
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    log(f"Référence créée : {name}")
            else:
                log(f"Erreur HTTP sur {url}: {response.status_code}")
        except Exception as e:
            log(f"Erreur intégrité {name}: {e}")
            results['error'] = str(e)
    return results

def check_for_malicious_patterns() -> Dict:
    log("Recherche de patterns suspects...")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [r'eval\s*\(', r'base64_decode\s*\(', r'exec\s*\(', r'system\s*\(', r'shell_exec\s*\(']
    try:
        response = requests.get(SITE_URL, timeout=10)
        if response.status_code == 200:
            for pat in patterns:
                if re.search(pat, response.text, re.IGNORECASE):
                    results['suspicious_patterns'].append(pat)
                    log(f"Pattern suspect détecté : {pat}")
        else:
            log("Erreur HTTP pendant la recherche de patterns.")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur pattern : {e}")
    return results

# === Monitoring principal ===
def main_monitoring():
    log("=== DÉMARRAGE SURVEILLANCE ===")
    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    alert_message = f"Surveillance WordPress : {SITE_URL}\n\n"
    issues = False

    if not availability['available']:
        issues = True
        alert_message += "❌ Site INACCESSIBLE\n"
        if availability['error']:
            alert_message += f"Erreur: {availability['error']}\n\n"

    if integrity['changed']:
        issues = True
        alert_message += "⚠️ Modifications détectées :\n"
        for c in integrity['changes']:
            alert_message += f"- {c['endpoint']} : {c['url']}\n"
        alert_message += "\n"

    if security['suspicious_patterns']:
        issues = True
        alert_message += "⚠️ Patterns suspects :\n"
        for p in security['suspicious_patterns']:
            alert_message += f"- {p}\n"
        alert_message += "\n"

    if issues:
        send_alert("🚨 Alerte Surveillance WordPress", alert_message)
    else:
        log("Aucun problème détecté.")
        send_alert("✅ Rapport Surveillance WordPress", "Aucune anomalie détectée.")
    log("=== FIN SURVEILLANCE ===")

# === Enchaînement backup + monitoring ===
def backup_and_monitor():
    log("Lancement sauvegarde...")
    backup_wordpress_content()
    log("Lancement surveillance...")
    main_monitoring()

if __name__ == "__main__":
    try:
        backup_and_monitor()
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}")
        send_alert("❌ Erreur critique dans la surveillance", str(e))
        sys.exit(1)
