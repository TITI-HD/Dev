#!/bin/bash
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
    exit 1
fi