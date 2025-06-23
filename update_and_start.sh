#!/bin/bash
# Script pour appliquer les migrations et démarrer le serveur API

# Appliquer les migrations Alembic
echo "Applying database migrations..."
python -m alembic upgrade head

# Démarrer le serveur API
echo "Starting API server..."
python start_api_server.py
