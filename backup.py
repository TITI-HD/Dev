#!/usr/bin/env python3
"""
Script de sauvegarde pour WordPress.com
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

# Configuration
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")

def create_backup_dir():
    """Crée le répertoire de sauvegarde s'il n'existe pas"""
    Path(BACKUP_DIR).mkdir(exist_ok=True)

def save_with_timestamp(content, backup_type, extension="html"):
    """Sauvegarde le contenu avec un horodatage"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{backup_type}_{timestamp}.{extension}"
    filepath = Path(BACKUP_DIR) / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Créer des métadonnées
    metadata = {
        "date": datetime.now().isoformat(),
        "url": SITE_URL,
        "type": backup_type,
        "filename": filename
    }
    
    meta_filepath = filepath.with_suffix(filepath.suffix + '.meta.json')
    with open(meta_filepath, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return filepath

def backup_homepage():
    """Sauvegarde la page d'accueil"""
    try:
        response = requests.get(SITE_URL)
        response.raise_for_status()
        
        filepath = save_with_timestamp(response.text, "homepage")
        print(f"✅ Page d'accueil sauvegardée: {filepath.name}")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde page d'accueil: {e}")
        return False

def backup_rss():
    """Sauvegarde le flux RSS"""
    try:
        rss_url = f"{SITE_URL}/feed/"
        response = requests.get(rss_url)
        response.raise_for_status()
        
        filepath = save_with_timestamp(response.text, "rss", "xml")
        print(f"✅ Flux RSS sauvegardé: {filepath.name}")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde RSS: {e}")
        return False

def backup_comments():
    """Sauvegarde les commentaires"""
    try:
        comments_url = f"{SITE_URL}/comments/feed/"
        response = requests.get(comments_url)
        response.raise_for_status()
        
        filepath = save_with_timestamp(response.text, "comments", "xml")
        print(f"✅ Commentaires sauvegardés: {filepath.name}")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde commentaires: {e}")
        return False

def main():
    """Fonction principale de sauvegarde"""
    print("💾 Démarrage de la sauvegarde")
    
    create_backup_dir()
    
    success_count = 0
    total_tasks = 3  # homepage, rss, comments
    
    if backup_homepage():
        success_count += 1
    
    if backup_rss():
        success_count += 1
    
    if backup_comments():
        success_count += 1
    
    print(f"📊 Résultat: {success_count}/{total_tasks} éléments sauvegardés")
    
    return success_count

if __name__ == "__main__":
    success_count = main()
    exit(0 if success_count > 0 else 1)