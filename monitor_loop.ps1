while ($true) {
    Write-Host "Démarrage de la surveillance - $(Get-Date)"
    python monitor_simple.py
    Write-Host "Prochaine exécution dans 30 minutes..."
    Start-Sleep -Seconds 1800
}