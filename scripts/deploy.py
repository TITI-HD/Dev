import os  # Pour accéder aux variables d'environnement et chemins de fichiers
import paramiko  # Pour la connexion SSH
import subprocess  # Pour exécuter des commandes système (rsync)
import sys  # Pour gérer les sorties et erreurs système
from utils import load_config, log  # Fonctions utilitaires personnalisées
import requests
import boto3
import cryptography
import schedule
import python-dotenv
import pytest
from scripts.utils import load_config

class WordPressDeployer:
    def __init__(self, env='production'):
        """
        Initialise le déployeur avec la config donnée.
        Charge la configuration et établit la connexion SSH.
        """
        self.config = load_config()  # Charge la config depuis le fichier INI
        self.ssh_client = None
        self.ssh_connect()  # Établit la connexion SSH dès l'init

    def ssh_connect(self):
        """
        Établit une connexion SSH persistante avec keepalive.
        Utilise la clé privée définie dans SSH_KEY_PATH.
        """
        try:
            key_path = os.getenv('SSH_KEY_PATH')  # Récupère le chemin de la clé privée
            if not key_path or not os.path.exists(key_path):
                log("Clé SSH non trouvée ou variable SSH_KEY_PATH non définie", level="error")
                sys.exit(1)

            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.config['server']['ip'],
                port=int(self.config['server']['ssh_port']),
                username=self.config['server']['ssh_user'],
                key_filename=key_path,
                timeout=10,
                banner_timeout=200,
                allow_agent=False,
                look_for_keys=False
            )
            log("Connexion SSH établie")
        except Exception as e:
            log(f"Erreur connexion SSH: {e}", level="error")
            sys.exit(1)

    def sync_files(self):
        """
        Synchronisation des fichiers WordPress via rsync sur SSH.
        Utilise les infos de config pour cibler le bon dossier.
        """
        try:
            wp_path = self.config['wordpress']['path']
            ssh_port = self.config['server']['ssh_port']
            ssh_user = self.config['server']['ssh_user']
            server_ip = self.config['server']['ip']

            # Commande rsync pour synchroniser wp-content
            rsync_command = (
                f"rsync -az --delete --partial -e 'ssh -p {ssh_port}' "
                f"./wp-content/ {ssh_user}@{server_ip}:{wp_path}/wp-content/"
            )
            log(f"Exécution de : {rsync_command}")
            subprocess.run(rsync_command, shell=True, check=True)
            log("Synchronisation fichiers réussie")
        except subprocess.CalledProcessError as e:
            log(f"Erreur rsync : {e}", level="error")
            self.rollback()
            sys.exit(1)

    def post_deploy_check(self):
        """
        Vérifie que le site répond correctement après déploiement.
        Fait une requête HTTP sur l'URL du site.
        """
        import requests
        url = self.config['wordpress']['url']
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log("Post-déploiement OK : site accessible")
                return True
            else:
                log(f"Post-déploiement KO : HTTP {response.status_code}", level="error")
                self.rollback()
                return False
        except Exception as e:
            log(f"Erreur vérification post-déploiement : {e}", level="error")
            self.rollback()
            return False

    def rollback(self):
        """
        Rollback automatique en cas d’erreur.
        Ici, on se contente de logguer, mais tu pourrais restaurer un backup.
        """
        log("Rollback déclenché - intervention requise", level="error")
        # À compléter : restauration automatique depuis le dernier backup

    def close_ssh(self):
        """
        Ferme la connexion SSH proprement.
        """
        if self.ssh_client:
            self.ssh_client.close()
            log("Connexion SSH fermée")

def main():
    deployer = WordPressDeployer()  # Instancie le déployeur
    deployer.sync_files()           # Lance la synchro des fichiers
    success = deployer.post_deploy_check()  # Vérifie le site après déploiement
    deployer.close_ssh()            # Ferme la connexion SSH
    if not success:
        sys.exit(1)
    log("Déploiement terminé avec succès")

if __name__ == "__main__":
    main()

def test_load_config():
    config = load_config("config/production.ini")
    assert "wordpress" in config
