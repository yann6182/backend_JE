#!/usr/bin/env python3
"""
Script de test pour la fonction de listing rapide SharePoint
Permet de tester l'accès et la navigation dans SharePoint
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au PATH pour les imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    from scripts.identify_relevant_files_sharepoint import SharePointClient
    print("✅ Module SharePoint importé avec succès")
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print("Assurez-vous que les dépendances SharePoint sont installées :")
    print("pip install -r requirements_sharepoint.txt")
    sys.exit(1)

def test_sharepoint_access():
    """Test d'accès SharePoint avec la fonction de listing rapide"""
    
    print("🧪 Test d'accès SharePoint - Listing rapide")
    print("=" * 50)
    
    # Vérifier les variables d'environnement
    required_vars = ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'GRAPH_DRIVE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables d'environnement manquantes : {', '.join(missing_vars)}")
        print("Veuillez configurer le fichier .env avec :")
        for var in missing_vars:
            print(f"  {var}=votre-valeur")
        return False
    
    print("✅ Variables d'environnement configurées")
    
    # Créer le client SharePoint
    try:
        client = SharePointClient()
        print("✅ Client SharePoint créé")
    except Exception as e:
        print(f"❌ Erreur lors de la création du client : {e}")
        return False
    
    # Tester différents dossiers
    test_folders = [
        "/",
        "/Documents partages",
        "/Documents partages/General",
        "/Shared Documents"  # Nom anglais alternatif
    ]
    
    for folder in test_folders:
        print(f"\n📁 Test du dossier : {folder}")
        print("-" * 40)
        
        try:
            files = client.list_first_10_files(folder)
            
            if files:
                print(f"✅ Accès réussi ! Trouvé {len(files)} éléments :")
                for i, file_info in enumerate(files, 1):
                    type_icon = "📁" if file_info['type'] == 'folder' else "📄"
                    size_str = f"{file_info['size']/1024/1024:.1f} MB" if file_info['size'] > 0 else "-"
                    print(f"  {i:2d}. {type_icon} {file_info['name']} ({size_str})")
                
                # Afficher quelques détails supplémentaires pour le premier élément
                if files:
                    first_file = files[0]
                    print(f"\n📊 Détails du premier élément :")
                    print(f"   ID : {first_file['id']}")
                    print(f"   Chemin : {first_file['path']}")
                    print(f"   Modifié : {first_file['modified']}")
                    if first_file.get('web_url'):
                        print(f"   URL Web : {first_file['web_url']}")
                        
            else:
                print("⚠️ Dossier vide ou inaccessible")
                
        except Exception as e:
            print(f"❌ Erreur d'accès : {str(e)}")
            
    return True

def test_specific_folder():
    """Test d'un dossier spécifique saisi par l'utilisateur"""
    
    print("\n" + "=" * 50)
    print("🔍 Test d'un dossier spécifique")
    print("=" * 50)
    
    folder_path = input("Entrez le chemin du dossier SharePoint à tester : ").strip()
    if not folder_path:
        folder_path = "/Documents partages"
        print(f"Utilisation du dossier par défaut : {folder_path}")
    
    try:
        client = SharePointClient()
        files = client.list_first_10_files(folder_path)
        
        if files:
            print(f"\n✅ Accès réussi au dossier : {folder_path}")
            print(f"📊 Trouvé {len(files)} éléments :")
            
            folders = [f for f in files if f['type'] == 'folder']
            documents = [f for f in files if f['type'] == 'file']
            
            if folders:
                print(f"\n📁 Dossiers ({len(folders)}) :")
                for folder in folders:
                    print(f"   - {folder['name']}")
                    
            if documents:
                print(f"\n📄 Fichiers ({len(documents)}) :")
                for doc in documents:
                    size_str = f"{doc['size']/1024/1024:.1f} MB" if doc['size'] > 0 else "0 MB"
                    print(f"   - {doc['name']} ({size_str})")
                    
        else:
            print(f"⚠️ Aucun élément trouvé dans : {folder_path}")
            
    except Exception as e:
        print(f"❌ Erreur lors du test : {str(e)}")

def main():
    """Fonction principale"""
    
    print("🚀 Test de connectivité SharePoint")
    print("Ce script teste la nouvelle fonctionnalité de listing rapide")
    print()
    
    # Charger les variables d'environnement
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Fichier .env chargé")
    except ImportError:
        print("⚠️ python-dotenv non installé, utilisation des variables système")
    
    # Test d'accès automatique
    if not test_sharepoint_access():
        print("\n❌ Échec des tests automatiques")
        return
    
    # Proposer un test manuel
    print("\n" + "=" * 50)
    choice = input("Voulez-vous tester un dossier spécifique ? (o/n) : ").strip().lower()
    if choice in ['o', 'oui', 'y', 'yes']:
        test_specific_folder()
    
    print("\n✅ Tests terminés !")
    print("\nPour utiliser cette fonctionnalité dans vos scripts :")
    print("from scripts.identify_relevant_files_sharepoint import SharePointClient")
    print("client = SharePointClient()")
    print("files = client.list_first_10_files('/Documents partages')")

if __name__ == "__main__":
    main()
