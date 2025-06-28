#!/usr/bin/env python3
"""
Script de test rapide pour identifier des fichiers DPGF dans des dossiers spécifiques
"""

import subprocess
import sys
from pathlib import Path

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
        
        try:
            # Utiliser la commande directement sans passer par l'URL parsing
            cmd = [
                sys.executable, 
                "scripts/identify_relevant_files_sharepoint.py",
                "--source", "sharepoint",
                "--folder", folder,
                "--mode", "quick", 
                "--max-files", "3",
                "--min-confidence", "0.1",
                "--formats", "txt"
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=120  # 2 minutes max par dossier
            )
            
            if result.returncode == 0:
                # Analyser la sortie pour voir s'il y a des fichiers identifiés
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
        except Exception as e:
            print(f"❌ Erreur: {str(e)}")
    
    print(f"\n{'='*50}")
    print("✅ Test rapide terminé !")
    print("\nPour lancer l'analyse complète optimisée:")
    print("python orchestrate_dpgf_workflow.py --interactive --max-files 30")

if __name__ == "__main__":
    test_specific_folders()
