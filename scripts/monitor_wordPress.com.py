import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===============================
# 🔧 Configuration via variables d'environnement
# ===============================
SITE_URL = os.environ.get("SITE_URL", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "")

SMTP_SERVER = os.environ.get("SMTP_SERVER", "")
SMTP_PORT = os.environ.get("SMTP_PORT", "587")  # Valeur par défaut
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

# Vérification et conversion du port
try:
    SMTP_PORT = int(SMTP_PORT) if SMTP_PORT.strip() else 587
except ValueError:
    print("⚠️ Erreur: SMTP_PORT invalide, utilisation du port par défaut 587")
    SMTP_PORT = 587


# ===============================
# 🔍 Vérification du site WordPress.com
# ===============================
def check_site(url: str) -> bool:
    """Vérifie si le site est accessible via HTTP."""
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erreur lors de l'accès au site: {e}")
        return False


def check_wordpress_com_api(url: str) -> bool:
    """Vérifie si l'API REST WordPress.com du site répond."""
    try:
        api_url = url.rstrip("/") + "/wp-json/"
        response = requests.get(api_url, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erreur API REST: {e}")
        return False


# ===============================
# 📧 Envoi d'alerte email
# ===============================
def send_alert(subject: str, message: str):
    """Envoie un mail d'alerte en cas de problème."""
    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        print("⚠️ Configuration SMTP incomplète, impossible d'envoyer l'alerte.")
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
        print(f"❌ Erreur lors de l'envoi de l'alerte: {e}")


# ===============================
# 🚀 Programme principal
# ===============================
def main():
    print(f"🔍 Vérification du site : {SITE_URL}")

    site_ok = check_site(SITE_URL)
    api_ok = check_wordpress_com_api(SITE_URL)

    if site_ok and api_ok:
        print(f"✅ Le site {SITE_URL} est en ligne et l’API REST répond correctement.")
    else:
        print(f"❌ Problème détecté sur {SITE_URL}")
        send_alert(
            subject="🚨 Alerte - WordPress.com Down",
            message=f"Le site {SITE_URL} ou son API REST est inaccessible."
        )


if __name__ == "__main__":
    main()