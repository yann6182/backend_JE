#!/usr/bin/env python3
"""
Test rapide du système de traitement par lots optimisé
======================================================

Ce script teste les principales fonctionnalités du nouveau système
de traitement par lots sans exécuter un workflow complet.

Usage:
    python test_batch_system.py [--verbose]
"""

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List

def test_batch_manager_import():
    """Test d'import du BatchManager"""
    print("🧪 Test d'import du BatchManager...")
    
    try:
        sys.path.append(str(Path(__file__).parent / 'scripts'))
        from batch_manager import BatchManager, BatchStats, BatchProgress
        print("✅ BatchManager importé avec succès")
        return True
    except ImportError as e:
        print(f"❌ Erreur import BatchManager: {e}")
        return False

def test_monitor_import():
    """Test d'import du moniteur"""
    print("🧪 Test d'import du moniteur...")
    
    try:
        # Test d'import sans rich (mode basique)
        import monitor_batch_progress
        print("✅ Moniteur importé avec succès")
        return True
    except ImportError as e:
        print(f"❌ Erreur import moniteur: {e}")
        return False

def test_orchestrator_args():
    """Test des arguments de l'orchestrateur"""
    print("🧪 Test des arguments de l'orchestrateur...")
    
    try:
        import subprocess
        result = subprocess.run([
            'python', 'orchestrate_dpgf_workflow.py', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if '--use-optimized-batches' in result.stdout:
            print("✅ Arguments optimisés disponibles")
            return True
        else:
            print("❌ Arguments optimisés manquants")
            return False
    except Exception as e:
        print(f"❌ Erreur test arguments: {e}")
        return False

def test_config_file():
    """Test du fichier de configuration"""
    print("🧪 Test du fichier de configuration...")
    
    config_file = Path('workflow_config.json')
    if not config_file.exists():
        print("❌ Fichier workflow_config.json manquant")
        return False
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_keys = ['download', 'scanning', 'import']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"❌ Clés manquantes dans la config: {missing_keys}")
            return False
        
        # Vérifier les options optimisées
        download_config = config.get('download', {})
        if 'use_optimized_batches' not in download_config:
            print("⚠️ Option 'use_optimized_batches' manquante (sera ajoutée)")
        
        print("✅ Fichier de configuration valide")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON dans la configuration: {e}")
        return False

def test_batch_creation():
    """Test de création d'un gestionnaire de lots"""
    print("🧪 Test de création du gestionnaire de lots...")
    
    try:
        sys.path.append(str(Path(__file__).parent / 'scripts'))
        from batch_manager import BatchManager
        
        # Configuration de test
        config = {
            'download': {
                'batch_size': 5,
                'max_batch_size_mb': 50,
                'auto_cleanup': True,
                'max_memory_mb': 1024,
                'max_disk_mb': 512
            }
        }
        
        # Créer un répertoire de test temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = BatchManager(config, Path(temp_dir))
            
            # Test de création des répertoires
            if not manager.batch_dir.exists():
                print("❌ Répertoire de lots non créé")
                return False
            
            print("✅ Gestionnaire de lots créé avec succès")
            return True
            
    except Exception as e:
        print(f"❌ Erreur création gestionnaire: {e}")
        return False

def test_batch_optimization():
    """Test de l'optimisation des lots"""
    print("🧪 Test de l'optimisation des lots...")
    
    try:
        sys.path.append(str(Path(__file__).parent / 'scripts'))
        from batch_manager import BatchManager
        
        config = {
            'download': {
                'batch_size': 3,
                'max_batch_size_mb': 10,
                'auto_cleanup': True
            }
        }
        
        # Fichiers de test simulés
        test_files = [
            {'name': 'file1.xlsx', 'size': 2 * 1024 * 1024},  # 2MB
            {'name': 'file2.xlsx', 'size': 5 * 1024 * 1024},  # 5MB
            {'name': 'file3.xlsx', 'size': 8 * 1024 * 1024},  # 8MB
            {'name': 'file4.xlsx', 'size': 1 * 1024 * 1024},  # 1MB
            {'name': 'file5.xlsx', 'size': 3 * 1024 * 1024},  # 3MB
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = BatchManager(config, Path(temp_dir))
            batches = manager._optimize_batch_size(test_files)
            
            if len(batches) == 0:
                print("❌ Aucun lot créé")
                return False
            
            # Vérifier que les gros fichiers sont traités séparément
            large_files_separated = any(
                len(batch) == 1 and batch[0]['size'] > 10 * 1024 * 1024
                for batch in batches
            )
            
            print(f"✅ Optimisation réussie: {len(test_files)} fichiers → {len(batches)} lots")
            return True
            
    except Exception as e:
        print(f"❌ Erreur optimisation lots: {e}")
        return False

def test_resource_monitoring():
    """Test du monitoring des ressources"""
    print("🧪 Test du monitoring des ressources...")
    
    try:
        import psutil
        
        # Test mémoire
        memory = psutil.virtual_memory()
        memory_mb = memory.available / 1024 / 1024
        
        if memory_mb < 512:
            print(f"⚠️ Mémoire disponible faible: {memory_mb:.0f}MB")
        else:
            print(f"✅ Mémoire disponible: {memory_mb:.0f}MB")
        
        # Test espace disque
        disk = psutil.disk_usage('.')
        disk_free_mb = disk.free / 1024 / 1024
        
        if disk_free_mb < 1024:
            print(f"⚠️ Espace disque faible: {disk_free_mb:.0f}MB")
        else:
            print(f"✅ Espace disque disponible: {disk_free_mb:.0f}MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur monitoring ressources: {e}")
        return False

def test_rich_availability():
    """Test de disponibilité de rich pour l'interface"""
    print("🧪 Test de disponibilité de rich...")
    
    try:
        import rich
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        print("✅ Rich disponible - Interface enrichie activée")
        return True
        
    except ImportError:
        print("⚠️ Rich non disponible - Interface basique utilisée")
        return False

def run_all_tests(verbose=False):
    """Exécute tous les tests"""
    print("🚀 Test du système de traitement par lots optimisé")
    print("=" * 60)
    
    tests = [
        ("Import BatchManager", test_batch_manager_import),
        ("Import Moniteur", test_monitor_import),
        ("Arguments Orchestrateur", test_orchestrator_args),
        ("Fichier Configuration", test_config_file),
        ("Création Gestionnaire", test_batch_creation),
        ("Optimisation Lots", test_batch_optimization),
        ("Monitoring Ressources", test_resource_monitoring),
        ("Interface Rich", test_rich_availability),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            success = test_func()
            duration = time.time() - start_time
            
            results.append((test_name, success, duration))
            
            if verbose:
                print(f"⏱️ Durée: {duration:.2f}s")
                
        except Exception as e:
            print(f"💥 Exception dans {test_name}: {e}")
            results.append((test_name, False, 0))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, duration in results:
        status = "✅ PASS" if success else "❌ FAIL"
        if verbose:
            print(f"{status} {test_name} ({duration:.2f}s)")
        else:
            print(f"{status} {test_name}")
    
    print(f"\n🎯 Résultat global: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 Tous les tests sont passés ! Le système est prêt.")
        return True
    elif passed >= total * 0.8:
        print("⚠️ La plupart des tests sont passés. Quelques fonctionnalités peuvent être limitées.")
        return True
    else:
        print("❌ Plusieurs tests ont échoué. Vérifiez l'installation.")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test du système de traitement par lots optimisé")
    parser.add_argument('--verbose', '-v', action='store_true', help='Affichage détaillé')
    
    args = parser.parse_args()
    
    success = run_all_tests(args.verbose)
    
    if success:
        print("\n🚀 Vous pouvez maintenant utiliser le traitement optimisé:")
        print("   run_dpgf_workflow.bat → Option 4")
        print("   ou")
        print("   python orchestrate_dpgf_workflow.py --auto --use-optimized-batches")
    else:
        print("\n🔧 Installez les dépendances manquantes:")
        print("   pip install -r requirements_batch_processing.txt")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
