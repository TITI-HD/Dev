# Supervision et Sauvegarde WordPress.com

Ce projet permet de superviser la disponibilité, la sécurité et d'effectuer des sauvegardes automatiques d'un site WordPress.com via GitHub Actions.

## Fonctionnalités
- Surveillance automatique de la disponibilité HTTP du site
- Scan de sécurité via Bandit
- Sauvegarde automatique du contenu public (RSS, API, pages)
- Alertes par email et WhatsApp en cas de problème
- Archivage des sauvegardes dans les artefacts GitHub

## Utilisation

1. Ajoutez les secrets suivants dans les paramètres GitHub du dépôt :
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