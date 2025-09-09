#!/usr/bin/env python3
"""
Script WordPress : Fetch + Sauvegarde + Restauration
- fetch : télécharge un snapshot statique d’un site WordPress
- backup : sauvegarde les fichiers avec un fichier de métadonnées global
- restore : restaure les fichiers avec vérification d’intégrité
"""

import os
import sys
import shutil
import hashlib
import json
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# === Configuration par défaut ===
DEFAULT_SOURCE = Path("wordpress_site")
BACKUP_DIR = Path("backups")
RESTORE_DIR = Path("restored")
LOG_FILE = BACKUP_DIR / "backup_restore.log"
META_FILE = BACKUP_DIR / "metadata.json"

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
    """Calcule le hash SHA256 d’un fichier"""
    h = hashlib.sha256()
    try:
        with file_path.open("rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        log(f"Erreur hash fichier {file_path}: {e}", "ERROR")
        return ""

# === Fetch WordPress ===
def fetch_wordpress_site(url: str, out_dir: Path):
    """Télécharge quelques endpoints publics WordPress (JSON + RSS + page d’accueil)"""
    out_dir.mkdir(parents=True, exist_ok=True)
    endpoints = {
        "homepage.html": url,
        "feed.xml": f"{url}/feed",
        "comments.xml": f"{url}/comments/feed",
        "posts.json": f"{url}/wp-json/wp/v2/posts",
        "pages.json": f"{url}/wp-json/wp/v2/pages",
    }
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_endpoint, endpoint, out_dir / filename): (filename, endpoint) for filename, endpoint in endpoints.items()}
        for future in futures:
            filename, endpoint = futures[future]
            try:
                future.result()
                log(f"Téléchargé : {endpoint} -> {out_dir / filename}", "SUCCESS")
            except Exception as e:
                log(f"Échec téléchargement {endpoint}: {e}", "ERROR")

def fetch_endpoint(endpoint: str, file_path: Path):
    try:
        resp = requests.get(endpoint, timeout=15)
        resp.raise_for_status()
        file_path.write_bytes(resp.content)
    except Exception as e:
        raise e

# === Sauvegarde ===
def backup_wordpress_content(source_dir: Path = DEFAULT_SOURCE):
    if not source_dir.exists():
        log(f"Dossier source '{source_dir}' inexistant.", "ERROR")
        return
    metadata = {}
    files_copied = 0
    for root, _, files in os.walk(source_dir):
        for filename in files:
            src_path = Path(root) / filename
            rel_path = src_path.relative_to(source_dir)
            dst_path = BACKUP_DIR / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, dst_path)
                metadata[str(rel_path)] = {
                    "hash": compute_hash(dst_path),
                    "timestamp": datetime.now().isoformat()
                }
                log(f"Fichier sauvegardé: {rel_path}", "SUCCESS")
                files_copied += 1
            except Exception as e:
                log(f"Impossible de sauvegarder {rel_path}: {e}", "ERROR")
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    log(f"Sauvegarde terminée: {files_copied} fichiers copiés.", "INFO")

# === Restauration ===
def restore_all_files(target_dir: Path = RESTORE_DIR):
    if not META_FILE.exists():
        log("Métadonnées introuvables, restauration impossible.", "ERROR")
        return
    try:
        with META_FILE.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        log(f"Erreur lecture métadonnées: {e}", "ERROR")
        return
    success_count = 0
    for rel_path, meta in metadata.items():
        backup_path = BACKUP_DIR / rel_path
        if backup_path.suffix == ".json":
            continue
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup_path, dest_path)
            current_hash = compute_hash(dest_path)
            if current_hash != meta["hash"]:
                log(f"Hash mismatch: {rel_path}", "ERROR")
            else:
                log(f"Restauration OK: {rel_path}", "SUCCESS")
            success_count += 1
        except Exception as e:
            log(f"Erreur restauration fichier {rel_path}: {e}", "ERROR")
    log(f"=== RESTAURATION TERMINÉE: {success_count}/{len(metadata)} fichiers ===", "INFO")

# === Menu principal ===
def main():
    if len(sys.argv) < 2:
        print("Usage: python wp_backup_restore.py [fetch|backup|restore] [--url=SITE] [--source=CHEMIN] [--dir=CHEMIN]")
        sys.exit(1)

    action = sys.argv[1].lower()
    source_dir = DEFAULT_SOURCE
    restore_target = RESTORE_DIR
    site_url = None

    for arg in sys.argv[2:]:
        if arg.startswith("--source="):
            source_dir = Path(arg.split("=", 1)[1])
        elif arg.startswith("--dir="):
            restore_target = Path(arg.split("=", 1)[1])
            restore_target.mkdir(parents=True, exist_ok=True)
        elif arg.startswith("--url="):
            site_url = arg.split("=", 1)[1]

    if action == "fetch":
        if not site_url:
            print("Erreur: --url= requis pour fetch")
            sys.exit(1)
        fetch_wordpress_site(site_url, source_dir)
    elif action == "backup":
        backup_wordpress_content(source_dir)
    elif action == "restore":
        restore_all_files(restore_target)
    else:
        print("Action inconnue. Utiliser 'fetch', 'backup' ou 'restore'.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Erreur critique: {e}", "ERROR")
        sys.exit(1)