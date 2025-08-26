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