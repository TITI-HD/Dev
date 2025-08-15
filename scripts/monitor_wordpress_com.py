import requests
import os
import difflib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

SITE_URL = os.environ.get("oupssecuretest.wordpress.com")
BACKUP_DIR = "backups"
ALERT_EMAIL = os.environ.get("ALERT_EMAIL")
SMTP_SERVER = os.environ.get("danieltiti882@gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("danieltiti882@gmail.com")
SMTP_PASS = os.environ.get("Smvqp hyhf iagh rveg")

def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = ALERT_EMAIL
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())

def save_content(url, filename):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text
    except Exception as e:
        send_alert("ALERTE: Site indisponible", f"Erreur lors de l'accès à {url} : {e}")
        return None

def compare_files(old_file, new_file):
    if not os.path.exists(old_file):
        return ""
    with open(old_file, encoding="utf-8") as f1, open(new_file, encoding="utf-8") as f2:
        old = f1.readlines()
        new = f2.readlines()
    diff = list(difflib.unified_diff(old, new))
    return "".join(diff)

def backup_and_monitor():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    homepage_file = os.path.join(BACKUP_DIR, f"homepage_{date_str}.html")
    rss_file = os.path.join(BACKUP_DIR, f"rss_{date_str}.xml")
    comments_file = os.path.join(BACKUP_DIR, f"comments_{date_str}.xml")

    # Sauvegarde
    homepage = save_content(SITE_URL, homepage_file)
    rss = save_content(f"{SITE_URL}/feed", rss_file)
    comments = save_content(f"{SITE_URL}/comments/feed", comments_file)

    # Détection de changements suspects sur la page d'accueil
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("homepage_")])
    if len(files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, files[-2]), homepage_file)
        if diff:
            send_alert("ALERTE: Changement détecté sur la page d'accueil", diff[:2000])

    # Détection de nouveaux articles
    rss_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("rss_")])
    if len(rss_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, rss_files[-2]), rss_file)
        if diff:
            send_alert("ALERTE: Changement détecté dans le flux RSS", diff[:2000])

    # Détection de nouveaux commentaires
    comments_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("comments_")])
    if len(comments_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, comments_files[-2]), comments_file)
        if diff:
            send_alert("ALERTE: Nouveau commentaire ou modification détectée", diff[:2000])

if __name__ == "__main__":
    backup_and_monitor()