@echo off
REM Script batch pour tester l'orchestrateur optimisé
REM Auteur: Assistant IA
REM Date: 2024

echo ========================================
echo 🚀 TEST DE L'ORCHESTRATEUR OPTIMISE
echo ========================================
echo.

REM Vérifier que Python est disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas disponible dans le PATH
    echo 💡 Installez Python ou ajoutez-le au PATH
    pause
    exit /b 1
)

echo ✅ Python detecte
python --version
echo.

REM Vérifier que les scripts existent
if not exist "orchestrate_dpgf_workflow_optimized.py" (
    echo ❌ Script orchestrate_dpgf_workflow_optimized.py non trouve
    pause
    exit /b 1
)

if not exist "test_orchestrator_optimized.py" (
    echo ❌ Script test_orchestrator_optimized.py non trouve
    pause
    exit /b 1
)

echo ✅ Scripts detectes
echo.

REM Créer les répertoires nécessaires
if not exist "logs" mkdir logs
if not exist "reports" mkdir reports

echo 📁 Repertoires prets
echo.

REM Menu interactif
:menu
echo ========================================
echo 🎯 CHOISISSEZ UN TEST:
echo ========================================
echo 1. Test complet de validation
echo 2. Test rapide (2 dossiers max)
echo 3. Test avec analyse approfondie
echo 4. Test avec filtres de dossiers
echo 5. Aide de l'orchestrateur
echo 6. Workflow complet (ATTENTION: peut être long)
echo 0. Quitter
echo.
set /p choice=Votre choix (0-6): 

if "%choice%"=="0" goto :end
if "%choice%"=="1" goto :test_complete
if "%choice%"=="2" goto :test_quick
if "%choice%"=="3" goto :test_deep
if "%choice%"=="4" goto :test_filters
if "%choice%"=="5" goto :help
if "%choice%"=="6" goto :workflow_full

echo ❌ Choix invalide, veuillez recommencer
echo.
goto :menu

:test_complete
echo.
echo 🧪 Lancement du test de validation complet...
echo.
python test_orchestrator_optimized.py
echo.
echo 📊 Test termine. Appuyez sur une touche pour revenir au menu...
pause >nul
goto :menu

:test_quick
echo.
echo ⚡ Test rapide avec limitations strictes...
echo.
python orchestrate_dpgf_workflow_optimized.py --test-mode --max-folders 2 --max-files-per-folder 5
echo.
echo 📊 Test termine. Appuyez sur une touche pour revenir au menu...
pause >nul
goto :menu

:test_deep
echo.
echo 🔍 Test avec analyse approfondie...
echo.
python orchestrate_dpgf_workflow_optimized.py --test-mode --deep-scan --max-folders 1 --max-files-per-folder 3
echo.
echo 📊 Test termine. Appuyez sur une touche pour revenir au menu...
pause >nul
goto :menu

:test_filters
echo.
echo 🎯 Test avec filtres sur les dossiers...
echo.
set /p filters=Entrez les filtres (ex: LOT,DPGF,2024): 
if "%filters%"=="" set filters=LOT,DPGF
echo.
python orchestrate_dpgf_workflow_optimized.py --test-mode --folder-filters "%filters%" --max-folders 2
echo.
echo 📊 Test termine. Appuyez sur une touche pour revenir au menu...
pause >nul
goto :menu

:help
echo.
echo 📖 Aide de l'orchestrateur optimise...
echo.
python orchestrate_dpgf_workflow_optimized.py --help
echo.
echo 📊 Appuyez sur une touche pour revenir au menu...
pause >nul
goto :menu

:workflow_full
echo.
echo ⚠️  ATTENTION: Vous allez lancer le workflow complet !
echo    Cela peut prendre plusieurs heures selon le nombre de dossiers.
echo.
set /p confirm=Êtes-vous sûr ? (oui/non): 
if /i not "%confirm%"=="oui" (
    echo ❌ Annule
    goto :menu
)

echo.
echo 🚀 Lancement du workflow complet...
echo    - Analyse approfondie activee
echo    - Import automatique active
echo    - Tous les dossiers SharePoint seront traites
echo.
python orchestrate_dpgf_workflow_optimized.py --deep-scan --auto-import --batch-size 3
echo.
echo 📊 Workflow termine. Verifiez les rapports dans le dossier 'reports/'
echo.
pause
goto :menu

:end
echo.
echo 👋 Au revoir !
echo.
pause
