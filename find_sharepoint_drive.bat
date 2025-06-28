@echo off
REM Script pour lister les drives SharePoint disponibles et aider à la configuration
echo =============================================
echo Diagnostic SharePoint pour l'import de DPGF
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
pip install -r requirements_sharepoint.txt >nul 2>&1

REM Exécuter le script avec l'option --list-drives
echo Recherche des drives SharePoint disponibles...
echo.
python scripts\import_sharepoint_dpgf.py --list-drives

echo.
echo =============================================
echo Pour lister les fichiers sans les importer :
echo python scripts\import_sharepoint_dpgf.py --dry-run
echo.
echo Pour importer les fichiers :
echo python scripts\import_sharepoint_dpgf.py
echo.
echo Pour tester avec un dossier spécifique :
echo python scripts\import_sharepoint_dpgf.py --folder "NomDuDossier"
echo =============================================
pause
