"""
Script de test pour l'accès aux drives et dossiers SharePoint
Permet de lister les différents drives et de tester l'accès aux dossiers
"""

import os
import sys
import argparse
import datetime
import requests
import msal
from dotenv import load_dotenv

def get_access_token():
    """Obtient un token d'accès pour Microsoft Graph API"""
    load_dotenv()
    
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    if not tenant_id or not client_id or not client_secret:
        print("❌ Variables d'authentification manquantes dans le fichier .env")
        return None
    
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret
    )
    
    scopes = ["https://graph.microsoft.com/.default"]
    result = app.acquire_token_for_client(scopes=scopes)
    
    if "access_token" not in result:
        error = result.get("error")
        error_description = result.get("error_description")
        print(f"❌ Erreur d'authentification: {error}")
        print(f"  Description: {error_description}")
        return None
    
    token_expires = datetime.datetime.now() + datetime.timedelta(seconds=result.get("expires_in", 3599))
    print(f"✅ Token obtenu (valide jusqu'à {token_expires.strftime('%H:%M:%S')})")
    
    return result["access_token"]

def list_drives(token):
    """Liste tous les drives accessibles"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    print("\n📁 Liste des drives SharePoint:")
    response = requests.get("https://graph.microsoft.com/v1.0/drives", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Erreur: {response.status_code}")
        print(f"  Détails: {response.text}")
        return None
    
    drives = response.json().get("value", [])
    print(f"✅ {len(drives)} drives trouvés")
    
    drive_id_env = os.getenv("GRAPH_DRIVE_ID")
    
    for i, drive in enumerate(drives, 1):
        name = drive.get("name", "Sans nom")
        id = drive.get("id")
        drive_type = drive.get("driveType", "Inconnu")
        owner = drive.get("owner", {}).get("user", {}).get("displayName", "Inconnu")
        
        print(f"\n{i}. {name}")
        print(f"   ID: {id}")
        print(f"   Type: {drive_type}")
        print(f"   Propriétaire: {owner}")
        
        if id == drive_id_env:
            print(f"   ✅ C'est le drive configuré dans .env")
    
    return drives

def list_folders(token, drive_id, path="root"):
    """Liste les dossiers d'un drive"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Déterminer l'URL en fonction du chemin
    if path == "root" or not path:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
    else:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/children"
    
    print(f"\n📁 Contenu du dossier: {path if path != 'root' else '/'}")
    print(f"URL: {url}")
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Erreur: {response.status_code}")
        print(f"  Détails: {response.text}")
        return
    
    items = response.json().get("value", [])
    
    folders = [item for item in items if "folder" in item]
    files = [item for item in items if "file" in item]
    
    print(f"✅ {len(items)} éléments trouvés ({len(folders)} dossiers, {len(files)} fichiers)")
    
    # Afficher les dossiers
    if folders:
        print("\nDossiers:")
        for i, folder in enumerate(folders, 1):
            name = folder.get("name", "Sans nom")
            id = folder.get("id")
            child_count = folder.get("folder", {}).get("childCount", 0)
            print(f"  {i}. {name} (ID: {id}, {child_count} éléments)")
    
    # Afficher les fichiers (filtrer pour les DPGF)
    dpgf_files = [file for file in files if 
                 file.get("name", "").lower().endswith((".xlsx", ".xls")) and 
                 "dpgf" in file.get("name", "").lower()]
    
    if dpgf_files:
        print("\nFichiers DPGF:")
        for i, file in enumerate(dpgf_files, 1):
            name = file.get("name", "Sans nom")
            size = file.get("size", 0)
            last_modified = file.get("lastModifiedDateTime", "")
            print(f"  {i}. {name} ({size/1024:.1f} KB, modifié: {last_modified})")
    
    # Afficher d'autres fichiers Excel
    other_excel = [file for file in files if 
                  file.get("name", "").lower().endswith((".xlsx", ".xls")) and 
                  "dpgf" not in file.get("name", "").lower()]
    
    if other_excel:
        print("\nAutres fichiers Excel:")
        for i, file in enumerate(other_excel[:5], 1):
            name = file.get("name", "Sans nom")
            size = file.get("size", 0)
            print(f"  {i}. {name} ({size/1024:.1f} KB)")
    
    # Autres fichiers (limités)
    other_files = [file for file in files if not file.get("name", "").lower().endswith((".xlsx", ".xls"))]
    if other_files and len(other_files) > 0:
        print(f"\nAutres fichiers: {len(other_files)} au total")
        for i, file in enumerate(other_files[:3], 1):
            name = file.get("name", "Sans nom")
            size = file.get("size", 0)
            print(f"  {i}. {name} ({size/1024:.1f} KB)")

def main():
    parser = argparse.ArgumentParser(description="Test d'accès aux drives et dossiers SharePoint")
    parser.add_argument("--drive", help="ID du drive à explorer (utilise GRAPH_DRIVE_ID par défaut)")
    parser.add_argument("--folder", default="root", help="Chemin du dossier à explorer (par défaut: racine)")
    parser.add_argument("--list-drives", action="store_true", help="Liste tous les drives disponibles")
    
    args = parser.parse_args()
    
    print("==== TEST D'ACCÈS SHAREPOINT ====")
    
    # Obtenir un token d'accès
    token = get_access_token()
    if not token:
        sys.exit(1)
    
    # Si demandé, lister tous les drives disponibles
    drives = None
    if args.list_drives:
        drives = list_drives(token)
        if not drives:
            sys.exit(1)
    
    # Déterminer le drive ID à utiliser
    drive_id = args.drive or os.getenv("GRAPH_DRIVE_ID")
    if not drive_id:
        if drives and len(drives) > 0:
            drive_id = drives[0].get("id")
            print(f"\n⚠️ GRAPH_DRIVE_ID non défini, utilisation du premier drive trouvé: {drive_id}")
        else:
            print("❌ Aucun drive ID spécifié et GRAPH_DRIVE_ID non défini dans .env")
            print("   Utilisez --drive ID ou définissez GRAPH_DRIVE_ID dans .env")
            sys.exit(1)
    
    # Lister le contenu du dossier spécifié
    list_folders(token, drive_id, args.folder)

if __name__ == "__main__":
    main()
