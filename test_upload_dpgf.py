#!/usr/bin/env python3
"""
Script de test pour l'upload et l'import automatique de fichiers DPGF
"""

import requests
import sys
from pathlib import Path

def upload_dpgf_file(file_path: str, api_url: str = "http://localhost:8000"):
    """
    Upload un fichier DPGF via l'API et lance l'import automatique
    
    Args:
        file_path: Chemin vers le fichier Excel DPGF
        api_url: URL de l'API (par défaut: http://localhost:8000)
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ Fichier non trouvé: {file_path}")
        return False
    
    if not file_path.suffix.lower() in ['.xlsx', '.xls']:
        print(f"❌ Le fichier doit être un fichier Excel (.xlsx ou .xls)")
        return False
    
    print(f"📁 Upload du fichier: {file_path.name}")
    
    try:
        # Préparer le fichier pour l'upload
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            # Envoyer la requête d'upload
            response = requests.post(f"{api_url}/api/v1/dpgf/upload", files=files)
            response.raise_for_status()
            
            result = response.json()
            print(f"✅ {result['message']}")
            print(f"📊 Fichier: {result['filename']}")
            print(f"🔄 Statut: {result['status']}")
            
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de l'upload: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Détail: {error_detail.get('detail', 'Erreur inconnue')}")
            except:
                print(f"   Réponse: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False

def check_import_status(api_url: str = "http://localhost:8000"):
    """
    Vérifie le statut des imports en cours
    """
    try:
        response = requests.get(f"{api_url}/api/v1/dpgf/import-status")
        response.raise_for_status()
        
        result = response.json()
        print(f"📊 Statut des imports: {result['status']}")
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification du statut: {e}")

def main():
    """Point d'entrée du script"""
    if len(sys.argv) < 2:
        print("Usage: python test_upload_dpgf.py <chemin_vers_fichier_excel>")
        print("Exemple: python test_upload_dpgf.py test_data/802\\ DPGF\\ Lot\\ 2\\ -\\ Curage.xlsx")
        sys.exit(1)
    
    file_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    print("🚀 Test d'upload et d'import automatique de fichier DPGF")
    print(f"🌐 API URL: {api_url}")
    print("-" * 60)
    
    # Upload du fichier
    if upload_dpgf_file(file_path, api_url):
        print("-" * 60)
        print("✅ Upload réussi ! L'import est en cours de traitement en arrière-plan.")
        print("💡 Vous pouvez vérifier le statut avec l'endpoint /api/v1/dpgf/import-status")
        
        # Vérifier le statut
        check_import_status(api_url)
    else:
        print("❌ Upload échoué.")
        sys.exit(1)

if __name__ == "__main__":
    main()
