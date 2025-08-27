#!/usr/bin/env python3
"""
Script de sauvegarde complet pour WordPress
Sauvegarde le contenu public et les métadonnées du site
Version corrigée pour WordPress.com
"""

import os
import requests
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Configuration
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
Path(BACKUP_DIR).mkdir(exist_ok=True)

def log(message: str):
    """Fonction de logging avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def fetch_url(url: str, timeout: int = 30) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (WordPress Backup Script)'}
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        log(f"ERREUR: Impossible de récupérer {url}: {e}")
        return None

def save_backup(content: str, backup_type: str, extension: str = "html") -> str:
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type}_{timestamp}.{extension}"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        # Sauvegarde contenu
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Hash SHA-256
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        metadata = {
            "url": SITE_URL,
            "date": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "type": backup_type,
            "filename": filename
        }
        
        with open(filepath + '.meta.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        log(f"SUCCES: Sauvegarde {backup_type} réussie: {filename}")
        return filepath
    except Exception as e:
        log(f"ERREUR: Impossible de sauvegarder {backup_type}: {e}")
        return None

def backup_wordpress_content():
    """Sauvegarde le contenu public WordPress"""
    log("DEBUT: Sauvegarde WordPress...")
    endpoints = [
        (SITE_URL, "homepage", "html"),
        (SITE_URL + "/feed/", "rss", "xml"),
        (SITE_URL + "/comments/feed/", "comments", "xml")
    ]
    
    successful_backups = 0
    for url, backup_type, extension in endpoints:
        content = fetch_url(url)
        if content and save_backup(content, backup_type, extension):
            successful_backups += 1
        else:
            log(f"ATTENTION: Impossible de sauvegarder: {backup_type}")
    
    report = {
        "date": datetime.now().isoformat(),
        "site_url": SITE_URL,
        "total_endpoints": len(endpoints),
        "successful_backups": successful_backups,
        "status": "completed" if successful_backups > 0 else "failed"
    }
    
    report_path = os.path.join(BACKUP_DIR, f"backup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log(f"SUCCES: Sauvegarde terminée: {successful_backups}/{len(endpoints)} réussites")

def cleanup_old_backups(days: int = 7):
    log(f"Nettoyage des sauvegardes de plus de {days} jours...")
    now = datetime.now()
    removed_files = 0
    for file in Path(BACKUP_DIR).glob("*"):
        if file.is_file():
            age_days = (now - datetime.fromtimestamp(file.stat().st_mtime)).days
            if age_days > days:
                try:
                    file.unlink()
                    removed_files += 1
                    log(f"SUPPRIMÉ: {file.name} (âgé de {age_days} jours)")
                except Exception as e:
                    log(f"Erreur suppression {file.name}: {e}")
    log("Nettoyage terminé." if removed_files else "Aucun fichier ancien à supprimer.")

if __name__ == "__main__":
    backup_wordpress_content()
