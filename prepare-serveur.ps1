# Script PowerShell : préparation serveur Linux pour WordPress CI/CD

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerHost,

    [Parameter(Mandatory=$false)]
    [int]$Port = 22,

    [Parameter(Mandatory=$true)]
    [string]$User,

    [Parameter(Mandatory=$true)]
    [string]$PubKeyPath
)

# Vérification de la disponibilité de SSH
function Test-SSH {
    try {
        $null = Get-Command ssh -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

# Vérification de la disponibilité de SCP
function Test-SCP {
    try {
        $null = Get-Command scp -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

if (-not (Test-SSH) -or -not (Test-SCP)) {
    Write-Error "SSH et/ou SCP ne sont pas disponibles. Veuillez installer OpenSSH ou utiliser Git Bash."
    Write-Host "Pour installer OpenSSH, exécutez PowerShell en tant qu'administrateur et tapez:"
    Write-Host "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
    exit 1
}

function Exec-SSH {
    param([string]$Cmd)
    & ssh -p $Port "${User}@${ServerHost}" $Cmd
}

# Le reste du script reste inchangé...
# [Insérez ici le reste de votre script]
# 1. Création utilisateur wp-deploy sans sudo
Exec-SSH "sudo adduser --disabled-password --gecos '' wp-deploy || echo 'Utilisateur wp-deploy existe déjà'"

# 2. Préparer dossier /var/www/html
Exec-SSH "sudo mkdir -p /var/www/html"
Exec-SSH "sudo chown -R www-data:www-data /var/www/html"
Exec-SSH "sudo chmod -R 755 /var/www/html"

# 3. Copier clé publique dans authorized_keys
$TmpRemoteKey = "/tmp/wp_deploy_key.pub"
$expandedPubKeyPath = $PubKeyPath -replace '^~', $HOME
& scp -P $Port "$expandedPubKeyPath" "${User}@${ServerHost}:$TmpRemoteKey"

Exec-SSH @"
sudo -u wp-deploy mkdir -p /home/wp-deploy/.ssh
sudo -u wp-deploy touch /home/wp-deploy/.ssh/authorized_keys
if ! sudo grep -q -f $TmpRemoteKey /home/wp-deploy/.ssh/authorized_keys; then
    sudo cat $TmpRemoteKey >> /home/wp-deploy/.ssh/authorized_keys
fi
sudo rm $TmpRemoteKey
sudo chown -R wp-deploy:wp-deploy /home/wp-deploy/.ssh
sudo chmod 700 /home/wp-deploy/.ssh
sudo chmod 600 /home/wp-deploy/.ssh/authorized_keys
"@

# 4. Installer paquets essentiels
Exec-SSH "sudo apt update"
Exec-SSH "sudo apt upgrade -y"
Exec-SSH "sudo apt install -y php php-cli php-mysql php-curl php-xml php-mbstring php-zip php-gd php-intl mariadb-client mariadb-server fail2ban ufw lz4 rsync curl"

# 5. Installer WP-CLI
Exec-SSH "curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar"
Exec-SSH "php wp-cli.phar --info"
Exec-SSH "chmod +x wp-cli.phar"
Exec-SSH "sudo mv wp-cli.phar /usr/local/bin/wp"

# 6. Configuration sudoers pour wp-deploy
Exec-SSH "echo 'wp-deploy ALL=(www-data) NOPASSWD: /usr/local/bin/wp' | sudo tee /etc/sudoers.d/wp-deploy-wpcli"
Exec-SSH "sudo chmod 440 /etc/sudoers.d/wp-deploy-wpcli"

# 7. Configurer et activer UFW
Exec-SSH "sudo ufw allow $Port/tcp"
Exec-SSH "sudo ufw allow 80/tcp"
Exec-SSH "sudo ufw allow 443/tcp"
Exec-SSH "sudo ufw --force enable"
Exec-SSH "sudo ufw status verbose"

Write-Host "Préparation du serveur terminée. Testez la connexion SSH et WP-CLI."