#!/usr/bin/env python3
"""
Script de sauvegarde pour WordPress.com
Sauvegarde le contenu public via les APIs disponibles
"""

import os
import requests
import json
from datetime import datetime
import gzip
import hashlib

# Configuration
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")

def create_backup_dir():
    """Crée le répertoire de sauvegarde"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return True

def backup_content(url, filename):
    """Sauvegarde le contenu d'une URL"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        content = response.text
        backup_path = os.path.join(BACKUP_DIR, filename)
        
        # Compression
        with gzip.open(backup_path + '.gz', 'wt', encoding='utf-8') as f:
            f.write(content)
            
        # Vérification de l'intégrité
        with open(backup_path + '.gz', 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        # Enregistrement des métadonnées
        metadata = {
            'url': url,
            'date': datetime.now().isoformat(),
            'hash': file_hash,
            'size': os.path.getsize(backup_path + '.gz')
        }
        
        with open(backup_path + '.meta.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde {url}: {e}")
        return False

def main():
    """Fonction principale de sauvegarde"""
    print("💾 Démarrage de la sauvegarde WordPress.com")
    
    if not create_backup_dir():
        print("❌ Impossible de créer le dossier de sauvegarde")
        return False
    
    # URLs à sauvegarder
    backup_urls = {
        'homepage': SITE_URL,
        'rss': f"{SITE_URL}/feed",
        'comments': f"{SITE_URL}/comments/feed",
        'api_posts': f"{SITE_URL}/wp-json/wp/v2/posts",
        'api_pages': f"{SITE_URL}/wp-json/wp/v2/pages"
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success_count = 0
    
    for name, url in backup_urls.items():
        filename = f"{name}_{timestamp}"
        if backup_content(url, filename):
            success_count += 1
            print(f"✅ {name} sauvegardé")
        else:
            print(f"❌ Échec sauvegarde {name}")
    
    print(f"📊 Résultat: {success_count}/{len(backup_urls)} sauvegardes réussies")
    return success_count == len(backup_urls)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)