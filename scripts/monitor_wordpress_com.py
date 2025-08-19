import os
import smtplib
import requests
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ===============================
# 🔧 Configuration via variables d'environnement
# ===============================
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL",danieltiti882@gmail.com"")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")
SMTP_USER = os.environ.get("SMTP_USER",danieltiti882@gmail.com)
SMTP_PASS = os.environ.get("SMTP_PASS", "frwl akld agpo yaki")
BACKUP_DIR = "backups"

# Vérification du port
try:
    SMTP_PORT = int(SMTP_PORT) if SMTP_PORT.strip() else 587
except ValueError:
    print("⚠️ SMTP_PORT invalide, utilisation du port par défaut 587")
    SMTP_PORT = 587


# ===============================
# 📧 Envoi d'alerte email
# ===============================
def send_alert(subject: str, message: str):
    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        print("⚠️ SMTP non configuré, alerte ignorée.")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())

        print(f"✅ Alerte envoyée à {ALERT_EMAIL}")
    except Exception as e:
        print(f"❌ Erreur envoi mail: {e}")


# ===============================
# 🔍 Vérification de disponibilité du site & API REST
# ===============================
def check_site(url: str) -> bool:
    try:
        r = requests.get(url, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Erreur site: {e}")
        return False

def check_api(url: str) -> bool:
    try:
        r = requests.get(url.rstrip("/") + "/wp-json/", timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Erreur API: {e}")
        return False


# ===============================
# 💾 Sauvegarde & Comparaison de contenu
# ===============================
def save_content(url, filename):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        return r.text
    except Exception as e:
        send_alert("🚨 Site indisponible", f"Erreur accès {url}: {e}")
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

    # Sauvegardes
    homepage = save_content(SITE_URL, homepage_file)
    rss = save_content(f"{SITE_URL}/feed", rss_file)
    comments = save_content(f"{SITE_URL}/comments/feed", comments_file)

    # Détection changements page d’accueil
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("homepage_")])
    if len(files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, files[-2]), homepage_file)
        if diff:
            send_alert("🚨 Changement page d'accueil", diff[:2000])

    # Détection nouveaux articles
    rss_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("rss_")])
    if len(rss_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, rss_files[-2]), rss_file)
        if diff:
            send_alert("🚨 Nouveau contenu RSS", diff[:2000])

    # Détection nouveaux commentaires
    comments_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("comments_")])
    if len(comments_files) >= 2:
        diff = compare_files(os.path.join(BACKUP_DIR, comments_files[-2]), comments_file)
        if diff:
            send_alert("🚨 Nouveau commentaire", diff[:2000])


# ===============================
# 🚀 Main
# ===============================
def main():
    print(f"🔍 Vérification du site : {SITE_URL}")

    site_ok = check_site(SITE_URL)
    api_ok = check_api(SITE_URL)

    if site_ok and api_ok:
        print(f"✅ {SITE_URL} est en ligne & API REST OK.")
    else:
        send_alert("🚨 WordPress.com Down", f"{SITE_URL} ou API REST inaccessible.")

    # Sauvegarde + surveillance contenu
    backup_and_monitor()


if __name__ == "__main__":
    main()