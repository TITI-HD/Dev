# Créer et exécuter le script de diagnostic
$diagnosticContent = @'
Write-Host "🔍 Diagnostic du système de surveillance WordPress"

# 1. Test de connexion Internet
Write-Host "`n🌐 Test de connexion Internet..."
Test-NetConnection -ComputerName "google.com" -Port 80

# 2. Test du site WordPress
Write-Host "`n🔗 Test du site WordPress..."
try {
    $response = Invoke-WebRequest -Uri "https://oupssecuretest.wordpress.com" -Method Head -ErrorAction Stop
    Write-Host "✅ Site accessible - Code: $($response.StatusCode)"
} catch {
    Write-Host "❌ Site inaccessible: $($_.Exception.Message)"
}

# 3. Vérification des dossiers
Write-Host "`n📁 Vérification des dossiers..."
if (Test-Path "backups") {
    Write-Host "✅ Dossier backups existe"
    Get-ChildItem "backups/"
} else {
    Write-Host "❌ Dossier backups n'existe pas"
}

# 4. Vérification des dépendances Python
Write-Host "`n🐍 Vérification des dépendances..."
python -c "import requests; print('✅ Requests installé'); import twilio; print('✅ Twilio installé')"

# 5. Test des variables d'environnement
Write-Host "`n⚙️ Variables d'environnement..."
Get-ChildItem Env: | Where-Object Name -Like "*TWILIO*" | Format-Table Name, Value
Get-ChildItem Env: | Where-Object Name -Like "*SMTP*" | Format-Table Name, Value
'@
Set-Content -Path "diagnostic.ps1" -Value $diagnosticContent

# Autoriser l'exécution de scripts PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Exécuter le diagnostic
.\diagnostic.ps1