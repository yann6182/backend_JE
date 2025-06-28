#!/usr/bin/env python3
"""
Script pour télécharger et tester directement un fichier DPGF du SharePoint avec IMPORT RÉEL
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

def test_specific_dpgf_file_real_import():
    """Télécharge et teste un fichier DPGF spécifique avec IMPORT RÉEL"""
    
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
            return False
            
        print(f"✅ Fichier trouvé: {target_file['name']}")
        
        # Télécharger le fichier vers un fichier temporaire
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Download directly to the temp file
            sharepoint_client.download_file(target_file['download_url'], temp_path)
            
            # Get file size for info
            file_size = os.path.getsize(temp_path)
            
            file_size = os.path.getsize(temp_path)
            print(f"📥 Fichier téléchargé: {temp_path}")
            print(f"   Taille fichier: {file_size} bytes")
            
            print(f"🧪 Test d'import RÉEL (pas de dry-run):")
            
            # Initialiser l'importeur SANS dry_run
            importer = DPGFImporter(
                debug=True,
                dry_run=False  # IMPORT RÉEL
            )
            
            # Lancer l'import
            result = importer.import_file(temp_path)
            
            if result == 0:
                print("✅ Import réussi!")
                return True
            else:
                print(f"❌ Import échoué, code: {result}")
                return False
                
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_specific_dpgf_file_real_import()
    print(f"✅ Test terminé, résultat: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)