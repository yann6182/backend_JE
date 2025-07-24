

"""
Script pour identifier et filtrer automatiquement les fichiers pertinents
de type DPGF (Décomposition du Prix Global et Forfaitaire), 
BPU (Bordereau des Prix Unitaires) et DQE (Détail Quantitatif Estimatif)
parmi une grande quantité de données.

Ce script parcourt récursivement un répertoire et identifie les fichiers Excel 
qui correspondent aux critères de DPGF, BPU ou DQE en se basant sur :
- Le nom du fichier
- Les mots-clés dans le contenu du fichier
- La structure des données

Usage:
    python identify_relevant_files.py --source-dir <dossier_source> --output-dir <dossier_destination> [options]

Options:
    --source-dir SOURCE_DIR     Chemin vers le répertoire source contenant les fichiers à analyser
    --output-dir OUTPUT_DIR     Chemin vers le répertoire où copier les fichiers pertinents
    --copy-files                Copier les fichiers identifiés vers output-dir (par défaut: ne liste que les fichiers)
    --deep-scan                 Effectue une analyse approfondie du contenu des fichiers (plus lent mais plus précis)
    --exclude-dirs DIRS         Liste de dossiers à exclure, séparés par des virgules
    --log-file LOG_FILE         Fichier pour enregistrer les résultats (par défaut: identification_results.log)
"""

import os
import sys
import re
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import concurrent.futures
from collections import Counter

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
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

def detect_document_type_from_filename(filepath: str) -> Dict[str, float]:
    """
    Détecte le type probable du document basé sur son nom de fichier.
    
    Returns:
        Dict[str, float]: Dictionnaire des types de documents avec un score de confiance
    """
    filename = os.path.basename(filepath).lower()
    scores = {'DPGF': 0.0, 'BPU': 0.0, 'DQE': 0.0}
    
    # Vérification directe des mots-clés dans le nom de fichier
    for doc_type, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in filename:
                scores[doc_type] += 0.5
                break
    
    # Vérification des patterns dans le nom de fichier
    for doc_type, patterns in FILE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename, re.IGNORECASE):
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
        
        # Recherche de mots-clés dans le contenu
        if len(df) > 0:
            # Convertir le DataFrame en chaîne pour rechercher des mots-clés
            content_sample = ""
            for i in range(min(10, len(df))):  # Analyser les 10 premières lignes
                for col in df.columns:
                    val = df.iloc[i].get(col, "")
                    if isinstance(val, str):
                        content_sample += " " + val.lower()
            
            # Vérifier la présence de mots-clés
            for doc_type, keywords in KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content_sample:
                        scores[doc_type] += 0.3
                        break
        
        # Analyse approfondie des données pour une meilleure précision
        if deep_scan:
            # Vérifier si le document contient des calculs typiques DPGF/DQE (quantité * prix = montant)
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) >= 3:  # Au moins 3 colonnes numériques
                # DPGF et DQE ont typiquement des calculs de montants
                if any("montant" in normalize_string(str(col)) for col in df.columns) or \
                   any("total" in normalize_string(str(col)) for col in df.columns):
                    scores['DPGF'] += 0.2
                    scores['DQE'] += 0.2
            
            # BPU contient généralement moins de colonnes de calcul
            if len(numeric_columns) <= 2 and any("prix" in normalize_string(str(col)) for col in df.columns):
                scores['BPU'] += 0.2
    
    except Exception as e:
        logger.warning(f"Erreur lors de l'analyse de {filepath}: {str(e)}")
    
    return scores

def process_file(filepath: str, deep_scan: bool = False) -> Tuple[str, str, float]:
    """
    Traite un fichier pour déterminer son type (DPGF, BPU, DQE) et son score de confiance.
    
    Returns:
        Tuple[str, str, float]: (chemin_fichier, type_document, score_confiance)
    """
    try:
        # Vérifier si c'est un fichier Excel
        if not filepath.lower().endswith(tuple(EXCEL_EXTENSIONS)):
            return filepath, "UNKNOWN", 0.0
        
        # Analyse rapide basée sur le nom de fichier
        filename_scores = detect_document_type_from_filename(filepath)
        
        # Analyse du contenu
        content_scores = scan_excel_content(filepath, deep_scan)
        
        # Combiner les scores (60% pour le contenu, 40% pour le nom de fichier)
        combined_scores = {}
        for doc_type in filename_scores.keys():
            combined_scores[doc_type] = content_scores.get(doc_type, 0) * 0.6 + filename_scores.get(doc_type, 0) * 0.4
        
        # Déterminer le type le plus probable
        best_type = max(combined_scores.items(), key=lambda x: x[1])
        doc_type, confidence = best_type
        
        # Ne retenir que si le score dépasse un seuil minimal
        if confidence >= 0.3:
            return filepath, doc_type, confidence
        else:
            return filepath, "UNKNOWN", confidence
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement de {filepath}: {str(e)}")
        return filepath, "ERROR", 0.0

def get_lot_info(filepath: str) -> Dict:
    """
    Extraire les informations de lot du fichier identifié.
    
    Returns:
        Dict: Informations sur le lot (numéro, nom, etc.)
    """
    lot_info = {"numero_lot": None, "nom_lot": None}
    
    try:
        df = pd.read_excel(filepath, nrows=15, engine='openpyxl')
        
        # Rechercher le motif "LOT <numéro> - <libellé>"
        pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
        
        for i in range(min(15, len(df))):
            for col in df.columns:
                cell_value = df.iloc[i, df.columns.get_loc(col)]
                if pd.notna(cell_value):
                    cell_str = str(cell_value).strip()
                    match = pattern.search(cell_str)
                    if match:
                        lot_info["numero_lot"] = match.group(1).strip()
                        lot_info["nom_lot"] = match.group(2).strip()
                        return lot_info
                        
    except Exception as e:
        logger.warning(f"Erreur lors de l'extraction des infos de lot de {filepath}: {str(e)}")
    
    # Si non trouvé, essayer d'extraire du nom de fichier
    filename = os.path.basename(filepath)
    match = re.search(r'lot\s*(\d+)[^a-zA-Z0-9]*(.*?)\.', filename, re.IGNORECASE)
    if match:
        lot_info["numero_lot"] = match.group(1)
        if match.group(2):
            lot_info["nom_lot"] = match.group(2).strip()
    
    return lot_info

def create_output_dirs(output_dir: str) -> None:
    """Crée les répertoires de sortie nécessaires."""
    os.makedirs(output_dir, exist_ok=True)
    for doc_type in ['DPGF', 'BPU', 'DQE', 'UNKNOWN']:
        os.makedirs(os.path.join(output_dir, doc_type), exist_ok=True)

def main():
    parser = argparse.ArgumentParser(description="Identification automatique de fichiers DPGF, BPU et DQE")
    parser.add_argument("--source-dir", required=True, help="Répertoire source contenant les fichiers à analyser")
    parser.add_argument("--output-dir", required=True, help="Répertoire où copier/déplacer les fichiers pertinents")
    parser.add_argument("--copy-files", action="store_true", help="Copier les fichiers identifiés vers output-dir")
    parser.add_argument("--deep-scan", action="store_true", help="Effectuer une analyse approfondie (plus lent mais plus précis)")
    parser.add_argument("--exclude-dirs", help="Liste de dossiers à exclure, séparés par des virgules")
    parser.add_argument("--log-file", default="identification_results.log", help="Fichier pour enregistrer les résultats")
    
    args = parser.parse_args()
    
    # Configurer le logging vers un fichier
    file_handler = logging.FileHandler(args.log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Vérifier que le répertoire source existe
    if not os.path.isdir(args.source_dir):
        logger.error(f"Le répertoire source {args.source_dir} n'existe pas")
        sys.exit(1)
    
    # Préparation des dossiers exclus
    excluded_dirs = set()
    if args.exclude_dirs:
        excluded_dirs = {os.path.normpath(d.strip()) for d in args.exclude_dirs.split(',')}
    
    # Créer les répertoires de sortie
    if args.copy_files:
        create_output_dirs(args.output_dir)
    
    # Collecter tous les fichiers Excel récursivement
    excel_files = []
    start_time = time.time()
    logger.info(f"Début de l'analyse du répertoire {args.source_dir}")
    
    for root, dirs, files in os.walk(args.source_dir):
        # Ignorer les répertoires exclus
        if any(os.path.normpath(os.path.join(args.source_dir, excluded)) in os.path.normpath(root) for excluded in excluded_dirs):
            continue
            
        for file in files:
            if file.lower().endswith(tuple(EXCEL_EXTENSIONS)):
                excel_files.append(os.path.join(root, file))
    
    logger.info(f"Trouvé {len(excel_files)} fichiers Excel à analyser")
    
    # Traiter les fichiers en parallèle pour accélérer le processus
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, os.cpu_count() or 1)) as executor:
        # Soumettre les tâches
        future_to_file = {executor.submit(process_file, filepath, args.deep_scan): filepath for filepath in excel_files}
        
        # Traiter les résultats avec une barre de progression
        for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(excel_files), desc="Analyse des fichiers"):
            filepath = future_to_file[future]
            try:
                file_path, doc_type, confidence = future.result()
                results.append((file_path, doc_type, confidence))
            except Exception as e:
                logger.error(f"Erreur lors du traitement de {filepath}: {str(e)}")
    
    # Compiler les statistiques
    stats = Counter([doc_type for _, doc_type, _ in results])
    
    # Filtrer les résultats pertinents (DPGF, BPU, DQE)
    relevant_files = [(filepath, doc_type, confidence) 
                     for filepath, doc_type, confidence in results 
                     if doc_type in ['DPGF', 'BPU', 'DQE']]
    
    # Trier par type et confiance
    relevant_files.sort(key=lambda x: (x[1], -x[2]))
    
    # Enregistrer le rapport détaillé
    with open(os.path.join(args.output_dir, 'rapport_identification.csv'), 'w', encoding='utf-8') as f:
        f.write("Chemin;Type;Confiance;NumeroLot;NomLot\n")
        for filepath, doc_type, confidence in relevant_files:
            if doc_type != 'UNKNOWN':
                lot_info = get_lot_info(filepath)
                f.write(f"{filepath};{doc_type};{confidence:.2f};{lot_info.get('numero_lot', '')};{lot_info.get('nom_lot', '')}\n")
    
    # Copier les fichiers si demandé
    if args.copy_files:
        logger.info("Copie des fichiers pertinents...")
        for filepath, doc_type, _ in tqdm(relevant_files, desc="Copie des fichiers"):
            if doc_type in ['DPGF', 'BPU', 'DQE']:
                dest_dir = os.path.join(args.output_dir, doc_type)
                dest_path = os.path.join(dest_dir, os.path.basename(filepath))
                
                # Ajouter un suffixe si le fichier existe déjà
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(dest_path)
                    dest_path = f"{base}_{int(time.time())}{ext}"
                
                try:
                    shutil.copy2(filepath, dest_path)
                except Exception as e:
                    logger.error(f"Erreur lors de la copie de {filepath}: {str(e)}")
    
    # Afficher le rapport final
    elapsed_time = time.time() - start_time
    logger.info(f"Analyse terminée en {elapsed_time:.2f} secondes")
    logger.info(f"Résultats:")
    logger.info(f"  - DPGF: {stats['DPGF']} fichiers")
    logger.info(f"  - BPU: {stats['BPU']} fichiers")
    logger.info(f"  - DQE: {stats['DQE']} fichiers")
    logger.info(f"  - Non identifiés/non pertinents: {stats['UNKNOWN']} fichiers")
    logger.info(f"  - Erreurs: {stats.get('ERROR', 0)} fichiers")
    logger.info(f"Rapport détaillé enregistré dans {os.path.join(args.output_dir, 'rapport_identification.csv')}")

if __name__ == "__main__":
    main()
