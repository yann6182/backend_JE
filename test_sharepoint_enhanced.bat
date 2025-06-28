@echo off
title Test SharePoint - Nouvelles fonctionnalités
color 0A

echo.
echo =======================================================
echo  Test des nouvelles fonctionnalités SharePoint
echo =======================================================
echo.

:menu
echo Que voulez-vous tester ?
echo.
echo 1. Test d'acces au dossier racine SharePoint (/)
echo 2. Test d'acces a un dossier specifique
echo 3. Analyse rapide avec rapport multi-formats
echo 4. Analyse avec import automatique
echo 5. Test avec limitation du nombre de fichiers
echo 6. Demonstration complete
echo 7. Quitter
echo.

set /p choice="Entrez votre choix (1-7): "

if "%choice%"=="1" goto test_root
if "%choice%"=="2" goto test_specific
if "%choice%"=="3" goto test_reports
if "%choice%"=="4" goto test_auto_import
if "%choice%"=="5" goto test_limit
if "%choice%"=="6" goto demo_complete
if "%choice%"=="7" goto end
goto menu

:test_root
echo.
echo Test d'acces au dossier racine SharePoint...
echo.
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "/" --test-access
cd ..
echo.
pause
goto menu

:test_specific
echo.
set /p folder="Entrez le chemin du dossier a tester (ex: /Documents partages): "
if "%folder%"=="" set folder=/Documents partages
echo.
echo Test d'acces au dossier: %folder%
echo.
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "%folder%" --test-access
cd ..
echo.
pause
goto menu

:test_reports
echo.
set /p folder="Dossier a analyser (defaut: /): "
if "%folder%"=="" set folder=/
echo.
echo Analyse avec rapports multi-formats (TXT, CSV, JSON, XLSX)...
echo.
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "%folder%" --mode quick --formats txt csv json xlsx --output-basename test_sharepoint
cd ..
echo.
echo Verifiez les rapports generes dans le dossier 'reports/'
echo.
pause
goto menu

:test_auto_import
echo.
echo ATTENTION: Cette option lancera l'import automatique des fichiers identifies !
set /p confirm="Etes-vous sur de vouloir continuer ? (o/n): "
if /i not "%confirm%"=="o" goto menu
echo.
set /p folder="Dossier a analyser et importer (defaut: /): "
if "%folder%"=="" set folder=/
echo.
echo Analyse avec import automatique...
echo.
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "%folder%" --mode quick --auto-import --max-files 5
cd ..
echo.
pause
goto menu

:test_limit
echo.
set /p folder="Dossier a analyser (defaut: /): "
if "%folder%"=="" set folder=/
set /p max_files="Nombre max de fichiers a analyser (defaut: 3): "
if "%max_files%"=="" set max_files=3
echo.
echo Analyse limitee a %max_files% fichiers...
echo.
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "%folder%" --mode quick --max-files %max_files% --formats txt json
cd ..
echo.
pause
goto menu

:demo_complete
echo.
echo Demonstration complete des nouvelles fonctionnalites...
echo.
echo 1. Test d'acces au dossier racine
cd scripts
python identify_relevant_files_sharepoint.py --source sharepoint --folder "/" --test-access
echo.
echo 2. Analyse rapide avec rapports multiples
python identify_relevant_files_sharepoint.py --source sharepoint --folder "/" --mode quick --max-files 5 --formats txt csv json --output-basename demo_complete
echo.
echo 3. Verification des fichiers generes
cd ..
if exist "reports\" (
    echo Rapports generes:
    dir reports\demo_complete*.* /b
) else (
    echo Aucun rapport genere
)
if exist "logs\" (
    echo Logs generes:
    dir logs\*.log /b | findstr /i sharepoint
) else (
    echo Aucun log genere
)
echo.
pause
goto menu

:end
echo.
echo Au revoir !
echo.
pause
exit
