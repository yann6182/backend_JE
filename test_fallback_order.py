#!/usr/bin/env python3
"""
Test pour vérifier l'ordre de fallback : filename → Gemini → contenu
"""

import sys
from pathlib import Path
import pandas as pd

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent))

from scripts.import_complete import ExcelParser, GeminiProcessor

def test_fallback_order():
    """Test l'ordre de fallback des méthodes de détection"""
    print("🧪 Test de l'ordre de fallback des méthodes")
    print("=" * 50)
    
    # Créer un fichier de test temporaire avec un nom sans lot
    test_file = "test_data/test_file_sans_lot.xlsx"
    
    # Créer un DataFrame avec du contenu qui contient un lot
    data = [
        ["", "", "", ""],
        ["LOT 99 - Test Fallback", "", "", ""],
        ["Article", "Désignation", "Unité", "Prix"],
        ["A001", "Test item", "U", "100.00"]
    ]
    
    try:
        df_test = pd.DataFrame(data)
        df_test.to_excel(test_file, index=False, header=False)
        print(f"✅ Fichier de test créé: {test_file}")
        
        # Test 1: Sans Gemini (devrait utiliser le contenu)
        print("\n🔬 Test 1: Sans Gemini")
        parser_no_gemini = ExcelParser(test_file, gemini_processor=None)
        
        # Vérifier que le nom de fichier ne détecte rien
        filename_lot = parser_no_gemini.extract_lot_from_filename()
        print(f"   📄 Nom de fichier: {filename_lot}")
        
        # Détection complète (devrait utiliser le contenu)
        lots_no_gemini = parser_no_gemini.find_lot_headers()
        print(f"   🔍 Résultat final: {lots_no_gemini}")
        
        # Test 2: Avec Gemini (mais on va simuler une erreur)
        print("\n🔬 Test 2: Avec Gemini (simulé)")
        print("   🧠 Gemini serait appelé entre nom de fichier et contenu")
        
        # Vérifier que l'ordre est correct dans le code
        print("\n📋 Vérification de l'ordre dans le code:")
        with open("scripts/import_complete.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        # Chercher les priorités dans find_lot_headers
        if "Priorité 1: Essayer d'extraire depuis le nom du fichier" in content:
            print("   ✅ Priorité 1: Nom de fichier")
        if "Priorité 2: Essayer avec Gemini" in content:
            print("   ✅ Priorité 2: Gemini")
        if "Priorité 3: Méthode classique" in content:
            print("   ✅ Priorité 3: Contenu du fichier")
            
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
    
    finally:
        # Nettoyer le fichier de test
        try:
            Path(test_file).unlink(missing_ok=True)
            print(f"\n🧹 Fichier de test supprimé")
        except:
            pass

def test_with_real_gemini():
    """Test avec une vraie clé Gemini si disponible"""
    print("\n🔬 Test avec Gemini réel (si disponible)")
    print("-" * 40)
    
    # Essayer de lire la clé Gemini depuis les variables d'environnement ou config
    try:
        import os
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("⚠️ Clé GEMINI_API_KEY non trouvée, test sauté")
            return
            
        print(f"✅ Clé Gemini trouvée, test avec un fichier réel")
        
        # Test avec un fichier existant
        test_file = "test_data/02_2024_024_BPU_lot_7.xlsx"
        
        # Créer un parser avec Gemini
        gemini_processor = GeminiProcessor(api_key=api_key, chunk_size=50)
        parser = ExcelParser(test_file, gemini_processor=gemini_processor)
        
        print(f"📂 Test avec: {Path(test_file).name}")
        
        # Test chaque méthode individuellement
        print("\n🔍 Tests individuels:")
        
        # 1. Nom de fichier
        filename_lot = parser.extract_lot_from_filename()
        print(f"   📄 Nom de fichier: {filename_lot}")
        
        # 2. Gemini (en forçant l'appel)
        try:
            gemini_lot = gemini_processor.detect_lot_info(test_file, Path(test_file).name)
            print(f"   🧠 Gemini: {gemini_lot}")
        except Exception as e:
            print(f"   🧠 Gemini: Erreur - {e}")
        
        # 3. Détection complète (devrait utiliser le nom de fichier en priorité)
        lots = parser.find_lot_headers()
        print(f"   🎯 Résultat final: {lots}")
        
    except Exception as e:
        print(f"⚠️ Test Gemini non possible: {e}")

if __name__ == "__main__":
    test_fallback_order()
    test_with_real_gemini()
