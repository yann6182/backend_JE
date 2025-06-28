@echo off
title Traitement Progressif DPGF - Dossier par Dossier
color 0A

echo.
echo ============================================================
echo   TRAITEMENT PROGRESSIF DPGF - DOSSIER PAR DOSSIER
echo ============================================================
echo.
echo Ce script traite les dossiers SharePoint un par un :
echo   1. Identifie les fichiers DPGF dans chaque dossier
echo   2. Telecharge et importe immediatement les fichiers
echo   3. Affiche le progres en temps reel
echo   4. Permet de reprendre en cas d'interruption
echo.
echo Avantages :
echo   - Traitement progressif (feedback immediat)
echo   - Gestion memoire optimale
echo   - Recuperation en cas d'erreur
echo   - Statistiques detaillees
echo.

set /p confirm="Voulez-vous continuer ? (o/n): "
if /i not "%confirm%"=="o" goto end

echo.
echo Activation de l'environnement virtuel...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Environnement virtuel active.
) else (
    echo ATTENTION: Environnement virtuel non trouve - utilisation Python systeme
)

echo.
echo Verification des dependances...
python -m pip install -q -r requirements_sharepoint.txt

echo.
echo ============================================================
echo   DEMARRAGE DU TRAITEMENT PROGRESSIF
echo ============================================================
echo.

python progressive_dpgf_processor.py

echo.
echo ============================================================
echo   TRAITEMENT TERMINE
echo ============================================================
echo.
echo Consultez les fichiers de log pour plus de details :
echo   - progressive_import/progressive_results_*.json
echo   - progressive_dpgf_import_*.log
echo.

:end
pause
exit
