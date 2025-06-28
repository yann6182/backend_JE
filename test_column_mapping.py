#!/usr/bin/env python3
"""
Test script pour vérifier la fonctionnalité de mapping interactif des colonnes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.import_complete import ExcelParser, ColumnMapping, ErrorReporter

def test_column_mapping():
    """Test de la fonctionnalité de mapping des colonnes"""
    print("🧪 Test du mapping interactif des colonnes")
    
    # Créer les composants nécessaires
    column_mapper = ColumnMapping()
    error_reporter = ErrorReporter()
    
    # Créer le parser avec un fichier de test
    test_file = "test_data/02_2024_024_BPU_lot_7.xlsx"
    parser = ExcelParser(test_file, column_mapper, error_reporter, dry_run=True)
    
    try:
        # Tenter la détection automatique
        print(f"\n📊 Analyse du fichier: {test_file}")
        
        # Ouvrir le fichier Excel et analyser la première feuille
        import pandas as pd
        df = pd.read_excel(test_file, header=None)
        print(f"✓ Fichier lu: {df.shape[0]} lignes, {df.shape[1]} colonnes")
        
        # Afficher les 10 premières lignes pour voir la structure
        print("\n📋 Aperçu des premières lignes:")
        for i in range(min(10, df.shape[0])):
            row_values = []
            for j in range(min(8, df.shape[1])):  # Limiter à 8 colonnes pour la lisibilité
                value = df.iloc[i, j]
                if pd.notna(value):
                    str_val = str(value)[:30]  # Limiter à 30 caractères
                else:
                    str_val = ""
                row_values.append(str_val)
            print(f"Ligne {i}: {row_values}")
        
        # Essayer de détecter la ligne d'en-tête
        header_row_idx = parser.find_header_row()
        if header_row_idx is not None:
            print(f"\n🎯 Ligne d'en-tête détectée: {header_row_idx}")
            headers = df.iloc[header_row_idx].tolist()
            print(f"En-têtes: {headers[:8]}...")  # Afficher les 8 premiers
            
            # Tester la détection des colonnes
            col_indices = parser.detect_column_indices(header_row_idx)
            print(f"\n🔍 Colonnes détectées:")
            for col_name, col_idx in col_indices.items():
                if col_idx is not None:
                    header_value = headers[col_idx] if col_idx < len(headers) else "N/A"
                    print(f"  {col_name}: colonne {col_idx} ({header_value})")
                else:
                    print(f"  {col_name}: NON DÉTECTÉE")
        else:
            print("\n❌ Aucune ligne d'en-tête détectée")
            
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_column_mapping()
