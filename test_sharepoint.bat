@echo off
REM Script de diagnostic pour la connexion SharePoint
echo =============================================
echo  Test de connexion SharePoint
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

REM Exécuter le script de diagnostic
python scripts\test_sharepoint_connection.py

echo.
echo =============================================
echo  Fin du diagnostic
echo =============================================
pause
