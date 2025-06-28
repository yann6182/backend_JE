@echo off
REM Script de diagnostic pour l'import SharePoint DPGF
echo ===================================================
echo  Diagnostic des variables d'environnement SharePoint
echo ===================================================
echo.

REM Vérifier que Python est installé
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [31mPython n'est pas installé ou n'est pas dans le PATH.[0m
    echo Installez Python depuis https://www.python.org/downloads/
    exit /b 1
)

REM Vérifier que les dépendances sont installées
echo Vérification des dépendances...
pip install -r requirements_sharepoint.txt >nul 2>&1

echo.
echo 1. Diagnostic des variables d'environnement
echo -------------------------------------------
python scripts\import_sharepoint_dpgf.py --debug-env

echo.
echo 2. Diagnostic de la connexion SharePoint
echo ---------------------------------------
python scripts\import_sharepoint_dpgf.py --list-drives

echo.
echo 3. Test de listage des fichiers (dry-run)
echo ---------------------------------------
python scripts\import_sharepoint_dpgf.py --dry-run

echo.
echo ===================================================
echo  Fin du diagnostic
echo ===================================================
pause
