"""
Script de vérification des permissions d'une application Azure AD
"""

import os
import requests
import msal
import json
from dotenv import load_dotenv

def main():
    print("===== VÉRIFICATION DES PERMISSIONS AZURE AD =====")
    
    # Charger les variables d'environnement
    load_dotenv()
    
    # Récupérer les identifiants
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    if not tenant_id or not client_id or not client_secret:
        print("❌ Variables d'authentification manquantes dans le fichier .env")
        return
    
    # Afficher les identifiants (partiellement masqués)
    print(f"TENANT_ID: {tenant_id[:8]}...{tenant_id[-4:]}")
    print(f"CLIENT_ID: {client_id[:8]}...{client_id[-4:]}")
    print(f"CLIENT_SECRET: {client_secret[:4]}...{client_secret[-2:] if len(client_secret) > 5 else ''}")
    
    # 1. Obtenir un token OAuth2 pour Microsoft Graph
    print("\n1. Tentative d'acquisition du token...")
    
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret
    )
    
    # Essayer d'acquérir un token avec un scope minimal
    scopes = ["https://graph.microsoft.com/.default"]
    result = app.acquire_token_for_client(scopes=scopes)
    
    if "access_token" not in result:
        print(f"❌ Échec d'obtention du token: {result.get('error')}")
        print(f"   Description: {result.get('error_description')}")
        return
    
    print("✅ Token obtenu avec succès")
    token = result["access_token"]
    
    # 2. Vérifier les permissions actuelles de l'application
    print("\n2. Vérification des permissions de l'application...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # Essayer d'obtenir les informations sur l'application
    try:
        # Note: La vérification directe des permissions nécessite des droits d'administrateur
        # On va plutôt tester les endpoints dont on a besoin
        
        # Test d'accès aux profils utilisateurs (basique)
        print("\nTest d'accès aux informations de base:")
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if response.status_code == 401:
            print("⚠️ Accès à /me: Non autorisé (normal pour un compte d'application)")
        else:
            print(f"✅ Accès à /me: {response.status_code}")
        
        # Test d'accès à la liste des sites
        print("\nTest d'accès aux sites SharePoint:")
        response = requests.get("https://graph.microsoft.com/v1.0/sites", headers=headers)
        if response.status_code != 200:
            print(f"❌ Accès aux sites: {response.status_code}")
            print(f"   Réponse: {response.text}")
            print("\n⚠️ Permission manquante possible: Sites.Read.All")
        else:
            print(f"✅ Accès aux sites: {response.status_code}")
            sites = response.json().get("value", [])
            print(f"   {len(sites)} sites trouvés")
        
        # Test d'accès à la liste des drives
        print("\nTest d'accès aux drives:")
        response = requests.get("https://graph.microsoft.com/v1.0/drives", headers=headers)
        if response.status_code != 200:
            print(f"❌ Accès aux drives: {response.status_code}")
            print(f"   Réponse: {response.text}")
            print("\n⚠️ Permission manquante possible: Files.Read.All")
        else:
            print(f"✅ Accès aux drives: {response.status_code}")
            drives = response.json().get("value", [])
            print(f"   {len(drives)} drives trouvés")
        
        # Test d'accès à un drive spécifique
        drive_id = os.getenv("GRAPH_DRIVE_ID")
        if drive_id:
            print(f"\nTest d'accès au drive spécifié (ID: {drive_id[:10]}...):")
            response = requests.get(f"https://graph.microsoft.com/v1.0/drives/{drive_id}", headers=headers)
            if response.status_code != 200:
                print(f"❌ Accès au drive: {response.status_code}")
                print(f"   Réponse: {response.text}")
                if response.status_code == 404:
                    print("\n⚠️ Le drive ID semble être incorrect")
                elif response.status_code == 401:
                    print("\n⚠️ Permission manquante possible: Files.Read.All, Sites.Read.All")
            else:
                print(f"✅ Accès au drive: {response.status_code}")
                drive = response.json()
                print(f"   Nom du drive: {drive.get('name', 'Sans nom')}")
        
        # 3. Résumé des permissions nécessaires
        print("\n3. Résumé des permissions nécessaires pour Microsoft Graph API:")
        print("   - Files.Read.All (pour lire les fichiers)")
        print("   - Files.ReadWrite.All (pour déplacer/renommer les fichiers traités)")
        print("   - Sites.Read.All (pour accéder aux sites SharePoint)")
        
        # 4. Instructions pour configurer les permissions
        print("\n4. Comment configurer ces permissions:")
        print("   1. Connectez-vous au portail Azure: https://portal.azure.com")
        print("   2. Accédez à Azure Active Directory > Inscriptions d'applications")
        print("   3. Sélectionnez votre application (ID client: " + client_id[:8] + "...)")
        print("   4. Allez à API permissions > Add a permission")
        print("   5. Choisissez Microsoft Graph > Application permissions")
        print("   6. Ajoutez: Files.Read.All, Files.ReadWrite.All, Sites.Read.All")
        print("   7. Cliquez sur 'Grant admin consent for [your tenant]'")
        
        # Vérifier le contexte de l'accès SharePoint
        print("\n5. Vérification du contexte SharePoint:")
        
        # Essayer d'obtenir des informations sur les sites SharePoint
        site_response = requests.get("https://graph.microsoft.com/v1.0/sites?search=*", headers=headers)
        if site_response.status_code == 200:
            sites = site_response.json().get("value", [])
            if sites:
                print(f"✅ Sites SharePoint trouvés: {len(sites)}")
                for i, site in enumerate(sites[:3], 1):
                    print(f"   {i}. {site.get('displayName', 'Sans nom')}")
                    print(f"      - URL: {site.get('webUrl', 'N/A')}")
                    print(f"      - ID: {site.get('id', 'N/A')}")
                    
                # Essayer de trouver les drives associés aux sites
                print("\nRecherche des drives associés aux sites:")
                for i, site in enumerate(sites[:2], 1):
                    site_id = site.get("id")
                    if site_id:
                        site_drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
                        site_drives_response = requests.get(site_drives_url, headers=headers)
                        if site_drives_response.status_code == 200:
                            site_drives = site_drives_response.json().get("value", [])
                            print(f"   Site {i}: {len(site_drives)} drives trouvés")
                            for j, drive in enumerate(site_drives[:2], 1):
                                drive_name = drive.get("name", "Sans nom")
                                drive_id = drive.get("id")
                                print(f"      {j}. {drive_name} (ID: {drive_id})")
                                
                                # Vérifier si c'est le drive configuré
                                if drive_id == os.getenv("GRAPH_DRIVE_ID"):
                                    print(f"         ✅ C'est le drive configuré!")
                                    
                                    # Essayer de lister les éléments à la racine du drive
                                    root_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
                                    root_response = requests.get(root_url, headers=headers)
                                    if root_response.status_code == 200:
                                        items = root_response.json().get("value", [])
                                        print(f"         ✅ Accès au contenu réussi: {len(items)} éléments trouvés")
                                    else:
                                        print(f"         ❌ Échec d'accès au contenu: {root_response.status_code}")
                        else:
                            print(f"   ❌ Échec d'accès aux drives du site {i}: {site_drives_response.status_code}")
            else:
                print("❌ Aucun site SharePoint trouvé")
        else:
            print(f"❌ Échec de recherche des sites: {site_response.status_code}")
            print(f"   Réponse: {site_response.text}")
        
        # Vérifier le type de contenu accessible
        print("\n6. Vérification du type d'accès:")
        print("   Votre application est configurée comme application cliente confidentielle (daemon/service)")
        print("   Ce type d'application fonctionne sans utilisateur et nécessite un consentement d'administrateur")
        print("   Pour des actions en tant qu'application, vous devez utiliser 'Application permissions'")
        print("   (et non 'Delegated permissions' qui nécessiteraient une authentification utilisateur)")
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification des permissions: {e}")

if __name__ == "__main__":
    main()
