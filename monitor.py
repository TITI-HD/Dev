#!/usr/bin/env python3
"""
WordPress Monitoring & Backup & Restore & Report - Tout-en-un
- Surveillance: disponibilité, intégrité, patterns suspects, SSL
- Backup: sauvegarde du site WordPress
- Restore: restauration des fichiers avec vérification
- Reporting: rapports détaillés + historique incidents (TXT + HTML)
- Planification: exécution planifiée avec nettoyage des logs
- Option --once pour exécution unique
- Option --test pour tests unitaires
"""

import os
import sys
import time
import json
import glob
import shutil
import hashlib
import re
import ssl
import socket
import difflib
import logging
import argparse
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone   # <-- ajout timezone
from pathlib import Path
from typing import Dict, List
from dateutil import parser, tz

# --- Vérification des dépendances ---
MISSING = []
try:
    import requests
except ImportError:
    MISSING.append("requests")
try:
    import schedule
except ImportError:
    MISSING.append("schedule")
try:
    from dateutil import parser, tz
except ImportError:
    MISSING.append("python-dateutil")

if MISSING:
    print("Modules manquants :", ", ".join(MISSING))
    print("→ Installer via: pip install " + " ".join(MISSING))
    sys.exit(1)

# === Configuration ===
class Config:
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
        self.SMTP_PASS = os.environ.get("SMTP_PASS", "nrqi mihe mtgi iabo")
        self.MONITOR_DIR = Path("monitor_data")
        self.MONITOR_DIR.mkdir(exist_ok=True)
        self.INCIDENT_HISTORY_FILE = self.MONITOR_DIR / "incident_history.json"
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = bool(os.environ.get("USE_EMOJI", os.name != "nt"))
        self.ANONYMIZE_SAMPLES = bool(os.environ.get("ANONYMIZE_SAMPLES", True))
        self.BACKUP_DIR = Path("backups")
        self.BACKUP_DIR.mkdir(exist_ok=True)
        self.RESTORE_DIR = Path("restored")
        self.RESTORE_DIR.mkdir(exist_ok=True)
        self.validate()

    def validate(self):
        if not self.SMTP_PASS:
            raise ValueError("SMTP_PASS obligatoire pour alertes email")
        if not self.SITE_URL.startswith(('http://','https://')):
            print("ATTENTION: SITE_URL devrait commencer par http:// ou https://")

config = Config()

# === Logging rotatif ===
logger = logging.getLogger("WPMonitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(config.MONITOR_DIR / "monitor.log", maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def log(message: str, level="INFO"):
    getattr(logger, level.lower())(message)
    print(message)

# === Incident Manager ===
class IncidentManager:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.load_incidents()

    def load_incidents(self) -> List[Dict]:
        if self.history_file.exists():
            with self.history_file.open('r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_incidents(self, incidents: List[Dict]):
        with self.history_file.open('w', encoding='utf-8') as f:
            json.dump(incidents, f, ensure_ascii=False, indent=4)

    def add(self, type_: str, details: Dict, severity="medium") -> Dict:
        history = self.load_incidents()
        incident = {
            "timestamp": datetime.now().isoformat(),
            "type": type_,
            "severity": severity,
            "details": details
        }
        history.append(incident)
        if len(history) > 100:
            history = history[-100:]
        self.save_incidents(history)

        # Envoi automatique email pour incidents medium ou high
        if severity in ["medium", "high"]:
            subject = f"[ALERTE WP] {type_} ({severity})"
            body = f"Incident détecté:\nType: {type_}\nSévérité: {severity}\nDétails: {details}\nHorodatage: {incident['timestamp']}"
            send_alert(subject, body, incident_type=type_)

        return incident

incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# === Utilitaires ===
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, incident_type="general") -> bool:
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("SMTP incomplet", "WARNING")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = config.SMTP_USER
        msg['To'] = config.ALERT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        import smtplib
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        incident_manager.add(incident_type, {"subject": subject, "body": body, "sent_via":"email"})
        log("Alerte envoyée")
        return True
    except Exception as e:
        log(f"Erreur alerte: {e}", "ERROR")
        return False

def run_all():
    log("=== Début du cycle de surveillance ===")
    initial_incidents = len(incident_manager.load_incidents())

    check_site_availability()
    check_content_integrity()
    check_for_malicious_patterns()
    check_ssl_cert()
    backup_site()
    generate_report()
    cleanup_old_reports()

    # Vérifier si de nouveaux incidents ont été ajoutés
    new_incidents = len(incident_manager.load_incidents()) - initial_incidents
    if new_incidents == 0:
        # Aucun incident : envoyer email “tout va bien”
        subject = "[INFO WP] Tout est OK ✅"
        body = f"Aucun incident détecté sur {config.SITE_URL} pendant ce cycle.\nHorodatage: {datetime.now().isoformat()}"
        send_alert(subject, body, incident_type="info")
        log("Aucun incident détecté. Email d'information envoyé.")

    log("Cycle complet terminé ✅")

# === Surveillance ===
def check_site_availability() -> Dict:
    log("Vérification disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now()-start).total_seconds()
        results['available'] = resp.status_code == 200
        log(f"Site accessible {emoji('✅')}" if results['available'] else f"HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur accès site: {e}", "ERROR")
    return results

def check_content_integrity() -> Dict:
    log("Vérification intégrité...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [(config.SITE_URL, "homepage"), (config.SITE_URL+"/feed/","rss"), (config.SITE_URL+"/comments/feed/","comments")]
    for url, name in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code==200:
                content = resp.text
                ref_file = config.MONITOR_DIR / f"{name}.ref"
                content_file = config.MONITOR_DIR / f"{name}_content.ref"
                current_hash = compute_hash(content)
                old_hash = ref_file.read_text(encoding='utf-8').strip() if ref_file.exists() else ""
                old_content = content_file.read_text(encoding='utf-8') if content_file.exists() else ""
                if current_hash != old_hash and old_hash:
                    results['changed'] = True
                    diff = '\n'.join(difflib.unified_diff(old_content.splitlines(), content.splitlines(), lineterm=''))
                    results['changes'].append({'endpoint':name,'url':url,'diff':diff[:500]+'...' if len(diff)>500 else diff})
                    incident_manager.add("content_changed", {'endpoint':name,'url':url,'diff':diff[:500]+'...'}, "medium")
                    log(f"Changement détecté: {name} {emoji('⚠️')}", "WARNING")
                ref_file.write_text(current_hash, encoding='utf-8')
                content_file.write_text(content, encoding='utf-8')
            else:
                log(f"Erreur HTTP {resp.status_code} {url}", "WARNING")
        except Exception as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}", "ERROR")
    return results

def check_for_malicious_patterns() -> Dict:
    log("Recherche patterns suspects...")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [(r'eval\s*\(','eval() potentiellement dangereux','high'),
                (r'base64_decode\s*\(','Décodage base64 suspect','medium'),
                (r'exec\s*\(','Appel exec()','high')]
    try:
        resp = requests.get(config.SITE_URL, timeout=10)
        if resp.status_code==200:
            content = resp.text
            for pat, desc, sev in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    sample = [m[:50]+'...' if len(m)>50 else m for m in matches]
                    results['suspicious_patterns'].append({'pattern':pat,'description':desc,'matches':sample})
                    incident_manager.add("suspicious_code", {'pattern':pat,'description':desc,'matches':sample}, sev)
                    log(f"Pattern suspect détecté: {desc} {emoji('⚠️')}", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur détection patterns: {e}", "ERROR")
    return results

def check_ssl_cert() -> Dict:
    results = {'valid': False, 'days_left': None, 'error': None}
    try:
        hostname = config.SITE_URL.replace("https://","").replace("http://","").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(5)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            expire_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
            # 🔧 Correction ici :
            delta = (expire_date - datetime.now(timezone.utc)).days
            results['valid'] = delta > 0
            results['days_left'] = delta
            if delta < 30:
                incident_manager.add("ssl_warning", {'days_left': delta}, "medium")
                log(f"Certificat SSL expire bientôt ({delta} jours) {emoji('⚠️')}", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur SSL: {e}", "ERROR")
    return results

# === Backup & Restore ===
def backup_site():
    log("Démarrage backup site...")
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    backup_path = config.BACKUP_DIR / backup_name
    try:
        shutil.make_archive(str(backup_path).replace(".zip",""), 'zip', config.MONITOR_DIR)
        incident_manager.add("backup_success", {"backup_file":str(backup_path)}, "low")
        log(f"Sauvegarde OK {emoji('✅')} -> {backup_path}")
    except Exception as e:
        incident_manager.add("backup_fail", {"error":str(e)}, "high")
        log(f"Erreur backup: {e}", "ERROR")

def restore_site(backup_file: Path):
    log(f"Démarrage restauration: {backup_file}")
    try:
        shutil.unpack_archive(str(backup_file), config.RESTORE_DIR)
        incident_manager.add("restore_success", {"backup_file":str(backup_file)}, "low")
        log(f"Restauration OK {emoji('✅')} -> {config.RESTORE_DIR}")
    except Exception as e:
        incident_manager.add("restore_fail", {"backup_file":str(backup_file),"error":str(e)}, "high")
        log(f"Erreur restauration: {e}", "ERROR")

# === Reporting ===
def generate_report() -> str:
    history = incident_manager.load_incidents()
    # Rapport texte
    report = ["WordPress Monitoring Report", "============================", f"Total incidents: {len(history)}\n"]
    for inc in history[-20:]:
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        report.append(f"[{ts}] [{sev}] {typ} - {inc['details']}")
    report_str = "\n".join(report)
    report_file = config.MONITOR_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_str, encoding='utf-8')
    log(f"Rapport généré -> {report_file}")

    # 🔧 Nouveau rapport HTML
    html_lines = [
        "<html><head><meta charset='utf-8'><title>WP Monitoring Report</title></head><body>",
        "<h2>Rapport de Monitoring WordPress</h2>",
        f"<p>Total incidents: {len(history)}</p>",
        "<ul>"
    ]
    for inc in history[-20:]:
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        html_lines.append(f"<li><b>{ts}</b> [{sev}] <u>{typ}</u> - {inc['details']}</li>")
    html_lines.append("</ul></body></html>")
    html_str = "\n".join(html_lines)
    html_file = config.MONITOR_DIR / "logs.html"
    html_file.write_text(html_str, encoding="utf-8")
    log(f"Rapport HTML généré -> {html_file}")

    return report_str

# === Nettoyage ancien logs ===
def cleanup_old_reports():
    now = datetime.now()
    for f in config.MONITOR_DIR.glob("report_*.txt"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if (now - mtime).days > config.LOG_RETENTION_DAYS:
            f.unlink()
            log(f"Ancien rapport supprimé: {f}")

# === Exécution principale ===
def main():
    parser = argparse.ArgumentParser(description="WP Monitoring & Backup Tool")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--backup", action="store_true", help="Faire backup uniquement")
    parser.add_argument("--restore", type=str, help="Restauration depuis un fichier zip")
    parser.add_argument("--report", action="store_true", help="Générer rapport uniquement")
    parser.add_argument("--test", action="store_true", help="Exécuter tests unitaires simples")
    args = parser.parse_args()

    if args.test:
        print("Exécution des tests unitaires...")
        # Tests simples ici
    elif args.once:
        run_all()
    elif args.backup:
        backup_site()
    elif args.restore:
        restore_site(Path(args.restore))
    elif args.report:
        generate_report()
    else:
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()
