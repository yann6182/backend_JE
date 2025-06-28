#!/usr/bin/env python3
"""
Script pour télécharger et tester directement un fichier DPGF du SharePoint
"""

import sys
import os
import tempfile
from pathlib import Path

# Ajouter le répertoire scripts au path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

try:
    from identify_relevant_files_sharepoint import SharePointClient
    from import_complete import DPGFImporter
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)

def test_specific_dpgf_file():
    """Télécharge et teste un fichier DPGF spécifique"""
    
    # Configuration SharePoint
    sharepoint_client = SharePointClient()
    
    # Nom du fichier à tester (celui des images montrées)
    target_filename = "3296-DCE-DPGF-Lot 08 MOBILIERS.xlsx"
    
    print(f"🔍 Recherche du fichier: {target_filename}")
    
    # Chercher le fichier dans le SharePoint
    try:
        # Lister les fichiers du dossier où nous savons qu'il y a des DPGF
        folder_path = "/0. A ENREGISTER SUR OPTIM"
        all_files = sharepoint_client.list_files_in_folder(folder_path, recursive=True)
        
        target_file = None
        for file_info in all_files:
            if target_filename in file_info['name']:
                target_file = file_info
                break
        
        if not target_file:
            print(f"❌ Fichier {target_filename} non trouvé")
            # Afficher les premiers fichiers pour debug
            print("\n📋 Fichiers trouvés (premiers 10):")
            for i, file_info in enumerate(all_files[:10]):
                if file_info['name'].endswith(('.xlsx', '.xls')):
                    print(f"  {i}: {file_info['name']}")
            return
        
        print(f"✅ Fichier trouvé: {target_file['name']}")
        
        # Télécharger le fichier
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        if sharepoint_client.download_file(target_file['id'], temp_path):
            print(f"📥 Fichier téléchargé: {temp_path}")
            
            # D'abord analyser la structure du fichier
            import pandas as pd
            try:
                # Vérifier la taille du fichier
                file_size = os.path.getsize(temp_path)
                print(f"   Taille fichier: {file_size} bytes")
                
                if file_size == 0:
                    print("❌ Fichier vide après téléchargement!")
                    return
                
                # Essayer de lire toutes les feuilles
                try:
                    xl_file = pd.ExcelFile(temp_path)
                    print(f"   Feuilles disponibles: {xl_file.sheet_names}")
                    
                    # Essayer de lire toutes les feuilles pour trouver des données
                    for sheet_name in xl_file.sheet_names:
                        try:
                            df_sheet = pd.read_excel(temp_path, sheet_name=sheet_name, header=None)
                            print(f"   Feuille '{sheet_name}': {df_sheet.shape[0]} lignes x {df_sheet.shape[1]} colonnes")
                            
                            if df_sheet.shape[0] > 0 and df_sheet.shape[1] > 0:
                                print(f"\n📋 Aperçu de la feuille '{sheet_name}' (premières 10 lignes):")
                                for i in range(min(10, df_sheet.shape[0])):
                                    row_values = [str(val) if pd.notna(val) else "" for val in df_sheet.iloc[i].values]
                                    truncated_values = [val[:30] + "..." if len(val) > 30 else val for val in row_values]
                                    print(f"     Ligne {i}: {truncated_values}")
                                
                                # Si on trouve une feuille avec des données, on l'utilise pour le test
                                if 'mobilier' in sheet_name.lower() or 'dpgf' in sheet_name.lower():
                                    print(f"\n🎯 Feuille de données identifiée: {sheet_name}")
                                    df = df_sheet
                                    break
                            else:
                                print(f"     ⚠️ Feuille '{sheet_name}' vide")
                        except Exception as e:
                            print(f"     ❌ Erreur lecture feuille '{sheet_name}': {e}")
                    
                except Exception as sheet_error:
                    print(f"   ❌ Erreur lecture feuilles: {sheet_error}")
                    # Essayer lecture standard
                    df = pd.read_excel(temp_path, header=None)
                    print(f"   Lecture standard: {df.shape[0]} lignes x {df.shape[1]} colonnes")
                    
            except Exception as e:
                print(f"⚠️ Erreur lecture Excel: {e}")
                # Vérifier si c'est vraiment un fichier Excel
                with open(temp_path, 'rb') as f:
                    header = f.read(8)
                    print(f"   En-tête fichier (hex): {header.hex()}")
                return
            
            # Tester l'import avec debug
            importer = DPGFImporter(
                base_url="http://127.0.0.1:8000",
                debug=True,
                dry_run=True  # Mode simulation pour éviter les erreurs API
            )
            
            print(f"\n🧪 Test d'import avec debug:")
            try:
                result = importer.import_file(
                    file_path=temp_path,
                    original_filename=target_file['name']
                )
                print(f"✅ Test terminé, résultat: {result}")
            except Exception as e:
                print(f"❌ Erreur lors du test: {e}")
                import traceback
                traceback.print_exc()
            
            # Nettoyer
            try:
                os.unlink(temp_path)
            except:
                pass
        else:
            print(f"❌ Échec du téléchargement")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_specific_dpgf_file()
