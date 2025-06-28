#!/usr/bin/env python3
"""
Script de test pour analyser un fichier DPGF spécifique du SharePoint
"""

import sys
import os
from pathlib import Path
import tempfile

# Ajouter le répertoire scripts au path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from import_complete import ExcelParser, ColumnMapping, ErrorReporter
import pandas as pd

def test_sharepoint_file():
    """Test d'analyse d'un fichier du SharePoint"""
    
    # Créer un fichier temporaire test avec une structure DPGF typique
    print("🧪 Test d'analyse de structure DPGF")
    
    # Simuler un fichier DPGF/BPU typique
    data = {
        'A': ['', '', 'BORDEREAU DE PRIX UNITAIRES', '', 'N°', '1.1', '1.1.1', '1.1.2', '1.2', '1.2.1'],
        'B': ['', '', 'LOT 08 - MOBILIERS', '', 'DESIGNATION', 'MOBILIER BUREAU', 'Bureau standard 120x60', 'Chaise ergonomique', 'MOBILIER TECHNIQUE', 'Armoire technique'],
        'C': ['', '', '', '', 'U', '', 'U', 'U', '', 'U'],
        'D': ['', '', '', '', 'P.U. HT', '', '350.00', '120.00', '', '450.00'],
        'E': ['', '', '', '', 'QTE', '', '10', '20', '', '5'],
        'F': ['', '', '', '', 'TOTAL HT', '', '3500.00', '2400.00', '', '2250.00']
    }
    
    df = pd.DataFrame(data)
    
    # Créer un fichier Excel temporaire
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        tmp_path = tmp_file.name
        df.to_excel(tmp_path, index=False, header=False)
    
    try:
        print(f"\n📊 Analyse du fichier test: {tmp_path}")
        
        # Créer les composants
        column_mapper = ColumnMapping()
        error_reporter = ErrorReporter()
        parser = ExcelParser(tmp_path, column_mapper, error_reporter, dry_run=True)
        
        # Afficher le contenu du fichier
        print("\n📋 Contenu du fichier:")
        for i in range(len(parser.df)):
            row_values = [str(val) if pd.notna(val) else "" for val in parser.df.iloc[i].values]
            print(f"Ligne {i}: {row_values}")
        
        # Détecter la ligne d'en-tête
        header_row = parser.find_header_row()
        print(f"\n🎯 Ligne d'en-tête détectée: {header_row}")
        
        if header_row is not None:
            # Analyser les colonnes
            col_indices = parser.detect_column_indices(header_row)
            print(f"\n🔍 Colonnes détectées:")
            for col_name, col_idx in col_indices.items():
                if col_idx is not None:
                    header_value = parser.df.iloc[header_row, col_idx] if col_idx < len(parser.df.columns) else "N/A"
                    print(f"  {col_name}: colonne {col_idx} ({header_value})")
                else:
                    print(f"  {col_name}: NON DÉTECTÉE")
            
            # Détecter les sections et éléments
            items = parser.detect_sections_and_elements(header_row)
            print(f"\n📊 Items détectés: {len(items)}")
            for item in items:
                print(f"  Ligne {item['row']}: {item['type']} - {item['data']}")
        
        # Tester la détection de lot
        lots = parser.find_lot_headers()
        print(f"\n🏷️ Lots détectés: {lots}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Nettoyer
        try:
            os.unlink(tmp_path)
        except:
            pass

if __name__ == "__main__":
    test_sharepoint_file()
