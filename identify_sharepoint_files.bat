@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo   IDENTIFICATION FICHIERS DPGF - SHAREPOINT
echo ===============================================
echo.

:: Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou n'est pas dans le PATH
    echo    Veuillez installer Python 3.8+ depuis https://python.org
    pause
    exit /b 1
)

:: Vérifier si le script existe
if not exist "scripts\identify_relevant_files_sharepoint.py" (
    echo ❌ Script non trouvé: scripts\identify_relevant_files_sharepoint.py
    echo    Assurez-vous d'être dans le bon répertoire
    pause
    exit /b 1
)

:: Vérifier la présence du fichier .env
if not exist ".env" (
    echo ❌ Fichier .env manquant
    echo    Veuillez configurer vos variables d'environnement SharePoint dans le fichier .env
    echo    Variables requises: TENANT_ID, CLIENT_ID, CLIENT_SECRET, GRAPH_DRIVE_ID
    pause
    exit /b 1
)

:: Initialiser le dossier par défaut
if not defined SHAREPOINT_FOLDER set SHAREPOINT_FOLDER=/Documents partages

:MENU
echo.
echo 📁 Dossier SharePoint actuel: %SHAREPOINT_FOLDER%
echo.
echo Que souhaitez-vous faire ?
echo.
echo 1. 🧪 Tester l'accès SharePoint (10 premiers fichiers)
echo 2. 🔍 Scan rapide (identification seulement)
echo 3. 📊 Scan approfondi (avec analyse détaillée)
echo 4. ⬇️  Télécharger les fichiers identifiés
echo 5. 📂 Changer le dossier SharePoint
echo 6. ❌ Quitter
echo.
set /p choice="Votre choix (1-6): "

if "%choice%"=="1" goto TEST_ACCESS
if "%choice%"=="2" goto SCAN_QUICK
if "%choice%"=="3" goto SCAN_DEEP
if "%choice%"=="4" goto DOWNLOAD
if "%choice%"=="5" goto CHANGE_FOLDER
if "%choice%"=="6" goto EXIT
echo Choix invalide, veuillez réessayer.
goto MENU

:TEST_ACCESS
echo.
echo 🧪 Test d'accès au SharePoint...
echo    Dossier: %SHAREPOINT_FOLDER%
echo.
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --folder "%SHAREPOINT_FOLDER%" --test-access
echo.
pause
goto MENU

:SCAN_QUICK
echo.
echo 🔍 Scan rapide en cours...
echo    Dossier: %SHAREPOINT_FOLDER%
echo    Mode: Identification rapide
echo.
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --folder "%SHAREPOINT_FOLDER%" --mode quick --output identified_files_quick.xlsx
echo.
if exist "identified_files_quick.xlsx" (
    echo ✅ Rapport généré: identified_files_quick.xlsx
    set /p open="Ouvrir le rapport ? (o/n): "
    if /i "!open!"=="o" start identified_files_quick.xlsx
)
pause
goto MENU

:SCAN_DEEP
echo.
echo 📊 Scan approfondi en cours...
echo    Dossier: %SHAREPOINT_FOLDER%
echo    Mode: Analyse détaillée (plus long)
echo.
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --folder "%SHAREPOINT_FOLDER%" --mode deep --output identified_files_deep.xlsx
echo.
if exist "identified_files_deep.xlsx" (
    echo ✅ Rapport généré: identified_files_deep.xlsx
    set /p open="Ouvrir le rapport ? (o/n): "
    if /i "!open!"=="o" start identified_files_deep.xlsx
)
pause
goto MENU

:DOWNLOAD
echo.
echo ⬇️ Téléchargement des fichiers...
echo    Dossier: %SHAREPOINT_FOLDER%
echo    Destination: downloaded_dpgf\
echo.
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --folder "%SHAREPOINT_FOLDER%" --mode download --download-folder downloaded_dpgf
echo.
if exist "downloaded_dpgf" (
    echo ✅ Fichiers téléchargés dans: downloaded_dpgf\
    set /p open="Ouvrir le dossier ? (o/n): "
    if /i "!open!"=="o" explorer downloaded_dpgf
)
pause
goto MENU

:CHANGE_FOLDER
echo.
echo 📂 Dossier SharePoint actuel: %SHAREPOINT_FOLDER%
echo.
echo Exemples de dossiers courants:
echo   - /Documents partages
echo   - /Documents partages/Projets
echo   - /Documents partages/DPGF
echo.
set /p new_folder="Nouveau dossier SharePoint: "
if not "%new_folder%"=="" set SHAREPOINT_FOLDER=%new_folder%
echo ✅ Dossier changé pour: %SHAREPOINT_FOLDER%
echo.
pause
goto MENU

:EXIT
echo.
echo 👋 Au revoir !
echo.
pause
exit /b 0
