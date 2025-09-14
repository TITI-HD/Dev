#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WP Monitor Fusionné
- Monitoring complet WordPress
- Détection disponibilité, intégrité, patterns suspects, SSL
- Sauvegarde après chaque scan
- Rapports TXT & HTML
- Envoi résumé email à chaque cycle
- CLI: --once, --report, --send-email, --backup, --restore, --test
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
import difflib
import logging
import argparse
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from dateutil import parser as dateutil_parser, tz as dateutil_tz
import requests
import schedule

# Charger variables d'environnement
load_dotenv('.env.local')

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
        self.INCIDENT_HISTORY_FILE = self.MONITOR_DIR / "incident_history.json"
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = os.environ.get("USE_EMOJI", "1") == "1"
        self.validate()

    def validate(self):
        if not self.ALERT_EMAIL:
            print("⚠️ ALERT_EMAIL non défini — notifications email désactivées.")
        if not self.SMTP_USER or not self.SMTP_PASS:
            print("⚠️ SMTP_USER ou SMTP_PASS non définis — envoi email échouera.")
        if not self.SITE_URL.startswith(("http://","https://")):
            print("⚠️ SITE_URL devrait commencer par http:// ou https://")

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

    def add(self, type_, details, severity="medium", notify=False):
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
        if notify and severity in ["medium","high"]:
            subject = f"[ALERTE WP] {type_} ({severity})"
            body = f"Incident détecté:\nType: {type_}\nSévérité: {severity}\nDétails: {json.dumps(details, ensure_ascii=False)}\nHorodatage: {incident['timestamp']}"
            send_alert(subject, body, html=False)
        return incident

incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# -------------------
# Utilitaires
# -------------------
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, html=True) -> bool:
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("SMTP incomplet — email non envoyé", "WARNING")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg['From'] = config.SMTP_USER
        msg['To'] = config.ALERT_EMAIL
        msg['Subject'] = subject
        part1 = MIMEText(body, 'plain', 'utf-8')
        msg.attach(part1)
        if html:
            html_body = f"<html><body><pre style='font-family:monospace'>{body}</pre></body></html>"
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part2)
        import smtplib
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        log(f"Alerte envoyée -> {config.ALERT_EMAIL}")
        return True
    except Exception as e:
        log(f"Erreur envoi alerte: {e}", "ERROR")
        return False

# -------------------
# Contrôles WordPress
# -------------------
def check_site_availability():
    log("Vérification disponibilité...")
    res = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        r = requests.get(config.SITE_URL, timeout=15)
        res['status_code'] = r.status_code
        res['response_time'] = (datetime.now() - start).total_seconds()
        res['available'] = r.status_code == 200
        if not res['available']:
            incident_manager.add("site_unavailable", {"status_code": r.status_code}, "high", notify=True)
        log(f"Site accessible ✅" if res['available'] else f"HTTP {r.status_code} ⚠️", "INFO" if res['available'] else "WARNING")
    except Exception as e:
        res['error'] = str(e)
        log(f"Erreur accès site: {e}", "ERROR")
        incident_manager.add("site_access_error", {"error": str(e)}, "high", notify=True)
    return res

def check_content_integrity():
    log("Vérification intégrité...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [(config.SITE_URL, "homepage"), (config.SITE_URL+"/feed/", "rss")]
    for url, name in endpoints:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                content = r.text
                ref_file = config.MONITOR_DIR / f"{name}.ref"
                content_file = config.MONITOR_DIR / f"{name}_content.ref"
                current_hash = compute_hash(content)
                old_hash = ref_file.read_text(encoding='utf-8').strip() if ref_file.exists() else ""
                old_content = content_file.read_text(encoding='utf-8') if content_file.exists() else ""
                if current_hash != old_hash and old_hash:
                    results['changed'] = True
                    diff = '\n'.join(difflib.unified_diff(old_content.splitlines(), content.splitlines(), lineterm=''))
                    short_diff = (diff[:1000]+'...') if len(diff)>1000 else diff
                    results['changes'].append({'endpoint':name,'url':url,'diff':short_diff})
                    incident_manager.add("content_changed", {'endpoint':name,'url':url,'diff':short_diff}, "medium", notify=True)
                    log(f"Changement détecté: {name} ⚠️", "WARNING")
                ref_file.write_text(current_hash, encoding='utf-8')
                content_file.write_text(content, encoding='utf-8')
        except Exception as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}", "ERROR")
    return results

def check_for_malicious_patterns():
    log("Recherche patterns suspects...")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [(r'eval\s*\(','eval() potentiellement dangereux','high'),(r'base64_decode\s*\(','Décodage base64 suspect','medium')]
    try:
        r = requests.get(config.SITE_URL, timeout=10)
        if r.status_code==200:
            content = r.text
            for pat, desc, sev in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    sample = [(m[:120]+'...') if len(m)>120 else m for m in matches]
                    results['suspicious_patterns'].append({'pattern':pat,'description':desc,'matches':sample})
                    incident_manager.add("suspicious_code", {'pattern':pat,'description':desc,'matches':sample}, sev, notify=True)
                    log(f"Pattern suspect détecté: {desc} ⚠️", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur détection patterns: {e}", "ERROR")
    return results

def check_ssl_cert():
    results={'valid':False,'days_left':None,'error':None}
    try:
        hostname=config.SITE_URL.replace("https://","").replace("http://","").split("/")[0]
        ctx=ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(8)
            s.connect((hostname,443))
            cert=s.getpeercert()
            not_after=cert.get('notAfter')
            if not_after:
                expire_dt=dateutil_parser.parse(not_after)
                if expire_dt.tzinfo is None:
                    expire_dt=expire_dt.replace(tzinfo=dateutil_tz.tzutc())
                delta=(expire_dt-datetime.now(timezone.utc)).days
                results['valid']=delta>0
                results['days_left']=delta
                if delta<30:
                    incident_manager.add("ssl_warning",{'days_left':delta},"medium", notify=True)
                    log(f"Certificat SSL expire bientôt ({delta} jours) ⚠️","WARNING")
    except Exception as e:
        results['error']=str(e)
        log(f"Erreur SSL: {e}","ERROR")
    return results

# -------------------
# Sauvegarde & Restauration
# -------------------
def backup_wordpress_content(source_dir: Path=config.MONITOR_DIR):
    if not source_dir.exists(): return
    files_copied=0
    for root, _, files in os.walk(source_dir):
        for filename in files:
            src = Path(root)/filename
            dst = config.BACKUP_DIR/(src.relative_to(source_dir))
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src,dst)
                files_copied+=1
            except: pass
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés.", "INFO")

def restore_all_files(target_dir: Path = config.RESTORE_DIR):
    metadata_file = config.BACKUP_DIR / "metadata.json"
    if not metadata_file.exists():
        log("Métadonnées introuvables, restauration impossible.", "ERROR")
        return
    try:
        with metadata_file.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        log(f"Erreur lecture métadonnées: {e}", "ERROR")
        return
    success_count = 0
    for rel_path, meta in metadata.items():
        backup_path = config.BACKUP_DIR / rel_path
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup_path, dest_path)
            success_count += 1
        except Exception as e:
            log(f"Erreur restauration fichier {rel_path}: {e}", "ERROR")
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{len(metadata)} fichiers ===", "INFO")

def generate_report():
    history = incident_manager.load_incidents()
    report_txt = ["WordPress Monitoring Report", "="*30, f"Total incidents: {len(history)}\n"]
    for inc in history[-20:]:
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        report_txt.append(f"[{ts}] [{sev}] {typ} - {inc['details']}")
    report_str = "\n".join(report_txt)
    report_file = config.MONITOR_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_str, encoding='utf-8')

    html_lines = ["<html><head><meta charset='utf-8'><title>WP Monitoring Report</title></head><body>",
                  "<h2>Rapport WordPress</h2>", f"<p>Total incidents: {len(history)}</p>", "<ul>"]
    for inc in history[-20:]:
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        details = json.dumps(inc.get("details", {}), ensure_ascii=False)
        html_lines.append(f"<li><b>{ts}</b> [{sev}] <u>{typ}</u> - <pre>{details}</pre></li>")
    html_lines.append("</ul></body></html>")
    html_file = config.MONITOR_DIR / "logs.html"
    html_file.write_text("\n".join(html_lines), encoding="utf-8")
    log(f"Rapport généré -> {report_file} et {html_file}")
    return report_str

def cleanup_old_reports():
    now = datetime.now()
    for f in config.MONITOR_DIR.glob("report_*.txt"):
        if (now - datetime.fromtimestamp(f.stat().st_mtime)).days > config.LOG_RETENTION_DAYS:
            try: f.unlink(); log(f"Ancien rapport supprimé: {f}", "INFO")
            except Exception as e: log(f"Erreur suppression {f}: {e}", "ERROR")

# -------------------
# Exécution principale
# -------------------
def run_all():
    log("=== Début cycle surveillance ===", "INFO")
    before = incident_manager.load_incidents()

    res_avail = check_site_availability()
    res_integrity = check_content_integrity()
    res_patterns = check_for_malicious_patterns()
    res_ssl = check_ssl_cert()
    backup_wordpress_content()
    report_text = generate_report()
    cleanup_old_reports()

    after = incident_manager.load_incidents()
    new_incidents = after[len(before):] if len(after)>len(before) else []
    
    if not new_incidents:
        subject = f"[INFO WP] Tout est OK - {config.SITE_URL}"
        body = f"Aucun incident détecté sur {config.SITE_URL}.\nDisponibilité: {res_avail['available']}\nIntégrité: {'Changements détectés' if res_integrity['changed'] else 'OK'}\nPatterns suspects: {len(res_patterns.get('suspicious_patterns', []))}\nSSL: {res_ssl.get('days_left')} jours restants"
        send_alert(subject, body)
        log("Aucun incident détecté. Email d'information envoyé.", "INFO")
    else:
        subject = f"[ALERTE WP] {len(new_incidents)} incident(s) détecté(s) - {config.SITE_URL}"
        body = "\n".join([f"- [{inc['severity']}] {inc['type']} @ {inc['timestamp']} : {inc['details']}" for inc in new_incidents])
        send_alert(subject, body)
        log(f"{len(new_incidents)} nouveaux incidents notifiés par email.", "WARNING")

    log("Cycle complet ✅", "INFO")

# -------------------
# CLI
# -------------------
def main():
    parser = argparse.ArgumentParser(description="WP Monitoring & Backup Tool")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--backup", action="store_true", help="Faire backup uniquement")
    parser.add_argument("--restore", type=str, help="Restauration depuis dossier")
    parser.add_argument("--report", action="store_true", help="Générer rapport uniquement")
    parser.add_argument("--send-email", action="store_true", help="Envoyer dernier rapport par email")
    parser.add_argument("--test", action="store_true", help="Tests unitaires simples")
    args = parser.parse_args()

    if args.test:
        log("Exécution des tests unitaires...", "INFO")
    elif args.once:
        run_all()
    elif args.backup:
        backup_wordpress_content()
    elif args.restore:
        restore_all_files(Path(args.restore))
    elif args.report:
        generate_report()
    elif args.send_email:
        html_files = sorted([f for f in config.MONITOR_DIR.glob("*.html")], reverse=True)
        if html_files:
            with html_files[0].open("r", encoding="utf-8") as f: content=f.read()
            send_alert(f"Rapport WP - {config.SITE_URL}", content, html=True)
    else:
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        log(f"Scheduler démarré: interval {config.CHECK_INTERVAL_HOURS}h", "INFO")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__=="__main__":
    main()