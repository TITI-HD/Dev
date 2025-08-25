#!/usr/bin/env python3
"""
SCRIPT PRINCIPAL DE SURVEILLANCE WORDPRESS
Surveillance complète avec alertes email/WhatsApp et sauvegarde de contenu
"""

import os
import smtplib
import requests
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from twilio.rest import Client  # API Twilio pour WhatsApp

# ===============================
# 🔧 CONFIGURATION - VARIABLES D'ENVIRONNEMENT
# ===============================
# Récupération des paramètres depuis les variables d'environnement
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "danieltiti882@gmail.com")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")
SMTP_USER = os.environ.get("SMTP_USER", "danieltiti882@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
ALERT_PHONE_NUMBER = os.environ.get("ALERT_PHONE_NUMBER", "")
BACKUP_DIR = "backups"  # Dossier de sauvegarde local

# Validation et conversion du port SMTP
try:
    SMTP_PORT = int(SMTP_PORT) if SMTP_PORT and SMTP_PORT.strip() else 587
except ValueError:
    print("⚠️ SMTP_PORT invalide, utilisation du port par défaut 587")
    SMTP_PORT = 587

# ===============================
# 📱 FONCTION D'ENVOI WHATSAPP
# ===============================
def send_whatsapp_notification(message: str):
    """
    Envoie une notification via WhatsApp Twilio
    Args:
        message (str): Message à envoyer
    Returns:
        bool: Succès de l'envoi
    """
    # Vérification de la configuration Twilio
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, ALERT_PHONE_NUMBER]):
        print("⚠️ Configuration Twilio manquante, notification WhatsApp ignorée.")
        return False
    
    try:
        # Initialisation client Twilio
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # Envoi du message WhatsApp
        message = client.messages.create(
            from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
            body=message,
            to=f'whatsapp:{ALERT_PHONE_NUMBER}'
        )
        print(f"✅ Notification WhatsApp envoyée: {message.sid}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi WhatsApp: {e}")
        return False

# ===============================
# 📧 FONCTION D'ENVOI D'ALERTE EMAIL
# ===============================
def send_alert(subject: str, message: str, whatsapp_priority: bool = False):
    """
    Envoie une alerte par email et optionnellement par WhatsApp
    Args:
        subject (str): Sujet de l'alerte
        message (str): Contenu du message
        whatsapp_priority (bool): Si True, envoie aussi sur WhatsApp
    """
    # Envoi Email
    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        print("⚠️ SMTP non configuré, alerte email ignorée.")
    else:
        try:
            # Construction du message email
            msg = MIMEMultipart()
            msg["From"] = SMTP_USER
            msg["To"] = ALERT_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            # Connexion et envoi SMTP
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())

            print(f"✅ Alerte email envoyée à {ALERT_EMAIL}")
        except Exception as e:
            print(f"❌ Erreur envoi mail: {e}")
    
    # Envoi WhatsApp pour les alertes prioritaires
    if whatsapp_priority:
        whatsapp_message = f"🚨 {subject}\n\n{message[:500]}..."  # Limiter la longueur
        send_whatsapp_notification(whatsapp_message)

# ===============================
# 🔍 VERIFICATION DISPONIBILITE SITE
# ===============================
def check_site(url: str) -> bool:
    """
    Vérifie si le site WordPress est accessible
    Args:
        url (str): URL du site à vérifier
    Returns:
        bool: True si le site est accessible
    """
    try:
        # Requête HTTP avec timeout
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            # Alerte si code HTTP anormal
            send_alert("🚨 Site WordPress Hors Ligne", 
                      f"Le site {url} répond avec code HTTP {r.status_code}", 
                      whatsapp_priority=True)
            return False
        return True
    except Exception as e:
        # Alerte en cas d'erreur de connexion
        send_alert("🚨 Site WordPress Inaccessible", 
                  f"Erreur de connexion au site {url}: {e}", 
                  whatsapp_priority=True)
        return False

def check_api(url: str) -> bool:
    """
    Vérifie si l'API REST WordPress est accessible
    Args:
        url (str): URL de l'API
    Returns:
        bool: True si l'API est accessible
    """
    try:
        r = requests.get(url.rstrip("/") + "/wp-json/", timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Erreur API: {e}")
        return False

# ===============================
# 💾 SAUVEGARDE ET COMPARAISON CONTENU
# ===============================
def save_content(url, filename):
    """
    Sauvegarde le contenu d'une URL dans un fichier
    Args:
        url (str): URL à sauvegarder
        filename (str): Chemin du fichier de sauvegarde
    Returns:
        str: Contenu sauvegardé ou None en cas d'erreur
    """
    try:
        # Téléchargement du contenu
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        # Écriture dans le fichier
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text
    except Exception as e:
        # Alerte en cas d'erreur
        send_alert("🚨 Site indisponible", f"Erreur accès {url}: {e}", whatsapp_priority=True)
        return None

def compare_files(old_file, new_file):
    """
    Compare deux fichiers et retourne les différences
    Args:
        old_file (str): Chemin du fichier ancien
        new_file (str): Chemin du fichier nouveau
    Returns:
        str: Différences entre les fichiers
    """
    if not os.path.exists(old_file):
        return ""
    # Lecture et comparaison des fichiers
    with open(old_file, encoding="utf-8") as f1, open(new_file, encoding="utf-8") as f2:
        old = f1.readlines()
        new = f2.readlines()
    # Génération des différences
    diff = list(difflib.unified_diff(old, new))
    return "".join(diff)

def backup_and_monitor():
    """
    Effectue une sauvegarde et surveille les changements
    """
    # Création du dossier de sauvegarde
    os.makedirs(BACKUP_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Définition des chemins de sauvegarde
    homepage_file = os.path.join(BACKUP_DIR, f"homepage_{date_str}.html")
    rss_file = os.path.join(BACKUP_DIR, f"rss_{date_str}.xml")
    comments_file = os.path.join(BACKUP_DIR, f"comments_{date_str}.xml")

    # Sauvegardes des différents contenus
    homepage = save_content(SITE_URL, homepage_file)
    rss = save_content(f"{SITE_URL}/feed", rss_file)
    comments = save_content(f"{SITE_URL}/comments/feed", comments_file)

    # Détection changements page d'accueil
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("homepage_")])
    if len(files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, files[-2]), homepage_file)
        if diff:
            send_alert("📝 Changement Page d'Accueil", 
                      f"Modifications détectées sur {SITE_URL}:\n\n{diff[:1500]}...")

    # Détection nouveaux articles
    rss_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("rss_")])
    if len(rss_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, rss_files[-2]), rss_file)
        if diff:
            send_alert("🆕 Nouvel Article WordPress", 
                      f"Nouveau contenu détecté dans le RSS:\n\n{diff[:1000]}...",
                      whatsapp_priority=True)

    # Détection nouveaux commentaires
    comments_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("comments_")])
    if len(comments_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, comments_files[-2]), comments_file)
        if diff:
            send_alert("💬 Nouveau Commentaire", 
                      f"Nouveau commentaire détecté:\n\n{diff[:800]}...")

# ===============================
# 🚀 FONCTION PRINCIPALE
# ===============================
def main():
    """
    Fonction principale de surveillance
    """
    print(f"🔍 Démarrage surveillance: {SITE_URL}")
    print(f"📧 Email alerte: {ALERT_EMAIL}")
    print(f"📱 WhatsApp configuré: {'OUI' if TWILIO_ACCOUNT_SID else 'NON'}")
    
    # Vérifications principales
    site_ok = check_site(SITE_URL)
    api_ok = check_api(SITE_URL)

    if site_ok and api_ok:
        status_message = f"✅ {SITE_URL} en ligne & API REST OK"
        print(status_message)
    else:
        error_message = f"{SITE_URL} ou API REST inaccessible"
        print(f"❌ {error_message}")

    # Sauvegarde + surveillance contenu
    backup_and_monitor()
    
    print("✅ Surveillance terminée avec succès")

if __name__ == "__main__":
    main()