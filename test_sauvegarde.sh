#!/bin/bash

echo "Fichiers de sauvegarde créés:"
ls -la "sauvegarde des épreuves/"
count=$(ls -1 "sauvegarde des épreuves/" | wc -l)
if [ $count -gt 0 ]; then
    echo "- Test de sauvegarde réussi"
else
    echo "Échec du test de sauvegarde"
    exit 1
fi

# Créer un fichier de test si le répertoire est vide
if [ ! -f "sauvegarde des épreuves/test.txt" ]; then
    echo "Création d'un fichier de test"
    echo "contenu de test" > "sauvegarde des épreuves/test.txt"
fi

# test_server_config.ps1
# Script de test pour la configuration serveur

# Test de connexion SSH
function Test-SSHConnection {
    param($Host, $Port, $User)
    try {
        $result = ssh -p $Port ${User}@${Host} "echo 'SSH connection successful'"
        if ($result -like "*successful*") {
            Write-Host "✅ Connexion SSH réussie"
            return $true
        }
    } catch {
        Write-Host "❌ Échec de connexion SSH: $($_.Exception.Message)"
        return $false
    }
}

# Test des services installés
function Test-Services {
    param($Host, $Port, $User)
    $services = @("php", "mysql", "ufw", "fail2ban")
    
    foreach ($service in $services) {
        try {
            $result = ssh -p $Port ${User}@${Host} "which $service"
            if ($result) {
                Write-Host "✅ Service $service installé"
            } else {
                Write-Host "❌ Service $service manquant"
                return $false
            }
        } catch {
            Write-Host "❌ Erreur vérification service $service : $($_.Exception.Message)"
            return $false
        }
    }
    return $true
}

# Test des permissions
function Test-Permissions {
    param($Host, $Port, $User)
    $paths = @("/var/www/html", "/home/wp-deploy/.ssh")
    
    foreach ($path in $paths) {
        try {
            $result = ssh -p $Port ${User}@${Host} "ls -la $path"
            Write-Host "📁 Permissions pour $path :"
            Write-Host $result
        } catch {
            Write-Host "❌ Erreur vérification permissions $path : $($_.Exception.Message)"
            return $false
        }
    }
    return $true
}

# Exécution des tests
$Host = "votre-serveur.com"
$Port = 22
$User = "utilisateur-test"

Write-Host "🧪 Début des tests de configuration serveur..."

$test1 = Test-SSHConnection -Host $Host -Port $Port -User $User
$test2 = Test-Services -Host $Host -Port $Port -User $User
$test3 = Test-Permissions -Host $Host -Port $Port -User $User

if ($test1 -and $test2 -and $test3) {
    Write-Host "🎉 Tous les tests serveur passés"
} else {
    Write-Host "❌ Certains tests serveur ont échoué"
    exit 1
}

@echo off
echo Fichiers de sauvegarde créés:
dir "sauvegarde des épreuves\"
for /f %%i in ('dir "sauvegarde des épreuves\" /b ^| find /c /v ""') do set count=%%i
if %count% GTR 0 (
    echo - Test de sauvegarde réussi
) else (
    echo Échec du test de sauvegarde
    exit /b 1
)