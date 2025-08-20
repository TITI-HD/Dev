#!/usr/bin/env python3
"""
Script de sauvegarde complet pour WordPress.com
Sauvegarde le contenu public via les APIs disponibles avec chiffrement et rotation
"""

import os
import requests
import json
from datetime import datetime, timedelta
import gzip
import hashlib
import gnupg
import shutil
from pathlib import Path

# Configuration
SITE_URL = os.environ.get("SITE_URL", "https://oupssecuretest.wordpress.com")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
GPG_RECIPIENT = os.environ.get("GPG_RECIPIENT", "")
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "7"))

def create_backup_dir():
    """Crée le répertoire de sauvegarde"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return True

def encrypt_file(filepath, recipient):
    """Chiffre un fichier avec GPG"""
    if not recipient:
        print("⚠️ Aucun destinataire GPG configuré, chiffrement ignoré")
        return filepath
        
    gpg = gnupg.GPG()
    encrypted_file = f"{filepath}.gpg"
    
    with open(filepath, 'rb') as f:
        status = gpg.encrypt_file(
            f,
            recipients=[recipient],
            output=encrypted_file,
            always_trust=True
        )
    
    if status.ok:
        os.remove(filepath)  # Supprime le fichier non chiffré
        return encrypted_file
    else:
        print(f"❌ Erreur chiffrement: {status.status}")
        return filepath

def rotate_backups():
    """Supprime les sauvegardes plus anciennes que RETENTION_DAYS"""
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    for item in Path(BACKUP_DIR).iterdir():
        if item.is_file():
            # Extraire la date du nom de fichier
            try:
                file_date_str = item.stem.split('_')[-1]
                file_date = datetime.strptime(file_date_str, "%Y%m%d_%H%M%S")
                
                if file_date < cutoff_date:
                    item.unlink()
                    print(f"🗑️ Suppression ancienne sauvegarde: {item.name}")
            except (ValueError, IndexError):
                # Fichier sans date valide, on ignore
                pass

def backup_content(url, filename):
    """Sauvegarde le contenu d'une URL avec chiffrement"""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        content = response.text
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{filename}_{timestamp}"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # Sauvegarde non compressée temporaire
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # Chiffrement
        encrypted_path = encrypt_file(backup_path, GPG_RECIPIENT)
        
        # Compression (si non chiffré)
        if not encrypted_path.endswith('.gpg'):
            with open(backup_path, 'rb') as f_in:
                with gzip.open(backup_path + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(backup_path)
            final_path = backup_path + '.gz'
        else:
            final_path = encrypted_path
            
        # Vérification de l'intégrité
        with open(final_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        # Enregistrement des métadonnées
        metadata = {
            'url': url,
            'date': datetime.now().isoformat(),
            'hash': file_hash,
            'size': os.path.getsize(final_path),
            'encrypted': final_path.endswith('.gpg')
        }
        
        with open(final_path + '.meta.json', 'w') as f:
            json.dump(metadata, f, indent=2)
            
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde {url}: {e}")
        return False

def backup_database():
    """Sauvegarde la base de données via XML-RPC (simulation pour WordPress.com)"""
    # WordPress.com ne permet pas l'accès direct à la DB
    # On utilise l'API d'export comme solution alternative
    try:
        export_url = f"{SITE_URL}/wp-json/wp/v2/export"
        response = requests.get(export_url, timeout=15)
        
        if response.status_code == 200:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"export_{timestamp}.xml")
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Chiffrement
            encrypted_path = encrypt_file(backup_path, GPG_RECIPIENT)
            
            metadata = {
                'type': 'database_export',
                'date': datetime.now().isoformat(),
                'encrypted': encrypted_path.endswith('.gpg')
            }
            
            with open(encrypted_path + '.meta.json', 'w') as f:
                json.dump(metadata, f, indent=2)
                
            return True
        else:
            print("⚠️ Export DB non disponible, utilisation des APIs standards")
            return False
    except Exception as e:
        print(f"❌ Erreur export DB: {e}")
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
        'api_pages': f"{SITE_URL}/wp-json/wp/v2/pages",
        'api_categories': f"{SITE_URL}/wp-json/wp/v2/categories",
        'api_tags': f"{SITE_URL}/wp-json/wp/v2/tags"
    }
    
    success_count = 0
    total_tasks = len(backup_urls) + 1  # +1 pour l'export DB
    
    # Sauvegarde de la base de données (export)
    if backup_database():
        success_count += 1
        print("✅ Export base de données sauvegardé")
    else:
        print("⚠️ Export base de données échoué, continuation avec APIs")
    
    # Sauvegarde du contenu
    for name, url in backup_urls.items():
        if backup_content(url, name):
            success_count += 1
            print(f"✅ {name} sauvegardé")
        else:
            print(f"❌ Échec sauvegarde {name}")
    
    # Rotation des sauvegardes
    rotate_backups()
    
    print(f"📊 Résultat: {success_count}/{total_tasks} sauvegardes réussies")
    return success_count >= len(backup_urls)  # On tolère l'échec de l'export DB

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)