"""
Script de diagnostic pour l'accès SharePoint
Vérifie l'environnement et teste la connexion à SharePoint
"""

import os
import sys
import datetime
from pathlib import Path
import requests
import msal
from dotenv import load_dotenv

def main():
    print("===== DIAGNOSTIC D'ACCÈS SHAREPOINT =====")
    print(f"Date et heure: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Répertoire courant: {os.getcwd()}")
    
    # 1. Vérifier le fichier .env
    env_file = Path('.env')
    if env_file.exists():
        print(f"\n✅ Fichier .env trouvé: {env_file.absolute()}")
        print(f"   Taille: {env_file.stat().st_size} octets")
        print(f"   Dernière modification: {datetime.datetime.fromtimestamp(env_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"\n❌ Fichier .env non trouvé à l'emplacement: {env_file.absolute()}")
        return
    
    # 2. Charger les variables d'environnement
    print("\nChargement des variables d'environnement...")
    load_dotenv(dotenv_path=env_file, override=True)
    
    # 3. Vérifier les variables essentielles
    required_vars = ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "GRAPH_DRIVE_ID"]
    missing_vars = []
    
    print("\nVérification des variables d'environnement:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Tronquer l'affichage pour les valeurs sensibles
            if var == "CLIENT_SECRET":
                display_value = f"{value[:5]}...{value[-4:] if len(value) > 8 else ''}"
            elif len(value) > 30:
                display_value = f"{value[:15]}...{value[-10:]}"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Non défini")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Variables manquantes: {', '.join(missing_vars)}")
        print("   Assurez-vous que ces variables sont définies dans le fichier .env")
        return
    
    # 4. Tester la connexion à Microsoft Graph
    print("\nTest de connexion à Microsoft Graph API...")
    
    # Récupérer les variables nécessaires
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    drive_id = os.getenv("GRAPH_DRIVE_ID")
    
    try:
        # Créer l'application MSAL
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret
        )
        
        # Acquérir le token
        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" not in result:
            print(f"\n❌ Échec de l'authentification:")
            print(f"   Erreur: {result.get('error')}")
            print(f"   Description: {result.get('error_description')}")
            return
        
        access_token = result["access_token"]
        token_expires = datetime.datetime.now() + datetime.timedelta(seconds=result.get("expires_in", 3599))
        
        print(f"✅ Token obtenu avec succès (expire à {token_expires.strftime('%H:%M:%S')})")
        
        # Tester l'accès à l'API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        print("\nTest d'accès aux drives SharePoint...")
        response = requests.get("https://graph.microsoft.com/v1.0/drives", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès aux drives: {response.status_code}")
            print(f"   Réponse: {response.text}")
        else:
            drives = response.json().get("value", [])
            print(f"✅ Accès réussi: {len(drives)} drives trouvés")
            
            for i, drive in enumerate(drives[:5], 1):
                name = drive.get("name", "Sans nom")
                id = drive.get("id")
                print(f"  {i}. {name} (ID: {id})")
                
                if id == drive_id:
                    print(f"     ✅ C'est le drive configuré!")
        
        # Test d'accès au drive spécifique
        print(f"\nTest d'accès au drive configuré (ID: {drive_id})...")
        response = requests.get(f"https://graph.microsoft.com/v1.0/drives/{drive_id}", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès au drive: {response.status_code}")
            print(f"   Réponse: {response.text}")
        else:
            drive_info = response.json()
            print(f"✅ Accès réussi: {drive_info.get('name', 'Sans nom')}")
            print(f"   Type: {drive_info.get('driveType', 'Inconnu')}")
            owner = drive_info.get('owner', {}).get('user', {}).get('displayName', 'Inconnu')
            print(f"   Propriétaire: {owner}")
        
        # Test d'accès au contenu du drive
        print(f"\nTest d'accès au contenu du drive...")
        response = requests.get(f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès au contenu: {response.status_code}")
            print(f"   Réponse: {response.text}")
        else:
            items = response.json().get("value", [])
            print(f"✅ Accès réussi: {len(items)} éléments à la racine")
            
            folders = [item for item in items if "folder" in item]
            files = [item for item in items if "file" in item]
            
            print(f"   {len(folders)} dossiers, {len(files)} fichiers")
            
            # Afficher quelques dossiers
            if folders:
                print("\n   Dossiers:")
                for i, folder in enumerate(folders[:3], 1):
                    name = folder.get("name", "Sans nom")
                    id = folder.get("id")
                    print(f"     {i}. {name} (ID: {id})")
            
            # Afficher quelques fichiers
            if files:
                print("\n   Fichiers:")
                for i, file in enumerate(files[:3], 1):
                    name = file.get("name", "Sans nom")
                    size = file.get("size", 0)
                    print(f"     {i}. {name} ({size/1024:.1f} KB)")
    
    except Exception as e:
        print(f"\n❌ Erreur lors du test de connexion:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
