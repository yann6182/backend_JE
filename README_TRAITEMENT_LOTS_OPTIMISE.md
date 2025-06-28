# Guide du Traitement par Lots Optimisé DPGF

## 🚀 Vue d'ensemble

Le nouveau système de traitement par lots optimisé permet de traiter de très gros volumes de fichiers DPGF sur SharePoint sans surcharger votre système local. 

### ✨ Principales fonctionnalités

- **Traitement par lots intelligents** : Optimisation automatique selon la taille des fichiers
- **Gestion mémoire avancée** : Surveillance et limitation de l'utilisation mémoire
- **Nettoyage automatique** : Suppression des fichiers après import pour économiser l'espace disque
- **Monitoring temps réel** : Suivi de la progression avec interface graphique
- **Robustesse** : Gestion des erreurs et reprise automatique
- **Configuration flexible** : Adaptation aux capacités de votre machine

## 🛠️ Installation

### 1. Dépendances de base
```bash
pip install -r requirements_sharepoint.txt
```

### 2. Dépendances pour le traitement optimisé
```bash
pip install -r requirements_batch_processing.txt
```

### 3. Vérification de l'installation
```bash
python test_workflow.py
```

## 🎯 Modes d'utilisation

### Mode 1 : Interface graphique (Recommandé)
```bash
run_dpgf_workflow.bat
# Choisir l'option 4 : "Workflow optimisé par lots"
```

### Mode 2 : Ligne de commande
```bash
python orchestrate_dpgf_workflow.py --auto --use-optimized-batches --batch-size 15 --max-memory 1024
```

### Mode 3 : Avec monitoring
```bash
# Terminal 1 : Lancer le workflow
python orchestrate_dpgf_workflow.py --auto --use-optimized-batches

# Terminal 2 : Lancer le monitoring
python monitor_batch_progress.py --refresh-rate 1
```

## ⚙️ Configuration avancée

### Fichier de configuration (`workflow_config.json`)

```json
{
  "download": {
    "use_optimized_batches": true,
    "batch_size": 10,
    "max_batch_size_mb": 100,
    "max_memory_mb": 2048,
    "max_disk_mb": 1024,
    "auto_cleanup": true,
    "retry_count": 3
  },
  "scanning": {
    "min_confidence": 0.5,
    "max_files": 100,
    "deep_scan": true
  }
}
```

### Paramètres clés

| Paramètre | Description | Défaut | Recommandé |
|-----------|-------------|---------|------------|
| `batch_size` | Nombre de fichiers par lot | 10 | 5-20 selon la RAM |
| `max_batch_size_mb` | Taille max d'un lot en MB | 100 | 50-200 selon l'espace |
| `max_memory_mb` | Limite mémoire système | 2048 | 50-70% de votre RAM |
| `max_disk_mb` | Espace disque temporaire | 1024 | 500-2000 selon l'espace |
| `auto_cleanup` | Nettoyage automatique | true | **Toujours true** |

## 📊 Workflow optimisé étape par étape

### 1. 🔍 Scan SharePoint
- Connexion sécurisée à SharePoint
- Identification des fichiers DPGF/BPU/DQE
- Filtrage par confiance et critères
- **Aucun téléchargement** à cette étape

### 2. 📦 Organisation en lots
- Regroupement intelligent par taille
- Optimisation pour éviter les surcharges mémoire
- Priorisation par niveau de confiance

### 3. 🔄 Traitement lot par lot
Pour chaque lot :
1. **Téléchargement** du lot uniquement
2. **Import immédiat** en base de données
3. **Nettoyage automatique** des fichiers locaux
4. **Monitoring** des ressources

### 4. 📈 Reporting final
- Statistiques complètes
- Détails par lot
- Métriques de performance

## 📊 Monitoring temps réel

### Interface du moniteur
```
📊 PROGRESSION DU WORKFLOW DPGF
┌─────────────────┬──────────┬─────────────┐
│ Métrique        │ Valeur   │ Détails     │
├─────────────────┼──────────┼─────────────┤
│ Progression lots│ 3/12     │ 25.0%       │
│ Fichiers        │ 45/120   │ 37.5%       │
│ Taux de succès  │ 42 OK    │ 93.3%       │
│ Données traitées│ 125.5MB  │             │
│ Temps écoulé    │ 5.2min   │             │
│ Temps restant   │ 8.1min   │ 🕐          │
│ Vitesse         │ 1.4 f/s  │ 2.1 MB/s    │
│ Mémoire         │ 1.2GB    │ 🧠          │
└─────────────────┴──────────┴─────────────┘

📦 STATISTIQUES DES DERNIERS LOTS
┌─────┬─────────┬────────┬────────┬────────┬────────┐
│ Lot │ Fichiers│ Import │ Taille │ Durée  │ Statut │
├─────┼─────────┼────────┼────────┼────────┼────────┤
│ #1  │ 10/10   │ 10     │ 45.2MB │ 2.1min │ ✅     │
│ #2  │ 10/10   │ 9      │ 38.7MB │ 1.9min │ ⚠️     │
│ #3  │ 10/10   │ 10     │ 41.6MB │ 2.0min │ ✅     │
└─────┴─────────┴────────┴────────┴────────┴────────┘
```

## 🔧 Optimisation des performances

### Pour machines avec peu de RAM (< 8GB)
```json
{
  "download": {
    "batch_size": 5,
    "max_batch_size_mb": 50,
    "max_memory_mb": 1024,
    "max_disk_mb": 500
  }
}
```

### Pour machines puissantes (> 16GB)
```json
{
  "download": {
    "batch_size": 20,
    "max_batch_size_mb": 200,
    "max_memory_mb": 4096,
    "max_disk_mb": 2048
  }
}
```

### Pour SharePoint lent ou instable
```json
{
  "download": {
    "batch_size": 3,
    "retry_count": 5,
    "timeout_seconds": 600
  }
}
```

## 🚨 Gestion des erreurs

### Types d'erreurs gérées
- **Erreurs réseau** : Retry automatique avec backoff
- **Erreurs mémoire** : Pause et réduction de lot
- **Erreurs disque** : Nettoyage forcé
- **Erreurs API** : Retry avec délai progressif

### Reprise après interruption
```bash
# Le système détecte automatiquement les interruptions
python orchestrate_dpgf_workflow.py --auto --use-optimized-batches --resume
```

## 📁 Structure des fichiers de travail

```
dpgf_workflow/
├── batches/                 # Lots temporaires (auto-nettoyés)
│   ├── batch_001/
│   ├── batch_002/
│   └── ...
├── logs/                    # Logs détaillés
│   ├── orchestration_dpgf.log
│   └── batch_*.log
├── reports/                 # Rapports finaux
│   └── workflow_report_*.txt
├── batch_progress.json      # État de progression
└── batch_stats.json         # Historique des lots
```

## 🎯 Cas d'usage typiques

### 1. SharePoint avec 500+ fichiers DPGF
```bash
python orchestrate_dpgf_workflow.py \
  --auto \
  --use-optimized-batches \
  --batch-size 8 \
  --max-files 200 \
  --min-confidence 0.6
```

### 2. Machine avec ressources limitées
```bash
python orchestrate_dpgf_workflow.py \
  --auto \
  --use-optimized-batches \
  --batch-size 3 \
  --max-memory 512 \
  --max-disk 256
```

### 3. Traitement de nuit avec monitoring
```bash
# Lancer le monitoring
python monitor_batch_progress.py --refresh-rate 5 &

# Lancer le workflow
python orchestrate_dpgf_workflow.py \
  --auto \
  --use-optimized-batches \
  --batch-size 15 \
  --max-files 500
```

## 📈 Métriques et KPIs

### Métriques surveillées
- **Débit** : Fichiers traités par minute
- **Efficacité** : Ratio succès/échec
- **Ressources** : Pic mémoire, espace disque
- **Temps** : Durée par lot, temps total
- **Données** : Volume téléchargé, lignes importées

### Seuils d'alerte
- Mémoire > 90% de la limite
- Espace disque < 100MB
- Taux d'échec > 20%
- Durée par lot > 10 minutes

## 🔍 Debugging et dépannage

### Problèmes courants

#### 1. "Mémoire insuffisante"
- Réduire `batch_size` à 3-5
- Diminuer `max_memory_mb`
- Fermer les autres applications

#### 2. "Espace disque insuffisant"
- Vérifier que `auto_cleanup` est activé
- Réduire `max_disk_mb`
- Libérer de l'espace manuellement

#### 3. "Erreurs SharePoint fréquentes"
- Augmenter `retry_count`
- Réduire `batch_size`
- Vérifier la connexion réseau

#### 4. "Import lent"
- Vérifier que l'API est accessible
- Réduire `chunk_size`
- Désactiver Gemini temporairement

### Logs de débogage
```bash
# Activer les logs détaillés
export DPGF_DEBUG=1
python orchestrate_dpgf_workflow.py --auto --use-optimized-batches
```

### Commandes de diagnostic
```bash
# Vérifier l'état du système
python -c "import psutil; print(f'RAM: {psutil.virtual_memory().available/1024**3:.1f}GB disponible')"

# Tester la connectivité SharePoint
python scripts/identify_relevant_files_sharepoint.py --test-connection

# Vérifier l'API
curl http://127.0.0.1:8000/health
```

## 🏆 Bonnes pratiques

### 1. **Planification**
- Exécuter pendant les heures creuses
- Surveiller l'espace disque disponible
- Sauvegarder la configuration avant modifications

### 2. **Monitoring**
- Toujours utiliser le monitoring temps réel
- Surveiller les logs d'erreur
- Configurer des alertes si possible

### 3. **Sécurité**
- Garder les clés API sécurisées
- Utiliser des variables d'environnement
- Ne pas committer les fichiers de configuration

### 4. **Performance**
- Adapter la taille des lots à votre machine
- Utiliser le nettoyage automatique
- Éviter les autres tâches intensives pendant le traitement

## 📞 Support et contribution

Pour des questions ou des améliorations :
1. Consulter les logs détaillés
2. Vérifier la configuration
3. Tester avec un petit échantillon
4. Documenter les cas d'erreur

---

*Ce guide sera mis à jour selon les retours d'expérience et les nouvelles fonctionnalités.*
