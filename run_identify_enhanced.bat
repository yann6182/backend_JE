@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo   IDENTIFICATION AMÉLIORÉE FICHIERS DPGF
echo ===============================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python non trouvé
    pause
    exit /b 1
)

:: Vérifier le script
if not exist "scripts\identify_relevant_files_sharepoint.py" (
    echo ❌ Script non trouvé: scripts\identify_relevant_files_sharepoint.py
    pause
    exit /b 1
)

:: Vérifier .env
if not exist ".env" (
    echo ❌ Fichier .env manquant
    echo    Configurez vos variables SharePoint (TENANT_ID, CLIENT_ID, etc.)
    pause
    exit /b 1
)

:MENU
echo.
echo 🎯 Que souhaitez-vous faire ?
echo.
echo 1. 🧪 Test d'accès SharePoint rapide
echo 2. 🔍 Scan rapide (5 fichiers max)
echo 3. 📊 Scan avec rapports multi-formats
echo 4. ⬇️ Scan + téléchargement + import auto
echo 5. 🔧 Scan personnalisé
echo 6. 📝 Démonstration complète
echo 7. ❌ Quitter
echo.
set /p choice="Votre choix (1-7): "

if "%choice%"=="1" goto TEST_ACCESS
if "%choice%"=="2" goto QUICK_SCAN
if "%choice%"=="3" goto MULTI_FORMAT
if "%choice%"=="4" goto FULL_WORKFLOW
if "%choice%"=="5" goto CUSTOM_SCAN
if "%choice%"=="6" goto DEMO
if "%choice%"=="7" goto EXIT
echo Choix invalide, veuillez réessayer.
goto MENU

:TEST_ACCESS
echo.
echo 🧪 Test d'accès SharePoint...
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --test-access
pause
goto MENU

:QUICK_SCAN
echo.
echo 🔍 Scan rapide limité à 5 fichiers...
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --mode quick --max-files 5 --formats txt,csv
echo.
echo ✅ Scan terminé! Consultez le dossier reports/
pause
goto MENU

:MULTI_FORMAT
echo.
echo 📊 Scan avec rapports multi-formats...
set /p max_files="Nombre max de fichiers (défaut 10): "
if "%max_files%"=="" set max_files=10

python scripts\identify_relevant_files_sharepoint.py --source sharepoint --mode quick --max-files %max_files% --formats txt,csv,json,xlsx --reports-dir enhanced_reports
echo.
echo ✅ Scan terminé! Consultez le dossier enhanced_reports/
pause
goto MENU

:FULL_WORKFLOW
echo.
echo ⬇️ Workflow complet : scan + téléchargement + import...
echo.
set /p confirm="⚠️ Ceci va télécharger et importer des fichiers. Continuer ? (o/N): "
if /i not "%confirm%"=="o" goto MENU

set /p max_files="Nombre max de fichiers (défaut 5): "
if "%max_files%"=="" set max_files=5

python scripts\identify_relevant_files_sharepoint.py --source sharepoint --mode download --max-files %max_files% --auto-import --formats txt,csv,json
echo.
echo ✅ Workflow terminé!
pause
goto MENU

:CUSTOM_SCAN
echo.
echo 🔧 Configuration personnalisée...
echo.
set /p folder="Dossier SharePoint (défaut /Documents partages): "
if "%folder%"=="" set folder="/Documents partages"

set /p max_files="Nombre max de fichiers: "
if "%max_files%"=="" set max_files=20

set /p confidence="Confiance minimum (0.0-1.0, défaut 0.3): "
if "%confidence%"=="" set confidence=0.3

set /p formats="Formats de rapport (txt,csv,json,xlsx): "
if "%formats%"=="" set formats=txt,csv

set /p deep="Analyse approfondie ? (o/N): "
if /i "%deep%"=="o" (
    set DEEP_FLAG=--deep-scan
) else (
    set DEEP_FLAG=
)

echo.
echo 🚀 Lancement du scan personnalisé...
python scripts\identify_relevant_files_sharepoint.py --source sharepoint --folder "%folder%" --max-files %max_files% --min-confidence %confidence% --formats %formats% %DEEP_FLAG%
echo.
echo ✅ Scan personnalisé terminé!
pause
goto MENU

:DEMO
echo.
echo 📝 Démonstration complète des nouvelles fonctionnalités...
python demo_identify_sharepoint.py
pause
goto MENU

:EXIT
echo.
echo 👋 Au revoir !
echo.
echo 📚 Documentation des nouvelles fonctionnalités:
echo   📊 Rapports multi-formats (TXT, CSV, JSON, Excel)
echo   🚫 Gestion d'erreurs SharePoint améliorée
echo   🔄 Import automatique après identification
echo   📁 Organisation logs/ et reports/
echo   🚀 Limitation fichiers pour tests
echo.
pause
exit /b 0
