@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo   INSTALLATION SYSTÈME LOTS OPTIMISÉS DPGF
echo ===============================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python non trouvé
    echo    Installez Python 3.8+ depuis https://python.org
    pause
    exit /b 1
)

echo ✅ Python détecté
python --version

:: Vérifier pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip non trouvé
    pause
    exit /b 1
)

echo ✅ pip détecté

echo.
echo 📦 Installation des dépendances...
echo.

:: Installer les dépendances SharePoint de base
echo 1️⃣ Installation des dépendances SharePoint...
if exist "requirements_sharepoint.txt" (
    pip install -r requirements_sharepoint.txt
    if errorlevel 1 (
        echo ❌ Erreur installation dépendances SharePoint
        pause
        exit /b 1
    )
    echo ✅ Dépendances SharePoint installées
) else (
    echo ⚠️ Fichier requirements_sharepoint.txt non trouvé
)

echo.
echo 2️⃣ Installation des dépendances pour le traitement par lots...
if exist "requirements_batch_processing.txt" (
    pip install -r requirements_batch_processing.txt
    if errorlevel 1 (
        echo ❌ Erreur installation dépendances lots optimisés
        echo    Certaines fonctionnalités peuvent être limitées
    ) else (
        echo ✅ Dépendances lots optimisés installées
    )
) else (
    echo ⚠️ Fichier requirements_batch_processing.txt non trouvé
    echo    Installation manuelle des packages principaux...
    pip install psutil rich colorama tqdm
)

echo.
echo 3️⃣ Test de l'installation...
python test_batch_system.py

echo.
echo 🎯 Installation terminée !
echo.
echo 📋 Prochaines étapes:
echo   1. Configurez vos variables d'environnement SharePoint dans .env
echo   2. Lancez: run_dpgf_workflow.bat
echo   3. Choisissez l'option 4: "Workflow optimisé par lots"
echo.
echo 📚 Documentation:
echo   - README_TRAITEMENT_LOTS_OPTIMISE.md
echo   - README_IDENTIFICATION_SHAREPOINT.md
echo.
pause
