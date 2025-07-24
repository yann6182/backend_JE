"""
Script pour identifier et filtrer automatiquement les fichiers pertinents
de type DPGF (Décomposition du Prix Global et Forfaitaire), 
BPU (Bordereau des Prix Unitaires) et DQE (Détail Quantitatif Estimatif)
depuis SharePoint ou un répertoire local.

Ce script peut :
1. Parcourir un répertoire local
2. Se connecter à SharePoint et analyser les fichiers distants
3. Identifier les fichiers Excel pertinents
4. Télécharger et analyser les fichiers identifiés

Usage:
    # Analyse locale
    python identify_relevant_files_sharepoint.py --source-type local --source-dir <dossier_source> [options]
    
    # Analyse SharePoint
    python identify_relevant_files_sharepoint.py --source-type sharepoint --sharepoint-url <url> [options]

Options:
    --source-type TYPE          Type de source: 'local' ou 'sharepoint'
    --source-dir SOURCE_DIR     Chemin vers le répertoire source (pour local)
    --sharepoint-url URL        URL SharePoint à analyser
    --output-dir OUTPUT_DIR     Répertoire de destination pour les fichiers téléchargés
    --copy-files                Copier/télécharger les fichiers identifiés
    --deep-scan                 Analyse approfondie du contenu des fichiers
    --exclude-dirs DIRS         Dossiers à exclure, séparés par des virgules
    --log-file LOG_FILE         Fichier de log (par défaut: identification_results.log)
    --download-only             Télécharger seulement sans import en base
    --test-access               Tester l'accès SharePoint
"""

import os
import sys
import re
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Union
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import concurrent.futures
from collections import Counter
import tempfile
import requests
import msal
from dotenv import load_dotenv
from urllib.parse import urlparse, unquote
import json
import csv
import subprocess
import unicodedata

# Configuration de l'encodage pour Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configuration du logging avec gestion des répertoires
def setup_logging(log_dir: str = "logs", log_file: str = None):
    """Configure le système de logs avec création automatique du répertoire"""
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(exist_ok=True)
    
    if log_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"identification_sharepoint_{timestamp}.log"
    
    log_path = log_dir_path / log_file
    
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Log initialisé: {log_path}")
    return logger

# Initialiser le logger (sera reconfiguré dans main())
logger = logging.getLogger(__name__)

# Extensions de fichiers à considérer
EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm'}

# Mots-clés pour identifier les types de documents
KEYWORDS = {
    'DPGF': [
        'dpgf', 'décomposition du prix global', 'decomposition du prix global',
        'prix global et forfaitaire', 'forfaitaire', 'décomposition des prix',
        'dpgf lot', 'dpgf-lot'
    ],
    'BPU': [
        'bpu', 'bordereau des prix', 'bordereau de prix', 'prix unitaires',
        'bordereau prix unitaires'
    ],
    'DQE': [
        'dqe', 'détail quantitatif', 'detail quantitatif', 'quantitatif estimatif',
        'détail estimatif', 'detail estimatif'
    ]
}

# Expression régulière pour les motifs de nommage typiques
FILE_PATTERNS = {
    'DPGF': [
        r'dpgf[-_ ]lot[_ ]?\d+',
        r'lot[_ ]?\d+[-_ ]dpgf',
        r'dpgf.*\d{2,4}',
    ],
    'BPU': [
        r'bpu[-_ ]lot[_ ]?\d+',
        r'lot[_ ]?\d+[-_ ]bpu',
        r'bpu.*\d{2,4}',
    ],
    'DQE': [
        r'dqe[-_ ]lot[_ ]?\d+',
        r'lot[_ ]?\d+[-_ ]dqe',
        r'dqe.*\d{2,4}',
    ]
}

# Colonnes typiques pour chaque type de document
COLUMNS_PATTERNS = {
    'DPGF': [
        ['designation', 'quantite', 'prix', 'montant'],
        ['designation', 'unite', 'quantite', 'pu', 'montant'],
        ['description', 'quantite', 'prix', 'total'],
    ],
    'BPU': [
        ['designation', 'unite', 'prix'],
        ['description', 'unite', 'pu'],
        ['reference', 'libelle', 'unite', 'prix'],
    ],
    'DQE': [
        ['designation', 'quantite', 'prix', 'montant'],
        ['designation', 'unite', 'quantite', 'pu', 'total'],
        ['reference', 'description', 'quantite', 'pu', 'montant'],
    ]
}

class SharePointClient:
    """Client pour accéder aux fichiers SharePoint via Microsoft Graph API"""
    
    def __init__(self):
        load_dotenv()
        self.tenant_id = os.getenv('TENANT_ID')
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.drive_id = os.getenv('GRAPH_DRIVE_ID')
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Variables d'environnement manquantes : TENANT_ID, CLIENT_ID, CLIENT_SECRET")
        
        self.access_token = None
        self.token_expires_at = None
        
    def get_access_token(self) -> str:
        """Obtient un token d'accès pour Microsoft Graph API avec gestion d'erreurs améliorée"""
        if self.access_token and self.token_expires_at and datetime.now().timestamp() < self.token_expires_at:
            return self.access_token
            
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )
        
        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            # Token expire dans 3600 secondes par défaut, on prend une marge
            self.token_expires_at = datetime.now().timestamp() + (result.get("expires_in", 3600) - 300)
            return self.access_token
        else:
            error_desc = result.get('error_description', 'Erreur inconnue')
            error_code = result.get('error', 'unknown_error')
            
            # Messages d'erreur plus clairs selon le code d'erreur
            if 'invalid_client' in error_code.lower():
                raise Exception(f"❌ Erreur d'authentification: Client ID ou Client Secret invalide.\n"
                               f"Vérifiez vos variables d'environnement TENANT_ID, CLIENT_ID, CLIENT_SECRET")
            elif 'unauthorized_client' in error_code.lower():
                raise Exception(f"❌ Permissions insuffisantes: L'application n'a pas les permissions requises.\n"
                               f"Vérifiez que les permissions 'Files.Read.All' et 'Sites.Read.All' sont accordées dans Azure AD")
            else:
                raise Exception(f"❌ Impossible d'obtenir le token d'accès: {error_desc}\n"
                               f"Code d'erreur: {error_code}")
    
    def _handle_sharepoint_error(self, response: requests.Response, operation: str) -> None:
        """Gère les erreurs SharePoint avec des messages explicites"""
        if response.status_code == 401:
            raise Exception(f"❌ Erreur 401 - Non autorisé lors de {operation}.\n"
                           f"🔧 Solutions possibles:\n"
                           f"   • Vérifiez que le token d'accès est valide\n"
                           f"   • Vérifiez les permissions 'Files.Read.All' dans Azure AD\n"
                           f"   • Assurez-vous que l'application est autorisée sur ce site SharePoint")
        elif response.status_code == 403:
            raise Exception(f"❌ Erreur 403 - Accès refusé lors de {operation}.\n"
                           f"🔧 Solutions possibles:\n"
                           f"   • Vérifiez que vous avez les permissions de lecture sur ce dossier\n"
                           f"   • Contactez l'administrateur SharePoint pour obtenir l'accès\n"
                           f"   • Vérifiez que GRAPH_DRIVE_ID correspond au bon site SharePoint")
        elif response.status_code == 404:
            raise Exception(f"❌ Erreur 404 - Ressource non trouvée lors de {operation}.\n"
                           f"🔧 Solutions possibles:\n"
                           f"   • Vérifiez que le chemin du dossier est correct\n"
                           f"   • Vérifiez que GRAPH_DRIVE_ID correspond au bon drive\n"
                           f"   • Le dossier a peut-être été déplacé ou supprimé")
        elif response.status_code == 429:
            raise Exception(f"❌ Erreur 429 - Trop de requêtes lors de {operation}.\n"
                           f"🔧 Solutions possibles:\n"
                           f"   • Attendez quelques minutes avant de réessayer\n"
                           f"   • Réduisez le nombre de fichiers traités simultanément")
        else:
            raise Exception(f"❌ Erreur {response.status_code} lors de {operation}.\n"
                           f"Détails: {response.text}")
    
    
    def parse_sharepoint_url(self, url: str) -> Tuple[str, str]:
        """
        Parse une URL SharePoint pour extraire le site et le chemin
        
        Args:
            url: URL SharePoint (ex: https://sef92230.sharepoint.com/sites/etudes/Documents%20partages/Forms/AllItems.aspx)
            
        Returns:
            Tuple[site_url, folder_path]: URL du site et chemin du dossier
        """
        parsed = urlparse(url)
        
        # Extraire le nom du site
        path_parts = parsed.path.strip('/').split('/')
        if 'sites' in path_parts:
            site_index = path_parts.index('sites')
            if site_index + 1 < len(path_parts):
                site_name = path_parts[site_index + 1]
                site_url = f"{parsed.scheme}://{parsed.netloc}/sites/{site_name}"
                
                # Le chemin commence après le nom du site
                if 'Documents' in path_parts:
                    docs_index = path_parts.index('Documents')
                    # On prend "Documents partages" ou similaire
                    if docs_index + 1 < len(path_parts) and 'partages' in path_parts[docs_index + 1].lower():
                        folder_path = f"/{'/'.join(path_parts[docs_index:docs_index+2])}"
                    else:
                        folder_path = f"/{path_parts[docs_index]}"
                else:
                    folder_path = "/"
                
                return site_url, folder_path
        
        # Fallback
        return f"{parsed.scheme}://{parsed.netloc}", "/"
    
    def get_drive_id_from_site(self, site_url: str) -> str:
        """Obtient l'ID du drive depuis l'URL du site SharePoint"""
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Extraire le hostname et le chemin du site
        parsed = urlparse(site_url)
        hostname = parsed.netloc
        site_path = parsed.path
        
        # Requête pour obtenir l'ID du site
        site_request_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}"
        response = requests.get(site_request_url, headers=headers)
        
        if response.status_code == 200:
            site_data = response.json()
            site_id = site_data['id']
            
            # Obtenir l'ID du drive par défaut du site
            drive_request_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
            drive_response = requests.get(drive_request_url, headers=headers)
            
            if drive_response.status_code == 200:
                drive_data = drive_response.json()
                return drive_data['id']
        
        raise Exception(f"Impossible d'obtenir l'ID du drive depuis {site_url}")
    
    def list_first_10_files(self, folder_path: str = "/") -> List[Dict]:
        """
        Liste les 10 premiers fichiers d'un dossier SharePoint (pour test rapide)
        
        Args:
            folder_path: Chemin du dossier (ex: "/Documents partages")
            
        Returns:
            List[Dict]: Liste des 10 premiers fichiers avec leurs métadonnées
        """
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        files = []
        
        if not self.drive_id:
            raise ValueError("GRAPH_DRIVE_ID non défini dans les variables d'environnement")
        
        if folder_path == "/":
            url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children?$top=10"
        else:
            # Encoder le chemin pour l'URL
            encoded_path = requests.utils.quote(folder_path.lstrip('/'), safe='/')
            url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{encoded_path}:/children?$top=10"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('value', []):
                    if 'file' in item:  # C'est un fichier
                        file_info = {
                            'id': item['id'],
                            'name': item['name'],
                            'path': f"{folder_path.rstrip('/')}/{item['name']}",
                            'size': item['size'],
                            'created': item['createdDateTime'],
                            'modified': item['lastModifiedDateTime'],
                            'download_url': item.get('@microsoft.graph.downloadUrl', ''),
                            'web_url': item.get('webUrl', ''),
                            'type': 'file'
                        }
                        files.append(file_info)
                    elif 'folder' in item:  # C'est un dossier
                        folder_info = {
                            'id': item['id'],
                            'name': item['name'],
                            'path': f"{folder_path.rstrip('/')}/{item['name']}",
                            'size': 0,
                            'created': item['createdDateTime'],
                            'modified': item['lastModifiedDateTime'],
                            'web_url': item.get('webUrl', ''),
                            'type': 'folder'
                        }
                        files.append(folder_info)
                        
            elif response.status_code == 404:
                logger.warning(f"Dossier non trouvé: {folder_path}")
                return []
            else:
                self._handle_sharepoint_error(response, f"la lecture du dossier {folder_path}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de connexion lors du scan du dossier {folder_path}: {str(e)}")
            return []
        except Exception as e:
            if "❌ Erreur" in str(e):  # C'est déjà une erreur formatée
                raise e
            else:
                logger.error(f"Erreur lors du scan du dossier {folder_path}: {str(e)}")
                return []
        
        return files

    def list_files_in_folder(self, folder_path: str = "/", recursive: bool = True) -> List[Dict]:
        """
        Liste les fichiers dans un dossier SharePoint
        
        Args:
            folder_path: Chemin du dossier (ex: "/Documents partages")
            recursive: Si True, parcourt récursivement les sous-dossiers
            
        Returns:
            List[Dict]: Liste des fichiers avec leurs métadonnées
        """
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        files = []
        
        # Si on n'a pas de drive_id, essayer de l'obtenir
        if not self.drive_id:
            raise ValueError("GRAPH_DRIVE_ID non défini dans les variables d'environnement")
        
        def scan_folder(path: str):
            # Normaliser le chemin pour éviter les problèmes d'encodage
            path = sanitize_sharepoint_path(path)
            
            if path == "/":
                base_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root/children"
            else:
                # Encoder le chemin pour l'URL avec gestion UTF-8 des caractères spéciaux
                try:
                    # Nettoyer le chemin d'abord
                    clean_path = path.lstrip('/')
                    
                    # Encoder chaque segment du chemin séparément pour une meilleure gestion
                    path_segments = [requests.utils.quote(segment, safe='', encoding='utf-8') 
                                   for segment in clean_path.split('/') if segment]
                    encoded_path = '/'.join(path_segments)
                    
                    base_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{encoded_path}:/children"
                    
                except UnicodeError as e:
                    logger.warning(f"Erreur d'encodage pour le chemin {path}: {str(e)}")
                    # Fallback: utiliser le chemin sans encodage spécial
                    clean_path = path.lstrip('/')
                    base_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{clean_path}:/children"
                except Exception as e:
                    logger.warning(f"Erreur lors de la construction de l'URL pour {path}: {str(e)}")
                    # Dernier fallback
                    clean_path = path.lstrip('/').replace('ç', 'c').replace('é', 'e').replace('è', 'e').replace('à', 'a').replace('ù', 'u')
                    base_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{clean_path}:/children"
            
            # Gérer la pagination pour obtenir TOUS les fichiers
            url = base_url
            
            try:
                while url:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        
                        for item in data.get('value', []):
                            if 'file' in item:  # C'est un fichier
                                file_info = {
                                    'id': item['id'],
                                    'name': item['name'],
                                    'path': f"{path.rstrip('/')}/{item['name']}",
                                    'size': item['size'],
                                    'created': item['createdDateTime'],
                                    'modified': item['lastModifiedDateTime'],
                                    'download_url': item.get('@microsoft.graph.downloadUrl', ''),
                                    'web_url': item.get('webUrl', ''),
                                    'type': 'file'
                                }
                                files.append(file_info)
                            elif 'folder' in item:  # C'est un dossier
                                folder_info = {
                                    'id': item['id'],
                                    'name': item['name'],
                                    'path': f"{path.rstrip('/')}/{item['name']}",
                                    'size': 0,
                                    'created': item['createdDateTime'],
                                    'modified': item['lastModifiedDateTime'],
                                    'web_url': item.get('webUrl', ''),
                                    'type': 'folder'
                                }
                                files.append(folder_info)
                                
                                if recursive:
                                    # Construire le chemin du sous-dossier avec gestion UTF-8
                                    try:
                                        folder_path_new = f"{path.rstrip('/')}/{item['name']}"
                                        # Normaliser le chemin du sous-dossier
                                        folder_path_new = sanitize_sharepoint_path(folder_path_new)
                                        scan_folder(folder_path_new)
                                    except Exception as e:
                                        logger.warning(f"Erreur lors du scan du sous-dossier {item['name']}: {str(e)}")
                                        # Essayer quand même avec le chemin brut
                                        try:
                                            folder_path_new = f"{path.rstrip('/')}/{item['name']}"
                                            scan_folder(folder_path_new)
                                        except:
                                            logger.error(f"Impossible de scanner le dossier: {item['name']}")
                        
                        # Vérifier s'il y a une page suivante
                        url = data.get('@odata.nextLink')
                        
                    elif response.status_code == 404:
                        logger.warning(f"Dossier non trouvé: {path}")
                        # Essayer avec un encodage différent si le chemin contient des caractères spéciaux
                        if any(ord(c) > 127 for c in path):
                            try:
                                # Essayer avec un encodage URL différent
                                alt_encoded_path = requests.utils.quote(path.lstrip('/'), safe='/', encoding='utf-8', errors='replace')
                                alt_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{alt_encoded_path}:/children"
                                alt_response = requests.get(alt_url, headers=headers)
                                if alt_response.status_code == 200:
                                    logger.info(f"Succès avec encodage alternatif pour: {path}")
                                    # Traiter la réponse alternative
                                    data = alt_response.json()
                                    # ... continuer le traitement normalement
                                else:
                                    logger.debug(f"Encodage alternatif échoué aussi pour: {path}")
                            except Exception as e:
                                logger.debug(f"Erreur avec encodage alternatif pour {path}: {str(e)}")
                        break
                    else:
                        logger.error(f"Erreur lors de la lecture du dossier {path}: {response.status_code} - {response.text}")
                        break
                        
            except Exception as e:
                logger.error(f"Erreur lors du scan du dossier {path}: {str(e)}")
        
        scan_folder(folder_path)
        return files
    
    def download_file(self, file_id: str, local_path: str) -> bool:
        """
        Télécharge un fichier depuis SharePoint
        
        Args:
            file_id: ID du fichier SharePoint
            local_path: Chemin local où enregistrer le fichier
            
        Returns:
            bool: True si le téléchargement a réussi
        """
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Obtenir l'URL de téléchargement
        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{file_id}/content"
        
        try:
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                logger.error(f"Erreur lors du téléchargement: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement: {str(e)}")
            return False

    def get_folders_summary(self, folder_path: str = "/") -> Dict:
        """
        Obtient un résumé rapide des dossiers pour évaluation
        
        Args:
            folder_path: Chemin du dossier racine
            
        Returns:
            Dict: Résumé des dossiers avec comptages
        """
        try:
            all_root_items = self.list_files_in_folder(folder_path, recursive=False)
            folders = [item for item in all_root_items if item.get('type') == 'folder']
            
            summary = {
                'total_folders': len(folders),
                'folders': [],
                'estimated_files': 0
            }
            
            # Pour les 5 premiers dossiers, obtenir un aperçu rapide
            sample_folders = folders[:5]
            for folder in sample_folders:
                folder_path_current = f"{folder_path.rstrip('/')}/{folder['name']}"
                try:
                    # Compter seulement les 50 premiers éléments pour estimation
                    first_files = self.list_first_10_files(folder_path_current)
                    
                    folder_info = {
                        'name': folder['name'],
                        'sample_files': len(first_files),
                        'excel_files': len([f for f in first_files if any(f['name'].lower().endswith(ext) for ext in EXCEL_EXTENSIONS)])
                    }
                    summary['folders'].append(folder_info)
                    summary['estimated_files'] += folder_info['sample_files'] * 5  # Estimation grossière
                    
                except Exception as e:
                    logger.warning(f"Erreur lors de l'aperçu de {folder['name']}: {str(e)}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Erreur lors du résumé des dossiers: {str(e)}")
            return {'total_folders': 0, 'folders': [], 'estimated_files': 0}


def sanitize_sharepoint_path(path: str) -> str:
    """
    Nettoie et normalise un chemin SharePoint pour éviter les erreurs d'encodage
    
    Args:
        path: Chemin SharePoint potentiellement avec caractères spéciaux
        
    Returns:
        str: Chemin nettoyé et correctement encodé
    """
    if not path:
        return path
    
    try:
        # S'assurer que le chemin est en UTF-8
        if isinstance(path, bytes):
            path = path.decode('utf-8', errors='replace')
        elif isinstance(path, str):
            # Re-encoder pour s'assurer de la cohérence
            path = path.encode('utf-8', errors='replace').decode('utf-8')
        
        # Normaliser les caractères Unicode (décomposer puis recomposer)
        path = unicodedata.normalize('NFC', path)
        
        # Remplacer les caractères problématiques souvent mal encodés
        replacements = {
            'Ã©': 'é', 'Ã¨': 'è', 'Ã ': 'à', 'Ã§': 'ç', 'Ã¹': 'ù',
            'Ãª': 'ê', 'Ã´': 'ô', 'Ã®': 'î', 'Ã¯': 'ï', 'Ã«': 'ë',
            'Ã‰': 'É', 'Ãˆ': 'È', 'Ã€': 'À', 'Ã‡': 'Ç', 'Ã™': 'Ù',
            'ï¿½': '', # Caractère de remplacement Unicode
            '�': '',   # Caractère de remplacement
        }
        
        for bad_char, good_char in replacements.items():
            path = path.replace(bad_char, good_char)
        
        return path
        
    except Exception as e:
        logger.warning(f"Erreur lors de la normalisation du chemin {path}: {str(e)}")
        # Fallback : garder le chemin original
        return str(path)

def normalize_string(s: str) -> str:
    """Normalise une chaîne en supprimant les accents, les caractères spéciaux et en la mettant en minuscule."""
    if not isinstance(s, str):
        return ""
    
    # Supprime caractères spéciaux et convertit en minuscule
    s = s.lower()
    s = re.sub(r'[éèêë]', 'e', s)
    s = re.sub(r'[àâä]', 'a', s)
    s = re.sub(r'[ùûü]', 'u', s)
    s = re.sub(r'[îï]', 'i', s)
    s = re.sub(r'[ôö]', 'o', s)
    s = re.sub(r'[ç]', 'c', s)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return s.strip()

def get_column_confidence(df: pd.DataFrame, doc_type: str) -> float:
    """
    Calcule un score de confiance basé sur la correspondance des noms de colonnes
    avec les modèles attendus pour le type de document.
    
    Returns:
        float: Score de confiance entre 0 et 1
    """
    confidence = 0.0
    
    # Normaliser les noms de colonnes
    cols = [normalize_string(str(col)) for col in df.columns]
    
    # Chercher les modèles de colonnes typiques
    for pattern in COLUMNS_PATTERNS.get(doc_type, []):
        found = 0
        for expected_col in pattern:
            for col in cols:
                if expected_col in col:
                    found += 1
                    break
        
        if len(pattern) > 0:
            score = found / len(pattern)
            confidence = max(confidence, score)
    
    return confidence

def detect_document_type_from_filename(filename: str) -> Dict[str, float]:
    """
    Détecte le type probable du document basé sur son nom de fichier.
    
    Returns:
        Dict[str, float]: Dictionnaire des types de documents avec un score de confiance
    """
    filename_lower = filename.lower()
    scores = {'DPGF': 0.0, 'BPU': 0.0, 'DQE': 0.0}
    
    # Vérification directe des mots-clés dans le nom de fichier
    for doc_type, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in filename_lower:
                scores[doc_type] += 0.5
                break
    
    # Vérification des patterns dans le nom de fichier
    for doc_type, patterns in FILE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                scores[doc_type] += 0.5
                break
    
    return scores

def scan_excel_content(filepath: str, deep_scan: bool = False) -> Dict[str, float]:
    """
    Analyse le contenu d'un fichier Excel pour détecter le type de document.
    
    Args:
        filepath: Chemin vers le fichier Excel
        deep_scan: Si True, effectue une analyse plus approfondie (plus lente)
        
    Returns:
        Dict[str, float]: Dictionnaire des types de documents avec un score de confiance
    """
    scores = {'DPGF': 0.0, 'BPU': 0.0, 'DQE': 0.0}
    
    try:
        # Lire uniquement les 100 premières lignes pour l'analyse rapide
        max_rows = None if deep_scan else 100
        df = pd.read_excel(filepath, nrows=max_rows, engine='openpyxl')
        
        # Vérifier les noms de colonnes typiques
        for doc_type in scores.keys():
            col_score = get_column_confidence(df, doc_type)
            scores[doc_type] += col_score * 0.7  # La structure des colonnes est un fort indicateur
        
        # Rechercher les mots-clés dans le contenu
        if deep_scan:
            content_text = ""
            for col in df.columns:
                if isinstance(col, str):
                    content_text += f" {col}"
            
            # Ajouter les premières cellules de chaque colonne
            for col in df.columns:
                first_values = df[col].dropna().head(10)
                for val in first_values:
                    if isinstance(val, str):
                        content_text += f" {val}"
            
            content_text = normalize_string(content_text)
            
            for doc_type, keywords in KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content_text:
                        scores[doc_type] += 0.3
                        break
                        
    except Exception as e:
        logger.warning(f"Erreur lors de l'analyse du fichier {filepath}: {str(e)}")
    
    return scores

def is_folder_relevant(folder_name: str) -> bool:
    """
    Détermine si un dossier est potentiellement pertinent pour contenir des fichiers DPGF/BPU/DQE
    
    Args:
        folder_name: Nom du dossier à analyser
        
    Returns:
        bool: True - Tous les dossiers sont explorés pour trouver des fichiers Excel pertinents
    """
  
    return True

def analyze_file(filepath: str, deep_scan: bool = False) -> Tuple[str, Dict[str, float], float]:
    """
    Analyse un fichier pour déterminer son type et son score de confiance.
    
    Returns:
        Tuple[filepath, scores, max_score]: Chemin du fichier, scores par type, score maximum
    """
    filename = os.path.basename(filepath)
    
    # Analyse basée sur le nom de fichier
    filename_scores = detect_document_type_from_filename(filename)
    
    # Analyse du contenu Excel
    content_scores = scan_excel_content(filepath, deep_scan)
    
    # Combinaison des scores
    combined_scores = {}
    for doc_type in filename_scores.keys():
        combined_scores[doc_type] = filename_scores[doc_type] + content_scores[doc_type]
    
    max_score = max(combined_scores.values()) if combined_scores.values() else 0.0
    
    return filepath, combined_scores, max_score

class FileIdentifier:
    """Classe principale pour l'identification des fichiers DPGF/BPU/DQE"""
    
    def __init__(self, min_confidence: float = 0.3, max_files: int = None):
        self.min_confidence = min_confidence
        self.max_files = max_files
        self.sharepoint_client = None
        
    def init_sharepoint(self):
        """Initialise le client SharePoint"""
        if not self.sharepoint_client:
            self.sharepoint_client = SharePointClient()
    
    def identify_local_files(self, source_dir: str, exclude_dirs: Set[str] = None, 
                           deep_scan: bool = False) -> List[Dict]:
        """
        Identifie les fichiers pertinents dans un répertoire local.
        
        Args:
            source_dir: Répertoire source
            exclude_dirs: Dossiers à exclure
            deep_scan: Analyse approfondie
            
        Returns:
            List[Dict]: Liste des fichiers identifiés avec leurs métadonnées
        """
        if exclude_dirs is None:
            exclude_dirs = set()
            
        # Trouver tous les fichiers Excel
        excel_files = []
        for root, dirs, files in os.walk(source_dir):
            # Filtrer les répertoires exclus
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if any(file.lower().endswith(ext) for ext in EXCEL_EXTENSIONS):
                    filepath = os.path.join(root, file)
                    excel_files.append(filepath)
        
        logger.info(f"Trouvé {len(excel_files)} fichiers Excel à analyser")
        
        # Analyser les fichiers
        identified_files = []
        
        with tqdm(total=len(excel_files), desc="Analyse des fichiers") as pbar:
            for filepath in excel_files:
                try:
                    file_path, scores, max_score = analyze_file(filepath, deep_scan)
                    
                    if max_score >= self.min_confidence:
                        best_type = max(scores, key=scores.get)
                        
                        file_info = {
                            'path': file_path,
                            'name': os.path.basename(file_path),
                            'type': best_type,
                            'confidence': max_score,
                            'scores': scores,
                            'size': os.path.getsize(file_path),
                            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                            'source': 'local'
                        }
                        identified_files.append(file_info)
                        
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse de {filepath}: {str(e)}")
                
                pbar.update(1)
        
        return identified_files
    
    def identify_sharepoint_files(self, sharepoint_url: str, deep_scan: bool = False,
                                download_dir: str = None) -> List[Dict]:
        """
        Identifie les fichiers pertinents sur SharePoint.
        
        Args:
            sharepoint_url: URL SharePoint
            deep_scan: Analyse approfondie (nécessite téléchargement)
            download_dir: Répertoire pour télécharger les fichiers temporairement
            
        Returns:
            List[Dict]: Liste des fichiers identifiés avec leurs métadonnées
        """
        self.init_sharepoint()
        
        # Parse l'URL SharePoint pour extraire le chemin du dossier
        try:
            site_url, folder_path = self.sharepoint_client.parse_sharepoint_url(sharepoint_url)
            logger.info(f"Analyse du site: {site_url}")
            logger.info(f"Dossier: {folder_path}")
        except Exception as e:
            logger.error(f"Erreur lors du parsing de l'URL: {str(e)}")
            # Utiliser le dossier racine par défaut
            folder_path = "/"
        
        # Si on analyse le dossier racine, explorer tous les sous-dossiers
        if folder_path == "/":
            logger.info("🔍 Exploration du dossier racine - analyse de tous les dossiers...")
            
            # Obtenir TOUS les éléments du dossier racine pour une analyse complète
            try:
                all_root_items = self.sharepoint_client.list_files_in_folder("/", recursive=False)
                # Filtrer seulement les dossiers
                all_folders = [item for item in all_root_items if item.get('type') == 'folder']
                logger.info(f"📊 Trouvé {len(all_root_items)} éléments dont {len(all_folders)} dossiers dans la racine")
            except Exception as e:
                logger.warning(f"Impossible d'obtenir la liste complète, utilisation de la liste partielle: {str(e)}")
                root_items = self.sharepoint_client.list_first_10_files("/")
                all_folders = [item for item in root_items if item.get('type') == 'folder']
            
            # Maintenant tous les dossiers sont considérés comme pertinents
            logger.info(f"🎯 Exploration de tous les {len(all_folders)} dossiers pour rechercher des fichiers Excel...")
            all_files = []
            
            # Explorer chaque dossier
            for i, folder in enumerate(all_folders, 1):
                folder_path_current = f"/{folder['name']}"
                logger.info(f"🔍 ({i}/{len(all_folders)}) Exploration du dossier: {folder['name']}")
                try:
                    folder_files = self.sharepoint_client.list_files_in_folder(folder_path_current, recursive=True)
                    
                    # Compter les fichiers Excel dans ce dossier
                    excel_files_in_folder = [f for f in folder_files 
                                           if any(f['name'].lower().endswith(ext) for ext in EXCEL_EXTENSIONS)]
                    
                    all_files.extend(folder_files)
                    logger.info(f"   → {len(folder_files)} fichier(s) total, {len(excel_files_in_folder)} Excel")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Erreur lors de l'exploration de {folder['name']}: {str(e)}")
                                
            logger.info(f"📈 Exploration terminée: {len(all_files)} fichiers trouvés au total")
        else:
            # Lister les fichiers du dossier spécifié
            logger.info("Récupération de la liste des fichiers SharePoint...")
            all_files = self.sharepoint_client.list_files_in_folder(folder_path, recursive=True)
        
        # Filtrer les fichiers Excel
        excel_files = [f for f in all_files 
                      if any(f['name'].lower().endswith(ext) for ext in EXCEL_EXTENSIONS)]
        
        logger.info(f"Trouvé {len(excel_files)} fichiers Excel sur SharePoint")
        
        # Limiter le nombre de fichiers si spécifié (utile pour les tests)
        if self.max_files and len(excel_files) > self.max_files:
            logger.info(f"🚀 Limitation activée: traitement des {self.max_files} premiers fichiers")
            excel_files = excel_files[:self.max_files]
        
        identified_files = []
        temp_dir = download_dir or tempfile.mkdtemp(prefix="sharepoint_analysis_")
        
        with tqdm(total=len(excel_files), desc="Analyse des fichiers SharePoint") as pbar:
            for file_info in excel_files:
                try:
                    # Analyse basique sur le nom de fichier
                    filename_scores = detect_document_type_from_filename(file_info['name'])
                    max_filename_score = max(filename_scores.values()) if filename_scores.values() else 0.0
                    
                    # Si l'analyse approfondie est demandée ou si le score du nom est prometteur
                    content_scores = {'DPGF': 0.0, 'BPU': 0.0, 'DQE': 0.0}
                    if deep_scan or max_filename_score >= self.min_confidence * 0.5:
                        # Télécharger temporairement pour analyser le contenu
                        temp_file_path = os.path.join(temp_dir, file_info['name'])
                        
                        if self.sharepoint_client.download_file(file_info['id'], temp_file_path):
                            content_scores = scan_excel_content(temp_file_path, deep_scan)
                            
                            # Nettoyer le fichier temporaire si pas dans le dossier de téléchargement permanent
                            if download_dir is None:
                                try:
                                    os.remove(temp_file_path)
                                except:
                                    pass
                    
                    # Combinaison des scores
                    combined_scores = {}
                    for doc_type in filename_scores.keys():
                        combined_scores[doc_type] = filename_scores[doc_type] + content_scores[doc_type]
                    
                    max_score = max(combined_scores.values()) if combined_scores.values() else 0.0
                    
                    if max_score >= self.min_confidence:
                        best_type = max(combined_scores, key=combined_scores.get)
                        
                        result_info = {
                            'path': file_info['path'],
                            'name': file_info['name'],
                            'type': best_type,
                            'confidence': max_score,
                            'scores': combined_scores,
                            'size': file_info['size'],
                            'modified': file_info['modified'],
                            'created': file_info['created'],
                            'sharepoint_id': file_info['id'],
                            'web_url': file_info.get('web_url', ''),
                            'source': 'sharepoint'
                        }
                        identified_files.append(result_info)
                        
                except Exception as e:
                    logger.error(f"Erreur lors de l'analyse de {file_info['name']}: {str(e)}")
                
                pbar.update(1)
        
        # Nettoyer le répertoire temporaire si créé automatiquement
        if download_dir is None:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
        return identified_files
    
    def download_identified_files(self, identified_files: List[Dict], output_dir: str) -> List[Dict]:
        """
        Télécharge les fichiers identifiés depuis SharePoint.
        
        Args:
            identified_files: Liste des fichiers identifiés
            output_dir: Répertoire de destination
            
        Returns:
            List[Dict]: Liste des fichiers téléchargés avec leurs nouveaux chemins
        """
        os.makedirs(output_dir, exist_ok=True)
        downloaded_files = []
        
        sharepoint_files = [f for f in identified_files if f.get('source') == 'sharepoint']
        if not sharepoint_files:
            logger.info("Aucun fichier SharePoint à télécharger")
            return identified_files
        
        self.init_sharepoint()
        
        with tqdm(total=len(sharepoint_files), desc="Téléchargement des fichiers") as pbar:
            for file_info in sharepoint_files:
                try:
                    # Créer le chemin de destination
                    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', file_info['name'])
                    local_path = os.path.join(output_dir, safe_filename)
                    
                    # Éviter les doublons
                    counter = 1
                    base_name, ext = os.path.splitext(local_path)
                    while os.path.exists(local_path):
                        local_path = f"{base_name}_{counter}{ext}"
                        counter += 1
                    
                    if self.sharepoint_client.download_file(file_info['sharepoint_id'], local_path):
                        # Mettre à jour les informations du fichier
                        updated_info = file_info.copy()
                        updated_info['local_path'] = local_path
                        updated_info['downloaded'] = True
                        downloaded_files.append(updated_info)
                        logger.info(f"Téléchargé: {file_info['name']} -> {local_path}")
                    else:
                        logger.error(f"Échec du téléchargement: {file_info['name']}")
                        
                except Exception as e:
                    logger.error(f"Erreur lors du téléchargement de {file_info['name']}: {str(e)}")
                
                pbar.update(1)
        
        # Ajouter les fichiers locaux (non SharePoint) à la liste
        local_files = [f for f in identified_files if f.get('source') != 'sharepoint']
        downloaded_files.extend(local_files)
        
        return downloaded_files

def generate_report(identified_files: List[Dict], output_dir: str = "reports", 
                   output_basename: str = None, formats: List[str] = None):
    """
    Génère un rapport des fichiers identifiés dans multiple formats
    
    Args:
        identified_files: Liste des fichiers identifiés
        output_dir: Répertoire de sortie pour les rapports
        output_basename: Nom de base pour les fichiers (sans extension)
        formats: Liste des formats de sortie ('txt', 'csv', 'json', 'xlsx')
    """
    if not identified_files:
        logger.info("Aucun fichier identifié à inclure dans le rapport")
        return []
    
    # Configuration par défaut
    if formats is None:
        formats = ['txt', 'csv']
    
    if output_basename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_basename = f"identified_files_{timestamp}"
    
    # Créer le répertoire de sortie
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(exist_ok=True)
    
    # Statistiques
    stats = {
        'total': len(identified_files),
        'by_type': Counter(f['type'] for f in identified_files),
        'by_source': Counter(f.get('source', 'unknown') for f in identified_files),
        'avg_confidence': sum(f['confidence'] for f in identified_files) / len(identified_files)
    }
    
    # Trier par confiance décroissante
    identified_files.sort(key=lambda x: x['confidence'], reverse=True)
    
    generated_files = []
    
    # 📄 Rapport texte
    if 'txt' in formats:
        txt_file = output_dir_path / f"{output_basename}.txt"
        report_lines = [
            "=" * 80,
            "RAPPORT D'IDENTIFICATION DES FICHIERS DPGF/BPU/DQE",
            "=" * 80,
            f"Date d'analyse: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Fichiers identifiés: {stats['total']}",
            f"Confiance moyenne: {stats['avg_confidence']:.2f}",
            "",
            "RÉPARTITION PAR TYPE:",
            *[f"  {doc_type}: {count}" for doc_type, count in stats['by_type'].items()],
            "",
            "RÉPARTITION PAR SOURCE:",
            *[f"  {source}: {count}" for source, count in stats['by_source'].items()],
            "",
            "DÉTAIL DES FICHIERS:",
            "-" * 80,
        ]
        
        for i, file_info in enumerate(identified_files, 1):
            report_lines.extend([
                f"{i:3d}. {file_info['name']}",
                f"     Type: {file_info['type']} (confiance: {file_info['confidence']:.2f})",
                f"     Chemin: {file_info['path']}",
                f"     Taille: {file_info['size']:,} octets",
                f"     Modifié: {file_info['modified']}",
                f"     Source: {file_info.get('source', 'unknown')}",
                ""
            ])
        
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))
        
        generated_files.append(str(txt_file))
        print("\n".join(report_lines))
    
    # 📊 Rapport CSV
    if 'csv' in formats:
        csv_file = output_dir_path / f"{output_basename}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Nom', 'Type', 'Confiance', 'Chemin', 'Taille', 'Modifié', 'Source',
                'Score_DPGF', 'Score_BPU', 'Score_DQE', 'SharePoint_ID'
            ])
            
            for file_info in identified_files:
                scores = file_info.get('scores', {})
                writer.writerow([
                    file_info['name'],
                    file_info['type'],
                    f"{file_info['confidence']:.3f}",
                    file_info['path'],
                    file_info['size'],
                    file_info['modified'],
                    file_info.get('source', 'unknown'),
                    f"{scores.get('DPGF', 0):.3f}",
                    f"{scores.get('BPU', 0):.3f}",
                    f"{scores.get('DQE', 0):.3f}",
                    file_info.get('sharepoint_id', '')
                ])
        
        generated_files.append(str(csv_file))
    
    # 🔧 Rapport JSON
    if 'json' in formats:
        json_file = output_dir_path / f"{output_basename}.json"
        
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_files': stats['total'],
                'average_confidence': stats['avg_confidence'],
                'stats_by_type': dict(stats['by_type']),
                'stats_by_source': dict(stats['by_source'])
            },
            'files': identified_files
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        generated_files.append(str(json_file))
    
    # 📋 Rapport Excel
    if 'xlsx' in formats:
        xlsx_file = output_dir_path / f"{output_basename}.xlsx"
        
        try:
            # Feuille principale avec les données
            df_files = pd.DataFrame(identified_files)
            
            # Feuille des statistiques
            stats_data = {
                'Métrique': ['Total fichiers', 'Confiance moyenne'] + 
                           [f'Type {t}' for t in stats['by_type'].keys()] +
                           [f'Source {s}' for s in stats['by_source'].keys()],
                'Valeur': [stats['total'], f"{stats['avg_confidence']:.2f}"] +
                         list(stats['by_type'].values()) +
                         list(stats['by_source'].values())
            }
            df_stats = pd.DataFrame(stats_data)
            
            with pd.ExcelWriter(xlsx_file, engine='openpyxl') as writer:
                df_files.to_excel(writer, sheet_name='Fichiers_Identifiés', index=False)
                df_stats.to_excel(writer, sheet_name='Statistiques', index=False)
            
            generated_files.append(str(xlsx_file))
            
        except ImportError:
            logger.warning("pandas ou openpyxl non disponible - rapport Excel ignoré")
    
    logger.info(f"📄 Rapports générés dans {output_dir}:")
    for file_path in generated_files:
        logger.info(f"  • {Path(file_path).name}")
    
    return generated_files

def auto_import_files(identified_files: List[Dict], import_script_path: str = None) -> bool:
    """
    Lance automatiquement l'import des fichiers identifiés via import_complete.py
    
    Args:
        identified_files: Liste des fichiers identifiés
        import_script_path: Chemin vers le script d'import (auto-détecté si None)
        
    Returns:
        bool: True si l'import a réussi
    """
    if not identified_files:
        logger.warning("Aucun fichier à importer")
        return True
    
    # Auto-détection du script d'import - prioriser import_complete.py
    if import_script_path is None:
        possible_paths = [
            "scripts/import_complete.py",
            "import_complete.py",
            "../scripts/import_complete.py",
            "../../scripts/import_complete.py",
            # Fallback vers l'ancien script
            "import_dpgf_unified.py",
            "scripts/import_dpgf_unified.py",
            "../import_dpgf_unified.py",
            "../../import_dpgf_unified.py"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                import_script_path = path
                break
        
        if import_script_path is None:
            logger.error("❌ Script d'import non trouvé (import_complete.py ou import_dpgf_unified.py)")
            logger.info("💡 Spécifiez le chemin avec --import-script ou placez le script dans:")
            for path in possible_paths[:4]:  # Afficher seulement les chemins de import_complete.py
                logger.info(f"   • {path}")
            return False
    
    # Préparer la liste des fichiers à importer
    files_to_import = []
    
    for file_info in identified_files:
        if file_info.get('source') == 'sharepoint':
            # Pour les fichiers SharePoint, utiliser le chemin local s'il existe
            if 'local_path' in file_info:
                files_to_import.append(file_info['local_path'])
            else:
                logger.warning(f"Fichier SharePoint non téléchargé: {file_info['name']}")
        else:
            # Pour les fichiers locaux
            files_to_import.append(file_info['path'])
    
    if not files_to_import:
        logger.warning("Aucun fichier disponible pour l'import")
        return True
    
    logger.info(f"🔄 Lancement de l'import automatique pour {len(files_to_import)} fichiers")
    logger.info(f"Script utilisé: {import_script_path}")
    
    try:
        # Construire la commande d'import
        cmd = [
            sys.executable,  # Python executable
            import_script_path
        ]
        
        # Ajouter les fichiers en arguments
        cmd.extend(files_to_import)
        
        # Lancer l'import
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # Timeout de 30 minutes
        )
        
        if result.returncode == 0:
            logger.info("✅ Import automatique terminé avec succès")
            if result.stdout:
                logger.info("Sortie de l'import:")
                for line in result.stdout.split('\n')[-10:]:  # 10 dernières lignes
                    if line.strip():
                        logger.info(f"  {line}")
            return True
        else:
            logger.error(f"❌ Erreur lors de l'import automatique (code: {result.returncode})")
            if result.stderr:
                logger.error("Erreurs:")
                for line in result.stderr.split('\n')[-5:]:  # 5 dernières lignes d'erreur
                    if line.strip():
                        logger.error(f"  {line}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout lors de l'import automatique (> 30 minutes)")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur lors du lancement de l'import: {str(e)}")
        return False

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Identifier et analyser les fichiers DPGF/BPU/DQE depuis SharePoint ou un dossier local",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  # Test d'accès SharePoint
  python identify_relevant_files_sharepoint.py --source sharepoint --test-access
  
  # Scan rapide avec limite
  python identify_relevant_files_sharepoint.py --source sharepoint --mode quick --max-files 20
  
  # Scan approfondi avec téléchargement et import automatique
  python identify_relevant_files_sharepoint.py --source sharepoint --mode download --deep-scan --auto-import
  
  # Export en multiple formats
  python identify_relevant_files_sharepoint.py --source sharepoint --formats txt,csv,json
        """
    )
    
    # Arguments principaux
    parser.add_argument('--source', choices=['sharepoint', 'local'], default='sharepoint',
                      help='Source des fichiers (sharepoint ou local)')
    parser.add_argument('--folder', type=str, default="/Documents partages",
                      help='Chemin du dossier SharePoint ou local')
    parser.add_argument('--mode', choices=['quick', 'deep', 'download'], default='quick',
                      help='Mode d\'analyse: quick (rapide), deep (approfondi), download (télécharger)')
    
    # Options d'analyse
    parser.add_argument('--min-confidence', type=float, default=0.3,
                      help='Score de confiance minimum (0.0-1.0, défaut: 0.3)')
    parser.add_argument('--max-files', type=int,
                      help='Nombre maximum de fichiers à analyser (utile pour les tests)')
    parser.add_argument('--deep-scan', action='store_true',
                      help='Analyse approfondie du contenu (plus lent mais plus précis)')
    
    # Options de sortie
    parser.add_argument('--reports-dir', type=str, default='reports',
                      help='Répertoire pour les rapports (défaut: reports/)')
    parser.add_argument('--log-dir', type=str, default='logs',
                      help='Répertoire pour les logs (défaut: logs/)')
    parser.add_argument('--formats', type=str, default='txt,csv',
                      help='Formats de rapport séparés par virgules: txt,csv,json,xlsx (défaut: txt,csv)')
    parser.add_argument('--output-basename', type=str,
                      help='Nom de base pour les fichiers de sortie (auto-généré si omis)')
    
    # Options de téléchargement
    parser.add_argument('--download-folder', type=str, default='downloaded_dpgf',
                      help='Dossier de téléchargement pour les fichiers')
    
    # Options d'import automatique
    parser.add_argument('--auto-import', action='store_true',
                      help='Lancer automatiquement l\'import des fichiers identifiés')
    parser.add_argument('--import-script', type=str,
                      help='Chemin vers le script d\'import (auto-détecté si omis)')
    
    # Tests
    parser.add_argument('--test-access', action='store_true',
                      help='Tester l\'accès SharePoint en listant les 10 premiers fichiers du dossier')
    parser.add_argument('--summary', action='store_true',
                      help='Afficher un résumé des dossiers avant l\'analyse complète')
    
    args = parser.parse_args()
    
    # Configuration du logging
    global logger
    logger = setup_logging(args.log_dir)
    
    # Analyser les formats de sortie
    output_formats = [fmt.strip() for fmt in args.formats.split(',')]
    
    logger.info(">> Demarrage de l'identification des fichiers DPGF/BPU/DQE")
    logger.info(f"Source: {args.source}")
    logger.info(f"Dossier: {args.folder}")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Confiance min: {args.min_confidence}")
    if args.max_files:
        logger.info(f"Limite fichiers: {args.max_files}")
    
    try:
        if args.source == 'sharepoint':
            sharepoint_client = SharePointClient()
            
            # Test d'accès rapide
            if args.test_access:
                print(f"Test du dossier SharePoint: {args.folder}")
                print("-" * 40)
                try:
                    first_files = sharepoint_client.list_first_10_files(args.folder)
                    if first_files:
                        print(f">> Acces reussi ! Trouve {len(first_files)} elements :")
                        print()
                        
                        # Séparer les dossiers des fichiers
                        folders = [f for f in first_files if f.get('type') == 'folder']
                        files = [f for f in first_files if f.get('type') == 'file']
                        
                        # Afficher les dossiers d'abord
                        if folders:
                            print("Dossiers :")
                            for i, folder_info in enumerate(folders, 1):
                                modified_date = folder_info.get('modified', '')[:10] if folder_info.get('modified') else 'N/A'
                                print(f"  {i:2d}. [DIR] {folder_info['name']} (modifie: {modified_date})")
                            print()
                        
                        # Afficher les fichiers
                        if files:
                            print("Fichiers :")
                            excel_count = 0
                            for i, file_info in enumerate(files, 1):
                                size_str = f"{file_info['size']/1024/1024:.1f} MB" if file_info['size'] > 0 else "0 KB"
                                modified_date = file_info.get('modified', '')[:10] if file_info.get('modified') else 'N/A'
                                
                                # Détecter les fichiers Excel
                                is_excel = any(file_info['name'].lower().endswith(ext) for ext in EXCEL_EXTENSIONS)
                                icon = "[XLS]" if is_excel else "[FILE]"
                                if is_excel:
                                    excel_count += 1
                                
                                print(f"  {i:2d}. {icon} {file_info['name']} ({size_str}, {modified_date})")
                            
                            if excel_count > 0:
                                print(f"\n!! {excel_count} fichier(s) Excel detecte(s) - potentiellement analysables")
                        
                        print("\nPour analyser ces fichiers, utilisez :")
                        print(f"  python {Path(__file__).name} --source sharepoint --folder '{args.folder}' --mode quick")
                        
                    else:
                        print("XX Aucun element trouve ou acces impossible")
                        print("!! Verifiez le chemin du dossier ou vos permissions")
                    return
                except Exception as e:
                    print(f"XX Erreur lors du test d'acces: {str(e)}")
                    return
            
            # Résumé des dossiers (pour dossier racine uniquement)
            if args.summary and args.folder == "/":
                print(f"📊 Résumé des dossiers SharePoint: {args.folder}")
                print("-" * 50)
                
                summary = sharepoint_client.get_folders_summary(args.folder)
                
                print(f"📁 Total des dossiers: {summary['total_folders']}")
                print(f"📈 Estimation des fichiers: ~{summary['estimated_files']:,}")
                print()
                
                if summary['folders']:
                    print("🔍 Aperçu des premiers dossiers:")
                    for i, folder_info in enumerate(summary['folders'], 1):
                        excel_info = f"({folder_info['excel_files']} Excel)" if folder_info['excel_files'] > 0 else "(pas d'Excel)"
                        print(f"  {i}. 📁 {folder_info['name']}")
                        print(f"     └─ {folder_info['sample_files']} fichiers échantillonnés {excel_info}")
                
                print(f"\n💡 Pour analyser tous les dossiers, utilisez :")
                print(f"  python {Path(__file__).name} --source sharepoint --folder '/' --mode quick")
                print(f"\n⚠️  ATTENTION: Avec {summary['total_folders']} dossiers, l'analyse complète peut prendre du temps.")
                print(f"  Utilisez --max-files pour limiter ou --summary pour estimer.")
                return
            
            # Initialiser l'identificateur avec les nouvelles options
            identifier = FileIdentifier(
                min_confidence=args.min_confidence,
                max_files=args.max_files
            )
            
            # Scan des fichiers
            print(f">> Scan des fichiers depuis SharePoint: {args.folder}")
            
            if args.mode == 'download':
                # Mode téléchargement
                identified_files = identifier.identify_sharepoint_files(
                    f"https://sef92230.sharepoint.com/sites/etudes{args.folder}",
                    deep_scan=args.deep_scan or args.mode == 'deep',
                    download_dir=args.download_folder
                )
                
                if identified_files:
                    # Télécharger les fichiers identifiés
                    downloaded_files = identifier.download_identified_files(
                        identified_files, args.download_folder
                    )
                    
                    # Utiliser les fichiers téléchargés pour le rapport
                    final_files = downloaded_files
                    
                    # Import automatique si demandé
                    if args.auto_import:
                        auto_import_files(downloaded_files, args.import_script)
                else:
                    final_files = []
            else:
                # Mode analyse seulement
                identified_files = identifier.identify_sharepoint_files(
                    f"https://sef92230.sharepoint.com/sites/etudes{args.folder}",
                    deep_scan=args.deep_scan or args.mode == 'deep'
                )
                final_files = identified_files
        
        else:  # source == 'local'
            identifier = FileIdentifier(
                min_confidence=args.min_confidence,
                max_files=args.max_files
            )
            
            print(f">> Scan des fichiers locaux: {args.folder}")
            
            identified_files = identifier.identify_local_files(
                args.folder,
                deep_scan=args.deep_scan or args.mode == 'deep'
            )
            final_files = identified_files
            
            # Import automatique si demandé
            if args.auto_import:
                auto_import_files(identified_files, args.import_script)
        
        # Générer les rapports
        if final_files:
            report_files = generate_report(
                final_files,
                output_dir=args.reports_dir,
                output_basename=args.output_basename,
                formats=output_formats
            )
            
            print(f"\n>> Analyse terminee!")
            print(f">> {len(final_files)} fichiers identifies")
            print(f">> Rapports generes: {len(report_files)}")
            
            # Afficher les chemins des rapports
            for report_file in report_files:
                print(f"  • {report_file}")
                
            if args.auto_import and final_files:
                print(f">> Import automatique {'termine' if args.mode == 'download' else 'lance'}")
        else:
            print("XX Aucun fichier identifie correspondant aux criteres")
            
    except KeyboardInterrupt:
        print("\n>> Analyse interrompue par l'utilisateur")
        return 1
    except Exception as e:
        if "XX Erreur" in str(e):  # C'est déjà une erreur formatée
            print(f"\n{str(e)}")
        else:
            logger.error(f"Erreur inattendue: {str(e)}")
            print(f"\nXX Erreur inattendue: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
