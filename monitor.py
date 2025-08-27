#!/usr/bin/env python3
"""
SCRIPT DE SURVEILLANCE WORDPRESS AVANCÉ
Surveillance proactive avec vérification d'intégrité et alertes
Version corrigée pour Windows
"""

import os
import smtplib
import requests
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# ===================== CONFIGURATION =====================
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "gmail")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "yizn odfb xlhz mygy")

# Dossiers de travail
MONITOR_DIR = "monitor_data"
Path(MONITOR_DIR).mkdir(exist_ok=True)

# ===================== FONCTIONS UTILITAIRES =====================
def log(message: str):
    """Journalisation avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    
    # Sauvegarde dans le fichier de log
    with open(os.path.join(MONITOR_DIR, "monitor.log"), "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def compute_hash(content: str) -> str:
    """Calcule le hash SHA-256 du contenu"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def send_alert(subject: str, body: str, is_critical: bool = False):
    """
    Envoie une alerte par email
    
    Args:
        subject: Sujet de l'email
        body: Corps du message
        is_critical: Si True, indique une alerte critique
    """
    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_EMAIL]):
        log("ATTENTION: Configuration SMTP incomplète - impossible d'envoyer une alerte")
        return False

    try:
        # Préparation du message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = subject
        
        # Corps du message
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Connexion et envoi
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        log("SUCCES: Alerte envoyée avec succès")
        return True
        
    except Exception as e:
        log(f"ERREUR: Impossible d'envoyer l'alerte: {e}")
        return False

# ===================== VÉRIFICATIONS =====================
def check_site_availability() -> dict:
    """
    Vérifie la disponibilité du site
    
    Returns:
        Dict avec les résultats de la vérification
    """
    log("VERIFICATION: Vérification de la disponibilité du site...")
    
    results = {
        'available': False,
        'status_code': None,
        'response_time': None,
        'error': None
    }
    
    try:
        start_time = datetime.now()
        response = requests.get(SITE_URL, timeout=15, 
                              headers={'User-Agent': 'WordPress Monitor/1.0'})
        end_time = datetime.now()
        
        results['status_code'] = response.status_code
        results['response_time'] = (end_time - start_time).total_seconds()
        results['available'] = response.status_code == 200
        
        if response.status_code == 200:
            log("SUCCES: Site accessible et répond correctement")
        else:
            log(f"ATTENTION: Site accessible mais retourne le code: {response.status_code}")
            
    except requests.RequestException as e:
        results['error'] = str(e)
        log(f"ERREUR: Site inaccessible: {e}")
    
    return results

def check_content_integrity() -> dict:
    """
    Vérifie l'intégrité du contenu en comparant avec la dernière sauvegarde
    
    Returns:
        Dict avec les résultats de la vérification
    """
    log("VERIFICATION: Vérification de l'intégrité du contenu...")
    
    results = {
        'changed': False,
        'changes': [],
        'error': None
    }
    
    # URLs à surveiller
    endpoints = [
        (SITE_URL, "homepage"),
        (SITE_URL + "/feed/", "rss"),
        (SITE_URL + "/comments/feed/", "comments")
    ]
    
    for url, endpoint_name in endpoints:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                current_content = response.text
                current_hash = compute_hash(current_content)
                
                # Fichier de référence pour cet endpoint
                ref_file = os.path.join(MONITOR_DIR, f"{endpoint_name}.ref")
                
                if os.path.exists(ref_file):
                    # Lecture du hash de référence
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        ref_hash = f.read().strip()
                    
                    # Comparaison
                    if current_hash != ref_hash:
                        results['changed'] = True
                        results['changes'].append({
                            'endpoint': endpoint_name,
                            'url': url,
                            'change_type': 'content_modified'
                        })
                        log(f"MODIFICATION: Changement détecté: {endpoint_name}")
                else:
                    # Premier passage, création de la référence
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        f.write(current_hash)
                    log(f"INFO: Référence créée: {endpoint_name}")
                    
            else:
                log(f"ATTENTION: Impossible de vérifier {endpoint_name}: HTTP {response.status_code}")
                
        except Exception as e:
            log(f"ERREUR: Impossible de vérifier {endpoint_name}: {e}")
            results['error'] = str(e)
    
    return results

def check_for_malicious_patterns() -> dict:
    """
    Recherche des patterns suspects dans le code source
    
    Returns:
        Dict avec les résultats de la vérification
    """
    log("VERIFICATION: Recherche de patterns suspects...")
    
    results = {
        'suspicious_patterns': [],
        'error': None
    }
    
    # Patterns à rechercher (simplifié pour WordPress.com)
    suspicious_patterns = [
        r'eval\s*\(',
        r'base64_decode\s*\(',
        r'exec\s*\(',
        r'system\s*\(',
        r'passthru\s*\(',
        r'shell_exec\s*\('
    ]
    
    import re
    
    try:
        response = requests.get(SITE_URL, timeout=10)
        if response.status_code == 200:
            content = response.text
            
            for pattern in suspicious_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    results['suspicious_patterns'].append({
                        'pattern': pattern,
                        'found': True
                    })
                    log(f"ATTENTION: Pattern suspect détecté: {pattern}")
        
        if not results['suspicious_patterns']:
            log("SUCCES: Aucun pattern suspect détecté")
            
    except Exception as e:
        results['error'] = str(e)
        log(f"ERREUR: Impossible de rechercher des patterns: {e}")
    
    return results

# ===================== FONCTION PRINCIPALE =====================
def main_monitoring():
    """
    Fonction principale de surveillance
    """
    log("DEBUT: Démarrage de la surveillance WordPress")
    log(f"INFO: Site surveillé: {SITE_URL}")
    
    # Réalisation des vérifications
    availability = check_site_availability()
    integrity = check_content_integrity()
    security = check_for_malicious_patterns()
    
    # Analyse des résultats
    issues_detected = False
    alert_message = "Rapport de surveillance WordPress:\n\n"
    
    # Vérification de disponibilité
    if not availability['available']:
        issues_detected = True
        alert_message += "PROBLEME DE DISPONIBILITE\n"
        alert_message += f"Le site {SITE_URL} est inaccessible.\n"
        if availability['error']:
            alert_message += f"Erreur: {availability['error']}\n"
        alert_message += "\n"
    
    # Vérification d'intégrité
    if integrity['changed']:
        issues_detected = True
        alert_message += "MODIFICATIONS DETECTEES\n"
        for change in integrity['changes']:
            alert_message += f"- {change['endpoint']}: {change['url']}\n"
        alert_message += "\n"
    
    # Vérification de sécurité
    if security['suspicious_patterns']:
        issues_detected = True
        alert_message += "PATTERNS SUSPECTS DETECTES\n"
        for pattern in security['suspicious_patterns']:
            alert_message += f"- Pattern: {pattern['pattern']}\n"
        alert_message += "\n"
    
    # Envoi des alertes si nécessaire
    if issues_detected:
        alert_subject = "ALERTE Surveillance WordPress - Problemes detectes"
        send_alert(alert_subject, alert_message, is_critical=True)
        log("ALERTE: Problemes détectés - Alertes envoyées")
    else:
        # Rapport d'inaction
        inactivity_message = "Rapport de surveillance WordPress\n\n"
        inactivity_message += "Aucune activité suspecte détectée sur le site.\n"
        inactivity_message += f"Site: {SITE_URL}\n"
        inactivity_message += f"Dernière vérification: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        send_alert("Rapport Surveillance WordPress - Aucune activité", inactivity_message)
        log("SUCCES: Aucun problème détecté - Rapport d'inaction envoyé")
    
    log("FIN: Surveillance terminée")

if __name__ == "__main__":
    try:
        main_monitoring()
    except Exception as e:
        log(f"ERREUR CRITIQUE: Erreur lors de la surveillance: {e}")
        # Tentative d'envoi d'alerte même en cas d'erreur
        try:
            send_alert("ERREUR Surveillance WordPress", 
                      f"Le script de surveillance a rencontré une erreur critique:\n\n{str(e)}", 
                      is_critical=True)
        except:
            pass
        exit(1)