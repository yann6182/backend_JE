@echo off
:: Script batch pour tester rapidement des dossiers SharePoint
:: pour identifier des fichiers DPGF/BPU/DQE
:: Version optimisée pour grands dossiers

echo.
echo ====================================================
echo    TEST RAPIDE OPTIMISÉ DE DOSSIERS SHAREPOINT
echo ====================================================
echo.

:: Activer l'environnement virtuel s'il existe
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [✓] Environnement virtuel activé
) else (
    echo [!] Environnement virtuel non trouvé, utilisation du Python système
)

:menu
echo.
echo Choisissez une option:
echo.
echo  1. Tester les dossiers prédéfinis récents
echo  2. Tester un dossier spécifique
echo  3. Mode avancé (paramètres personnalisés)
echo  4. Quitter
echo.

set /p choix="Votre choix [1-4]: "

if "%choix%"=="1" (
    echo.
    echo Lancement du test sur les dossiers prédéfinis...
    python test_quick_dpgf_optimized.py --predefined
    goto fin
)

if "%choix%"=="2" (
    echo.
    echo Entrez le chemin du dossier SharePoint à tester:
    echo  - Commencez par / (ex: /Projets/2024)
    echo  - Laissez vide pour tester à la racine
    echo.
    
    set /p folder="Dossier: "
    
    echo.
    echo Lancement du test sur le dossier: %folder%
    python test_quick_dpgf_optimized.py "%folder%"
    goto fin
)

if "%choix%"=="3" (
    echo.
    echo === Mode avancé ===
    echo.
    echo Entrez le chemin du dossier SharePoint:
    set /p folder="Dossier: "
    
    echo.
    echo Nombre max de fichiers à analyser par dossier (défaut: 5):
    set /p max_files="Max fichiers: "
    if "%max_files%"=="" set max_files=5
    
    echo.
    echo Nombre de tentatives en cas d'erreur réseau (défaut: 2):
    set /p retries="Tentatives: "
    if "%retries%"=="" set retries=2
    
    echo.
    echo Lancement du test avec les paramètres personnalisés...
    python test_quick_dpgf_optimized.py --max-files %max_files% --retries %retries% "%folder%"
    goto fin
)

if "%choix%"=="4" (
    goto fin
) else (
    echo.
    echo [!] Option invalide, veuillez réessayer.
    goto menu
)

:fin
echo.
echo ====================================================
echo Test terminé!
echo.
echo Pour lancer une analyse complète, utilisez:
echo python orchestrate_dpgf_workflow.py --interactive
echo ====================================================
echo.

pause
