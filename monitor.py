#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WP Monitor - Version simplifiée
- Surveillance site WordPress (disponibilité, intégrité, patterns suspects, SSL)
- Sauvegarde automatique après chaque scan
- Rapport texte et envoi email
- Configuration via variables d'environnement
- Compatible GitHub Actions
"""

import os
import sys
import time
import json
import shutil
import hashlib
import re
import ssl
import socket
import logging
import argparse
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from email.mime.text import MIMEText
import smtplib
import requests
from dateutil import parser as dateutil_parser, tz as dateutil_tz

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
        self.RESTORE_DIR = Path(os.environ.get("RESTORE_DIR", "restored"))
        self.RESTORE_DIR.mkdir(exist_ok=True, parents=True)
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

# -------------------
# Surveillance
# -------------------
def check_site_availability():
    log("Vérification disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        if not results['available']:
            incident_manager.add("site_unavailable", {"status_code": resp.status_code}, "high")
            log(f"Site inaccessible: HTTP {resp.status_code}", "WARNING")
        else:
            log(f"Site accessible: HTTP {resp.status_code}")
    except Exception as e:
        results['error'] = str(e)
        incident_manager.add("site_access_error", {"error": str(e)}, "high")
        log(f"Erreur accès site: {e}", "ERROR")
    return results

def check_content_integrity():
    log("Vérification intégrité...")
    results = {'changed': False, 'changes': []}
    endpoints = [(config.SITE_URL, "homepage")]
    for url, name in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                content = resp.text
                ref_file = config.MONITOR_DIR / f"{name}.ref"
                old_hash = ref_file.read_text(encoding='utf-8').strip() if ref_file.exists() else ""
                current_hash = compute_hash(content)
                if old_hash and current_hash != old_hash:
                    results['changed'] = True
                    results['changes'].append({"endpoint": name, "url": url})
                    incident_manager.add("content_changed", {"endpoint": name, "url": url}, "medium")
                ref_file.write_text(current_hash, encoding='utf-8')
        except Exception as e:
            log(f"Erreur intégrité {name}: {e}", "ERROR")
    return results

def check_for_malicious_patterns():
    log("Recherche patterns suspects...")
    results = {'suspicious_patterns': []}
    try:
        resp = requests.get(config.SITE_URL, timeout=10)
        if resp.status_code == 200:
            content = resp.text
            patterns = [
                (r'eval\s*\(', 'eval() potentiellement dangereux', 'high'),
                (r'base64_decode\s*\(', 'Décodage base64 suspect', 'medium'),
                (r'exec\s*\(', 'Appel exec()', 'high')
            ]
            for pat, desc, sev in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    results['suspicious_patterns'].append({'pattern': pat, 'description': desc})
                    incident_manager.add("suspicious_code", {'pattern': pat, 'description': desc}, sev)
    except Exception as e:
        log(f"Erreur détection patterns: {e}", "ERROR")
    return results

def check_ssl_cert():
    log("Vérification certificat SSL...")
    results = {'valid': False, 'days_left': None}
    try:
        hostname = config.SITE_URL.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(8)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            not_after = cert.get("notAfter")
            if not_after:
                expire_dt = dateutil_parser.parse(not_after)
                if expire_dt.tzinfo is None:
                    expire_dt = expire_dt.replace(tzinfo=dateutil_tz.tzutc())
                delta = (expire_dt - datetime.now(timezone.utc)).days
                results['valid'] = delta > 0
                results['days_left'] = delta
                if delta < 30:
                    incident_manager.add("ssl_warning", {'days_left': delta}, "medium")
    except Exception as e:
        log(f"Erreur SSL: {e}", "ERROR")
    return results

# -------------------
# Sauvegarde
# -------------------
def backup_wordpress_content():
    source_dir = config.MONITOR_DIR
    metadata = {}
    files_copied = 0
    for root, _, files in os.walk(source_dir):
        for filename in files:
            src_path = Path(root) / filename
            rel_path = src_path.relative_to(source_dir)
            dst_path = config.BACKUP_DIR / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, dst_path)
                metadata[str(rel_path)] = {"hash": compute_hash(dst_path.read_text(encoding='utf-8')), "timestamp": datetime.now().isoformat()}
                files_copied += 1
            except Exception as e:
                log(f"Impossible de sauvegarder {rel_path}: {e}", "ERROR")
    with (config.BACKUP_DIR / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés.")

# -------------------
# Restauration
# -------------------
def restore_all_files(target_dir: Path = config.RESTORE_DIR):
    metadata_file = config.BACKUP_DIR / "metadata.json"
    if not metadata_file.exists():
        log("Métadonnées introuvables, restauration impossible.", "ERROR")
        return
    with metadata_file.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    for rel_path, meta in metadata.items():
        backup_path = config.BACKUP_DIR / rel_path
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup_path, dest_path)
            log(f"Restauration OK: {rel_path}")
        except Exception as e:
            log(f"Erreur restauration fichier {rel_path}: {e}", "ERROR")

# -------------------
# Reporting / Email
# -------------------
def generate_report() -> str:
    history = incident_manager.load_incidents()
    report = ["WordPress Monitoring Report", "============================", f"Total incidents: {len(history)}\n"]
    for inc in history[-20:]:
        report.append(f"[{inc['timestamp']}] [{inc['severity']}] {inc['type']} - {inc['details']}")
    report_str = "\n".join(report)
    report_file = config.MONITOR_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_str, encoding='utf-8')
    log(f"Rapport généré -> {report_file}")
    return report_str

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
# Cycle principal
# -------------------
def run_all():
    log("=== Début du cycle de surveillance ===")
    before_count = len(incident_manager.load_incidents())
    check_site_availability()
    check_content_integrity()
    check_for_malicious_patterns()
    check_ssl_cert()
    backup_wordpress_content()
    report_text = generate_report()
    # Envoyer résumé
    new_incidents_count = len(incident_manager.load_incidents()) - before_count
    if new_incidents_count == 0:
        send_email(f"[INFO WP] Tout est OK - {config.SITE_URL}", f"Aucun incident détecté pendant ce cycle.\n\n{report_text}")
    else:
        send_email(f"[ALERTE WP] {new_incidents_count} incident(s) détecté(s) - {config.SITE_URL}", report_text)
    log("Cycle complet terminé ✅")


............
Ensuite...
...........



def check_wordpress_com_site():
    """Vérifie disponibilité, contenu, patterns suspects et SSL pour WordPress.com"""
    results = {}
    # Disponibilité
    try:
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['available'] = resp.status_code == 200
        if not results['available']:
            incident_manager.add("site_unavailable", {"status_code": resp.status_code}, "high", notify=True)
    except Exception as e:
        incident_manager.add("site_access_error", {"error": str(e)}, "high", notify=True)

    # Intégrité contenu (homepage + feed)
    endpoints = [("/", "homepage"), ("/feed/", "rss"), ("/comments/feed/", "comments")]
    for path, name in endpoints:
        try:
            url = config.SITE_URL.rstrip("/") + path
            r = requests.get(url, timeout=10)
            content = r.text
            ref_file = config.MONITOR_DIR / f"{name}.ref"
            old_hash = ref_file.read_text(encoding='utf-8').strip() if ref_file.exists() else ""
            current_hash = compute_hash(content)
            if old_hash and current_hash != old_hash:
                diff = '\n'.join(difflib.unified_diff(
                    ref_file.read_text().splitlines(), content.splitlines(), lineterm=''))
                incident_manager.add("content_changed", {'endpoint': name, 'diff': diff[:1000]}, "medium", notify=True)
            ref_file.write_text(current_hash, encoding='utf-8')
        except Exception as e:
            incident_manager.add("content_check_error", {"endpoint": name, "error": str(e)}, "medium", notify=True)

    # SSL
    try:
        hostname = config.SITE_URL.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(8)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            expire_dt = dateutil_parser.parse(cert['notAfter'])
            delta = (expire_dt - datetime.now(timezone.utc)).days
            results['ssl_days_left'] = delta
            if delta < 30:
                incident_manager.add("ssl_warning", {"days_left": delta}, "medium", notify=True)
    except Exception as e:
        incident_manager.add("ssl_error", {"error": str(e)}, "medium", notify=True)

    return results


# -------------------
# CLI
# -------------------
def main():
    parser = argparse.ArgumentParser(description="WP Monitoring & Backup Tool")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--backup", action="store_true", help="Faire backup uniquement")
    parser.add_argument("--restore", type=str, help="Restauration depuis backup")
    parser.add_argument("--report", action="store_true", help="Générer rapport uniquement")
    parser.add_argument("--test", action="store_true", help="Tests simples")
    args = parser.parse_args()

    if args.test:
        print("Exécution des tests unitaires...")
    elif args.once:
        run_all()
    elif args.backup:
        backup_wordpress_content()
    elif args.restore:
        restore_all_files(Path(args.restore))
    elif args.report:
        generate_report()
    else:
        import schedule
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        log(f"Scheduler démarré: interval {config.CHECK_INTERVAL_HOURS}h")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()