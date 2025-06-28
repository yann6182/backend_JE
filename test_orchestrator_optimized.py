#!/usr/bin/env python3
"""
Script de test pour valider l'orchestrateur optimisé.

Ce script teste rapidement l'orchestrateur optimisé sur quelques dossiers
pour valider son bon fonctionnement avant de lancer un traitement complet.

Auteur: Assistant IA
Date: 2024
"""

import subprocess
import sys
import os
from pathlib import Path

def run_test(test_name, command, description):
    """Lance un test et affiche le résultat"""
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {test_name}")
    print(f"📝 {description}")
    print(f"🔧 Commande: {' '.join(command)}")
    print('='*60)
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max par test
        )
        
        print("SORTIE:")
        print(result.stdout)
        
        if result.stderr:
            print("\nERREURS:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {test_name} - RÉUSSI")
        else:
            print(f"❌ {test_name} - ÉCHEC (code: {result.returncode})")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} - TIMEOUT (> 5 minutes)")
        return False
    except Exception as e:
        print(f"💥 {test_name} - ERREUR: {str(e)}")
        return False

def main():
    print("🚀 Tests de l'orchestrateur optimisé")
    print("="*60)
    
    # Vérifier que le script existe
    orchestrator_script = "orchestrate_dpgf_workflow_optimized.py"
    if not Path(orchestrator_script).exists():
        print(f"❌ Script non trouvé: {orchestrator_script}")
        return 1
    
    # Interpréteur Python
    python_exe = sys.executable
    
    # Tests à lancer
    tests = [
        {
            'name': 'Test d\'aide',
            'command': [python_exe, orchestrator_script, '--help'],
            'description': 'Vérifier que le script se lance et affiche l\'aide correctement'
        },
        {
            'name': 'Test mode minimal',
            'command': [
                python_exe, orchestrator_script, 
                '--test-mode',
                '--max-folders', '2',
                '--max-files-per-folder', '3'
            ],
            'description': 'Test avec limitations strictes (2 dossiers, 3 fichiers max)'
        },
        {
            'name': 'Test avec filtres',
            'command': [
                python_exe, orchestrator_script,
                '--test-mode',
                '--folder-filters', 'LOT,DPGF',
                '--max-folders', '1'
            ],
            'description': 'Test avec filtrage de dossiers par nom'
        },
        {
            'name': 'Test analyse approfondie',
            'command': [
                python_exe, orchestrator_script,
                '--test-mode',
                '--deep-scan',
                '--max-folders', '1',
                '--max-files-per-folder', '2'
            ],
            'description': 'Test avec analyse approfondie du contenu'
        }
    ]
    
    # Lancer les tests
    results = []
    for test in tests:
        success = run_test(test['name'], test['command'], test['description'])
        results.append((test['name'], success))
    
    # Résumé des résultats
    print(f"\n{'='*60}")
    print("📊 RÉSUMÉ DES TESTS")
    print('='*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    failed_tests = total_tests - passed_tests
    
    for test_name, success in results:
        status = "✅ RÉUSSI" if success else "❌ ÉCHEC"
        print(f"{status:12} - {test_name}")
    
    print('='*60)
    print(f"📈 Total: {total_tests} tests")
    print(f"✅ Réussis: {passed_tests}")
    print(f"❌ Échecs: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 Tous les tests sont passés ! L'orchestrateur optimisé est prêt.")
        print("\n💡 Pour lancer le workflow complet:")
        print(f"   {python_exe} {orchestrator_script} --auto-import --deep-scan")
    else:
        print(f"\n⚠️  {failed_tests} test(s) en échec. Vérifiez les erreurs ci-dessus.")
    
    return 0 if failed_tests == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
