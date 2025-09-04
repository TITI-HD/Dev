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
SOURCE_DIR = Path("wordpress_site")
BACKUP_DIR = Path("backups")
RESTORE_DIR = Path("restored")
LOG_FILE = RESTORE_DIR / "backup_restore.log"

BACKUP_DIR.mkdir(exist_ok=True, parents=True)
RESTORE_DIR.mkdir(exist_ok=True, parents=True)

# === Logging ===
def log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# === Utilitaires ===
def compute_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    try:
        with file_path.open("rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        log(f"Erreur hash fichier {file_path}: {e}", "ERROR")
        return ""

def save_metadata(src_path: Path, backup_path: Path):
    meta = {
        "original_file": str(src_path.relative_to(SOURCE_DIR)),
        "backup_file": str(backup_path.relative_to(BACKUP_DIR)),
        "hash": compute_hash(backup_path),
        "timestamp": datetime.now().isoformat()
    }
    meta_file = backup_path.with_suffix(backup_path.suffix + ".json")
    try:
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log(f"Erreur création métadonnées {meta_file}: {e}", "ERROR")

def load_metadata(backup_path: Path) -> dict:
    meta_file = backup_path.with_suffix(backup_path.suffix + ".json")
    if not meta_file.exists():
        log(f"Métadonnées manquantes pour {backup_path.name}", "WARNING")
        return {}
    try:
        with meta_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"Erreur lecture métadonnées {meta_file}: {e}", "ERROR")
        return {}

# === Fonctions principales ===
def backup_wordpress_content():
    if not SOURCE_DIR.exists():
        log(f"Dossier source '{SOURCE_DIR}' inexistant.", "ERROR")
        return
    files_copied = 0
    for root, _, files in os.walk(SOURCE_DIR):
        for filename in files:
            src_path = Path(root) / filename
            rel_path = src_path.relative_to(SOURCE_DIR)
            dst_path = BACKUP_DIR / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, dst_path)
                save_metadata(src_path, dst_path)
                log(f"Fichier sauvegardé: {rel_path}", "SUCCESS")
                files_copied += 1
            except Exception as e:
                log(f"Impossible de sauvegarder {rel_path}: {e}", "ERROR")
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés.", "INFO")

def restore_file(backup_path: Path):
    rel_path = Path(backup_path.name)
    dest_path = RESTORE_DIR / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(backup_path, dest_path)
        log(f"Fichier restauré: {rel_path}", "SUCCESS")
        meta = load_metadata(backup_path)
        if "hash" in meta:
            current_hash = compute_hash(dest_path)
            if current_hash != meta["hash"]:
                log(f"Hash mismatch: {rel_path}", "ERROR")
            else:
                log(f"Intégrité vérifiée: {rel_path}", "SUCCESS")
        return True
    except Exception as e:
        log(f"Erreur restauration fichier {rel_path}: {e}", "ERROR")
        return False

def restore_all_files():
    files = sorted(BACKUP_DIR.rglob("*.*"))
    if not files:
        log("Aucune sauvegarde trouvée.", "WARNING")
        return
    success_count = 0
    for file_path in files:
        if restore_file(file_path):
            success_count += 1
    total_files = len(files)
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{total_files} fichiers restaurés ===", "INFO")

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
        log(f"Erreur critique: {e}", "ERROR")
        sys.exit(1)
