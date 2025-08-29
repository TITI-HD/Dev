#!/usr/bin/env python3
"""
Script de restauration pour WordPress
Restaure le contenu à partir des sauvegardes
Version améliorée pour gérer les anciennes sauvegardes
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
import hashlib

def log(message: str):
    """Fonction de logging avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{timestamp}] {message}")
    except UnicodeEncodeError:
        # Si l'encodage échoue (ex: ✅ sur Windows), on remplace par un simple texte
        print(f"[{timestamp}] {message.encode('ascii', 'replace').decode()}")

def verify_backup_integrity(backup_path: str) -> bool:
    """Vérifie l'intégrité d'un fichier de sauvegarde"""
    try:
        metadata_path = backup_path + '.meta.json'
        if not os.path.exists(metadata_path):
            log(f"ATTENTION: Métadonnées manquantes pour {os.path.basename(backup_path)}")
            return True
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        if content_hash == metadata.get('hash'):
            log(f"SUCCES: Intégrité vérifiée: {os.path.basename(backup_path)}")
            return True
        else:
            log(f"ERREUR: Hash mismatch: {os.path.basename(backup_path)}")
            return False
    except Exception as e:
        log(f"ERREUR: Impossible de vérifier {os.path.basename(backup_path)}: {e}")
        return False

def restore_backups(backup_dir=None):
    """Restaure les sauvegardes vers le dossier de restauration"""
    if backup_dir is None:
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
    restore_dir = os.environ.get("RESTORE_DIR", "restore")

    Path(restore_dir).mkdir(exist_ok=True)

    if not os.path.exists(backup_dir):
        log(f"ERREUR: Le dossier de sauvegarde n'existe pas: {backup_dir}")
        return False

    backup_files = [f for f in os.listdir(backup_dir)
                    if not f.endswith('.meta.json') and not f.endswith('_report.json')]

    if not backup_files:
        log("ERREUR: Aucune sauvegarde trouvée")
        return False

    log(f"INFO: {len(backup_files)} sauvegardes trouvées")

    restored_files = []
    failed_files = []

    for file in backup_files:
        backup_path = os.path.join(backup_dir, file)
        verify_backup_integrity(backup_path)
        try:
            restore_path = os.path.join(restore_dir, file)
            shutil.copy2(backup_path, restore_path)

            metadata_src = backup_path + '.meta.json'
            metadata_dest = restore_path + '.meta.json'
            if os.path.exists(metadata_src):
                shutil.copy2(metadata_src, metadata_dest)

            restored_files.append(file)
            log(f"SUCCES: Fichier restauré: {file}")

        except Exception as e:
            log(f"ERREUR: Impossible de restaurer {file}: {e}")
            failed_files.append(file)

    # Création du rapport
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

if __name__ == "__main__":
    main()
