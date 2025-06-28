# Guide d'utilisation de l'import DPGF avancé

Ce guide explique comment configurer et utiliser la nouvelle fonctionnalité d'import DPGF avancé qui utilise le script de production pour une meilleure qualité d'import.

## Configuration

L'import DPGF avancé nécessite que le script de production `import_complete.py` soit accessible. Par défaut, le système cherche ce script dans plusieurs emplacements :

1. Dans le répertoire `scripts` du projet
2. Dans les répertoires parents
3. Dans le répertoire courant
4. Dans d'autres emplacements standard

Si le script n'est pas trouvé automatiquement, vous pouvez spécifier son emplacement de plusieurs façons :

### 1. Utiliser le script de configuration

Exécutez le script de configuration pour définir automatiquement les variables d'environnement nécessaires :

```bash
python setup_dpgf_import.py
```

Options disponibles :
- `--script-path` : Chemin explicite vers le script import_complete.py
- `--api-url` : URL de l'API (par défaut: http://127.0.0.1:8000)
- `--env-file` : Créer un fichier .env avec les variables
- `--batch-file` : Créer un fichier batch pour Windows

### 2. Définir manuellement les variables d'environnement

Sous Windows :
```
set DPGF_IMPORT_SCRIPT_PATH=D:\CH4\backend_JE\scripts\import_complete.py
set API_BASE_URL=http://127.0.0.1:8000
```

Sous Linux/macOS :
```
export DPGF_IMPORT_SCRIPT_PATH=/path/to/scripts/import_complete.py
export API_BASE_URL=http://127.0.0.1:8000
```

## Utilisation

### Via l'API REST

Envoyez une requête POST à l'endpoint `/api/v1/dpgf/upload-advanced` avec :
- Le fichier DPGF dans un champ multipart nommé `file`
- Un paramètre optionnel `use_production_script` (boolean, défaut: true)

Exemple avec curl :
```bash
curl -X POST "http://localhost:8000/api/v1/dpgf/upload-advanced?use_production_script=true" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/your/dpgf_file.xlsx"
```

### Via le script de test

Un script de test est fourni pour comparer les deux modes d'import (script de production vs. service intégré) :

```bash
python scripts/test_import_modes.py --file "test_data/02_2024_024_BPU_lot_7.xlsx"
```

## Dépannage

### Erreur "Script de production introuvable"

1. Vérifiez que le fichier `import_complete.py` existe bien dans le répertoire `scripts` du projet
2. Utilisez le script de configuration pour définir explicitement le chemin
3. Vérifiez les permissions d'accès au fichier

### Problèmes d'exécution du script

1. Assurez-vous que toutes les dépendances nécessaires sont installées
2. Vérifiez que l'interpréteur Python utilisé a accès à tous les modules requis
3. Activez le mode debug pour plus d'informations

## Comparaison des modes d'import

| Fonctionnalité | Service intégré | Script de production |
|----------------|----------------|---------------------|
| Vitesse        | Plus rapide    | Légèrement plus lent |
| Qualité de détection | Bonne    | Excellente |
| Détection des sections | Basique | Avancée |
| Hiérarchie | Simple | Complexe et précise |
| Dépendances | Minimales | Requiert le script externe |
