"""
Script de récupération des IDs SharePoint
Permet d'identifier les sites et drives SharePoint accessibles
"""

import os
import argparse
import requests
import msal
import json
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
    
    print(f"✅ Token obtenu avec succès")
    return result["access_token"]

def find_sites(token):
    """Trouve tous les sites SharePoint accessibles"""
    if not token:
        return []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Recherche de tous les sites
    print("\n📊 Recherche des sites SharePoint...")
    try:
        # D'abord essayer avec une recherche
        response = requests.get("https://graph.microsoft.com/v1.0/sites?search=*", headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Échec de la recherche des sites: {response.status_code}")
            # Essayer de lister les sites sans filtrer
            response = requests.get("https://graph.microsoft.com/v1.0/sites", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès aux sites: {response.status_code}")
            print(f"   Message: {response.text}")
            return []
        
        sites = response.json().get("value", [])
        print(f"✅ {len(sites)} sites trouvés")
        return sites
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche des sites: {e}")
        return []

def find_drives_for_site(token, site_id, site_name):
    """Trouve tous les drives pour un site spécifique"""
    if not token:
        return []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        print(f"\n📊 Recherche des drives pour le site: {site_name}")
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès aux drives: {response.status_code}")
            print(f"   Message: {response.text}")
            return []
        
        drives = response.json().get("value", [])
        print(f"✅ {len(drives)} drives trouvés")
        return drives
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche des drives: {e}")
        return []

def find_all_drives(token):
    """Trouve tous les drives accessibles"""
    if not token:
        return []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        print("\n📊 Recherche de tous les drives accessibles...")
        url = "https://graph.microsoft.com/v1.0/drives"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès aux drives: {response.status_code}")
            print(f"   Message: {response.text}")
            return []
        
        drives = response.json().get("value", [])
        print(f"✅ {len(drives)} drives trouvés")
        return drives
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche des drives: {e}")
        return []

def explore_drive_contents(token, drive_id, drive_name):
    """Explore le contenu à la racine d'un drive"""
    if not token:
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        print(f"\n📊 Exploration du contenu du drive: {drive_name}")
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès au contenu: {response.status_code}")
            print(f"   Message: {response.text}")
            return False
        
        items = response.json().get("value", [])
        
        folders = [item for item in items if "folder" in item]
        files = [item for item in items if "file" in item]
        
        print(f"✅ Contenu accessible: {len(items)} éléments ({len(folders)} dossiers, {len(files)} fichiers)")
        
        # Afficher quelques éléments
        if folders:
            print("\n   Dossiers:")
            for i, folder in enumerate(folders[:3], 1):
                name = folder.get("name", "Sans nom")
                print(f"     {i}. {name}")
        
        if files:
            print("\n   Fichiers:")
            for i, file in enumerate(files[:3], 1):
                name = file.get("name", "Sans nom")
                size = file.get("size", 0)
                print(f"     {i}. {name} ({size/1024:.1f} KB)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'exploration du drive: {e}")
        return False

def find_dpgf_files(token, drive_id, drive_name):
    """Cherche des fichiers DPGF dans un drive"""
    if not token:
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        print(f"\n🔍 Recherche de fichiers DPGF dans: {drive_name}")
        
        # D'abord chercher à la racine
        root_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        response = requests.get(root_url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès à la racine: {response.status_code}")
            return False
        
        items = response.json().get("value", [])
        
        # Chercher les fichiers Excel qui contiennent "dpgf" dans le nom
        dpgf_files = [
            item for item in items 
            if "file" in item and 
            item.get("name", "").lower().endswith((".xlsx", ".xls")) and 
            "dpgf" in item.get("name", "").lower()
        ]
        
        if dpgf_files:
            print(f"✅ {len(dpgf_files)} fichiers DPGF trouvés à la racine")
            for i, file in enumerate(dpgf_files, 1):
                name = file.get("name", "Sans nom")
                print(f"   {i}. {name}")
            return True
        
        # Chercher dans le dossier "Documents" si aucun fichier n'est trouvé à la racine
        print("   Aucun fichier DPGF trouvé à la racine, recherche dans le dossier 'Documents'...")
        
        # Vérifier si le dossier "Documents" existe
        docs_folder = next((item for item in items if 
                           item.get("name", "").lower() == "documents" and 
                           "folder" in item), None)
        
        if not docs_folder:
            print("   Dossier 'Documents' non trouvé")
            return False
        
        # Chercher dans le dossier "Documents"
        docs_id = docs_folder.get("id")
        docs_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{docs_id}/children"
        
        response = requests.get(docs_url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Échec de l'accès au dossier Documents: {response.status_code}")
            return False
        
        docs_items = response.json().get("value", [])
        
        # Chercher les fichiers Excel qui contiennent "dpgf" dans le nom
        docs_dpgf_files = [
            item for item in docs_items 
            if "file" in item and 
            item.get("name", "").lower().endswith((".xlsx", ".xls")) and 
            "dpgf" in item.get("name", "").lower()
        ]
        
        if docs_dpgf_files:
            print(f"✅ {len(docs_dpgf_files)} fichiers DPGF trouvés dans 'Documents'")
            for i, file in enumerate(docs_dpgf_files, 1):
                name = file.get("name", "Sans nom")
                print(f"   {i}. {name}")
            return True
        else:
            print("   Aucun fichier DPGF trouvé dans le dossier 'Documents'")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche de fichiers DPGF: {e}")
        return False

def search_for_drives_with_dpgf(token):
    """Cherche tous les drives qui contiennent des fichiers DPGF"""
    if not token:
        return
    
    # 1. Trouver tous les sites SharePoint
    sites = find_sites(token)
    
    if not sites:
        print("⚠️ Aucun site SharePoint trouvé ou accessible")
        print("   Vérifiez que vous avez bien la permission 'Sites.Read.All'")
    
    # 2. Trouver tous les drives pour chaque site
    drives_by_site = {}
    for site in sites:
        site_id = site.get("id")
        site_name = site.get("displayName", "Sans nom")
        site_url = site.get("webUrl", "")
        
        drives = find_drives_for_site(token, site_id, site_name)
        if drives:
            drives_by_site[site_name] = {
                "site_id": site_id,
                "url": site_url,
                "drives": drives
            }
    
    # 3. Chercher des fichiers DPGF dans chaque drive
    drives_with_dpgf = []
    
    print("\n🔍 Recherche de fichiers DPGF dans tous les drives...")
    
    for site_name, site_info in drives_by_site.items():
        for drive in site_info["drives"]:
            drive_id = drive.get("id")
            drive_name = drive.get("name", "Sans nom")
            
            found = find_dpgf_files(token, drive_id, drive_name)
            if found:
                drives_with_dpgf.append({
                    "site_name": site_name,
                    "site_url": site_info["url"],
                    "drive_id": drive_id,
                    "drive_name": drive_name
                })
    
    # 4. Afficher les résultats
    if drives_with_dpgf:
        print("\n✅ Drives contenant des fichiers DPGF:")
        for i, drive_info in enumerate(drives_with_dpgf, 1):
            print(f"\n{i}. Drive: {drive_info['drive_name']}")
            print(f"   Site: {drive_info['site_name']}")
            print(f"   URL: {drive_info['site_url']}")
            print(f"   Drive ID: {drive_info['drive_id']}")
            
            # Vérifier si c'est le drive configuré
            if drive_info['drive_id'] == os.getenv("GRAPH_DRIVE_ID"):
                print(f"   ✅ C'est le drive actuellement configuré dans .env")
    else:
        print("\n⚠️ Aucun drive contenant des fichiers DPGF n'a été trouvé")
        print("   Vérifiez que les fichiers DPGF sont bien présents et accessibles")
    
    # Générer la liste des actions à entreprendre
    print("\n🔧 Actions recommandées:")
    
    if drives_with_dpgf:
        correct_drive = os.getenv("GRAPH_DRIVE_ID")
        correct_drive_found = any(d["drive_id"] == correct_drive for d in drives_with_dpgf)
        
        if correct_drive_found:
            print("1. Votre configuration semble correcte - le drive ID configuré contient des fichiers DPGF")
            print("2. Vérifiez les permissions de l'application dans le portail Azure")
            print("   - Ajoutez Files.Read.All, Files.ReadWrite.All et Sites.Read.All")
            print("   - Accordez le consentement administrateur")
        else:
            print("1. Mettez à jour votre fichier .env avec le bon Drive ID")
            print("   Un des IDs ci-dessus devrait être utilisé dans GRAPH_DRIVE_ID")
            if drives_with_dpgf:
                print(f"   Exemple: GRAPH_DRIVE_ID={drives_with_dpgf[0]['drive_id']}")
            print("2. Vérifiez les permissions de l'application dans le portail Azure")
            print("   - Ajoutez Files.Read.All, Files.ReadWrite.All et Sites.Read.All")
            print("   - Accordez le consentement administrateur")
    else:
        print("1. Vérifiez que les fichiers DPGF existent bien dans SharePoint")
        print("2. Vérifiez les permissions de l'application dans le portail Azure")
        print("3. Vérifiez que le compte de service a accès aux fichiers SharePoint")

def main():
    parser = argparse.ArgumentParser(description="Recherche de drives SharePoint contenant des fichiers DPGF")
    
    print("===== RECHERCHE DE DRIVES SHAREPOINT AVEC FICHIERS DPGF =====")
    
    # Obtenir un token d'accès
    token = get_access_token()
    if not token:
        return
    
    # Chercher des drives contenant des fichiers DPGF
    search_for_drives_with_dpgf(token)

if __name__ == "__main__":
    main()
