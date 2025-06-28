#!/usr/bin/env python3
"""
Script de configuration pour le service d'import DPGF
Ce script aide à configurer les chemins et variables d'environnement nécessaires
pour le bon fonctionnement de l'import DPGF avancé.
"""
import os
import sys
from pathlib import Path
import subprocess
import argparse


def find_script_path():
    """
    Recherche le chemin du script import_complete.py
    """
    possible_paths = [
        Path.cwd() / "scripts" / "import_complete.py",
        Path.cwd().parent / "scripts" / "import_complete.py",
        Path(__file__).parent / "scripts" / "import_complete.py",
        Path(__file__).parent.parent / "scripts" / "import_complete.py",
        Path.home() / "CH4" / "backend_JE" / "scripts" / "import_complete.py"
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def setup_environment(script_path=None, api_url=None):
    """
    Configure les variables d'environnement nécessaires
    """
    if script_path:
        script_path = Path(script_path)
        if not script_path.exists():
            print(f"⚠️ Script non trouvé: {script_path}")
            return False
    else:
        script_path = find_script_path()
        if not script_path:
            print("❌ Impossible de trouver le script import_complete.py automatiquement")
            print("Veuillez spécifier le chemin avec --script-path")
            return False
    
    # Configurer les variables d'environnement
    os.environ["DPGF_IMPORT_SCRIPT_PATH"] = str(script_path)
    if api_url:
        os.environ["API_BASE_URL"] = api_url
    
    print("✅ Variables d'environnement configurées:")
    print(f"   - DPGF_IMPORT_SCRIPT_PATH = {os.environ['DPGF_IMPORT_SCRIPT_PATH']}")
    if api_url:
        print(f"   - API_BASE_URL = {os.environ['API_BASE_URL']}")
    
    return True


def create_env_file(script_path=None, api_url=None):
    """
    Crée un fichier .env avec les variables configurées
    """
    if script_path:
        script_path = Path(script_path)
        if not script_path.exists():
            print(f"⚠️ Script non trouvé: {script_path}")
            return False
    else:
        script_path = find_script_path()
        if not script_path:
            print("❌ Impossible de trouver le script import_complete.py automatiquement")
            return False
    
    if not api_url:
        api_url = "http://127.0.0.1:8000"
    
    env_file = Path.cwd() / ".env"
    with open(env_file, "w") as f:
        f.write(f"DPGF_IMPORT_SCRIPT_PATH={script_path}\n")
        f.write(f"API_BASE_URL={api_url}\n")
    
    print(f"✅ Fichier .env créé: {env_file}")
    print("   Contenu:")
    print(f"   DPGF_IMPORT_SCRIPT_PATH={script_path}")
    print(f"   API_BASE_URL={api_url}")
    
    return True


def create_batch_script(script_path=None, api_url=None):
    """
    Crée un fichier batch pour configurer les variables d'environnement
    """
    if script_path:
        script_path = Path(script_path)
        if not script_path.exists():
            print(f"⚠️ Script non trouvé: {script_path}")
            return False
    else:
        script_path = find_script_path()
        if not script_path:
            print("❌ Impossible de trouver le script import_complete.py automatiquement")
            return False
    
    if not api_url:
        api_url = "http://127.0.0.1:8000"
    
    batch_file = Path.cwd() / "set_dpgf_env.bat"
    with open(batch_file, "w") as f:
        f.write("@echo off\n")
        f.write(f"set DPGF_IMPORT_SCRIPT_PATH={script_path}\n")
        f.write(f"set API_BASE_URL={api_url}\n")
        f.write('echo Variables d\'environnement configurees:\n')
        f.write('echo DPGF_IMPORT_SCRIPT_PATH=%DPGF_IMPORT_SCRIPT_PATH%\n')
        f.write('echo API_BASE_URL=%API_BASE_URL%\n')
    
    print(f"✅ Fichier batch créé: {batch_file}")
    print("   Pour l'utiliser, exécutez:")
    print(f"   {batch_file}")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configuration pour l'import DPGF avancé")
    parser.add_argument("--script-path", help="Chemin du script import_complete.py")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="URL de l'API (défaut: http://127.0.0.1:8000)")
    parser.add_argument("--env-file", action="store_true", help="Créer un fichier .env")
    parser.add_argument("--batch-file", action="store_true", help="Créer un fichier batch pour Windows")
    
    args = parser.parse_args()
    
    if not args.env_file and not args.batch_file:
        # Mode interactif - configurer pour la session courante
        if setup_environment(args.script_path, args.api_url):
            print("✅ Configuration terminée avec succès pour la session courante")
    
    if args.env_file:
        create_env_file(args.script_path, args.api_url)
    
    if args.batch_file:
        create_batch_script(args.script_path, args.api_url)
