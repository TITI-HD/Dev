# Script PowerShell : préparation serveur Linux pour WordPress CI/CD
# Usage : ./prepare-serveur.ps1 -Host <IP> -Port <SSH Port> -User <utilisateur SSH> -PubKeyPath <chemin clé publique>

param(
    [Parameter(Mandatory=$true)]
    [string]$Host,

    [Parameter(Mandatory=$false)]
    [int]$Port = 22,

    [Parameter(Mandatory=$true)]
    [string]$User,

    [Parameter(Mandatory=$true)]
    [string]$PubKeyPath
)

function Exec-SSH {
    param(
        [string]$Cmd
    )
    $sshCommand = "ssh -p $Port $User@$Host `"$Cmd`""
    Write-Host "Exécution SSH: $Cmd"
    Invoke-Expression $sshCommand
}

# 1. Création utilisateur wp-deploy sans sudo
Exec-SSH "sudo adduser --disabled-password --gecos '' wp-deploy || echo 'Utilisateur wp-deploy existe déjà'"

# 2. Préparer dossier /var/www/html
Exec-SSH "sudo mkdir -p /var/www/html && sudo chown -R www-data:www-data /var/www/html && sudo chmod -R 755 /var/www/html"

# 3. Copier clé publique dans authorized_keys
# On copie la clé publique locale vers un fichier temporaire sur le serveur, puis on l’ajoute à authorized_keys
$TmpRemoteKey = "/tmp/wp_deploy_key.pub"
scp -P $Port $PubKeyPath "$User@$Host:$TmpRemoteKey"
Exec-SSH @"
mkdir -p /home/wp-deploy/.ssh
touch /home/wp-deploy/.ssh/authorized_keys
grep -qxFf $TmpRemoteKey /home/wp-deploy/.ssh/authorized_keys || cat $TmpRemoteKey >> /home/wp-deploy/.ssh/authorized_keys
rm $TmpRemoteKey
chown -R wp-deploy:wp-deploy /home/wp-deploy/.ssh
chmod 700 /home/wp-deploy/.ssh
chmod 600 /home/wp-deploy/.ssh/authorized_keys
"@

# 4. Installer paquets essentiels
Exec-SSH @"
sudo apt update && sudo apt upgrade -y
sudo apt install -y php php-cli php-mysql php-curl php-xml php-mbstring php-zip php-gd php-intl mariadb-client mariadb-server fail2ban ufw lz4 rsync curl
"@

# 5. Installer WP-CLI
Exec-SSH @"
curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
php wp-cli.phar --info
chmod +x wp-cli.phar
sudo mv wp-cli.phar /usr/local/bin/wp
"@

# 6. Configuration sudoers pour wp-deploy (exécution WP-CLI en tant que www-data)
Exec-SSH @"
sudo bash -c 'echo \"wp-deploy ALL=(www-data) NOPASSWD: /usr/local/bin/wp\" > /etc/sudoers.d/wp-deploy-wpcli'
sudo chmod 440 /etc/sudoers.d/wp-deploy-wpcli
"@

# 7. Configurer et activer UFW
Exec-SSH @"
sudo ufw allow $Port/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
"@

Write-Host "Préparation du serveur terminée. Testez la connexion SSH et WP-CLI."
