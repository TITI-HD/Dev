#!/usr/bin/env python3
"""
Script complet WordPress : sauvegarde et restauration
- Sauvegarde les fichiers WordPress avec métadonnées JSON
- Restaure les fichiers avec vérification d'intégrité
- Compatible Windows et Linux
"""

import os
import sys
import shutil
import hashlib
import json
from pathlib import Path
from datetime import datetime

# === Configuration ===
SOURCE_DIR = "wordpress_site"   # Dossier WordPress à sauvegarder
BACKUP_DIR = "backups"          # Dossier pour sauvegarde
RESTORE_DIR = "restored"        # Dossier pour restauration
Path(BACKUP_DIR).mkdir(exist_ok=True)
Path(RESTORE_DIR).mkdir(exist_ok=True)
LOG_FILE = os.path.join(RESTORE_DIR, "backup_restore.log")

# === Logging ===
def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# === Utilitaires ===
def compute_hash(file_path: str) -> str:
    """Calcule le hash SHA256 du fichier"""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        log(f"ERREUR hash fichier {file_path}: {e}")
        return ""

def save_metadata(file_path: str, backup_file: str):
    """Génère un fichier JSON avec les métadonnées du fichier sauvegardé"""
    meta = {
        "original_file": os.path.basename(file_path),
        "backup_file": os.path.basename(backup_file),
        "hash": compute_hash(backup_file),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    meta_file = f"{backup_file}.json"
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log(f"ERREUR création métadonnées {meta_file}: {e}")

def load_metadata(file_path: str) -> dict:
    """Charge les métadonnées JSON si elles existent"""
    meta_path = f"{file_path}.json"
    if not os.path.exists(meta_path):
        log(f"ATTENTION: Métadonnées manquantes pour {os.path.basename(file_path)}")
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"ERREUR lecture métadonnées {meta_path}: {e}")
        return {}

# === Fonctions principales ===
def backup_wordpress_content():
    """Sauvegarde tous les fichiers et génère les métadonnées"""
    if not os.path.exists(SOURCE_DIR):
        log(f"[ERREUR] Le dossier source '{SOURCE_DIR}' n'existe pas.")
        return

    files_copied = 0
    for root, _, files in os.walk(SOURCE_DIR):
        for filename in files:
            src_path = os.path.join(root, filename)
            dst_path = os.path.join(BACKUP_DIR, filename)
            try:
                shutil.copy2(src_path, dst_path)
                save_metadata(src_path, dst_path)
                log(f"[SUCCES] Fichier sauvegardé: {filename}")
                files_copied += 1
            except Exception as e:
                log(f"[ERREUR] Impossible de sauvegarder {filename}: {e}")
    log(f"[INFO] Sauvegarde terminée: {files_copied} fichiers copiés.")

def restore_file(file_path: str):
    """Restaure un fichier et vérifie l'intégrité si métadonnées présentes"""
    dest_path = os.path.join(RESTORE_DIR, os.path.basename(file_path))
    try:
        shutil.copy2(file_path, dest_path)
        log(f"SUCCES: Fichier restauré: {os.path.basename(file_path)}")
        meta = load_metadata(file_path)
        if "hash" in meta:
            current_hash = compute_hash(dest_path)
            if current_hash != meta["hash"]:
                log(f"ERREUR: Hash mismatch: {os.path.basename(file_path)}")
            else:
                log(f"SUCCES: Intégrité vérifiée: {os.path.basename(file_path)}")
        return True
    except Exception as e:
        log(f"ERREUR restauration fichier {os.path.basename(file_path)}: {e}")
        return False

def restore_all_files():
    """Restaure tous les fichiers de BACKUP_DIR"""
    files = sorted(Path(BACKUP_DIR).glob("*.*"))
    if not files:
        log("Aucune sauvegarde trouvée.")
        return
    success_count = 0
    for file_path in files:
        if restore_file(str(file_path)):
            success_count += 1
    total_files = len(files)
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{total_files} fichiers restaurés ===")

# === Menu principal ===
def main():
    if len(sys.argv) < 2:
        print("Usage: python wp_backup_restore.py [backup|restore]")
        sys.exit(1)
    action = sys.argv[1].lower()
    if action == "backup":
        backup_wordpress_content()
    elif action == "restore":
        restore_all_files()
    else:
        print("Action inconnue. Utiliser 'backup' ou 'restore'.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}")
        sys.exit(1)
