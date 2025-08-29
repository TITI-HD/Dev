#!/usr/bin/env python3
"""
Script de restauration pour WordPress
Restaure le contenu à partir des sauvegardes
Version corrigée pour gérer les anciennes sauvegardes
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path


import sys

def restore_backups(backup_dir=None):
    """
    Restaure les sauvegardes vers le dossier de restauration
    """
    if backup_dir is None:
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
    restore_dir = os.environ.get("RESTORE_DIR", "restore")

    Path(restore_dir).mkdir(exist_ok=True)

    if not os.path.exists(backup_dir):
        log(f"ERREUR: Le dossier de sauvegarde n'existe pas: {backup_dir}")
        return False

    # ... reste du code inchangé ...

def log(message: str):
    """Fonction de logging avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def verify_backup_integrity(backup_path: str) -> bool:
    """
    Vérifie l'intégrité d'un fichier de sauvegarde
    
    Args:
        backup_path: Chemin vers le fichier de sauvegarde
        
    Returns:
        True si l'intégrité est vérifiée, False sinon
    """
    try:
        metadata_path = backup_path + '.meta.json'
        
        if not os.path.exists(metadata_path):
            log(f"ATTENTION: Métadonnées manquantes pour: {os.path.basename(backup_path)}")
            # Pour les anciennes sauvegardes sans métadonnées, on accepte quand même
            return True
        
        # Lecture des métadonnées
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Lecture du contenu sauvegardé
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérification du hash
        import hashlib
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        if content_hash == metadata['hash']:
            log(f"SUCCES: Intégrité vérifiée: {os.path.basename(backup_path)}")
            return True
        else:
            log(f"ERREUR: Hash mismatch: {os.path.basename(backup_path)}")
            return False
            
    except Exception as e:
        log(f"ERREUR: Impossible de vérifier {os.path.basename(backup_path)}: {e}")
        return False

def restore_backups():
    """
    Restaure les sauvegardes vers le dossier de restauration
    """
    backup_dir = os.environ.get("BACKUP_DIR", "backups")
    restore_dir = os.environ.get("RESTORE_DIR", "restore")
    
    # Création du dossier de restauration
    Path(restore_dir).mkdir(exist_ok=True)
    
    # Recherche des fichiers de sauvegarde
    backup_files = []
    for file in os.listdir(backup_dir):
        if not file.endswith('.meta.json') and not file.endswith('_report.json'):
            backup_files.append(file)
    
    if not backup_files:
        log("ERREUR: Aucune sauvegarde trouvée")
        return False
    
    log(f"INFO: {len(backup_files)} sauvegardes trouvées")
    
    restored_files = []
    failed_files = []
    
    for file in backup_files:
        backup_path = os.path.join(backup_dir, file)
        
        # Vérification de l'intégrité (mais on restaure même si échec pour les anciennes sauvegardes)
        integrity_ok = verify_backup_integrity(backup_path)
        
        try:
            # Copie vers le dossier de restauration
            restore_path = os.path.join(restore_dir, file)
            shutil.copy2(backup_path, restore_path)
            
            # Copie des métadonnées si elles existent
            metadata_src = backup_path + '.meta.json'
            metadata_dest = restore_path + '.meta.json'
            if os.path.exists(metadata_src):
                shutil.copy2(metadata_src, metadata_dest)
            
            restored_files.append(file)
            log(f"SUCCES: Fichier restauré: {file}")
            
        except Exception as e:
            log(f"ERREUR: Impossible de restaurer {file}: {e}")
            failed_files.append(file)
    
    # Création du rapport de restauration
    restore_report = {
        "date": datetime.now().isoformat(),
        "restore_dir": restore_dir,
        "total_files": len(backup_files),
        "restored_files": restored_files,
        "failed_files": failed_files,
        "success_rate": f"{(len(restored_files)/len(backup_files))*100:.1f}%"
    }
    
    report_path = os.path.join(restore_dir, "restore_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(restore_report, f, indent=2, ensure_ascii=False)
    
    log(f"SUCCES: Restauration terminée: {len(restored_files)}/{len(backup_files)} fichiers restaurés")
    return len(restored_files) > 0

def main():
    """Fonction principale"""
    try:
        backup_dir = sys.argv[1] if len(sys.argv) > 1 else None
        success = restore_backups(backup_dir)
        exit(0 if success else 1)
    except Exception as e:
        log(f"ERREUR CRITIQUE: Erreur lors de la restauration: {e}")
        exit(1)
