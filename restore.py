#!/usr/bin/env python3
"""
Script de restauration pour sauvegardes WordPress.com
"""

import os
import json
import gnupg
import shutil
from datetime import datetime
from pathlib import Path

# Configuration
BACKUP_DIR = os.environ.get("BACKUP_DIR", "backups")
RESTORE_DIR = os.environ.get("RESTORE_DIR", "restore")
GPG_PASSPHRASE = os.environ.get("GPG_PASSPHRASE", "")

def decrypt_file(filepath, passphrase):
    """Déchiffre un fichier avec GPG"""
    if not filepath.endswith('.gpg'):
        return filepath
        
    gpg = gnupg.GPG()
    decrypted_file = filepath[:-4]  # Remove .gpg extension
    
    with open(filepath, 'rb') as f:
        status = gpg.decrypt_file(
            f,
            passphrase=passphrase,
            output=decrypted_file
        )
    
    if status.ok:
        return decrypted_file
    else:
        raise Exception(f"Erreur déchiffrement: {status.status}")

def find_latest_backup(backup_type):
    """Trouve la sauvegarde la plus récente d'un type donné"""
    backups = []
    backup_path = Path(BACKUP_DIR)
    
    for item in backup_path.iterdir():
        if item.is_file() and item.name.startswith(backup_type) and not item.name.endswith('.meta.json'):
            # Extraire la date du nom de fichier
            try:
                file_date_str = item.stem.split('_')[-1]
                if item.name.endswith('.gpg'):
                    file_date_str = file_date_str[:-4]  # Remove .gpg
                file_date = datetime.strptime(file_date_str, "%Y%m%d_%H%M%S")
                backups.append((file_date, item))
            except (ValueError, IndexError):
                continue
    
    if not backups:
        return None
        
    # Retourner la plus récente
    backups.sort(key=lambda x: x[0], reverse=True)
    return backups[0][1]

def restore_backup(backup_file, target_dir):
    """Restaure une sauvegarde"""
    target_dir_path = Path(target_dir)
    os.makedirs(target_dir_path, exist_ok=True)
    
    # Vérifier les métadonnées
    meta_file = backup_file.with_suffix(backup_file.suffix + '.meta.json')
    if meta_file.exists():
        with open(meta_file, 'r') as f:
            metadata = json.load(f)
        
        print(f"📋 Métadonnées: {metadata.get('date')} - {metadata.get('url', 'N/A')}")
    
    # Déchiffrer si nécessaire
    working_file = decrypt_file(str(backup_file), GPG_PASSPHRASE)
    
    # Copier le fichier dans le répertoire de restauration
    shutil.copy2(working_file, target_dir_path)
    
    # Nettoyer les fichiers temporaires
    if working_file != str(backup_file):
        os.remove(working_file)
    
    print(f"✅ Restauré: {backup_file.name} -> {target_dir}")

def find_latest_backup(backup_type):
    """Trouve la sauvegarde la plus récente d'un type donné"""
    backups = []
    backup_path = Path(BACKUP_DIR)
    
    for item in backup_path.iterdir():
        # Chercher les fichiers avec différentes extensions
        if (item.is_file() and 
            item.name.startswith(backup_type + '_') and 
            not item.name.endswith('.meta.json') and
            (item.name.endswith('.html') or item.name.endswith('.xml') or 
             item.name.endswith('.json') or item.name.endswith('.gz'))):
            
            # Extraire la date du nom de fichier
            try:
                stem = item.stem
                # Gérer les différentes extensions
                if stem.endswith('.html'):
                    stem = stem[:-5]  # Enlever .html
                elif stem.endswith('.xml'):
                    stem = stem[:-4]  # Enlever .xml
                
                parts = stem.split('_')
                if len(parts) >= 3:  # Format: type_YYYYMMDD_HHMMSS
                    file_date_str = f"{parts[-2]}_{parts[-1]}"
                    file_date = datetime.strptime(file_date_str, "%Y%m%d_%H%M%S")
                    backups.append((file_date, item))
            except (ValueError, IndexError):
                continue
    
    if not backups:
        return None
        
    # Retourner la plus récente
    backups.sort(key=lambda x: x[0], reverse=True)
    return backups[0][1]

def main():
    """Fonction principale de restauration"""
    print("🔄 Démarrage de la restauration")
    
    # Créer le répertoire de restauration
    restore_path = Path(RESTORE_DIR)
    os.makedirs(restore_path, exist_ok=True)
    
    # Types de sauvegardes à restaurer
    backup_types = ['homepage', 'rss', 'comments', 'export']
    
    restored_count = 0
    
    for backup_type in backup_types:
        latest_backup = find_latest_backup(backup_type)
        
        if latest_backup:
            try:
                target_path = restore_path / backup_type
                os.makedirs(target_path, exist_ok=True)
                
                restore_backup(latest_backup, str(target_path))
                restored_count += 1
                print(f"✅ {backup_type} restauré")
            except Exception as e:
                print(f"❌ Erreur restauration {backup_type}: {e}")
        else:
            print(f"⚠️ Aucune sauvegarde trouvée pour {backup_type}")
    
    print(f"📊 Résultat: {restored_count}/{len(backup_types)} éléments restaurés")
    
    # Générer un rapport de restauration
    report = {
        "date": datetime.now().isoformat(),
        "restored_items": restored_count,
        "total_items": len(backup_types),
        "backup_dir": BACKUP_DIR,
        "restore_dir": RESTORE_DIR
    }
    
    report_path = restore_path / "restore_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    return restored_count > 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)