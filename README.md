# Supervision WordPress.com

Ce projet permet de superviser la disponibilité et la sécurité d’un site WordPress.com via GitHub Actions.

## Fonctionnalités
- Vérification automatique de la disponibilité HTTP du site.
- Scan de sécurité via l'API WPScan (détection de la version WordPress et interrogation pour vulnérabilités).
- Envoi d'alertes par e-mail en cas de problème (indisponibilité ou vulnérabilités détectées).
- Résultats consultables dans l’onglet Actions de GitHub.

## Utilisation

1. Ajoutez les secrets suivants dans les paramètres GitHub du dépôt :
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