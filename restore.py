#!/usr/bin/env python3
"""
Script de restauration WordPress
- Restaure les fichiers à partir des sauvegardes
- Vérifie intégrité via hash si les métadonnées existent
- Compatible Windows et Linux
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# === Configuration ===
BACKUP_DIR = "backups"
RESTORE_DIR = "restored"
Path(RESTORE_DIR).mkdir(exist_ok=True)
Path(BACKUP_DIR).mkdir(exist_ok=True)
LOG_FILE = os.path.join(RESTORE_DIR, "restore.log")


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


def restore_file(file_path: str):
    """Restaure un fichier et vérifie l'intégrité si métadonnées présentes"""
    dest_path = os.path.join(RESTORE_DIR, os.path.basename(file_path))
    try:
        # Copier le fichier
        with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
            dst.write(src.read())
        log(f"SUCCES: Fichier restauré: {os.path.basename(file_path)}")

        # Vérifier hash si métadonnées présentes
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


def main():
    log("=== DÉBUT RESTAURATION ===")
    success_count = 0
    files = sorted(Path(BACKUP_DIR).glob("*.*"))  # tous les fichiers

    if not files:
        log("Aucune sauvegarde trouvée.")
        sys.exit(1)

    for file_path in files:
        if restore_file(str(file_path)):
            success_count += 1

    total_files = len(files)
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{total_files} fichiers restaurés ===")

    # Sortie du script selon succès
    if success_count == total_files:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERREUR CRITIQUE: {e}")
        sys.exit(1)
