#!/usr/bin/env python3
"""
Script pour démarrer l'API FastAPI et tester l'upload de fichiers DPGF
"""

import uvicorn
import threading
import time
import sys
from pathlib import Path

def start_api_server():
    """Démarre le serveur API FastAPI"""
    print("🚀 Démarrage du serveur API FastAPI...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )

def main():
    """Point d'entrée principal"""
    print("🏗️  Système d'import automatique DPGF")
    print("=" * 50)
    
    # Vérifier que nous sommes dans le bon répertoire
    if not Path("app/main.py").exists():
        print("❌ Erreur: Ce script doit être exécuté depuis le répertoire racine du projet")
        sys.exit(1)
    
    print("📋 Instructions d'utilisation:")
    print("1. Le serveur API va démarrer sur http://localhost:8000")
    print("2. Utilisez test_upload_dpgf.py pour uploader vos fichiers DPGF")
    print("3. L'import sera traité automatiquement en arrière-plan")
    print()
    print("💡 Exemples de commandes:")
    print("   python test_upload_dpgf.py test_data/802\\ DPGF\\ Lot\\ 2\\ -\\ Curage.xlsx")
    print("   python test_upload_dpgf.py \"test_data/DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx\"")
    print()
    print("🌐 Documentation API: http://localhost:8000/docs")
    print("=" * 50)
    
    try:
        start_api_server()
    except KeyboardInterrupt:
        print("\\n🛑 Arrêt du serveur...")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage du serveur: {e}")

if __name__ == "__main__":
    main()
