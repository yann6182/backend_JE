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
