#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" 
WP Monitor - version complète et améliorée

Fonctions principales :
· Vérification disponibilité du site
· Intégrité du contenu (hash + diff)
· Recherche patterns suspects
· Vérification certificat SSL
· Sauvegarde fichiers de monitoring
· Restauration depuis backups
· Historique incidents et notifications email
· Rapports TXT et HTML
· Scheduler ou exécution unique
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
import smtplib
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import schedule

# --- Charger variables d'environnement ---
from dotenv import load_dotenv
load_dotenv('.env.local')

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
    from dateutil import parser as dateutil_parser, tz as dateutil_tz
except ImportError:
    MISSING.append("python-dateutil")
try:
    from dotenv import load_dotenv
except ImportError:
    MISSING.append("python-dotenv")

if MISSING:
    print("Modules manquants :", ", ".join(MISSING))
    print("→ Installer via: pip install " + " ".join(MISSING))
    sys.exit(1)

# --- Configuration ---
class Config:
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", None)
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", None)
        self.SMTP_PASS = os.environ.get("SMTP_PASS", None)
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
        if not self.SITE_URL.startswith(('http://', 'https://')):
            print(f"URL invalide: {self.SITE_URL}")
            sys.exit(1)

config = Config()

# --- Logging ---
logger = logging.getLogger("WPMonitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(config.MONITOR_DIR / "monitor.log", maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def log(message: str, level="INFO"):
    getattr(logger, level.lower())(message)
    print(f"[{level}] {message}")

# --- Gestion des incidents ---
class IncidentManager:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._ensure_file()
    
    def _ensure_file(self):
        if not self.history_file.exists():
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def load_incidents(self) -> List[Dict]:
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def save_incidents(self, incidents: List[Dict]):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(incidents, f, indent=2, ensure_ascii=False)
    
    def add(self, incident_type: str, details: Dict, severity: str = "medium", notify: bool = False):
        incidents = self.load_incidents()
        incident = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": incident_type,
            "severity": severity,
            "details": json.dumps(details, ensure_ascii=False)
        }
        incidents.append(incident)
        self.save_incidents(incidents)
        
        if notify:
            subject = f"[WP Monitor] Incident {severity.upper()}: {incident_type}"
            body = f"Type: {incident_type}\nSeverity: {severity}\nDetails: {json.dumps(details, indent=2)}\nTime: {incident['timestamp']}"
            send_alert(subject, body, incident_type)

incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# --- Utilitaires ---
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    return symbol if config.USE_EMOJI else ""

# --- Notification email ---
def send_alert(subject: str, body: str, incident_type="general", html: bool = False) -> bool:
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("Configuration SMTP incomplète — e-mail non envoyé", "WARNING")
        return False
    
    try:
        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "html"))
        else:
            msg = MIMEText(body)
        
        msg['From'] = config.SMTP_USER
        msg['To'] = config.ALERT_EMAIL
        msg['Subject'] = subject
        
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        
        log(f"Alerte email envoyée: {subject}", "INFO")
        return True
    except Exception as e:
        log(f"Erreur envoi email: {e}", "ERROR")
        return False

# --- Fonctions de surveillance ---
def check_site_availability() -> Dict:
    log("Vérification disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = time.time()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['response_time'] = time.time() - start
        results['status_code'] = resp.status_code
        results['available'] = resp.status_code == 200
        
        if results['available']:
            log(f"Site accessible {emoji('✅')}", "INFO")
        else:
            log(f"HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
            incident_manager.add("site_unavailable", {"status_code": resp.status_code}, "high", notify=True)
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur accès site: {e}", "ERROR")
        incident_manager.add("site_access_error", {"error": str(e)}, "high", notify=True)
    
    return results

def check_content_integrity() -> Dict:
    log("Vérification intégrité du site...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [
        (config.SITE_URL, "homepage"),
        (config.SITE_URL + "/feed/", "rss"),
        (config.SITE_URL + "/comments/feed/", "comments")
    ]
    
    for url, name in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                log(f"Erreur HTTP {resp.status_code} pour {url}", "WARNING")
                continue
            
            content = resp.text
            ref_file = config.MONITOR_DIR / f"{name}.ref"
            content_file = config.MONITOR_DIR / f"{name}_content.txt"
            current_hash = compute_hash(content)
            
            # Vérifier si le fichier de référence existe
            if ref_file.exists():
                old_hash = ref_file.read_text(encoding='utf-8').strip()
                
                if old_hash != current_hash:
                    results['changed'] = True
                    log(f"Changement détecté sur {name} {emoji('⚠️')}", "WARNING")
                    
                    # Charger l'ancien contenu si disponible
                    old_content = ""
                    if content_file.exists():
                        old_content = content_file.read_text(encoding='utf-8')
                    
                    # Calculer les différences
                    diff = list(difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"old_{name}",
                        tofile=f"new_{name}"
                    ))
                    
                    diff_text = ''.join(diff)
                    results['changes'].append({
                        'endpoint': name,
                        'diff': diff_text
                    })
                    
                    incident_manager.add(
                        "content_changed", 
                        {"endpoint": name, "diff": diff_text[:500] + "..." if len(diff_text) > 500 else diff_text},
                        "medium",
                        notify=True
                    )
                else:
                    log(f"Aucun changement sur {name} {emoji('✅')}", "INFO")
            else:
                log(f"Première vérification pour {name}, création référence", "INFO")
            
            # Mettre à jour les fichiers de référence
            ref_file.write_text(current_hash, encoding='utf-8')
            content_file.write_text(content, encoding='utf-8')
            
        except Exception as e:
            results['error'] = str(e)
            log(f"Erreur vérification intégrité {name}: {e}", "ERROR")
    
    return results

def check_for_malicious_patterns() -> Dict:
    log("Recherche de patterns suspects...")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [
        (r'eval\s*\(', 'eval() potentiellement dangereux', 'high'),
        (r'base64_decode\s*\(', 'Décodage base64 suspect', 'medium'),
        (r'exec\s*\(', 'Appel exec()', 'high'),
    ]
    
    try:
        resp = requests.get(config.SITE_URL, timeout=10)
        if resp.status_code != 200:
            log(f"Erreur HTTP {resp.status_code} pour {config.SITE_URL}", "WARNING")
            return results
        
        content = resp.text
        for pat, desc, sev in patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            if matches:
                sample = [m[:50] + '...' if len(m) > 50 else m for m in matches[:3]]  # Limiter les exemples
                results['suspicious_patterns'].append({
                    'pattern': pat, 
                    'description': desc, 
                    'matches': sample
                })
                
                incident_manager.add(
                    "suspicious_code",
                    {'pattern': pat, 'description': desc, 'matches': sample},
                    sev,
                    notify=True
                )
                log(f"Pattern suspect détecté: {desc} {emoji('⚠️')}", "WARNING")
    
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur détection patterns: {e}", "ERROR")
    
    return results

def check_ssl_cert() -> Dict:
    log("Vérification certificat SSL...")
    results = {'valid': False, 'days_left': None, 'error': None}
    
    try:
        hostname = config.SITE_URL.replace("https://", "").replace("http://", "").split("/")[0]
        ctx = ssl.create_default_context()
        
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(8)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            
            # Extraire la date d'expiration
            not_after = cert.get('notAfter')
            if not_after:
                expire_dt = dateutil_parser.parse(not_after)
                if expire_dt.tzinfo is None:
                    expire_dt = expire_dt.replace(tzinfo=dateutil_tz.UTC)
                
                now = datetime.now(timezone.utc)
                delta = (expire_dt - now).days
                results['valid'] = delta > 0
                results['days_left'] = delta
                
                if delta <= 30:
                    log(f"Certificat SSL expire bientôt ({delta} jours) {emoji('⚠️')}", "WARNING")
                    incident_manager.add(
                        "ssl_warning", 
                        {'days_left': delta, 'hostname': hostname}, 
                        "medium", 
                        notify=True
                    )
                else:
                    log(f"Certificat SSL valide ({delta} jours restants) {emoji('✅')}", "INFO")
            else:
                log("Impossible de lire 'notAfter' dans le certificat", "WARNING")
    
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur vérification SSL: {e}", "ERROR")
    
    return results

# --- Sauvegarde ---
def backup_wordpress_content(source_dir: Path = config.MONITOR_DIR):
    if not source_dir.exists():
        log(f"Dossier source '{source_dir}' inexistant.", "ERROR")
        return
    
    metadata = {}
    files_copied = 0
    
    # Créer un sous-dossier avec horodatage
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config.BACKUP_DIR / f"backup_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)
    
    for item in source_dir.iterdir():
        if item.is_file():
            try:
                # Copier le fichier
                dest_file = backup_path / item.name
                shutil.copy2(item, dest_file)
                
                # Calculer le hash
                file_content = item.read_text(encoding='utf-8')
                metadata[item.name] = {
                    "hash": compute_hash(file_content),
                    "timestamp": datetime.now().isoformat(),
                    "size": len(file_content)
                }
                
                log(f"Fichier sauvegardé: {item.name}", "INFO")
                files_copied += 1
            except Exception as e:
                log(f"Impossible de sauvegarder {item.name}: {e}", "ERROR")
    
    # Sauvegarder les métadonnées
    metadata_file = backup_path / "metadata.json"
    with metadata_file.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés vers {backup_path}.", "INFO")

# --- Restauration ---
def restore_all_files(target_dir: Path = config.RESTORE_DIR):
    # Trouver le dernier backup
    backups = sorted(config.BACKUP_DIR.glob("backup_*"), key=os.path.getmtime, reverse=True)
    
    if not backups:
        log("Aucune sauvegarde trouvée", "ERROR")
        return
    
    latest_backup = backups[0]
    metadata_file = latest_backup / "metadata.json"
    
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
    for filename, fileinfo in metadata.items():
        backup_file = latest_backup / filename
        dest_file = target_dir / filename
        
        if not backup_file.exists():
            log(f"Fichier de backup manquant: {filename}", "WARNING")
            continue
        
        try:
            # Copier le fichier
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, dest_file)
            
            # Vérifier le hash
            current_content = dest_file.read_text(encoding='utf-8')
            current_hash = compute_hash(current_content)
            
            if current_hash != fileinfo["hash"]:
                log(f"Hash mismatch: {filename}", "ERROR")
            else:
                log(f"Restauration OK: {filename}", "INFO")
                success_count += 1
                
        except Exception as e:
            log(f"Erreur restauration fichier {filename}: {e}", "ERROR")
    
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{len(metadata)} fichiers ===", "INFO")

# --- Reporting ---
def generate_report() -> str:
    history = incident_manager.load_incidents()
    report_lines = [
        "WordPress Monitoring Report",
        "============================",
        f"Généré le: {datetime.now().isoformat()}",
        f"Site surveillé: {config.SITE_URL}",
        f"Total incidents: {len(history)}",
        ""
    ]
    
    for inc in history[-20:]:  # Les 20 incidents les plus récents
        ts = inc["timestamp"]
        typ = inc["type"]
        sev = inc["severity"]
        details = inc["details"]
        report_lines.append(f"[{ts}] [{sev}] {typ} - {details}")
    
    report_str = "\n".join(report_lines)
    report_file = config.MONITOR_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_str, encoding='utf-8')
    
    log(f"Rapport TXT généré -> {report_file}", "INFO")
    return report_str

# --- Nettoyage anciens logs ---
def cleanup_old_reports():
    now = datetime.now()
    
    # Nettoyer les anciens rapports
    for f in config.MONITOR_DIR.glob("report_*.txt"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if (now - mtime).days > config.LOG_RETENTION_DAYS:
            try:
                f.unlink()
                log(f"Ancien rapport supprimé: {f.name}", "INFO")
            except Exception as e:
                log(f"Erreur suppression ancien rapport {f.name}: {e}", "ERROR")
    
    # Nettoyer les anciens backups
    for f in config.BACKUP_DIR.glob("backup_*"):
        if f.is_dir():
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if (now - mtime).days > config.LOG_RETENTION_DAYS:
                try:
                    shutil.rmtree(f)
                    log(f"Ancien backup supprimé: {f.name}", "INFO")
                except Exception as e:
                    log(f"Erreur suppression ancien backup {f.name}: {e}", "ERROR")

# --- Exécution principale ---
def run_all():
    log("=== Début du cycle de surveillance ===", "INFO")
    before_incidents = incident_manager.load_incidents()
    before_count = len(before_incidents)
    
    # Exécuter toutes les vérifications
    res_avail = check_site_availability()
    res_integrity = check_content_integrity()
    res_patterns = check_for_malicious_patterns()
    res_ssl = check_ssl_cert()
    
    # Nettoyer les anciens rapports
    cleanup_old_reports()
    
    # Vérifier s'il y a de nouveaux incidents
    after_incidents = incident_manager.load_incidents()
    new_incidents = after_incidents[before_count:]
    
    # Générer un rapport
    generate_report()
    
    # Envoyer une notification si nécessaire
    if not new_incidents:
        subject = f"[WP Monitor] Site OK - {config.SITE_URL}"
        body = f"""Surveillance WordPress - Aucun problème détecté

Horodatage: {datetime.now(timezone.utc).isoformat()}
Disponibilité: {res_avail['available']} (HTTP {res_avail.get('status_code')})
Temps de réponse: {res_avail.get('response_time', 0):.2f} s
Intégrité: {'Changements détectés' if res_integrity['changed'] else 'OK'}
Patterns suspects: {len(res_patterns.get('suspicious_patterns', []))}
SSL: {res_ssl.get('days_left')} jours restants

Rapport complet dans le dossier {config.MONITOR_DIR}
"""
        send_alert(subject, body, incident_type="info", html=False)
        log("Aucun incident détecté. Email d'information envoyé.", "INFO")
    else:
        subject = f"[ALERTE WP] {len(new_incidents)} incident(s) détecté(s) - {config.SITE_URL}"
        body_lines = [f"- [{inc['severity']}] {inc['type']} @ {inc['timestamp']} : {inc['details']}" 
                     for inc in new_incidents]
        body = "Nouveaux incidents détectés pendant ce cycle:\n\n" + "\n".join(body_lines)
        send_alert(subject, body, incident_type="summary", html=False)
        log(f"{len(new_incidents)} nouveaux incidents notifiés par email.", "WARNING")
    
    log("=== Fin du cycle de surveillance ===\n", "INFO")

# --- CLI ---
def main():
    parser = argparse.ArgumentParser(description="WP Monitoring & Backup Tool")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--backup", action="store_true", help="Faire backup uniquement")
    parser.add_argument("--restore", action="store_true", help="Restauration depuis le dernier backup")
    parser.add_argument("--report", action="store_true", help="Générer rapport uniquement")
    parser.add_argument("--test", action="store_true", help="Exécuter tests unitaires simples")
    args = parser.parse_args()
    
    if args.backup:
        backup_wordpress_content()
    elif args.restore:
        restore_all_files()
    elif args.report:
        generate_report()
    elif args.test:
        # Tests simples
        print("Test de base...")
        print(f"URL: {config.SITE_URL}")
        print(f"Hash test: {compute_hash('test')}")
    elif args.once:
        run_all()
    else:
        # Mode planifié
        log(f"Démarrage du monitoring planifié (toutes les {config.CHECK_INTERVAL_HOURS} heures)", "INFO")
        schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_all)
        
        # Exécuter une première fois immédiatement
        run_all()
        
        # Boucle principale
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Vérifier toutes les minutes
        except KeyboardInterrupt:
            log("Arrêt demandé par l'utilisateur", "INFO")

if __name__ == "__main__":
    main()