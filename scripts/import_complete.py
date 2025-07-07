"""
Script d'import DPGF complet amélioré:
- Détection automatique du client
- Import de lots
- Import des sections et sous-sections
- Import des éléments d'ouvrage
- Détection dynamique des colonnes de prix et quantités
- Gestion intelligente des erreurs et des doublons
- Classification avancée avec l'API Google Gemini (optionnelle)
- Support des fichiers SharePoint avec détection spécialisée
"""

import argparse
import sys
import json
import os
import re
import hashlib
import pickle
import csv
from typing import Optional, Dict, List, Tuple, Generator
from datetime import date
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm

# Import du module de logging amélioré
try:
    from scripts.enhanced_logging import get_import_logger, ImportLogger
except ImportError:
    # Essayer import direct si dans le même répertoire
    try:
        from enhanced_logging import get_import_logger, ImportLogger
    except ImportError:
        # Fallback vers logging standard
        import logging
        
        class ImportLogger:
            def __init__(self, file_path):
                self.logger = logging.getLogger(f"import_{Path(file_path).stem}")
                self.logger.setLevel(logging.INFO)
                if not self.logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    self.logger.addHandler(handler)
            
            def info(self, msg): self.logger.info(msg)
            def warning(self, msg): self.logger.warning(msg)
            def error(self, msg): self.logger.error(msg)
            def debug(self, msg): self.logger.debug(msg)
            def log_file_start(self, *args): self.info("Import démarré")
            def log_file_success(self, *args): self.info("Import terminé avec succès")
            def log_file_error(self, *args, **kwargs): self.error(f"Import échoué: {kwargs}")
            def log_lot_detected(self, *args): self.info("Lot détecté")
            def log_section_detected(self, *args): self.info("Section détectée")
            def log_element_detected(self, *args): self.info("Élément détecté")
            def log_element_without_section(self, *args): self.warning("Élément sans section")
            def close(self): pass
        
        def get_import_logger(file_path):
            return ImportLogger(file_path)

# Import du module d'aide pour les fichiers SharePoint
try:
    from scripts.sharepoint_import_helper import SharePointExcelHelper, is_sharepoint_file
    SHAREPOINT_HELPER_AVAILABLE = True
except ImportError:
    SHAREPOINT_HELPER_AVAILABLE = False
    print("⚠️ Module sharepoint_import_helper non disponible. Le support optimisé pour SharePoint ne sera pas utilisé.")

# Import conditionnel de l'API Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Module google.generativeai non disponible. L'analyse avancée par IA ne sera pas utilisée.")

# Configuration de l'encodage pour éviter les erreurs avec les caractères spéciaux
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


class ImportStats:
    """Statistiques d'import"""
    def __init__(self):
        self.total_rows = 0
        self.sections_created = 0
        self.elements_created = 0
        self.sections_reused = 0
        self.lots_created = 0
        self.lots_reused = 0
        self.errors = 0
        self.gemini_calls = 0
        self.cache_hits = 0
        self.gemini_fallback_used = False  # Nouveau flag pour le fallback
        self.gemini_failure_reason = None  # Raison de l'échec de Gemini


class ColumnMapping:
    """Gestionnaire de mapping des colonnes avec persistance"""
    
    def __init__(self, mappings_file: str = "mappings.pkl"):
        self.mappings_file = mappings_file
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """Charge les mappings sauvegardés"""
        if os.path.exists(self.mappings_file):
            try:
                with open(self.mappings_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️ Erreur chargement mappings: {e}")
        return {}
    
    def _save_mappings(self):
        """Sauvegarde les mappings sur disque"""
        try:
            with open(self.mappings_file, 'wb') as f:
                pickle.dump(self.mappings, f)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde mappings: {e}")
    
    def _get_file_signature(self, headers: List[str], filename: str = None) -> str:
        """Génère une signature unique pour un type de fichier"""
        # Utiliser les headers pour créer une signature
        headers_str = '|'.join([str(h).strip().lower() for h in headers if h])
        signature = hashlib.md5(headers_str.encode()).hexdigest()[:8]
        
        # Ajouter des infos du nom de fichier si disponible
        if filename:
            file_pattern = re.sub(r'\d+', 'X', filename.lower())  # Remplacer chiffres par X
            return f"{signature}_{file_pattern}"
        
        return signature
    
    def get_mapping(self, headers: List[str], filename: str = None) -> Optional[Dict[str, int]]:
        """Récupère un mapping existant"""
        signature = self._get_file_signature(headers, filename)
        return self.mappings.get(signature)
    
    def save_mapping(self, headers: List[str], mapping: Dict[str, int], filename: str = None):
        """Sauvegarde un nouveau mapping"""
        signature = self._get_file_signature(headers, filename)
        self.mappings[signature] = mapping
        self._save_mappings()
        print(f"✅ Mapping sauvegardé pour le type de fichier: {signature}")
    
    def interactive_mapping(self, headers: List[str]) -> Dict[str, Optional[int]]:
        """Interface interactive pour créer un mapping manuel"""
        print("\n" + "="*60)
        print("🔧 CONFIGURATION MANUELLE DU MAPPING DES COLONNES")
        print("="*60)
        print("En-têtes détectés dans le fichier:")
        for i, header in enumerate(headers):
            print(f"  {i}: {header}")
        
        print("\nVeuillez indiquer l'indice de colonne pour chaque type de donnée:")
        print("(Tapez 'skip' ou laissez vide si la colonne n'existe pas)")
        
        mapping = {}
        column_types = [
            ('designation', 'Désignation/Description'),
            ('unite', 'Unité'),
            ('quantite', 'Quantité'),
            ('prix_unitaire', 'Prix unitaire'),
            ('prix_total', 'Prix total')
        ]
        
        for col_key, col_description in column_types:
            while True:
                try:
                    response = input(f"\n{col_description}: ").strip()
                    if response.lower() in ['skip', '']:
                        mapping[col_key] = None
                        break
                    
                    col_index = int(response)
                    if 0 <= col_index < len(headers):
                        mapping[col_key] = col_index
                        print(f"✓ {col_description} -> Colonne {col_index}: {headers[col_index]}")
                        break
                    else:
                        print(f"❌ Indice invalide. Doit être entre 0 et {len(headers)-1}")
                        
                except ValueError:
                    print("❌ Veuillez entrer un nombre ou 'skip'")
        
        print("\n" + "="*60)
        print("Mapping configuré:")
        for col_key, col_index in mapping.items():
            if col_index is not None:
                print(f"  {col_key}: Colonne {col_index} ({headers[col_index]})")
            else:
                print(f"  {col_key}: Non mappé")
        print("="*60)
        
        # Demander confirmation
        while True:
            confirm = input("\nConfirmer ce mapping? (o/n): ")

            if confirm.lower() in ['o', 'oui', 'y', 'yes']:
                return mapping
            elif confirm.lower() in ['n', 'non', 'no']:
                print("Mapping annulé, recommencer...")
                return self.interactive_mapping(headers)
            else:
                print("Répondez par 'o' ou 'n'")


class ErrorReporter:
    """Gestionnaire de rapport d'erreurs CSV"""
    
    def __init__(self, error_file: str = "import_errors.csv"):
        self.error_file = error_file
        self.errors = []
        self._init_csv()
    
    def _init_csv(self):
        """Initialise le fichier CSV avec les en-têtes"""
        if not os.path.exists(self.error_file):
            with open(self.error_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'filename', 'line_number', 'error_type', 'error_message', 'raw_data'])
    
    def add_error(self, filename: str, line_number: int, error_type: str, error_message: str, raw_data: str = ""):
        """Ajoute une erreur au rapport"""
        from datetime import datetime
        error = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'line_number': line_number,
            'error_type': error_type,
            'error_message': error_message,
            'raw_data': raw_data
        }
        self.errors.append(error)
    
    def save_report(self):
        """Sauvegarde toutes les erreurs dans le fichier CSV"""
        if not self.errors:
            return
        
        with open(self.error_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for error in self.errors:
                writer.writerow([
                    error['timestamp'],
                    error['filename'],
                    error['line_number'],
                    error['error_type'],
                    error['error_message'],
                    error['raw_data']
                ])
        
        print(f"📝 {len(self.errors)} erreur(s) sauvegardée(s) dans {self.error_file}")
        self.errors.clear()


class ClientDetector:
    """Détecteur automatique du nom du client"""
    
    def __init__(self):
        # Patterns pour extraire le client du nom de fichier
        self.filename_patterns = [
            r'DPGF[_\-\s]*([A-Z][A-Za-z\s&\'\.]+?)[_\-\s]*Lot',
            r'([A-Z][A-Za-z\s&\'\.]+?)[\-_\s]*DPGF',
            r'Client[_\-\s]*([A-Z][A-Za-z\s&\'\.]+)',
            r'([A-Z]{2,}[\s&][A-Z\s\'\.]+)',  # Acronymes + mots
            r'^((?:[A-Z][a-zA-Z\'\.]+\s*)+)',  # Séquence de mots capitalisés au début
            r'[\\/]([A-Z][A-Za-z\s&\'\.]+?)[\\/][^\\\/]+\.xlsx$', # Client dans le chemin du dossier
            r'(?:projet|chantier)[_\-\s]+([A-Z][A-Za-z\s&\'\.]+)',  # Pattern après "projet" ou "chantier"
            r'_([A-Z][a-z]{2,}(?:[A-Z][a-z]+)+)_', # Nom en camelCase entouré de underscores
        ]
        
        # Patterns pour détecter un client dans le contenu
        self.content_patterns = [
            r'(?:client|maître d\'ouvrage|maitre d\'ouvrage|donneur d\'ordre)[^\w\n]{1,5}([A-Z][A-Za-z\s&\'\.]{2,})',
            r'(?:pour|destiné à|réalisé pour)[^\w\n]{1,5}([A-Z][A-ZaZ\s&\'\.]{2,})',
            r'(?:société|entreprise|groupe)[^\w\n]{1,5}([A-Z][A-ZaZ\s&\'\.]{2,})',
            r'^([A-Z][A-z]+(?:[\s\-][A-Z][A-z]+){1,3})\s*$', # Ligne avec uniquement un nom capitalisé
            r'Projet\s*(?:pour|de|avec)?\s*(?:la|le)?\s*([A-Z][A-Za-z\s&\'\.]{2,})',
            r'Chantier\s*(?:de|pour)?\s*([A-Z][A-ZaZ\s&\'\.]{2,})',
            r'(?:SA|SAS|SARL|GROUP|HABITAT)\s+([A-Z][A-ZaZ\s&\'\.]{2,})',
            r'([A-Z][A-ZaZ\s&\'\.]{2,})\s+(?:SA|SAS|SARL|GROUP|HABITAT)'
        ]
        
        # Mots-clés à ignorer dans la détection
        self.ignore_words = {'LOT', 'DPGF', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN', 
                           'JUILLET', 'AOUT', 'SEPTEMBRE', 'OCTOBRE', 'DCE', 'CONSTRUCTION', 'TRAVAUX', 'BATIMENT',
                           'APPEL', 'OFFRE', 'MARCHE', 'MAITRISE', 'OEUVRE', 'PROJET', 'CHANTIER', 'RENOVATION',
                           'REHABILITATION', 'DEVIS', 'ESTIMATION', 'PRIX', 'DOCUMENT', 'BORDEREAU', 'QUANTITATIF',
                           'REFERENCE', 'DESCRIPTION', 'CODE', 'UNITE', 'TOTAL', 'EUROS', 'EUR', 'HT', 'TTC'}
    
    def detect_from_filename(self, file_path: str) -> Optional[str]:
        """Détecte le client depuis le nom de fichier"""
        filename = Path(file_path).stem
        print(f"Analyse du nom de fichier: {filename}")
        
        for pattern in self.filename_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()
                # Nettoyer et valider
                client_name = self._clean_client_name(client_name)
                if client_name and len(client_name) > 3:
                    print(f"Client détecté dans le nom de fichier: {client_name}")
                    return client_name
        
        return None
        
    def detect_from_excel_header(self, file_path: str) -> Optional[str]:
        """Détecte le client dans les 15 premières lignes du fichier Excel"""
        try:
            # Détection automatique du moteur Excel selon l'extension
            engine = detect_excel_engine(file_path)
            # Lire seulement les premières lignes (augmenté à 15 pour une meilleure couverture)
            df = pd.read_excel(file_path, engine=engine, nrows=15, header=None)
            
            print("Analyse des premières lignes du fichier...")
            
            # 1. D'abord chercher des mots-clés spécifiques comme "Client:", "Maître d'ouvrage:"
            for row_idx in range(min(15, len(df))):
                row_text = " ".join([str(val).strip() for val in df.iloc[row_idx].values if pd.notna(val)])
                
                for pattern in self.content_patterns:
                    match = re.search(pattern, row_text, re.IGNORECASE)
                    if match:
                        client_name = match.group(1).strip()
                        client_name = self._clean_client_name(client_name)
                        if client_name and len(client_name) > 2:
                            print(f"Client détecté avec pattern spécifique (ligne {row_idx}): {client_name}")
                            return client_name
            
            # 2. Chercher dans toutes les cellules des premières lignes
            for row_idx in range(min(15, len(df))):
                for col_idx in range(min(8, len(df.columns))):  # Augmenté à 8 colonnes
                    cell_value = df.iloc[row_idx, col_idx]
                    
                    if pd.notna(cell_value):
                        cell_text = str(cell_value).strip()
                        
                        # Chercher des patterns de nom de client
                        client = self._extract_client_from_text(cell_text)
                        if client:
                            print(f"Client détecté dans la cellule [{row_idx},{col_idx}]: {client}")
                            return client
            
            # 3. Recherche de texte libre avec des noms d'entreprises connus
            known_companies = [
                "CDC HABITAT", "VINCI", "BOUYGUES", "EIFFAGE", "AXA", "BNP", "ICADE", "NEXITY", 
                "KAUFMAN", "COGEDIM", "PITCH", "PICHET", "AMETIS", "ADIM", "SOGEPROM", "MARIGNAN",
                "DEMATHIEU BARD", "ALTAREA", "CREDIT AGRICOLE", "SOCIETE GENERALE", "CARREFOUR", 
                "LECLERC", "AUCHAN", "LEROY MERLIN", "CASTORAMA", "LIDL", "ALDI", "COLAS"
            ]
            
            for row_idx in range(min(15, len(df))):
                row_text = " ".join([str(val).strip() for val in df.iloc[row_idx].values if pd.notna(val)])
                for company in known_companies:
                    if company in row_text.upper():
                        print(f"Entreprise connue détectée (ligne {row_idx}): {company}")
                        return company
            
            return None
        except Exception as e:
            print(f"Erreur lors de l'analyse de l'en-tête: {e}")
            return None
            
    def _extract_client_from_text(self, text: str) -> Optional[str]:
        """Extrait un nom de client depuis un texte"""
        # Patterns pour identifier un client
        client_patterns = [
            r'^([A-Z]{2,}(?:\s+[A-Z&\'\.]+)*)\s*$',  # Acronymes en majuscules
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z\'\.]+)*)\s*(?:HABITAT|GROUP|COMPANY|SA|SAS|SARL|SCI|IMMOBILIER)',
            r'((?:[A-Z]{2,}\s*)+)(?:HABITAT|GROUP|IMMOBILIER)',  # CDC HABITAT, BNP GROUP, etc.
            r'(?:^|\s)([A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){1,3})(?:\s|$)',  # Mots capitalisés (2-4 mots)
            r'(?:^|\s)([A-Z]{2,}(?:\s*[A-Z]{2,}){0,2})(?:\s|$)',  # Acronymes 2-3 lettres
            r'(?:société|entreprise|groupe|client|constructeur)\s+([A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){0,3})',
            r'[Pp]our\s+(?:le\s+compte\s+de\s+)?([A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){0,3})',
            r'[Aa]dresse\s*:?\s*(?:[^,]+,\s*)?([A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){1,3})',
            r'(?:^|\n)\s*([A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){1,2})\s*(?:$|\n)', # Nom isolé sur une ligne
        ]
        
        text = text.strip()
        for pattern in client_patterns:
            match = re.search(pattern, text)
            if match:
                client_name = match.group(1).strip()
                client_name = self._clean_client_name(client_name)
                
                # Valider que c'est un vrai nom de client
                if (len(client_name) >= 3 and 
                    not any(word.upper() in self.ignore_words for word in client_name.split()) and
                    any(c.isalpha() for c in client_name) and
                    len([w for w in client_name.split() if len(w) > 1]) > 0):  # Au moins un mot de plus d'une lettre
                    return client
        
        # Détecter les noms d'entreprises connus même sans pattern
        known_companies = [
            "CDC HABITAT", "VINCI", "BOUYGUES", "EIFFAGE", "AXA", "BNP", "ICADE", "NEXITY", 
            "KAUFMAN", "COGEDIM", "PITCH", "PICHET", "AMETIS", "ADIM", "SOGEPROM", "MARIGNAN",
            "DEMATHIEU BARD", "ALTAREA", "CREDIT AGRICOLE", "SOCIETE GENERALE", "CARREFOUR", 
            "LECLERC", "AUCHAN", "LEROY MERLIN", "CASTORAMA", "LIDL", "ALDI", "COLAS"
        ]
        for company in known_companies:
            if company in text.upper():
                return company
                
        return None
    
    def _clean_client_name(self, name: str) -> str:
        """Nettoie un nom de client"""
        # Supprimer caractères indésirables
        name = re.sub(r'[_\-\.]+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        # Supprimer mots parasites
        words = name.split()
        cleaned_words = [w for w in words if w.upper() not in self.ignore_words]
        
        return ' '.join(cleaned_words)
        
    def detect_client(self, file_path: str, include_file_suffix: bool = True) -> Optional[str]:
        """
        Détection complète du client (nom de fichier + contenu)
        
        Args:
            file_path: Chemin du fichier Excel
            include_file_suffix: Si True, ajoute un suffixe du nom de fichier au client pour le rendre unique
        """
        print(f"🔍 Détection automatique du client pour: {file_path}")
        filename = Path(file_path).stem
        
        client_candidates = []
        
        # 1. Essayer depuis le contenu du fichier (priorité au contenu car plus fiable)
        client_from_content = self.detect_from_excel_header(file_path)
        if client_from_content:
            client_candidates.append(("contenu", client_from_content))
        
        # 2. Essayer depuis le nom de fichier
        client_from_filename = self.detect_from_filename(file_path)
        if client_from_filename:
            client_candidates.append(("nom_fichier", client_from_filename))
        
        # 3. Essayer avec des mots uniques du nom de fichier
        unique_words = []
        if len(filename) > 5:
            words = re.findall(r'[A-Za-z]{4,}', filename)
            for word in words:
                if word.upper() not in self.ignore_words and word not in ["DPGF", "Lot", "LOT"]:
                    if len(word) >= 4:
                        unique_words.append(word)
        
        # Sélection du meilleur candidat
        if client_candidates:
            # Priorité au client détecté dans le contenu
            source, client = next((s, c) for s, c in client_candidates if s == "contenu") \
                            if any(s == "contenu" for s, _ in client_candidates) \
                            else client_candidates[0]
            
            # Générer un identifiant unique basé sur le nom de fichier
            if include_file_suffix:
                # Extraire un identifiant significatif du nom de fichier
                # Préférer un numéro de lot s'il existe
                lot_match = re.search(r'Lot\s*(\d+)', filename, re.IGNORECASE)
                if lot_match:
                    file_id = f"Lot{lot_match.group(1)}"
                else:
                    # Sinon utiliser un mot unique ou les premiers caractères
                    if unique_words:
                        file_id = unique_words[0][:8]
                    else:
                        file_id = filename.split()[0][:8]  # Premiers caractères du premier mot
                
                # Ajouter l'identifiant uniquement s'il n'est pas déjà dans le nom du client
                if file_id.upper() not in client.upper():
                    client = f"{client} ({file_id})"
            
            print(f"✓ Client détecté (source: {source}): {client}")
            return client
        
        # 4. Dernier recours: utiliser une partie du nom de fichier
        if unique_words:
            client = unique_words[0].capitalize()
            print(f"⚠️ Utilisation d'un mot unique du nom de fichier comme client: {client}")
            return client
        
        print("⚠️ Aucun client détecté automatiquement")
        return None


def detect_excel_engine(file_path: str) -> str:
    """Détecte automatiquement le bon moteur Excel selon l'extension du fichier"""
    file_extension = Path(file_path).suffix.lower()
    
    if file_extension == '.xls':
        # Fichier Excel ancien, utiliser xlrd
        try:
            import xlrd
            return 'xlrd'
        except ImportError:
            print("⚠️ Module xlrd non disponible pour les fichiers .xls")
            # Essayer openpyxl quand même (peut échouer)
            return 'openpyxl'
    elif file_extension in ['.xlsx', '.xlsm']:
        # Fichier Excel moderne, utiliser openpyxl
        return 'openpyxl'
    else:
        # Extension non reconnue, essayer openpyxl par défaut
        return 'openpyxl'


class GeminiCache:
    """Cache intelligent pour les réponses Gemini"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "gemini_patterns.pkl"
        self.patterns = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Charge le cache depuis le disque"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        """Sauvegarde le cache sur disque"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.patterns, f)
    
    def _get_pattern_hash(self, rows: List[str]) -> str:
        """Génère un hash pour un pattern de lignes"""
        # Normaliser les lignes (enlever espaces, casse)
        normalized = []
        for row in rows:
            normalized.append(''.join(row.lower().split()))
        
        pattern = '|'.join(normalized)
        return hashlib.md5(pattern.encode()).hexdigest()
    
    def get(self, rows: List[str]) -> Optional[List[Dict]]:
        """Récupère une classification depuis le cache"""
        pattern_hash = self._get_pattern_hash(rows)
        return self.patterns.get(pattern_hash)
    
    def set(self, rows: List[str], classification: List[Dict]):
        """Met en cache une classification"""
        pattern_hash = self._get_pattern_hash(rows)
        self.patterns[pattern_hash] = classification
        self._save_cache()


class ExcelParser:
    """Analyse les fichiers Excel DPGF avec détection de colonnes améliorée
    et support spécifique pour les formats SharePoint"""
    
    def __init__(self, file_path: str, column_mapper: ColumnMapping = None, error_reporter: ErrorReporter = None, 
                 dry_run: bool = False, gemini_processor: 'GeminiProcessor' = None):
        self.file_path = file_path
        self.column_mapper = column_mapper or ColumnMapping()
        self.error_reporter = error_reporter or ErrorReporter()
        self.dry_run = dry_run
        self.gemini_processor = gemini_processor
        
        # Initialiser le logger d'import amélioré
        self.logger = get_import_logger(file_path)
        self.logger.info(f"Initialisation de l'analyse pour {Path(file_path).name}")
        
        # Initialiser tous les attributs de colonnes et confiance
        self.col_designation = None
        self.col_unite = None
        self.col_quantite = None
        self.col_prix_unitaire = None
        self.col_prix_total = None
        self.mapping_confidence = 'unknown'  # 'high', 'medium', 'low', 'manual', 'sharepoint'
        self.headers_detected = False  # Ajouter cette ligne manquante
        self.is_sharepoint = False  # Initialiser par défaut à False
        
        # Vérifier si c'est un fichier SharePoint
        if SHAREPOINT_HELPER_AVAILABLE:
            try:
                self.is_sharepoint = is_sharepoint_file(file_path)
                if self.is_sharepoint:
                    self.logger.info("Format SharePoint détecté - Utilisation du helper spécialisé")
                    print("🔄 Format SharePoint détecté - Utilisation du helper spécialisé")
                    self.sharepoint_helper = SharePointExcelHelper(file_path)
                    self.sharepoint_helper.select_best_sheet()
                    self.df = self.sharepoint_helper.load_selected_sheet()
                    self.mapping_confidence = 'sharepoint'  # Indiquer que c'est un fichier SharePoint
                    return
            except Exception as e:
                self.logger.error(f"Erreur lors de l'analyse SharePoint: {e}")
                print(f"❌ Erreur lors de l'analyse SharePoint: {e}")
                self.is_sharepoint = False
        
        # Si ce n'est pas un fichier SharePoint ou si l'analyse échoue, utiliser la méthode standard
        self.df = self._read_best_sheet(file_path)
    
    def _read_best_sheet(self, file_path: str) -> pd.DataFrame:
        """Lit la meilleure feuille du fichier Excel (celle qui contient des données DPGF)"""
        try:
            # Détection automatique du moteur Excel selon l'extension
            engine = detect_excel_engine(file_path)
            xl_file = pd.ExcelFile(file_path, engine=engine)
            
            if len(xl_file.sheet_names) == 1:
                # Un seule feuille, l'utiliser directement
                return pd.read_excel(file_path, engine=engine, header=None)
            
            print(f"🔍 Fichier multi-feuilles détecté ({len(xl_file.sheet_names)} feuilles)")
            
            best_sheet = None
            best_score = 0
            
            for sheet_name in xl_file.sheet_names:
                try:
                    # Éviter les pages de garde et feuilles vides
                    if any(skip_word in sheet_name.lower() for skip_word in ['garde', 'page', 'cover', 'sommaire']):
                        continue
                    
                    df_sheet = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, header=None)
                    
                    if df_sheet.shape[0] == 0 or df_sheet.shape[1] == 0:
                        continue  # Feuille vide
                    
                    # Ajouter le nom de la feuille comme attribut pour le scoring
                    df_sheet.name = sheet_name
                    
                    # Scorer la feuille selon son contenu DPGF
                    score = self._score_sheet_content(df_sheet)
                    
                    print(f"   Feuille '{sheet_name}': {df_sheet.shape[0]}×{df_sheet.shape[1]}, score: {score}")
                    
                    if score > best_score:
                        best_score = score
                        best_sheet = (sheet_name, df_sheet)
                        
                except Exception as e:
                    print(f"   ⚠️ Erreur lecture feuille '{sheet_name}': {e}")
                    continue
            
            if best_sheet:
                sheet_name, df = best_sheet
                print(f"✅ Feuille sélectionnée: '{sheet_name}' (score: {best_score})")
                return df
            else:
                print("⚠️ Aucune feuille valide trouvée, utilisation de la première")
                return pd.read_excel(file_path, engine=engine, header=None)
                
        except Exception as e:
            print(f"⚠️ Erreur lors de la détection multi-feuilles: {e}")
            return pd.read_excel(file_path, engine=engine, header=None)
    
    def _score_sheet_content(self, df: pd.DataFrame) -> int:
        """Score le contenu d'une feuille pour déterminer si elle contient des données DPGF"""
        score = 0
        
        # === VÉRIFICATIONS PRIORITAIRES ===
        # Bonus important si la feuille contient plus de 20 lignes (données substantielles)
        if df.shape[0] > 20:
            score += 10
        elif df.shape[0] > 10:
            score += 5
        
        # Bonus pour le nombre de colonnes approprié pour un DPGF (4-15 colonnes typiques)
        if 4 <= df.shape[1] <= 15:
            score += 5
        elif df.shape[1] > 15:
            score -= 2  # Pénalité pour trop de colonnes
        
        # === ANALYSE DU CONTENU ===
        # Chercher des indices de contenu DPGF dans les premières lignes
        search_rows = min(20, df.shape[0])
        
        for i in range(search_rows):
            row = df.iloc[i]
            row_text = ' '.join([str(val).lower() for val in row if pd.notna(val)])
            
            # Mots-clés DPGF très spécifiques
            dpgf_keywords = [
                'designation', 'désignation', 'quantité', 'quantite', 'prix unitaire', 'prix total',
                'montant', 'unitaire', 'p.u.', 'pu', 'unité', 'unite'
            ]
            for keyword in dpgf_keywords:
                if keyword in row_text:
                    score += 8  # Score élevé pour les mots-clés DPGF
            
            # Patterns de numérotation d'articles (X.X.X, A.1.2)
            for val in row:
                if pd.notna(val):
                    val_str = str(val).strip()
                    if re.match(r'^\d+(\.\d+)*$', val_str) or re.match(r'^[A-Z]\d+(\.\d+)*$', val_str):
                        score += 3
            
            # Unités typiques BTP
            unit_keywords = ['ens', 'u', 'ml', 'm2', 'm²', 'm3', 'm³', 'kg', 'h', 'j', 'forfait', 'ft']
            for keyword in unit_keywords:
                if keyword in row_text:
                    score += 2
            
            # Termes techniques BTP
            btp_keywords = [
                'fourniture', 'pose', 'installation', 'montage', 'maçonnerie', 'maconnerie',
                'charpente', 'couverture', 'menuiserie', 'plomberie', 'électricité', 'electricite'
            ]
            for keyword in btp_keywords:
                if keyword in row_text:
                    score += 3
        
        # === DÉTECTION DE VALEURS NUMÉRIQUES ===
        # Compter les colonnes avec beaucoup de valeurs numériques (prix, quantités)
        numeric_columns = 0
        for col in range(min(10, df.shape[1])):
            numeric_count = 0
            for row in range(min(20, df.shape[0])):
                try:
                    if pd.notna(df.iloc[row, col]):
                        val = str(df.iloc[row, col]).replace(',', '.')
                        float(val)
                        numeric_count += 1
                except (ValueError, TypeError):
                    pass
            
            if numeric_count > 5:  # Plus de 5 valeurs numériques dans la colonne
                numeric_columns += 1
        
        score += numeric_columns * 3  # Bonus pour les colonnes numériques
        
        # === PÉNALITÉS POUR FAUSSES FEUILLES ===
        sheet_names_penalties = ['info', 'infos', 'garde', 'page', 'cover', 'sommaire', 'recap']
        sheet_name = getattr(df, 'name', '').lower() if hasattr(df, 'name') else ''
        
        # Pénalité si c'est probablement une feuille d'information
        if any(penalty_name in sheet_name for penalty_name in sheet_names_penalties):
            score -= 15
        
        # Pénalité si très peu de lignes (moins de 10)
        if df.shape[0] < 10:
            score -= 10
        
        # Bonus pour les noms de feuilles évocateurs de lots
        if re.search(r'lot\s*\d+', sheet_name, re.IGNORECASE):
            score += 15
        
        return max(0, score)  # Score minimum de 0
    
    def find_lot_headers(self) -> List[Tuple[str, str]]:
        """
        Recherche les intitulés de lot avec priorité au nom de fichier.
        Ordre de priorité:
        1. Extraction depuis le nom de fichier (le plus fiable)
        2. Détection avec Gemini (si disponible)
        3. Méthode classique - contenu du fichier
        
        Returns:
            Liste de tuples (numero_lot, nom_lot)
        """
        lots = []
        
        self.logger.info("==== DÉTECTION DE LOT ====")
        self.logger.info("Méthode 1: Extraction depuis le nom du fichier")
        
        # Priorité 1: Essayer d'extraire depuis le nom de fichier (plus fiable)
        filename_lot = self.extract_lot_from_filename()
        if filename_lot:
            self.logger.log_lot_detection("filename", True, filename_lot)
            print(f"✅ Lot détecté depuis le nom de fichier: {filename_lot[0]} - {filename_lot[1]}")
            return [filename_lot]
        else:
            self.logger.log_lot_detection("filename", False, error="Aucun pattern de lot trouvé dans le nom du fichier")
        
        # Priorité 2: Essayer avec Gemini si disponible
        if self.gemini_processor:
            self.logger.info("Méthode 2: Détection avec l'IA Gemini")
            try:
                filename = Path(self.file_path).name
                gemini_lot = self.gemini_processor.detect_lot_info(self.file_path, filename)
                if gemini_lot:
                    self.logger.log_lot_detection("gemini", True, gemini_lot)
                    print(f"✅ Lot détecté par Gemini: {gemini_lot[0]} - {gemini_lot[1]}")
                    return [gemini_lot]
                else:
                    self.logger.log_lot_detection("gemini", False, error="Gemini n'a pas pu identifier un lot")
            except Exception as e:
                error_msg = f"Erreur Gemini pour détection lot: {e}"
                self.logger.log_lot_detection("gemini", False, error=error_msg)
                print(f"⚠️ {error_msg}, fallback sur méthode classique")
        else:
            self.logger.info("Méthode 2: Détection avec l'IA Gemini [NON DISPONIBLE]")
        
        # Priorité 3: Méthode classique - analyser le contenu du fichier
        self.logger.info("Méthode 3: Analyse classique du contenu")
        pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
        
        # Parcourir les 15 premières lignes
        self.logger.debug(f"Recherche dans les {min(15, len(self.df))} premières lignes du fichier")
        for i in range(min(15, len(self.df))):
            for col in range(len(self.df.columns)):
                if col < len(self.df.columns):  # Vérification de sécurité
                    cell_value = self.df.iloc[i, col]
                    if pd.notna(cell_value):
                        cell_str = str(cell_value).strip()
                        match = pattern.search(cell_str)
                        if match:
                            numero_lot = match.group(1).strip()
                            nom_lot = match.group(2).strip()
                            lot_info = (numero_lot, nom_lot)
                            self.logger.log_lot_detection("content", True, lot_info, 
                                                         pattern=r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)',
                                                         error=f"Trouvé dans la cellule [{i},{col}]: '{cell_str}'")
                            print(f"✅ Lot détecté dans le contenu: {numero_lot} - {nom_lot}")
                            lots.append(lot_info)
        
        if lots:
            return lots
        
        self.logger.warning("ÉCHEC DE DÉTECTION - Aucun lot trouvé avec les méthodes disponibles")
        print("⚠️ Aucun lot détecté avec aucune méthode")
        return lots
    
    def extract_lot_from_filename(self) -> Optional[Tuple[str, str]]:
        """
        Extrait le numéro et nom du lot depuis le nom du fichier.
        Version ultra-renforcée pour tous les formats, même exotiques.
        
        Returns:
            Tuple (numero_lot, nom_lot) ou None si non trouvé
        """
        filename = Path(self.file_path).stem
        
        self.logger.debug(f"Analyse du nom de fichier: {filename}")
        
        # Patterns renforcés pour détecter un lot dans le nom de fichier (ordre de priorité)
        patterns = [
            # === PATTERNS STANDARDS ===
            # LOT 06 - DPGF - METALLERIE (très spécifique)
            r'lot\s*(\d{1,2})\s*-\s*(?:dpgf|devis|bpu|dqe)\s*-\s*([\w\s\-&°\'\.]+)',
            
            # DPGF-Lot 06 Métallerie (avec tiret)
            r'dpgf\s*[-_]?\s*lot\s*(\d{1,2})\s+([\w\s\-&°\'\.]+)',
            
            # LOT 06 - METALLERIE (avec tiret et nom)
            r'lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)',
            
            # === PATTERNS COMPLEXES ===
            # 802 DPGF Lot 2 - Curage (numéro au début + lot)
            r'^\d+\s+dpgf\s+lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)',
            
            # DPGF Lot 6 - Métallerie
            r'dpgf\s+lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)',
            
            # Lot06_Métallerie ou Lot 06 Métallerie
            r'lot\s*(\d{1,2})[_\-\s]+([\w\s\-&°\'\.]+)',
            
            # === PATTERNS SHAREPOINT ET ENTREPRISES ===
            # 25S012 - DPGF -Lot4 (pattern spécial SharePoint)
            r'-\s*dpgf\s*-?\s*lot\s*(\d{1,2})\s*-?\s*([\w\s\-&°\'\.]*)',
            
            # [Entreprise] - Lot 03 - Nom du lot
            r'[\[\(][\w\s]+[\]\)]\s*-\s*lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)',
            
            # === PATTERNS AVEC PRÉFIXES ===
            # DCE_Lot_06_Metallerie
            r'(?:dce|bce|appel|marche|projet)[-_\s]*lot[-_\s]*(\d{1,2})[-_\s]+([\w\s\-&°\'\.]+)',
            
            # Chantier_Nom_Lot06_Description
            r'(?:chantier|projet|travaux)[-_\s]*[\w\s]*[-_\s]*lot[-_\s]*(\d{1,2})[-_\s]+([\w\s\-&°\'\.]+)',
            
            # === PATTERNS AVEC CODES CLIENTS ===
            # CDC_HABITAT_LOT_6_METALLERIE
            r'(?:cdc|bnp|axa|vinci|bouygues)[-_\s]*(?:habitat|group|immobilier)?[-_\s]*lot[-_\s]*(\d{1,2})[-_\s]+([\w\s\-&°\'\.]+)',
            
            # === PATTERNS ALTERNATIFS ===
            # LOT6 - Description (collé)
            r'lot(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)',
            
            # Lot_6_Description (avec underscores)
            r'lot[-_](\d{1,2})[-_]([\w\s\-&°\'\.]+)',
            
            # 06_METALLERIE_LOT (inversé)
            r'(\d{1,2})[-_\s]*([\w\s\-&°\'\.]+)[-_\s]*lot',
            
            # === PATTERNS MINIMALISTES ===
            # Lot6 (juste numéro, sans description)
            r'lot\s*(\d{1,2})(?!\d)(?:[^\w\d]|$)',  # Éviter lot123
            
            # L06, L6 (format abrégé)
            r'\bL(\d{1,2})\b',
            
            # 6-METALLERIE (sans "lot")
            r'^(\d{1,2})\s*-\s*([\w\s\-&°\'\.]{5,})',
            
            # === PATTERNS DANS LE CHEMIN ===
            # Chercher aussi dans le chemin du fichier
            r'[\\/]lot[-_\s]*(\d{1,2})[-_\s]*([\w\s\-&°\'\.]*)',
        ]
        
        for idx, pattern in enumerate(patterns):
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    numero_lot = match.group(1).strip()
                    
                    # Si on a un deuxième groupe de capture, c'est le nom du lot
                    if len(match.groups()) > 1 and match.group(2):
                        nom_lot = self._clean_lot_name(match.group(2).strip())
                        
                        # Validation du nom de lot
                        if len(nom_lot) < 3:
                            nom_lot = self._generate_fallback_lot_name(numero_lot, filename)
                    else:
                        nom_lot = self._generate_fallback_lot_name(numero_lot, filename)
                    
                    # Validation du numéro de lot
                    try:
                        lot_num = int(numero_lot)
                        if not (1 <= lot_num <= 99):
                            continue  # Numéro de lot invalide
                    except ValueError:
                        continue
                    
                    self.logger.debug(f"Pattern #{idx+1} correspondant: '{pattern}' dans '{filename}'")
                    print(f"✓ Lot détecté depuis le nom du fichier: {numero_lot} - {nom_lot}")
                    return (numero_lot, nom_lot)
                except Exception as e:
                    self.logger.debug(f"Erreur lors de l'extraction avec le pattern #{idx+1}: {e}")
        
        # === DÉTECTION AVANCÉE PAR MOTS-CLÉS ===
        self.logger.debug("Aucun pattern standard trouvé, essai de détection avancée")
        
        # Chercher des mots-clés spécialisés du BTP pour inférer le type de lot
        specialty_keywords = {
            'gros_oeuvre': ['gros', 'oeuvre', 'béton', 'beton', 'maçonnerie', 'maconnerie', 'structure'],
            'charpente': ['charpente', 'bois', 'ossature'],
            'couverture': ['couverture', 'toiture', 'zinc', 'tuile', 'ardoise'],
            'menuiserie': ['menuiserie', 'fenêtre', 'fenetre', 'porte', 'volet'],
            'serrurerie': ['serrurerie', 'métallerie', 'metallerie', 'acier', 'fer'],
            'plomberie': ['plomberie', 'sanitaire', 'eau', 'évacuation', 'evacuation'],
            'electricite': ['électricité', 'electricite', 'éclairage', 'eclairage', 'courant'],
            'peinture': ['peinture', 'revêtement', 'revetement', 'finition'],
            'isolation': ['isolation', 'thermique', 'phonique'],
            'carrelage': ['carrelage', 'faïence', 'faience', 'sol'],
            'cloisons': ['cloison', 'doublage', 'plâtre', 'platre'],
            'vrd': ['vrd', 'voirie', 'réseau', 'reseau', 'assainissement'],
            'espaces_verts': ['espaces', 'verts', 'paysager', 'jardinage', 'plantation']
        }
        
        keywords = ['lot', 'dpgf', 'bpu', 'dqe', 'devis', 'bordereau']
        if any(keyword in filename.lower() for keyword in keywords):
            # Chercher un numéro dans le contexte
            digit_matches = re.finditer(r'(\d{1,2})', filename)
            for match in digit_matches:
                numero = match.group(1)
                try:
                    if 1 <= int(numero) <= 99:
                        # Identifier le type de lot par les mots-clés
                        filename_lower = filename.lower()
                        lot_type = "Travaux"  # Type par défaut
                        
                        for specialty, keywords_list in specialty_keywords.items():
                            if any(kw in filename_lower for kw in keywords_list):
                                lot_type = specialty.replace('_', ' ').title()
                                break
                        
                        nom_lot = f"{lot_type} - Lot {numero}"
                        
                        self.logger.debug(f"Lot inféré par mots-clés: {numero} - {nom_lot}")
                        print(f"✓ Lot inféré depuis le nom du fichier: {numero} - {nom_lot}")
                        return (numero, nom_lot)
                except ValueError:
                    continue
        
        # === ANALYSE DU CHEMIN DU FICHIER ===
        full_path = str(self.file_path)
        path_match = re.search(r'[\\/]lot[-_\s]*(\d{1,2})[-_\s]*([\w\s\-&°\'\.]*)', full_path, re.IGNORECASE)
        if path_match:
            numero_lot = path_match.group(1)
            nom_lot = self._clean_lot_name(path_match.group(2)) if path_match.group(2) else f"Lot {numero_lot}"
            
            self.logger.debug(f"Lot détecté dans le chemin: {numero_lot} - {nom_lot}")
            print(f"✓ Lot détecté depuis le chemin du fichier: {numero_lot} - {nom_lot}")
            return (numero_lot, nom_lot)
        
        self.logger.debug("Échec de la détection de lot dans le nom du fichier")
        return None
    
    def _clean_lot_name(self, name: str) -> str:
        """Nettoie et normalise un nom de lot"""
        if not name:
            return ""
        
        # Supprimer caractères indésirables
        cleaned = re.sub(r'[_\-\.]+', ' ', name)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        # Supprimer les extensions de fichier résiduelles
        cleaned = re.sub(r'\.(xlsx?|pdf|docx?)$', '', cleaned, flags=re.IGNORECASE)
        
        # Supprimer les mots parasites
        parasites = ['dpgf', 'bpu', 'dqe', 'devis', 'bordereau', 'quantitatif', 'prix', 'lot']
        words = cleaned.split()
        cleaned_words = [w for w in words if w.lower() not in parasites]
        
        result = ' '.join(cleaned_words).strip()
        
        # Capitaliser proprement
        if result:
            result = result.title()
        
        return result
    
    def _generate_fallback_lot_name(self, numero_lot: str, filename: str) -> str:
        """Génère un nom de lot par défaut basé sur le contexte"""
        # Essayer d'extraire des mots significatifs du nom de fichier
        words = re.findall(r'[A-Za-z]{3,}', filename)
        meaningful_words = []
        
        ignore_words = {
            'dpgf', 'bpu', 'dqe', 'devis', 'bordereau', 'quantitatif', 'prix', 'lot',
            'document', 'fichier', 'excel', 'pdf', 'word', 'nouveau', 'final',
            'version', 'copie', 'backup', 'temp', 'draft', 'brouillon'
        }
        
        for word in words:
            if word.lower() not in ignore_words and len(word) > 3:
                meaningful_words.append(word.title())
                if len(meaningful_words) >= 3:  # Limiter à 3 mots
                    break
        
        if meaningful_words:
            return f"Lot {numero_lot} - {' '.join(meaningful_words)}"
        else:
            return f"Lot {numero_lot} - Travaux"
        
    def detect_project_name(self, client_name: str = None) -> str:
        """
        Extrait le nom de projet avec une stratégie intelligente pour garantir l'unicité.
        
        Args:
            client_name: Nom du client pour l'inclure dans le nom du projet
            
        Returns:
            Nom du projet (str)
        """
        potential_names = []
        filename = Path(self.file_path).stem
        
        # 1. Chercher dans les premières cellules
        for i in range(min(5, len(self.df))):
            for col in range(min(3, len(self.df.columns))):
                cell_value = self.df.iloc[i, col]
                if pd.notna(cell_value):
                    value = str(cell_value).strip()
                    if len(value) > 5 and not any(w in value.upper() for w in ['DPGF', 'QUANTITATIF', 'BORDEREAU']):
                        potential_names.append(value)
        
        # 2. Extraire des infos pertinentes du nom de fichier
        file_info = []
        
        # Extraire le numéro et nom de lot
        lot_match = re.search(r'Lot\s*(\d+)[^\w]*([\w\s\-]+?)(?:\.xlsx|$)', filename, re.IGNORECASE)
        if lot_match:
            lot_num = lot_match.group(1)
            lot_name = lot_match.group(2).strip()
            if lot_name:
                file_info.append(f"Lot {lot_num} - {lot_name}")
            else:
                file_info.append(f"Lot {lot_num}")
        
        # 3. Construire un nom de projet distinctif
        project_parts = []
        
        # Inclure le nom du client s'il est fourni
        if client_name and len(client_name) > 2:
            project_parts.append(client_name)
        
        # Ajouter la meilleure info de contenu 
        if potential_names:
            best_name = max(potential_names, key=len)[:50]  # Limiter la longueur
            if best_name and not any(best_name.lower() in part.lower() for part in project_parts):
                project_parts.append(best_name)
        
        # Ajouter l'info du fichier
        if file_info:
            best_file_info = file_info[0]
            if not any(best_file_info.lower() in part.lower() for part in project_parts):
                project_parts.append(best_file_info)
        
        # Si on n'a pas assez d'infos, utiliser le nom de fichier
        if not project_parts or len(' - '.join(project_parts)) < 10:
            return filename
            
        # Construire le nom final
        return ' - '.join(project_parts)
    
    def find_header_row(self) -> Optional[int]:
        """
        Trouve la ligne d'en-tête contenant Désignation/Quantité/Prix unitaire/Prix total.
        Version améliorée avec plus de patterns et de robustesse.
        
        Returns:
            Index de la ligne d'en-tête ou None si non trouvée
        """
        # Si c'est un fichier SharePoint, utiliser la détection spécialisée
        if self.is_sharepoint and self.sharepoint_helper:
            self.logger.info("Utilisation de la détection d'en-tête SharePoint")
            header_row = self.sharepoint_helper.find_header_row_sharepoint()
            if header_row is not None:
                self.logger.info(f"En-tête SharePoint trouvé à la ligne {header_row+1}")
            else:
                self.logger.warning("Aucun en-tête SharePoint trouvé")
            return header_row
            
        # Patterns améliorés pour reconnaître les en-têtes (français et variations)
        header_patterns = {
            'designation': [
                r'désignation', r'designation', r'libellé', r'libelle', r'description', r'prestation', 
                r'article', r'détail', r'detail', r'ouvrage', r'intitulé', r'intitule', r'nature',
                r'objet', r'travaux', r'ouvrages?', r'prestations?', r'descriptions?', r'libelles?',
                r'n°.*art.*', r'ref.*art.*', r'code.*art.*', r'art\.?.*dés.*', r'dés.*art.*'
            ],
            'unite': [
                r'unité', r'unite', r'u\.?$', r'un\.?$', r'un$', r'unité de mesure', r'mesure', 
                r'unit', r'^u$', r'unités', r'mesures', r'type.*unit.*', r'unit.*mes.*'
            ],
            'quantite': [
                r'quantité', r'quantite', r'qté\.?', r'qt\.?', r'quant\.?', r'qte', r'nombre', 
                r'nb\.?', r'q\.?$', r'qtés?', r'quantités', r'nbres?', r'nombres'
            ],
            'prix_unitaire': [
                r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', 
                r'pu(?:\s*h\.?t\.?)?$', r'prix$', r'pu\s*ht$', r'prix\s*ht$',
                r'coût.*unit.*', r'tarif.*unit.*', r'€.*unit.*', r'euro.*unit.*',
                r'prix.*€', r'tarif', r'coût', r'montant.*unit.*'
            ],
            'prix_total': [
                r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', 
                r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?',
                r'sous.*total', r'coût.*total', r'€.*total', r'somme', r'montants?'
            ]
        }
        best_row = None
        best_score = 0
        
        # Parcourir les 30 premières lignes pour chercher les en-têtes
        for i in range(min(30, len(self.df))):
            row_values = [str(val).strip().lower() if pd.notna(val) else "" for val in self.df.iloc[i].values]
            row_text = " ".join(row_values)
            
            # Compter le nombre de patterns correspondants dans cette ligne
            score = 0
            found_patterns = {k: False for k in header_patterns.keys()}
            
            for col_name, patterns in header_patterns.items():
                # Chercher chaque pattern dans toute la ligne d'abord
                for pattern in patterns:
                    if re.search(pattern, row_text, re.IGNORECASE):
                        found_patterns[col_name] = True
                        score += 1
                        break
                
                # Si le pattern n'est pas trouvé dans la ligne entière, chercher dans chaque cellule
                if not found_patterns[col_name]:
                    for col_idx, cell_text in enumerate(row_values):
                        for pattern in patterns:
                            if re.search(f"^{pattern}$", cell_text, re.IGNORECASE):
                                found_patterns[col_name] = True
                                score += 1
                                break
                        if found_patterns[col_name]:
                            break
            
            # Si on a trouvé au moins 2 des 5 en-têtes attendus, c'est probablement la bonne ligne
            if score >= 2:
                if score > best_score:
                    best_score = score
                    best_row = i
            
            # Si on a trouvé tous les en-têtes, on arrête la recherche
            if score >= 4:  # 4/5 colonnes trouvées = excellent score
                print(f"✓ Ligne d'en-tête trouvée (ligne {i+1}): score excellent ({score}/5)")
                return i
        
        if best_row is not None:
            print(f"✓ Ligne d'en-tête trouvée (ligne {best_row+1}): score {best_score}/5")
        else:
            print("⚠️ Aucune ligne d'en-tête trouvée, l'analyse pourrait être moins précise")
            
        return best_row
    
    def detect_column_indices(self, header_row_idx: Optional[int]) -> Dict[str, Optional[int]]:
        """
        Détermine l'indice des colonnes importantes en se basant sur l'en-tête
        Intègre le mapping manuel interactif et persistant
        
        Args:
            header_row_idx: Indice de la ligne d'en-tête
            
        Returns:
            Dictionnaire avec les indices des colonnes
        """
        # Si c'est un fichier SharePoint, utiliser la détection spécialisée
        if self.is_sharepoint and self.sharepoint_helper:
            self.logger.info("Utilisation de la détection de colonnes SharePoint")
            column_indices = self.sharepoint_helper.detect_column_indices_sharepoint(header_row_idx)
            self._store_column_indices(column_indices)
            self.mapping_confidence = 'sharepoint'
            print(f"✅ Mapping SharePoint appliqué: {column_indices}")
            return column_indices
            
        # Récupérer les headers pour le mapping
        if header_row_idx is not None:
            headers = [str(val).strip() if pd.notna(val) else f"Colonne_{i}" 
                      for i, val in enumerate(self.df.iloc[header_row_idx].values)]
        else:
            # Générer des headers par défaut
            headers = [f"Colonne_{i}" for i in range(len(self.df.columns))]
        
        # 1. Essayer de récupérer un mapping existant
        filename = Path(self.file_path).stem
        existing_mapping = self.column_mapper.get_mapping(headers, filename)
        
        if existing_mapping:
            print("✅ Mapping existant trouvé et appliqué")
            self.mapping_confidence = 'manual'
            self._store_column_indices(existing_mapping)
            return existing_mapping
        
        # 2. Essayer la détection automatique
        column_indices = self._detect_columns_automatically(header_row_idx, headers)
        
        # 3. Évaluer la confiance du mapping automatique
        confidence_score = self._evaluate_mapping_confidence(column_indices, headers)
        
        if confidence_score >= 4:  # Mapping très confiant
            self.mapping_confidence = 'high'
            print(f"✅ Mapping automatique avec haute confiance (score: {confidence_score}/5)")
        elif confidence_score >= 2:  # Mapping modérément confiant
            self.mapping_confidence = 'medium'
            print(f"⚠️ Mapping automatique avec confiance moyenne (score: {confidence_score}/5)")
            
            # Demander confirmation en mode interactif
            if not self.dry_run:
                print("\nVoulez-vous:")
                print("1. Utiliser ce mapping automatique")
                print("2. Configurer manuellement")
                choice = input("Votre choix (1/2): ").strip()
                
                if choice == '2':
                    column_indices = self.column_mapper.interactive_mapping(headers)
                    self.column_mapper.save_mapping(headers, column_indices, filename)
                    self.mapping_confidence = 'manual'
        else:  # Mapping peu confiant
            self.mapping_confidence = 'low'
            print(f"❌ Mapping automatique peu fiable (score: {confidence_score}/5)")
            
            if not self.dry_run:
                print("🔧 Configuration manuelle recommandée...")
                column_indices = self.column_mapper.interactive_mapping(headers)
                self.column_mapper.save_mapping(headers, column_indices, filename)
                self.mapping_confidence = 'manual'
            else:
                print("⚠️ Mode dry-run: mapping automatique utilisé malgré la faible confiance")
        
        self._store_column_indices(column_indices)
        return column_indices
    
    def _store_column_indices(self, column_indices: Dict[str, Optional[int]]):
        """Stocke les indices des colonnes dans l'instance"""
        self.col_designation = column_indices['designation']
        self.col_unite = column_indices['unite']
        self.col_quantite = column_indices['quantite']
        self.col_prix_unitaire = column_indices['prix_unitaire']
        self.col_prix_total = column_indices['prix_total']
        self.headers_detected = True
    
    def _evaluate_mapping_confidence(self, column_indices: Dict[str, Optional[int]], headers: List[str]) -> int:
        """Évalue la confiance du mapping automatique"""
        score = 0
        
        # Compter les colonnes essentielles détectées
        essential_cols = ['designation', 'unite', 'prix_unitaire']
        for col in essential_cols:
            if column_indices.get(col) is not None:
                score += 1
        
        # Bonus si on a quantité ou prix total
        if column_indices.get('quantite') is not None or column_indices.get('prix_total') is not None:
            score += 1
        
        # Vérifier que les headers semblent cohérents
        if column_indices.get('designation') is not None and column_indices['designation'] < len(headers):
            header = headers[column_indices['designation']].lower()
            if any(word in header for word in ['designation', 'description', 'libelle', 'article']):
                score += 1
        
        return score
    
    def _detect_columns_automatically(self, header_row_idx: Optional[int], headers: List[str]) -> Dict[str, Optional[int]]:
        """Détection automatique des colonnes (code original)"""
        # Initialiser les indices à None
        column_indices = {
            'designation': None,
            'unite': None,
            'quantite': None,
            'prix_unitaire': None,
            'prix_total': None
        }
        
        # Si on n'a pas d'en-tête, on essaie une approche par défaut
        if header_row_idx is None:
            print("⚠️ Utilisation des indices de colonne par défaut")
            column_indices['designation'] = 0
            
            # Pour les autres colonnes, on examine quelques lignes pour trouver des nombres
            num_rows = min(20, len(self.df))
            num_cols = min(10, len(self.df.columns))
            
            # Compter combien de valeurs numériques on a dans chaque colonne
            num_counts = {col: 0 for col in range(1, num_cols)}
            for row in range(5, num_rows):  # Commencer après les potentiels en-têtes
                for col in range(1, num_cols):
                    if pd.notna(self.df.iloc[row, col]):
                        try:
                            # Tester si la valeur est numérique (entier ou décimal)
                            val_str = str(self.df.iloc[row, col]).replace(',', '.')
                            float(val_str)
                            num_counts[col] += 1
                        except ValueError:
                            pass
            
            # Les colonnes avec le plus de valeurs numériques sont probablement quantité/prix
            numeric_cols = sorted([(col, count) for col, count in num_counts.items() if count > 3], 
                                  key=lambda x: x[1], reverse=True)
            
            if len(numeric_cols) >= 3:
                # Supposer un ordre typique: unité, quantité, prix unitaire, prix total
                column_indices['unite'] = 1  # Souvent juste avant les nombres
                column_indices['quantite'] = numeric_cols[0][0]
                column_indices['prix_unitaire'] = numeric_cols[1][0]
                column_indices['prix_total'] = numeric_cols[2][0]
            elif len(numeric_cols) == 2:
                # Au minimum, on a besoin de quantité et prix
                column_indices['quantite'] = numeric_cols[0][0]
                column_indices['prix_unitaire'] = numeric_cols[1][0]
            
            print(f"Détection colonnes par défaut: {column_indices}")
            return column_indices
        
        # Si on a un en-tête, on cherche les correspondances avec des patterns connus
        header_row = [str(val).strip().lower() if pd.notna(val) else "" for val in self.df.iloc[header_row_idx].values]
        
        # Patterns pour chaque type de colonne
        patterns = {
            'designation': [r'désignation', r'designation', r'libellé', r'libelle', r'description', r'prestation', r'article', r'détail', r'detail', r'ouvrage', r'intitulé', r'intitule', r'nature'],
            'unite': [r'unité', r'unite', r'u\.?$', r'un\.?$', r'un$', r'unité de mesure', r'mesure', r'^u$'],
            'quantite': [r'quantité', r'quantite', r'qté\.?', r'qt\.?', r'quant\.?', r'qte'],
            'prix_unitaire': [r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', r'pu(?:\s*h\.?t\.?)?', r'pu\s*ht$', r'prix\s*ht$'],
            'prix_total': [r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?']
        }
        
        # Chercher chaque pattern dans les cellules de la ligne d'en-tête
        for col_name, col_patterns in patterns.items():
            for col_idx, cell_text in enumerate(header_row):
                cell_text = cell_text.lower()
                for pattern in col_patterns:
                    if re.search(pattern, cell_text, re.IGNORECASE):
                        column_indices[col_name] = col_idx
                        print(f"Colonne '{col_name}' détectée: indice {col_idx}, valeur: '{header_row[col_idx]}'")
                        break
                if column_indices[col_name] is not None:
                    break
        
        # Pour les colonnes non détectées, essayer une détection par position logique
        # Si la désignation n'est pas trouvée, chercher la colonne la plus large avec du texte
        if column_indices['designation'] is None:
            # Chercher la colonne avec le plus de contenu textuel dans les lignes suivantes
            max_text_col = 0
            max_text_score = 0
            
            for col_idx in range(min(5, len(header_row))):  # Examiner les 5 premières colonnes
                text_score = 0
                for row_idx in range(header_row_idx + 1, min(header_row_idx + 10, len(self.df))):
                    if col_idx < len(self.df.iloc[row_idx]) and pd.notna(self.df.iloc[row_idx, col_idx]):
                        cell_value = str(self.df.iloc[row_idx, col_idx])
                        if len(cell_value) > 10:  # Désignations sont généralement longues
                            text_score += len(cell_value)
                
                if text_score > max_text_score:
                    max_text_score = text_score
                    max_text_col = col_idx
            
            column_indices['designation'] = max_text_col
            print(f"⚠️ Colonne 'designation' non détectée, supposée être à l'indice {max_text_col} (analyse du contenu)")
        
        # Vérifications et inférences des colonnes non détectées
        # Si on a trouvé prix unitaire et quantité mais pas prix total, on cherche après prix unitaire
        if column_indices['prix_unitaire'] is not None and column_indices['quantite'] is not None and column_indices['prix_total'] is None:
            if column_indices['prix_unitaire'] + 1 < len(header_row):
                column_indices['prix_total'] = column_indices['prix_unitaire'] + 1
                print(f"⚠️ Colonne 'prix_total' non détectée, supposée être à l'indice {column_indices['prix_total']}")
        
        # Si on a trouvé prix total et quantité mais pas prix unitaire, on cherche avant prix total
        if column_indices['prix_total'] is not None and column_indices['quantite'] is not None and column_indices['prix_unitaire'] is None:
            if column_indices['prix_total'] - 1 >= 0:
                column_indices['prix_unitaire'] = column_indices['prix_total'] - 1
                print(f"⚠️ Colonne 'prix_unitaire' non détectée, supposée être à l'indice {column_indices['prix_unitaire']}")
        
        # Si on a trouvé prix unitaire mais pas quantité, vérifier si ce n'est pas un BPU (bordereau de prix unitaires)
        # Dans un BPU, il n'y a souvent pas de colonne quantité car ce sont des prix de référence
        if column_indices['prix_unitaire'] is not None and column_indices['quantite'] is None:
            # Si on a 'designation', 'unite' et 'prix_unitaire' mais pas 'quantite', c'est probablement un BPU
            if column_indices['designation'] is not None and column_indices['unite'] is not None:
                print(f"ℹ️ Format BPU détecté (pas de colonne quantité), ce qui est normal")
                # Ne pas assigner d'indice de colonne pour quantité dans ce cas
            else:
                # Sinon, essayer d'inférer la position de la quantité
                if column_indices['prix_unitaire'] - 1 >= 0:
                    column_indices['quantite'] = column_indices['prix_unitaire'] - 1
                    print(f"⚠️ Colonne 'quantite' non détectée, supposée être à l'indice {column_indices['quantite']}")
        
        # Si l'unité n'est pas trouvée, on peut supposer qu'elle est entre désignation et quantité
        if column_indices['unite'] is None and column_indices['designation'] is not None and column_indices['quantite'] is not None:
            if column_indices['quantite'] > column_indices['designation'] + 1:
                column_indices['unite'] = column_indices['quantite'] - 1
                print(f"⚠️ Colonne 'unite' non détectée, supposée être à l'indice {column_indices['unite']}")
        
        # Afficher les résultats de la détection
        print(f"✓ Indices des colonnes détectés: {column_indices}")
        
        return column_indices
    
    def safe_convert_to_float(self, value) -> float:
        """
        Convertit une valeur en float de façon sécurisée, en gérant les formats européens.
        
        Args:
            value: Valeur à convertir (str, int, float, etc.)
            
        Returns:
            Valeur convertie en float, ou 0.0 si erreur
        """
        if pd.isna(value):
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            # Nettoyer la valeur
            val_str = str(value).strip()
            
            # Supprimer les symboles monétaires et autres caractères
            val_str = re.sub(r'[€$£\s]', '', val_str)
            
            # Remplacer les virgules par des points (format européen)
            if ',' in val_str and '.' not in val_str:
                val_str = val_str.replace(',', '.')
            
            # Traiter les cas comme "1.234,56" (format européen) -> "1234.56"
            if '.' in val_str and ',' in val_str:
                if val_str.find('.') < val_str.find(','):
                    val_str = val_str.replace('.', '')
                    val_str = val_str.replace(',', '.')
            
            # Convertir en float
            return float(val_str)
        except (ValueError, TypeError):
            # Si la conversion échoue, on retourne 0
            print(f"⚠️ Impossible de convertir en nombre: '{value}'")
            return 0.0
    
    def detect_sections_and_elements(self, header_row: Optional[int] = None) -> List[Dict]:
        """
        Version considérablement améliorée de la détection des sections et éléments d'ouvrage.
        Utilise des algorithmes adaptatifs et des heuristiques avancées pour tous les formats de DPGF.
        
        Args:
            header_row: Index de la ligne d'en-tête
            
        Returns:
            Liste de dictionnaires avec 'type' ('section' ou 'element') et 'data'
        """
        results = []
        
        self.logger.info("==== DÉTECTION AVANCÉE DES SECTIONS ET ÉLÉMENTS ====")
        
        # Trouver la ligne d'en-tête si non spécifiée
        if header_row is None:
            header_row = self.find_header_row()
            self.logger.info(f"Recherche automatique de l'en-tête: {'trouvé à la ligne ' + str(header_row+1) if header_row is not None else 'non trouvé'}")
        else:
            self.logger.info(f"Utilisation de l'en-tête spécifié: ligne {header_row+1}")
        
        # Détecter les indices des colonnes
        if not self.headers_detected:
            self.detect_column_indices(header_row)
        
        # Si on n'a pas pu détecter les colonnes essentielles, on utilise des valeurs par défaut
        if self.col_designation is None:
            self.col_designation = 0
            self.logger.warning("Colonne de désignation non détectée, utilisation de la première colonne par défaut")
        
        self.logger.info(f"Colonnes utilisées: désignation={self.col_designation}, unité={self.col_unite}, "
              f"quantité={self.col_quantite}, prix unitaire={self.col_prix_unitaire}, prix total={self.col_prix_total}")
        
        print(f"Colonnes utilisées: désignation={self.col_designation}, unité={self.col_unite}, "
              f"quantité={self.col_quantite}, prix unitaire={self.col_prix_unitaire}, prix total={self.col_prix_total}")
        
        # Patterns ultra-renforcés pour la détection des sections
        section_patterns = {
            # === PATTERNS STANDARDS ===
            # Sections numérotées standard (1.2.3 Titre)
            'numbered_standard': re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)'),
            
            # Sections numérotées avec tirets ou points (1.2.3- Titre, 1.2.3. Titre)
            'numbered_punctuated': re.compile(r'^(\d+(?:\.\d+)*)[.-]\s*(.+)'),
            
            # === PATTERNS HIÉRARCHIQUES ===
            # Numérotation hiérarchique complexe (A.1.2.3, 01.02.03.04)
            'hierarchical_complex': re.compile(r'^([A-Z]?\d{1,2}(?:\.\d{1,2}){1,4})\s+(.+)'),
            
            # Numérotation avec préfixes (A1, B2, C3)
            'letter_number': re.compile(r'^([A-Z]\d{1,3})\s+(.+)'),
            
            # === PATTERNS SPÉCIALISÉS BTP ===
            # Sections avec numéros de lots (LOT 06.01, LOT 6.1)
            'lot_subsection': re.compile(r'^(LOT\s+\d{1,2}(?:\.\d+)*)\s+(.+)', re.IGNORECASE),
            
            # Articles de devis (ART. 123, Art 456)
            'article_numbered': re.compile(r'^(ART\.?\s*\d+)\s+(.+)', re.IGNORECASE),
            
            # === PATTERNS DE TITRES ===
            # Titres en majuscules (ESCALIERS METALLIQUES)
            'uppercase_title': re.compile(r'^([A-Z][A-Z\s\d\.\-\_\&\']{4,})$'),
            
            # Titres soulignés ou encadrés
            'underlined_title': re.compile(r'^([=\-_]{3,})\s*([A-Z].{3,})\s*[=\-_]{3,}$'),
            
            # Titres avec numérotation romaine (I. Titre, IV - Titre)
            'roman_numeral': re.compile(r'^([IVX]{1,5})[.\-\s]\s*(.+)'),
            
            # Lettres majuscules (A. Titre, B - Titre)
            'letter_numeral': re.compile(r'^([A-H])[.\-\s]\s*(.+)'),
            
            # === PATTERNS AVEC PRÉFIXES ===
            # Sections avec préfixes (CHAPITRE 1, LOT 06, PARTIE A)
            'prefixed_section': re.compile(r'^(CHAPITRE|LOT|PARTIE|SECTION|SOUS-SECTION|TITRE)\s+([A-Z0-9]+)[\s\:]*(.*)'),
            
            # Sections avec préfixes techniques (POSTE, OUVRAGE, PRESTATION)
            'technical_prefix': re.compile(r'^(POSTE|OUVRAGE|PRESTATION|TRAVAUX|FOURNITURE)\s+([A-Z0-9\.]+)[\s\:]*(.*)'),
            
            # === PATTERNS DE TOTAUX ===
            # Totaux et sous-totaux (SOUS-TOTAL, TOTAL GENERAL)
            'total_section': re.compile(r'^(SOUS[\-\s]*TOTAL|TOTAL|MONTANT\s+TOTAL|RÉCAPITULATIF|RECAPITULATIF)[\s\:]*(.*)'),
            
            # === PATTERNS SHAREPOINT SPÉCIAUX ===
            # Sections SharePoint spéciales (5.1, 5.1.1)
            'sharepoint_numbered': re.compile(r'^(\d+\.\d+(?:\.\d+)*)\s*(.*)'),
            
            # Numérotation SharePoint avec tirets
            'sharepoint_dashed': re.compile(r'^(\d+\-\d+(?:\-\d+)*)\s+(.+)'),
            
            # === PATTERNS EXOTIQUES ===
            # Sections avec parenthèses (1) Titre, (A) Titre
            'parentheses_numbered': re.compile(r'^\(([A-Z0-9]+)\)\s+(.+)'),
            
            # Sections avec crochets [1] Titre, [A] Titre
            'brackets_numbered': re.compile(r'^\[([A-Z0-9]+)\]\s+(.+)'),
            
            # Sections avec tirets initiaux (- Titre de section)
            'dash_section': re.compile(r'^\s*[-•]\s+([A-Z].{5,})$'),
            
            # Sections avec puces (• Titre, ◦ Titre)
            'bullet_section': re.compile(r'^\s*[•◦▪▫]\s+([A-Z].{5,})$'),
            
            # === PATTERNS DE NUMÉROTATION ALTERNATIVE ===
            # Numérotation décimale française (1,2,3 au lieu de 1.2.3)
            'decimal_french': re.compile(r'^(\d+(?:,\d+)*)\s+(.+)'),
            
            # Numérotation avec suffixes (1er, 2ème, 3ème)
            'ordinal_french': re.compile(r'^(\d+(?:er|ème|nd|rd|th))\s+(.+)'),
            
            # === PATTERNS CONTEXTUELS ===
            # Phases de travaux (PHASE 1, ÉTAPE A)
            'phase_step': re.compile(r'^(PHASE|ÉTAPE|ETAPE|STADE)\s+([A-Z0-9]+)\s*[\:\-]?\s*(.*)'),
            
            # Zones de travaux (ZONE A, SECTEUR 1)
            'zone_sector': re.compile(r'^(ZONE|SECTEUR|PÉRIMÈTRE|PERIMETRE)\s+([A-Z0-9]+)\s*[\:\-]?\s*(.*)'),
            
            # === PATTERNS MULTI-FORMATS ===
            # Format mixte alphanumérique (A1.2, B3.4)
            'mixed_alphanumeric': re.compile(r'^([A-Z]\d+(?:\.\d+)*)\s+(.+)'),
            
            # Codes articles complexes (ABC123, XYZ456)
            'complex_codes': re.compile(r'^([A-Z]{2,4}\d{2,4})\s+(.+)'),
            
            # === PATTERNS DE CONTINUITÉ ===
            # Numérotation continue avec slash (1/10, 2/10)
            'fraction_numbered': re.compile(r'^(\d+/\d+)\s+(.+)'),
            
            # Numérotation avec version (V1.2, REV.3)
            'version_numbered': re.compile(r'^(V\d+(?:\.\d+)*|REV\.?\d+)\s+(.+)'),
        }
        
        self.logger.info(f"Patterns de détection utilisés: {len(section_patterns)} patterns avancés")
        self.logger.debug(f"Patterns: {', '.join(section_patterns.keys())}")
        current_section = None
        
        # Si header_row est None (pas trouvé), commencer depuis le début
        start_row = header_row + 1 if header_row is not None else 0
        self.logger.info(f"Début de l'analyse à partir de la ligne {start_row+1}")
        
        sections_count = 0
        elements_count = 0
        default_sections_created = 0
        
        # Variables pour l'analyse contextuelle
        last_section_level = 0
        section_hierarchy = {}
        potential_elements_without_section = []
        
        for i in range(start_row, len(self.df)):
            row = self.df.iloc[i]
            
            # Ignorer les lignes vides
            if all(pd.isna(val) for val in row.values):
                continue
            
            # Vérifier si c'est une section (texte en début de ligne)
            if pd.notna(row.iloc[self.col_designation]):
                cell_text = str(row.iloc[self.col_designation]).strip()
                section_detected = False
                
                # Essayer tous les patterns de section dans l'ordre de priorité
                for pattern_name, pattern in section_patterns.items():
                    match = pattern.match(cell_text)
                    if match:
                        section_data = self._extract_section_from_match(match, pattern_name, cell_text)
                        
                        if section_data:
                            # Calculer le niveau hiérarchique
                            niveau = self._calculate_hierarchical_level(section_data['numero_section'], pattern_name, last_section_level)
                            section_data['niveau_hierarchique'] = niveau
                            
                            # Mettre à jour la hiérarchie
                            section_hierarchy[niveau] = section_data['numero_section']
                            # Nettoyer les niveaux inférieurs
                            keys_to_remove = [k for k in section_hierarchy.keys() if k > niveau]
                            for k in keys_to_remove:
                                del section_hierarchy[k]
                            
                            current_section = section_data
                            last_section_level = niveau
                            
                            self.logger.log_section_detection(True, i, current_section, pattern_name, cell_text)
                            
                            results.append({
                                'type': 'section',
                                'data': current_section,
                                'row': i
                            })
                            sections_count += 1
                            section_detected = True
                            break
                
                if section_detected:
                    continue
                else:
                    self.logger.log_section_detection(False, i, None, "aucun", cell_text)
                
                # Si ce n'est pas une section, analyser si c'est un élément
                element_analysis = self._analyze_potential_element(row, cell_text, i)
                
                if element_analysis['is_element']:
                    # Si on n'a pas encore de section, créer une section par défaut ou utiliser les éléments en attente
                    if current_section is None:
                        if not potential_elements_without_section:
                            # Créer une section par défaut
                            current_section = {
                                'numero_section': '1',
                                'titre_section': 'Éléments du bordereau',
                                'niveau_hierarchique': 1
                            }
                            results.append({
                                'type': 'section',
                                'data': current_section,
                                'row': i
                            })
                            self.logger.log_section_creation('1', 'Éléments du bordereau', 1, True)
                            default_sections_created += 1
                            sections_count += 1
                        else:
                            # Traiter les éléments en attente
                            for pending_element in potential_elements_without_section:
                                results.append(pending_element)
                                elements_count += 1
                            potential_elements_without_section.clear()
                    
                    # Créer l'élément avec les données extraites
                    element_data = self._create_element_data(row, element_analysis, cell_text)
                    
                    self.logger.log_element_detection(i, element_data['designation_exacte'], 
                                                      element_analysis['has_price_data'], 
                                                      element_analysis['has_unit_data'])
                    
                    element_entry = {
                        'type': 'element',
                        'data': element_data,
                        'row': i
                    }
                    
                    if current_section is not None:
                        results.append(element_entry)
                        elements_count += 1
                    else:
                        potential_elements_without_section.append(element_entry)
                    
                    continue
        
        # Traiter les éléments en attente à la fin
        if potential_elements_without_section:
            # Créer une dernière section par défaut si nécessaire
            if current_section is None:
                current_section = {
                    'numero_section': '1',
                    'titre_section': 'Éléments restants',
                    'niveau_hierarchique': 1
                }
                results.append({
                    'type': 'section',
                    'data': current_section,
                    'row': len(self.df)
                })
                sections_count += 1
                default_sections_created += 1
            
            for pending_element in potential_elements_without_section:
                results.append(pending_element)
                elements_count += 1
        
        self.logger.info(f"Détection terminée: {sections_count} sections ({default_sections_created} par défaut), {elements_count} éléments")
        print(f"Total éléments/sections détectés: {len(results)} ({sections_count} sections, {elements_count} éléments)")
        return results

    def _extract_section_from_match(self, match, pattern_name: str, original_text: str) -> Optional[Dict]:
        """Extrait les données de section selon le pattern correspondant avec gestion étendue"""
        try:
            if pattern_name == 'uppercase_title':
                # Titre en majuscules
                titre_section = match.group(1).strip()
                # Générer un numéro unique mais prévisible
                section_hash = abs(hash(titre_section)) % 10000
                numero_section = f"S{section_hash:04d}"
                
            elif pattern_name in ['numbered_standard', 'numbered_punctuated', 'sharepoint_numbered', 'sharepoint_dashed']:
                # Sections numérotées standards
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else f"Section {numero_section}"
                
            elif pattern_name in ['roman_numeral', 'letter_numeral']:
                # Numérotation romaine ou lettre
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name in ['prefixed_section', 'technical_prefix']:
                # Sections avec préfixes (CHAPITRE, LOT, POSTE, etc.)
                prefix = match.group(1).strip()
                number = match.group(2).strip()
                title = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
                numero_section = f"{prefix} {number}"
                titre_section = title if title else numero_section
                
            elif pattern_name == 'total_section':
                # Totaux et sous-totaux
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else numero_section
                
            elif pattern_name in ['hierarchical_complex', 'mixed_alphanumeric', 'complex_codes']:
                # Articles et codes complexes
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name in ['parentheses_numbered', 'brackets_numbered']:
                # Sections avec parenthèses ou crochets
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name in ['dash_section', 'bullet_section']:
                # Sections avec tirets ou puces
                titre_section = match.group(1).strip()
                numero_section = f"SEC_{abs(hash(titre_section)) % 1000:03d}"
                
            elif pattern_name in ['letter_number', 'lot_subsection', 'article_numbered']:
                # Patterns avec lettres + numéros
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else f"Section {numero_section}"
                
            elif pattern_name in ['decimal_french', 'ordinal_french', 'fraction_numbered', 'version_numbered']:
                # Numérotations alternatives
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name in ['phase_step', 'zone_sector']:
                # Phases et zones
                prefix = match.group(1).strip()
                identifier = match.group(2).strip()
                description = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
                numero_section = f"{prefix} {identifier}"
                titre_section = description if description else numero_section
                
            elif pattern_name == 'underlined_title':
                # Titres soulignés
                titre_section = match.group(2).strip()
                numero_section = f"TITLE_{abs(hash(titre_section)) % 1000:03d}"
                
            else:
                # Pattern non reconnu, essayer une extraction générique
                if len(match.groups()) >= 2:
                    numero_section = match.group(1).strip()
                    titre_section = match.group(2).strip()
                else:
                    titre_section = match.group(1).strip()
                    numero_section = f"GEN_{abs(hash(titre_section)) % 1000:03d}"
            
            # Nettoyage et validation
            if not titre_section:
                titre_section = f"Section {numero_section}"
            
            # S'assurer que le numéro de section ne dépasse pas 50 caractères (contrainte DB)
            if len(numero_section) > 50:
                numero_section = numero_section[:47] + "..."
            
            # S'assurer que le titre ne dépasse pas 255 caractères
            if len(titre_section) > 255:
                titre_section = titre_section[:252] + "..."
            
            return {
                'numero_section': numero_section,
                'titre_section': titre_section
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction de section avec pattern '{pattern_name}': {e}")
            # Fallback en cas d'erreur
            safe_title = re.sub(r'[^\w\s\-]', '', original_text)[:100]
            return {
                'numero_section': f"ERR_{abs(hash(safe_title)) % 1000:03d}",
                'titre_section': safe_title if safe_title else "Section non identifiée"
            }

    def _calculate_hierarchical_level(self, numero_section: str, pattern_name: str, last_level: int) -> int:
        """Calcule le niveau hiérarchique d'une section avec gestion étendue des patterns"""
        if pattern_name in ['numbered_standard', 'numbered_punctuated', 'sharepoint_numbered', 
                          'hierarchical_complex', 'mixed_alphanumeric']:
            # Pour les sections numérotées, compter les points/séparateurs
            level = numero_section.count('.') + numero_section.count(',') + 1
            
            # Cas spéciaux pour les numérotations complexes
            if pattern_name == 'hierarchical_complex':
                # A.1.2.3 -> niveau 4, mais A1 -> niveau 1
                if re.match(r'^[A-Z]\d+$', numero_section):
                    level = 1
                else:
                    level = numero_section.count('.') + 1
            
            return level
            
        elif pattern_name in ['uppercase_title', 'underlined_title']:
            # Les titres en majuscules sont généralement de niveau 1 (titres principaux)
            return 1
            
        elif pattern_name in ['roman_numeral']:
            # Numérotation romaine = niveau 1 généralement (chapitres principaux)
            return 1
            
        elif pattern_name in ['letter_numeral', 'letter_number']:
            # Lettres = niveau 2 généralement (sous-sections)
            return 2
            
        elif pattern_name in ['prefixed_section', 'technical_prefix']:
            # Les sections préfixées sont souvent de niveau 1 (sections principales)
            return 1
            
        elif pattern_name == 'total_section':
            # Les totaux sont au même niveau que la section précédente ou niveau 2
            return max(2, last_level)
            
        elif pattern_name in ['lot_subsection', 'article_numbered']:
            # Sous-sections de lot = niveau 2 ou 3
            if re.search(r'\d+\.\d+', numero_section):
                return 3  # LOT 06.01 = niveau 3
            else:
                return 2  # LOT 06 = niveau 2
                
        elif pattern_name in ['parentheses_numbered', 'brackets_numbered']:
            # Sections avec parenthèses/crochets = niveau 2 ou 3
            if numero_section.isdigit():
                return int(numero_section) if int(numero_section) <= 5 else 2
            else:
                return 2
                
        elif pattern_name in ['dash_section', 'bullet_section']:
            # Sections avec tirets/puces = niveau 2 généralement
            return 2
            
        elif pattern_name in ['decimal_french', 'ordinal_french']:
            # Numérotation décimale française = compter les virgules
            return numero_section.count(',') + 1
            
        elif pattern_name in ['fraction_numbered']:
            # Numérotation fractionnelle (1/10) = niveau basé sur le premier nombre
            first_num = numero_section.split('/')[0]
            try:
                return min(int(first_num), 5)  # Max niveau 5
            except ValueError:
                return 2
                
        elif pattern_name in ['version_numbered']:
            # Numérotation de version = niveau 1 (versions principales)
            return 1
            
        elif pattern_name in ['phase_step', 'zone_sector']:
            # Phases et zones = niveau 1 (divisions principales)
            return 1
            
        elif pattern_name in ['sharepoint_dashed']:
            # Numérotation SharePoint avec tirets = compter les tirets
            return numero_section.count('-') + 1
            
        elif pattern_name in ['complex_codes']:
            # Codes complexes = niveau 2 généralement
            return 2
            
        else:
            # Pattern non reconnu, utiliser le niveau précédent ou 1 par défaut
            return max(1, last_level)

    def _analyze_potential_element(self, row, cell_text: str, row_index: int) -> Dict:
        """
        Analyse ultra-renforcée pour déterminer si une ligne est un élément d'ouvrage.
        Capable de gérer tous les formats DPGF, même exotiques, avec gestion multi-lignes.
        """
        analysis = {
            'is_element': False,
            'has_price_data': False,
            'has_unit_data': False,
            'has_designation_data': False,
            'has_article_number': False,
            'has_technical_indicators': False,
            'has_quantity_data': False,
            'is_multiline_element': False,
            'confidence_score': 0,
            'element_type': 'standard'  # 'standard', 'forfait', 'variable', 'bpu'
        }
        
        # === 1. ANALYSE DE LA DÉSIGNATION ===
        if len(cell_text) > 2:
            analysis['has_designation_data'] = True
            analysis['confidence_score'] += 1
            
            # Indicateurs techniques avancés dans la désignation
            technical_indicators = [
                # Fourniture et pose
                'fourniture', 'pose', 'f et p', 'f&p', 'fp', 'fourni et posé', 'fourni posé',
                'installation', 'montage', 'mise en place', 'mise en œuvre', 'mise en oeuvre',
                
                # Actions spécifiques du BTP
                'démolition', 'demolition', 'dépose', 'depose', 'découpe', 'decoupe', 'perçage', 'percage',
                'calfeutrement', 'étanchéité', 'etancheite', 'isolation', 'raccordement',
                'scellement', 'fixation', 'assemblage', 'soudure', 'vissage', 'clouage',
                
                # Types d'ouvrages
                'maçonnerie', 'maconnerie', 'béton', 'beton', 'ferraillage', 'coffrage', 'banche',
                'charpente', 'couverture', 'zinguerie', 'bardage', 'façade', 'facade',
                'cloison', 'doublage', 'plafond', 'sol', 'carrelage', 'faïence', 'faience',
                'peinture', 'enduit', 'crépi', 'crepi', 'papier peint', 'tapisserie',
                'menuiserie', 'serrurerie', 'métallerie', 'metallerie', 'aluminium', 'pvc',
                'plomberie', 'sanitaire', 'chauffage', 'ventilation', 'climatisation', 'vmc',
                'électricité', 'electricite', 'éclairage', 'eclairage', 'tableau électrique',
                'réseau', 'reseau', 'câblage', 'cablage', 'gaine', 'conduit',
                
                # Matériaux spécifiques
                'acier', 'inox', 'galvanisé', 'galvanise', 'laiton', 'cuivre', 'plomb',
                'pierre', 'marbre', 'granit', 'calcaire', 'grès', 'gres', 'ardoise',
                'tuile', 'zinc', 'plomb', 'membrane', 'bitume', 'epdm',
                'laine de verre', 'laine de roche', 'polystyrène', 'polystyrene',
                'plaque de plâtre', 'ba13', 'fermacell', 'osb', 'contreplaqué', 'contreplaque',
                
                # Équipements et accessoires
                'robinetterie', 'appareil', 'équipement', 'equipement', 'accessoire',
                'poignée', 'poignee', 'serrure', 'cylindre', 'gâche', 'gache',
                'charnière', 'charniere', 'paumelle', 'pivot', 'rail', 'guide',
                
                # Finitions
                'finition', 'parement', 'habillage', 'protection', 'traitement',
                'lasure', 'vernis', 'teinture', 'imprégnation', 'impregnation'
            ]
            
            if any(indicator in cell_text.lower() for indicator in technical_indicators):
                analysis['has_technical_indicators'] = True
                analysis['confidence_score'] += 2
                
            # Détection des forfaits et prestations globales
            forfait_indicators = [
                'forfait', 'ft', 'global', 'ensemble', 'prestation',
                'intervention', 'déplacement', 'deplacement', 'minimum',
                'heure', 'jour', 'semaine', 'mois', 'période', 'periode'
            ]
            
            if any(indicator in cell_text.lower() for indicator in forfait_indicators):
                analysis['element_type'] = 'forfait'
                analysis['confidence_score'] += 1
                
            # Détection des prix variables/provisoires
            variable_indicators = [
                'variable', 'provisoire', 'éventuel', 'eventuel', 'optionnel',
                'selon', 'suivant', 'conformément', 'conformement',
                'à définir', 'a definir', 'à préciser', 'a preciser'
            ]
            
            if any(indicator in cell_text.lower() for indicator in variable_indicators):
                analysis['element_type'] = 'variable'
                analysis['confidence_score'] += 1
        
        # === 2. ANALYSE DES NUMÉROS D'ARTICLES (RENFORCÉE) ===
        if cell_text:
            words = cell_text.split()
            if words:
                first_word = words[0].strip()
                
                # Patterns d'articles étendus
                article_patterns = [
                    r'^[A-Z]\d+(?:\.\d+)*$',           # A1.2.3
                    r'^\d+(?:\.\d+){1,4}$',            # 1.2.3.4
                    r'^[A-Z]{1,3}\.\d+(?:\.\d+)*$',    # ABC.1.2
                    r'^\d{2,4}[A-Z]?$',                # 1234, 123A
                    r'^[A-Z]\d{2,4}$',                 # A123
                    r'^\d+[A-Z]\d+$',                  # 1A2
                    r'^Art\.\s*\d+',                   # Art. 123
                    r'^\d+\s*-',                       # 123 -
                    r'^\d+\)',                         # 123)
                    r'^\w+\.\w+\.\w+',                 # ABC.DEF.123
                ]
                
                for pattern in article_patterns:
                    if re.match(pattern, first_word, re.IGNORECASE):
                        analysis['has_article_number'] = True
                        analysis['confidence_score'] += 2
                        break
                
                # Vérifier si le premier mot ressemble à un code article même sans pattern strict
                if (len(first_word) >= 3 and 
                    any(c.isdigit() for c in first_word) and 
                    len(cell_text) > len(first_word) + 5):
                    analysis['has_article_number'] = True
                    analysis['confidence_score'] += 1
        
        # === 3. ANALYSE DES UNITÉS (ULTRA-RENFORCÉE) ===
        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
            unit_text = str(row.iloc[self.col_unite]).strip().lower()
            if unit_text and unit_text not in ['', '0', 'nan', '-']:
                analysis['has_unit_data'] = True
                analysis['confidence_score'] += 1
                
                # Unités étendues et variantes
                standard_units = [
                    # Surfaces
                    'm2', 'm²', 'M2', 'M²', 'mètres carrés', 'metres carres', 'mc', 'm.c.',
                    'dm2', 'dm²', 'cm2', 'cm²', 'ha', 'hectare',
                    
                    # Longueurs
                    'ml', 'm.l.', 'mètre linéaire', 'metre lineaire', 'mètres linéaires',
                    'm', 'mètre', 'metre', 'mm', 'millimètre', 'millimetre',
                    'cm', 'centimètre', 'centimetre', 'km', 'kilomètre', 'kilometre',
                    
                    # Volumes
                    'm3', 'm³', 'M3', 'M³', 'mètres cubes', 'metres cubes',
                    'dm3', 'dm³', 'cm3', 'cm³', 'litre', 'l', 'L',
                    
                    # Poids
                    'kg', 'kilogramme', 'kilo', 'g', 'gramme', 't', 'tonne',
                    
                    # Unités de comptage
                    'u', 'un', 'unité', 'unite', 'pièce', 'piece', 'pce', 'pc',
                    'ens', 'ensemble', 'jeu', 'lot', 'série', 'serie',
                    'paire', 'pr', 'kit', 'boîte', 'boite', 'sachet', 'sac',
                    
                    # Temps
                    'h', 'heure', 'j', 'jour', 'journée', 'journee',
                    'semaine', 'mois', 'année', 'annee',
                    
                    # Forfaits
                    'forfait', 'ft', 'f', 'global', 'gb', 'intervention',
                    
                    # Spécialisées BTP
                    'point', 'pt', 'passage', 'rang', 'couche',
                    'application', 'appl', 'traitement', 'trmt'
                ]
                
                if any(unit in unit_text for unit in standard_units):
                    analysis['confidence_score'] += 2
                elif len(unit_text) <= 5 and unit_text.isalpha():
                    # Unité courte alphabétique probable
                    analysis['confidence_score'] += 1
        
        # === 4. ANALYSE DES DONNÉES NUMÉRIQUES (AMÉLIORÉE) ===
        numeric_cols_with_data = 0
        total_numeric_value = 0
        
        # Vérifier la quantité
        if self.col_quantite is not None and self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite]):
            try:
                val = self.safe_convert_to_float(row.iloc[self.col_quantite])
                if val > 0:
                    analysis['has_quantity_data'] = True
                    numeric_cols_with_data += 1
                    total_numeric_value += val
                    analysis['confidence_score'] += 1
                    
                    # Bonus pour quantités cohérentes
                    if 0.01 <= val <= 10000:  # Plage raisonnable
                        analysis['confidence_score'] += 1
            except:
                pass
        
        # Vérifier le prix unitaire
        if self.col_prix_unitaire is not None and self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]):
            try:
                val = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
                if val > 0:
                    analysis['has_price_data'] = True
                    numeric_cols_with_data += 1
                    total_numeric_value += val
                    analysis['confidence_score'] += 2
                    
                    # Bonus pour prix cohérents
                    if 0.01 <= val <= 100000:  # Plage raisonnable pour un prix unitaire
                        analysis['confidence_score'] += 1
            except:
                pass
        
        # Vérifier le prix total
        if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
            try:
                val = self.safe_convert_to_float(row.iloc[self.col_prix_total])
                if val > 0:
                    analysis['has_price_data'] = True
                    numeric_cols_with_data += 1
                    total_numeric_value += val
                    analysis['confidence_score'] += 2
                    
                    # Bonus pour prix totaux cohérents
                    if 1 <= val <= 1000000:  # Plage raisonnable pour un prix total
                        analysis['confidence_score'] += 1
            except:
                pass
        
        # === 5. DÉTECTION MULTI-LIGNES ===
        # Vérifier si l'élément continue sur la ligne suivante
        if row_index + 1 < len(self.df):
            next_row = self.df.iloc[row_index + 1]
            if pd.notna(next_row.iloc[self.col_designation]):
                next_text = str(next_row.iloc[self.col_designation]).strip()
                
                # Indicateurs de continuation
                continuation_patterns = [
                    r'^-',                    # Commence par tiret
                    r'^\.',                   # Commence par point
                    r'^[a-z]',               # Commence par minuscule
                    r'^et\s',                # Commence par "et"
                    r'^ou\s',                # Commence par "ou"
                    r'^\(',                  # Commence par parenthèse
                    r'^avec\s',              # Commence par "avec"
                    r'^comprenant\s',        # Commence par "comprenant"
                    r'^y\s*compris\s',       # Y compris
                ]
                
                if any(re.match(pattern, next_text, re.IGNORECASE) for pattern in continuation_patterns):
                    analysis['is_multiline_element'] = True
                    analysis['confidence_score'] += 1
        
        # === 6. INDICATEURS CONTEXTUELS SPÉCIALISÉS ===
        context_indicators = [
            # Termes techniques BTP
            'selon dtu', 'selon nf', 'selon caue', 'conforme à', 'conforme a',
            'règles de l\'art', 'regles de l\'art', 'prescriptions', 'cahier des charges',
            
            # Localisation des travaux
            'en façade', 'en facade', 'en toiture', 'en combles', 'en sous-sol',
            'à l\'étage', 'a l\'etage', 'au rez-de-chaussée', 'au rdc',
            'en extérieur', 'en exterieur', 'en intérieur', 'en interieur',
            
            # Conditions de mise en œuvre
            'sur chantier', 'en atelier', 'en usine', 'à pied d\'œuvre', 'a pied d\'oeuvre',
            'transport compris', 'livraison comprise', 'évacuation comprise',
            
            # Prestations associées
            'nettoyage compris', 'protection comprise', 'étiquetage compris',
            'garantie comprise', 'maintenance comprise', 'entretien compris'
        ]
        
        if any(indicator in cell_text.lower() for indicator in context_indicators):
            analysis['confidence_score'] += 1
        
        # === 7. DÉTECTION DE FAUX POSITIFS ===
        false_positive_indicators = [
            # Titres et sections
            'chapitre', 'partie', 'section', 'sous-total', 'total général', 'total general',
            'montant total', 'récapitulatif', 'recapitulatif', 'sommaire',
            
            # En-têtes et descriptions
            'désignation', 'designation', 'quantité', 'quantite', 'prix unitaire',
            'prix total', 'montant', 'référence', 'reference',
            
            # Informations générales
            'page', 'feuille', 'annexe', 'note', 'remarque', 'observation',
            'conditions générales', 'conditions generales', 'modalités', 'modalites'
        ]
        
        if any(indicator in cell_text.lower() for indicator in false_positive_indicators):
            if len(cell_text) < 50:  # Si c'est court, c'est probablement un faux positif
                analysis['confidence_score'] -= 2
        
        # === 8. AJUSTEMENTS SELON LE TYPE DE DOCUMENT ===
        if analysis['element_type'] == 'forfait':
            # Pour les forfaits, moins d'exigences sur les données numériques
            min_score_required = 2
        elif analysis['element_type'] == 'variable':
            # Pour les éléments variables, accepter sans prix
            min_score_required = 3
        else:
            # Pour les éléments standards
            min_score_required = 3
        
        # === 9. DÉCISION FINALE MULTI-CRITÈRES ===
        essential_criteria = (
            analysis['has_designation_data'] and
            len(cell_text) >= 5 and  # Désignation minimum viable
            (
                analysis['has_price_data'] or 
                analysis['has_unit_data'] or 
                analysis['has_article_number'] or
                analysis['has_technical_indicators'] or
                numeric_cols_with_data >= 1
            )
        )
        
        # Critères de qualité supplémentaires
        quality_criteria = (
            analysis['confidence_score'] >= min_score_required and
            not (analysis['confidence_score'] < 0)  # Pas de score négatif
        )
        
        analysis['is_element'] = essential_criteria and quality_criteria
        
        # Logging détaillé pour debug
        if analysis['is_element']:
            self.logger.debug(f"Élément détecté ligne {row_index+1}: score={analysis['confidence_score']}, "
                            f"type={analysis['element_type']}, multi-lignes={analysis['is_multiline_element']}")
        elif essential_criteria:
            self.logger.debug(f"Élément potentiel rejeté ligne {row_index+1}: score insuffisant ({analysis['confidence_score']}/{min_score_required})")
        
        return analysis

    def _create_element_data(self, row, analysis: Dict, designation: str) -> Dict:
        """
        Crée les données d'un élément d'ouvrage avec gestion avancée des différents types
        et agrégation multi-lignes
        """
        # === GESTION MULTI-LIGNES ===
        full_designation = designation
        
        # Si c'est un élément multi-lignes, agréger les lignes suivantes
        if analysis.get('is_multiline_element', False):
            current_row_idx = self.df.index[self.df.iloc[:, self.col_designation] == designation].tolist()
            if current_row_idx:
                row_idx = current_row_idx[0]
                # Chercher les lignes de continuation
                for next_idx in range(row_idx + 1, min(row_idx + 5, len(self.df))):  # Max 5 lignes
                    if pd.notna(self.df.iloc[next_idx, self.col_designation]):
                        next_text = str(self.df.iloc[next_idx, self.col_designation]).strip()
                        
                        # Vérifier si c'est une continuation
                        continuation_patterns = [
                            r'^-', r'^\.', r'^[a-z]', r'^et\s', r'^ou\s', r'^\(',
                            r'^avec\s', r'^comprenant\s', r'^y\s*compris\s'
                        ]
                        
                        if any(re.match(pattern, next_text, re.IGNORECASE) for pattern in continuation_patterns):
                            full_designation += " " + next_text
                            self.logger.debug(f"Agrégation multi-lignes: {next_text}")
                        else:
                            break
                    else:
                        break
        
        # === RÉCUPÉRATION DES DONNÉES DE BASE ===
        # Unité avec normalisation
        unite = ""
        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
            unite_raw = str(row.iloc[self.col_unite]).strip()
            unite = self._normalize_unit(unite_raw)
        
        # Quantité avec validation
        quantite = 0.0
        if self.col_quantite is not None and self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite]):
            quantite = self.safe_convert_to_float(row.iloc[self.col_quantite])
            # Validation de cohérence
            if quantite < 0:
                self.logger.warning(f"Quantité négative détectée: {quantite}, conversion en valeur absolue")
                quantite = abs(quantite)
        
        # Prix unitaire avec validation
        prix_unitaire = 0.0
        if self.col_prix_unitaire is not None and self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]):
            prix_unitaire = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
            if prix_unitaire < 0:
                self.logger.warning(f"Prix unitaire négatif détecté: {prix_unitaire}, conversion en valeur absolue")
                prix_unitaire = abs(prix_unitaire)
        
        # Prix total avec validation et calcul intelligent
        prix_total = 0.0
        if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
            prix_total = self.safe_convert_to_float(row.iloc[self.col_prix_total])
            if prix_total < 0:
                self.logger.warning(f"Prix total négatif détecté: {prix_total}, conversion en valeur absolue")
                prix_total = abs(prix_total)
        
        # === CALCULS INTELLIGENTS ET COHÉRENCE ===
        # Si prix total manque mais on a quantité et prix unitaire
        if prix_total == 0 and quantite > 0 and prix_unitaire > 0:
            prix_total = quantite * prix_unitaire
            self.logger.debug(f"Prix total calculé: {quantite} × {prix_unitaire} = {prix_total}")
        
        # Si prix unitaire manque mais on a quantité et prix total
        elif prix_unitaire == 0 and quantite > 0 and prix_total > 0:
            prix_unitaire = prix_total / quantite
            self.logger.debug(f"Prix unitaire calculé: {prix_total} ÷ {quantite} = {prix_unitaire}")
        
        # Si quantité manque mais on a prix unitaire et prix total
        elif quantite == 0 and prix_unitaire > 0 and prix_total > 0:
            quantite = prix_total / prix_unitaire
            self.logger.debug(f"Quantité calculée: {prix_total} ÷ {prix_unitaire} = {quantite}")
        
        # === GESTION DES CAS SPÉCIAUX ===
        element_type = analysis.get('element_type', 'standard')
        
        if element_type == 'forfait':
            # Pour les forfaits, la quantité est souvent 1
            if quantite == 0:
                quantite = 1.0
                if prix_total > 0:
                    prix_unitaire = prix_total
                self.logger.debug(f"Forfait détecté, quantité ajustée à 1")
        
        elif element_type == 'variable':
            # Pour les éléments variables, marquer dans la désignation
            if 'variable' not in full_designation.lower():
                full_designation += " (Prix variable)"
        
        # === VALIDATION FINALE ===
        # Vérifications de cohérence
        if quantite > 0 and prix_unitaire > 0:
            calculated_total = quantite * prix_unitaire
            if prix_total > 0 and abs(calculated_total - prix_total) > 0.02:  # Tolérance de 2 centimes
                self.logger.warning(f"Incohérence détectée: {quantite} × {prix_unitaire} = {calculated_total} ≠ {prix_total}")
                # Prioriser le prix total s'il est cohérent
                if prix_total > 0:
                    prix_unitaire = prix_total / quantite
        
        # === EXTRACTION DU NUMÉRO D'ARTICLE ===
        numero_article = ""
        words = full_designation.split()
        if words and analysis.get('has_article_number', False):
            first_word = words[0].strip()
            article_patterns = [
                r'^[A-Z]\d+(?:\.\d+)*$',
                r'^\d+(?:\.\d+){1,4}$',
                r'^[A-Z]{1,3}\.\d+(?:\.\d+)*$',
                r'^\d{2,4}[A-Z]?$',
                r'^[A-Z]\d{2,4}$'
            ]
            
            for pattern in article_patterns:
                if re.match(pattern, first_word, re.IGNORECASE):
                    numero_article = first_word
                    # Retirer le numéro de la désignation pour éviter la duplication
                    full_designation = " ".join(words[1:]).strip()
                    break
        
        return {
            'designation_exacte': full_designation[:500],  # Limiter à 500 caractères
            'numero_article': numero_article[:20] if numero_article else "",
            'unite': unite[:10] if unite else "",
            'quantite': round(quantite, 4),  # Précision à 4 décimales
            'prix_unitaire_ht': round(prix_unitaire, 4),
            'prix_total_ht': round(prix_total, 2),  # Prix en centimes
            'type_element': element_type,
            'multilignes': analysis.get('is_multiline_element', False)
        }
    
    def _normalize_unit(self, unit_raw: str) -> str:
        """Normalise les unités pour uniformiser les données"""
        unit_normalized = unit_raw.lower().strip()
        
        # Dictionnaire de normalisation des unités
        unit_mapping = {
            # Surfaces
            'm²': 'm2', 'M²': 'm2', 'M2': 'm2', 'mètres carrés': 'm2', 'metres carres': 'm2',
            'dm²': 'dm2', 'cm²': 'cm2', 'hectare': 'ha',
            
            # Longueurs
            'm.l.': 'ml', 'mètre linéaire': 'ml', 'metre lineaire': 'ml', 'mètres linéaires': 'ml',
            'mètre': 'm', 'metre': 'm', 'millimètre': 'mm', 'millimetre': 'mm',
            'centimètre': 'cm', 'centimetre': 'cm', 'kilomètre': 'km', 'kilometre': 'km',
            
            # Volumes
            'm³': 'm3', 'M³': 'm3', 'M3': 'm3', 'mètres cubes': 'm3', 'metres cubes': 'm3',
            'dm³': 'dm3', 'cm³': 'cm3', 'litre': 'L',
            
            # Poids
            'kilogramme': 'kg', 'kilo': 'kg', 'gramme': 'g', 'tonne': 't',
            
            # Unités de comptage
            'unité': 'u', 'unite': 'u', 'pièce': 'u', 'piece': 'u', 'pce': 'u', 'pc': 'u',
            'ensemble': 'ens', 'paire': 'pr', 'boîte': 'boite', 'boite': 'boite',
            
            # Temps
            'heure': 'h', 'jour': 'j', 'journée': 'j', 'journee': 'j',
            
            # Forfaits
            'forfait': 'ft', 'global': 'gb'
        }
        
        # Chercher une correspondance exacte
        if unit_normalized in unit_mapping:
            return unit_mapping[unit_normalized]
        
        # Chercher une correspondance partielle
        for original, normalized in unit_mapping.items():
            if original in unit_normalized:
                return normalized
        
        # Si pas de correspondance, retourner l'unité nettoyée
        return unit_raw[:10]  # Limiter à 10 caractères


class GeminiProcessor:
    """Traitement des données avec l'API Gemini"""
    
    def __init__(self, api_key: str, chunk_size: int = 20):
        if not GEMINI_AVAILABLE:
            raise ImportError("Le module google.generativeai n'est pas disponible")
        
        self.api_key = api_key
        self.chunk_size = chunk_size
        self.cache = GeminiCache()
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.stats = ImportStats()
        
        # Flags pour le fallback automatique
        self.gemini_failed = False
        self.consecutive_failures = 0
        self.max_failures_before_fallback = 3
    
    def read_excel_chunks(self, file_path: str) -> Generator[pd.DataFrame, None, None]:
        """Lit un fichier Excel par chunks pour économiser la mémoire"""
        print(f"Lecture du fichier par chunks de {self.chunk_size} lignes...")
        
        # Lire par chunks
        skip_rows = 0
        # Détection automatique du moteur Excel selon l'extension
        engine = detect_excel_engine(file_path)
        
        while True:
            try:
                chunk = pd.read_excel(
                    file_path, 
                    engine=engine,
                    skiprows=range(1, skip_rows + 1) if skip_rows > 0 else None,
                    nrows=self.chunk_size
                )
                
                if chunk.empty:
                    break
                
                yield chunk
                skip_rows += self.chunk_size
                
            except Exception as e:
                print(f"Erreur lecture chunk à partir de la ligne {skip_rows}: {e}")
                break
    
    def classify_chunk(self, df_chunk: pd.DataFrame, chunk_offset: int = 0) -> List[Dict]:
        """Classifie un chunk avec Gemini + cache + fallback intelligent"""
        
        # Si Gemini a échoué trop de fois, ne pas essayer
        if self.gemini_failed:
            print(f"⚠️ Gemini en mode fallback (trop d'échecs) - chunk ignoré")
            return []
        
        # Préparer les données du chunk
        chunk_rows = []
        for i, row in df_chunk.iterrows():
            row_values = [str(val) if pd.notna(val) else "" for val in row.values]
            if any(val.strip() for val in row_values):
                chunk_rows.append(f"Ligne {chunk_offset + i}: {row_values}")
        
        if not chunk_rows:
            return []
        
        # Vérifier le cache
        cached_result = self.cache.get(chunk_rows)
        if cached_result:
            self.stats.cache_hits += 1
            print(f"Cache hit pour chunk de {len(chunk_rows)} lignes")
            # Ajuster les numéros de ligne pour le chunk actuel
            for item in cached_result:
                item['row'] += chunk_offset
            return cached_result
        
        # Appel Gemini si pas en cache
        self.stats.gemini_calls += 1
        result = self._call_gemini_api(chunk_rows, chunk_offset)
        
        # Vérifier si Gemini a retourné un résultat valide
        if result is None:  # Erreur d'API
            self.consecutive_failures += 1
            print(f"⚠️ Échec Gemini #{self.consecutive_failures} pour ce chunk")
            
            if self.consecutive_failures >= self.max_failures_before_fallback:
                self.gemini_failed = True
                print(f"❌ Gemini désactivé après {self.consecutive_failures} échecs consécutifs (quota/erreur API)")
            
            return []
        elif result == []:  # Résultat vide mais pas d'erreur
            return []
        else:  # Succès
            self.consecutive_failures = 0  # Reset du compteur d'échecs
            
            # Mettre en cache (avec les numéros de ligne relatifs)
            cache_result = []
            for item in result:
                cache_item = item.copy()
                cache_item['row'] -= chunk_offset  
                cache_result.append(cache_item)
            self.cache.set(chunk_rows, cache_result)
            
            return result
    
    def detect_lot_info(self, file_path: str, filename: str) -> Optional[Tuple[str, str]]:
        """
        Utilise Gemini pour détecter les informations de lot depuis le fichier Excel
        
        Args:
            file_path: Chemin vers le fichier Excel
            filename: Nom du fichier (pour contexte)
            
        Returns:
            Tuple (numero_lot, nom_lot) ou None si non détecté
        """
        try:
            print(f"🧠 Détection du lot avec Gemini depuis {filename}")
            
            # Lire les premières lignes du fichier pour l'analyse
            df = pd.read_excel(file_path, nrows=20)  # Les 20 premières lignes suffisent
            
            # Convertir les données en texte pour Gemini
            content_lines = []
            content_lines.append(f"NOM DU FICHIER: {filename}")
            content_lines.append("")
            
            # Ajouter le contenu des premières cellules
            for i in range(min(15, len(df))):
                row_data = []
                for j in range(min(10, len(df.columns))):  # Premières 10 colonnes
                    cell_value = df.iloc[i, j]
                    if pd.notna(cell_value):
                        row_data.append(str(cell_value).strip())
                    else:
                        row_data.append("")
                
                if any(cell for cell in row_data):  # Ne pas inclure les lignes vides
                    content_lines.append(f"Ligne {i}: " + " | ".join(row_data))
            
            content_text = "\n".join(content_lines)
            
            # Prompt pour Gemini
            prompt = f"""
Analyse ce document DPGF/BPU/DQE et identifie les informations de lot.

CONTENU DU DOCUMENT:
{content_text}

TÂCHE:
1. Identifie le numéro de lot (généralement entre 1 et 99)
2. Identifie le nom/description du lot

EXEMPLES DE FORMATS POSSIBLES:
- "LOT 06 - MÉTALLERIE SERRURERIE"
- "Lot 4 - Charpente & Ossature bois"
- "DPGF Lot 10 - Platrerie"
- Ou simplement dans le nom de fichier

RÉPONSE REQUISE:
Si tu identifies un lot, réponds EXACTEMENT au format:
LOT_FOUND:numéro|description

Si aucun lot n'est identifié clairement, réponds:
NO_LOT_FOUND

Exemples de réponses valides:
LOT_FOUND:06|MÉTALLERIE SERRURERIE
LOT_FOUND:4|Charpente & Ossature bois
NO_LOT_FOUND
"""

            # Appel à Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            print(f"   Réponse Gemini: {response_text}")
            
            # Parser la réponse
            if response_text.startswith("LOT_FOUND:"):
                lot_info = response_text.replace("LOT_FOUND:", "").strip()
                if "|" in lot_info:
                    parts = lot_info.split("|", 1)
                    numero_lot = parts[0].strip()
                    nom_lot = parts[1].strip()
                    
                    # Validation du numéro de lot
                    try:
                        int_lot = int(numero_lot)
                        if 1 <= int_lot <= 99:
                            print(f"✅ Lot détecté par Gemini: {numero_lot} - {nom_lot}")
                            return (numero_lot, nom_lot)
                    except ValueError:
                        pass
            
            print("⚠️ Gemini n'a pas pu identifier un lot valide")
            return None
            
        except Exception as e:
            print(f"❌ Erreur lors de la détection du lot avec Gemini: {e}")
            return None
    
    def _call_gemini_api(self, chunk_rows: List[str], chunk_offset: int) -> List[Dict]:
        """Appel direct à l'API Gemini avec détection d'erreurs améliorée"""
        data_text = "\n".join(chunk_rows)
        
        prompt = f"""
        Analyse ce chunk de fichier Excel DPGF ligne par ligne.
        
        Classifie chaque ligne comme :
        - "section" : Titre de section (ex: "2.9 FERRURES", "LOT 06")
        - "element" : Élément d'ouvrage avec prix/quantité 
        - "ignore" : Ligne vide, en-tête, non pertinente
        
        Pour les SECTIONS, extrais :
        - numero_section, titre_section, niveau_hierarchique
        
        Pour les ELEMENTS, extrais :
        - designation_exacte (OBLIGATOIRE - même si vide mettre "Description manquante")
        - unite, quantite, prix_unitaire_ht, prix_total_ht
        
        Données :
        {data_text}
        
        Réponds en JSON : [{{"row": N, "type": "section|element|ignore", "data": {{...}}}}]
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Nettoyer le JSON
            if response_text.startswith('```json'):
                response_text = response_text.split('```json')[1].split('```')[0]
            elif response_text.startswith('```'):
                response_text = response_text.split('```')[1]
            
            result = json.loads(response_text.strip())
            print(f"Gemini a classifié {len(result)} lignes du chunk")
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Détecter les erreurs spécifiques d'API
            if any(keyword in error_msg for keyword in ['429', 'quota', 'rate limit', 'too many requests']):
                print(f"❌ Quota Gemini dépassé: {e}")
            elif any(keyword in error_msg for keyword in ['401', 'unauthorized', 'api key']):
                print(f"❌ Erreur d'authentification Gemini: {e}")
            elif any(keyword in error_msg for keyword in ['500', 'internal', 'server']):
                print(f"❌ Erreur serveur Gemini: {e}")
            else:
                print(f"❌ Erreur Gemini pour chunk: {e}")
            
            # Retourner None pour indiquer une erreur d'API (différent de [])
            return None


class DPGFImporter:
    """Importeur complet de DPGF avec détection intelligente des colonnes"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", gemini_key: Optional[str] = None, 
                 use_gemini: bool = False, chunk_size: int = 20, debug: bool = False, dry_run: bool = False):
        self.base_url = base_url
        self.stats = ImportStats()
        self.gemini_key = gemini_key
        self.use_gemini = use_gemini and gemini_key and GEMINI_AVAILABLE
        self.chunk_size = chunk_size
        self.debug = debug
        self.dry_run = dry_run
        
        # Initialiser les nouveaux composants
        self.column_mapper = ColumnMapping()
        self.error_reporter = ErrorReporter()
        
        # Initialiser le processeur Gemini si demandé
        self.gemini = None
        if self.use_gemini:
            try:
                self.gemini = GeminiProcessor(api_key=gemini_key, chunk_size=chunk_size)
                print(f"✅ Mode IA activé: classification avec Gemini (chunks de {chunk_size} lignes)")
            except Exception as e:
                print(f"❌ Erreur initialisation Gemini: {e}")
                self.use_gemini = False
    
    def get_or_create_client(self, client_name: str) -> int:
        """Récupère ou crée un client dans l'API"""
        if not client_name:
            raise ValueError("Nom de client requis")
        
        # 1. Essayer de trouver le client existant
        try:
            response = requests.get(f"{self.base_url}/api/v1/clients")
            response.raise_for_status()
            
            clients = response.json()
            for client in clients:
                if client.get('nom_client', '').upper() == client_name.upper():
                    print(f"✅ Client existant trouvé: {client_name} (ID: {client['id_client']})")
                    return client['id_client']
        
        except Exception as e:
            print(f"Erreur lors de la recherche de clients: {e}")
        
        # 2. Créer le client s'il n'existe pas
        try:            
            # Utiliser 'nom_client' comme attendu par le schéma ClientCreate
            client_payload = {
                'nom_client': client_name,
            }
            
            response = requests.post(f"{self.base_url}/api/v1/clients", json=client_payload)
            response.raise_for_status()
            
            client_id = response.json()['id_client']
            print(f"✅ Nouveau client créé: {client_name} (ID: {client_id})")
            return client_id
            
        except Exception as e:
            print(f"❌ Erreur création client {client_name}: {e}")
           
            raise
            
    def get_or_create_dpgf(self, client_id: int, nom_projet: str, file_path: str) -> int:
        """Récupère ou crée un DPGF pour le client"""
        fichier_source = Path(file_path).name
        
        # 1. Chercher DPGF existant UNIQUEMENT par fichier source exact
        try:
            response = requests.get(f"{self.base_url}/api/v1/dpgf", params={'id_client': client_id})
            response.raise_for_status()
            
            dpgfs = response.json()
            # Recherche UNIQUEMENT par fichier source pour éviter les confusions
            for dpgf in dpgfs:
                if dpgf.get('fichier_source') == fichier_source:
                    print(f"✅ DPGF existant trouvé (fichier source identique): {dpgf['nom_projet']} (ID: {dpgf['id_dpgf']})")
                    return dpgf['id_dpgf']
                    
            print(f"🆕 Aucun DPGF existant trouvé pour le fichier {fichier_source}. Création d'un nouveau DPGF.")
        
        except Exception as e:
            print(f"Erreur lors de la recherche de DPGF: {e}")
        
        # 2. Créer nouveau DPGF (toujours créer un nouveau pour chaque fichier unique)
        try:
            # S'assurer que le nom du projet est unique en ajoutant le nom du fichier
            if fichier_source not in nom_projet:
                nom_projet_unique = f"{nom_projet} - {fichier_source}"
            else:
                nom_projet_unique = nom_projet
                
            # Adapter le payload au schéma DPGFCreate attendu
            dpgf_payload = {
                'id_client': client_id,
                'nom_projet': nom_projet_unique,
                'date_dpgf': date.today().isoformat(),
                'statut_offre': 'en_cours',
                'fichier_source': fichier_source
            }
            
            response = requests.post(f"{self.base_url}/api/v1/dpgf", json=dpgf_payload)
            response.raise_for_status()
            
            dpgf_id = response.json()['id_dpgf']
            print(f"✅ Nouveau DPGF créé: {nom_projet} (ID: {dpgf_id})")
            return dpgf_id
            
        except Exception as e:
            print(f"❌ Erreur création DPGF {nom_projet}: {e}")
            raise
    
    def get_or_create_lot(self, dpgf_id: int, numero_lot: str, nom_lot: str) -> int:
        """Récupère ou crée un lot dans l'API"""
        # 1. Vérifier si le lot existe déjà
        try:
            response = requests.get(f"{self.base_url}/api/v1/lots", params={'id_dpgf': dpgf_id})
            response.raise_for_status()
            
            lots = response.json()
            for lot in lots:
                if lot.get('numero_lot') == numero_lot:
                    print(f"🔄 Lot existant réutilisé: {numero_lot} - {lot.get('nom_lot')}")
                    self.stats.lots_reused += 1
                    return lot['id_lot']
        
        except Exception as e:
            print(f"Erreur lors de la recherche de lots: {e}")
        
        # 2. Créer le lot s'il n'existe pas
        try:
            lot_payload = {
                'id_dpgf': dpgf_id,
                'numero_lot': numero_lot,
                'nom_lot': nom_lot
            }
            
            response = requests.post(f"{self.base_url}/api/v1/lots", json=lot_payload)
            response.raise_for_status()
            
            lot_id = response.json()['id_lot']
            print(f"✅ Nouveau lot créé: {numero_lot} - {nom_lot} (ID: {lot_id})")
            self.stats.lots_created += 1
            return lot_id
            
        except Exception as e:
            print(f"❌ Erreur création lot {numero_lot}: {e}")
            raise
    
    def create_section(self, lot_id: int, section_data: Dict) -> int:
        """Crée une section unique ou la récupère si elle existe déjà"""
        numero = section_data.get('numero_section', '')
        niveau_hierarchique = section_data.get('niveau_hierarchique', 1)
        
        # Mode dry-run: ne fait que simuler
        if self.dry_run:
            print(f"[DRY-RUN] Section: {numero} - {section_data.get('titre_section', '')}")
            return -1  # ID fictif pour le dry-run
        
        # 1. Vérifier si une section avec ce numéro existe déjà dans ce lot
        try:
            response = requests.get(f"{self.base_url}/api/v1/sections", params={'lot_id': lot_id})
            response.raise_for_status()
            
            sections = response.json()
            for section in sections:
                if section.get('numero_section') == numero:
                    print(f"🔄 Section existante réutilisée: {numero} - {section.get('titre_section')}")
                    self.stats.sections_reused += 1
                    return section['id_section']
        except Exception as e:
            print(f"Erreur lors de la recherche de section existante: {e}")
        
        # 2. Créer la section si elle n'existe pas
        payload = {
            'id_lot': lot_id,
            'section_parent_id': None,
            'numero_section': numero,
            'titre_section': section_data.get('titre_section', ''),
            'niveau_hierarchique': niveau_hierarchique
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/v1/sections", json=payload)
            response.raise_for_status()
            section_id = response.json()['id_section']
            print(f"➕ Nouvelle section créée: {numero} - {section_data.get('titre_section')}")
            self.stats.sections_created += 1
            return section_id
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 500:
                error_details = e.response.text
                print(f"Erreur 500 détaillée pour la section: {error_details}")
            self.stats.errors += 1
            raise
    
    def create_element(self, section_id: int, element_data: Dict, row_number: int = 0):
        """Crée un élément d'ouvrage avec gestion d'erreur améliorée"""
        filename = Path(self.file_path).name if hasattr(self, 'file_path') else "inconnu"
        
        # Mode dry-run: ne fait que simuler
        if self.dry_run:
            print(f"[DRY-RUN] Élément: {element_data.get('designation_exacte', 'N/A')}")
            return {"id_element": -1}  # ID fictif
        
        # Afficher les valeurs en mode debug pour diagnostiquer les problèmes
        if self.debug:
            print(f"DEBUG - Données élément: {element_data}")
        
        # Nettoyage des données avec gestion des valeurs nulles
        def safe_float(value, default=0.0):
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        # Nettoyer et afficher les valeurs numériques pour debug
        quantite = safe_float(element_data.get('quantite'))
        prix_unitaire = safe_float(element_data.get('prix_unitaire_ht'))
        prix_total = safe_float(element_data.get('prix_total_ht'))
        
        if self.debug:
            print(f"DEBUG - Valeurs numériques converties: quantité={quantite}, PU={prix_unitaire}, PT={prix_total}")
        
        cleaned_data = {
            'id_section': section_id,
            'designation_exacte': element_data.get('designation_exacte', 'Description manquante'),
            'unite': str(element_data.get('unite', ''))[:10],
            'quantite': quantite,
            'prix_unitaire_ht': prix_unitaire,
            'prix_total_ht': prix_total,
            'offre_acceptee': False
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/v1/element_ouvrages", json=cleaned_data)
            response.raise_for_status()
            self.stats.elements_created += 1
            return response.json()
        except requests.exceptions.HTTPError as e:
            self.stats.errors += 1
            error_msg = f"Erreur API HTTP {e.response.status_code}: {e.response.text if e.response else str(e)}"
            
            # Ajouter l'erreur au rapport
            self.error_reporter.add_error(
                filename=filename,
                line_number=row_number,
                error_type="API_ERROR",
                error_message=error_msg,
                raw_data=str(element_data)
            )
            
            print(f"❌ Erreur création élément ligne {row_number}: {error_msg}")
            if e.response and e.response.status_code == 500:
                error_details = e.response.text
                print(f"Erreur 500 détaillée: {error_details}")
            raise
        except Exception as e:
            self.stats.errors += 1
            error_msg = f"Erreur inattendue: {str(e)}"
            
            # Ajouter l'erreur au rapport
            self.error_reporter.add_error(
                filename=filename,
                line_number=row_number,
                error_type="PROCESSING_ERROR",
                error_message=error_msg,
                raw_data=str(element_data)
            )
            
            print(f"❌ Erreur inattendue ligne {row_number}: {error_msg}")
            raise    
            
    def classify_with_gemini(self, description: str) -> str:
        """
        Classifie une description d'élément d'ouvrage en utilisant l'API Google Gemini.
        
        Args:
            description: Description de l'élément à classifier
        
        Returns:
            Résultat de la classification (texte)
        """
        if not GEMINI_AVAILABLE:
            raise RuntimeError("API Google Gemini non disponible")
        
        try:
            # Appel à l'API Gemini pour la classification en utilisant GenerativeModel
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Classifie l'élément de construction suivant dans une catégorie appropriée (max 3 mots): {description}"
            
            response = model.generate_content(prompt, 
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=60,
                    top_p=0.95,
                    top_k=40
                )
            )
            
            # Extraire et retourner le résultat
            if response and hasattr(response, 'text'):
                result = response.text.strip()
                print(f"🔍 Classification Gemini: {result}")
                return result
            
            return "Classification inconnue"
        
        except Exception as e:
            print(f"❌ Erreur classification Gemini: {e}")
            return "Erreur classification"
            
    def import_file(self, file_path: str, dpgf_id: Optional[int] = None, lot_num: Optional[str] = None, original_filename: Optional[str] = None):
        """Import complet d'un fichier DPGF Excel avec mapping interactif et rapport d'erreurs"""
        self.file_path = file_path  # Pour les rapports d'erreur
        filename = Path(file_path).name
        
        print(f"\n📁 Import DPGF: {file_path}")
        print(f"Mode traitement: {'Gemini AI' if self.use_gemini else 'Analyse classique'}")
        print(f"Mode debug: {'Activé' if self.debug else 'Désactivé'}")
        print(f"Mode dry-run: {'Activé' if self.dry_run else 'Désactivé'}")
        
        try:
            # Initialiser le parser avec les nouveaux composants
            parser = ExcelParser(file_path, self.column_mapper, self.error_reporter, self.dry_run, 
                               self.gemini if hasattr(self, 'gemini') else None)
            client_detector = ClientDetector()
            
            # 1. Détecter le client si nécessaire
            # Utiliser le nom original du fichier pour la détection si fourni
            filename_for_detection = original_filename if original_filename else file_path
            client_name = client_detector.detect_client(filename_for_detection)
            if not client_name:
                client_name = "Client par défaut"
                print(f"⚠️ Utilisation d'un nom de client par défaut: {client_name}")
            
            if not self.dry_run:
                client_id = self.get_or_create_client(client_name)
            else:
                client_id = -1  # ID fictif pour dry-run
                print(f"[DRY-RUN] Client: {client_name}")
            
            # 2. Obtenir ou créer le DPGF
            if not dpgf_id:
                project_name = parser.detect_project_name(client_name)
                if not self.dry_run:
                    dpgf_id = self.get_or_create_dpgf(client_id, project_name, file_path)
                else:
                    dpgf_id = -1  # ID fictif pour dry-run
                    print(f"[DRY-RUN] DPGF: {project_name}")
            
            # 3. Détecter ou utiliser le lot spécifié
            if lot_num:
                # Utiliser un nom générique pour le lot spécifié
                parser.logger.info(f"Utilisation du lot spécifié en paramètre: {lot_num}")
                if not self.dry_run:
                    lot_id = self.get_or_create_lot(dpgf_id, lot_num, f"Lot {lot_num}")
                    parser.logger.log_lot_creation(lot_num, f"Lot {lot_num}", "parameter")
                else:
                    lot_id = -1  # ID fictif pour dry-run
                    print(f"[DRY-RUN] Lot: {lot_num} - Lot {lot_num}")
            else:
                # Rechercher dans le fichier
                lots = parser.find_lot_headers()
                if not lots:
                    parser.logger.warning("AUCUN LOT TROUVÉ - Création d'un lot par défaut pour éviter la perte de données")
                    if not self.dry_run:
                        # Créer un lot par défaut au lieu d'échouer
                        default_lot_num = "00"
                        default_lot_name = f"Lot par défaut - {Path(file_path).stem}"
                        lot_id = self.get_or_create_lot(dpgf_id, default_lot_num, default_lot_name)
                        parser.logger.log_lot_creation(default_lot_num, default_lot_name, "fallback", True)
                        print(f"⚠️ Aucun lot trouvé, création d'un lot par défaut: {default_lot_num} - {default_lot_name}")
                        lot_num, lot_name = default_lot_num, default_lot_name
                    else:
                        print("[DRY-RUN] Aucun lot trouvé, création d'un lot par défaut")
                        lot_id = -1
                        lot_num, lot_name = "00", "Lot par défaut"
                else:
                    # Utiliser le premier lot trouvé
                    lot_num, lot_name = lots[0]
                    parser.logger.info(f"Utilisation du lot détecté: {lot_num} - {lot_name}")
                    if not self.dry_run:
                        lot_id = self.get_or_create_lot(dpgf_id, lot_num, lot_name)
                        parser.logger.log_lot_creation(lot_num, lot_name, "detection")
                    else:
                        lot_id = -1
                        print(f"[DRY-RUN] Lot: {lot_num} - {lot_name}")
            
            # 4. Extraire les sections et éléments
            items = []
            gemini_fallback_triggered = False
            
            if self.use_gemini:
                # Utiliser Gemini pour la classification avancée
                print(f"🧠 Traitement avec Gemini (mode IA avancé)")
                
                chunks_processed = 0
                for chunk_num, df_chunk in enumerate(self.gemini.read_excel_chunks(file_path)):
                    print(f"\nTraitement chunk {chunk_num + 1} (lignes {chunk_num*self.chunk_size}-{chunk_num*self.chunk_size + len(df_chunk)})")
                    classified_rows = self.gemini.classify_chunk(df_chunk, chunk_num*self.chunk_size)
                    items.extend(classified_rows)
                    chunks_processed += 1
                    
                    # Si Gemini a échoué, on va basculer vers la méthode classique
                    if self.gemini.gemini_failed:
                        print(f"🔄 FALLBACK AUTOMATIQUE: Basculement vers la méthode classique")
                        gemini_fallback_triggered = True
                        break
                
                # Mettre à jour les statistiques depuis Gemini
                self.stats.cache_hits = self.gemini.stats.cache_hits
                self.stats.gemini_calls = self.gemini.stats.gemini_calls
                
                # Vérifier si Gemini n'a pas produit de résultats du tout
                if not items and chunks_processed > 0:
                    print(f"⚠️ Gemini n'a produit aucun résultat - activation du fallback")
                    gemini_fallback_triggered = True
            
            # Si Gemini a échoué ou n'est pas utilisé, utiliser la méthode classique
            if not self.use_gemini or gemini_fallback_triggered:
                if gemini_fallback_triggered:
                    print(f"🔧 FALLBACK: Analyse classique après échec de Gemini")
                else:
                    print(f"📋 Analyse classique (détection automatique des colonnes)")
                
                # Utiliser l'analyse classique avec détection automatique des colonnes
                header_row = parser.find_header_row()
                
                if header_row is None:
                    print("⚠️ Impossible de trouver les en-têtes du tableau DPGF")
                
                # Détecter les colonnes
                col_indices = parser.detect_column_indices(header_row)
                
                # En mode debug, on affiche les premières lignes du fichier pour aider au diagnostic
                if self.debug:
                    print("\nDEBUG - Aperçu des 15 premières lignes:")
                    for i in range(min(15, len(parser.df))):
                        row_values = [str(val) if pd.notna(val) else "" for val in parser.df.iloc[i].values]
                        print(f"Ligne {i}: {row_values}")
                    
                    if header_row is not None:
                        print(f"\nDEBUG - Ligne d'en-tête (ligne {header_row}):")
                        header_values = [str(val) if pd.notna(val) else "" for val in parser.df.iloc[header_row].values]
                        print(f"Valeurs: {header_values}")
                
                # Utiliser la nouvelle méthode de détection des sections et éléments
                classic_items = parser.detect_sections_and_elements(header_row)
                
                # Si c'est un fallback, remplacer les items de Gemini par ceux de la méthode classique
                if gemini_fallback_triggered:
                    items = classic_items
                    self.stats.gemini_fallback_used = True
                    if self.gemini.gemini_failed:
                        self.stats.gemini_failure_reason = f"Gemini a échoué après {self.gemini.consecutive_failures} tentatives"
                    else:
                        self.stats.gemini_failure_reason = "Gemini n'a produit aucun résultat"
                    print(f"✅ Fallback terminé: {len(items)} items détectés par la méthode classique")
                else:
                    items = classic_items
                
                # Si on était en mode fallback, remplacer les items Gemini par les items classiques
                if gemini_fallback_triggered:
                    items = classic_items
                    print(f"✅ Fallback terminé: {len(items)} items détectés par la méthode classique")
                else:
                    items = classic_items
            
            # Debug: afficher tous les items avant filtrage
            if self.debug:
                print(f"\nDEBUG - Items détectés avant filtrage ({len(items)}):")
                for i, item in enumerate(items[:10]):  # Limiter à 10 pour éviter trop de logs
                    print(f"  {i}: {item}")
                if len(items) > 10:
                    print(f"  ... et {len(items) - 10} autres")
            
            # Filtrer les items ignorés
            items_before_filter = len(items)
            items = [item for item in items if item.get('type') != 'ignore']
            items_after_filter = len(items)
            
            print(f"🔍 {items_after_filter} items valides détectés sur {items_before_filter} total ({sum(1 for i in items if i.get('type') == 'section')} sections, {sum(1 for i in items if i.get('type') == 'element')} éléments)")
            
            # Debug: afficher les items finaux
            if self.debug and items:
                print(f"\nDEBUG - Items finaux ({len(items)}):")
                for i, item in enumerate(items[:5]):
                    print(f"  {i}: Ligne {item.get('row', '?')}, Type: {item.get('type', '?')}, Data: {str(item.get('data', {}))[:100]}...")
                if len(items) > 5:
                    print(f"  ... et {len(items) - 5} autres")
            elif self.debug:
                print("\nDEBUG - Aucun item final détecté !")
            
            # 5. Traiter les items
            current_section_id = None
            for item in tqdm(items, desc="Import"):
                self.stats.total_rows += 1
                
                if item['type'] == 'section':
                    try:
                        current_section_id = self.create_section(lot_id, item['data'])
                    except Exception as e:
                        print(f"❌ Erreur section ligne {item['row']}: {e}")
                        self.stats.errors += 1
                
                elif item['type'] == 'element' and current_section_id:
                    try:
                        # Classification avancée avec Gemini
                        if self.use_gemini:
                            description = item['data'].get('designation_exacte', '')
                            classification = self.classify_with_gemini(description)
                            item['data']['classification'] = classification
                        
                        self.create_element(current_section_id, item['data'], item['row'])
                    except Exception as e:
                        self.error_reporter.add_error(
                            filename=filename,
                            line_number=item['row'],
                            error_type="ELEMENT_PROCESSING_ERROR",
                            error_message=str(e),
                            raw_data=str(item['data'])
                        )
                        print(f"❌ Erreur élément ligne {item['row']}: {e}")
                        self.stats.errors += 1
            
            # 6. Afficher les warnings de mapping si nécessaire
            if parser.mapping_confidence == 'low':
                print(f"\n⚠️⚠️⚠️ ATTENTION: MAPPING DE COLONNES PEU FIABLE ⚠️⚠️⚠️")
                print(f"Le mapping automatique des colonnes pour ce fichier est incertain.")
                print(f"Vérifiez impérativement le rapport d'erreurs: {self.error_reporter.error_file}")
                print(f"Considérez utiliser le mapping manuel interactif à la prochaine exécution.")
            elif parser.mapping_confidence == 'medium':
                print(f"\n⚠️ Mapping automatique avec confiance moyenne.")
                print(f"Vérifiez le rapport d'erreurs si nécessaire: {self.error_reporter.error_file}")
            
            # 7. Sauvegarder le rapport d'erreurs
            self.error_reporter.save_report()
            
            # 8. Afficher les statistiques
            print(f"\n✅ Import terminé:")
            if self.dry_run:
                print(f"   [DRY-RUN] Mode simulation - aucune donnée insérée")
            
            # Afficher le mode utilisé
            if self.use_gemini and not gemini_fallback_triggered:
                print(f"   📊 Mode: Gemini IA (appels: {self.stats.gemini_calls}, cache: {self.stats.cache_hits})")
            elif gemini_fallback_triggered:
                print(f"   📊 Mode: Fallback Automatique (Gemini → Classique)")
                print(f"       Gemini: {self.stats.gemini_calls} appels avant échec")
            else:
                print(f"   📊 Mode: Analyse classique")
            
            print(f"   - Lots créés: {self.stats.lots_created}, réutilisés: {self.stats.lots_reused}")
            print(f"   - Sections créées: {self.stats.sections_created}, réutilisées: {self.stats.sections_reused}")
            print(f"   - Éléments créés: {self.stats.elements_created}")
            print(f"   - Erreurs: {self.stats.errors}")
            print(f"   - Confiance mapping: {parser.mapping_confidence}")
            
            if gemini_fallback_triggered:
                print(f"\n💡 INFO: Le fallback automatique a été activé car Gemini a rencontré des erreurs")
                print(f"    (quota dépassé, erreur d'API, etc.). Les données ont été traitées")
                print(f"    avec la méthode classique pour garantir un résultat complet.")
            
            if self.use_gemini:
                print(f"   - Appels Gemini: {self.stats.gemini_calls}")
                print(f"   - Cache hits: {self.stats.cache_hits}")
            
            return dpgf_id
            
        except Exception as e:
            # Ajouter l'erreur critique au rapport
            self.error_reporter.add_error(
                filename=filename,
                line_number=0,
                error_type="CRITICAL_ERROR",
                error_message=str(e),
                raw_data="Script failure"
            )
            self.error_reporter.save_report()
            
            print(f"❌ Erreur critique: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Point d'entrée du script"""
    parser = argparse.ArgumentParser(description="Import complet d'un fichier DPGF avec mapping interactif")
    parser.add_argument("--file", required=True, help="Chemin du fichier Excel DPGF")
    parser.add_argument("--original-filename", help="Nom original du fichier (si différent du nom du fichier local)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de l'API")
    parser.add_argument("--dpgf-id", type=int, help="ID du DPGF existant (optionnel)")
    parser.add_argument("--lot-num", help="Numéro du lot (optionnel)")
    parser.add_argument("--gemini-key", help="Clé API Google Gemini pour la classification avancée")
    parser.add_argument("--chunk-size", type=int, default=20, help="Taille des chunks pour l'analyse Gemini (défaut: 20)")
    parser.add_argument("--no-gemini", action="store_true", help="Désactiver l'utilisation de Gemini même si la clé est fournie")
    parser.add_argument("--debug", action="store_true", help="Activer le mode debug pour plus d'informations")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation: analyse et preview sans insertion en base")
    parser.add_argument("--log-dir", default="logs", help="Répertoire pour les logs détaillés (par défaut: 'logs')")
    parser.add_argument("--verbose-logs", action="store_true", help="Activer la journalisation détaillée pour le diagnostic d'erreurs")
    
    args = parser.parse_args()
    
    # Déterminer si on utilise Gemini
    use_gemini = args.gemini_key is not None and not args.no_gemini
    
    importer = DPGFImporter(
        base_url=args.base_url,
        gemini_key=args.gemini_key,
        use_gemini=use_gemini,
        chunk_size=args.chunk_size,
        debug=args.debug,
        dry_run=args.dry_run
    )
    
    # Utiliser le nom original pour la détection si fourni
    file_path_for_detection = args.original_filename if args.original_filename else args.file
    
    importer.import_file(
        file_path=args.file,
        dpgf_id=args.dpgf_id,
        lot_num=args.lot_num,
        original_filename=file_path_for_detection
    )


if __name__ == "__main__":
    main()
