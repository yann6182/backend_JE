@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo   ORCHESTRATEUR WORKFLOW DPGF COMPLET
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

:: Vérifier si le script d'orchestration existe
if not exist "orchestrate_dpgf_workflow.py" (
    echo ❌ Script d'orchestration non trouvé: orchestrate_dpgf_workflow.py
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

:MENU
echo.
echo 🎯 Workflow DPGF - Que souhaitez-vous faire ?
echo.
echo 1. 🚀 Workflow complet automatique (recommandé)
echo 2. 🤔 Workflow interactif avec confirmations
echo 3. ⚙️  Workflow avec configuration personnalisée
echo 4. ⚡ Workflow optimisé par lots (NOUVEAU)
echo 5. 📊 Moniteur temps réel
echo 6. 🧪 Test des prérequis seulement
echo 7. � Voir les derniers rapports
echo 8. 🧹 Nettoyer les fichiers temporaires
echo 9. ❌ Quitter
echo.
set /p choice="Votre choix (1-9): "

if "%choice%"=="1" goto WORKFLOW_AUTO
if "%choice%"=="2" goto WORKFLOW_INTERACTIVE
if "%choice%"=="3" goto WORKFLOW_CUSTOM
if "%choice%"=="4" goto WORKFLOW_OPTIMIZED
if "%choice%"=="5" goto MONITOR
if "%choice%"=="6" goto TEST_PREREQUISITES
if "%choice%"=="7" goto VIEW_REPORTS
if "%choice%"=="8" goto CLEANUP
if "%choice%"=="9" goto EXIT
echo Choix invalide, veuillez réessayer.
goto MENU

:WORKFLOW_AUTO
echo.
echo 🚀 Lancement du workflow automatique complet...
echo.
echo Configuration utilisée:
echo   - Confiance minimum: 0.5
echo   - Fichiers max: 50
echo   - Taille des lots: 10 fichiers
echo   - Analyse approfondie: Oui
echo   - Nettoyage automatique: Oui
echo   - Import parallèle: Non (plus stable)
echo.
set /p gemini_key="Clé API Gemini (optionnel, Entrée pour ignorer): "

if "%gemini_key%"=="" (
    python orchestrate_dpgf_workflow.py --auto --min-confidence 0.5 --max-files 50 --batch-size 10 --deep-scan --auto-cleanup
) else (
    python orchestrate_dpgf_workflow.py --auto --min-confidence 0.5 --max-files 50 --batch-size 10 --deep-scan --auto-cleanup --gemini-key "%gemini_key%"
)

echo.
echo ✅ Workflow automatique terminé!
echo 📄 Consultez le dossier dpgf_workflow/reports/ pour les rapports détaillés
pause
goto MENU

:WORKFLOW_INTERACTIVE
echo.
echo 🤔 Lancement du workflow interactif...
echo    Vous serez invité à confirmer chaque étape
echo.
set /p gemini_key="Clé API Gemini (optionnel, Entrée pour ignorer): "

if "%gemini_key%"=="" (
    python orchestrate_dpgf_workflow.py --interactive --min-confidence 0.3 --max-files 100
) else (
    python orchestrate_dpgf_workflow.py --interactive --min-confidence 0.3 --max-files 100 --gemini-key "%gemini_key%"
)

echo.
echo ✅ Workflow interactif terminé!
pause
goto MENU

:WORKFLOW_CUSTOM
echo.
echo ⚙️ Workflow avec configuration personnalisée
echo.
if exist "workflow_config.json" (
    echo Configuration trouvée: workflow_config.json
    set /p use_config="Utiliser cette configuration ? (o/N): "
    if /i "!use_config!"=="o" (
        set CONFIG_FILE=--config workflow_config.json
    ) else (
        set CONFIG_FILE=
    )
) else (
    echo ⚠️ Fichier workflow_config.json non trouvé
    echo Utilisation des paramètres par défaut
    set CONFIG_FILE=
)

echo.
echo Paramètres personnalisables:
set /p min_conf="Confiance minimum (0.0-1.0, défaut 0.3): "
if "%min_conf%"=="" set min_conf=0.3

set /p max_files="Nombre max de fichiers (défaut 100): "
if "%max_files%"=="" set max_files=100

set /p batch_size="Taille des lots (nombre de fichiers, défaut 10): "
if "%batch_size%"=="" set batch_size=10

set /p deep_scan="Analyse approfondie ? (o/N): "
if /i "%deep_scan%"=="o" (
    set DEEP_SCAN=--deep-scan
) else (
    set DEEP_SCAN=
)

set /p cleanup="Nettoyage automatique après chaque lot ? (O/n): "
if /i "%cleanup%"=="n" (
    set AUTO_CLEANUP=
) else (
    set AUTO_CLEANUP=--auto-cleanup
)

set /p parallel="Import parallèle ? (o/N - non recommandé avec lots): "
if /i "%parallel%"=="o" (
    set PARALLEL=--parallel-import
) else (
    set PARALLEL=
)

set /p gemini_key="Clé API Gemini (optionnel): "
if not "%gemini_key%"=="" (
    set GEMINI_KEY=--gemini-key "%gemini_key%"
) else (
    set GEMINI_KEY=
)

echo.
echo 🚀 Lancement du workflow personnalisé...
python orchestrate_dpgf_workflow.py --auto %CONFIG_FILE% --min-confidence %min_conf% --max-files %max_files% --batch-size %batch_size% %DEEP_SCAN% %AUTO_CLEANUP% %PARALLEL% %GEMINI_KEY%

echo.
echo ✅ Workflow personnalisé terminé!
pause
goto MENU

:WORKFLOW_OPTIMIZED
echo.
echo ⚡ Lancement du workflow optimisé par lots...
echo.
echo 🎯 Fonctionnalités optimisées:
echo   - Traitement par lots intelligents selon la taille
echo   - Nettoyage automatique après chaque lot
echo   - Gestion mémoire optimisée
echo   - Reprise automatique en cas d'interruption
echo   - Monitoring temps réel disponible
echo.
set /p batch_size="Taille des lots (défaut 10): "
if "%batch_size%"=="" set batch_size=10

set /p max_memory="Mémoire max MB (défaut 2048): "
if "%max_memory%"=="" set max_memory=2048

set /p auto_monitor="Lancer le moniteur en parallèle ? (o/N): "

echo.
echo 🚀 Configuration optimisée:
echo   - Lots de %batch_size% fichiers
echo   - Mémoire limitée à %max_memory%MB
echo   - Nettoyage automatique: OUI
echo   - Gestion erreurs: Robuste
echo.

set /p gemini_key="Clé API Gemini (optionnel): "
if not "%gemini_key%"=="" (
    set GEMINI_KEY=--gemini-key "%gemini_key%"
) else (
    set GEMINI_KEY=
)

:: Lancer le moniteur en arrière-plan si demandé
if /i "%auto_monitor%"=="o" (
    echo 📊 Démarrage du moniteur temps réel...
    start "Moniteur DPGF" python monitor_batch_progress.py --refresh-rate 1.5
    timeout /t 2 /nobreak >nul
)

echo 🚀 Lancement du workflow optimisé...
python orchestrate_dpgf_workflow.py --auto --use-optimized-batches --batch-size %batch_size% --max-memory %max_memory% %GEMINI_KEY%

echo.
echo ✅ Workflow optimisé terminé!
echo 📊 Consultez dpgf_workflow/reports/ pour les rapports détaillés
echo 📈 Les statistiques de lots sont dans dpgf_workflow/batch_stats.json
pause
goto MENU

:MONITOR
echo.
echo 📊 Moniteur temps réel du workflow DPGF
echo.
echo Ce moniteur affiche la progression en temps réel:
echo   - Progression des lots et fichiers
echo   - Statistiques de performance
echo   - Utilisation mémoire et disque
echo   - Vitesses de traitement
echo.
set /p refresh_rate="Taux de rafraîchissement en secondes (défaut 2): "
if "%refresh_rate%"=="" set refresh_rate=2

echo 🚀 Démarrage du moniteur...
echo ⚠️ Appuyez sur Ctrl+C pour arrêter
echo.
python monitor_batch_progress.py --refresh-rate %refresh_rate%

echo.
echo 📊 Moniteur arrêté
pause
goto MENU

:TEST_PREREQUISITES
echo.
echo 🧪 Test des prérequis du workflow...
echo.

:: Test Python et modules
echo 1. Test Python et modules...
python -c "import requests, pandas, openpyxl; print('✅ Modules Python OK')" 2>nul
if errorlevel 1 (
    echo ❌ Modules Python manquants
    echo    Installez avec: pip install -r requirements_sharepoint.txt
) else (
    echo ✅ Modules Python OK
)

:: Test variables d'environnement
echo.
echo 2. Test variables d'environnement SharePoint...
python -c "import os; vars=['TENANT_ID','CLIENT_ID','CLIENT_SECRET','GRAPH_DRIVE_ID']; missing=[v for v in vars if not os.getenv(v)]; print('❌ Variables manquantes:', missing) if missing else print('✅ Variables SharePoint OK')" 2>nul

:: Test API
echo.
echo 3. Test connectivité API...
python -c "import requests; r=requests.get('http://127.0.0.1:8000/health', timeout=5); print('✅ API accessible') if r.status_code==200 else print('❌ API non accessible')" 2>nul
if errorlevel 1 echo ❌ API non accessible ou timeout

:: Test scripts
echo.
echo 4. Test présence des scripts...
if exist "scripts\identify_relevant_files_sharepoint.py" (
    echo ✅ Script identification SharePoint OK
) else (
    echo ❌ Script identification SharePoint manquant
)

if exist "scripts\import_dpgf_unified.py" (
    echo ✅ Script import DPGF OK
) else (
    echo ❌ Script import DPGF manquant
)

echo.
echo 🧪 Test des prérequis terminé!
pause
goto MENU

:VIEW_REPORTS
echo.
echo 📊 Rapports de workflow disponibles:
echo.
if exist "dpgf_workflow\reports\" (
    dir /b "dpgf_workflow\reports\*.txt" 2>nul
    echo.
    set /p report_choice="Ouvrir un rapport ? (nom du fichier ou N): "
    if not "!report_choice!"=="N" if not "!report_choice!"=="n" (
        if exist "dpgf_workflow\reports\!report_choice!" (
            start notepad "dpgf_workflow\reports\!report_choice!"
        ) else (
            echo ❌ Rapport non trouvé
        )
    )
) else (
    echo ⚠️ Aucun rapport trouvé
    echo    Exécutez d'abord un workflow pour générer des rapports
)

pause
goto MENU

:CLEANUP
echo.
echo 🧹 Nettoyage des fichiers temporaires...
echo.
if exist "dpgf_workflow\" (
    echo Contenu du répertoire de travail:
    dir "dpgf_workflow\" /s /b | find /c /v "" > nul
    if not errorlevel 1 (
        echo.
        set /p confirm="Supprimer tous les fichiers temporaires ? (o/N): "
        if /i "!confirm!"=="o" (
            rmdir /s /q "dpgf_workflow\downloaded_files" 2>nul
            rmdir /s /q "dpgf_workflow\logs" 2>nul
            echo ✅ Fichiers temporaires supprimés
            echo ⚠️ Les rapports ont été conservés
        ) else (
            echo Nettoyage annulé
        )
    )
) else (
    echo ⚠️ Aucun fichier temporaire trouvé
)

pause
goto MENU

:EXIT
echo.
echo 👋 Au revoir !
echo.
echo 📚 Documentation disponible:
echo   - README_IDENTIFICATION_SHAREPOINT.md
echo   - README_SHAREPOINT_TEST_RAPIDE.md
echo   - README_FRONTEND_DPGF_ANALYSIS.md
echo.
pause
exit /b 0
