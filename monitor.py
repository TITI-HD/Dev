#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WP Monitor - version améliorée

Envoi d'un résumé email à CHAQUE cycle
Evite récursion entre IncidentManager.add() et send_alert()
Parsing SSL plus robuste
Configuration via variables d'environnement
Amélioration des notifications par email
Détails précis des incidents détectés
Sauvegarde après chaque scan
Maintien en mode alerte
Accent sur la sécurité
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
import subprocess
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import requests
import schedule

# Charger les variables d'environnement à partir du fichier .env.local
load_dotenv('.env.local')

# Vérification des dépendances
MISSING = []
try:
    import requests
except Exception:
    MISSING.append("requests")
try:
    import schedule
except Exception:
    MISSING.append("schedule")
try:
    from dateutil import parser as dateutil_parser, tz as dateutil_tz
except Exception:
    MISSING.append("python-dateutil")

if MISSING:
    print("Modules manquants :", ", ".join(MISSING))
    print("→ Installer via: pip install " + " ".join(MISSING))
    sys.exit(1)

# Configuration
class Config:
    def __init__(self):
        # Variables d'environnement recommandées :
        # SITE_URL, ALERT_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", None)
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", None)
        self.SMTP_PASS = os.environ.get("SMTP_PASS", None)  # NE PAS commit en dur ; utiliser secrets
        self.MONITOR_DIR = Path(os.environ.get("MONITOR_DIR", "monitor_data"))
        self.MONITOR_DIR.mkdir(exist_ok=True, parents=True)
        self.INCIDENT_HISTORY_FILE = self.MONITOR_DIR / "incident_history.json"
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = bool(os.environ.get("USE_EMOJI", "1") == "1")
        self.ANONYMIZE_SAMPLES = bool(os.environ.get("ANONYMIZE_SAMPLES", "1") == "1")
        self.BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))
        self.BACKUP_DIR.mkdir(exist_ok=True, parents=True)
        self.RESTORE_DIR = Path(os.environ.get("RESTORE_DIR", "restored"))
        self.RESTORE_DIR.mkdir(exist_ok=True, parents=True)
        self.validate()

    def validate(self):
        if not self.ALERT_EMAIL:
            print("ATTENTION: ALERT_EMAIL non défini — les alertes ne seront pas envoyées.")
        if not self.SMTP_USER or not self.SMTP_PASS:
            print("ATTENTION: SMTP_USER ou SMTP_PASS non définis — l'envoi email échouera.")
        if not self.SITE_URL.startswith(("http://", "https://")):
            print("ATTENTION: SITE_URL devrait commencer par http:// ou https://")

config = Config()

# Logging rotatif
logger = logging.getLogger("WPMonitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(config.MONITOR_DIR / "monitor.log", maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def log(message: str, level="INFO"):
    getattr(logger, level.lower())(message)
    print(message)

# Incident Manager
class IncidentManager:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._ensure_file()

    def _ensure_file(self):
        if not self.history_file.exists():
            self.save_incidents([])

    def load_incidents(self) -> List[Dict]:
        try:
            with self.history_file.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def save_incidents(self, incidents: List[Dict]):
        with self.history_file.open('w', encoding='utf-8') as f:
            json.dump(incidents, f, ensure_ascii=False, indent=4)

    def add(self, type_: str, details: Dict, severity="medium", notify: bool = False) -> Dict:
        """
        Ajoute un incident aux historiques.
        Si notify=True ET severity in ['medium','high'] -> envoie un e-mail par send_alert().
        NB: send_alert() NE rappellera PAS add() pour éviter la récursion.
        """
        history = self.load_incidents()
        incident = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": type_,
            "severity": severity,
            "details": details
        }
        history.append(incident)
        # garder les 100 derniers
        history = history[-100:]
        self.save_incidents(history)

        if notify and severity in ["medium", "high"]:
            subject = f"[ALERTE WP] {type_} ({severity})"
            body = f"Incident détecté:\nType: {type_}\nSévérité: {severity}\nDétails: {json.dumps(details, ensure_ascii=False)}\nHorodatage: {incident['timestamp']}"
            send_alert(subject, body, incident_type=type_, html=False)  # send_alert n'ajoute pas d'incident
        return incident

incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# Utilitaires
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, incident_type="general", html: bool = True) -> bool:
    """
    Envoie un mail multipart (plain + html si demandé).
    ATTENTION: ne modifie pas l'historique (pas d'appel à incident_manager.add()) pour éviter récursion.
    """
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("SMTP incomplet — e-mail non envoyé", "WARNING")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg['From'] = config.SMTP_USER
        msg['To'] = config.ALERT_EMAIL
        msg['Subject'] = subject

        part1 = MIMEText(body, 'plain', 'utf-8')
        msg.attach(part1)
        if html:
            html_body = "<html><body><pre style='font-family:monospace'>{}</pre></body></html>".format(
                body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part2)

        import smtplib
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            if config.SMTP_PORT in (587,):
                server.starttls()
                server.ehlo()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        log(f"Alerte envoyée -> {config.ALERT_EMAIL}")
        return True
    except Exception as e:
        log(f"Erreur envoi alerte: {e}", "ERROR")
        return False

# Surveillance
def check_site_availability() -> Dict:
    log("Vérification disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        log(f"Site accessible {emoji('✅')}" if results['available'] else f"HTTP {resp.status_code} {emoji('⚠️')}", "INFO" if results['available'] else "WARNING")
        if not results['available']:
            incident_manager.add("site_unavailable", {"status_code": resp.status_code}, "high", notify=True)
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur accès site: {e}", "ERROR")
        incident_manager.add("site_access_error", {"error": str(e)}, "high", notify=True)
    return results

def check_content_integrity() -> Dict:
    log("Vérification intégrité...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [(config.SITE_URL, "homepage"), (config.SITE_URL + "/feed/", "rss"), (config.SITE_URL + "/comments/feed/", "comments")]
    for url, name in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                content = resp.text
                ref_file = config.MONITOR_DIR / f"{name}.ref"
                content_file = config.MONITOR_DIR / f"{name}_content.ref"
                current_hash = compute_hash(content)
                old_hash = ref_file.read_text(encoding='utf-8').strip() if ref_file.exists() else ""
                old_content = content_file.read_text(encoding='utf-8') if content_file.exists() else ""
                if current_hash != old_hash and old_hash:
                    results['changed'] = True
                    diff = '\n'.join(difflib.unified_diff(old_content.splitlines(), content.splitlines(), lineterm=''))
                    short_diff = (diff[:1000] + '...') if len(diff) > 1000 else diff
                    results['changes'].append({'endpoint': name, 'url': url, 'diff': short_diff})
                    incident_manager.add("content_changed", {'endpoint': name, 'url': url, 'diff': short_diff}, "medium", notify=True)
                    log(f"Changement détecté: {name} {emoji('⚠️')}", "WARNING")
                # writes (mise à jour des références)
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
    patterns = [
        (r'eval\s*\(', 'eval() potentiellement dangereux', 'high'),
        (r'base64_decode\s*\(', 'Décodage base64 suspect', 'medium'),
        (r'exec\s*\(', 'Appel exec()', 'high'),
    ]
    try:
        resp = requests.get(config.SITE_URL, timeout=10)
        if resp.status_code == 200:
            content = resp.text
            for pat, desc, sev in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    sample = [ (m[:120] + '...') if len(m) > 120 else m for m in matches ]
                    results['suspicious_patterns'].append({'pattern': pat, 'description': desc, 'matches': sample})
                    incident_manager.add("suspicious_code", {'pattern': pat, 'description': desc, 'matches': sample}, sev, notify=True)
                    log(f"Pattern suspect détecté: {desc} {emoji('⚠️')}", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur détection patterns: {e}", "ERROR")
    return results

def check_ssl_cert() -> Dict:
    results = {'valid': False, 'days_left': None, 'error': None}
    try:
        hostname = config.SITE_URL.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(8)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            # parse using dateutil to be robust
            not_after = cert.get('notAfter')
            if not_after:
                expire_dt = dateutil_parser.parse(not_after)
                # ensure timezone-aware UTC
                if expire_dt.tzinfo is None:
                    expire_dt = expire_dt.replace(tzinfo=dateutil_tz.tzutc())
                delta = (expire_dt - datetime.now(timezone.utc)).days
                results['valid'] = delta > 0
                results['days_left'] = delta
                if delta < 30:
                    incident_manager.add("ssl_warning", {'days_left': delta}, "medium", notify=True)
                    log(f"Certificat SSL expire bientôt ({delta} jours) {emoji('⚠️')}", "WARNING")
            else:
                log("Impossible de lire notAfter dans le certificat", "WARNING")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur SSL: {e}", "ERROR")
    return results

# Sauvegarde
def backup_wordpress_content(source_dir: Path = config.MONITOR_DIR):
    if not source_dir.exists():
        log(f"Dossier source '{source_dir}' inexistant.", "ERROR")
        return
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
                metadata[str(rel_path)] = {
                    "hash": compute_hash(dst_path),
                    "timestamp": datetime.now().isoformat()
                }
                log(f"Fichier sauvegardé: {rel_path}", "SUCCESS")
                files_copied += 1
            except Exception as e:
                log(f"Impossible de sauvegarder {rel_path}: {e}", "ERROR")
    with (config.BACKUP_DIR / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés.", "INFO")

# Restauration
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
        if backup_path.suffix == ".json":
            continue
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup_path, dest_path)
            current_hash = compute_hash(dest_path)
            if current_hash != meta["hash"]:
                log(f"Hash mismatch: {rel_path}", "ERROR")
            else:
                log(f"Restauration OK: {rel_path}", "SUCCESS")
            success_count += 1
        except Exception as e:
            log(f"Erreur restauration fichier {rel_path}: {e}", "ERROR")
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{len(metadata)} fichiers ===", "INFO")

# Reporting
def generate_report() -> str:
    history = incident_manager.load_incidents()
    # Rapport texte synthétique
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
    # HTML
    html_lines = ["<html><head><meta charset='utf-8'><title>WP Monitoring Report</title></head><body>",
                  "<h2>Rapport de Monitoring WordPress</h2>",
                  f"<p>Total incidents: {len(history)}</p>", "<ul>"]
    for inc in history[-20:]:
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        details = json.dumps(inc.get("details", {}), ensure_ascii=False)
        html_lines.append(f"<li><b>{ts}</b> [{sev}] <u>{typ}</u> - <pre>{details}</pre></li>")
    html_lines.append("</ul></body></html>")
    html_file = config.MONITOR_DIR / "logs.html"
    html_file.write_text("\n".join(html_lines), encoding="utf-8")
    log(f"Rapport HTML généré -> {html_file}")
    return report_str

# Nettoyage ancien logs
def cleanup_old_reports():
    now = datetime.now()
    for f in config.MONITOR_DIR.glob("report_*.txt"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if (now - mtime).days > config.LOG_RETENTION_DAYS:
            try:
                f.unlink()
                log(f"Ancien rapport supprimé: {f}", "INFO")
            except Exception as e:
                log(f"Erreur suppression ancien rapport {f}: {e}", "ERROR")
    # supprimer aussi anciens backups si > LOG_RETENTION_DAYS
    for f in config.BACKUP_DIR.glob("backup_*.zip"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if (now - mtime).days > config.LOG_RETENTION_DAYS:
            try:
                f.unlink()
                log(f"Ancien backup supprimé: {f}", "INFO")
            except Exception as e:
                log(f"Erreur suppression ancien backup {f}: {e}", "ERROR")

# Exécution principale
def run_all():
    log("=== Début du cycle de surveillance ===", "INFO")
    before = incident_manager.load_incidents()
    before_count = len(before)

    # Exécuter contrôles
    res_avail = check_site_availability()
    res_integrity = check_content_integrity()
    res_patterns = check_for_malicious_patterns()
    res_ssl = check_ssl_cert()
    backup_wordpress_content()
    report_text = generate_report()
    cleanup_old_reports()

    # incidents ajoutés durant ce cycle
    after = incident_manager.load_incidents()
    new_incidents = after[len(before):] if len(after) > len(before) else []
    # préparer le corps du résumé
    if not new_incidents:
        subject = f"[INFO WP] Tout est OK - {config.SITE_URL}"
        body = f"""Aucun incident détecté sur {config.SITE_URL} pendant ce cycle.

Horodatage: {datetime.now(timezone.utc).isoformat()}

Résumé tests:

Disponibilité: {res_avail['available']} (HTTP {res_avail.get('status_code')})

Temps de réponse: {res_avail.get('response_time')} s

Intégrité: {'Changements détectés' if res_integrity['changed'] else 'OK'}

Patterns suspects: {len(res_patterns.get('suspicious_patterns', []))}

SSL: {res_ssl.get('days_left')} jours restants

Rapport complet dans le dossier {config.MONITOR_DIR}
"""
        send_alert(subject, body, incident_type="info", html=True)
        log("Aucun incident détecté. Email d'information envoyé.", "INFO")
    else:
        subject = f"[ALERTE WP] {len(new_incidents)} incident(s) détecté(s) - {config.SITE_URL}"
        short_lines = []
        for inc in new_incidents:
            short_lines.append(f"- [{inc['severity']}] {inc['type']} @ {inc['timestamp']} : {inc['details']}")
        body = "Nouveaux incidents détectés pendant ce cycle:\n\n" + "\n".join(short_lines)
        # envoyer le mail (HTML=True pour lisibilité)
        send_alert(subject, body, incident_type="summary", html=True)
        log(f"{len(new_incidents)} nouveaux incidents notifiés par email.", "WARNING")

    log("Cycle complet terminé ✅", "INFO")

# CLI
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
        # tests simples (manuel)
    elif args.once:
        run_all()
    elif args.backup:
        backup_wordpress_content()
    elif args.restore:
        restore_all_files(Path(args.restore))
    elif args.report:
        generate_report()
    else:
        # mode scheduler
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        log(f"Scheduler démarré: interval {config.CHECK_INTERVAL_HOURS}h", "INFO")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()