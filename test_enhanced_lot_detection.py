"""
Test de l'orchestrateur optimisé avec la détection de lots améliorée par Gemini.
Ce script teste quelques fichiers avec la nouvelle fonctionnalité.
"""

import subprocess
import sys
import os
from pathlib import Path


def test_orchestrator_with_gemini_lots():
    """Test l'orchestrateur avec la détection de lots améliorée"""
    
    print("🧪 TEST DE L'ORCHESTRATEUR OPTIMISÉ AVEC DÉTECTION DE LOTS GEMINI")
    print("=" * 70)
    
    # Commandes de test à essayer
    test_cases = [
        {
            'name': 'Test basique (3 dossiers, sans Gemini)',
            'cmd': [
                'python', 'orchestrate_dpgf_workflow_optimized.py',
                '--max-folders', '3',
                '--max-files-per-folder', '5', 
                '--test-mode'
            ]
        },
        {
            'name': 'Test avec import automatique (sans Gemini)',
            'cmd': [
                'python', 'orchestrate_dpgf_workflow_optimized.py',
                '--max-folders', '2',
                '--max-files-per-folder', '3',
                '--auto-import',
                '--debug-import'
            ]
        }
    ]
    
    # Test avec Gemini si clé fournie
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        test_cases.append({
            'name': 'Test avec Gemini pour détection des lots',
            'cmd': [
                'python', 'orchestrate_dpgf_workflow_optimized.py',
                '--max-folders', '2',
                '--max-files-per-folder', '3',
                '--auto-import',
                '--debug-import',
                '--gemini-key', gemini_key
            ]
        })
    else:
        print("⚠️ Variable d'environnement GEMINI_API_KEY non définie")
        print("💡 Définissez-la pour tester avec Gemini: set GEMINI_API_KEY=your_key")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\\n{i}️⃣ {test_case['name']}")
        print("-" * 50)
        
        try:
            print(f"Commande: {' '.join(test_case['cmd'])}")
            print("\\nExécution en cours...")
            
            result = subprocess.run(
                test_case['cmd'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300,  # 5 minutes max par test
                cwd=Path(__file__).parent
            )
            
            if result.returncode == 0:
                print("✅ Test réussi !")
                
                # Extraire les statistiques importantes de la sortie
                lines = result.stdout.split('\\n')
                for line in lines:
                    if any(keyword in line for keyword in ['✅', '📁', '📊', '🎯', '💾', '⚠️']):
                        print(f"   {line}")
                        
            else:
                print(f"❌ Test échoué (code {result.returncode})")
                if result.stderr:
                    print(f"Erreur: {result.stderr[:300]}")
                    
        except subprocess.TimeoutExpired:
            print("⏰ Test interrompu (timeout)")
        except Exception as e:
            print(f"💥 Erreur lors de l'exécution: {e}")


def test_import_direct_with_gemini():
    """Test l'import direct avec Gemini"""
    
    print("\\n" + "=" * 70)
    print("🔧 TEST D'IMPORT DIRECT AVEC DÉTECTION LOTS GEMINI")
    print("=" * 70)
    
    # Choisir un fichier de test
    test_files = [
        "test_data/LOT 06 - DPGF - METALLERIE_.xlsx",
        "test_data/DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx"
    ]
    
    for test_file in test_files:
        if Path(test_file).exists():
            print(f"\\n📄 Test avec: {Path(test_file).name}")
            print("-" * 40)
            
            # Test sans Gemini
            cmd_classic = [
                'python', 'scripts/import_complete.py',
                '--file', test_file,
                '--dry-run',
                '--debug'
            ]
            
            print("1. Import sans Gemini (dry-run):")
            try:
                result = subprocess.run(
                    cmd_classic,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60,
                    cwd=Path(__file__).parent
                )
                
                if result.returncode == 0:
                    # Chercher les lignes sur la détection du lot
                    lines = result.stdout.split('\\n')
                    for line in lines:
                        if 'lot' in line.lower() and ('détecté' in line.lower() or 'trouvé' in line.lower()):
                            print(f"   {line}")
                else:
                    print(f"   ❌ Échec (code {result.returncode})")
                    
            except Exception as e:
                print(f"   💥 Erreur: {e}")
            
            # Test avec Gemini si clé disponible
            gemini_key = os.environ.get('GEMINI_API_KEY')
            if gemini_key:
                cmd_gemini = [
                    'python', 'scripts/import_complete.py',
                    '--file', test_file,
                    '--dry-run',
                    '--debug',
                    '--gemini-key', gemini_key
                ]
                
                print("\\n2. Import avec Gemini (dry-run):")
                try:
                    result = subprocess.run(
                        cmd_gemini,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=120,  # Plus de temps pour Gemini
                        cwd=Path(__file__).parent
                    )
                    
                    if result.returncode == 0:
                        # Chercher les lignes sur Gemini et la détection du lot
                        lines = result.stdout.split('\\n')
                        for line in lines:
                            if any(keyword in line for keyword in ['🧠', 'Gemini', 'lot', 'Lot']):
                                print(f"   {line}")
                    else:
                        print(f"   ❌ Échec (code {result.returncode})")
                        if result.stderr:
                            print(f"   Erreur: {result.stderr[:200]}")
                            
                except Exception as e:
                    print(f"   💥 Erreur: {e}")
            else:
                print("\\n2. Test Gemini ignoré (clé API non définie)")
            
            break  # Tester seulement le premier fichier trouvé
    else:
        print("❌ Aucun fichier de test trouvé")


def main():
    """Fonction principale"""
    print("🚀 TESTS DE LA DÉTECTION DE LOTS AMÉLIORÉE AVEC GEMINI")
    print("=" * 70)
    
    # Vérifier la configuration
    if not Path("orchestrate_dpgf_workflow_optimized.py").exists():
        print("❌ orchestrate_dpgf_workflow_optimized.py non trouvé")
        return 1
    
    if not Path("scripts/import_complete.py").exists():
        print("❌ scripts/import_complete.py non trouvé")
        return 1
    
    # Lancer les tests
    test_orchestrator_with_gemini_lots()
    test_import_direct_with_gemini()
    
    print("\\n" + "=" * 70)
    print("📋 RÉSUMÉ DES AMÉLIORATIONS")
    print("=" * 70)
    print("✅ Détection des lots déléguée à Gemini quand disponible")
    print("✅ Fallback sur la méthode classique si Gemini échoue")
    print("✅ Amélioration de la robustesse de détection des lots")
    print("✅ Tests de validation créés")
    print("\\n💡 Pour utiliser Gemini:")
    print("   set GEMINI_API_KEY=your_api_key")
    print("   python orchestrate_dpgf_workflow_optimized.py --auto-import --gemini-key %GEMINI_API_KEY%")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
