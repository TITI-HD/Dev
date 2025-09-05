#!/usr/bin/env python3
"""
Script principal de surveillance WordPress amélioré
- Notifications détaillées avec type, heure et contenu des modifications
- Rapports complets avec solutions proposées
- Fonctionnement autonome avec planification
- Modifications: Sécurité renforcée, backup optionnel, diffs pour changements, logging rotatif
"""

import os
import sys
import time
import json
import glob
import smtplib
import hashlib
import re
import ssl
import socket
import difflib  # Ajouté pour diffs de contenu
import logging  # Ajouté pour logging rotatif
from logging.handlers import RotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# --- Vérification des dépendances tierces avant d'importer ---
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
    print("ERREUR: modules Python manquants :", ", ".join(MISSING))
    print()
    print("→ Solution recommandée (manuel) :")
    print("   1) Crée un venv : python -m venv .venv")
    print("   2) Active-le :")
    print("        Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1")
    print("        Linux/macOS: source .venv/bin/activate")
    print("   3) Installe les dépendances : python -m pip install --upgrade pip")
    print("      puis : python -m pip install -r requirements.txt")
    print()
    print("→ Pour installation automatique (optionnelle), relance le script avec --install-deps")
    if "--install-deps" in sys.argv:
        import subprocess
        try:
            print("Installation automatique des paquets manquants :", ", ".join(MISSING))
            subprocess.check_call([sys.executable, "-m", "pip", "install", *MISSING])
            print("Installation terminée. Relance le script normalement.")
        except Exception as e:
            print("Échec de l'installation automatique:", e)
    sys.exit(1)

# Import backup.py (optionnel maintenant)
backup_available = True
try:
    from backup import backup_wordpress_content
except ImportError:
    backup_available = False
    print("[AVERTISSEMENT] Impossible d'importer backup_wordpress_content depuis backup.py. Backup désactivé.")

# === Configuration ===
class Config:
    """Centralized configuration class / Classe de configuration centralisée"""
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
        self.SMTP_PASS = os.environ.get("SMTP_PASS", "")  # Obligatoire maintenant
        self.MONITOR_DIR = "monitor_data"
        self.INCIDENT_HISTORY_FILE = os.path.join(self.MONITOR_DIR, "incident_history.json")
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = bool(os.environ.get("USE_EMOJI", os.name != "nt"))
        self.ANONYMIZE_SAMPLES = bool(os.environ.get("ANONYMIZE_SAMPLES", True))  # Nouveau: Anonymiser samples suspects
        
        # Créer le répertoire de surveillance s'il n'existe pas
        Path(self.MONITOR_DIR).mkdir(exist_ok=True)
        
        # Valider la configuration
        self.validate()
    
    def validate(self):
        """Validate configuration / Valide la configuration"""
        if not self.SMTP_PASS:
            raise ValueError("ERREUR: SMTP_PASS est obligatoire pour les alertes email.")
        
        if not self.SITE_URL.startswith(('http://', 'https://')):
            print("ATTENTION: SITE_URL devrait commencer par http:// ou https://")

# Initialiser la configuration
config = Config()

# === Logging rotatif ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(config.MONITOR_DIR, "monitor.log"),
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5
)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def log(message: str, level: str = "INFO"):
    """Journalisation avec timestamp (utilise logging maintenant)"""
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)
    print(message)  # Garder l'affichage console pour debug

# === Gestion des incidents ===
class IncidentManager:
    """Incident manager / Gestionnaire d'incidents"""
    def __init__(self, history_file: str):
        self.history_file = history_file
    
    def load_incident_history(self) -> List[Dict]:
        """Load incident history / Charge l'historique des incidents"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []
    
    def save_incident_history(self, history: List[Dict]):
        """Save incident history / Sauvegarde l'historique"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            log(f"Erreur lors de la sauvegarde de l'historique: {e}", "ERROR")
    
    def add_incident(self, incident_type: str, details: Dict, severity: str = "medium") -> Dict:
        """Add an incident / Ajoute un incident"""
        history = self.load_incident_history()
        incident = {
            "timestamp": datetime.now().isoformat(),
            "type": incident_type,
            "severity": severity,
            "details": details
        }
        history.append(incident)
        if len(history) > 100:
            history = history[-100:]
        self.save_incident_history(history)
        return incident

incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# === Utilitaires ===
def compute_hash(content: str) -> str:
    """Compute SHA256 hash / Calcule le hash SHA256"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    """Return emoji if enabled / Retourne l'emoji si activé"""
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, incident_type: str = "general") -> bool:
    """Send email alert and record incident / Envoie une alerte et enregistre l'incident"""
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("Configuration SMTP incomplète.", "WARNING")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config.SMTP_USER
        msg['To'] = config.ALERT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        
        incident_manager.add_incident(incident_type, {
            "subject": subject,
            "body": body,
            "sent_via": "email"
        })
        
        log("SUCCÈS: Alerte envoyée")
        return True
    except Exception as e:
        log(f"ERREUR lors de l'envoi d'alerte : {e}", "ERROR")
        return False

def generate_solutions_report(issues: Dict) -> str:
    """Generate solutions report / Génère un rapport de solutions"""
    solutions = []
    
    if not issues.get('available', True):
        solutions.append({
            "problem": "Site inaccessible",
            "solutions": [
                "Vérifier la connexion Internet",
                "Vérifier si le serveur hébergeant WordPress est en ligne",
                "Contacter l'hébergeur en cas de panne prolongée"
            ]
        })
    
    if issues.get('content_changed', False):
        solutions.append({
            "problem": "Contenu modifié",
            "solutions": [
                "Vérifier les logs WordPress pour identifier l'auteur des modifications",
                "Contrôler les comptes utilisateurs ayant des droits d'édition",
                "Restaurer une version précédente depuis la sauvegarde si nécessaire"
            ]
        })
    
    if issues.get('suspicious_patterns', []):
        solutions.append({
            "problem": "Code suspect détecté",
            "solutions": [
                "Analyser les fichiers modifiés avec un antivirus",
                "Scanner le site avec un outil de sécurité WordPress comme Wordfence",
                "Changer tous les mots de passe administrateur",
                "Mettre à jour WordPress et tous les plugins"
            ]
        })
    
    if issues.get('ssl_invalid', False):
        solutions.append({
            "problem": "Certificat SSL invalide",
            "solutions": [
                "Renouveler le certificat SSL",
                "Vérifier la date d'expiration du certificat",
                "Contacter l'hébergeur pour assistance"
            ]
        })
    
    if not solutions:
        return "✅ Aucun problème détecté, tout fonctionne normalement."
    
    report = "🔧 SOLUTIONS PROPOSÉES :\n\n"
    for i, solution_set in enumerate(solutions, 1):
        report += f"{i}. {solution_set['problem']} :\n"
        for j, solution in enumerate(solution_set['solutions'], 1):
            report += f"   {j}. {solution}\n"
        report += "\n"
    
    return report

# === Détection type WordPress (nouveau) ===
def detect_wp_type() -> str:
    """Detect if WP is self-hosted or hosted / Détecte le type de WP"""
    try:
        resp = requests.get(f"{config.SITE_URL}/wp-json/", timeout=5)
        if resp.status_code == 200 and "WordPress.com" in resp.text:
            return "hosted (WordPress.com)"
        return "self-hosted"
    except Exception:
        return "inconnu"

# === Vérifications améliorées ===
def check_site_availability() -> Dict:
    """Check site availability / Vérifie la disponibilité"""
    log("Vérification de disponibilité...")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        
        if results['available']:
            log(f"Site accessible {emoji('✅')}")
        else:
            log(f"Site retourne HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
            incident_manager.add_incident("site_unavailable", {
                "status_code": resp.status_code,
                "response_time": results['response_time']
            }, "high")
            
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"ERREUR accès site : {e}", "ERROR")
        incident_manager.add_incident("site_unavailable", {"error": str(e)}, "high")
        
    return results

def check_content_integrity() -> Dict:
    """Check content integrity with diffs / Vérifie l'intégrité avec diffs"""
    log("Vérification d'intégrité...")
    results = {'changed': False, 'changes': [], 'error': None}
    endpoints = [
        (config.SITE_URL, "homepage"),
        (config.SITE_URL + "/feed/", "rss"),
        (config.SITE_URL + "/comments/feed/", "comments")
    ]
    
    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                current_content = response.text
                current_hash = compute_hash(current_content)
                ref_file = os.path.join(config.MONITOR_DIR, f"{name}.ref")
                content_file = os.path.join(config.MONITOR_DIR, f"{name}_content.ref")  # Nouveau: Stocke contenu pour diffs
                
                if os.path.exists(ref_file) and os.path.exists(content_file):
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        old_hash = f.read().strip()
                    with open(content_file, 'r', encoding='utf-8') as f:
                        old_content = f.read()
                    
                    if current_hash != old_hash:
                        results['changed'] = True
                        diff = '\n'.join(difflib.unified_diff(
                            old_content.splitlines(),
                            current_content.splitlines(),
                            lineterm=''
                        ))
                        change_detail = {
                            'endpoint': name, 
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'old_hash': old_hash,
                            'new_hash': current_hash,
                            'diff': diff[:500] + '...' if len(diff) > 500 else diff  # Limite pour rapports
                        }
                        results['changes'].append(change_detail)
                        
                        incident_manager.add_incident("content_changed", change_detail, "medium")
                        log(f"Changement détecté : {name} {emoji('⚠️')}", "WARNING")
                        
                        # Mettre à jour références
                        with open(ref_file, 'w', encoding='utf-8') as f:
                            f.write(current_hash)
                        with open(content_file, 'w', encoding='utf-8') as f:
                            f.write(current_content)
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    with open(content_file, 'w', encoding='utf-8') as f:
                        f.write(current_content)
                    log(f"Référence créée : {name}")
            else:
                log(f"Erreur HTTP sur {url}: {response.status_code}", "WARNING")
                
        except requests.RequestException as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}", "ERROR")
            
    return results

def check_for_malicious_patterns() -> Dict:
    """Search for malicious patterns with scoring / Recherche patterns avec scoring"""
    log("Recherche de patterns suspects...")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [  # Amélioré avec sévérité
        (r'eval\s*\(', "Fonction eval() potentiellement dangereuse", "high"),
        (r'base64_decode\s*\(', "Décodage base64 suspect", "medium"),
        (r'exec\s*\(', "Appel système exec()", "high"),
        (r'system\s*\(', "Appel système system()", "high"),
        (r'shell_exec\s*\(', "Appel système shell_exec()", "high"),
        (r'<script>[^<]*(alert|prompt|confirm)[^<]*</script>', "Script JavaScript suspect", "medium"),
        (r'<iframe[^>]*src=[^>]*>', "Iframe potentiellement malveillant", "medium")
    ]
    whitelist_patterns = []  # Ajoute des regex à ignorer si besoin, e.g., [r'known_safe_eval']
    
    try:
        response = requests.get(config.SITE_URL, timeout=10)
        if response.status_code == 200:
            content = response.text
            
            for pat, description, severity in patterns:
                if any(re.search(wp, content, re.IGNORECASE) for wp in whitelist_patterns):
                    continue  # Skip si whitelist match
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    sample = matches[0] if len(matches) > 0 else None
                    if config.ANONYMIZE_SAMPLES:
                        sample = "[ANONYMISÉ]"  # Anonymiser
                    results['suspicious_patterns'].append({
                        'pattern': pat,
                        'description': description,
                        'severity': severity,
                        'matches_count': len(matches),
                        'sample': sample
                    })
                    
                    incident_manager.add_incident("suspicious_code", {
                        'pattern': pat,
                        'description': description,
                        'severity': severity,
                        'matches_count': len(matches)
                    }, severity)
                    
                    log(f"Pattern suspect ({severity}): {description} ({len(matches)}) {emoji('⚠️')}", "WARNING")
                    
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"Erreur pattern : {e}", "ERROR")
        
    return results

def check_ssl_certificate() -> Dict:
    """Check SSL certificate with chain validation / Vérifie SSL avec chaîne"""
    log("Vérification du certificat SSL...")
    
    results = {"valid": False, "error": None, "expires_in": None, "chain_valid": False}
    try:
        hostname = config.SITE_URL.replace("https://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                results["valid"] = True
                
                # Vérif chaîne (basique: check si issuer présent)
                results["chain_valid"] = 'issuer' in cert
                
                # Date expiration avec timezone fixée
                expire_date = parser.parse(cert['notAfter']).astimezone(tz.UTC)
                now = datetime.now(tz.UTC)
                results["expires_in"] = (expire_date - now).days
                
                if results["expires_in"] < 7:
                    incident_manager.add_incident("ssl_expiring_soon", {
                        "hostname": hostname,
                        "expire_date": cert['notAfter'],
                        "days_until_expire": results["expires_in"]
                    }, "medium")
                    log(f"Certificat expire dans {results['expires_in']} jours {emoji('⚠️')}", "WARNING")
                else:
                    log(f"Certificat valide (expire dans {results['expires_in']} jours) {emoji('✅')}")
                    
    except Exception as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR SSL: {e}", "ERROR")
        incident_manager.add_incident("ssl_error", {"error": str(e)}, "high")
        
    return results

# === Génération de rapports ===
def generate_detailed_report(availability, integrity, security, ssl_check) -> str:
    """Generate detailed report / Génère un rapport détaillé"""
    wp_type = detect_wp_type()
    report = f"📊 RAPPORT DE SURVEILLANCE WORDPRESS\n"
    report += f"📍 Site: {config.SITE_URL} (Type: {wp_type})\n"  # Ajout type WP
    report += f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "="*50 + "\n\n"
    
    # Sections inchangées, mais avec diffs dans integrity
    report += "🌐 DISPONIBILITÉ DU SITE:\n"
    if availability['available']:
        report += f"✅ Site accessible (HTTP {availability['status_code']}, {availability['response_time']:.2f}s)\n"
    else:
        report += f"❌ Site inaccessible\n"
        if availability['error']:
            report += f"   Erreur: {availability['error']}\n"
        else:
            report += f"   Code HTTP: {availability['status_code']}\n"
    report += "\n"
    
    report += "🔍 INTÉGRITÉ DU CONTENU:\n"
    if integrity['changed']:
        report += f"⚠️ {len(integrity['changes'])} modification(s) détectée(s):\n"
        for change in integrity['changes']:
            report += f"   - {change['endpoint']}: {change['url']}\n"
            report += f"     Heure: {change['timestamp']}\n"
            report += f"     Diff: {change['diff']}\n"
    else:
        report += "✅ Aucune modification détectée\n"
    
    if integrity['error']:
        report += f"   Erreur: {integrity['error']}\n"
    report += "\n"
    
    report += "🛡️ SÉCURITÉ:\n"
    if security['suspicious_patterns']:
        report += f"⚠️ {len(security['suspicious_patterns'])} pattern(s) suspect(s) détecté(s):\n"
        for pattern in security['suspicious_patterns']:
            report += f"   - {pattern['description']} ({pattern['severity']})\n"
            report += f"     Occurences: {pattern['matches_count']}\n"
            report += f"     Sample: {pattern['sample']}\n"
    else:
        report += "✅ Aucun code suspect détecté\n"
    
    if security['error']:
        report += f"   Erreur: {security['error']}\n"
    report += "\n"
    
    report += "🔒 CERTIFICAT SSL:\n"
    if ssl_check['valid']:
        status = "valide" if ssl_check['chain_valid'] else "valide mais chaîne incomplète"
        if ssl_check['expires_in'] < 7:
            report += f"⚠️ Certificat {status} mais expire dans {ssl_check['expires_in']} jours\n"
        else:
            report += f"✅ Certificat {status} (expire dans {ssl_check['expires_in']} jours)\n"
    else:
        report += f"❌ Certificat invalide: {ssl_check['error']}\n"
    report += "\n"
    
    return report

# === Monitoring principal ===
def main_monitoring() -> str:
    """Run full monitoring / Exécute surveillance complète"""
    log("=== DÉMARRAGE SURVEILLANCE ===")

    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    ssl_check = check_ssl_certificate()

    detailed_report = generate_detailed_report(availability, integrity, security, ssl_check)

    issues = {
        'available': availability['available'],
        'content_changed': integrity['changed'],
        'suspicious_patterns': len(security['suspicious_patterns']) > 0,
        'ssl_invalid': not ssl_check['valid'] or ssl_check['expires_in'] < 7 or not ssl_check['chain_valid']
    }

    solutions_report = generate_solutions_report(issues)
    full_report = detailed_report + "\n" + solutions_report

    # Déterminer le type d'alerte
    if not availability['available']:
        subject = "🚨 CRITIQUE: Site WordPress inaccessible"
        incident_type = "site_down"
    elif issues['suspicious_patterns']:
        subject = "⚠️ ALERTE: Code suspect détecté sur WordPress"
        incident_type = "suspicious_code"
    elif issues['content_changed']:
        subject = "ℹ️ MODIFICATION: Contenu WordPress modifié"
        incident_type = "content_changed"
    elif issues['ssl_invalid']:
        subject = "⚠️ ALERTE: Problème de certificat SSL"
        incident_type = "ssl_issue"
    else:
        subject = "✅ RAPPORT: Surveillance WordPress - Aucun problème"
        incident_type = "all_ok"

    # Système anti-répétition d'alerte
    cache_file = os.path.join(config.MONITOR_DIR, "incident_cache.json")
    cache_data = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            try:
                cache_data = json.load(f)
            except json.JSONDecodeError:
                cache_data = {}

    last_sent = cache_data.get(incident_type)
    now_ts = int(time.time())

    if not last_sent or (now_ts - last_sent > 3600):  # Évite d'envoyer la même alerte toutes les minutes
        send_alert(subject, full_report, incident_type)
        cache_data[incident_type] = now_ts
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

    # Sauvegarde du rapport
    date_folder = datetime.now().strftime('%Y-%m-%d')
    report_dir = os.path.join(config.MONITOR_DIR, "daily", date_folder)
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    report_file = os.path.join(report_dir, f"report_{datetime.now().strftime('%H%M%S')}.txt")

    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(full_report)
        log(f"Rapport sauvegardé: {report_file}")
    except IOError as e:
        log(f"ERREUR sauvegarde rapport: {e}", "ERROR")

    log("=== FIN SURVEILLANCE ===")
    return full_report


def cleanup_old_logs():
    """Clean old logs / Nettoie anciens logs"""
    cutoff_time = datetime.now() - timedelta(days=config.LOG_RETENTION_DAYS)
    
    log_files = glob.glob(os.path.join(config.MONITOR_DIR, "report_*.txt"))
    for log_file in log_files:
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_time:
                try:
                    os.remove(log_file)
                    log(f"Fichier log nettoyé: {log_file}")
                except IOError as e:
                    log(f"ERREUR suppression: {e}", "ERROR")

# === Planification ===
def run_scheduled_monitoring():
    """Run scheduled monitoring / Exécute surveillance planifiée"""
    log("Démarrage du service planifié")
    
    cleanup_old_logs()
    
    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(main_monitoring)
    schedule.every().day.do(cleanup_old_logs)
    
    main_monitoring()  # Run immédiat
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(schedule.idle_seconds() or 60)  # Sleep intelligent
        except KeyboardInterrupt:
            log("Arrêt utilisateur")
            break
        except Exception as e:
            log(f"Erreur planification: {e}", "ERROR")
            time.sleep(300)

# === Enchaînement backup + monitoring ===
def backup_and_monitor() -> str:
    """Backup then monitor / Sauvegarde puis surveillance"""
    if backup_available:
        log("Lancement sauvegarde...")
        try:
            backup_wordpress_content()
        except Exception as e:
            log(f"Erreur backup: {e}", "WARNING")
    else:
        log("Backup non disponible, skip.")
    log("Lancement surveillance...")
    return main_monitoring()

# === Tests unitaires basiques (nouveau) ===
import unittest

class TestUtils(unittest.TestCase):
    def test_compute_hash(self):
        self.assertEqual(compute_hash("test"), hashlib.sha256("test".encode('utf-8')).hexdigest())
    
    # Ajoute plus de tests si besoin

#!/usr/bin/env python3
"""
Monitoring basique WordPress :
- Vérifie accessibilité site
- Enregistre dans monitor.log
- Option --once pour exécution unique
"""

import requests
import argparse
from datetime import datetime
from pathlib import Path

MONITOR_DIR = Path("monitor_data")
MONITOR_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = MONITOR_DIR / "monitor.log"

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def check_site(url: str):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            log(f"Site accessible ✅ : {url}")
        else:
            log(f"Site inaccessible ❌ ({r.status_code}) : {url}")
    except Exception as e:
        log(f"Site inaccessible ❌ : {url} ({e})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--url", type=str, default="https://oupssecuretest.wordpress.com")
    args = parser.parse_args()

    if args.once:
        check_site(args.url)

if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main()
    try:
        if "--scheduled" in sys.argv:
            run_scheduled_monitoring()
        elif "--once" in sys.argv:
            backup_and_monitor()
        else:
            backup_and_monitor()
    except KeyboardInterrupt:
        log("Arrêt utilisateur")
        sys.exit(0)
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}", "ERROR")
        send_alert("❌ Erreur critique", str(e), "system_error")
        sys.exit(1)