"""
Script de test pour l'import de DPGF
"""

import sys
import os
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.dpgf_import import DPGFImportService

def test_import(file_path: str):
    """Test l'import d'un fichier DPGF et affiche les résultats détaillés"""
    print(f"\n=== TEST IMPORT DPGF: {file_path} ===\n")
    
    # Créer une session de base de données
    db: Session = SessionLocal()
    try:
        # Créer le service d'import
        import_service = DPGFImportService(debug=True)
        
        # Importer le fichier
        print(f"Lancement de l'import...")
        dpgf_id = import_service.import_file(db, file_path)
        
        if dpgf_id:
            print(f"\n✅ DPGF importé avec succès (ID: {dpgf_id})")
            
            # Afficher les statistiques
            print(f"\nStatistiques d'import:")
            print(f"   - Lots créés: {import_service.stats.lots_created}, réutilisés: {import_service.stats.lots_reused}")
            print(f"   - Sections créées: {import_service.stats.sections_created}, réutilisées: {import_service.stats.sections_reused}")
            print(f"   - Éléments créés: {import_service.stats.elements_created}")
            print(f"   - Erreurs: {import_service.stats.errors}")
            
            # Vérifier que des sections et des éléments ont été créés
            if import_service.stats.sections_created == 0:
                print("\n❌ ATTENTION: Aucune section n'a été créée")
            else:
                print(f"\n✓ {import_service.stats.sections_created} sections créées")
                
            if import_service.stats.elements_created == 0:
                print("❌ ATTENTION: Aucun élément d'ouvrage n'a été créé")
            else:
                print(f"✓ {import_service.stats.elements_created} éléments d'ouvrage créés")
        else:
            print("\n❌ Erreur: L'import a échoué")
    
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_upload_dpgf.py <fichier_dpgf.xlsx>")
        print("\nFichiers disponibles:")
        
        # Lister les fichiers .xlsx dans le dossier test_data
        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        if os.path.exists(test_data_dir):
            excel_files = [f for f in os.listdir(test_data_dir) if f.endswith(".xlsx")]
            for i, file in enumerate(excel_files):
                print(f"{i+1}. {file}")
                
            # Si des fichiers sont disponibles, proposer d'utiliser le premier
            if excel_files:
                default_file = os.path.join(test_data_dir, excel_files[0])
                print(f"\nUtilisation du premier fichier: {excel_files[0]}")
                test_import(default_file)
            else:
                print("Aucun fichier Excel trouvé dans le dossier test_data")
        else:
            print(f"Dossier test_data non trouvé: {test_data_dir}")
    else:
        file_path = sys.argv[1]
        test_import(file_path)
