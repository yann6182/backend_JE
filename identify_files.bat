@echo off
REM Script batch pour lancer le script d'identification des fichiers DPGF, BPU, DQE
REM Auteur: GitHub Copilot
REM Date: Juin 2025

echo ===================================================
echo  IDENTIFICATION DES FICHIERS DPGF, BPU ET DQE
echo ===================================================
echo.

REM Vérifier que Python est installé
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python n'est pas installé ou n'est pas dans le PATH.
    echo Veuillez installer Python 3.8 ou supérieur.
    pause
    exit /b 1
)

REM Vérifier que l'environnement virtuel existe, sinon le créer
if not exist ".venv\Scripts\activate.bat" (
    echo Création de l'environnement virtuel...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Erreur lors de la création de l'environnement virtuel.
        pause
        exit /b 1
    )
    
    echo Installation des dépendances...
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    
    REM Ajouter pandas, openpyxl et tqdm si nécessaire
    pip install pandas openpyxl tqdm
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo Veuillez entrer les informations suivantes :

REM Demander le répertoire source
set /p SOURCE_DIR="Répertoire source contenant les fichiers à analyser: "

REM Demander le répertoire de destination
set /p OUTPUT_DIR="Répertoire de destination pour les résultats: "

REM Demander si analyse approfondie
set /p DEEP_SCAN="Effectuer une analyse approfondie? (o/n, par défaut: n): "
if "%DEEP_SCAN%"=="o" (
    set DEEP_SCAN_OPTION=--deep-scan
) else (
    set DEEP_SCAN_OPTION=
)

REM Demander si copier les fichiers
set /p COPY_FILES="Copier les fichiers identifiés vers le répertoire de destination? (o/n, par défaut: n): "
if "%COPY_FILES%"=="o" (
    set COPY_FILES_OPTION=--copy-files
) else (
    set COPY_FILES_OPTION=
)

REM Demander s'il y a des répertoires à exclure
set /p EXCLUDE_DIRS="Répertoires à exclure (séparés par des virgules, laisser vide si aucun): "
if not "%EXCLUDE_DIRS%"=="" (
    set EXCLUDE_DIRS_OPTION=--exclude-dirs "%EXCLUDE_DIRS%"
) else (
    set EXCLUDE_DIRS_OPTION=
)

echo.
echo Configuration:
echo  - Répertoire source: %SOURCE_DIR%
echo  - Répertoire destination: %OUTPUT_DIR%
echo  - Analyse approfondie: %DEEP_SCAN%
echo  - Copier les fichiers: %COPY_FILES%
echo  - Répertoires exclus: %EXCLUDE_DIRS%
echo.

set /p CONFIRM="Lancer l'analyse? (o/n): "
if not "%CONFIRM%"=="o" (
    echo Opération annulée.
    pause
    exit /b 0
)

echo.
echo Lancement de l'analyse...
echo.

REM Exécuter le script Python avec les paramètres fournis
python scripts\identify_relevant_files.py --source-dir "%SOURCE_DIR%" --output-dir "%OUTPUT_DIR%" %DEEP_SCAN_OPTION% %COPY_FILES_OPTION% %EXCLUDE_DIRS_OPTION%

echo.
if %errorlevel% equ 0 (
    echo Analyse terminée avec succès!
    echo Les résultats ont été enregistrés dans %OUTPUT_DIR%\rapport_identification.csv
) else (
    echo Une erreur s'est produite lors de l'analyse.
)

pause
