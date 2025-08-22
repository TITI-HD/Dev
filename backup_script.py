#!/usr/bin/env python3
"""
Script de sauvegarde pour WordPress.com - Version complète
"""

import os
import requests
from datetime import datetime
import json
import hashlib

# Configuration
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

def fetch_url(url):
    """Récupère le contenu d'une URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Erreur lors de la récupération de {url}: {e}")
        return None

def save_backup(content, backup_type, extension="html"):
    """Sauvegarde le contenu dans un fichier"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{backup_type}_{timestamp}.{extension}"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Calcul du hash pour vérification d'intégrité
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    
    # Sauvegarde des métadonnées
    metadata = {
        "url": SITE_URL,
        "date": datetime.now().isoformat(),
        "hash": content_hash,
        "size": len(content),
        "type": backup_type
    }
    
    with open(filepath + '.meta.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Sauvegarde {backup_type} réussie: {filename}")
    return filepath

def handle_manual_export():
    """Gère l'export manuel WordPress"""
    print("📋 Export manuel détecté")
    
    # Chercher le fichier d'export le plus récent
    export_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith('export_') and f.endswith('.xml')]
    
    if export_files:
        # Prendre le fichier le plus récent
        latest_export = sorted(export_files, reverse=True)[0]
        export_path = os.path.join(BACKUP_DIR, latest_export)
        
        # Lire le contenu pour calculer le hash
        with open(export_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # Créer les métadonnées
        metadata = {
            "url": SITE_URL,
            "date": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "type": "manual_export",
            "file": latest_export
        }
        
        with open(export_path + '.meta.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Export manuel enregistré: {latest_export}")
        return True
    else:
        print("⚠️ Aucun fichier d'export manuel trouvé")
        return False

def main():
    """Fonction principale de sauvegarde"""
    print("🔄 Démarrage de la sauvegarde...")
    
    # Sauvegarde de la page d'accueil
    homepage = fetch_url(SITE_URL)
    if homepage:
        save_backup(homepage, "homepage")
    
    # Sauvegarde du flux RSS
    rss_url = SITE_URL + "/feed/"
    rss_content = fetch_url(rss_url)
    if rss_content:
        save_backup(rss_content, "rss")
    
    # Sauvegarde du flux de commentaires
    comments_rss_url = SITE_URL + "/comments/feed/"
    comments_rss_content = fetch_url(comments_rss_url)
    if comments_rss_content:
        save_backup(comments_rss_content, "comments")
    
    # Gestion de l'export manuel
    handle_manual_export()
    
    print("✅ Sauvegarde terminée")

if __name__ == "__main__":
    main()