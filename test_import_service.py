"""
Script de test pour le service d'import DPGF
Ce script teste directement le service d'import sans passer par l'API
"""
import os
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Importer les modules nécessaires
from app.db.session import SessionLocal
from app.services.dpgf_import import DPGFImportService

def test_import_service():
    """Teste le service d'import sur un fichier DPGF d'exemple"""
    print("=== Test du service d'import DPGF ===")
    
    # Ouvrir une session DB
    db = SessionLocal()
    
    try:
        # Chemin vers un fichier DPGF d'exemple
        test_files_dir = Path("test_data")
        if not test_files_dir.exists():
            print(f"❌ Répertoire test_data introuvable: {test_files_dir.absolute()}")
            return
          # Lister les fichiers de test disponibles
        print("Fichiers de test disponibles:")
        test_files = list(test_files_dir.glob("*.xlsx"))
        
        if not test_files:
            print("❌ Aucun fichier XLSX trouvé dans test_data/")
            return
            
        for i, file_path in enumerate(test_files):
            print(f"  {i+1}. {file_path.name}")
            
        # Demander quel fichier tester
        print("\nQuel fichier voulez-vous tester?")
        print("1. Tester tous les fichiers")
        print("2-7. Tester un fichier spécifique (2=premier fichier, etc.)")
        choice = input("Votre choix (1-7): ")
        
        test_files_to_process = []
        
        if choice == "1":
            # Tester tous les fichiers
            test_files_to_process = test_files
        elif choice.isdigit() and 2 <= int(choice) <= len(test_files) + 1:
            # Tester un fichier spécifique
            test_files_to_process = [test_files[int(choice) - 2]]
        else:
            # Par défaut, tester le premier fichier
            test_files_to_process = [test_files[0]]
              # Tester chaque fichier sélectionné
        for test_file in test_files_to_process:
            print(f"\n{'=' * 80}")
            print(f"FICHIER: {test_file}")
            print(f"{'=' * 80}")
            
            # Créer le service d'import
            import_service = DPGFImportService(use_gemini=False, debug=True)
            
            print("\nDémarrage de l'import...")
            # Lancer l'import
            dpgf_id = import_service.import_file(db, str(test_file))
            
            if not dpgf_id:
                print("❌ Échec de l'import")
                continue
                
            print(f"\n✅ Import réussi! DPGF ID: {dpgf_id}")
            
            # Afficher les statistiques d'import
            print("\nStatistiques d'import:")
            print(f"- Lots créés: {import_service.stats.lots_created}")
            print(f"- Lots réutilisés: {import_service.stats.lots_reused}")
            print(f"- Sections créées: {import_service.stats.sections_created}")
            print(f"- Sections réutilisées: {import_service.stats.sections_reused}")
            print(f"- Éléments créés: {import_service.stats.elements_created}")
            print(f"- Erreurs: {import_service.stats.errors}")
            
            # Vérifier si des sections et des éléments ont été importés
            if import_service.stats.sections_created == 0:
                print("\n⚠️ Attention: Aucune section n'a été créée!")
            else:
                print(f"\n✅ {import_service.stats.sections_created} sections créées avec succès")
                
            if import_service.stats.elements_created == 0:
                print("\n⚠️ Attention: Aucun élément d'ouvrage n'a été créé!")
            else:
                print(f"\n✅ {import_service.stats.elements_created} éléments d'ouvrage créés avec succès")
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_import_service()
