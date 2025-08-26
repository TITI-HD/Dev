# Définir le chemin du dossier de sauvegarde
$backupDir = "sauvegarde des épreuves"

Write-Host "Vérification du dossier de sauvegarde..."

# Créer le dossier s'il n'existe pas
if (-not (Test-Path $backupDir)) {
    Write-Host "Création du dossier: $backupDir"
    try {
        New-Item -ItemType Directory -Path $backupDir -Force
        Write-Host "✅ Dossier créé avec succès"
    } catch {
        Write-Host "❌ Erreur lors de la création du dossier: $($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Host "✅ Le dossier existe déjà"
}

# Vérifier que le dossier a été créé
if (-not (Test-Path $backupDir)) {
    Write-Host "❌ Le dossier n'a pas pu être créé"
    exit 1
}

# Créer un fichier de test si le dossier est vide
$files = Get-ChildItem $backupDir
if ($files.Count -eq 0) {
    Write-Host "Création d'un fichier de test..."
    try {
        "Ceci est un fichier de sauvegarde de test" | Out-File "$backupDir\test_sauvegarde.txt" -Encoding UTF8
        Write-Host "✅ Fichier de test créé"
    } catch {
        Write-Host "❌ Erreur lors de la création du fichier: $($_.Exception.Message)"
        exit 1
    }
}

# Afficher les fichiers
Write-Host "`nFichiers de sauvegarde créés:"
Get-ChildItem $backupDir | Format-Table Name, Length, LastWriteTime

# Compter les fichiers
$count = (Get-ChildItem $backupDir).Count
if ($count -gt 0) {
    Write-Host "✅ Test de sauvegarde réussi ($count fichiers trouvés)"
} else {
    Write-Host "❌ Échec du test de sauvegarde"
    exit 1
}