# Guide d'utilisation du script d'identification automatique

Ce document explique comment utiliser le script `identify_relevant_files.py` pour identifier automatiquement les fichiers pertinents de type DPGF (Décomposition du Prix Global et Forfaitaire), BPU (Bordereau des Prix Unitaires) et DQE (Détail Quantitatif Estimatif) parmi une grande quantité de données.

## Prérequis

- Python 3.8 ou supérieur
- Packages Python : pandas, openpyxl, tqdm
- Accès en lecture aux fichiers source
- Accès en écriture au répertoire de destination

## Installation des dépendances

Avant d'exécuter le script, assurez-vous d'installer les dépendances requises :

```bash
pip install pandas openpyxl tqdm
```

Ou si vous utilisez l'environnement virtuel du projet :

```bash
pip install -r requirements.txt
pip install pandas openpyxl tqdm
```

## Méthode 1 : Exécution via le fichier batch (Windows)

Pour une utilisation simplifiée sous Windows, utilisez le fichier batch fourni :

1. Double-cliquez sur `identify_files.bat`
2. Suivez les instructions à l'écran pour:
   - Spécifier le répertoire source contenant vos fichiers
   - Spécifier le répertoire de destination pour les résultats
   - Choisir si une analyse approfondie est nécessaire
   - Choisir si les fichiers identifiés doivent être copiés
   - Spécifier des répertoires à exclure (optionnel)

## Méthode 2 : Exécution en ligne de commande

Le script peut être lancé directement en ligne de commande avec les options suivantes :

```bash
python scripts/identify_relevant_files.py --source-dir "CHEMIN_SOURCE" --output-dir "CHEMIN_DESTINATION" [options]
```

### Options disponibles

- `--source-dir` : Répertoire source contenant les fichiers à analyser (obligatoire)
- `--output-dir` : Répertoire où enregistrer les résultats (obligatoire)
- `--copy-files` : Copier les fichiers identifiés vers le répertoire de destination
- `--deep-scan` : Effectuer une analyse approfondie du contenu (plus précis, mais plus lent)
- `--exclude-dirs` : Liste de dossiers à exclure, séparés par des virgules
- `--log-file` : Nom du fichier journal (par défaut : identification_results.log)

### Exemples

#### Exemple 1 : Analyse simple sans copie de fichiers

```bash
python scripts/identify_relevant_files.py --source-dir "D:/Projets" --output-dir "D:/Resultats"
```

Cette commande analysera tous les fichiers Excel dans le répertoire "D:/Projets" et créera un rapport dans "D:/Resultats" sans copier les fichiers.

#### Exemple 2 : Analyse approfondie avec copie des fichiers

```bash
python scripts/identify_relevant_files.py --source-dir "D:/Projets" --output-dir "D:/Resultats" --deep-scan --copy-files
```

Cette commande effectuera une analyse approfondie et copiera les fichiers identifiés dans "D:/Resultats", organisés par type (DPGF, BPU, DQE).

#### Exemple 3 : Exclure certains répertoires

```bash
python scripts/identify_relevant_files.py --source-dir "D:/Projets" --output-dir "D:/Resultats" --copy-files --exclude-dirs "Archives,Temporaire,Sauvegardes"
```

Cette commande ignorera les dossiers "Archives", "Temporaire" et "Sauvegardes" lors de l'analyse.

## Structure des résultats

Après exécution, le script génère :

1. **rapport_identification.csv** : Un fichier CSV contenant les informations sur tous les fichiers identifiés avec :
   - Chemin du fichier
   - Type détecté (DPGF, BPU ou DQE)
   - Score de confiance
   - Numéro de lot (si détecté)
   - Nom du lot (si détecté)

2. **Dossiers organisés** (si l'option `--copy-files` est utilisée) :
   - `DPGF/` : Contient les fichiers identifiés comme DPGF
   - `BPU/` : Contient les fichiers identifiés comme BPU
   - `DQE/` : Contient les fichiers identifiés comme DQE

3. **identification_results.log** : Journal détaillé de l'exécution

## Mécanisme de détection

Le script utilise plusieurs critères pour identifier les types de fichiers :

1. **Analyse du nom de fichier** (40% du score) :
   - Recherche de mots-clés (ex: "dpgf", "bpu", "dqe")
   - Reconnaissance de patterns (ex: "lot X - dpgf")

2. **Analyse du contenu** (60% du score) :
   - Structure des colonnes (ex: présence de colonnes "désignation", "quantité", "prix")
   - Recherche de mots-clés dans le contenu
   - Analyse des formules et calculs typiques (mode analyse approfondie)

## Conseils pour de meilleurs résultats

- Si possible, utilisez l'option `--deep-scan` pour une meilleure précision
- Pour traiter des volumes importants de données (>100 Go), lancez le script sur des sous-répertoires séparément
- Examinez le rapport CSV pour valider les résultats et ajuster le traitement si nécessaire
- Si le script manque certains fichiers, vérifiez s'ils suivent un format non standard et ajustez les critères dans le code si nécessaire

## Résolution des problèmes courants

1. **Le script est très lent** :
   - Désactivez l'option `--deep-scan` pour une exécution plus rapide
   - Traitez les données par lots (sous-répertoires)

2. **Fichiers non identifiés** :
   - Vérifiez si les fichiers sont protégés en lecture
   - Vérifiez si les fichiers sont dans un format Excel non standard
   - Examinez les erreurs dans le fichier journal

3. **Erreurs de mémoire** :
   - Traitez un volume de données plus petit à la fois
   - Assurez-vous que votre système dispose de suffisamment de RAM

## Support

Pour toute question ou problème concernant ce script, veuillez contacter l'équipe de développement.
