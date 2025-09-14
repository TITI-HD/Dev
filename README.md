3
Ce projet utilise GitHub Actions pour superviser la disponibilité, la sécurité et effectuer des sauvegardes automatiques d'un site WordPress.com. Il génère des rapports détaillés et envoie des alertes par email en cas de problème.
Fonctionnalités
 * Surveillance automatique : Vérification de la disponibilité HTTP et de l'état du certificat SSL.
 * Scan de sécurité : Utilisation de WPScan pour détecter les versions et vulnérabilités connues. Le script identifie également des patterns suspects comme eval ou base64_decode dans le contenu du site.
 * Sauvegarde automatique : Archivage du contenu public (pages, RSS, commentaires) dans des artefacts GitHub.
 * Génération de rapports : Création de rapports détaillés aux formats TXT et HTML.
 * Notifications : Envoi d'alertes par email (SMTP) en cas d'incidents critiques ou moyens.
 * Automatisation : Exécution planifiée via GitHub Actions, ou en mode unique via le script monitor.py.
Limitations sur WordPress.com
Gardez à l'esprit que ce projet est conçu pour une plateforme gérée. Les fonctionnalités sont limitées par l'accès public à l'API de WordPress.com.
 * Accès à l'API : Le script ne peut interagir qu'avec les APIs publiques.
 * Pas d'accès direct : Il est impossible d'accéder directement à la base de données ou aux fichiers sur le serveur.
 * Sauvegarde partielle : La sauvegarde se limite au contenu public. Les thèmes et les plugins ne peuvent pas être scannés ou sauvegardés automatiquement.
> Note : Pour un site WordPress auto-hébergé, le script et le workflow devraient être adaptés pour tirer parti d'un accès complet à la base de données et aux fichiers.
> 
Prérequis
Dépendances système
 * Python version 3.11 ou supérieure.
 * pip
 * Git
Dépendances Python
Installez les bibliothèques requises en utilisant le fichier requirements.txt :
pip install -r requirements.txt

Si le fichier n'est pas disponible, vous pouvez les installer manuellement :
pip install requests schedule python-dateutil python-dotenv

Configuration
Variables d'environnement
Créez un fichier .env.local à la racine du projet et définissez les variables suivantes :
SITE_URL=https://oupssecuretest.wordpress.com
ALERT_EMAIL=ton_email@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ton_email@gmail.com
SMTP_PASS=ton_mot_de_passe_app
MONITOR_DIR=monitor_data
BACKUP_DIR=backups
RESTORE_DIR=restored
LOG_RETENTION_DAYS=30
CHECK_INTERVAL_HOURS=3
USE_EMOJI=1
ANONYMIZE_SAMPLES=1
WPSCAN_API=ta_clef_wpscan

> Attention : Pour Gmail, vous devez utiliser un mot de passe d'application pour vous connecter.
> 
Secrets GitHub
Pour sécuriser vos informations sensibles dans GitHub Actions, ajoutez les secrets suivants dans les paramètres de votre dépôt :
 * SMTP_PASS
 * WPSCAN_API (si vous activez les scans WPScan)
Structure du projet
.
├── monitor.py          # Script principal
├── requirements.txt    # Dépendances Python
├── monitor_data/       # Rapports, logs et historique d'incidents
├── backups/            # Fichiers de sauvegarde
├── restored/           # Fichiers de restauration
├── .github/
│   └── workflows/
│       └── monitor.yml # Workflow GitHub Actions
├── .env.local          # Configuration locale
└── README.md

Utilisation
Exécution locale
 * Clonez le dépôt :
   git clone <URL_DU_DEPOT>
cd <REPERTOIRE>

 * Installez les dépendances :
   pip install -r requirements.txt

 * Configurez le fichier .env.local.
 * Lancer le script avec les options suivantes :
   * Pour une exécution unique :
     python monitor.py --once

   * Pour générer uniquement le rapport :
     python monitor.py --report

   * Pour sauvegarder uniquement le contenu :
     python monitor.py --backup

   * Pour restaurer depuis un backup :
     python monitor.py --restore restored/

Exécution planifiée avec GitHub Actions
Le workflow monitor.yml est pré-configuré pour automatiser l'exécution.
 * Fréquence : Le monitoring s'exécute toutes les 3 heures, et un rapport quotidien est généré à 08h30.
 * Artefacts : Les rapports et les sauvegardes sont archivés automatiquement et peuvent être consultés dans l'onglet Actions de votre dépôt GitHub.
Reporting et Sauvegarde
Rapports
 * Rapport TXT : monitor_data/report_YYYYMMDD_HHMMSS.txt
 * Rapport HTML : monitor_data/logs.html
 * Historique des incidents : monitor_data/incident_history.json
Sauvegarde & Restauration
Les sauvegardes du contenu public sont stockées dans le dossier backups/.
Vous pouvez les restaurer manuellement en déplaçant les fichiers vers le dossier restored/ et en utilisant la commande python monitor.py --restore.
Bonnes Pratiques et Avertissements
 * Ne jamais committer vos mots de passe ou secrets dans le code. Utilisez toujours les secrets GitHub.
 * Testez les sauvegardes et les restaurations régulièrement.
 * Vérifiez toujours la validité de vos dépendances et de votre configuration SMTP.
 * Consultez monitor_data/logs.html pour une vue d'ensemble des incidents.
 * Le projet est limité par l'accès public à l'API de WordPress.com.
Développement et Contact
 * Ajouter des fonctionnalités : Modifiez le script monitor.py pour ajouter des patterns de sécurité, des alertes supplémentaires (via Twilio, par exemple) ou pour l'adapter à un site auto-hébergé.
 * Auteur : Daniel Titi
 * Email : danieltiti882@gmail.com
