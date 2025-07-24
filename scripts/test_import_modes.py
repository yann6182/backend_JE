#!/usr/bin/env python3
"""
Script de test pour comparer les deux modes d'import DPGF :
1. Service intégré (logique dans l'API)
2. Script de production (meilleure qualité)

Ce script permet de tester facilement les deux approches sur un même fichier
et de comparer les résultats.
"""
import argparse
import requests
import os
import json
from pathlib import Path
import time


def test_import_modes(file_path, api_url="http://127.0.0.1:8000"):
    """
    Teste les deux modes d'import sur un même fichier DPGF
    et affiche les résultats pour comparaison.
    
    Args:
        file_path: Chemin vers le fichier DPGF à tester
        api_url: URL de l'API
    """
    if not os.path.exists(file_path):
        print(f"❌ Fichier introuvable: {file_path}")
        return
    
    filename = Path(file_path).name
    
    print(f"🧪 Test d'import pour {filename}")
    print(f"API: {api_url}")
    print("-" * 50)
    
    # 1. Test avec le service intégré
    print("\n📊 Mode 1: Service intégré à l'API")
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            start_time = time.time()
            response = requests.post(
                f"{api_url}/api/v1/dpgf/upload-advanced?use_production_script=false", 
                files=files
            )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Import réussi en {elapsed:.2f} secondes")
            print(f"  - DPGF ID: {result.get('dpgf_id')}")
            print(f"  - Méthode: {result.get('method')}")
            print("\n📝 Dernières lignes du log:")
            for line in result.get("logs", [])[-10:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"❌ Échec de l'import: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    print("-" * 50)
    
    # 2. Test avec le script de production
    print("\n📊 Mode 2: Script de production")
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            start_time = time.time()
            response = requests.post(
                f"{api_url}/api/v1/dpgf/upload-advanced?use_production_script=true", 
                files=files
            )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Import réussi en {elapsed:.2f} secondes")
            print(f"  - DPGF ID: {result.get('dpgf_id')}")
            print(f"  - Méthode: {result.get('method')}")
            print("\n📝 Dernières lignes du log:")
            for line in result.get("logs", [])[-10:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"❌ Échec de l'import: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test des différents modes d'import DPGF")
    parser.add_argument("--file", required=True, help="Chemin du fichier DPGF à tester")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="URL de l'API")
    args = parser.parse_args()
    
    test_import_modes(args.file, args.api_url)
