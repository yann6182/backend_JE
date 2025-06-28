# Guide d'Identification des Fichiers DPGF/BPU/DQE sur SharePoint

Ce guide explique comment utiliser le système d'identification automatique des fichiers DPGF (Décomposition du Prix Global et Forfaitaire), BPU (Bordereau des Prix Unitaires) et DQE (Détail Quantitatif Estimatif) directement depuis SharePoint.

## Vue d'ensemble

Le système peut analyser et identifier automatiquement les fichiers pertinents dans deux environnements :
- **Répertoires locaux** : Parcourt les dossiers de votre machine
- **SharePoint** : Se connecte et analyse les fichiers directement sur SharePoint

## Prérequis

### 1. Configuration Python
```bash
# Installer les dépendances
pip install -r requirements.txt
pip install -r requirements_sharepoint.txt
```

### 2. Configuration SharePoint
Créer un fichier `.env` avec vos identifiants Azure AD :
```env
TENANT_ID=votre-tenant-id
CLIENT_ID=votre-client-id
CLIENT_SECRET=votre-client-secret
GRAPH_DRIVE_ID=votre-drive-id
```

**Note** : Consultez `GUIDE_PERMISSIONS_AZURE.md` pour la configuration des permissions Azure AD.

## Utilisation

### Option 1 : Script Batch (Recommandé)

Le script batch `identify_sharepoint_files.bat` offre une interface interactive :

```batch
identify_sharepoint_files.bat
```

**Modes disponibles :**
1. **Analyse rapide** : Analyse basée sur les noms de fichiers uniquement
2. **Analyse approfondie** : Télécharge temporairement et analyse le contenu
3. **Analyse avec téléchargement** : Garde les fichiers identifiés localement
4. **Configuration personnalisée** : Paramètres sur mesure

### Option 2 : Ligne de Commande

#### Analyse SharePoint Basique
```bash
python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages"
```

#### Analyse Approfondie avec Téléchargement
```bash
python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages" \
    --deep-scan \
    --copy-files \
    --output-dir "./identified_files"
```

#### Analyse Locale (Comparaison)
```bash
python scripts/identify_relevant_files_sharepoint.py \
    --source-type local \
    --source-dir "C:\Documents\Projets" \
    --deep-scan \
    --copy-files \
    --output-dir "./local_identified"
```

## Options de Configuration

### Paramètres Principaux

| Option | Description | Valeur par défaut |
|--------|-------------|-------------------|
| `--source-type` | Type de source (`local` ou `sharepoint`) | Requis |
| `--sharepoint-url` | URL SharePoint complète | Requis pour SharePoint |
| `--source-dir` | Répertoire local | Requis pour local |
| `--output-dir` | Dossier de destination | `./identified_files` |

### Paramètres d'Analyse

| Option | Description | Défaut |
|--------|-------------|---------|
| `--deep-scan` | Analyse approfondie du contenu | Désactivé |
| `--copy-files` | Télécharger/copier les fichiers | Désactivé |
| `--min-confidence` | Score de confiance minimum (0.0-1.0) | 0.3 |
| `--exclude-dirs` | Dossiers à exclure (séparés par virgules) | Aucun |

### Paramètres de Sortie

| Option | Description | Défaut |
|--------|-------------|---------|
| `--log-file` | Fichier de log | `identification_results.log` |
| `--download-only` | Télécharger sans import en base | Désactivé |

## Types de Fichiers Détectés

### Critères d'Identification

Le système utilise plusieurs critères pour détecter les fichiers :

#### 1. Mots-clés dans le nom de fichier
- **DPGF** : `dpgf`, `décomposition du prix global`, `prix global et forfaitaire`
- **BPU** : `bpu`, `bordereau des prix`, `prix unitaires`
- **DQE** : `dqe`, `détail quantitatif`, `quantitatif estimatif`

#### 2. Patterns de nommage
- Formats typiques : `DPGF-Lot01`, `BPU_lot_2`, `DQE-Lot-03`
- Numérotation : `DPGF2024`, `BPU_2023`

#### 3. Structure des colonnes (analyse approfondie)
- **DPGF** : `designation`, `quantité`, `prix`, `montant`
- **BPU** : `designation`, `unité`, `prix unitaire`
- **DQE** : `description`, `quantité`, `prix unitaire`, `total`

## Algorithme de Scoring

### Score de Confiance
Chaque fichier reçoit un score de confiance basé sur :

1. **Nom de fichier** (50% du score)
   - Mots-clés directs : +0.5 point
   - Patterns de nommage : +0.5 point

2. **Contenu des colonnes** (70% du score)
   - Correspondance avec les structures attendues
   - Pondération selon la précision de la correspondance

3. **Contenu textuel** (30% du score, analyse approfondie uniquement)
   - Présence de mots-clés dans les cellules
   - Terminologie métier spécifique

### Seuils de Confiance Recommandés
- **0.3** : Détection large (peut inclure des faux positifs)
- **0.5** : Équilibre précision/rappel
- **0.7** : Haute précision (peut manquer certains fichiers)

## Résultats d'Analyse

### Fichiers Générés

1. **Log d'exécution** (`identify_sharepoint.log`)
   - Détails de l'exécution
   - Erreurs et avertissements
   - Statistiques de performance

2. **Rapport d'analyse** (`identify_sharepoint_report.txt`)
   - Résumé des fichiers identifiés
   - Statistiques par type de document
   - Liste détaillée avec scores de confiance

3. **Fichiers téléchargés** (si `--copy-files`)
   - Fichiers identifiés copiés localement
   - Noms nettoyés pour éviter les conflits

### Format du Rapport

```
===============================================================================
RAPPORT D'IDENTIFICATION DES FICHIERS DPGF/BPU/DQE
===============================================================================
Date d'analyse: 2024-01-15 14:30:25
Fichiers identifiés: 15
Confiance moyenne: 0.67

RÉPARTITION PAR TYPE:
  DPGF: 8
  BPU: 4
  DQE: 3

RÉPARTITION PAR SOURCE:
  sharepoint: 15

DÉTAIL DES FICHIERS:
--------------------------------------------------------------------------------
  1. DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx
     Type: DPGF (confiance: 0.85)
     Chemin: /Documents partages/Projets/DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx
     Taille: 2,456,789 octets
     Modifié: 2024-11-15T10:30:00Z
     Source: sharepoint
```

## Intégration avec l'Import en Base

### Workflow Complet

1. **Identification** : Détection automatique des fichiers pertinents
2. **Téléchargement** : Récupération des fichiers depuis SharePoint
3. **Import** : Traitement et insertion en base de données

### Commande Intégrée
```bash
# Identification et import en une seule commande
python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages" \
    --deep-scan \
    --copy-files \
    --output-dir "./identified_files" && \
python scripts/import_dpgf_unified.py \
    --source-dir "./identified_files" \
    --auto-confirm
```

## Gestion des Erreurs

### Erreurs Courantes

#### 1. Erreurs d'Authentification
```
Erreur 401: Unauthorized
```
**Solutions :**
- Vérifier les variables d'environnement `.env`
- Renouveler les secrets Azure AD
- Vérifier les permissions du service principal

#### 2. Erreurs d'Accès aux Fichiers
```
Erreur 403: Forbidden
```
**Solutions :**
- Vérifier les permissions sur le drive SharePoint
- Utiliser le script `check_permissions.bat` pour diagnostiquer

#### 3. Erreurs de Chemin
```
Erreur 404: Not Found
```
**Solutions :**
- Vérifier l'URL SharePoint
- Utiliser le script `find_dpgf_drives.bat` pour lister les drives disponibles

### Scripts de Diagnostic

- `test_sharepoint.bat` : Test de connectivité de base
- `check_permissions.bat` : Vérification des permissions
- `find_dpgf_drives.bat` : Recherche de drives contenant des fichiers DPGF

## Optimisation des Performances

### Stratégies d'Analyse

1. **Analyse rapide** : Recommandée pour une première exploration
   - Basée uniquement sur les noms de fichiers
   - Très rapide (quelques secondes)
   - Peut manquer certains fichiers mal nommés

2. **Analyse approfondie** : Pour une précision maximale
   - Télécharge et analyse le contenu
   - Plus lente (quelques minutes selon le nombre de fichiers)
   - Détection plus précise

### Conseils de Performance

- Utilisez `--min-confidence` élevé pour réduire les faux positifs
- Excluez les dossiers non pertinents avec `--exclude-dirs`
- Utilisez l'analyse rapide pour une première passe, puis l'analyse approfondie sur les résultats

## Exemples d'Utilisation

### Cas d'Usage 1 : Audit Complet
```bash
# Identifier tous les fichiers DPGF/BPU/DQE sur SharePoint
python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages" \
    --deep-scan \
    --min-confidence 0.3 \
    --log-file audit_complet.log
```

### Cas d'Usage 2 : Collecte pour Import
```bash
# Télécharger les fichiers identifiés pour import ultérieur
python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages" \
    --deep-scan \
    --copy-files \
    --output-dir "./import_queue" \
    --min-confidence 0.5
```

### Cas d'Usage 3 : Comparaison Local/SharePoint
```bash
# Analyser les deux sources et comparer
python scripts/identify_relevant_files_sharepoint.py \
    --source-type local \
    --source-dir "C:\Projets\DPGF" \
    --log-file local_analysis.log

python scripts/identify_relevant_files_sharepoint.py \
    --source-type sharepoint \
    --sharepoint-url "https://sef92230.sharepoint.com/sites/etudes/Documents%20partages" \
    --log-file sharepoint_analysis.log
```

## Dépannage

### Problèmes de Configuration

1. **Variables d'environnement manquantes**
   ```bash
   # Vérifier la présence des variables
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('TENANT_ID:', bool(os.getenv('TENANT_ID')))"
   ```

2. **Erreurs de dépendances**
   ```bash
   # Réinstaller les packages
   pip install -r requirements.txt -r requirements_sharepoint.txt --upgrade
   ```

### Problèmes de Performance

1. **Analyse lente**
   - Désactiver `--deep-scan` pour un premier test
   - Augmenter `--min-confidence` pour réduire le nombre de fichiers analysés

2. **Erreurs de mémoire**
   - Traiter les fichiers par petits lots
   - Utiliser `--exclude-dirs` pour limiter la portée

## Support et Maintenance

### Logs et Surveillance

- Consultez régulièrement les fichiers de log
- Surveillez les taux de réussite d'identification
- Ajustez les seuils de confiance selon les résultats

### Mise à Jour des Critères

Les critères d'identification peuvent être mis à jour dans le fichier :
- `KEYWORDS` : Mots-clés de détection
- `FILE_PATTERNS` : Patterns de nommage
- `COLUMNS_PATTERNS` : Structures de colonnes attendues

### Documentation API

Pour intégrer l'identification dans d'autres systèmes, consultez les classes :
- `SharePointClient` : Accès aux fichiers SharePoint
- `FileIdentifier` : Logique d'identification
- `analyze_file()` : Fonction d'analyse individuelle

---

**Note** : Ce guide est complémentaire aux autres guides du projet (`README_DPGF_IMPORT.md`, `GUIDE_PERMISSIONS_AZURE.md`, etc.). Assurez-vous d'avoir configuré correctement l'environnement avant d'utiliser ces fonctionnalités.
