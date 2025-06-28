#!/usr/bin/env python3
"""
Script de test rapide pour le workflow DPGF
Permet de tester l'orchestration avec des paramètres sécurisés
"""

import os
import sys
import subprocess
from pathlib import Path

def test_workflow_prerequisites():
    """Test rapide des prérequis"""
    print("🧪 Test des prérequis du workflow DPGF...")
    
    issues = []
    
    # Test Python
    try:
        import pandas, requests, openpyxl
        print("✅ Modules Python OK")
    except ImportError as e:
        issues.append(f"Module Python manquant: {e}")
    
    # Test variables d'environnement
    required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'GRAPH_DRIVE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        issues.append(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
    else:
        print("✅ Variables d'environnement SharePoint OK")
    
    # Test scripts
    scripts_to_check = [
        'orchestrate_dpgf_workflow.py',
        'scripts/identify_relevant_files_sharepoint.py',
        'scripts/import_dpgf_unified.py'
    ]
    
    for script in scripts_to_check:
        if not Path(script).exists():
            issues.append(f"Script manquant: {script}")
    
    if not issues:
        print("✅ Scripts d'orchestration OK")
    
    # Test API (optionnel)
    try:
        import requests
        response = requests.get('http://127.0.0.1:8000/health', timeout=5)
        if response.status_code == 200:
            print("✅ API backend accessible")
        else:
            issues.append("API backend non accessible")
    except:
        issues.append("API backend non accessible (normal si pas démarrée)")
    
    return issues

def run_test_workflow():
    """Lance un workflow de test sécurisé"""
    print("\n🚀 Lancement d'un workflow de test...")
    print("Configuration de test:")
    print("   - Mode: Interactif")
    print("   - Confiance min: 0.8 (élevée pour limiter les téléchargements)")
    print("   - Fichiers max: 5 (test limité)")
    print("   - Scan: Rapide")
    
    cmd = [
        'python', 'orchestrate_dpgf_workflow.py',
        '--interactive',
        '--min-confidence', '0.8',
        '--max-files', '5',
        '--work-dir', 'dpgf_test_workflow'
    ]
    
    print(f"\nCommande: {' '.join(cmd)}")
    print("\n" + "="*50)
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Workflow de test terminé avec succès!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erreur lors du workflow de test: {e}")
        return False
    except KeyboardInterrupt:
        print("\n⏹️ Workflow interrompu par l'utilisateur")
        return False
    
    return True

def main():
    print("🎯 Test rapide du workflow DPGF automatisé")
    print("=" * 50)
    
    # Test des prérequis
    issues = test_workflow_prerequisites()
    
    if issues:
        print("\n❌ Problèmes détectés:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n💡 Résolvez ces problèmes avant de continuer")
        return False
    
    print("\n✅ Tous les prérequis sont satisfaits!")
    
    # Demander confirmation pour le test
    response = input("\n🤔 Lancer un workflow de test sécurisé ? (o/N): ").strip().lower()
    if response in ['o', 'oui', 'y', 'yes']:
        return run_test_workflow()
    else:
        print("\nTest annulé. Pour lancer le workflow complet:")
        print("   python orchestrate_dpgf_workflow.py --auto")
        print("ou")
        print("   run_dpgf_workflow.bat")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
