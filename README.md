# Supervision et Sauvegarde WordPress.com

Ce projet permet de superviser la disponibilité, la sécurité et d'effectuer des sauvegardes automatiques d'un site WordPress.com via GitHub Actions.

## Fonctionnalités
<<<<<<< HEAD
- Surveillance automatique de la disponibilité HTTP du site
- Scan de sécurité via Bandit
- Sauvegarde automatique du contenu public (RSS, API, pages)
- Alertes par email et WhatsApp en cas de problème
- Archivage des sauvegardes dans les artefacts GitHub
=======
- Vérification automatique de la disponibilité HTTP du site.
- Scan de sécurité via l'API WPScan (détection de la version WordPress et interrogation pour vulnérabilités).
- Envoi d'alertes par e-mail en cas de problème (indisponibilité ou vulnérabilités détectées).
- Résultats consultables dans l’onglet Actions de GitHub.
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874

## Utilisation

1. Ajoutez les secrets suivants dans les paramètres GitHub du dépôt :
<<<<<<< HEAD
   - `ALERT_EMAIL` : L'adresse e-mail pour les alertes
   - `SMTP_*` : Configuration SMTP pour l'envoi d'emails
   - `TWILIO_*` : Configuration Twilio pour les notifications WhatsApp

2. Configurez les variables d'environnement :
   - `SITE_URL` : URL de votre site WordPress.com

3. Le workflow s'exécute automatiquement selon la planification ou manuellement

## Planification
- Surveillance : Toutes les 6 heures
- Sauvegarde : Tous les jours à 2h du matin

## Limitations WordPress.com
- Accès limité aux APIs publiques
- Pas d'accès direct à la base de données
- Sauvegarde limitée au contenu public

    ✅ Sécurisation : Scan de sécurité avec Bandit, surveillance continue

    ✅ Sauvegarde : Script de sauvegarde du contenu public avec compression et vérification d'intégrité

    ✅ Restauration : Archivage des sauvegardes dans les artefacts GitHub pour restauration manuelle

    ✅ CI/CD : Workflows GitHub Actions pour automatisation

    ✅ Monitoring : Alertes temps réel par email et WhatsApp

    ✅ Documentation : README mis à jour avec instructions complètes

Les limitations de WordPress.com sont correctement prises en compte, et la solution propose une approche maximisant les possibilités offertes par les APIs publiques.
=======
   - `WPSCAN_API` : Votre clé API WPScan (obtenue sur https://wpscan.com/register).
   - `ALERT_EMAIL` : L'adresse e-mail pour les alertes.
   - `SMTP_USER` : L'utilisateur SMTP (par exemple, votre adresse Gmail).
   - `SMTP_PASS` : Le mot de passe SMTP (par exemple, un mot de passe d'application pour Gmail).
2. Modifiez l’URL du site dans `.github/workflows/monitor.yml` si nécessaire (par défaut : https://oupssecuretest.wordpress.com).
3. Poussez le projet sur GitHub.
4. Lancez le workflow depuis l’onglet Actions ou attendez l'exécution planifiée.

## Limites
- Pas de déploiement, backup ou monitoring de fichiers (WordPress.com ne le permet pas).
- Le scan se limite à la version WordPress core détectée publiquement ; pour les plugins/thèmes, des adaptations supplémentaires seraient nécessaires.
- Pour un WordPress auto-hébergé, adaptez le pipeline et les scripts Python.

## Dépendances
- Voir `requirements.txt` pour les bibliothèques Python requises.
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
