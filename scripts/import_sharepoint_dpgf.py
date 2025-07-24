"""
Script pour récupérer les fichiers DPGF depuis SharePoint et les importer en lot
Utilise l'API Microsoft Graph pour accéder à SharePoint
Télécharge les fichiers temporairement et utilise le script d'import unifié
"""

import os
import sys
import tempfile
import datetime
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import requests
import msal
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

print("==== DÉMARRAGE DU SCRIPT IMPORT_SHAREPOINT_DPGF ====")
print(f"Version Python: {sys.version}")
print(f"Répertoire courant: {os.getcwd()}")
print(f"Fichier .env présent: {os.path.exists('.env')}")

# Charger les variables d'environnement explicitement
load_dotenv(override=True)
print("Variables d'environnement chargées")

# Importer la configuration de l'application
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.config import settings
    print("Module settings importé avec succès")
except Exception as e:
    print(f"ERREUR lors de l'import des settings: {e}")
    import traceback
    traceback.print_exc()

# Importer le script d'import unifié
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.import_dpgf_unified import UnifiedDPGFImporter
    from app.db.session import get_db
    print("Module UnifiedDPGFImporter importé avec succès")
except Exception as e:
    print(f"ERREUR lors de l'import de UnifiedDPGFImporter: {e}")
    import traceback
    traceback.print_exc()

class SharePointDPGFImporter:
    """Classe pour importer des DPGF depuis SharePoint"""
    def __init__(self):
        # Charger les variables d'environnement
        load_dotenv()
        
        # Configuration Microsoft Graph API - Faire une recherche exhaustive des variables
        # 1. Vérifier dans os.environ directement (plus fiable)
        # 2. Utiliser settings de Pydantic
        # 3. Chercher dans les variables d'environnement avec getenv
        self.tenant_id = os.environ.get("TENANT_ID") or settings.TENANT_ID or os.getenv("TENANT_ID")
        self.client_id = os.environ.get("CLIENT_ID") or settings.CLIENT_ID or os.getenv("CLIENT_ID")
        self.client_secret = os.environ.get("CLIENT_SECRET") or settings.CLIENT_SECRET or os.getenv("CLIENT_SECRET")
        self.drive_id = os.environ.get("GRAPH_DRIVE_ID") or settings.GRAPH_DRIVE_ID or os.getenv("GRAPH_DRIVE_ID")
        self.dpgf_folder = os.environ.get("GRAPH_DPFG_FOLDER") or settings.GRAPH_DPFG_FOLDER or os.getenv("GRAPH_DPFG_FOLDER", "Documents")
        
        # Configuration de l'API
        self.api_url = os.environ.get("API_URL") or os.getenv("API_URL", "http://127.0.0.1:8000")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        
        # Dossier temporaire pour stocker les fichiers DPGF
        self.temp_dir = os.getenv("DPGF_UPLOAD_DIR") or settings.DPGF_UPLOAD_DIR or tempfile.gettempdir()
        Path(self.temp_dir).mkdir(exist_ok=True)
        
        print(f"Configuration SharePoint initialisée:")
        print(f"- Client ID: {self.client_id[:5]}...{self.client_id[-4:] if self.client_id else 'Non défini'}")
        print(f"- Tenant ID: {self.tenant_id[:5]}...{self.tenant_id[-4:] if self.tenant_id else 'Non défini'}")
        print(f"- Drive ID: {self.drive_id}")
        print(f"- Dossier: {self.dpgf_folder}")
        print(f"- Dossier temporaire: {self.temp_dir}")
        
        # Token d'accès pour Microsoft Graph API
        self.access_token = None
        self.token_expires = datetime.datetime.now()
        
    def get_access_token(self) -> str:
        """Obtient un token d'accès pour Microsoft Graph API"""
        # Vérifier si le token est encore valide
        if self.access_token and self.token_expires > datetime.datetime.now():
            return self.access_token
        
        # Configuration de l'application pour acquérir le token
        app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        
        # Acquérir le token pour Microsoft Graph avec les scopes appropriés
        scopes = [
            "https://graph.microsoft.com/.default"
        ]
        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in result:
            error = result.get("error")
            error_description = result.get("error_description")
            raise ValueError(f"Erreur d'authentification: {error} - {error_description}")
        
        # Stocker le token et sa durée de validité
        self.access_token = result["access_token"]
        self.token_expires = datetime.datetime.now() + datetime.timedelta(seconds=result.get("expires_in", 3599))
        
        print(f"✅ Token d'accès obtenu (valide jusqu'à {self.token_expires.strftime('%H:%M:%S')})")
        return self.access_token
    
    def test_graph_api_connection(self):
        """Test de la connexion à l'API Graph et affiche les informations de diagnostic"""
        token = self.get_access_token()
        
        print(f"\n🔍 Test de connexion à Microsoft Graph API")
        
        # 1. Tester l'accès à l'API Graph (point d'entrée de base)
        base_url = "https://graph.microsoft.com/v1.0/"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        try:
            # Test de base - Obtenir des informations sur l'utilisateur/application
            response = requests.get(f"{base_url}me", headers=headers)
            if response.status_code == 401:
                print(f"⚠️ Accès à /me non autorisé (normal pour un compte d'application): {response.status_code}")
            else:
                print(f"✅ Accès à /me: {response.status_code}")
            
            # Test des sites disponibles
            response = requests.get(f"{base_url}sites", headers=headers)
            if response.status_code != 200:
                print(f"⚠️ Erreur lors de l'accès aux sites: {response.status_code}")
                print(f"Détails: {response.text}")
            else:
                print(f"✅ Accès aux sites réussi")
                sites = response.json().get("value", [])
                print(f"📁 {len(sites)} sites trouvés")
                for i, site in enumerate(sites[:3]):
                    name = site.get("displayName", "Sans nom")
                    id = site.get("id", "")
                    print(f"  - Site {i+1}: {name} (ID: {id})")
            
            # Test d'accès à un drive spécifique
            if self.drive_id:
                response = requests.get(f"{base_url}drives/{self.drive_id}", headers=headers)
                if response.status_code != 200:
                    print(f"⚠️ Erreur lors de l'accès au drive {self.drive_id}: {response.status_code}")
                    print(f"Détails: {response.text}")
                else:
                    drive_info = response.json()
                    print(f"✅ Accès au drive réussi: {drive_info.get('name', 'Sans nom')}")
                    print(f"  - Type: {drive_info.get('driveType', 'Inconnu')}")
                    print(f"  - Propriétaire: {drive_info.get('owner', {}).get('user', {}).get('displayName', 'Inconnu')}")
        
            # 3. Liste des drives disponibles dans le tenant
            print("\n📁 Liste de tous les drives accessibles:")
            response = requests.get(f"{base_url}drives", headers=headers)
            if response.status_code != 200:
                print(f"⚠️ Erreur lors de la liste des drives: {response.status_code}")
                print(f"Détails: {response.text}")
            else:
                drives = response.json().get("value", [])
                print(f"📁 {len(drives)} drives trouvés")
                for i, drive in enumerate(drives[:5]):
                    name = drive.get("name", "Sans nom")
                    id = drive.get("id", "")
                    drive_type = drive.get("driveType", "")
                    print(f"  - Drive {i+1}: {name} (ID: {id}, Type: {drive_type})")
                    
                    # Si c'est le drive qu'on cherche, afficher plus d'infos
                    if id == self.drive_id:
                        print(f"    ✅ C'est le drive configuré!")
                
                # Suggérer un drive à utiliser si le drive_id n'est pas défini
                if not self.drive_id and drives:
                    suggestion = drives[0].get("id", "")
                    print(f"\n📌 Suggestion: Utilisez ce drive_id: {suggestion}")
                    print("   Ajoutez-le à votre fichier .env: GRAPH_DRIVE_ID="+suggestion)
        
        except Exception as e:
            print(f"❌ Erreur lors du test de connexion: {e}")
            
    def list_dpgf_files(self) -> List[Dict]:
        """Liste les fichiers DPGF disponibles sur SharePoint"""
        token = self.get_access_token()
        
        print(f"\n🔍 Tentative d'accès au dossier: {self.dpgf_folder}")
        
        # Essayer d'abord de lister les drives pour diagnostic
        self.test_graph_api_connection()
        
        # Essayer avec l'approche drive / racine puis chemin
        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        try:
            # Essayer de lister la racine d'abord pour diagnostiquer
            print(f"🔍 Tentative d'accès à la racine du drive {self.drive_id}")
            response = requests.get(url, headers=headers)
            
            # Afficher plus d'informations sur l'erreur si elle se produit
            if response.status_code != 200:
                print(f"⚠️ Erreur d'accès à la racine: {response.status_code}")
                print(f"Détails: {response.text}")
                
                # Si l'erreur est 401, suggérer les problèmes possibles
                if response.status_code == 401:
                    print("\n🔧 Solutions possibles pour l'erreur 401:")
                    print("1. Vérifiez que le TENANT_ID, CLIENT_ID et CLIENT_SECRET sont corrects")
                    print("2. Assurez-vous que l'application enregistrée dans Azure AD a les permissions appropriées:")
                    print("   - Files.Read.All")
                    print("   - Files.ReadWrite.All")
                    print("   - Sites.Read.All")
                    print("3. Assurez-vous que l'administrateur a consenti aux permissions")
                    return []
                
                # Si l'erreur est 404, le drive_id est probablement incorrect
                if response.status_code == 404:
                    print("\n🔧 Solutions possibles pour l'erreur 404:")
                    print("1. Le GRAPH_DRIVE_ID est probablement incorrect")
                    print("2. Utilisez un des drive_id suggérés plus haut")
                    return []
            else:
                print("✅ Accès à la racine réussi")
                root_files = response.json().get("value", [])
                print(f"📁 {len(root_files)} éléments trouvés à la racine")
                
                # Afficher les premiers éléments pour aider au diagnostic
                for i, item in enumerate(root_files[:5]):
                    name = item.get("name", "Sans nom")
                    is_folder = "folder" in item
                    print(f"  - {name} {'(dossier)' if is_folder else '(fichier)'}")
                
                # Si le dossier cible n'est pas la racine, chercher le dossier
                if self.dpgf_folder != "" and self.dpgf_folder.lower() != "root":
                    # Chercher le dossier demandé
                    target_folder = next((f for f in root_files if f.get("name") == self.dpgf_folder and "folder" in f), None)
                    
                    if target_folder:
                        print(f"✅ Dossier '{self.dpgf_folder}' trouvé")
                        folder_id = target_folder.get("id")
                        # Utiliser l'ID du dossier pour accéder à son contenu
                        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{folder_id}/children"
                    else:
                        print(f"⚠️ Dossier '{self.dpgf_folder}' non trouvé dans la racine")
                        # Tenter avec le chemin relatif comme avant
                        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{self.dpgf_folder}:/children"
        
            # Faire la requête pour le dossier spécifié ou la racine
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Filtrer pour ne garder que les fichiers Excel
            files = response.json().get("value", [])
            excel_files = [
                file for file in files 
                if file.get("file") and 
                file.get("name", "").lower().endswith((".xlsx", ".xls")) and
                "dpgf" in file.get("name", "").lower()
            ]
            
            print(f"📁 {len(excel_files)} fichiers DPGF trouvés sur SharePoint")
            return excel_files
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ Erreur HTTP: {e}")
            print(f"Détails de la réponse: {e.response.text}")
            return []
        except Exception as e:
            print(f"❌ Erreur lors de la liste des fichiers: {e}")
            return []
    
    def download_file(self, file_item: Dict) -> str:
        """
        Télécharge un fichier depuis SharePoint
        
        Args:
            file_item: Information du fichier à télécharger
            
        Returns:
            Chemin du fichier téléchargé
        """
        token = self.get_access_token()
        
        file_name = file_item.get("name")
        download_url = file_item.get("@microsoft.graph.downloadUrl")
        file_id = file_item.get("id")
        
        print(f"🔄 Téléchargement du fichier: {file_name}")
        
        try:
            if not download_url:
                # Si le lien direct de téléchargement n'est pas disponible, utiliser l'API
                download_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}/content"
                headers = {"Authorization": f"Bearer {token}"}
            else:
                # Si le lien direct est disponible, pas besoin d'authentification
                headers = {}
                
            # Télécharger le fichier avec gestion des erreurs
            response = requests.get(download_url, headers=headers, stream=True)
            
            # Si erreur, essayer une approche alternative
            if response.status_code != 200:
                print(f"⚠️ Erreur de téléchargement direct: {response.status_code}")
                print(f"Tentative alternative avec l'API Graph...")
                
                # Essayer avec une approche alternative
                alt_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}"
                response_info = requests.get(alt_url, headers={"Authorization": f"Bearer {token}"})
                
                if response_info.status_code == 200:
                    file_info = response_info.json()
                    if "@microsoft.graph.downloadUrl" in file_info:
                        download_url = file_info["@microsoft.graph.downloadUrl"]
                        print(f"✅ URL de téléchargement alternative trouvée")
                        response = requests.get(download_url, stream=True)
                    else:
                        print(f"⚠️ Pas d'URL de téléchargement alternative disponible")
                        response.raise_for_status()
                else:
                    print(f"⚠️ Impossible d'obtenir les informations du fichier: {response_info.status_code}")
                    response.raise_for_status()
            
            response.raise_for_status()
            
            # Chemin du fichier temporaire
            local_path = os.path.join(self.temp_dir, file_name)
            
            # Écrire le fichier sur le disque avec indication de progression
            total_size = int(response.headers.get('content-length', 0))
            print(f"📥 Téléchargement de {file_name} ({total_size/1024:.1f} KB)...")
            
            downloaded = 0
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Afficher la progression pour les gros fichiers
                        if total_size > 1024*1024 and downloaded % (1024*1024) < 8192:  # Tous les Mo
                            print(f"  {downloaded/1024/1024:.1f} Mo / {total_size/1024/1024:.1f} Mo")
            
            print(f"✅ Fichier téléchargé: {local_path}")
            return local_path
            
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement du fichier {file_name}: {e}")
            raise
    
    def mark_file_as_processed(self, file_item: Dict):
        """
        Marque un fichier comme traité en le déplaçant dans un sous-dossier "Traité"
        ou en ajoutant un préfixe au nom du fichier
        
        Args:
            file_item: Information du fichier à marquer
        """
        token = self.get_access_token()
        file_id = file_item.get("id")
        
        # Date actuelle pour renommage pour éviter les conflits
        date_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = file_item.get("name")
        file_extension = os.path.splitext(file_name)[1]
        file_basename = os.path.splitext(file_name)[0]
        new_name = f"{file_basename}_traite_{date_suffix}{file_extension}"
        
        try:
            # 1. Vérifier si le dossier "Traité" existe, sinon le créer
            processed_folder_name = "Traite"
            parent_path = file_item.get("parentReference", {}).get("path", "")
            parent_id = file_item.get("parentReference", {}).get("id", "")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            # Si nous avons l'ID du parent, utilisez-le pour créer le dossier
            if parent_id:
                url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{parent_id}/children"
                print(f"🔍 Recherche du dossier 'Traite' dans le dossier parent (ID: {parent_id})")
                
                # Vérifier si le dossier "Traité" existe déjà
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                children = response.json().get("value", [])
                processed_folder_item = next((item for item in children if 
                                          item.get("name") == processed_folder_name and 
                                          "folder" in item), None)
                
                # Si le dossier n'existe pas, le créer
                if not processed_folder_item:
                    print(f"📁 Création du dossier 'Traite'...")
                    folder_data = {
                        "name": processed_folder_name,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "rename"
                    }
                    
                    response = requests.post(url, headers=headers, json=folder_data)
                    if response.status_code not in [201, 200]:
                        print(f"⚠️ Erreur lors de la création du dossier: {response.status_code}")
                        print(f"Détails: {response.text}")
                        # Renommer le fichier sur place au lieu de le déplacer
                        self._rename_file_in_place(file_id, new_name, token)
                        return
                    
                    processed_folder_item = response.json()
                    print(f"✅ Dossier 'Traite' créé avec succès")
                else:
                    print(f"✅ Dossier 'Traite' trouvé")
                
                # 2. Déplacer le fichier dans le dossier "Traité"
                processed_folder_id = processed_folder_item.get("id")
                move_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}"
                
                move_data = {
                    "parentReference": {
                        "id": processed_folder_id
                    },
                    "name": new_name
                }
                
                print(f"🔄 Déplacement du fichier vers le dossier 'Traite'...")
                response = requests.patch(move_url, headers=headers, json=move_data)
                
                if response.status_code == 200:
                    print(f"✅ Fichier déplacé avec succès: {new_name}")
                else:
                    print(f"⚠️ Erreur lors du déplacement du fichier: {response.status_code}")
                    print(f"Détails: {response.text}")
                    # Renommer le fichier sur place au lieu de le déplacer
                    self._rename_file_in_place(file_id, new_name, token)
            else:
                # Si nous n'avons pas l'ID du parent, renommer simplement le fichier
                print("⚠️ ID du dossier parent non disponible, renommage du fichier sur place")
                self._rename_file_in_place(file_id, new_name, token)
                
        except Exception as e:
            print(f"❌ Erreur lors du marquage du fichier comme traité: {e}")
            # En cas d'erreur, essayer simplement de renommer le fichier sur place
            try:
                self._rename_file_in_place(file_id, new_name, token)
            except Exception as rename_error:
                print(f"❌ Impossible de renommer le fichier: {rename_error}")
    
    def _rename_file_in_place(self, file_id: str, new_name: str, token: str):
        """Renomme un fichier sur place"""
        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {"name": new_name}
        
        print(f"🔄 Renommage du fichier en '{new_name}'...")
        response = requests.patch(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print(f"✅ Fichier renommé avec succès")
        else:
            print(f"⚠️ Erreur lors du renommage du fichier: {response.status_code}")
            print(f"Détails: {response.text}")
    
    def import_file(self, file_path: str, db: Session):
        """
        Importe un fichier DPGF dans la base de données
        
        Args:
            file_path: Chemin du fichier à importer
            db: Session de base de données
        """
        print(f"\n🔄 Importation du fichier: {os.path.basename(file_path)}")
        
        try:
            # Créer l'importeur unifié
            importer = UnifiedDPGFImporter(
                base_url=self.api_url,
                gemini_key=self.gemini_api_key,
                chunk_size=100,
                max_workers=4,
                batch_size=10,
                use_gemini=bool(self.gemini_api_key)
            )
            
            # Importer le fichier avec détection automatique
            dpgf_id = importer.import_file(
                file_path=file_path,
                dpgf_id=None,
                lot_num=None,
                auto_detect=True
            )
            
            print(f"✅ Import réussi pour {file_path}, DPGF ID: {dpgf_id}")
            return dpgf_id
            
        except Exception as e:
            print(f"❌ Erreur lors de l'import du fichier {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def list_all_drives(self):
        """Liste tous les drives disponibles pour l'application"""
        token = self.get_access_token()
        
        print(f"\n📋 Liste de tous les drives disponibles:")
        
        url = "https://graph.microsoft.com/v1.0/drives"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            drives = response.json().get("value", [])
            if not drives:
                print("⚠️ Aucun drive accessible avec ce compte d'application")
                return []
                
            print(f"📁 {len(drives)} drives trouvés:")
            
            for i, drive in enumerate(drives, 1):
                name = drive.get("name", "Sans nom")
                id = drive.get("id")
                drive_type = drive.get("driveType", "Inconnu")
                owner = drive.get("owner", {}).get("user", {}).get("displayName", "Inconnu")
                
                print(f"  {i}. {name} (ID: {id})")
                print(f"     - Type: {drive_type}")
                print(f"     - Propriétaire: {owner}")
                
                # Marquer le drive configuré
                if id == self.drive_id:
                    print(f"     ✅ C'est le drive configuré dans les paramètres")
            
            # Si le drive configuré n'a pas été trouvé, le signaler
            if self.drive_id and self.drive_id not in [d.get("id") for d in drives]:
                print(f"\n⚠️ Le drive configuré (ID: {self.drive_id}) n'a pas été trouvé dans la liste!")
                print(f"    Vous devez mettre à jour GRAPH_DRIVE_ID avec l'un des IDs ci-dessus")
            
            return drives
        
        except Exception as e:
            print(f"❌ Erreur lors de la liste des drives: {e}")
            return []

    def run(self, limit: Optional[int] = None, dry_run: bool = False, list_drives: bool = False):
        """
        Exécute le processus complet d'importation depuis SharePoint
        
        Args:
            limit: Limite de fichiers à traiter (None pour tous)
            dry_run: Si True, liste les fichiers sans les télécharger ou les importer
            list_drives: Si True, liste tous les drives disponibles puis s'arrête
        """
        print(f"🔄 Démarrage de l'import depuis SharePoint")
          # Vérifier que les variables d'environnement nécessaires sont définies
        missing_vars = []
        for var_name in ['TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'GRAPH_DRIVE_ID']:
            var_value = getattr(self, var_name.lower(), None)
            if not var_value:
                missing_vars.append(var_name)
                
            # Debug: Afficher les valeurs pour diagnostiquer
            attr_value = getattr(self, var_name.lower(), "Non défini")
            print(f"DEBUG - {var_name}: {attr_value[:10]}... (type: {type(attr_value)})")
        
        if missing_vars:
            print(f"❌ Variables d'environnement manquantes: {', '.join(missing_vars)}")
            print("   Ces variables doivent être définies dans le fichier .env")
            print("\nDébug environment:")
            print(f"- Drive ID from settings: {settings.GRAPH_DRIVE_ID}")
            print(f"- Drive ID from env: {os.getenv('GRAPH_DRIVE_ID')}")
            print(f"- Drive ID from environ: {os.environ.get('GRAPH_DRIVE_ID')}")
            return
            
        # Si demandé, lister tous les drives et s'arrêter
        if list_drives:
            self.list_all_drives()
            return
            
        # 1. Lister les fichiers DPGF disponibles
        files = self.list_dpgf_files()
        
        if not files:
            print("❌ Aucun fichier DPGF trouvé sur SharePoint")
            print("   Vérifiez le chemin du dossier et les permissions")
            return
        
        # Limiter le nombre de fichiers à traiter si demandé
        if limit:
            files = files[:limit]
            print(f"ℹ️ Traitement limité à {limit} fichiers")
        
        if dry_run:
            print("\n📋 Mode simulation (dry run) - les fichiers ne seront pas téléchargés:")
            for idx, file in enumerate(files, 1):
                print(f"  {idx}. {file.get('name')} ({file.get('size', 0) / 1024:.1f} KB)")
            return
        
        # Obtenir une session de base de données
        try:
            # Créer une connexion à la base de données
            db = next(get_db())
            
            # 2. Traiter chaque fichier
            success_count = 0
            error_count = 0
            
            for idx, file in enumerate(files, 1):
                print(f"\n📄 Traitement du fichier {idx}/{len(files)}: {file.get('name')}")
                
                try:
                    # Télécharger le fichier
                    local_path = self.download_file(file)
                    
                    # Importer le fichier
                    dpgf_id = self.import_file(local_path, db)
                    
                    if dpgf_id:
                        # Marquer le fichier comme traité
                        self.mark_file_as_processed(file)
                        success_count += 1
                    else:
                        error_count += 1
                    
                    # Supprimer le fichier temporaire
                    if os.path.exists(local_path):
                        os.remove(local_path)
                        print(f"✅ Fichier temporaire supprimé: {local_path}")
                    
                except Exception as e:
                    print(f"❌ Erreur lors du traitement du fichier {file.get('name')}: {e}")
                    error_count += 1
                    # Continuer avec le fichier suivant
            
            print(f"\n✅ Traitement terminé pour {len(files)} fichiers DPGF")
            print(f"  - Importés avec succès: {success_count}")
            print(f"  - Échecs: {error_count}")
            
        except Exception as e:
            print(f"❌ Erreur générale: {e}")
        finally:
            # Fermer la connexion à la base de données
            db.close()


def debug_environment_vars():
    """Fonction de diagnostic pour vérifier les variables d'environnement"""
    print("\n🔍 DIAGNOSTIC DES VARIABLES D'ENVIRONNEMENT")
    
    # Recharger explicitement les variables d'environnement
    load_dotenv(override=True)
    
    # Variables à vérifier
    vars_to_check = [
        "TENANT_ID", 
        "CLIENT_ID", 
        "CLIENT_SECRET", 
        "GRAPH_DRIVE_ID",
        "GRAPH_DPFG_FOLDER",
        "DATABASE_URL"
    ]
    
    # Vérifier chaque variable
    for var_name in vars_to_check:
        # Valeurs depuis différentes sources
        os_env_value = os.environ.get(var_name, "Non défini")
        os_getenv_value = os.getenv(var_name, "Non défini")
        settings_value = getattr(settings, var_name, "Non défini") if hasattr(settings, var_name) else "Non disponible"
        
        # Formater les valeurs pour l'affichage (masquer les secrets)
        if var_name in ["CLIENT_SECRET", "DATABASE_URL"]:
            if os_env_value != "Non défini":
                os_env_value = f"{os_env_value[:5]}...{os_env_value[-4:] if len(os_env_value) > 8 else ''}"
            if os_getenv_value != "Non défini":
                os_getenv_value = f"{os_getenv_value[:5]}...{os_getenv_value[-4:] if len(os_getenv_value) > 8 else ''}"
            if settings_value != "Non défini" and settings_value != "Non disponible":
                settings_value = f"{settings_value[:5]}...{settings_value[-4:] if len(settings_value) > 8 else ''}"
        else:
            # Tronquer les valeurs longues
            if os_env_value != "Non défini" and len(os_env_value) > 30:
                os_env_value = f"{os_env_value[:15]}...{os_env_value[-10:]}"
