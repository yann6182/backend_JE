"""
Service d'importation de DPGF
Intègre la logique du script d'import directement dans l'API
"""

import os
import re
import hashlib
import pickle
import json
from typing import Optional, Dict, List, Tuple, Any
from datetime import date
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
import requests

# Import conditionnel de l'API Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Module google.generativeai non disponible. L'analyse avancée par IA ne sera pas utilisée.")

# Import modèles et schemas
from app.db.models.dpgf import DPGF, StatutOffre
from app.db.models.lot import Lot
from app.db.models.section import Section
from app.db.models.element_ouvrage import ElementOuvrage
from app.crud import client as client_crud
from app.crud import dpgf as dpgf_crud
from app.crud import lot as lot_crud
from app.crud import section as section_crud
from app.crud import element_ouvrage as element_crud
from app.schemas.client import ClientCreate
from app.schemas.dpgf import DPGFCreate
from app.schemas.lot import LotCreate
from app.schemas.section import SectionCreate
from app.schemas.element_ouvrage import ElementOuvrageCreate


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


class GeminiCache:
    """Cache pour les résultats de classification Gemini"""
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            self.cache_dir = Path("cache")
            self.cache_dir.mkdir(exist_ok=True)
        else:
            self.cache_dir = cache_dir
        
        self.cache_file = self.cache_dir / "gemini_patterns.pkl"
        self.patterns = self._load_cache()
    
    def _load_cache(self):
        """Charge le cache depuis le disque"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Erreur lors du chargement du cache: {e}")
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


class GeminiProcessor:
    """Traitement des données avec l'API Gemini"""
    
    def __init__(self, api_key: str, chunk_size: int = 20):
        if not GEMINI_AVAILABLE:
            raise ImportError("Module google.generativeai non disponible. L'analyse avancée par IA ne peut pas être utilisée.")
        
        self.api_key = api_key
        self.chunk_size = chunk_size
        self.cache = GeminiCache()
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.stats = ImportStats()
    
    def classify_descriptions(self, descriptions: List[str]) -> List[Dict]:
        """
        Classifie une liste de descriptions d'éléments d'ouvrage
        
        Args:
            descriptions: Liste de textes à classifier
        
        Returns:
            Liste de dictionnaires de classification
        """
        # Vérifier si déjà dans le cache
        cached_result = self.cache.get(descriptions)
        if cached_result:
            self.stats.cache_hits += 1
            return cached_result
            
        self.stats.gemini_calls += 1
        
        prompt = f"""
        Tu es un expert en classification de travaux du bâtiment. 
        Je vais te donner une liste d'éléments d'ouvrage du BTP, et tu dois les classifier selon:
        
        1. MÉTIER (ex: Maçonnerie, Plomberie, Électricité, etc.)
        2. TYPE D'ÉLÉMENT (ex: Fondation, Mur, Plancher, Toiture, Porte, etc.)
        3. MATÉRIAU PRINCIPAL (ex: Béton, Bois, Acier, PVC, etc.)
        
        Voici les éléments à classifier:
        {descriptions}
        
        Réponds UNIQUEMENT avec un JSON structuré comme:
        [
            {{
                "description": "Texte original de l'élément",
                "metier": "Métier principal",
                "type": "Type d'élément",
                "materiau": "Matériau principal"
            }},
            ...
        ]
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Nettoyer le JSON
            if response_text.startswith('```json'):
                response_text = response_text.split('```json')[1].split('```')[0]
            elif response_text.startswith('```'):
                response_text = response_text.split('```')[1].split('```')[0]
            
            result = json.loads(response_text.strip())
            print(f"Gemini a classifié {len(result)} lignes")
            
            # Mettre en cache
            self.cache.set(descriptions, result)
            
            return result
            
        except Exception as e:
            print(f"Erreur Gemini: {e}")
            return []


class ExcelParser:
    """Analyse les fichiers Excel DPGF avec détection de colonnes améliorée"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df = pd.read_excel(file_path, engine='openpyxl', header=None)
        # Colonnes détectées (indices)
        self.col_designation = None
        self.col_unite = None
        self.col_quantite = None
        self.col_prix_unitaire = None
        self.col_prix_total = None
        self.headers_detected = False
    
    def find_lot_headers(self) -> List[Tuple[str, str]]:
        """
        Recherche les intitulés de lot dans le fichier Excel.
        Version améliorée avec plus de patterns et détection dans le nom du fichier.
        
        Returns:
            Liste de tuples (numero_lot, nom_lot)
        """
        lots = []
        
        # Patterns pour détecter les lots dans le contenu du fichier
        lot_patterns = [
            re.compile(r'lot\s+n?[°\.]?\s*([^\s\-–]+)\s*[\-–:]\s*(.+)', re.IGNORECASE),  # LOT N°06 - MÉTALLERIE
            re.compile(r'lot\s+n?[°\.]?\s*([^\s\-–]+)[\s\-–:]*$', re.IGNORECASE),  # LOT 06 (sans titre)
            re.compile(r'^([0-9]{1,2})[\.]\s+([A-Z].+)$'),  # 6. MÉTALLERIE
        ]
        
        # Parcourir les 20 premières lignes
        for i in range(min(20, len(self.df))):
            for col in range(min(10, len(self.df.columns))):
                if col < len(self.df.columns) and pd.notna(self.df.iloc[i, col]):
                    cell_text = str(self.df.iloc[i, col]).strip()
                    for pattern in lot_patterns:
                        match = pattern.search(cell_text)
                        if match:
                            numero_lot = match.group(1).strip()
                            nom_lot = match.group(2).strip() if len(match.groups()) > 1 else f"Lot {numero_lot}"
                            lots.append((numero_lot, nom_lot))
        
        # Si aucun lot trouvé dans le contenu, essayer depuis le nom de fichier
        if not lots:
            filename_lot = self.extract_lot_fromFilename()
            if filename_lot:
                lots.append(filename_lot)
        
        # Nettoyer et dédupliquer les lots
        cleaned_lots = []
        seen_nums = set()
        
        for lot_num, lot_name in lots:
            # Nettoyer le numéro (garder seulement les chiffres et points)
            clean_num = re.sub(r'[^\d\.]', '', lot_num)
            if not clean_num:
                clean_num = lot_num  # Si rien ne reste, garder l'original
            
            if clean_num not in seen_nums:
                seen_nums.add(clean_num)
                cleaned_lots.append((clean_num, lot_name))
        
        return cleaned_lots
    
    def extract_lot_from_filename(self) -> Optional[Tuple[str, str]]:
        """
        Extrait le numéro et nom du lot depuis le nom du fichier.
        
        Returns:
            Tuple (numero_lot, nom_lot) ou None si non trouvé
        """
        filename = Path(self.file_path).stem
        
        # Patterns pour détecter un lot dans le nom de fichier
        patterns = [
            # LOT 06 - DPGF - METALLERIE
            r'lot\s*(\d+)\s*-\s*(?:dpgf|devis)\s*-\s*([\w\s-]+)',
            # LOT 06 - METALLERIE
            r'lot\s*(\d+)\s*-\s*([\w\s-]+)',
            # DPGF Lot 6 - Métallerie
            r'dpgf\s*lot\s*(\d+)\s*-\s*([\w\s-]+)',
            # Lot06-Métallerie
            r'lot\s*(\d+)[_\-\s]+([\w\s-]+)',
            # Lot6
            r'lot\s*(\d+)',
            # 06 Métallerie
            r'(\d{1,2})\s+([\w\s-]+)',
        ]
        
        # Essayer chaque pattern
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                numero_lot = match.group(1).strip()
                nom_lot = ""
                if len(match.groups()) > 1 and match.group(2):
                    nom_lot = match.group(2).strip()
                else:
                    nom_lot = f"Lot {numero_lot}"
                return (numero_lot, nom_lot)
        
        # Si on n'a pas trouvé, retourner un lot par défaut basé sur le nom du fichier
        if re.search(r'\bdpgf\b', filename, re.IGNORECASE):
            return ("1", f"Lot issu de {filename}")
        
        return None
    
    def find_client_name(self) -> str:
        """
        Détecte le nom du client dans le DPGF.
        
        Returns:
            Nom du client ou chaîne vide si non détecté
        """
        # Patterns typiques pour le nom du client
        client_patterns = [
            r'client\s*:\s*([^,;:]+)',
            r"maître\s*d[\'\"]ouvrage\s*:\s*([^,;:]+)",
            r'mo\s*:\s*([^,;:]+)',
        ]
        
        # Examiner les 15 premières lignes
        for i in range(min(15, len(self.df))):
            for col in range(min(5, len(self.df.columns))):  # Limiter aux 5 premières colonnes
                if pd.notna(self.df.iloc[i, col]):
                    cell_text = str(self.df.iloc[i, col]).lower()
                    for pattern in client_patterns:
                        match = re.search(pattern, cell_text, re.IGNORECASE)
                        if match:
                            client_name = match.group(1).strip()
                            print(f"✓ Client détecté: {client_name}")
                            return client_name
        
        # Si pas trouvé, essayer de déduire du nom de fichier
        filename = Path(self.file_path).stem
        
        # Si le nom contient une suite de chiffres qui pourrait être une référence client
        client_ref_match = re.search(r'(\d{5,})', filename)
        if client_ref_match:
            ref = client_ref_match.group(1)
            client_name = f"Client Réf. {ref}"
            print(f"? Client déduit depuis la référence: {client_name}")
            return client_name
        
        # Nom par défaut basé sur le nom du fichier
        default_name = f"Client du {Path(self.file_path).stem}"
        print(f"⚠️ Client non détecté, utilisation du nom par défaut: {default_name}")
        return default_name
    
    def find_header_row(self) -> Optional[int]:
        """
        Trouve la ligne d'en-tête avec désignation, unité, quantité, prix unitaire, prix total.
        Approche améliorée avec recherche de patterns.
        
        Returns:
            Indice de la ligne d'en-tête ou None si non trouvée
        """
        header_patterns = {
            'designation': [r'désignation', r'des(?:\.|ignat)', r'libellé', r'description', r'intitulé', r'détail des ouvrages'],
            'unite': [r'unité', r'u\.', r'un\.', r'un$', r'unité de mesure', r'mesure'],
            'quantite': [r'quantité', r'qté\.?', r'qt\.?', r'quant\.?', r'qte'],
            'prix_unitaire': [r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', r'pu(?:\s*h\.?t\.?)?'],
            'prix_total': [r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)']
        }
        
        best_row = None
        best_score = 0
        
        # Parcourir les 50 premières lignes pour chercher les en-têtes
        for i in range(min(50, len(self.df))):
            # Vérifier individuellement chaque cellule
            row_values = []
            for col_idx in range(min(15, len(self.df.columns))):  # Limiter aux 15 premières colonnes
                cell_value = ""
                if col_idx < len(self.df.columns) and pd.notna(self.df.iloc[i, col_idx]):
                    cell_value = str(self.df.iloc[i, col_idx]).strip().lower()
                row_values.append(cell_value)
            
            row_text = " ".join(row_values)
            
            # Compter le nombre de patterns correspondants dans cette ligne
            score = 0
            found_patterns = {k: False for k in header_patterns.keys()}
            found_columns = {}
            
            # Pour chaque colonne possible
            for col_name, patterns in header_patterns.items():
                # Pour chaque cellule de la ligne
                for col_idx, cell_text in enumerate(row_values):
                    for pattern in patterns:
                        if re.search(pattern, cell_text, re.IGNORECASE):
                            found_patterns[col_name] = True
                            found_columns[col_name] = col_idx
                            score += 1
                            break
                    if found_patterns[col_name]:
                        break
            
            # Si le score est meilleur que le précédent
            if score >= 3 and score > best_score:
                best_score = score
                best_row = i
                
                # Si on a trouvé 4 colonnes ou plus, c'est probablement la bonne ligne d'en-tête
                if score >= 4:
                    print(f"✓ Ligne d'en-tête trouvée (ligne {i+1}): {score}/5 patterns trouvés")
                    # Pré-configurer les indices de colonnes
                    self.col_designation = found_columns.get('designation')
                    self.col_unite = found_columns.get('unite')
                    self.col_quantite = found_columns.get('quantite')
                    self.col_prix_unitaire = found_columns.get('prix_unitaire')
                    self.col_prix_total = found_columns.get('prix_total')
                    self.headers_detected = True
                    return i
        
        # Si on a au moins une ligne avec un score de 3 ou plus
        if best_row is not None:
            print(f"✓ Ligne d'en-tête trouvée (ligne {best_row+1}): score {best_score}/5")
            return best_row
        
        print("⚠️ Aucune ligne d'en-tête trouvée, l'analyse utilisera les premiers éléments du fichier")
        return None
    
    def detect_column_indices(self, header_row_idx: Optional[int]) -> Dict[str, Optional[int]]:
        """
        Détermine l'indice des colonnes importantes en se basant sur l'en-tête
        
        Args:
            header_row_idx: Indice de la ligne d'en-tête
            
        Returns:
            Dictionnaire avec les indices des colonnes
        """
        # Initialiser les indices à None
        column_indices = {
            'designation': None,
            'unite': None,
            'quantite': None,
            'prix_unitaire': None,
            'prix_total': None
        }
        
        # Si on a une ligne d'en-tête, on cherche les patterns spécifiques
        if header_row_idx is not None:
            header_row = [str(val).strip().lower() if pd.notna(val) else "" for val in self.df.iloc[header_row_idx].values]
            
            # Définir les patterns pour chaque colonne
            col_patterns = {
                'designation': [r'désignation', r'des(?:\.|ignat)', r'libellé', r'description', r'intitulé'],
                'unite': [r'unité', r'u\.', r'un\.', r'un$', r'unité de mesure', r'mesure'],
                'quantite': [r'quantité', r'qté\.?', r'qt\.?', r'quant\.?', r'qte'],
                'prix_unitaire': [r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', r'pu(?:\s*h\.?t\.?)?'],
                'prix_total': [r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?']
            }
            
            # Pour chaque colonne, chercher le pattern correspondant
            for col_idx, cell_text in enumerate(header_row):
                for col_name, patterns in col_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, cell_text, re.IGNORECASE):
                            column_indices[col_name] = col_idx
                            break
        
        # Mettre à jour les attributs de la classe
        self.col_designation = column_indices['designation']
        self.col_unite = column_indices['unite']
        self.col_quantite = column_indices['quantite']
        self.col_prix_unitaire = column_indices['prix_unitaire']
        self.col_prix_total = column_indices['prix_total']
        self.headers_detected = True
        
        return column_indices
        
    def safe_convert_to_float(self, value) -> float:
        """
        Convertit une valeur en float de manière sécurisée (gestion des formats)
        
        Args:
            value: Valeur à convertir (peut être string, float, etc.)
            
        Returns:
            Valeur convertie en float
        """
        try:
            # Si c'est déjà un float ou un int, retourner directement
            if isinstance(value, (float, int)):
                return float(value)
            
            # Convertir en string et nettoyer
            val_str = str(value).strip()
            
            # Supprimer les symboles monétaires et autres caractères
            val_str = re.sub(r'[€$£\s]', '', val_str)
            
            # Remplacer les virgules par des points (format européen)
            if ',' in val_str and '.' not in val_str:
                val_str = val_str.replace(',', '.')
            
            # Traiter les cas comme "1.234,56" (format européen) -> "1234.56"            if '.' in val_str and ',' in val_str:
                if val_str.find('.') < val_str.find(','):
                    val_str = val_str.replace('.', '')
                    val_str = val_str.replace(',', '.')
            
            # Convertir en float
            return float(val_str)
        except (ValueError, TypeError):
            # Si la conversion échoue, on retourne 0            print(f"⚠️ Impossible de convertir en nombre: '{value}'")
            return 0.0
    
    def _try_to_detect_numeric_columns(self):
        """
        Essaie de détecter automatiquement les colonnes numériques qui n'ont pas été trouvées
        en utilisant des heuristiques sur les premières lignes du fichier.
        """
        print("Tentative de détection automatique des colonnes numériques...")
        numeric_cols = []
        
        # Parcourir les 50 premières lignes pour analyser les colonnes numériques
        for i in range(min(50, len(self.df))):
            for col in range(min(15, len(self.df.columns))):
                cell_value = self.df.iloc[i, col]
                if pd.notna(cell_value):
                    try:
                        # Si c'est un nombre ou peut être converti en nombre
                        float_value = self.safe_convert_to_float(cell_value)
                        if float_value > 0:
                            # On note cette colonne comme potentiellement numérique
                            numeric_cols.append(col)
                    except:
                        pass
        
        # Compter les occurrences de chaque colonne numérique
        col_counts = {}
        for col in numeric_cols:
            col_counts[col] = col_counts.get(col, 0) + 1
        
        # Trier les colonnes par fréquence d'apparition (décroissant)
        sorted_cols = sorted(col_counts.keys(), key=lambda x: col_counts[x], reverse=True)
        
        # Si on a trouvé au moins 3 colonnes numériques, on suppose que ce sont les colonnes
        # quantité, prix unitaire, prix total (dans cet ordre, en partant de la gauche)
        if len(sorted_cols) >= 3:
            sorted_cols = sorted(sorted_cols[:3])
            
            # Si colonne de quantité n'est pas détectée
            if self.col_quantite is None:
                self.col_quantite = sorted_cols[0]
                print(f"Détection auto: quantité = colonne {self.col_quantite}")
            
            # Si colonne de prix unitaire n'est pas détectée
            if self.col_prix_unitaire is None:
                self.col_prix_unitaire = sorted_cols[1]
                print(f"Détection auto: prix unitaire = colonne {self.col_prix_unitaire}")
            
            # Si colonne de prix total n'est pas détectée
            if self.col_prix_total is None:
                self.col_prix_total = sorted_cols[2]
                print(f"Détection auto: prix total = colonne {self.col_prix_total}")
        elif len(sorted_cols) >= 2:
            sorted_cols = sorted(sorted_cols[:2])
            
            # Avec 2 colonnes, on suppose qu'il s'agit de quantité et prix unitaire
            if self.col_quantite is None:
                self.col_quantite = sorted_cols[0]
                print(f"Détection auto: quantité = colonne {self.col_quantite}")
            
            if self.col_prix_unitaire is None:
                self.col_prix_unitaire = sorted_cols[1]
                print(f"Détection auto: prix unitaire = colonne {self.col_prix_unitaire}")    
                    
        elif len(sorted_cols) >= 1:
            # Avec 1 colonne, on suppose que c'est le prix total
            if self.col_prix_total is None:
                self.col_prix_total = sorted_cols[0]
                print(f"Détection auto: prix total = colonne {self.col_prix_total}")
    
    def detect_sections_and_elements(self, header_row: Optional[int] = None) -> List[Dict]:
        """
        Détecte les sections et éléments d'ouvrage à partir de la ligne d'en-tête.
        Cette version utilise la détection dynamique des colonnes.
        
        Args:
            header_row: Index de la ligne d'en-tête
            
        Returns:
            Liste de dictionnaires avec 'type' ('section' ou 'element') et 'data'
        """
        results = []
        
        # Trouver la ligne d'en-tête si non spécifiée
        if header_row is None:
            header_row = self.find_header_row()
        
        # Détecter les indices des colonnes
        if not self.headers_detected:
            self.detect_column_indices(header_row)
        
        # Si on n'a pas pu détecter les colonnes essentielles, on utilise des valeurs par défaut
        if self.col_designation is None:
            self.col_designation = 0
        
        # Utiliser des heuristiques pour essayer de détecter plus précisément les colonnes
        # Si on n'a pas trouvé toutes les colonnes, essayer de les déduire
        if self.col_quantite is None or self.col_prix_unitaire is None or self.col_prix_total is None:
            self._try_to_detect_numeric_columns()
        
        print(f"Colonnes utilisées: désignation={self.col_designation}, unité={self.col_unite}, "
              f"quantité={self.col_quantite}, prix unitaire={self.col_prix_unitaire}, prix total={self.col_prix_total}")
        
        section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+(.*)')
        title_pattern = re.compile(r'^([A-Z][A-Z\s\d\.]+)$')  # Pour les titres en majuscules sans numéro
        current_section = None
        
        # Si header_row est None (pas trouvé), commencer depuis le début
        start_row = header_row + 1 if header_row is not None else 0
        
        for i in range(start_row, len(self.df)):
            row = self.df.iloc[i]
            
            # Ignorer les lignes vides
            if all(pd.isna(val) for val in row.values):
                continue
            
            # Vérifier si c'est une section (texte en début de ligne avec numéro ou en majuscules)
            if pd.notna(row.iloc[self.col_designation]):
                cell_text = str(row.iloc[self.col_designation]).strip()
                
                # Essayer de détecter une section avec numéro (ex: "1.2 Section Title")
                match = section_pattern.match(cell_text)
                
                if match:
                    numero_section = match.group(1).strip()
                    titre_section = match.group(2).strip()
                    
                    # Calculer le niveau hiérarchique
                    niveau = numero_section.count('.') + 1
                    
                    # Stocker la section
                    current_section = {
                        'numero_section': numero_section,
                        'titre_section': titre_section,
                        'niveau_hierarchique': niveau
                    }
                    
                    results.append({
                        'type': 'section',
                        'data': current_section,
                        'row': i
                    })
                    continue
                
                # Deuxième test: est-ce un titre en majuscules sans numéro?
                if len(cell_text) > 3 and title_pattern.match(cell_text):
                    # C'est probablement un titre de section en majuscules
                    titre_section = cell_text
                    
                    # Générer un numéro pour cette section, mais qu'on puisse tracer à l'original
                    # (contrairement au hash du script original)
                    numero_section = titre_section  # Utiliser le titre comme numéro
                    
                    # Stocker la section
                    current_section = {
                        'numero_section': numero_section if len(numero_section) <= 50 else numero_section[:47] + "...",
                        'titre_section': titre_section,
                        'niveau_hierarchique': 1  # Section de premier niveau par défaut
                    }
                    
                    results.append({
                        'type': 'section',
                        'data': current_section,
                        'row': i
                    })
                    continue
                
                # Si on a une section active, et qu'il y a des données de prix et quantité, c'est un élément
                if current_section is not None or len(results) > 0:  # S'assurer qu'on a au moins une section existante
                    has_price_data = False
                    if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
                        has_price_data = True
                    elif self.col_prix_unitaire is not None and self.col_quantite is not None:
                        if (self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]) and 
                            self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite])):
                            has_price_data = True
                    
                    # Vérifier également si le texte ressemble à un élément sans prix
                    element_indicators = ['m2', 'm²', 'ml', 'u', 'ens', 'ensemble', 'unité', 'unite', 'forfait', 'ft']
                    has_unit_indicator = any(indicator in cell_text.lower() for indicator in element_indicators)
                    
                    if has_price_data or has_unit_indicator or len(cell_text) > 30:
                        # C'est un élément
                        designation = cell_text
                        
                        # Récupérer l'unité si disponible
                        unite = ""
                        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
                            unite = str(row.iloc[self.col_unite])
                        
                        # Récupérer quantité et prix avec conversion sécurisée
                        quantite = 0.0
                        if self.col_quantite is not None and self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite]):
                            quantite = self.safe_convert_to_float(row.iloc[self.col_quantite])
                        
                        prix_unitaire = 0.0
                        if self.col_prix_unitaire is not None and self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]):
                            prix_unitaire = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
                        
                        prix_total = 0.0
                        if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
                            prix_total = self.safe_convert_to_float(row.iloc[self.col_prix_total])
                        elif quantite > 0 and prix_unitaire > 0:
                            # Calculer le prix total si non disponible
                            prix_total = quantite * prix_unitaire
                        
                        # Si prix total est disponible mais pas prix unitaire ou quantité, essayer de calculer
                        if prix_total > 0:
                            if prix_unitaire == 0 and quantite > 0:
                                prix_unitaire = prix_total / quantite
                            elif quantite == 0 and prix_unitaire > 0:
                                quantite = prix_total / prix_unitaire
                        
                        results.append({
                            'type': 'element',
                            'data': {
                                'designation_exacte': designation,
                                'unite': unite[:10],  # Limiter à 10 caractères
                                'quantite': quantite,
                                'prix_unitaire_ht': prix_unitaire,
                                'prix_total_ht': prix_total,                            },
                            'row': i
                        })
        
        print(f"Total éléments/sections détectés: {len(results)}")
        return results


class ExcelParser:
    # ... (classe existante)
    
    def _has_numeric_data(self, row):
        """
        Vérifie si la ligne contient des données numériques (prix, quantité)
        Vérifie également si les colonnes de prix contiennent des valeurs significatives
        """
        # Prix total direct
        if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
            value = self.safe_convert_to_float(row.iloc[self.col_prix_total])
            if value > 0:  # Ne considérer que les prix > 0
                return True
        
        # Ou prix unitaire
        if self.col_prix_unitaire is not None and self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]):
            value = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
            if value > 0:  # Ne considérer que les prix > 0
                return True
        
        # Ou combinaison quantité + prix unitaire
        if self.col_prix_unitaire is not None and self.col_quantite is not None:
            if (self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]) and 
                self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite])):
                value_prix = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
                value_qte = self.safe_convert_to_float(row.iloc[self.col_quantite])
                if value_prix > 0 and value_qte > 0:  # Les deux doivent être > 0
                    return True
        
        # Vérifier si la colonne quantité contient une valeur significative
        if self.col_quantite is not None and self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite]):
            value = self.safe_convert_to_float(row.iloc[self.col_quantite])
            if value > 0:  # Ne considérer que les quantités > 0
                return True
        
        return False
    
    def _is_section_pattern(self, text: str) -> bool:
        """Vérifie si le texte correspond à un pattern de section"""
        # Patterns pour les sections (similaires au script de production)
        section_patterns = [
            r'^(\d+(?:\.\d+)*)\s+(.+)',  # Format numéroté (ex: "1.2 Section Title")
            r'^([A-Z][A-Z0-9\s\.\-\_]{3,})$',  # Titre en majuscules long
            r'^(CHAPITRE\s+[A-Z0-9]+|LOT\s+[A-Z0-9]+)[\s\:]+(.+)',  # Chapitre/Lot
            r'^(SOUS[\-\s]TOTAL|TOTAL)[\s\:]*(.*)',  # Totaux et sous-totaux
            r'^([A-Z]{3,}[\s\-]*)+$',  # Plusieurs mots en majuscules
        ]
        for pattern in section_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
        
    def _extract_section_data(self, text: str) -> Dict:
        """
        Extrait les données d'une section depuis le texte
        Sépare correctement numero_section et titre_section
        Suit strictement la logique du script de production
        """
        # Pattern principal : numéro + titre (format le plus courant: "2.1 Escaliers métalliques")
        num_title_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)', text.strip())
        if num_title_match:
            numero_section = num_title_match.group(1).strip()  # Ex: "2.1"
            titre_section = num_title_match.group(2).strip()   # Ex: "Escaliers métalliques"
        else:
            # Patterns spéciaux avec numérotation claire
            special_patterns = [
                # CHAPITRE 2: Menuiseries → numero="CHAPITRE 2", titre="Menuiseries"
                (r'^(CHAPITRE\s+[A-Z0-9]+)[\s\:]+(.+)', lambda m: (m.group(1), m.group(2))),
                # LOT 06 - MÉTALLERIE → numero="LOT 06", titre="MÉTALLERIE"
                (r'^(LOT\s+[A-Z0-9]+)[\s\:]+(.+)', lambda m: (m.group(1), m.group(2))),
                # SOUS-TOTAL Escaliers → numero="SOUS-TOTAL", titre="Escaliers"
                (r'^(SOUS[\-\s]TOTAL|TOTAL)[\s\:]*(.*)', lambda m: (m.group(1), m.group(2) if m.group(2) else m.group(1))),
            ]
            
            # Initialiser avec des valeurs par défaut
            numero_section = ""
            titre_section = text.strip()
            
            # Essayer les patterns spéciaux
            for pattern, extractor in special_patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    numero_section, titre_section = extractor(match)
                    break
              # Si aucun pattern spécial n'a été trouvé
            if not numero_section:
                # Pour les sections en majuscules comme "FERRURES"
                # On crée un numéro unique mais on garde le titre séparé
                if titre_section.isupper() or re.match(r'^[A-Z][A-Z0-9\.\s\-\_]{3,}$', titre_section):
                    numero_section = titre_section
                else:
                    # Utiliser un identifiant générique pour les autres cas
                    numero_section = f"SEC_{hash(titre_section) % 10000}"
        
        # Limiter la taille du numéro de section à 50 caractères max (contrainte de la base de données)
        if len(numero_section) > 50:
            print(f"⚠️ Numéro de section trop long, troncature: '{numero_section}' → '{numero_section[:47]}...'")
            # Si c'est un titre utilisé comme numéro, le tronquer intelligemment
            if numero_section == titre_section:
                # Garder uniquement les premiers mots jusqu'à la limite de 50 caractères
                words = numero_section.split()
                numero_section = ""
                for word in words:
                    if len(numero_section) + len(word) + 1 <= 50:  # +1 pour l'espace
                        if numero_section:
                            numero_section += " " + word
                        else:
                            numero_section = word
                    else:
                        break
                # Si toujours trop long, tronquer brutalement
                if len(numero_section) > 50:
                    numero_section = numero_section[:47] + "..."
            else:
                # C'est un identifiant de section qui ne devrait pas être modifié
                # Dans ce cas exceptionnel où l'identifiant est trop long, on le tronque brutalement
                numero_section = numero_section[:47] + "..."
                
        # Vérification finale pour s'assurer que la longueur est strictement respectée
        if len(numero_section) > 50:  # Double vérification pour être absolument sûr
            numero_section = numero_section[:47] + "..."
        
        # Calculer le niveau hiérarchique basé sur le numéro (si c'est un format numérique comme 2.1.3)
        if numero_section and re.match(r'^\d+(\.\d+)*$', numero_section):            niveau = numero_section.count('.') + 1
        else:
            niveau = 1
            
        return {
            'numero_section': numero_section,
            'titre_section': titre_section,
            'niveau_hierarchique': niveau
        }
    
def _extract_element_data(self, row, designation_text: str) -> Dict:
        """
        Extrait les données d'un élément d'ouvrage
        Sépare le numéro de la designation_exacte
        """
        # Extraire le numéro et la description
        element_description = designation_text
        
        # Pattern pour extraire "2.8.1 Description élément"
        element_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)', designation_text)
        if element_match:
            element_number = element_match.group(1).strip()  # Numéro (ex: "2.8.1")
            element_description = element_match.group(2).strip()  # Description sans numéro
        else:
            # Pattern pour les sous-éléments avec lettres, comme "a) Description"
            sub_element_match = re.match(r'^([a-z]\))\s+(.+)', designation_text)
            if sub_element_match:
                element_number = sub_element_match.group(1).strip()  # Référence (ex: "a)")
                element_description = sub_element_match.group(2).strip()  # Description
            else:
                # Pattern pour les tirets ou puces, comme "- Description"
                bullet_match = re.match(r'^[\-\*•]\s+(.+)', designation_text)
                if bullet_match:
                    element_description = bullet_match.group(1).strip()  # Description sans puce
        
        # Si après traitement la description est vide, utiliser le texte original
        if not element_description:
            element_description = designation_text
        
        # Assurer qu'on a une description (obligatoire selon le script de production)
        if not element_description or element_description.strip() == "":
            element_description = "Description manquante"
        
        element_data = {
            'designation_exacte': element_description,  # Uniquement la description, sans le numéro
            'unite': "",
            'quantite': 0.0,
            'prix_unitaire_ht': 0.0,
            'prix_total_ht': 0.0,
        }
        
        # Récupérer l'unité si disponible
        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
            element_data['unite'] = str(row.iloc[self.col_unite])[:10]  # Limiter à 10 caractères
        
        # Récupérer quantité et prix avec conversion sécurisée
        if self.col_quantite is not None and self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite]):
            element_data['quantite'] = self.safe_convert_to_float(row.iloc[self.col_quantite])
        
        if self.col_prix_unitaire is not None and self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]):
            element_data['prix_unitaire_ht'] = self.safe_convert_to_float(row.iloc[self.col_prix_unitaire])
        
        if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
            element_data['prix_total_ht'] = self.safe_convert_to_float(row.iloc[self.col_prix_total])
            
        # Calcul des valeurs manquantes
        if element_data['prix_total_ht'] == 0 and element_data['quantite'] > 0 and element_data['prix_unitaire_ht'] > 0:
            element_data['prix_total_ht'] = element_data['quantite'] * element_data['prix_unitaire_ht']
        elif element_data['quantite'] == 0 and element_data['prix_unitaire_ht'] > 0 and element_data['prix_total_ht'] > 0:
            element_data['quantite'] = element_data['prix_total_ht'] / element_data['prix_unitaire_ht']
        elif element_data['prix_unitaire_ht'] == 0 and element_data['quantite'] > 0 and element_data['prix_total_ht'] > 0:
            element_data['prix_unitaire_ht'] = element_data['prix_total_ht'] / element_data['quantite']
        
        return element_data


class DPGFImportService:
    """Service d'import de DPGF intégré à l'API"""
    
    def __init__(self, gemini_key: Optional[str] = None, use_gemini: bool = False, chunk_size: int = 20, debug: bool = False):
        self.stats = ImportStats()
        self.gemini_key = gemini_key
        self.use_gemini = use_gemini and gemini_key and GEMINI_AVAILABLE
        self.chunk_size = chunk_size
        self.debug = debug
        
        # Initialiser le processeur Gemini si demandé
        self.gemini = None
        if self.use_gemini:
            try:
                self.gemini = GeminiProcessor(gemini_key, chunk_size)
                print("✅ Processeur Gemini initialisé")
            except Exception as e:
                print(f"⚠️ Impossible d'initialiser le processeur Gemini: {e}")
                self.use_gemini = False
    
    def get_or_create_client(self, db: Session, client_name: str) -> int:
        """
        Récupère ou crée un client dans la base de données
        
        Args:
            db: Session de base de données
            client_name: Nom du client
            
        Returns:
            ID du client
        """
        if not client_name:
            raise ValueError("Nom de client requis")
        
        # 1. Essayer de trouver le client existant (insensible à la casse)
        clients = client_crud.get_clients(db)
        for client in clients:
            if client.nom_client.upper() == client_name.upper():
                print(f"✅ Client existant réutilisé: {client_name} (ID: {client.id_client})")
                return client.id_client
        
        # 2. Créer le client s'il n'existe pas
        try:
            client_create = ClientCreate(nom_client=client_name)
            new_client = client_crud.create_client(db, client_create)
            print(f"✅ Nouveau client créé: {client_name} (ID: {new_client.id_client})")
            return new_client.id_client
            
        except Exception as e:
            print(f"❌ Erreur création client {client_name}: {e}")
            raise
            
    def get_or_create_dpgf(self, db: Session, client_id: int, nom_projet: str, file_path: str) -> int:
        """
        Récupère ou crée un DPGF pour le client
        
        Args:
            db: Session de base de données
            client_id: ID du client
            nom_projet: Nom du projet
            file_path: Chemin du fichier source
            
        Returns:
            ID du DPGF
        """
        fichier_source = Path(file_path).name
        
        # 1. Chercher DPGF existant UNIQUEMENT par fichier source exact
        dpgfs = dpgf_crud.get_dpgfs(db)
        for dpgf in dpgfs:
            if dpgf.fichier_source == fichier_source and dpgf.id_client == client_id:
                print(f"✅ DPGF existant trouvé: {dpgf.nom_projet} (ID: {dpgf.id_dpgf})")
                return dpgf.id_dpgf
                
        print(f"🆕 Aucun DPGF existant trouvé pour le fichier {fichier_source}. Création d'un nouveau DPGF.")
        
        # 2. Créer nouveau DPGF (toujours créer un nouveau pour chaque fichier unique)
        try:
            dpgf_create = DPGFCreate(
                id_client=client_id,
                nom_projet=nom_projet,
                date_dpgf=date.today(),
                statut_offre=StatutOffre.en_cours,
                fichier_source=fichier_source
            )
            new_dpgf = dpgf_crud.create_dpgf(db, dpgf_create)
            print(f"✅ Nouveau DPGF créé: {nom_projet} (ID: {new_dpgf.id_dpgf})")
            return new_dpgf.id_dpgf
            
        except Exception as e:
            print(f"❌ Erreur création DPGF: {e}")
            raise
    
    def get_or_create_lot(self, db: Session, dpgf_id: int, numero_lot: str, nom_lot: str) -> int:
        """
        Récupère ou crée un lot dans la base de données
        
        Args:
            db: Session de base de données
            dpgf_id: ID du DPGF
            numero_lot: Numéro du lot
            nom_lot: Nom du lot
            
        Returns:
            ID du lot
        """
        # Nettoyer le numéro de lot
        numero_lot = str(numero_lot).strip()
        if not numero_lot:
            numero_lot = "1"  # Valeur par défaut si vide
            
        # Nettoyer le nom du lot
        if not nom_lot or nom_lot.strip() == "":
            nom_lot = f"Lot {numero_lot}"  # Nom par défaut
        
        # 1. Vérifier si un lot avec ce numéro existe déjà pour ce DPGF
        lots = lot_crud.get_lots_by_dpgf(db, dpgf_id)
        for lot in lots:
            if lot.numero_lot == numero_lot:
                print(f"✅ Lot existant réutilisé: {lot.numero_lot} - {lot.nom_lot} (ID: {lot.id_lot})")
                self.stats.lots_reused += 1
                return lot.id_lot
        
        # 2. Créer le lot s'il n'existe pas
        try:
            lot_create = LotCreate(
                id_dpgf=dpgf_id,
                numero_lot=numero_lot,
                nom_lot=nom_lot
            )
            new_lot = lot_crud.create_lot(db, lot_create)
            print(f"✅ Nouveau lot créé: {numero_lot} - {nom_lot} (ID: {new_lot.id_lot})")
            self.stats.lots_created += 1
            return new_lot.id_lot
            
        except Exception as e:
            print(f"❌ Erreur création lot {numero_lot}: {e}")
            raise
            
    def create_section(self, db: Session, lot_id: int, section_data: Dict) -> int:
        """
        Crée une section ou la récupère si elle existe déjà (par numéro)
        
        Args:
            db: Session de base de données
            lot_id: ID du lot
            section_data: Données de la section (numero_section, titre_section, niveau_hierarchique)
            
        Returns:
            ID de la section
        """
        # Valider les données requises
        numero_section = section_data.get('numero_section', '')
        titre_section = section_data.get('titre_section', '')
        niveau = section_data.get('niveau_hierarchique', 1)
        
        # Vérifier si une section avec ce numéro existe déjà
        sections = section_crud.get_sections_by_lot(db, lot_id)
        for section in sections:
            if section.numero_section == numero_section:
                print(f"🔄 Section existante réutilisée: {numero_section} - {section.titre_section}")
                self.stats.sections_reused += 1
                return section.id_section
        
        # Créer la section si elle n'existe pas
        try:
            section_create = SectionCreate(
                id_lot=lot_id,
                section_parent_id=None,  # Pas de hiérarchie pour l'instant
                numero_section=numero_section,
                titre_section=titre_section,
                niveau_hierarchique=niveau
            )
            new_section = section_crud.create_section(db, section_create)
            print(f"➕ Nouvelle section créée: {numero_section} - {titre_section}")
            self.stats.sections_created += 1
            return new_section.id_section
            
        except Exception as e:
            print(f"❌ Erreur création section {numero_section}: {e}")
            self.stats.errors += 1
            raise
    
    def create_element(self, db: Session, section_id: int, element_data: Dict) -> int:
        """
        Crée un élément d'ouvrage
        
        Args:
            db: Session de base de données
            section_id: ID de la section parente
            element_data: Données de l'élément (designation_exacte, unite, quantite, prix_unitaire_ht, prix_total_ht)
            
        Returns:
            ID de l'élément créé
        """
        # Valider et nettoyer les données
        designation = element_data.get('designation_exacte', 'Description manquante')
        unite = element_data.get('unite', '')[:10]  # Limiter à 10 caractères
        
        # Convertir les valeurs numériques avec gestion des cas None
        def safe_float(val, default=0.0):
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        
        quantite = safe_float(element_data.get('quantite'))
        prix_unitaire = safe_float(element_data.get('prix_unitaire_ht'))
        prix_total = safe_float(element_data.get('prix_total_ht'))
        
        # Si on a prix unitaire et quantité mais pas prix total, le calculer
        if prix_total == 0 and prix_unitaire > 0 and quantite > 0:
            prix_total = prix_unitaire * quantite
            
        # Créer l'élément d'ouvrage
        try:
            element_create = ElementOuvrageCreate(
                id_section=section_id,
                designation_exacte=designation,
                unite=unite,
                quantite=quantite,
                prix_unitaire_ht=prix_unitaire,
                prix_total_ht=prix_total,
                offre_acceptee=False
            )
            new_element = element_crud.create_element_ouvrage(db, element_create)
            print(f"➕ Nouvel élément créé: {designation[:30]}..." if len(designation) > 30 else designation)
            self.stats.elements_created += 1
            return new_element.id_element_ouvrage
            
        except Exception as e:
            print(f"❌ Erreur création élément: {e}")
            self.stats.errors += 1
            raise
    
    def import_file(self, db: Session, file_path: str, client_name: Optional[str] = None):
        """
        Importe un fichier DPGF dans la base de données
        
        Args:
            db: Session de base de données
            file_path: Chemin du fichier Excel
            client_name: Nom du client (optionnel, détecté automatiquement si non fourni)
            
        Returns:
            ID du DPGF importé
        """
        print(f"🔄 Import du fichier {file_path}")
        self.stats = ImportStats()  # Réinitialiser les stats
        
        # 1. Parser le fichier Excel
        parser = ExcelParser(file_path)
        
        # 2. Détecter ou utiliser le client
        if not client_name:
            client_name = parser.find_client_name()
        client_id = self.get_or_create_client(db, client_name)
        
        # 3. Créer le DPGF
        projet_name = f"Projet {client_name} - {Path(file_path).stem}"
        dpgf_id = self.get_or_create_dpgf(db, client_id, projet_name, file_path)
        
        # 4. Détecter les lots
        lot_headers = parser.find_lot_headers()
        
        # Si aucun lot n'est trouvé, créer un lot par défaut
        if not lot_headers:
            lot_headers = [("1", f"Lot principal {Path(file_path).stem}")]
            print(f"⚠️ Aucun lot détecté, création d'un lot par défaut")
        
        # Pour chaque lot trouvé
        for numero_lot, nom_lot in lot_headers:
            print(f"\n📋 Traitement du lot {numero_lot} - {nom_lot}")
            
            # Créer/récupérer le lot
            lot_id = self.get_or_create_lot(db, dpgf_id, numero_lot, nom_lot)
            
            # Détecter l'en-tête et les colonnes
            header_row = parser.find_header_row()
            if not parser.headers_detected:
                parser.detect_column_indices(header_row)
            
            # Analyser le fichier pour extraire sections et éléments
            items = parser.detect_sections_and_elements(header_row)
            
            # Organiser les sections et éléments
            current_section_id = None
            for item in items:
                try:
                    if item['type'] == 'section':
                        # Créer/récupérer la section
                        section_id = self.create_section(db, lot_id, item['data'])
                        current_section_id = section_id
                    
                    elif item['type'] == 'element' and current_section_id:
                        # Créer l'élément
                        self.create_element(db, current_section_id, item['data'])
                        
                except Exception as e:
                    print(f"❌ Erreur traitement ligne {item.get('row', '?')}: {e}")
                    self.stats.errors += 1
                
                self.stats.total_rows += 1
        
        # Afficher les statistiques finales
        print(f"\n✅ Import terminé pour {file_path}")
        print(f"   - Lignes traitées: {self.stats.total_rows}")
        print(f"   - Lots créés: {self.stats.lots_created} (réutilisés: {self.stats.lots_reused})")
        print(f"   - Sections créées: {self.stats.sections_created} (réutilisées: {self.stats.sections_reused})")
        print(f"   - Éléments créés: {self.stats.elements_created}")
        print(f"   - Erreurs: {self.stats.errors}")
        
        if self.use_gemini:
            print(f"   - Appels Gemini: {self.gemini.stats.gemini_calls}")
            print(f"   - Cache hits Gemini: {self.gemini.stats.cache_hits}")
        
        return dpgf_id
    
    def extract_data_from_file(self, file_path: str, auto_detect: bool = True) -> Dict[str, Any]:
        """
        Extrait les données d'un fichier DPGF sans les importer en base
        
        Args:
            file_path: Chemin du fichier à analyser
            auto_detect: Si True, tente de détecter automatiquement le client, projet et lot
            
        Returns:
            Un dictionnaire contenant les données structurées du DPGF
        """
        print(f"Extraction des données depuis {file_path}")
        
        # Initialiser les résultats
        results = {
            "client": None,
            "lots": [],
            "sections": [],
            "elements": []
        }
        
        try:
            # Vérifier que le fichier existe
            if not os.path.exists(file_path):
                print(f"❌ Fichier non trouvé: {file_path}")
                return results
                
            # Lire le fichier Excel
            print("Lecture du fichier Excel...")
            df = pd.read_excel(file_path, engine='openpyxl', header=None)
            
            if df.empty:
                print("❌ Fichier Excel vide")
                return results
                
            print(f"✅ Fichier chargé. {len(df)} lignes trouvées")
            
            # 1. Détection du client et projet (uniquement si auto_detect=True)
            client_info = None
            if auto_detect:
                client_info = self._detect_client_info(df)
                if client_info:
                    results["client"] = client_info
            
            # 2. Détecter les colonnes du DPGF
            col_mapping = self._detect_columns(df)
            if not col_mapping:
                print("❌ Structure de colonnes non reconnue")
                return results
            
            # 3. Détecter le lot si auto_detect=True
            lot_info = None
            if auto_detect:
                lot_info = self._detect_lot_info(df, file_path)
                if lot_info:
                    results["lots"].append(lot_info)
            
            # 4. Parser les sections et éléments d'ouvrage
            sections, elements = self._parse_sections_and_elements(
                df, 
                col_mapping,
                lot_id=None  # Pas de lot_id car on ne crée pas en base
            )
            
            # Ajouter les sections et éléments aux résultats
            results["sections"] = [s.dict() for s in sections]
            results["elements"] = [e.dict() for e in elements]
            
            print(f"✅ Extraction terminée: {len(sections)} sections, {len(elements)} éléments")
            return results
            
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction des données: {str(e)}")
            import traceback
            traceback.print_exc()
            return results
