#!/usr/bin/env python3
"""
Script de démonstration des nouvelles fonctionnalités d'identification SharePoint
==============================================================================

Ce script démontre toutes les améliorations apportées au système d'identification :
- Gestion d'erreurs SharePoint améliorée
- Rapports multi-formats
- Import automatique
- Organisation des logs et rapports
- Limitation du nombre de fichiers pour tests

Usage:
    python demo_identify_sharepoint.py [--quick-test]
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Exécute une commande et affiche le résultat"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"Commande: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ Succès!")
            if result.stdout:
                print("Sortie:")
                print(result.stdout)
        else:
            print(f"❌ Erreur (code: {result.returncode})")
            if result.stderr:
                print("Erreurs:")
                print(result.stderr)
    
    except subprocess.TimeoutExpired:
        print("⏰ Timeout (5 minutes)")
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
    
    print("\n" + "="*60)

def main():
    script_path = Path(__file__).parent / "identify_relevant_files_sharepoint.py"
    
    if not script_path.exists():
        print(f"❌ Script non trouvé: {script_path}")
        return 1
    
    # Vérifier les variables d'environnement
    required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'GRAPH_DRIVE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables d'environnement manquantes: {missing_vars}")
        print("   Configurez votre fichier .env avant de continuer")
        return 1
    
    print("🚀 DÉMONSTRATION DES NOUVELLES FONCTIONNALITÉS")
    print("=" * 60)
    
    base_cmd = [sys.executable, str(script_path)]
    
    # 1. Test d'accès rapide
    run_command(
        base_cmd + ["--source", "sharepoint", "--test-access"],
        "Test d'accès SharePoint avec gestion d'erreurs améliorée"
    )
    
    # 2. Scan rapide avec limitation
    run_command(
        base_cmd + [
            "--source", "sharepoint", 
            "--mode", "quick",
            "--max-files", "5",
            "--formats", "txt,csv,json",
            "--reports-dir", "demo_reports"
        ],
        "Scan rapide limité à 5 fichiers avec rapports multi-formats"
    )
    
    # 3. Test avec répertoires organisés
    run_command(
        base_cmd + [
            "--source", "sharepoint",
            "--mode", "quick",
            "--max-files", "3",
            "--formats", "csv,json",
            "--reports-dir", "demo_reports/quick_scan",
            "--log-dir", "demo_logs"
        ],
        "Test avec organisation des répertoires (logs/ et reports/)"
    )
    
    # 4. Afficher les fichiers générés
    print("\n📁 FICHIERS GÉNÉRÉS:")
    print("=" * 40)
    
    demo_reports = Path("demo_reports")
    demo_logs = Path("demo_logs")
    
    if demo_reports.exists():
        print(f"\n📊 Rapports ({demo_reports}):")
        for file_path in demo_reports.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"  • {file_path} ({size:,} octets)")
    
    if demo_logs.exists():
        print(f"\n📝 Logs ({demo_logs}):")
        for file_path in demo_logs.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"  • {file_path} ({size:,} octets)")
    
    print("\n🎉 Démonstration terminée!")
    print("\n💡 Fonctionnalités démontrées:")
    print("   ✅ Gestion d'erreurs SharePoint améliorée")
    print("   ✅ Rapports multi-formats (TXT, CSV, JSON)")
    print("   ✅ Organisation des fichiers (logs/, reports/)")
    print("   ✅ Limitation du nombre de fichiers pour tests")
    print("   ✅ Messages d'erreur explicites")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
