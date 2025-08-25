#!/usr/bin/env python3
# Shebang pour exécuter le script avec Python 3.

"""
Script de surveillance WordPress
# Docstring décrivant le but global du script : surveiller des sites WordPress.
"""
<<<<<<< HEAD
from twilio.rest import Client
import os
=======

>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
import requests  # Importe la bibliothèque requests pour les requêtes HTTP.
import time  # Importe time pour des delays potentiels (non utilisé ici).
from send_whatsapp_notification import send_whatsapp_notification  # Importe la fonction d'envoi WhatsApp (définie ailleurs).

def check_wordpress_site(url):  # Fonction pour vérifier l'état d'un site WordPress.
    """Vérifie l'état d'un site WordPress"""  # Docstring expliquant la fonction : envoie une requête GET et vérifie le statut.
    try:  # Bloc try pour gérer les exceptions de requête.
        response = requests.get(url, timeout=10)  # Envoie une requête GET avec timeout de 10 secondes.
        
        if response.status_code == 200:  # Vérifie si le code HTTP est 200 (OK).
            print(f"✅ Site {url} accessible")  # Affiche un message de succès.
            return True  # Retourne True si accessible.
        else:  # Sinon, code non 200.
            print(f"❌ Site {url} retourne code {response.status_code}")  # Affiche un message d'erreur avec le code.
            return False  # Retourne False.
            
    except requests.RequestException as e:  # Capture les exceptions liées à requests.
        print(f"❌ Erreur de connexion à {url}: {e}")  # Affiche l'erreur.
        return False  # Retourne False en cas d'exception.

def main():  # Fonction principale du script.
    """Fonction principale"""  # Docstring pour la fonction main : orchestre la surveillance.
    sites_to_monitor = [  # Liste des sites à surveiller (hardcodée).
        "https://votresite1.com",  # Premier site exemple.
        "https://votresite2.com"  # Deuxième site exemple.
    ]
    
    all_ok = True  # Flag initial pour indiquer si tous les sites sont OK.
    
    for site in sites_to_monitor:  # Boucle sur chaque site.
        if not check_wordpress_site(site):  # Appelle la fonction de check ; si False.
            all_ok = False  # Met le flag à False si un site échoue.
    
    # Envoi de notification  # Section pour notifier les résultats.
    if all_ok:  # Si tous OK.
        send_whatsapp_notification(  # Appelle la fonction d'envoi.
            "Surveillance WordPress - Tous les sites sont opérationnels",  # Message de succès.
            is_success=True  # Flag pour succès.
        )
    else:  # Si échec.
        send_whatsapp_notification(  # Appelle la fonction d'envoi.
            "Surveillance WordPress ÉCHEC - Un ou plusieurs sites sont indisponibles",  # Message d'échec.
            is_success=False  # Flag pour échec.
        )

<<<<<<< HEAD


def send_whatsapp_notification(message, is_success=True):
    try:
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        from_ = os.environ['TWILIO_WHATSAPP_FROM']
        to = os.environ['TWILIO_WHATSAPP_TO']
        
        client = Client(account_sid, auth_token)
        
        emoji = "✅" if is_success else "❌"
        full_message = f"{emoji} {message}"
        
        message = client.messages.create(
            body=full_message,
            from_=from_,
            to=to
        )
        return True
    except Exception as e:
        print(f"Erreur d'envoi WhatsApp: {e}")
        return False

=======
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
if __name__ == "__main__":  # Vérifie si le script est exécuté directement.
    main()  # Appelle la fonction main.