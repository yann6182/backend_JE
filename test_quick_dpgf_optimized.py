#!/usr/bin/env python3
"""
Script de test rapide optimisé pour identifier des fichiers DPGF dans des dossiers 
SharePoint avec gestion améliorée des grands dossiers et des timeouts.
"""

import subprocess
import sys
import os
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("quick_test_logs.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_specific_folders():
    """Teste quelques dossiers spécifiques récents"""
    
    # Dossiers récents qui ont plus de chances de contenir des DPGF
    test_folders = [
        "/06-27-2025-BOULOGNE-BILLANCOURT - CONSTRUCTION MAISON REPIT VNO",
        "/06-27-2025-I3F-PARIS-REHA_BALCONS_GARDE_COPRS", 
        "/07-04-2025-BOIS_COLOMBES-HALLE_DE_MARCHE VNO",
        "/07-04-2025-CHAMARANDE- CONSTRUCTION-14LGT VNO"
    ]
    
    print("🔍 Test rapide de dossiers spécifiques récents...")
    print("=" * 50)
    
    all_identified_files = []
    
    for folder in test_folders:
        print(f"\n📁 Test du dossier: {folder}")
        print("-" * 40)
        
        # Approche en deux phases:
        # 1. Vérification rapide avec échantillonnage pour estimer le volume
        # 2. Analyse complète avec pagination si nécessaire
        
        try:
            # Phase 1: Échantillonnage rapide avec --summary et --max-files
            print("🔄 Phase 1: Échantillonnage rapide...")
            cmd_sample = [
                sys.executable, 
                "scripts/identify_relevant_files_sharepoint.py",
                "--source", "sharepoint",
                "--folder", folder,
                "--mode", "summary",  # Mode sommaire pour estimer le volume
                "--max-files", "10",
                "--quiet",
                "--output-format", "json"
            ]
            
            result_sample = subprocess.run(
                cmd_sample, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=60  # 60 secondes max pour l'échantillonnage
            )
            
            # Analyser le résultat de l'échantillonnage
            folder_size = None
            if result_sample.returncode == 0:
                try:
                    # Essayer de parser le JSON de sortie
                    output_lines = result_sample.stdout.strip().split('\n')
                    for line in output_lines:
                        if line.startswith('{') and line.endswith('}'):
                            data = json.loads(line)
                            if 'total_files' in data:
                                folder_size = data.get('total_files', 0)
                                print(f"📊 Estimation: environ {folder_size} fichiers dans ce dossier")
                                
                                # Vérifier les résultats préliminaires
                                relevant_count = data.get('potential_dpgf_count', 0) + data.get('potential_bpu_count', 0) + data.get('potential_dqe_count', 0)
                                if relevant_count > 0:
                                    print(f"✅ Détecté ~{relevant_count} fichiers potentiellement pertinents dans l'échantillon")
                                else:
                                    print("⚠️ Aucun fichier pertinent détecté dans l'échantillon")
                except json.JSONDecodeError:
                    pass
            
            # Phase 2: Analyse complète avec pagination si nécessaire
            print("🔄 Phase 2: Analyse détaillée...")
            
            # Ajuster les paramètres en fonction de la taille du dossier
            max_files = 5
            timeout_value = 180  # 3 minutes par défaut
            
            if folder_size:
                if folder_size > 1000:
                    max_files = 3
                    timeout_value = 300  # 5 minutes pour les très grands dossiers
                elif folder_size > 500:
                    max_files = 5
                    timeout_value = 240  # 4 minutes pour les grands dossiers
                elif folder_size > 100:
                    max_files = 10
                    timeout_value = 180  # 3 minutes pour les dossiers moyens
            
            # Générer un nom de fichier de sortie unique pour cette analyse
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_basename = f"quick_test_{timestamp}_{folder.replace('/', '_').replace(' ', '_')[:30]}"
            
            cmd = [
                sys.executable, 
                "scripts/identify_relevant_files_sharepoint.py",
                "--source", "sharepoint",
                "--folder", folder,
                "--mode", "quick", 
                "--max-files", str(max_files),
                "--min-confidence", "0.1",
                "--formats", "txt,json",  # Sortie dans les deux formats
                "--output-basename", output_basename
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=timeout_value
            )
            
            # Analyser le résultat
            if result.returncode == 0:
                # Essayer de lire le fichier JSON de résultats
                json_report_path = f"reports/{output_basename}.json"
                if os.path.exists(json_report_path):
                    try:
                        with open(json_report_path, 'r', encoding='utf-8') as f:
                            report_data = json.load(f)
                            
                        identified_files = report_data.get('identified_files', [])
                        if identified_files:
                            print(f"✅ {len(identified_files)} fichiers DPGF trouvés dans ce dossier !")
                            for file_info in identified_files[:3]:  # Afficher les 3 premiers
                                print(f"   - {file_info.get('name')} (Score: {file_info.get('confidence', 0):.2f})")
                            if len(identified_files) > 3:
                                print(f"   - ... et {len(identified_files)-3} autres fichiers")
                        else:
                            print("❌ Aucun fichier DPGF identifié")
                    except (json.JSONDecodeError, FileNotFoundError) as e:
                        print(f"⚠️ Erreur lors de la lecture du rapport JSON: {str(e)}")
                        # Fallback sur l'analyse de la sortie texte
                        output = result.stdout
                        if "fichiers identifiés" in output and "0 fichiers identifiés" not in output:
                            print("✅ Fichiers DPGF trouvés dans ce dossier !")
                            # Extraire les détails
                            for line in output.split('\n'):
                                if "fichiers identifiés" in line:
                                    print(f"   {line.strip()}")
                        else:
                            print("❌ Aucun fichier DPGF identifié")
            else:
                print(f"⚠️ Erreur: {result.stderr[:200]}...")
                
        except subprocess.TimeoutExpired:
            print("⏰ Timeout - dossier trop volumineux")
            print("   Essayez avec une analyse plus ciblée ou utilisez l'orchestrateur.")
        except Exception as e:
            print(f"❌ Erreur: {str(e)}")
    
    print(f"\n{'='*50}")
    print("✅ Test rapide terminé !")
    print("\nPour lancer l'analyse complète optimisée:")
    print("python orchestrate_dpgf_workflow.py --interactive --max-files 30")

def test_specific_folder(folder_path: str, max_files: int = 5):
    """Teste un dossier spécifique avec gestion optimisée des grands dossiers"""
    
    print(f"\n📁 Test du dossier: {folder_path}")
    print("-" * 40)
    
    try:
        # Générer un nom de fichier de sortie unique
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_basename = f"quick_test_{timestamp}"
        
        # Échantillonnage rapide avec --summary
        print("🔄 Échantillonnage rapide...")
        cmd_sample = [
            sys.executable, 
            "scripts/identify_relevant_files_sharepoint.py",
            "--source", "sharepoint",
            "--folder", folder_path,
            "--mode", "summary",
            "--output-format", "json"
        ]
        
        sample_result = subprocess.run(
            cmd_sample, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            timeout=60
        )
        
        estimated_size = 0
        if sample_result.returncode == 0:
            try:
                # Analyser la sortie JSON
                output_lines = sample_result.stdout.strip().split('\n')
                for line in output_lines:
                    if line.startswith('{') and line.endswith('}'):
                        data = json.loads(line)
                        estimated_size = data.get('total_files', 0)
                        print(f"📊 Estimation: environ {estimated_size} fichiers")
            except json.JSONDecodeError:
                pass
        
        # Ajuster les paramètres en fonction de la taille estimée
        adjusted_max_files = max_files
        timeout_value = 240  # 4 minutes par défaut
        
        if estimated_size > 1000:
            adjusted_max_files = min(max_files, 3)
            timeout_value = 300  # 5 minutes pour très grands dossiers
        elif estimated_size > 500:
            adjusted_max_files = min(max_files, 5)
            timeout_value = 240
        
        print(f"🔄 Analyse avec max_files={adjusted_max_files}, timeout={timeout_value}s...")
        
        # Exécuter l'analyse complète
        cmd = [
            sys.executable, 
            "scripts/identify_relevant_files_sharepoint.py",
            "--source", "sharepoint",
            "--folder", folder_path,
            "--mode", "quick", 
            "--max-files", str(adjusted_max_files),
            "--min-confidence", "0.2",
            "--formats", "txt,json",
            "--output-basename", output_basename
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            timeout=timeout_value
        )
        
        # Analyser le résultat
        if result.returncode == 0:
            # Chercher le fichier de rapport JSON
            json_report_path = f"reports/{output_basename}.json"
            if os.path.exists(json_report_path):
                try:
                    with open(json_report_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    
                    identified_files = report_data.get('identified_files', [])
                    total_scanned = report_data.get('total_files_scanned', 0)
                    
                    print(f"📊 {total_scanned} fichiers analysés")
                    
                    if identified_files:
                        print(f"✅ {len(identified_files)} fichiers pertinents trouvés:")
                        for idx, file_info in enumerate(identified_files[:5]):
                            print(f"   {idx+1}. {file_info.get('name')} (Score: {file_info.get('confidence', 0):.2f})")
                        if len(identified_files) > 5:
                            print(f"   ... et {len(identified_files)-5} autres fichiers")
                            
                        # Optionnel: afficher le chemin vers le rapport complet
                        txt_report_path = f"reports/{output_basename}.txt"
                        if os.path.exists(txt_report_path):
                            print(f"\n📝 Rapport complet: {txt_report_path}")
                    else:
                        print("❌ Aucun fichier pertinent identifié")
                        
                    return identified_files
                    
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"⚠️ Erreur lecture rapport: {str(e)}")
            else:
                print("⚠️ Rapport JSON non trouvé, analyse de la sortie texte...")
                output = result.stdout
                if "fichiers identifiés" in output and "0 fichiers identifiés" not in output:
                    print("✅ Fichiers pertinents trouvés!")
                    for line in output.split('\n'):
                        if "fichiers identifiés" in line:
                            print(f"   {line.strip()}")
                else:
                    print("❌ Aucun fichier pertinent identifié")
        else:
            print(f"⚠️ Erreur: {result.stderr[:200]}...")
            
    except subprocess.TimeoutExpired:
        print("⏰ Timeout - Le dossier est trop volumineux")
        print("   Recommandations:")
        print("   1. Utiliser un sous-dossier plus spécifique")
        print("   2. Augmenter le timeout ou réduire max_files")
        print("   3. Utiliser l'orchestrateur pour traitement par lots")
    except Exception as e:
        print(f"❌ Erreur inattendue: {str(e)}")
    
    return []

def test_with_retry(folder_path: str, max_files: int = 5, max_retries: int = 2):
    """Teste un dossier avec système de retry en cas d'erreur réseau"""
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"\n🔄 Tentative {attempt+1}/{max_retries+1}...")
                time.sleep(3)  # Attendre un peu entre les tentatives
            return test_specific_folder(folder_path, max_files)
        except (requests.exceptions.RequestException, ConnectionError) as e:
            if attempt < max_retries:
                print(f"⚠️ Erreur réseau: {str(e)}")
                print("   Nouvelle tentative dans quelques secondes...")
            else:
                print(f"❌ Échec après {max_retries+1} tentatives: {str(e)}")
                return []

def print_help():
    """Affiche l'aide du script"""
    print("""
Usage: python test_quick_dpgf_optimized.py [OPTIONS] [FOLDER]

Options:
  --max-files N     Nombre maximum de fichiers à analyser par dossier (défaut: 5)
  --retries N       Nombre maximum de tentatives en cas d'erreur réseau (défaut: 2)
  --predefined      Tester les dossiers prédéfinis (comportement par défaut)
  --help            Afficher cette aide
  
Exemples:
  python test_quick_dpgf_optimized.py
  python test_quick_dpgf_optimized.py "/07-04-2025-BOIS_COLOMBES-HALLE_DE_MARCHE VNO"
  python test_quick_dpgf_optimized.py --max-files 10 "/Projets importants/DPGF"
    """)

if __name__ == "__main__":
    # Traiter les arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Test rapide optimisé des dossiers SharePoint")
    parser.add_argument("folder", nargs="?", help="Dossier SharePoint à tester")
    parser.add_argument("--max-files", type=int, default=5, help="Nombre max de fichiers à analyser")
    parser.add_argument("--retries", type=int, default=2, help="Nombre de tentatives en cas d'erreur")
    parser.add_argument("--predefined", action="store_true", help="Tester les dossiers prédéfinis")
    parser.add_argument("--show-help", action="store_true", help="Afficher l'aide")
    
    args = parser.parse_args()
    
    if args.show_help:
        print_help()
        sys.exit(0)
    
    if not args.folder and not args.predefined:
        # Par défaut, tester les dossiers prédéfinis
        test_specific_folders()
    elif args.folder:
        print(f"\n🔍 Test du dossier SharePoint: {args.folder}")
        test_with_retry(args.folder, args.max_files, args.retries)
    else:  # args.predefined
        test_specific_folders()
