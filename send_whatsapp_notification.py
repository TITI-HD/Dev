#!/usr/bin/env python3
"""
Script de surveillance WordPress
"""

import requests
import time
from send_whatsapp_notification import send_whatsapp_notification

def check_wordpress_site(url):
    """Vérifie l'état d'un site WordPress"""
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Site {url} accessible")
            return True
        else:
            print(f"❌ Site {url} retourne code {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Erreur de connexion à {url}: {e}")
        return False

def main():
    """Fonction principale"""
    sites_to_monitor = [
        "https://votresite1.com",
        "https://votresite2.com"
    ]
    
    all_ok = True
    
    for site in sites_to_monitor:
        if not check_wordpress_site(site):
            all_ok = False
    
    # Envoi de notification
    if all_ok:
        send_whatsapp_notification(
            "Surveillance WordPress - Tous les sites sont opérationnels",
            is_success=True
        )
    else:
        send_whatsapp_notification(
            "Surveillance WordPress ÉCHEC - Un ou plusieurs sites sont indisponibles",
            is_success=False
        )

if __name__ == "__main__":
    main()