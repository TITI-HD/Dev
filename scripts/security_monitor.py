import hashlib
import os
import requests
import schedule
import sys
import time
from utils import load_config, log, send_alert

def uptime_check(config):
    """
    Vérifie que le site répond avec code HTTP 200.
    """
    url = config['wordpress']['url']
    try:
        resp = requests.get(url, timeout=5, headers={'User-Agent': 'WP-Monitor/1.0'})
        if resp.status_code != 200:
            send_alert(f"Site {url} répond avec HTTP {resp.status_code}")
            log(f"HTTP {resp.status_code} reçu", level="warning")
        else:
            log(f"Site {url} OK")
    except Exception as e:
        send_alert(f"Erreur connectivité site: {e}")
        log(f"Erreur HTTP: {e}", level="error")

def file_integrity_check(config):
    """
    Vérifie l’intégrité des fichiers critiques via hash statique.
    """
    critical_files = {
        'wp-login.php': 'd3f4ultH4sh',
        '.htaccess': 'an0th3rH4sh'
    }
    base_path = config['wordpress']['path']
    for f, expected_hash in critical_files.items():
        filepath = os.path.join(base_path, f)
        if not os.path.exists(filepath):
            send_alert(f"Fichier critique manquant: {f}")
            log(f"Fichier manquant: {f}", level="error")
            continue
        with open(filepath, 'rb') as file_to_check:
            data = file_to_check.read()
            current_hash = hashlib.sha256(data).hexdigest()
        if current_hash != expected_hash:
            send_alert(f"Intégrité compromise: {f}")
            log(f"Hash différent pour {f}", level="warning")
        else:
            log(f"Intégrité OK pour {f}")

def security_scan(config):
    """
    Placeholder pour scan WPScan API.
    À implémenter avec un client WPScan officiel.
    """
    log("Scan sécurité à implémenter")

def run_monitor():
    """
    Planifie et exécute les tâches de monitoring.
    """
    config = load_config()
    schedule.every(config['monitoring'].get('uptime_check_interval', 5)).minutes.do(lambda: uptime_check(config))
    schedule.every(config['monitoring'].get('uptime_check_interval', 5)).minutes.do(lambda: file_integrity_check(config))
    # Ajouter d'autres tâches si nécessaire

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    if "--monitor" in sys.argv:
        run_monitor()
    else:
        print("Usage: python security_monitor.py --monitor")
