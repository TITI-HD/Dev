#!/usr/bin/env python3
"""
Script de sauvegarde complet pour WordPress.com
- Sauvegarde la homepage, RSS et commentaires
- Ajoute métadonnées (hash, taille, date)
- Nettoie les anciennes sauvegardes (> 7 jours)
"""

import os
import requests
import json
import hashlib
from datetime import datetime
from pathlib import Path

# === Configuration ===
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
Path(BACKUP_DIR).mkdir(exist_ok=True)

def log(message: str):
    """Log avec timestamp"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def fetch_url(url: str, timeout: int = 30) -> str:
    """Télécharge une page avec User-Agent"""
    try:
        headers = {'User-Agent': 'WordPress Backup Bot/1.0'}
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        log(f"ERREUR récupération {url}: {e}")
        return None

def save_backup(content: str, backup_type: str, extension: str = "html") -> str:
    """Sauvegarde contenu + métadonnées"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type}_{timestamp}.{extension}"
        filepath = os.path.join(BACKUP_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        metadata = {
            "url": SITE_URL,
            "date": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "type": backup_type,
            "filename": filename
        }
        with open(filepath + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        log(f"SUCCÈS sauvegarde {backup_type}: {filename}")
        return filepath
    except Exception as e:
        log(f"ERREUR sauvegarde {backup_type}: {e}")
        return None

def backup_wordpress_content():
    """Sauvegarde principale WordPress"""
    log("=== Début sauvegarde WordPress ===")
    endpoints = [
        (SITE_URL, "homepage", "html"),
        (SITE_URL + "/feed/", "rss", "xml"),
        (SITE_URL + "/comments/feed/", "comments", "xml"),
    ]
    success = 0
    for url, name, ext in endpoints:
        content = fetch_url(url)
        if content and save_backup(content, name, ext):
            success += 1
    log(f"=== Fin sauvegarde: {success}/{len(endpoints)} réussies ===")

def cleanup_old_backups(days: int = 7):
    """Supprime sauvegardes > N jours"""
    now = datetime.now()
    for file in Path(BACKUP_DIR).glob("*"):
        if file.is_file():
            age = (now - datetime.fromtimestamp(file.stat().st_mtime)).days
            if age > days:
                try:
                    file.unlink()
                    log(f"Supprimé ancien fichier: {file.name}")
                except Exception as e:
                    log(f"Erreur suppression {file.name}: {e}")
        
import gzip

TIMEOUT = int(os.environ.get("BACKUP_TIMEOUT", "30"))

def fetch_url(url: str, timeout: int = TIMEOUT) -> str:
    """Télécharge une page avec User-Agent et timeout configurable"""
    try:
        headers = {'User-Agent': 'WordPress Backup Bot/1.0'}
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        log(f"ERREUR récupération {url}: {e}")
        return None

def save_backup(content: str, backup_type: str, extension: str = "html") -> str:
    """Sauvegarde compressée + métadonnées"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{backup_type}_{timestamp}.{extension}.gz"
        filepath = os.path.join(BACKUP_DIR, filename)

        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            f.write(content)

        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        metadata = {
            "url": SITE_URL,
            "date": datetime.now().isoformat(),
            "hash": content_hash,
            "size": len(content),
            "compressed_file": filename
        }
        with open(filepath + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return filepath
    except Exception as e:
        log(f"ERREUR sauvegarde {backup_type}: {e}")
        return None


if __name__ == "__main__":
    backup_wordpress_content()
    cleanup_old_backups(7)
