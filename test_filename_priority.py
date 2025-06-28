#!/usr/bin/env python3
"""
Test pour vérifier que la détection de lot priorise bien le nom de fichier
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.append(str(Path(__file__).parent))

from scripts.import_complete import ExcelParser, GeminiProcessor

def test_filename_priority():
    """Test la priorité de détection des lots"""
    print("🧪 Test de priorité de détection des lots")
    print("=" * 50)
    
    # Tester avec plusieurs fichiers de test
    test_files = [
        "02_2024_024_BPU_lot_7.xlsx",
        "25S012 - DPGF -Lot4.xlsx", 
        "802 DPGF Lot 2 - Curage.xlsx",
        "803 DPGF Lot 3 - Gros-oeuvre - Démolition.xlsx",
        "804 DPGF Lot 4 - Charpente & Ossature bois - Ind B.xlsx",
        "DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx",
        "LOT 06 - DPGF - METALLERIE_.xlsx"
    ]
    
    # Initialiser Gemini si disponible
    gemini_processor = None
    try:
        import google.generativeai as genai
        # On peut tester sans clé API pour voir le fallback
        gemini_processor = GeminiProcessor(api_key="test", chunk_size=50)
        print("✅ Gemini processor initialisé (mode test)")
    except:
        print("⚠️ Gemini non disponible")
    
    results = []
    
    for filename in test_files:
        file_path = f"test_data/{filename}"
        print(f"\n📂 Test du fichier: {filename}")
        print("-" * 40)
        
        try:
            # Créer l'analyseur
            parser = ExcelParser(file_path, gemini_processor=None)  # Sans Gemini d'abord
            
            # Test 1: Detection depuis le nom de fichier uniquement
            filename_lot = parser.extract_lot_from_filename()
            if filename_lot:
                print(f"  📄 Nom de fichier → Lot {filename_lot[0]}: {filename_lot[1]}")
            else:
                print(f"  📄 Nom de fichier → Aucun lot détecté")
            
            # Test 2: Detection complète (avec toutes les priorités)
            lots = parser.find_lot_headers()
            if lots:
                print(f"  🔍 Détection complète → Lot {lots[0][0]}: {lots[0][1]}")
            else:
                print(f"  🔍 Détection complète → Aucun lot détecté")
            
            results.append({
                'filename': filename,
                'filename_detection': filename_lot,
                'full_detection': lots[0] if lots else None
            })
            
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            results.append({
                'filename': filename,
                'filename_detection': None,
                'full_detection': None,
                'error': str(e)
            })
    
    # Résumé des résultats
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES RÉSULTATS")
    print("=" * 60)
    
    filename_success = 0
    total_success = 0
    
    for result in results:
        print(f"\n📂 {result['filename']}")
        if result.get('error'):
            print(f"   ❌ Erreur: {result['error']}")
        else:
            if result['filename_detection']:
                print(f"   ✅ Nom fichier: Lot {result['filename_detection'][0]} - {result['filename_detection'][1]}")
                filename_success += 1
            else:
                print(f"   ⚠️ Nom fichier: Non détecté")
            
            if result['full_detection']:
                print(f"   ✅ Total: Lot {result['full_detection'][0]} - {result['full_detection'][1]}")
                total_success += 1
            else:
                print(f"   ❌ Total: Non détecté")
    
    print(f"\n📈 STATISTIQUES:")
    print(f"   Détection par nom de fichier: {filename_success}/{len(test_files)} ({filename_success/len(test_files)*100:.1f}%)")
    print(f"   Détection totale: {total_success}/{len(test_files)} ({total_success/len(test_files)*100:.1f}%)")
    
    # Vérifier la priorité
    priority_correct = all(
        result.get('filename_detection') == result.get('full_detection') 
        for result in results 
        if result.get('filename_detection') and not result.get('error')
    )
    
    if priority_correct:
        print("✅ La priorité du nom de fichier est respectée!")
    else:
        print("⚠️ Attention: La priorité du nom de fichier pourrait ne pas être respectée")

if __name__ == "__main__":
    test_filename_priority()
