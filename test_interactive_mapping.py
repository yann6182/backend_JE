#!/usr/bin/env python3
"""
Test du mapping interactif avec headers ambigus
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.import_complete import ExcelParser, ColumnMapping, ErrorReporter
import pandas as pd
import tempfile

def test_interactive_mapping():
    """Test avec headers ambigus pour déclencher le mapping interactif"""
    print("🧪 Test du mapping interactif avec headers ambigus")
    
    # Créer un fichier Excel temporaire avec headers ambigus
    data = {
        'Col1': ['Description A', 'Description B', 'Description C'],
        'Col2': ['Item', 'Piece', 'Unit'],
        'Col3': [10, 20, 30],
        'Col4': [100.0, 200.0, 300.0],
        'Col5': [1000.0, 4000.0, 9000.0]
    }
    
    df = pd.DataFrame(data)
    
    # Créer un fichier temporaire
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        tmp_path = tmp_file.name
        df.to_excel(tmp_path, index=False)
    
    try:
        # Créer les composants
        column_mapper = ColumnMapping()
        error_reporter = ErrorReporter()
        parser = ExcelParser(tmp_path, column_mapper, error_reporter, dry_run=True)
        
        print(f"\n📊 Fichier test créé: {tmp_path}")
        
        # Lire le fichier pour vérifier
        test_df = pd.read_excel(tmp_path, header=None)
        print(f"✓ Contenu du fichier test:")
        for i in range(test_df.shape[0]):
            print(f"  Ligne {i}: {test_df.iloc[i].tolist()}")
        
        # Détecter la ligne d'en-tête
        header_row_idx = parser.find_header_row()
        print(f"\n🎯 Ligne d'en-tête détectée: {header_row_idx}")
        
        if header_row_idx is not None:
            # Tester la détection automatique
            col_indices = parser.detect_column_indices(header_row_idx)
            print(f"\n🔍 Résultat du mapping automatique:")
            for col_name, col_idx in col_indices.items():
                print(f"  {col_name}: {col_idx}")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Nettoyer le fichier temporaire
        try:
            os.unlink(tmp_path)
        except:
            pass

if __name__ == "__main__":
    test_interactive_mapping()
