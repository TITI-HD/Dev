Checklist serveur (actions à faire sur le serveur cible avant première utilisation)

    Créer utilisateur wp-deploy (sans sudo ou avec permissions strictes).

    mkdir -p /var/www/html && chown -R www-data:www-data /var/www/html

    Ajouter clé publique PROD_SSH_PUB dans /home/wp-deploy/.ssh/authorized_keys.

    Installer wp-cli, PHP, MySQL/MariaDB, fail2ban, ufw.

    Configurer wp-cli (si besoin) et s’assurer que l’utilisateur wp-deploy peut exécuter wp (ou exécuter sudo -u www-data wp … avec sudoers minimal).

    Mettre en place rotatation des logs, monitoring CPU (Node exporter / Prometheus si souhaité).

    Installer lz4 et rsync sur le serveur.


Comment les utiliser ?

    Les scripts doivent être déposés avec les bons droits dans /opt/wordpress-scripts/.

    Le playbook Ansible s’assure de copier ces fichiers.

    Le service systemd démarre le security_monitor.py --monitor en tâche de fond.

    Le script backup_restore.py peut être appelé manuellement ou via un cron/job GitHub Actions.



    Notes importantes :

    Deinir la variable d’environnement SSH_KEY_PATH pointant vers ma clé privée SSH, pour authentification sécurisée.

    La synchronisation utilise rsync avec options -az --delete --partial pour copier uniquement ce qui a changé.

    En cas d’échec, un rollback minimal est déclenché (à améliorer selon besoin).

    Le post-déploiement vérifie que le site répond HTTP 200 (tu peux ajouter plus de tests).





    CI-CD.yml:
            Explications :

    Jobs séquencés : build-and-test avant deploy.

    Cache pip pour accélérer l’installation.

    Variables secrètes injectées via secrets GitHub.

    Déploiement via deploy.py avec clé SSH privée.

    Vérification post-déploiement en ligne de commande Python.

    À adapter selon les noms, URLs, et secrets spécifiques.


    backup-monitor.yml:
            Points importants :

    Le workflow s’exécute toutes les 5 minutes selon la planification CRON.

    Installer l’environnement Python et dépendances.

    Exécuter la sauvegarde via backup_restore.py backup.

    Lancer le monitoring continu (le script est conçu pour tourner en boucle).

    Variables sensibles injectées via secrets GitHub (AWS et Slack).

    possible d'ajuster la fréquence dans la clé cron.*



    pentest.yml:
                Explications :

    Schedule : scan quotidien automatisé à 3h du matin + déclenchement manuel possible.

    Installation WPScan CLI via Ruby gem.

    Scan ciblé avec token API sécurisé (stocké dans secrets).

    Sortie JSON sauvegardée comme artifact pour analyse.

    Échec du job si vulnérabilités détectées (grâce à jq pour parser JSON).



    