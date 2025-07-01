#!/bin/bash
echo "Starting DPGF SharePoint Orchestrator..."

# Activation de l'environnement virtuel (si applicable)
# source venv/bin/activate

# Démarrage de l'API backend
echo "Starting API backend..."
python start_api_server.py &
API_PID=$!

# Attente de 10 secondes pour que l'API démarre
sleep 10

# Démarrage de l'orchestrateur en mode planifié
echo "Starting SharePoint Orchestrator..."
python sharepoint_orchestrator.py scheduled

# Nettoyage à la fin
kill $API_PID 2>/dev/null
