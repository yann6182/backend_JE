@echo off
REM Script pour importer les fichiers DPGF depuis SharePoint
echo ======================================
echo Import des DPGF depuis SharePoint
echo ======================================

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
echo Démarrage de l'import depuis SharePoint...
echo Appuyez sur CTRL+C pour annuler l'opération.
echo.

REM Exécuter le script d'import
python scripts\import_sharepoint_dpgf.py %*

echo.
if %ERRORLEVEL% EQU 0 (
    echo [32mImport terminé avec succès![0m
) else (
    echo [31mDes erreurs se sont produites lors de l'import.[0m
    echo Consultez les messages ci-dessus pour plus de détails.
)

pause
