"""
Script de test pour la détection des colonnes dans les fichiers DPGF

Ce script analyse un fichier Excel DPGF et affiche le résultat de la détection des colonnes
sans effectuer d'import réel dans la base de données.

Usage:
    python test_column_detection.py --file path/to/file.xlsx
"""

import argparse
import pandas as pd
from pathlib import Path
import re
from scripts.import_complete_improved import ExcelParser
import sys

def inspect_file(file_path):
    """Inspecte un fichier DPGF pour analyser sa structure et ses données"""
    print(f"\n📊 Analyse du fichier: {file_path}")
    
    # Charger le fichier
    parser = ExcelParser(file_path)
    
    # 1. Trouver la ligne d'en-tête et afficher son contenu
    header_row = parser.find_header_row()
    if header_row is not None:
        print(f"\n✓ Ligne d'en-tête trouvée: {header_row+1}")
        header_values = []
        for i, val in enumerate(parser.df.iloc[header_row]):
            if pd.notna(val):
                header_values.append(f"Col {i}: '{val}'")
        print("Contenu: " + ", ".join(header_values))
    else:
        print("❌ Aucune ligne d'en-tête détectée")
    
    # 2. Détecter les colonnes
    col_indices = parser.detect_column_indices(header_row)
    print("\n📋 Indices des colonnes détectés:")
    for col_name, idx in col_indices.items():
        if idx is not None:
            val = f"'{parser.df.iloc[header_row, idx]}'" if header_row is not None and idx < len(parser.df.columns) and pd.notna(parser.df.iloc[header_row, idx]) else "N/A"
            print(f"  - {col_name}: colonne {idx} ({val})")
        else:
            print(f"  - {col_name}: non détecté")
    
    # 3. Analyser quelques éléments pour vérifier l'extraction
    print("\n🔍 Test d'extraction des éléments:")
    start_row = header_row + 1 if header_row is not None else 5
    examined_count = 0
    
    # Chercher dans les 20 lignes suivant l'en-tête
    for i in range(start_row, min(start_row + 20, len(parser.df))):
        row = parser.df.iloc[i]
        
        # Ignorer les lignes vides
        if all(pd.isna(val) for val in row.values):
            continue
            
        # Vérifier si cette ligne contient des valeurs numériques (probable élément)
        has_numeric = False
        if col_indices['quantite'] is not None and col_indices['quantite'] < len(row):
            has_numeric = pd.notna(row.iloc[col_indices['quantite']])
        
        if not has_numeric and col_indices['prix_unitaire'] is not None and col_indices['prix_unitaire'] < len(row):
            has_numeric = pd.notna(row.iloc[col_indices['prix_unitaire']])
            
        if not has_numeric and col_indices['prix_total'] is not None and col_indices['prix_total'] < len(row):
            has_numeric = pd.notna(row.iloc[col_indices['prix_total']])
        
        if has_numeric:
            print(f"\n📝 Élément potentiel (ligne {i+1}):")
            
            # Extraire et afficher la désignation
            designation = ""
            if col_indices['designation'] is not None and col_indices['designation'] < len(row) and pd.notna(row.iloc[col_indices['designation']]):
                designation = str(row.iloc[col_indices['designation']])
                print(f"  Désignation: {designation[:50]}..." if len(designation) > 50 else f"  Désignation: {designation}")
            
            # Extraire et afficher l'unité
            unite = ""
            if col_indices['unite'] is not None and col_indices['unite'] < len(row) and pd.notna(row.iloc[col_indices['unite']]):
                unite = str(row.iloc[col_indices['unite']])
                print(f"  Unité: {unite}")
            
            # Extraire et afficher les valeurs numériques avec leurs formats originaux
            if col_indices['quantite'] is not None and col_indices['quantite'] < len(row) and pd.notna(row.iloc[col_indices['quantite']]):
                val_orig = row.iloc[col_indices['quantite']]
                val_conv = parser.safe_convert_to_float(val_orig)
                print(f"  Quantité: {val_orig} → {val_conv}")
            
            if col_indices['prix_unitaire'] is not None and col_indices['prix_unitaire'] < len(row) and pd.notna(row.iloc[col_indices['prix_unitaire']]):
                val_orig = row.iloc[col_indices['prix_unitaire']]
                val_conv = parser.safe_convert_to_float(val_orig)
                print(f"  Prix unitaire: {val_orig} → {val_conv}")
            
            if col_indices['prix_total'] is not None and col_indices['prix_total'] < len(row) and pd.notna(row.iloc[col_indices['prix_total']]):
                val_orig = row.iloc[col_indices['prix_total']]
                val_conv = parser.safe_convert_to_float(val_orig)
                print(f"  Prix total: {val_orig} → {val_conv}")
            
            examined_count += 1
            if examined_count >= 5:  # Limiter à 5 éléments pour éviter une sortie trop longue
                break
    
    # 4. Tester la détection des sections
    print("\n📑 Test de détection des sections:")
    section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+(.*)')
    title_pattern = re.compile(r'^([A-Z][A-Z\s\d\.]+)$')
    
    examined_count = 0
    for i in range(start_row, min(start_row + 30, len(parser.df))):
        row = parser.df.iloc[i]
        
        # Ignorer les lignes vides
        if all(pd.isna(val) for val in row.values):
            continue
        
        # Vérifier si cette ligne correspond à une section
        is_section = False
        if col_indices['designation'] is not None and col_indices['designation'] < len(row) and pd.notna(row.iloc[col_indices['designation']]):
            cell_text = str(row.iloc[col_indices['designation']]).strip()
            
            # Test 1: Section avec numéro
            match = section_pattern.match(cell_text)
            if match:
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                print(f"  Section numérotée (ligne {i+1}): {numero_section} - {titre_section}")
                is_section = True
            
            # Test 2: Titre en majuscules
            elif title_pattern.match(cell_text):
                print(f"  Section en majuscules (ligne {i+1}): {cell_text}")
                is_section = True
        
        if is_section:
            examined_count += 1
            if examined_count >= 3:  # Limiter à 3 sections
                break
    
    print("\n🏁 Analyse terminée")


def main():
    parser = argparse.ArgumentParser(description="Test de détection des colonnes dans un fichier DPGF")
    parser.add_argument("--file", required=True, help="Chemin du fichier Excel DPGF à analyser")
    
    args = parser.parse_args()
    
    # Vérifier l'existence du fichier
    if not Path(args.file).exists():
        print(f"Erreur: Le fichier {args.file} n'existe pas")
        sys.exit(1)
    
    inspect_file(args.file)


if __name__ == "__main__":
    main()
