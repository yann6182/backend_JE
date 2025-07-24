# DPGF API

API FastAPI pour la gestion des DPGF de l'entreprise **SEFARX**.

## Installation locale

1. Créez un environnement virtuel et activez-le.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # ou `.venv\Scripts\activate` sous Windows
   ```
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Copiez le fichier `.env` et modifiez si besoin la variable `DATABASE_URL`.
4. Démarrez l'API :
   ```bash
   uvicorn app.main:app --reload
   ```

## Installation via Docker

1. Lancez la stack :
   ```bash
   docker-compose up --build
   ```
2. L'API est disponible sur `http://localhost:8000`.

## Exemple de requête

```bash
curl -X POST "http://localhost:8000/api/v1/clients/" -H "Content-Type: application/json" -d '{"nom_client": "Exemple"}'
```

La documentation interactive Swagger est accessible sur `http://localhost:8000/docs`.

## Identification automatique des fichiers DPGF, BPU et DQE

Le script `scripts/identify_relevant_files.py` permet d'identifier automatiquement les fichiers pertinents (DPGF, BPU, DQE) parmi une grande quantité de données.

### Utilisation

```bash
python scripts/identify_relevant_files.py --source-dir "chemin/vers/donnees" --output-dir "chemin/vers/dossier/resultats" [options]
```

### Options disponibles

- `--source-dir` : Répertoire source contenant les fichiers à analyser (obligatoire)
- `--output-dir` : Répertoire où enregistrer les résultats et les fichiers identifiés (obligatoire)
- `--copy-files` : Copier les fichiers identifiés vers le répertoire de sortie 
- `--deep-scan` : Effectuer une analyse approfondie du contenu des fichiers (plus lent mais plus précis)
- `--exclude-dirs` : Liste de dossiers à exclure, séparés par des virgules
- `--log-file` : Fichier pour enregistrer les logs (par défaut: identification_results.log)

### Exemple

```bash
python scripts/identify_relevant_files.py --source-dir "D:/Projets" --output-dir "D:/Fichiers_Identifies" --copy-files --deep-scan
```

Cette commande analysera tous les fichiers Excel dans le répertoire "D:/Projets", identifiera les DPGF, BPU et DQE, et copiera les fichiers pertinents dans "D:/Fichiers_Identifies".
