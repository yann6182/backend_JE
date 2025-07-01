

import argparse
import sys
import re
import os
from pathlib import Path
from typing import Optional, List, Tuple
import pandas as pd
import requests
from tqdm import tqdm


def find_lot_headers(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """
    Recherche dans les 15 premières lignes les intitulés de lot au format
    « LOT <numéro> – <libellé> » (maj/min indifférent).
    
    Returns:
        List of tuples (numero_lot, nom_lot)
    """
    lots = []
    pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
    
    # Parcourir les 15 premières lignes
    for i in range(min(15, len(df))):
        for col in df.columns:
            cell_value = df.iloc[i, df.columns.get_loc(col)]
            if pd.notna(cell_value):
                cell_str = str(cell_value).strip()
                match = pattern.search(cell_str)
                if match:
                    numero_lot = match.group(1).strip()
                    nom_lot = match.group(2).strip()
                    lots.append((numero_lot, nom_lot))
    
    return lots


def detect_project_name(df: pd.DataFrame, filename: str) -> str:
    """
    Extrait le nom de projet : première cellule non vide ou nom du fichier.
    
    Returns:
        Project name as string
    """
    # Chercher la première cellule non vide
    for i in range(min(5, len(df))):  # Limiter aux 5 premières lignes
        for col in df.columns:
            cell_value = df.iloc[i, df.columns.get_loc(col)]
            if pd.notna(cell_value):
                cell_str = str(cell_value).strip()
                if cell_str and len(cell_str) > 3:  # Éviter les cellules trop courtes
                    return cell_str
    
    # Fallback : nom du fichier sans extension
    return Path(filename).stem


def create_client_if_needed(base_url: str, client_id: Optional[int] = None, client_name: Optional[str] = None) -> int:
    """
    Crée ou récupère un client via l'API.
    
    Returns:
        Client ID
    """
    if client_id:
        # Vérifier que le client existe
        response = requests.get(f"{base_url}/clients/{client_id}")
        response.raise_for_status()
        return client_id
    
    elif client_name:
        # Essayer de trouver le client par nom
        response = requests.get(f"{base_url}/clients")
        response.raise_for_status()
        clients = response.json()
        
        for client in clients:
            if client.get('nom_client') == client_name:
                return client['id_client']
        
        # Client non trouvé, le créer
        client_data = {"nom_client": client_name}
        response = requests.post(f"{base_url}/clients", json=client_data)
        response.raise_for_status()
        return response.json()['id_client']
    
    else:
        raise ValueError("Client ID ou Client Name requis")


def process_excel_file(filepath: str, base_url: str, client_id: int) -> None:
    """
    Traite un fichier Excel : extrait projet et lots, puis appelle l'API.
    """
    try:
        # Lire le fichier Excel
        df = pd.read_excel(filepath, engine='openpyxl')
        
        # Détecter le nom du projet
        project_name = detect_project_name(df, filepath)
        
        # Trouver les lots
        lots = find_lot_headers(df)
        
        if not lots:
            print(f"⚠️  Aucun lot trouvé dans {filepath}", file=sys.stderr)
            return
          # Créer le DPGF
        from datetime import datetime
        dpgf_data = {
            "id_client": client_id,
            "nom_projet": project_name,
            "date_dpgf": datetime.now().strftime("%Y-%m-%d"),  # Date actuelle
            "statut_offre": "en_cours",  # Utiliser la valeur enum correcte
            "fichier_source": os.path.basename(filepath)
        }
        
        response = requests.post(f"{base_url}/dpgf", json=dpgf_data)
        response.raise_for_status()
        dpgf_id = response.json()['id_dpgf']
        
        # Créer chaque lot
        for numero_lot, nom_lot in lots:
            lot_data = {
                "id_dpgf": dpgf_id,
                "numero_lot": numero_lot,
                "nom_lot": nom_lot
            }
            
            response = requests.post(f"{base_url}/lots", json=lot_data)
            response.raise_for_status()
        
        print(f"✅ {filepath} - Projet: {project_name} - {len(lots)} lot(s) créé(s)")
        
    except Exception as e:
        print(f"❌ Erreur lors du traitement de {filepath}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Import DPGF from Excel files")
    parser.add_argument("--dir", required=True, help="Dossier à parcourir")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de base de l'API")
    
    # Group mutuellement exclusif pour client
    client_group = parser.add_mutually_exclusive_group(required=True)
    client_group.add_argument("--client-id", type=int, help="ID du client existant")
    client_group.add_argument("--client-name", help="Nom du client à créer/récupérer")
    
    args = parser.parse_args()
    
    # Vérifier que le dossier existe
    if not os.path.isdir(args.dir):
        print(f"❌ Le dossier {args.dir} n'existe pas", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Créer ou récupérer le client
        client_id = create_client_if_needed(args.base_url, args.client_id, args.client_name)
        print(f"📋 Client ID: {client_id}")
        
        # Trouver tous les fichiers Excel
        excel_files = []
        for root, dirs, files in os.walk(args.dir):
            for file in files:
                if file.lower().endswith('.xlsx'):
                    excel_files.append(os.path.join(root, file))
        
        if not excel_files:
            print(f"⚠️  Aucun fichier Excel trouvé dans {args.dir}")
            return
        
        print(f"📁 {len(excel_files)} fichier(s) Excel trouvé(s)")
        
        # Traiter chaque fichier avec barre de progression
        for filepath in tqdm(excel_files, desc="Traitement des fichiers"):
            process_excel_file(filepath, args.base_url, client_id)
        
        print("🎉 Import terminé avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()