#!/bin/bash
<<<<<<< HEAD
# Script de test de restauration complet

echo "🧪 Démarrage des tests de restauration..."

# Configuration
BACKUP_DIR="test-backups"
RESTORE_DIR="test-restore"
TEST_DATA_DIR="test-data"

# Nettoyer les anciens tests
rm -rf "$BACKUP_DIR" "$RESTORE_DIR" "$TEST_DATA_DIR"

# Créer des données de test
mkdir -p "$TEST_DATA_DIR"
echo "<html><body>Test homepage</body></html>" > "$TEST_DATA_DIR/homepage.html"
echo '{"posts": [{"id": 1, "title": "Test Post"}]}' > "$TEST_DATA_DIR/api_posts.json"

# Créer une sauvegarde de test
mkdir -p "$BACKUP_DIR"
timestamp=$(date +%Y%m%d_%H%M%S)

for item in "$TEST_DATA_DIR"/*; do
    filename=$(basename "$item")
    cp "$item" "$BACKUP_DIR/${filename%.*}_$timestamp"
    
    # Créer des métadonnées
    meta=$(cat << EOF
{
    "url": "https://example.com/$filename",
    "date": "$(date -Iseconds)",
    "hash": "test123",
    "size": $(wc -c < "$item"),
    "encrypted": false
}
EOF
    )
    echo "$meta" > "$BACKUP_DIR/${filename%.*}_$timestamp.meta.json"
done

# Exécuter le script de restauration
echo "🔧 Configuration de l'environnement pour le test..."
export BACKUP_DIR="$BACKUP_DIR"
export RESTORE_DIR="$RESTORE_DIR"
export GPG_PASSPHRASE=""

echo "🔄 Exécution de la restauration..."
python restore.py

# Vérifier les résultats
echo "📊 Vérification des résultats..."
if [ -d "$RESTORE_DIR" ] && [ "$(ls -A "$RESTORE_DIR")" ]; then
    echo "✅ Test de restauration réussi"
    echo "📁 Contenu restauré:"
    find "$RESTORE_DIR" -type f
    
    # Vérifier le rapport
    if [ -f "$RESTORE_DIR/restore_report.json" ]; then
        echo "📋 Rapport de restauration:"
        cat "$RESTORE_DIR/restore_report.json"
    fi
    
    # Nettoyer
    rm -rf "$BACKUP_DIR" "$RESTORE_DIR" "$TEST_DATA_DIR"
    exit 0
else
    echo "❌ Échec du test de restauration"
    rm -rf "$BACKUP_DIR" "$RESTORE_DIR" "$TEST_DATA_DIR"
=======
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
>>>>>>> f187b1211e2b27bf3d01b368312f0f2bba2b0874
    exit 1
fi