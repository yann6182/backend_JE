"""
Test de la détection améliorée des lots avec Gemini.
Ce script teste la nouvelle fonctionnalité de détection des lots utilisant Gemini.
"""

import os
import sys
from pathlib import Path
import argparse

# Ajouter le répertoire scripts au path
sys.path.append(str(Path(__file__).parent / "scripts"))

try:
    from import_complete import ExcelParser, GeminiProcessor, ColumnMapping, ErrorReporter
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("💡 Assurez-vous que import_complete.py est dans scripts/")
    sys.exit(1)


def test_lot_detection_with_gemini(file_path: str, gemini_key: str = None):
    """
    Test la détection des lots avec et sans Gemini
    
    Args:
        file_path: Chemin vers le fichier Excel à tester
        gemini_key: Clé API Gemini (optionnelle)
    """
    print(f"🧪 Test de détection des lots pour: {Path(file_path).name}")
    print("=" * 60)
    
    # Test 1: Détection classique (sans Gemini)
    print("\\n1️⃣ DÉTECTION CLASSIQUE (sans Gemini)")
    print("-" * 40)
    
    try:
        parser_classic = ExcelParser(file_path, ColumnMapping(), ErrorReporter(), dry_run=True)
        lots_classic = parser_classic.find_lot_headers()
        
        if lots_classic:
            print(f"✅ Lots détectés (méthode classique): {len(lots_classic)}")
            for numero, nom in lots_classic:
                print(f"   • Lot {numero}: {nom}")
        else:
            print("❌ Aucun lot détecté avec la méthode classique")
            
    except Exception as e:
        print(f"❌ Erreur méthode classique: {e}")
        lots_classic = []
    
    # Test 2: Détection avec Gemini (si clé fournie)
    lots_gemini = []
    if gemini_key:
        print("\\n2️⃣ DÉTECTION AVEC GEMINI")
        print("-" * 40)
        
        try:
            gemini_processor = GeminiProcessor(api_key=gemini_key, chunk_size=20)
            parser_gemini = ExcelParser(file_path, ColumnMapping(), ErrorReporter(), 
                                      dry_run=True, gemini_processor=gemini_processor)
            lots_gemini = parser_gemini.find_lot_headers()
            
            if lots_gemini:
                print(f"✅ Lots détectés (avec Gemini): {len(lots_gemini)}")
                for numero, nom in lots_gemini:
                    print(f"   • Lot {numero}: {nom}")
            else:
                print("❌ Aucun lot détecté avec Gemini")
                
        except Exception as e:
            print(f"❌ Erreur Gemini: {e}")
            lots_gemini = []
    else:
        print("\\n2️⃣ DÉTECTION AVEC GEMINI")
        print("-" * 40)
        print("⚠️ Clé Gemini non fournie, test ignoré")
    
    # Comparaison des résultats
    print("\\n3️⃣ COMPARAISON DES RÉSULTATS")
    print("-" * 40)
    
    if lots_classic and lots_gemini:
        if lots_classic == lots_gemini:
            print("✅ Les deux méthodes donnent les mêmes résultats")
        else:
            print("⚠️ Résultats différents entre les deux méthodes:")
            print(f"   Classique: {lots_classic}")
            print(f"   Gemini: {lots_gemini}")
    elif lots_gemini and not lots_classic:
        print("🚀 Gemini a réussi là où la méthode classique a échoué !")
        print("   Ceci démontre l'amélioration apportée par l'IA")
    elif lots_classic and not lots_gemini:
        print("🔄 La méthode classique a réussi mais pas Gemini")
        print("   Ceci peut indiquer un problème avec le prompt Gemini")
    elif not lots_classic and not lots_gemini:
        print("❌ Aucune méthode n'a réussi à détecter un lot")
        print("   Le fichier ne contient peut-être pas d'information de lot claire")
    
    # Analyse du contenu pour debug
    print("\\n4️⃣ ANALYSE DU CONTENU (DEBUG)")
    print("-" * 40)
    
    try:
        import pandas as pd
        df = pd.read_excel(file_path, nrows=10)
        
        print("Aperçu du contenu (10 premières lignes):")
        for i in range(min(10, len(df))):
            row_data = []
            for j in range(min(5, len(df.columns))):
                cell_value = df.iloc[i, j]
                if pd.notna(cell_value):
                    row_data.append(str(cell_value)[:30])  # Limiter à 30 caractères
                else:
                    row_data.append("")
            print(f"   Ligne {i}: {' | '.join(row_data)}")
    except Exception as e:
        print(f"❌ Erreur lecture fichier: {e}")
    
    return lots_classic, lots_gemini


def test_multiple_files(test_dir: str = "test_data", gemini_key: str = None):
    """
    Test la détection des lots sur plusieurs fichiers
    
    Args:
        test_dir: Répertoire contenant les fichiers de test
        gemini_key: Clé API Gemini (optionnelle)
    """
    print("🧪 TEST DE DÉTECTION DES LOTS SUR PLUSIEURS FICHIERS")
    print("=" * 70)
    
    test_path = Path(test_dir)
    if not test_path.exists():
        print(f"❌ Répertoire de test non trouvé: {test_dir}")
        return
    
    excel_files = list(test_path.glob("*.xlsx")) + list(test_path.glob("*.xls"))
    
    if not excel_files:
        print(f"❌ Aucun fichier Excel trouvé dans {test_dir}")
        return
    
    print(f"📁 {len(excel_files)} fichiers Excel trouvés")
    
    results = {
        'total_files': len(excel_files),
        'classic_success': 0,
        'gemini_success': 0,
        'both_success': 0,
        'neither_success': 0,
        'gemini_improvement': 0
    }
    
    for i, file_path in enumerate(excel_files, 1):
        print(f"\\n📄 [{i}/{len(excel_files)}] {file_path.name}")
        print("-" * 50)
        
        try:
            lots_classic, lots_gemini = test_lot_detection_with_gemini(str(file_path), gemini_key)
            
            # Statistiques
            classic_found = len(lots_classic) > 0
            gemini_found = len(lots_gemini) > 0
            
            if classic_found:
                results['classic_success'] += 1
            if gemini_found:
                results['gemini_success'] += 1
            if classic_found and gemini_found:
                results['both_success'] += 1
            if not classic_found and not gemini_found:
                results['neither_success'] += 1
            if gemini_found and not classic_found:
                results['gemini_improvement'] += 1
            
            # Résumé pour ce fichier
            if classic_found and gemini_found:
                print("   🎯 Résultat: Les deux méthodes ont réussi")
            elif gemini_found and not classic_found:
                print("   🚀 Résultat: Seul Gemini a réussi (amélioration !)")
            elif classic_found and not gemini_found:
                print("   🔄 Résultat: Seule la méthode classique a réussi")
            else:
                print("   ❌ Résultat: Aucune méthode n'a réussi")
                
        except Exception as e:
            print(f"   ❌ Erreur lors du test: {e}")
    
    # Rapport final
    print("\\n" + "=" * 70)
    print("📊 RAPPORT FINAL")
    print("=" * 70)
    print(f"📁 Fichiers testés: {results['total_files']}")
    print(f"✅ Succès méthode classique: {results['classic_success']}/{results['total_files']} ({results['classic_success']/results['total_files']*100:.1f}%)")
    
    if gemini_key:
        print(f"🧠 Succès avec Gemini: {results['gemini_success']}/{results['total_files']} ({results['gemini_success']/results['total_files']*100:.1f}%)")
        print(f"🎯 Succès des deux méthodes: {results['both_success']}/{results['total_files']} ({results['both_success']/results['total_files']*100:.1f}%)")
        print(f"🚀 Améliorations Gemini: {results['gemini_improvement']}/{results['total_files']} ({results['gemini_improvement']/results['total_files']*100:.1f}%)")
        print(f"❌ Échec total: {results['neither_success']}/{results['total_files']} ({results['neither_success']/results['total_files']*100:.1f}%)")
        
        if results['gemini_improvement'] > 0:
            print(f"\\n🎉 Gemini améliore la détection dans {results['gemini_improvement']} cas !")
        
        # Recommandations
        print("\\n💡 RECOMMANDATIONS:")
        if results['gemini_success'] > results['classic_success']:
            print("   • Gemini améliore significativement la détection des lots")
            print("   • Recommandation: Utiliser Gemini par défaut pour la détection des lots")
        elif results['gemini_success'] == results['classic_success']:
            print("   • Les deux méthodes ont des performances similaires")
            print("   • Recommandation: Garder Gemini comme méthode de fallback")
        else:
            print("   • La méthode classique reste plus fiable")
            print("   • Recommandation: Améliorer le prompt Gemini")
    else:
        print("⚠️ Tests Gemini non effectués (clé API non fournie)")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Test de détection des lots avec Gemini")
    parser.add_argument("--file", help="Fichier Excel spécifique à tester")
    parser.add_argument("--test-dir", default="test_data", help="Répertoire contenant les fichiers de test")
    parser.add_argument("--gemini-key", help="Clé API Google Gemini")
    parser.add_argument("--all", action="store_true", help="Tester tous les fichiers du répertoire")
    
    args = parser.parse_args()
    
    if not args.gemini_key:
        print("⚠️ Clé Gemini non fournie - seule la méthode classique sera testée")
        print("💡 Utilisez --gemini-key pour tester avec l'IA")
    
    if args.file:
        # Test d'un fichier spécifique
        if not Path(args.file).exists():
            print(f"❌ Fichier non trouvé: {args.file}")
            return 1
        
        test_lot_detection_with_gemini(args.file, args.gemini_key)
        
    elif args.all:
        # Test de tous les fichiers du répertoire
        test_multiple_files(args.test_dir, args.gemini_key)
        
    else:
        print("❌ Spécifiez --file ou --all")
        print("\\nExemples d'utilisation:")
        print("  python test_gemini_lot_detection.py --file test_data/mon_fichier.xlsx --gemini-key YOUR_KEY")
        print("  python test_gemini_lot_detection.py --all --gemini-key YOUR_KEY")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
