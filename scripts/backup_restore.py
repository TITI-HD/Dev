import boto3
import hashlib
import os
import subprocess
import sys
import time
from cryptography.fernet import Fernet
from utils import load_config, log

def backup_site():
    """
    Sauvegarde complète du site WordPress :
    - export base de données avec wp-cli
    - chiffrement AES-256 avec Fernet
    - upload vers bucket S3
    """
    config = load_config()
    backup_name = f"backup-{os.uname().nodename}-{int(time.time())}"
    db_file = f"/tmp/{backup_name}.sql"

    try:
        log("Début export base de données")
        # Export DB WordPress
        cmd = f"wp db export {db_file} --add-drop-table --path={config['wordpress']['path']}"
        subprocess.run(cmd, shell=True, check=True)

        log("Lecture et chiffrement du dump SQL")
        cipher = Fernet(config['backup']['encryption_key'].encode())
        with open(db_file, 'rb') as f:
            encrypted = cipher.encrypt(f.read())

        s3 = boto3.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
        checksum = hashlib.sha256(encrypted).hexdigest()
        s3.put_object(
            Bucket=config['backup']['s3_bucket'],
            Key=f"backups/{backup_name}.enc",
            Body=encrypted,
            Metadata={'checksum': checksum}
        )
        log(f"Sauvegarde {backup_name} réussie")
    except Exception as e:
        log(f"Erreur sauvegarde : {e}", level="error")
        sys.exit(1)
    finally:
        if os.path.exists(db_file):
            os.remove(db_file)

def restore_site(backup_key):
    """
    Restauration depuis un backup chiffré S3.
    - Télécharge et déchiffre le fichier
    - Importe la base SQL
    """
    config = load_config()
    cipher = Fernet(config['backup']['encryption_key'].encode())
    s3 = boto3.client('s3',
                      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

    tmp_encrypted = f"/tmp/{backup_key}.enc"
    tmp_decrypted = f"/tmp/{backup_key}.sql"

    try:
        log(f"Téléchargement du backup {backup_key}")
        s3.download_file(config['backup']['s3_bucket'], backup_key, tmp_encrypted)

        log("Déchiffrement du fichier")
        with open(tmp_encrypted, 'rb') as f_enc:
            decrypted = cipher.decrypt(f_enc.read())
        with open(tmp_decrypted, 'wb') as f_dec:
            f_dec.write(decrypted)

        log("Import de la base de données")
        cmd = f"wp db import {tmp_decrypted} --path={config['wordpress']['path']}"
        subprocess.run(cmd, shell=True, check=True)
        log("Restauration terminée")
    except Exception as e:
        log(f"Erreur restauration : {e}", level="error")
        sys.exit(1)
    finally:
        for f in [tmp_encrypted, tmp_decrypted]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backup_restore.py backup|restore [backup_key]")
        sys.exit(1)
    if sys.argv[1] == "backup":
        backup_site()
    elif sys.argv[1] == "restore" and len(sys.argv) == 3:
        restore_site(sys.argv[2])
    else:
        print("Arguments invalides.")
