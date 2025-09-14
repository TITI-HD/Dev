#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WP Monitor - Version WordPress.com
- Surveillance site WordPress.com (disponibilité, contenu via REST API, patterns suspects)
- Sauvegarde automatique JSON du contenu éditorial
- Rapport texte et email
- Compatible GitHub Actions
"""

import os
import sys
import time
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
import requests
import smtplib
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler

# -------------------
# Configuration
# -------------------
class Config:
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER")
        self.SMTP_PASS = os.environ.get("SMTP_PASS")
        self.MONITOR_DIR = Path(os.environ.get("MONITOR_DIR", "monitor_data"))
        self.MONITOR_DIR.mkdir(exist_ok=True, parents=True)
        self.BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))
        self.BACKUP_DIR.mkdir(exist_ok=True, parents=True)
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.validate()

    def validate(self):
        if not self.ALERT_EMAIL:
            print("ATTENTION: ALERT_EMAIL non défini — les alertes ne seront pas envoyées.")
        if not self.SMTP_USER or not self.SMTP_PASS:
            print("ATTENTION: SMTP_USER ou SMTP_PASS non définis — l'envoi email échouera.")

config = Config()

# -------------------
# Logging rotatif
# -------------------
logger = logging.getLogger("WPMonitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(config.MONITOR_DIR / "monitor.log", maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def log(message: str, level="INFO"):
    getattr(logger, level.lower())(message)
    print(message)

# -------------------
# Incident Manager
# -------------------
class IncidentManager:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._ensure_file()

    def _ensure_file(self):
        if not self.history_file.exists():
            self.save_incidents([])

    def load_incidents(self):
        try:
            with self.history_file.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def save_incidents(self, incidents):
        with self.history_file.open('w', encoding='utf-8') as f:
            json.dump(incidents, f, ensure_ascii=False, indent=4)

    def add(self, type_, details, severity="medium", notify=True):
        history = self.load_incidents()
        incident = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": type_,
            "severity": severity,
            "details": details
        }
        history.append(incident)
        history = history[-100:]
        self.save_incidents(history)
        if notify and severity in ["medium", "high"]:
            subject = f"[ALERTE WP] {type_} ({severity})"
            body = f"Incident détecté:\nType: {type_}\nSévérité: {severity}\nDétails: {json.dumps(details, ensure_ascii=False)}\nHorodatage: {incident['timestamp']}"
            send_email(subject, body)
        return incident

incident_manager = IncidentManager(config.MONITOR_DIR / "incident_history.json")

# -------------------
# Utilitaires
# -------------------
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def send_email(subject: str, body: str):
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("SMTP incomplet — e-mail non envoyé", "WARNING")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER
    msg["To"] = config.ALERT_EMAIL
    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        log(f"Email envoyé -> {config.ALERT_EMAIL}")
    except Exception as e:
        log(f"Erreur envoi email: {e}", "ERROR")

# -------------------
# Surveillance WordPress.com via REST API
# -------------------
def fetch_wp_content(endpoint):
    url = config.SITE_URL.rstrip("/") + endpoint
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json() if 'application/json' in resp.headers.get('Content-Type', '') else resp.text
        else:
            incident_manager.add("wp_api_error", {"endpoint": endpoint, "status": resp.status_code}, "medium")
    except Exception as e:
        incident_manager.add("wp_api_error", {"endpoint": endpoint, "error": str(e)}, "medium")
    return None

def backup_wp_content():
    endpoints = ["/wp-json/wp/v2/posts", "/wp-json/wp/v2/pages", "/wp-json/wp/v2/comments"]
    backup_data = {}
    for ep in endpoints:
        data = fetch_wp_content(ep)
        if data:
            backup_data[ep] = data

    # Gestion incrémentale
    backup_file = config.BACKUP_DIR / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_file.write_text(json.dumps(backup_data, ensure_ascii=False, indent=4), encoding='utf-8')
    log(f"Backup WordPress.com généré -> {backup_file}")
    return backup_file

# -------------------
# Génération rapport TXT
# -------------------
def generate_report() -> str:
    history = incident_manager.load_incidents()
    report = ["WordPress.com Monitoring Report", "="*30, f"Total incidents: {len(history)}\n"]
    for inc in history[-20:]:
        report.append(f"[{inc['timestamp']}] [{inc['severity']}] {inc['type']} - {inc['details']}")
    report_str = "\n".join(report)
    report_file = config.MONITOR_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_str, encoding='utf-8')
    log(f"Rapport TXT généré -> {report_file}")
    return report_str

# -------------------
# Cycle principal
# -------------------
def run_all():
    log("=== Début du cycle WP Monitor ===")
    before_count = len(incident_manager.load_incidents())

    # Disponibilité simple (HTTP 200)
    try:
        r = requests.get(config.SITE_URL, timeout=10)
        if r.status_code != 200:
            incident_manager.add("site_unavailable", {"status": r.status_code}, "high")
    except Exception as e:
        incident_manager.add("site_access_error", {"error": str(e)}, "high")

    # Backup contenu via REST API
    backup_file = backup_wp_content()

    # Rapport et email
    report_text = generate_report()
    new_incidents_count = len(incident_manager.load_incidents()) - before_count
    if new_incidents_count == 0:
        send_email(f"[INFO WP] Tout est OK - {config.SITE_URL}", f"Aucun incident détecté.\nBackup: {backup_file}\n\n{report_text}")
    else:
        send_email(f"[ALERTE WP] {new_incidents_count} incident(s) détecté(s) - {config.SITE_URL}", report_text)
    log("Cycle terminé ✅")

# -------------------
# CLI
# -------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WP.com Monitoring & Backup Tool")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    args = parser.parse_args()

    if args.once:
        run_all()
    else:
        import schedule
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        log(f"Scheduler démarré: interval {config.CHECK_INTERVAL_HOURS}h")
        while True:
            schedule.run_pending()
            time.sleep(1)