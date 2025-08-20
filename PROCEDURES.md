# Procédures de Sauvegarde et Restauration WordPress.com

## 📋 Overview

Ce système permet la sauvegarde et restauration de contenu WordPress.com via ses APIs publiques.

## 🔧 Configuration Requise

### Variables d'Environnement

| Variable | Description | Requise |
|----------|-------------|---------|
| `SITE_URL` | URL du site WordPress.com | Oui |
| `GPG_RECIPIENT` | Clé GPG pour chiffrement | Non |
| `GPG_PASSPHRASE` | Passphrase GPG | Si chiffrement |
| `RETENTION_DAYS` | Jours de rétention (défaut: 7) | Non |

### Secrets GitHub

- `GPG_PRIVATE_KEY`: Clé privée GPG pour déchiffrement
- `GPG_PASSPHRASE`: Passphrase pour la clé GPG
- `TWILIO_*`: Configuration pour notifications WhatsApp

## 🔄 Procédure de Sauvegarde

1. **Planification**: Exécution quotidienne à 2h00 UTC
2. **Contenu sauvegardé**:
   - Page d'accueil (HTML)
   - Flux RSS
   - Commentaires (RSS)
   - API Posts (JSON)
   - API Pages (JSON)
   - API Categories (JSON)
   - API Tags (JSON)
   - Export de contenu (XML)

3. **Chiffrement**: Optionnel avec GPG
4. **Rotation**: Suppression automatique après `RETENTION_DAYS`

## 🚀 Procédure de Restauration

### Restauration Automatique (Staging)

1. Déclencher manuellement le workflow
2. Sélectionner l'environnement "staging"
3. Le workflow restaure la dernière sauvegarde

### Restauration Manuelle

1. Télécharger l'artefact de sauvegarde
2. Extraire les fichiers
3. Utiliser le script de restauration:
   ```bash
   export BACKUP_DIR="chemin/vers/sauvegardes"
   export RESTORE_DIR="chemin/vers/restauration"
   export GPG_PASSPHRASE="votre_passphrase"
   python restore.py