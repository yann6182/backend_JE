#!/usr/bin/env python3
"""
Extension du script d'identification SharePoint pour supporter le traitement par lots
Permet de télécharger uniquement un sous-ensemble spécifique de fichiers
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict
import tempfile
import os

# Ajouter le répertoire parent au PATH pour les imports
sys.path.append(str(Path(__file__).parent))

try:
    from identify_relevant_files_sharepoint import SharePointClient, FileIdentifier
except ImportError:
    print("❌ Erreur d'import du module SharePoint")
    sys.exit(1)

def download_specific_files(sharepoint_url: str, file_list: List[Dict], output_dir: str) -> List[Dict]:
    """
    Télécharge une liste spécifique de fichiers depuis SharePoint
    
    Args:
        sharepoint_url: URL SharePoint
        file_list: Liste des fichiers à télécharger avec leurs métadonnées
        output_dir: Répertoire de destination
        
    Returns:
        List[Dict]: Liste des fichiers téléchargés avec succès
    """
    client = SharePointClient()
    
    # Parse l'URL SharePoint pour extraire le chemin du dossier
    try:
        site_url, folder_path = client.parse_sharepoint_url(sharepoint_url)
        print(f"📁 Dossier SharePoint: {folder_path}")
    except Exception as e:
        print(f"Erreur lors du parsing de l'URL: {str(e)}")
        folder_path = "/"
    
    downloaded_files = []
    os.makedirs(output_dir, exist_ok=True)
    
    for file_info in file_list:
        try:
            file_name = file_info.get('name', 'unknown.xlsx')
            file_id = file_info.get('sharepoint_id')
            
            if not file_id:
                print(f"⚠️ ID SharePoint manquant pour {file_name}")
                continue
            
            # Créer le chemin de destination
            local_path = os.path.join(output_dir, file_name)
            
            # Éviter les doublons
            counter = 1
            base_name, ext = os.path.splitext(local_path)
            while os.path.exists(local_path):
                local_path = f"{base_name}_{counter}{ext}"
                counter += 1
            
            # Télécharger le fichier
            if client.download_file(file_id, local_path):
                downloaded_info = file_info.copy()
                downloaded_info['local_path'] = local_path
                downloaded_info['downloaded'] = True
                downloaded_files.append(downloaded_info)
                print(f"✅ Téléchargé: {file_name}")
            else:
                print(f"❌ Échec téléchargement: {file_name}")
                
        except Exception as e:
            print(f"❌ Erreur téléchargement {file_info.get('name', 'unknown')}: {str(e)}")
    
    return downloaded_files

def create_batch_from_identified_files(identified_files: List[Dict], batch_size: int, batch_num: int) -> List[Dict]:
    """
    Crée un lot de fichiers à partir d'une liste de fichiers identifiés
    
    Args:
        identified_files: Liste complète des fichiers identifiés
        batch_size: Taille du lot
        batch_num: Numéro du lot (0-based)
        
    Returns:
        List[Dict]: Fichiers du lot demandé
    """
    start_idx = batch_num * batch_size
    end_idx = min(start_idx + batch_size, len(identified_files))
    
    if start_idx >= len(identified_files):
        return []
    
    return identified_files[start_idx:end_idx]

def main():
    parser = argparse.ArgumentParser(description="Téléchargement par lots depuis SharePoint")
    parser.add_argument('--sharepoint-url', required=True, help='URL SharePoint')
    parser.add_argument('--output-dir', required=True, help='Répertoire de destination')
    parser.add_argument('--batch-size', type=int, default=10, help='Taille des lots')
    parser.add_argument('--batch-num', type=int, default=0, help='Numéro du lot à télécharger')
    parser.add_argument('--file-list', help='Fichier JSON avec la liste des fichiers identifiés')
    parser.add_argument('--min-confidence', type=float, default=0.3, help='Confiance minimum')
    parser.add_argument('--identify-first', action='store_true', help='Identifier d\'abord les fichiers')
    
    args = parser.parse_args()
    
    try:
        identified_files = []
        
        if args.identify_first:
            # Identifier d'abord les fichiers
            print("🔍 Identification des fichiers SharePoint...")
            identifier = FileIdentifier()
            identified_files = identifier.identify_sharepoint_files(
                args.sharepoint_url, 
                deep_scan=False
            )
            
            # Sauvegarder la liste pour référence future
            list_file = Path(args.output_dir) / "identified_files.json"
            with open(list_file, 'w', encoding='utf-8') as f:
                json.dump(identified_files, f, indent=2, ensure_ascii=False)
            print(f"📄 Liste sauvegardée: {list_file}")
            
        elif args.file_list and Path(args.file_list).exists():
            # Charger depuis un fichier existant
            print(f"📄 Chargement de la liste: {args.file_list}")
            with open(args.file_list, 'r', encoding='utf-8') as f:
                identified_files = json.load(f)
        else:
            print("❌ Aucune liste de fichiers fournie. Utilisez --identify-first ou --file-list")
            sys.exit(1)
        
        # Filtrer par confiance
        filtered_files = [
            f for f in identified_files 
            if f.get('confidence', 0) >= args.min_confidence
        ]
        
        print(f"📊 {len(filtered_files)} fichiers avec confiance >= {args.min_confidence}")
        
        # Créer le lot demandé
        batch_files = create_batch_from_identified_files(
            filtered_files, 
            args.batch_size, 
            args.batch_num
        )
        
        if not batch_files:
            print(f"⚠️ Lot {args.batch_num} vide ou hors limites")
            sys.exit(0)
        
        print(f"📦 Lot {args.batch_num}: {len(batch_files)} fichiers à télécharger")
        
        # Télécharger le lot
        downloaded = download_specific_files(
            args.sharepoint_url,
            batch_files,
            args.output_dir
        )
        
        print(f"✅ Téléchargement terminé: {len(downloaded)} fichiers réussis")
        
        # Sauvegarder les informations du lot téléchargé
        batch_info_file = Path(args.output_dir) / f"batch_{args.batch_num}_info.json"
        with open(batch_info_file, 'w', encoding='utf-8') as f:
            json.dump({
                'batch_num': args.batch_num,
                'batch_size': args.batch_size,
                'files_downloaded': len(downloaded),
                'files_info': downloaded
            }, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Info du lot sauvegardée: {batch_info_file}")
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
