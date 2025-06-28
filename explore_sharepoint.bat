@echo off
REM Script pour explorer les drives et dossiers SharePoint
echo =============================================
echo  Exploration des drives SharePoint
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

echo.
echo 1) Lister tous les drives disponibles
echo 2) Explorer le drive configuré (racine)
echo 3) Explorer un dossier spécifique
echo 4) Quitter
echo.

choice /C 1234 /N /M "Choisissez une option (1-4): "

if %ERRORLEVEL% EQU 1 (
    echo.
    echo Listage des drives disponibles...
    python scripts\explore_sharepoint_drives.py --list-drives
) else if %ERRORLEVEL% EQU 2 (
    echo.
    echo Exploration du drive configuré (racine)...
    python scripts\explore_sharepoint_drives.py
) else if %ERRORLEVEL% EQU 3 (
    echo.
    set /p folder="Entrez le nom du dossier à explorer: "
    echo Exploration du dossier %folder%...
    python scripts\explore_sharepoint_drives.py --folder "%folder%"
) else (
    exit /b 0
)

echo.
echo =============================================
echo  Fin de l'exploration
echo =============================================
pause
