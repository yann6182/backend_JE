#!/usr/bin/env python3
"""
Script de debug pour analyser la détection des lots dans les fichiers DPGF.
Aide à identifier pourquoi certains lots ne sont pas détectés.
"""

import sys
import os
import re
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional

# Ajouter le répertoire scripts au path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

try:
    from import_complete import ExcelParser
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)

def test_filename_patterns(filename: str) -> List[Tuple[str, str, str]]:
    """
    Teste tous les patterns de détection de lot sur un nom de fichier.
    
    Returns:
        Liste de (pattern_name, numero_lot, nom_lot) pour tous les matches
    """
    results = []
    filename_stem = Path(filename).stem
    
    patterns = [
        ("LOT XX - DPGF - NOM", r'lot\s*(\d+)\s*-\s*(?:dpgf|devis)\s*-\s*([\w\s-]+)'),
        ("LOT XX - NOM", r'lot\s*(\d+)\s*-\s*([\w\s-]+)'),
        ("DPGF Lot X - NOM", r'dpgf\s*lot\s*(\d+)\s*-\s*([\w\s-]+)'),
        ("LotXX-NOM", r'lot\s*(\d+)[_\-\s]+([\w\s-]+)'),
        ("LotX", r'lot\s*(\d+)'),
        ("XX NOM", r'(\d{1,2})\s+([\w\s-]+)'),
        ("Dernière chance", r'(\d{1,2})'),
    ]
    
    for pattern_name, pattern in patterns:
        match = re.search(pattern, filename_stem, re.IGNORECASE)
        if match:
            try:
                numero_lot = match.group(1).strip()
                if len(match.groups()) > 1 and match.group(2):
                    nom_lot = match.group(2).strip()
                else:
                    nom_lot = f"Lot {numero_lot}"
                
                # Validation du numéro de lot pour le pattern de dernière chance
                if pattern_name == "Dernière chance":
                    if not (1 <= int(numero_lot) <= 99):
                        continue
                
                results.append((pattern_name, numero_lot, nom_lot))
            except:
                pass
    
    return results

def test_content_detection(filepath: str) -> List[Tuple[str, str]]:
    """
    Teste la détection de lot dans le contenu du fichier.
    
    Returns:
        Liste de (numero_lot, nom_lot) trouvés dans le contenu
    """
    try:
        parser = ExcelParser(filepath)
        lots = []
        
        # Pattern utilisé dans le code original
        pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
        
        # Parcourir les 15 premières lignes
        for i in range(min(15, len(parser.df))):
            for col in parser.df.columns:
                cell_value = parser.df.iloc[i, col]
                if pd.notna(cell_value):
                    cell_str = str(cell_value).strip()
                    match = pattern.search(cell_str)
                    if match:
                        numero_lot = match.group(1).strip()
                        nom_lot = match.group(2).strip()
                        lots.append((numero_lot, nom_lot))
        
        return lots
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse du contenu de {filepath}: {e}")
        return []

def analyze_file(filepath: str) -> None:
    """Analyse complète d'un fichier DPGF."""
    filename = Path(filepath).name
    print(f"\n🔍 ANALYSE: {filename}")
    print("=" * 60)
    
    # Test des patterns de nom de fichier
    print("📄 DÉTECTION DEPUIS LE NOM DE FICHIER:")
    filename_results = test_filename_patterns(filename)
    
    if filename_results:
        for i, (pattern_name, numero, nom) in enumerate(filename_results, 1):
            print(f"   {i}. Pattern '{pattern_name}': Lot {numero} - {nom}")
        
        # Le premier résultat est celui qui serait utilisé
        first_result = filename_results[0]
        print(f"   ✅ SÉLECTIONNÉ: Lot {first_result[1]} - {first_result[2]}")
    else:
        print("   ❌ Aucun lot détecté depuis le nom de fichier")
    
    # Test de détection dans le contenu
    print("\n📄 DÉTECTION DEPUIS LE CONTENU:")
    if os.path.exists(filepath):
        content_results = test_content_detection(filepath)
        
        if content_results:
            for i, (numero, nom) in enumerate(content_results, 1):
                print(f"   {i}. Contenu: Lot {numero} - {nom}")
        else:
            print("   ❌ Aucun lot détecté dans le contenu")
    else:
        print("   ⚠️ Fichier non trouvé, test du contenu ignoré")
    
    # Résumé
    print("\n📋 RÉSUMÉ:")
    has_filename_detection = bool(filename_results)
    has_content_detection = bool(content_results) if os.path.exists(filepath) else False
    
    if has_filename_detection:
        print("   ✅ Détection depuis nom de fichier: OUI")
    else:
        print("   ❌ Détection depuis nom de fichier: NON")
    
    if os.path.exists(filepath):
        if has_content_detection:
            print("   ✅ Détection depuis contenu: OUI")
        else:
            print("   ❌ Détection depuis contenu: NON")
    
    if not has_filename_detection and not has_content_detection:
        print("   🚨 PROBLÈME: Aucune méthode ne détecte de lot!")
    elif has_filename_detection:
        print("   ✅ OK: Lot sera détecté (priorité nom de fichier)")

def main():
    """Fonction principale."""
    print("🧪 DIAGNOSTIC DE DÉTECTION DES LOTS DPGF")
    print("=" * 60)
    
    # Lister tous les fichiers Excel dans test_data
    test_data_dir = Path(__file__).parent / "test_data"
    
    if not test_data_dir.exists():
        print(f"❌ Répertoire {test_data_dir} non trouvé")
        return
    
    excel_files = list(test_data_dir.glob("*.xlsx")) + list(test_data_dir.glob("*.xls"))
    
    if not excel_files:
        print(f"❌ Aucun fichier Excel trouvé dans {test_data_dir}")
        return
    
    print(f"📁 {len(excel_files)} fichiers Excel trouvés")
    
    # Analyser chaque fichier
    for filepath in sorted(excel_files):
        analyze_file(str(filepath))
    
    # Tests de cas problématiques potentiels
    print("\n🧪 TESTS DE CAS PROBLÉMATIQUES:")
    print("=" * 60)
    
    problematic_cases = [
        "fichier_sans_numero.xlsx",
        "Document-métallerie.xlsx", 
        "DEVIS-serrurerie-v2.xlsx",
        "BPU_travaux_divers.xlsx",
        "DPGF complet 2024.xlsx",
        "Lot_11_plomberie.xlsx",
        "100_DPGF_Lot_25.xlsx",  # Numéro > 99
        "LOT0_test.xlsx",  # Numéro 0
        "lot-final.xlsx",  # Pas de numéro
    ]
    
    for filename in problematic_cases:
        fake_filepath = test_data_dir / filename
        analyze_file(str(fake_filepath))

if __name__ == "__main__":
    main()
