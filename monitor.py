#!/usr/bin/env python3
"""
Script principal de surveillance WordPress amélioré
- Notifications détaillées avec type, heure et contenu des modifications
- Rapports complets avec solutions proposées
- Fonctionnement autonome avec planification
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    from dateutil import parser
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

# Import backup.py
try:
    from backup import backup_wordpress_content
except ImportError:
    print("[ERREUR IMPORT] Impossible d'importer backup_wordpress_content depuis backup.py")
    sys.exit(1)

# === Configuration ===
class Config:
    """Classe de configuration centralisée"""
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
        self.SMTP_PASS = os.environ.get("SMTP_PASS", "")  # Doit être défini via variable d'environnement
        self.MONITOR_DIR = "monitor_data"
        self.INCIDENT_HISTORY_FILE = os.path.join(self.MONITOR_DIR, "incident_history.json")
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = os.name != "nt"
        
        # Créer le répertoire de surveillance s'il n'existe pas
        Path(self.MONITOR_DIR).mkdir(exist_ok=True)
        
        # Valider la configuration
        self.validate()
    
    def validate(self):
        """Valide la configuration"""
        if not self.SMTP_PASS:
            print("ATTENTION: SMTP_PASS n'est pas défini. Les alertes par email ne fonctionneront pas.")
        
        if not self.SITE_URL.startswith(('http://', 'https://')):
            print("ATTENTION: SITE_URL devrait commencer par http:// ou https://")

# Initialiser la configuration
config = Config()

# === Gestion des incidents ===
class IncidentManager:
    """Gestionnaire d'incidents"""
    def __init__(self, history_file: str):
        self.history_file = history_file
    
    def load_incident_history(self) -> List[Dict]:
        """Charge l'historique des incidents depuis le fichier"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                log(f"Erreur lors du chargement de l'historique: {e}", "ERROR")
                return []
        return []
    
    def save_incident_history(self, history: List[Dict]):
        """Sauvegarde l'historique des incidents dans le fichier"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            log(f"Erreur lors de la sauvegarde de l'historique: {e}", "ERROR")
    
    def add_incident(self, incident_type: str, details: Dict, severity: str = "medium") -> Dict:
        """Ajoute un incident à l'historique"""
        history = self.load_incident_history()
        incident = {
            "timestamp": datetime.now().isoformat(),
            "type": incident_type,
            "severity": severity,
            "details": details
        }
        history.append(incident)
        # Garder seulement les 100 derniers incidents
        if len(history) > 100:
            history = history[-100:]
        self.save_incident_history(history)
        return incident

# Initialiser le gestionnaire d'incidents
incident_manager = IncidentManager(config.INCIDENT_HISTORY_FILE)

# === Logging amélioré ===
def log(message: str, level: str = "INFO"):
    """Journalisation avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    try:
        with open(os.path.join(config.MONITOR_DIR, "monitor.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except IOError as e:
        print(f"ERREUR: Impossible d'écrire dans le fichier log: {e}")

# === Utilitaires ===
def compute_hash(content: str) -> str:
    """Calcule le hash SHA256 d'un contenu"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    """Retourne l'emoji si configuré, sinon une chaîne vide"""
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, incident_type: str = "general") -> bool:
    """Envoie une alerte par email et enregistre l'incident"""
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("ATTENTION: Configuration SMTP incomplète.", "WARNING")
        return False
    
    if not config.SMTP_PASS:
        log("ATTENTION: SMTP_PASS non défini, impossible d'envoyer des emails", "WARNING")
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
        
        # Enregistrer l'incident
        incident_manager.add_incident(incident_type, {
            "subject": subject,
            "body": body,
            "sent_via": "email"
        })
        
        log("SUCCÈS: Alerte envoyée", "INFO")
        return True
    except smtplib.SMTPException as e:
        log(f"ERREUR SMTP lors de l'envoi d'alerte : {e}", "ERROR")
        return False
    except Exception as e:
        log(f"ERREUR inattendue lors de l'envoi d'alerte : {e}", "ERROR")
        return False

def generate_solutions_report(issues: Dict) -> str:
    """Génère un rapport de solutions basé sur les problèmes détectés"""
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
    
    # Formatage du rapport de solutions
    report = "🔧 SOLUTIONS PROPOSÉES :\n\n"
    for i, solution_set in enumerate(solutions, 1):
        report += f"{i}. {solution_set['problem']} :\n"
        for j, solution in enumerate(solution_set['solutions'], 1):
            report += f"   {j}. {solution}\n"
        report += "\n"
    
    return report

# === Vérifications améliorées ===
def check_site_availability() -> Dict:
    """Vérifie la disponibilité du site"""
    log("Vérification de disponibilité...", "INFO")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        
        if results['available']:
            log(f"Site accessible {emoji('✅')}", "INFO")
        else:
            log(f"Site retourne HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
            incident_manager.add_incident("site_unavailable", {
                "status_code": resp.status_code,
                "response_time": results['response_time']
            }, "high")
            
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"ERREUR accès site : {e}", "ERROR")
        incident_manager.add_incident("site_unavailable", {
            "error": str(e)
        }, "high")
        
    return results

def check_content_integrity() -> Dict:
    """Vérifie l'intégrité du contenu"""
    log("Vérification d'intégrité...", "INFO")
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
                current_hash = compute_hash(response.text)
                ref_file = os.path.join(config.MONITOR_DIR, f"{name}.ref")
                
                if os.path.exists(ref_file):
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        old_hash = f.read().strip()
                    
                    if current_hash != old_hash:
                        results['changed'] = True
                        change_detail = {
                            'endpoint': name, 
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'old_hash': old_hash,
                            'new_hash': current_hash
                        }
                        results['changes'].append(change_detail)
                        
                        # Enregistrer l'incident de modification
                        incident_manager.add_incident("content_changed", change_detail, "medium")
                        log(f"Changement détecté : {name} {emoji('⚠️')}", "WARNING")
                        
                        # Mettre à jour la référence
                        with open(ref_file, 'w', encoding='utf-8') as f:
                            f.write(current_hash)
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    log(f"Référence créée : {name}", "INFO")
            else:
                log(f"Erreur HTTP sur {url}: {response.status_code}", "WARNING")
                
        except requests.RequestException as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}", "ERROR")
            
    return results

def check_for_malicious_patterns() -> Dict:
    """Recherche des patterns malveillants dans le contenu"""
    log("Recherche de patterns suspects...", "INFO")
    results = {'suspicious_patterns': [], 'error': None}
    patterns = [
        (r'eval\s*\(', "Fonction eval() potentiellement dangereuse"),
        (r'base64_decode\s*\(', "Décodage base64 suspect"),
        (r'exec\s*\(', "Appel système exec()"),
        (r'system\s*\(', "Appel système system()"),
        (r'shell_exec\s*\(', "Appel système shell_exec()"),
        (r'<script>[^<]*(alert|prompt|confirm)[^<]*</script>', "Script JavaScript suspect"),
        (r'<iframe[^>]*src=[^>]*>', "Iframe potentiellement malveillant")
    ]
    
    try:
        response = requests.get(config.SITE_URL, timeout=10)
        if response.status_code == 200:
            content = response.text
            
            for pat, description in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    results['suspicious_patterns'].append({
                        'pattern': pat,
                        'description': description,
                        'matches_count': len(matches),
                        'sample': matches[0] if len(matches) > 0 else None
                    })
                    
                    # Enregistrer l'incident de sécurité
                    incident_manager.add_incident("suspicious_code", {
                        'pattern': pat,
                        'description': description,
                        'matches_count': len(matches)
                    }, "high")
                    
                    log(f"Pattern suspect détecté : {description} ({len(matches)} occurences) {emoji('⚠️')}", "WARNING")
                    
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"Erreur pattern : {e}", "ERROR")
        
    return results

def check_ssl_certificate() -> Dict:
    """Vérifie si le certificat SSL est valide"""
    log("Vérification du certificat SSL...", "INFO")
    
    results = {"valid": False, "error": None, "expires_in": None}
    try:
        hostname = config.SITE_URL.replace("https://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                results["valid"] = True
                
                # Vérifier la date d'expiration
                expire_date = parser.parse(cert['notAfter'])
                days_until_expire = (expire_date - datetime.now()).days
                results["expires_in"] = days_until_expire
                
                if days_until_expire < 7:  # Moins d'une semaine
                    incident_manager.add_incident("ssl_expiring_soon", {
                        "hostname": hostname,
                        "expire_date": cert['notAfter'],
                        "days_until_expire": days_until_expire
                    }, "medium")
                    log(f"Certificat SSL expire dans {days_until_expire} jours {emoji('⚠️')}", "WARNING")
                else:
                    log(f"Certificat SSL valide pour {hostname} (expire dans {days_until_expire} jours) ✅", "INFO")
                    
    except ssl.SSLError as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR certificat SSL: {e}", "ERROR")
        incident_manager.add_incident("ssl_error", {"error": str(e)}, "high")
    except (socket.gaierror, socket.timeout, ConnectionRefusedError) as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR connexion SSL: {e}", "ERROR")
        incident_manager.add_incident("ssl_connection_error", {"error": str(e)}, "high")
    except Exception as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR inattendue lors de la vérification SSL: {e}", "ERROR")
        incident_manager.add_incident("ssl_unexpected_error", {"error": str(e)}, "high")
        
    return results

# === Génération de rapports ===
def generate_detailed_report(availability, integrity, security, ssl_check) -> str:
    """Génère un rapport détaillé de la surveillance"""
    report = f"📊 RAPPORT DE SURVEILLANCE WORDPRESS\n"
    report += f"📍 Site: {config.SITE_URL}\n"
    report += f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "="*50 + "\n\n"
    
    # Section disponibilité
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
    
    # Section intégrité
    report += "🔍 INTÉGRITÉ DU CONTENU:\n"
    if integrity['changed']:
        report += f"⚠️ {len(integrity['changes'])} modification(s) détectée(s):\n"
        for change in integrity['changes']:
            report += f"   - {change['endpoint']}: {change['url']}\n"
            report += f"     Heure: {change['timestamp']}\n"
    else:
        report += "✅ Aucune modification détectée\n"
    
    if integrity['error']:
        report += f"   Erreur: {integrity['error']}\n"
    report += "\n"
    
    # Section sécurité
    report += "🛡️ SÉCURITÉ:\n"
    if security['suspicious_patterns']:
        report += f"⚠️ {len(security['suspicious_patterns'])} pattern(s) suspect(s) détecté(s):\n"
        for pattern in security['suspicious_patterns']:
            report += f"   - {pattern['description']}\n"
            report += f"     Occurences: {pattern['matches_count']}\n"
    else:
        report += "✅ Aucun code suspect détecté\n"
    
    if security['error']:
        report += f"   Erreur: {security['error']}\n"
    report += "\n"
    
    # Section SSL
    report += "🔒 CERTIFICAT SSL:\n"
    if ssl_check['valid']:
        if ssl_check['expires_in'] and ssl_check['expires_in'] < 7:
            report += f"⚠️ Certificat valide mais expire dans {ssl_check['expires_in']} jours\n"
        else:
            report += f"✅ Certificat valide (expire dans {ssl_check['expires_in']} jours)\n"
    else:
        report += f"❌ Certificat invalide: {ssl_check['error']}\n"
    report += "\n"
    
    return report

# === Monitoring principal amélioré ===
def main_monitoring() -> str:
    """Exécute une surveillance complète et génère un rapport"""
    log(f"=== DÉMARRAGE SURVEILLANCE ===", "INFO")
    
    # Exécuter toutes les vérifications
    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    ssl_check = check_ssl_certificate()
    
    # Générer le rapport détaillé
    detailed_report = generate_detailed_report(availability, integrity, security, ssl_check)
    
    # Identifier les problèmes
    issues = {
        'available': availability['available'],
        'content_changed': integrity['changed'],
        'suspicious_patterns': len(security['suspicious_patterns']) > 0,
        'ssl_invalid': not ssl_check['valid'] or (ssl_check['expires_in'] is not None and ssl_check['expires_in'] < 7)
    }
    
    # Ajouter les solutions au rapport
    solutions_report = generate_solutions_report(issues)
    full_report = detailed_report + "\n" + solutions_report
    
    # Déterminer le sujet de l'alerte
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
    
    # Envoyer le rapport
    send_alert(subject, full_report, incident_type)
    
    # Sauvegarder le rapport dans un fichier
    report_file = os.path.join(config.MONITOR_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(full_report)
        log(f"Rapport sauvegardé: {report_file}", "INFO")
    except IOError as e:
        log(f"ERREUR sauvegarde rapport: {e}", "ERROR")
    
    log(f"=== FIN SURVEILLANCE ===", "INFO")
    
    return full_report

def cleanup_old_logs():
    """Nettoie les anciens fichiers de log selon la rétention configurée"""
    cutoff_time = datetime.now() - timedelta(days=config.LOG_RETENTION_DAYS)
    
    log_files = [
        os.path.join(config.MONITOR_DIR, "monitor.log"),
        *glob.glob(os.path.join(config.MONITOR_DIR, "report_*.txt")),
        *glob.glob(os.path.join(config.MONITOR_DIR, "reports", "comprehensive_report_*.txt"))
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_time:
                try:
                    os.remove(log_file)
                    log(f"Fichier log nettoyé: {log_file}", "INFO")
                except IOError as e:
                    log(f"ERREUR suppression fichier log: {e}", "ERROR")

# === Planification et exécution continue ===
def run_scheduled_monitoring():
    """Exécute la surveillance selon un planning défini"""
    log("Démarrage du service de surveillance planifié", "INFO")
    
    # Nettoyer les anciens logs au démarrage
    cleanup_old_logs()
    
    # Planifier une exécution selon l'intervalle configuré
    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(main_monitoring)
    
    # Planifier le nettoyage des logs tous les jours
    schedule.every().day.do(cleanup_old_logs)
    
    # Exécuter aussi immédiatement
    main_monitoring()
    
    # Boucle principale
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les minutes
        except KeyboardInterrupt:
            log("Arrêt demandé par l'utilisateur", "INFO")
            break
        except Exception as e:
            log(f"Erreur dans la boucle de planification: {e}", "ERROR")
            time.sleep(300)  # Attendre 5 minutes en cas d'erreur

# === Enchaînement backup + monitoring ===
def backup_and_monitor() -> str:
    """Exécute une sauvegarde suivie d'une surveillance"""
    log("Lancement sauvegarde...", "INFO")
    backup_wordpress_content()
    log("Lancement surveillance...", "INFO")
    return main_monitoring()

if __name__ == "__main__":
    try:
        # Vérifier les arguments de ligne de commande
        if "--scheduled" in sys.argv:
            # Mode service avec planification
            run_scheduled_monitoring()
        elif "--once" in sys.argv:
            # Exécution unique
            backup_and_monitor()
        else:
            # Mode par défaut: exécution unique
            backup_and_monitor()
            
    except KeyboardInterrupt:
        log("Arrêt demandé par l'utilisateur", "INFO")
        sys.exit(0)
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}", "ERROR")
        send_alert("❌ Erreur critique dans la surveillance", str(e), "system_error")
        sys.exit(1)

#!/usr/bin/env python3
"""
Script complet de surveillance WordPress optimisé
- Notifications détaillées avec type, heure et contenu des modifications
- Rapports complets avec solutions proposées
- Fonctionnement autonome avec planification
- Sauvegarde intégrée
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

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
    print("ERREUR: modules Python manquants :", ", ".join(MISSING))
    sys.exit(1)

# Import backup.py
try:
    from backup import backup_wordpress_content
except ImportError:
    print("[ERREUR IMPORT] Impossible d'importer backup_wordpress_content depuis backup.py")
    sys.exit(1)

# === Configuration ===
class Config:
    def __init__(self):
        self.SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
        self.ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
        self.SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
        self.SMTP_PASS = os.environ.get("SMTP_PASS", "")
        self.MONITOR_DIR = "monitor_data"
        self.INCIDENT_HISTORY_FILE = os.path.join(self.MONITOR_DIR, "incident_history.json")
        self.LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))
        self.CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "3"))
        self.USE_EMOJI = os.name != "nt"
        Path(self.MONITOR_DIR).mkdir(exist_ok=True)
        self.validate()

    def validate(self):
        if not self.SMTP_PASS:
            print("ATTENTION: SMTP_PASS n'est pas défini. Les alertes email ne fonctionneront pas.")
        if not self.SITE_URL.startswith(('http://', 'https://')):
            print("ATTENTION: SITE_URL devrait commencer par http:// ou https://")

config = Config()

# === Gestion des incidents ===
class IncidentManager:
    def __init__(self, history_file: str):
        self.history_file = history_file

    def load_incident_history(self) -> List[Dict]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def save_incident_history(self, history: List[Dict]):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except IOError as e:
            log(f"ERREUR sauvegarde historique: {e}", "ERROR")

    def add_incident(self, incident_type: str, details: Dict, severity: str = "medium") -> Dict:
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

# === Logging ===
def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    try:
        os.makedirs(config.MONITOR_DIR, exist_ok=True)
        with open(os.path.join(config.MONITOR_DIR, "monitor.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except IOError as e:
        print(f"ERREUR: Impossible d'écrire dans le log: {e}")

# === Utilitaires ===
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def emoji(symbol: str) -> str:
    return symbol if config.USE_EMOJI else ""

def send_alert(subject: str, body: str, incident_type: str = "general") -> bool:
    if not all([config.SMTP_SERVER, config.SMTP_USER, config.SMTP_PASS, config.ALERT_EMAIL]):
        log("ATTENTION: SMTP incomplet.", "WARNING")
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
        incident_manager.add_incident(incident_type, {"subject": subject, "body": body, "sent_via": "email"})
        log("SUCCÈS: Alerte envoyée", "INFO")
        return True
    except Exception as e:
        log(f"ERREUR SMTP: {e}", "ERROR")
        return False

def generate_solutions_report(issues: Dict) -> str:
    solutions = []
    if not issues.get('available', True):
        solutions.append({
            "problem": "Site inaccessible",
            "solutions": [
                "Vérifier la connexion Internet",
                "Vérifier si le serveur hébergeant WordPress est en ligne",
                "Contacter l'hébergeur"
            ]
        })
    if issues.get('content_changed', False):
        solutions.append({
            "problem": "Contenu modifié",
            "solutions": [
                "Vérifier les logs WordPress",
                "Contrôler les comptes utilisateurs ayant droits d'édition",
                "Restaurer une version précédente depuis la sauvegarde"
            ]
        })
    if issues.get('suspicious_patterns', []):
        solutions.append({
            "problem": "Code suspect détecté",
            "solutions": [
                "Analyser les fichiers avec un antivirus",
                "Scanner avec un outil de sécurité WordPress",
                "Changer tous les mots de passe administrateur",
                "Mettre à jour WordPress et plugins"
            ]
        })
    if issues.get('ssl_invalid', False):
        solutions.append({
            "problem": "Certificat SSL invalide",
            "solutions": [
                "Renouveler le certificat SSL",
                "Vérifier la date d'expiration du certificat",
                "Contacter l'hébergeur"
            ]
        })
    if not solutions:
        return "✅ Aucun problème détecté, tout fonctionne normalement."

    report = "🔧 SOLUTIONS PROPOSÉES :\n\n"
    for i, sol in enumerate(solutions, 1):
        report += f"{i}. {sol['problem']} :\n"
        for j, s in enumerate(sol['solutions'], 1):
            report += f"   {j}. {s}\n"
        report += "\n"
    return report

# === Vérifications ===
def check_site_availability() -> Dict:
    log("Vérification de disponibilité...", "INFO")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(config.SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        if results['available']:
            log(f"Site accessible {emoji('✅')}", "INFO")
        else:
            log(f"Site retourne HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
            incident_manager.add_incident("site_unavailable", {"status_code": resp.status_code}, "high")
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"ERREUR accès site: {e}", "ERROR")
        incident_manager.add_incident("site_unavailable", {"error": str(e)}, "high")
    return results

def check_content_integrity() -> Dict:
    log("Vérification d'intégrité...", "INFO")
    results = {'changed': False, 'changes': [], 'error': ""}
    endpoints = [
        (config.SITE_URL, "homepage"),
        (config.SITE_URL + "/feed/", "rss"),
        (config.SITE_URL + "/comments/feed/", "comments")
    ]
    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                current_hash = compute_hash(response.text)
                ref_file = os.path.join(config.MONITOR_DIR, f"{name}.ref")
                if os.path.exists(ref_file):
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        old_hash = f.read().strip()
                    if current_hash != old_hash:
                        results['changed'] = True
                        change_detail = {
                            'endpoint': name,
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'old_hash': old_hash,
                            'new_hash': current_hash
                        }
                        results['changes'].append(change_detail)
                        incident_manager.add_incident("content_changed", change_detail, "medium")
                        log(f"Changement détecté : {name} {emoji('⚠️')}", "WARNING")
                        with open(ref_file, 'w', encoding='utf-8') as f:
                            f.write(current_hash)
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    log(f"Référence créée : {name}", "INFO")
            else:
                log(f"Erreur HTTP sur {url}: {response.status_code}", "WARNING")
        except requests.RequestException as e:
            results['error'] += f"; {str(e)}"
            log(f"Erreur intégrité {name}: {e}", "ERROR")
    return results

def check_for_malicious_patterns() -> Dict:
    log("Recherche de patterns suspects...", "INFO")
    results = {'suspicious_patterns': [], 'error': ""}
    patterns = [
        (r'eval\s*\(', "Fonction eval() potentiellement dangereuse"),
        (r'base64_decode\s*\(', "Décodage base64 suspect"),
        (r'exec\s*\(', "Appel système exec()"),
        (r'system\s*\(', "Appel système system()"),
        (r'shell_exec\s*\(', "Appel système shell_exec()"),
        (r'<script>[^<]*(alert|prompt|confirm)[^<]*</script>', "Script JavaScript suspect"),
        (r'<iframe[^>]*src=[^>]*>', "Iframe potentiellement malveillant")
    ]
    try:
        response = requests.get(config.SITE_URL, timeout=10)
        if response.status_code == 200:
            content = response.text
            for pat, desc in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                if matches:
                    results['suspicious_patterns'].append({'pattern': pat, 'description': desc, 'matches_count': len(matches)})
                    incident_manager.add_incident("suspicious_code", {'pattern': pat, 'description': desc, 'matches_count': len(matches)}, "high")
                    log(f"Pattern suspect détecté: {desc} ({len(matches)} occurences) {emoji('⚠️')}", "WARNING")
    except requests.RequestException as e:
        results['error'] += f"; {str(e)}"
        log(f"Erreur pattern: {e}", "ERROR")
    return results

def check_ssl_certificate() -> Dict:
    log("Vérification du certificat SSL...", "INFO")
    results = {"valid": False, "error": None, "expires_in": None}
    try:
        hostname = config.SITE_URL.replace("https://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                results["valid"] = True
                expire_date = parser.parse(cert.get('notAfter', ''))
                expire_date_naive = expire_date.astimezone(tz.UTC).replace(tzinfo=None)
                results["expires_in"] = (expire_date_naive - datetime.utcnow()).days
                if results["expires_in"] < 7:
                    incident_manager.add_incident("ssl_expiring_soon", {"hostname": hostname, "expire_date": cert['notAfter'], "days_until_expire": results["expires_in"]}, "medium")
                    log(f"Certificat SSL expire dans {results['expires_in']} jours {emoji('⚠️')}", "WARNING")
                else:
                    log(f"Certificat SSL valide pour {hostname} (expire dans {results['expires_in']} jours) ✅", "INFO")
    except Exception as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR certificat SSL: {e}", "ERROR")
        incident_manager.add_incident("ssl_error", {"error": str(e)}, "high")
    return results

# === Génération du rapport détaillé ===
def generate_detailed_report(availability, integrity, security, ssl_check) -> str:
    report = f"📊 RAPPORT DE SURVEILLANCE WORDPRESS\n"
    report += f"📍 Site: {config.SITE_URL}\n"
    report += f"⏰ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "="*50 + "\n\n"

    report += "🌐 DISPONIBILITÉ DU SITE:\n"
    if availability['available']:
        report += f"✅ Site accessible (HTTP {availability['status_code']}, {availability['response_time']:.2f}s)\n"
    else:
        report += f"❌ Site inaccessible\n"
        if availability['error']:
            report += f"   Erreur: {availability['error']}\n"
    report += "\n"

    report += "🔍 INTÉGRITÉ DU CONTENU:\n"
    if integrity['changed']:
        report += f"⚠️ {len(integrity['changes'])} modification(s) détectée(s):\n"
        for change in integrity['changes']:
            report += f"   - {change['endpoint']}: {change['url']}\n"
            report += f"     Heure: {change['timestamp']}\n"
    else:
        report += "✅ Aucune modification détectée\n"
    if integrity['error']:
        report += f"   Erreur: {integrity['error']}\n"
    report += "\n"

    report += "🛡️ SÉCURITÉ:\n"
    if security['suspicious_patterns']:
        report += f"⚠️ {len(security['suspicious_patterns'])} pattern(s) suspect(s) détecté(s):\n"
        for pattern in security['suspicious_patterns']:
            report += f"   - {pattern['description']} ({pattern['matches_count']} occurences)\n"
    else:
        report += "✅ Aucun code suspect détecté\n"
    if security['error']:
        report += f"   Erreur: {security['error']}\n"
    report += "\n"

    report += "🔒 CERTIFICAT SSL:\n"
    if ssl_check['valid']:
        if ssl_check['expires_in'] < 7:
            report += f"⚠️ Certificat valide mais expire dans {ssl_check['expires_in']} jours\n"
        else:
            report += f"✅ Certificat valide (expire dans {ssl_check['expires_in']} jours)\n"
    else:
        report += f"❌ Certificat invalide: {ssl_check['error']}\n"
    report += "\n"

    return report

# === Monitoring principal ===
def main_monitoring() -> str:
    log("=== DÉMARRAGE SURVEILLANCE ===", "INFO")
    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    ssl_check = check_ssl_certificate()

    detailed_report = generate_detailed_report(availability, integrity, security, ssl_check)

    issues = {
        'available': availability['available'],
        'content_changed': integrity['changed'],
        'suspicious_patterns': len(security['suspicious_patterns']) > 0,
        'ssl_invalid': not ssl_check['valid'] or (ssl_check['expires_in'] is not None and ssl_check['expires_in'] < 7)
    }

    solutions_report = generate_solutions_report(issues)
    full_report = detailed_report + "\n" + solutions_report

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

    send_alert(subject, full_report, incident_type)

    report_file = os.path.join(config.MONITOR_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(full_report)
        log(f"Rapport sauvegardé: {report_file}", "INFO")
    except IOError as e:
        log(f"ERREUR sauvegarde rapport: {e}", "ERROR")

    log("=== FIN SURVEILLANCE ===", "INFO")
    return full_report

# === Nettoyage ancien logs ===
def cleanup_old_logs():
    cutoff_time = datetime.now() - timedelta(days=config.LOG_RETENTION_DAYS)
    log_files = [os.path.join(config.MONITOR_DIR, "monitor.log"), *glob.glob(os.path.join(config.MONITOR_DIR, "report_*.txt"))]
    for log_file in log_files:
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_time:
                try:
                    os.remove(log_file)
                    log(f"Fichier log nettoyé: {log_file}", "INFO")
                except IOError as e:
                    log(f"ERREUR suppression fichier log: {e}", "ERROR")

# === Planification ===
def run_scheduled_monitoring():
    log("Démarrage service planifié", "INFO")
    cleanup_old_logs()
    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(main_monitoring)
    schedule.every().day.do(cleanup_old_logs)
    main_monitoring()
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            log("Arrêt demandé par l'utilisateur", "INFO")
            break
        except Exception as e:
            log(f"Erreur boucle planification: {e}", "ERROR")
            time.sleep(60)

# === Sauvegarde + Monitoring ===
def backup_and_monitor() -> str:
    log("Lancement sauvegarde...", "INFO")
    backup_wordpress_content()
    log("Lancement surveillance...", "INFO")
    return main_monitoring()

# === Entrée principale ===
if __name__ == "__main__":
    try:
        if "--scheduled" in sys.argv:
            run_scheduled_monitoring()
        else:
            backup_and_monitor()
    except KeyboardInterrupt:
        log("Arrêt demandé par l'utilisateur", "INFO")
        sys.exit(0)
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}", "ERROR")
        send_alert("❌ Erreur critique dans la surveillance", str(e), "system_error")
        sys.exit(1)
