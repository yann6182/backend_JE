@echo off
REM Script de recherche des fichiers DPGF dans SharePoint
echo =============================================
echo  Recherche des drives SharePoint avec DPGF
echo =============================================

REM Vérifier que Python est installé
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [31mPython n'est pas installé ou n'est pas dans le PATH.[0m
    echo Installez Python depuis https://www.python.org/downloads/
    exit /b 1
)

REM Vérifier que les dépendances sont installées
echo Vérification des dépendances...
pip install msal requests python-dotenv >nul 2>&1

REM Exécuter le script de recherche
python scripts\find_dpgf_drives.py

echo.
echo =============================================
echo  Fin de la recherche
echo =============================================
echo.
echo Pour mettre à jour votre configuration:
echo 1. Modifiez le fichier .env avec le bon Drive ID
echo 2. Vérifiez les permissions dans le portail Azure
echo    (voir GUIDE_PERMISSIONS_AZURE.md)
echo.
pause
