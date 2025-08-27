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
    """
    Récupère le contenu d'une URL avec gestion des erreurs
    
    Args:
        url: L'URL à récupérer
        timeout: Timeout de la requête en secondes
        
    Returns:
        Le contenu texte de la réponse ou None en cas d'erreur
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (WordPress Backup Script)'}
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        log(f"ERREUR: Impossible de récupérer {url}: {e}")
        return None

def save_backup(content: str, backup_type: str, extension: str = "html") -> str:
    """
    Sauvegarde le contenu dans un fichier avec métadonnées
    
    Args:
        content: Le contenu à sauvegarder
        backup_type: Type de sauvegarde (homepage, rss, comments, etc.)
        extension: Extension du fichier
        
    Returns:
        Le chemin du fichier sauvegardé
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type}_{timestamp}.{extension}"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        # Sauvegarde du contenu
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Calcul du hash SHA-256 pour l'intégrité
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Métadonnées de sauvegarde
        metadata = {
            "url": SITE_URL,
            "date": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "type": backup_type,
            "filename": filename
        }
        
        # Sauvegarde des métadonnées
        with open(filepath + '.meta.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        log(f"SUCCES: Sauvegarde {backup_type} réussie: {filename}")
        return filepath
        
    except Exception as e:
        log(f"ERREUR: Impossible de sauvegarder {backup_type}: {e}")
        return None

def backup_wordpress_content():
    """Sauvegarde le contenu public WordPress"""
    log("DEBUT: Démarrage de la sauvegarde WordPress...")
    
    # URLs à sauvegarder (uniquement celles disponibles sur WordPress.com)
    endpoints = [
        (SITE_URL, "homepage", "html"),
        (SITE_URL + "/feed/", "rss", "xml"),
        (SITE_URL + "/comments/feed/", "comments", "xml")
    ]
    
    successful_backups = 0
    
    for url, backup_type, extension in endpoints:
        content = fetch_url(url)
        if content:
            if save_backup(content, backup_type, extension):
                successful_backups += 1
        else:
            log(f"ATTENTION: Impossible de sauvegarder: {backup_type}")
    
    # Rapport de sauvegarde
    backup_report = {
        "date": datetime.now().isoformat(),
        "site_url": SITE_URL,
        "total_endpoints": len(endpoints),
        "successful_backups": successful_backups,
        "status": "completed" if successful_backups > 0 else "failed"
    }
    
    report_path = os.path.join(BACKUP_DIR, f"backup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(backup_report, f, indent=2, ensure_ascii=False)
    
    log(f"SUCCES: Sauvegarde terminée: {successful_backups}/{len(endpoints)} réussites")

def main():
    """Fonction principale"""
    try:
        backup_wordpress_content()
    except Exception as e:
        log(f"ERREUR CRITIQUE: Erreur lors de la sauvegarde: {e}")
        exit(1)

if __name__ == "__main__":
    main()