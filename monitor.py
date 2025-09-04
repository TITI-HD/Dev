#!/usr/bin/env python3
"""
Script principal de surveillance WordPress
- Vérification disponibilité, intégrité et sécurité
- Appelle la sauvegarde depuis backup.py
- Compatible Windows et Linux
"""

import os
import sys

# --- Vérification des dépendances tierces avant d'importer ---
MISSING = []
try:
    import requests
except ImportError:
    MISSING.append("requests")

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

# --- Imports confirmés après vérif ---
import smtplib
import hashlib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Dict

# Import backup.py
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
SMTP_PASS = os.environ.get("SMTP_PASS", "yizn odfb xlhz mygy")  # ⚠️ Mets ceci dans une variable d'env en production
MONITOR_DIR = "monitor_data"
Path(MONITOR_DIR).mkdir(exist_ok=True)

# Emoji facultatif selon l’OS
USE_EMOJI = os.name != "nt"

def emoji(symbol: str) -> str:
    return symbol if USE_EMOJI else ""

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
        log("SUCCÈS: Alerte envoyée")
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
        log(f"Site accessible {emoji('✅')}" if results['available'] else f"Site retourne HTTP {resp.status_code} {emoji('⚠️')}")
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
                        log(f"Changement détecté : {name} {emoji('⚠️')}")
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    log(f"Référence créée : {name}")
            else:
                log(f"Erreur HTTP sur {url}: {response.status_code}")
        except Exception as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}")
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
                    log(f"Pattern suspect détecté : {pat} {emoji('⚠️')}")
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur pattern : {e}")
    return results

# === Monitoring principal ===
def main_monitoring():
    log(f"=== DÉMARRAGE SURVEILLANCE ===")
    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    alert_message = f"Surveillance WordPress : {SITE_URL}\n\n"
    issues = False

    if not availability['available']:
        issues = True
        alert_message += f"Site INACCESSIBLE {emoji('❌')}\n"
        if availability['error']:
            alert_message += f"Erreur: {availability['error']}\n\n"

    if integrity['changed']:
        issues = True
        alert_message += "Modifications détectées :\n"
        for c in integrity['changes']:
            alert_message += f"- {c['endpoint']} : {c['url']}\n"
        alert_message += "\n"

    if security['suspicious_patterns']:
        issues = True
        alert_message += "Patterns suspects :\n"
        for p in security['suspicious_patterns']:
            alert_message += f"- {p}\n"
        alert_message += "\n"

    if issues:
        send_alert("🚨 Alerte Surveillance WordPress", alert_message)
    else:
        log(f"Aucun problème détecté {emoji('✅')}")
        send_alert("✅ Rapport Surveillance WordPress", "Aucune anomalie détectée.")
    log(f"=== FIN SURVEILLANCE ===")

# === Enchaînement backup + monitoring ===
def backup_and_monitor():
    log("Lancement sauvegarde...")
    backup_wordpress_content()
    log("Lancement surveillance...")
    main_monitoring()

def check_ssl_certificate():
    """Vérifie si le certificat SSL est valide"""
    import ssl, socket
    results = {"valid": False, "error": None}
    try:
        hostname = SITE_URL.replace("https://", "").split("/")[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443)) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                ssock.getpeercert()
                results["valid"] = True
                log(f"Certificat SSL valide pour {hostname} ✅")
    except Exception as e:
        results["error"] = str(e)
        log(f"ERREUR certificat SSL: {e}")
    return results

if __name__ == "__main__":
    try:
        backup_and_monitor()
    except Excepti#!/usr/bin/env python3
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
import schedule
from datetime import datetime, timedelta

# --- Vérification des dépendances tierces avant d'importer ---
MISSING = []
try:
    import requests
except ImportError:
    MISSING.append("requests")

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

# --- Imports confirmés après vérif ---
import smtplib
import hashlib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List

# Import backup.py
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
SMTP_PASS = os.environ.get("SMTP_PASS", "yizn odfb xlhz mygy")  # ⚠️ Mets ceci dans une variable d'env en production
MONITOR_DIR = "monitor_data"
Path(MONITOR_DIR).mkdir(exist_ok=True)

# Historique des incidents
INCIDENT_HISTORY_FILE = os.path.join(MONITOR_DIR, "incident_history.json")

# Emoji facultatif selon l'OS
USE_EMOJI = os.name != "nt"

def emoji(symbol: str) -> str:
    return symbol if USE_EMOJI else ""

# === Gestion des incidents ===
def load_incident_history() -> List[Dict]:
    """Charge l'historique des incidents depuis le fichier"""
    if os.path.exists(INCIDENT_HISTORY_FILE):
        try:
            with open(INCIDENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_incident_history(history: List[Dict]):
    """Sauvegarde l'historique des incidents dans le fichier"""
    with open(INCIDENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def add_incident(incident_type: str, details: Dict, severity: str = "medium"):
    """Ajoute un incident à l'historique"""
    history = load_incident_history()
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
    save_incident_history(history)
    return incident

# === Logging amélioré ===
def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    with open(os.path.join(MONITOR_DIR, "monitor.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

# === Utilitaires ===
def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def send_alert(subject: str, body: str, incident_type: str = "general") -> bool:
    """Envoie une alerte par email et enregistre l'incident"""
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_EMAIL]):
        log("ATTENTION: Configuration SMTP incomplète.", "WARNING")
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
        
        # Enregistrer l'incident
        add_incident(incident_type, {
            "subject": subject,
            "body": body,
            "sent_via": "email"
        })
        
        log("SUCCÈS: Alerte envoyée", "INFO")
        return True
    except Exception as e:
        log(f"ERREUR envoi alerte : {e}", "ERROR")
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
    log("Vérification de disponibilité...", "INFO")
    results = {'available': False, 'status_code': None, 'response_time': None, 'error': None}
    try:
        start = datetime.now()
        resp = requests.get(SITE_URL, timeout=15)
        results['status_code'] = resp.status_code
        results['response_time'] = (datetime.now() - start).total_seconds()
        results['available'] = resp.status_code == 200
        
        if results['available']:
            log(f"Site accessible {emoji('✅')}", "INFO")
        else:
            log(f"Site retourne HTTP {resp.status_code} {emoji('⚠️')}", "WARNING")
            add_incident("site_unavailable", {
                "status_code": resp.status_code,
                "response_time": results['response_time']
            }, "high")
            
    except Exception as e:
        results['error'] = str(e)
        log(f"ERREUR accès site : {e}", "ERROR")
        add_incident("site_unavailable", {
            "error": str(e)
        }, "high")
        
    return results

def check_content_integrity() -> Dict:
    log("Vérification d'intégrité...", "INFO")
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
                        change_detail = {
                            'endpoint': name, 
                            'url': url,
                            'timestamp': datetime.now().isoformat(),
                            'old_hash': old_hash,
                            'new_hash': current_hash
                        }
                        results['changes'].append(change_detail)
                        
                        # Enregistrer l'incident de modification
                        add_incident("content_changed", change_detail, "medium")
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
                
        except Exception as e:
            results['error'] = str(e)
            log(f"Erreur intégrité {name}: {e}", "ERROR")
            
    return results

def check_for_malicious_patterns() -> Dict:
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
        response = requests.get(SITE_URL, timeout=10)
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
                    add_incident("suspicious_code", {
                        'pattern': pat,
                        'description': description,
                        'matches_count': len(matches)
                    }, "high")
                    
                    log(f"Pattern suspect détecté : {description} ({len(matches)} occurences) {emoji('⚠️')}", "WARNING")
                    
    except Exception as e:
        results['error'] = str(e)
        log(f"Erreur pattern : {e}", "ERROR")
        
    return results

def check_ssl_certificate():
    """Vérifie si le certificat SSL est valide"""
    import ssl, socket
    from dateutil import parser
    
    results = {"valid": False, "error": None, "expires_in": None}
    try:
        hostname = SITE_URL.replace("https://", "").split("/")[0]
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
                    add_incident("ssl_expiring_soon", {
                        "hostname": hostname,
                        "expire_date": cert['notAfter'],
                        "days_until_expire": days_until_expire
                    }, "medium")
                    log(f"Certificat SSL expire dans {days_until_expire} jours {emoji('⚠️')}", "WARNING")
                else:
                    log(f"Certificat SSL valide pour {hostname} (expire dans {days_until_expire} jours) ✅", "INFO")
                    
    except Exception as e:
        results["error"] = str(e)
        results["valid"] = False
        log(f"ERREUR certificat SSL: {e}", "ERROR")
        add_incident("ssl_error", {"error": str(e)}, "high")
        
    return results

# === Génération de rapports ===
def generate_detailed_report(availability, integrity, security, ssl_check) -> str:
    """Génère un rapport détaillé de la surveillance"""
    report = f"📊 RAPPORT DE SURVEILLANCE WORDPRESS\n"
    report += f"📍 Site: {SITE_URL}\n"
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
        if ssl_check['expires_in'] < 7:
            report += f"⚠️ Certificat valide mais expire dans {ssl_check['expires_in']} jours\n"
        else:
            report += f"✅ Certificat valide (expire dans {ssl_check['expires_in']} jours)\n"
    else:
        report += f"❌ Certificat invalide: {ssl_check['error']}\n"
    report += "\n"
    
    return report

# === Monitoring principal amélioré ===
def main_monitoring():
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
    report_file = os.path.join(MONITOR_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(full_report)
    
    log(f"Rapport sauvegardé: {report_file}", "INFO")
    log(f"=== FIN SURVEILLANCE ===", "INFO")
    
    return full_report

# === Planification et exécution continue ===
def run_scheduled_monitoring():
    """Exécute la surveillance selon un planning défini"""
    log("Démarrage du service de surveillance planifié", "INFO")
    
    # Planifier une exécution toutes les 3 heures
    schedule.every(3).hours.do(main_monitoring)
    
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
def backup_and_monitor():
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
            
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}", "ERROR")
        send_alert("❌ Erreur critique dans la surveillance", str(e), "system_error")
        sys.exit(1)on as e:
        log(f"ERREUR CRITIQUE: {e}")
        send_alert("❌ Erreur critique dans la surveillance", str(e))
        sys.exit(1)
def cleanup_old_logs():
    """Nettoie les anciens fichiers de log selon la rétention configurée"""
    retention_days = int(os.environ.get("LOG_RETENTION_DAYS", 30))
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    
    log_files = [
        os.path.join(MONITOR_DIR, "monitor.log"),
        *glob.glob(os.path.join(MONITOR_DIR, "report_*.txt")),
        *glob.glob(os.path.join(MONITOR_DIR, "reports", "comprehensive_report_*.txt"))
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_time:
                os.remove(log_file)
                log(f"Fichier log nettoyé: {log_file}", "INFO")