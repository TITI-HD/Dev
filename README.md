# Supervision WordPress.com

Ce projet permet de superviser la disponibilité et la sécurité d’un site WordPress.com via GitHub Actions.

## Fonctionnalités
- Vérification automatique de la disponibilité HTTP du site
- Scan de sécurité WPScan (API)
- Résultats consultables dans l’onglet Actions de GitHub

## Utilisation

1. Ajoute le secret `WPSCAN_API` dans les paramètres GitHub du dépôt.
2. Modifie l’URL du site dans `.github/workflows/ci-cd.yml` si besoin.
3. Pousse le projet sur GitHub.
4. Lance le workflow depuis l’onglet Actions.

## Limites

- Pas de déploiement, backup ou monitoring de fichiers (WordPress.com ne le permet pas).
- Pour un WordPress auto-hébergé, adapte le pipeline et les scripts Python.