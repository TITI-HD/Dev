#!/bin/bash
# test_restore.sh
echo "🧪 Test de restauration..."

# Créer un scénario de restauration
BACKUP_SOURCE="test-backups"
RESTORE_TARGET="test-restore"

# Créer un dossier de restauration
mkdir -p $RESTORE_TARGET

# Simuler une restauration en copiant les backups
if [ -d "$BACKUP_SOURCE" ] && [ "$(ls -A $BACKUP_SOURCE)" ]; then
    echo "📦 Restauration des sauvegardes..."
    cp -r $BACKUP_SOURCE/* $RESTORE_TARGET/
    
    # Vérifier la restauration
    if [ "$(ls -A $RESTORE_TARGET)" ]; then
        echo "✅ Test de restauration réussi"
        echo "Fichiers restaurés:"
        ls -la $RESTORE_TARGET/
    else
        echo "❌ Échec de la restauration"
        exit 1
    fi
else
    echo "❌ Aucune sauvegarde à restaurer"
    exit 1
fi