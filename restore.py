#!/usr/bin/env python3
"""
Script de restauration manuelle pour WordPress.com
"""

import os
import shutil
import json
from datetime import datetime

def restore_backup():
    backup_dir = "backups"
    restore_dir = "restore"
    
    if not os.path.exists(restore_dir):
        os.makedirs(restore_dir)
    
    # Trouver la dernière sauvegarde
    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.html') or f.endswith('.xml')]
    if not backup_files:
        print("❌ Aucune sauvegarde trouvée")
        return False
    
    # Restaurer les fichiers
    for file in backup_files:
        shutil.copy2(os.path.join(backup_dir, file), restore_dir)
        print(f"✅ Fichier restauré: {file}")
    
    # Créer un rapport de restauration
    report = {
        "date": datetime.now().isoformat(),
        "restored_files": backup_files,
        "status": "success"
    }
    
    with open(os.path.join(restore_dir, "restore_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    
    print("✅ Restauration terminée avec succès")
    return True

if __name__ == "__main__":
    restore_backup()