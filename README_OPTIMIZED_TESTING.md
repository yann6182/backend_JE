# Test Rapide Optimisé pour Grands Dossiers SharePoint

Ce script permet de tester rapidement les dossiers SharePoint pour trouver des fichiers DPGF/BPU/DQE en utilisant une approche optimisée pour les dossiers volumineux. Il introduit des mécanismes pour éviter les timeouts et gérer efficacement les grandes quantités de fichiers.

## Optimisations Clés

1. **Analyse en deux phases**:
   - Phase 1: Échantillonnage rapide pour estimer la taille du dossier
   - Phase 2: Analyse ciblée avec paramètres adaptés

2. **Gestion adaptative des ressources**:
   - Ajustement automatique du `max-files` en fonction du volume
   - Timeout variable selon la complexité du dossier
   - Paramètres optimisés pour les grands dossiers

3. **Robustesse améliorée**:
   - Mécanisme de retry automatique en cas d'erreur réseau
   - Récupération des rapports JSON pour analyse fiable
   - Gestion élégante des timeouts avec recommandations

4. **Interface améliorée**:
   - Script exécutable en ligne de commande ou via fichier batch
   - Options configurables (max-files, retries, etc.)
   - Reporting clair et structuré

## Utilisation

### Via le script batch (Recommandé)

Lancez le fichier batch interactif:

```
test_quick_dpgf_optimized.bat
```

### Via la ligne de commande

#### Tester les dossiers prédéfinis:

```
python test_quick_dpgf_optimized.py --predefined
```

#### Tester un dossier spécifique:

```
python test_quick_dpgf_optimized.py "/Chemin/Vers/Dossier"
```

#### Avec options personnalisées:

```
python test_quick_dpgf_optimized.py --max-files 10 --retries 3 "/Chemin/Vers/Dossier"
```

## Paramètres disponibles

| Paramètre | Description | Valeur par défaut |
|-----------|-------------|-------------------|
| `--max-files` | Nombre maximum de fichiers à analyser | 5 |
| `--retries` | Nombre de tentatives en cas d'erreur réseau | 2 |
| `--predefined` | Utiliser les dossiers prédéfinis | - |
| `--help` | Afficher l'aide | - |

## Comment ça marche

1. **Estimation du volume**: Le script fait d'abord une estimation rapide de la taille du dossier pour adapter sa stratégie.
2. **Ajustement des paramètres**: En fonction de la taille estimée, le script ajuste automatiquement:
   - Le nombre maximum de fichiers à analyser
   - Le temps d'attente avant timeout
3. **Analyse optimisée**: Le script utilise les paramètres optimaux pour l'analyse complète.
4. **Génération de rapport**: Les résultats sont sauvegardés dans un rapport txt et json dans le dossier `reports`.

## Avantages par rapport à la version précédente

- ✅ **Beaucoup moins de timeouts** sur les grands dossiers
- ✅ **Plus d'informations**: estimation du volume, score des fichiers...
- ✅ **Meilleure robustesse**: gestion des erreurs réseau
- ✅ **Rapports structurés**: txt et json pour analyse ultérieure
- ✅ **Interface batch interactive**: pour utilisation simplifiée

## Stratégie pour les très grands dossiers

Si vous rencontrez encore des timeouts avec les dossiers très volumineux:

1. **Utilisez un sous-dossier plus spécifique** au lieu du dossier racine
2. **Réduisez la valeur de `max-files`** à 2 ou 3
3. **Utilisez l'orchestrateur complet** qui gère mieux les grands volumes:
   ```
   python orchestrate_dpgf_workflow.py --interactive --max-files 10
   ```

## Exemples de résultats

Exemple de sortie pour un dossier avec fichiers DPGF:

```
📁 Test du dossier: /Projets/2023/Construction
-----------------------------------------
🔄 Échantillonnage rapide...
📊 Estimation: environ 245 fichiers
🔄 Analyse avec max_files=5, timeout=240s...
📊 127 fichiers analysés
✅ 3 fichiers pertinents trouvés:
   1. DPGF-Lot 06 Métallerie-Serrurerie.xlsx (Score: 0.92)
   2. LOT 06 - DPGF - METALLERIE.xlsx (Score: 0.89)
   3. 804 DPGF Lot 4 - Charpente & Ossature bois.xlsx (Score: 0.76)

📝 Rapport complet: reports/quick_test_20240712_152342.txt
```

## Que faire après avoir identifié les fichiers?

Une fois que vous avez identifié les fichiers pertinents, vous pouvez:

1. **Importer les fichiers identifiés** avec l'orchestrateur:
   ```
   python orchestrate_dpgf_workflow.py --interactive --folder "/Chemin/Identifié"
   ```

2. **Analyser les rapports** générés dans le dossier `reports/` pour voir les détails de tous les fichiers identifiés

3. **Exécuter un import ciblé** en utilisant les chemins de fichiers identifiés dans le rapport JSON
