"""
Script d'import DPGF considérablement amélioré:
- Détection adaptative et intelligente des sections et éléments
- Patterns avancés pour tous les formats de DPGF
- Analyse par contenu quand les en-têtes manquent
- Détection robuste des colonnes avec fallback
- Support des formats SharePoint, BPU, etc.
- Pas de dépendance à Gemini (utilisation optionnelle seulement)
"""

import argparse
import sys
import json
import os
import re
import hashlib
import pickle
import csv
import numpy as np
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
    try:
        from enhanced_logging import get_import_logger, ImportLogger
    except ImportError:
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

# Import des modules existants
try:
    from scripts.import_complete import ColumnMapping, ErrorReporter, ClientDetector, detect_excel_engine
except ImportError:
    print("⚠️ Import de scripts.import_complete échoué, utilisation des classes de base")

# Configuration de l'encodage pour éviter les erreurs avec les caractères spéciaux
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


class ImportStats:
    """Statistiques d'import améliorées"""
    def __init__(self):
        self.total_rows = 0
        self.sections_created = 0
        self.elements_created = 0
        self.sections_reused = 0
        self.lots_created = 0
        self.lots_reused = 0
        self.errors = 0
        self.detection_method = "classic"  # classic, sharepoint, content_analysis
        self.confidence_score = 0


class EnhancedExcelParser:
    """Analyseur Excel considérablement amélioré avec détection adaptative"""
    
    def __init__(self, file_path: str, column_mapper: ColumnMapping = None, 
                 error_reporter: ErrorReporter = None, dry_run: bool = False):
        self.file_path = file_path
        self.column_mapper = column_mapper or ColumnMapping()
        self.error_reporter = error_reporter or ErrorReporter()
        self.dry_run = dry_run
        
        # Initialiser le logger d'import amélioré
        self.logger = get_import_logger(file_path)
        self.logger.info(f"Initialisation de l'analyse améliorée pour {Path(file_path).name}")
        
        # Initialiser tous les attributs de colonnes
        self.col_designation = None
        self.col_unite = None
        self.col_quantite = None
        self.col_prix_unitaire = None
        self.col_prix_total = None
        self.headers_detected = False
        self.mapping_confidence = 'unknown'
        
        # Charger le fichier avec le meilleur moteur
        self.df = self._load_best_excel_format(file_path)
        
    def _load_best_excel_format(self, file_path: str) -> pd.DataFrame:
        """Charge le fichier Excel avec le meilleur format et la meilleure feuille"""
        try:
            engine = detect_excel_engine(file_path)
            xl_file = pd.ExcelFile(file_path, engine=engine)
            
            if len(xl_file.sheet_names) == 1:
                return pd.read_excel(file_path, engine=engine, header=None)
            
            print(f"🔍 Fichier multi-feuilles détecté ({len(xl_file.sheet_names)} feuilles)")
            
            best_sheet = None
            best_score = 0
            
            for sheet_name in xl_file.sheet_names:
                try:
                    if any(skip_word in sheet_name.lower() for skip_word in ['garde', 'page', 'cover', 'sommaire']):
                        continue
                    
                    df_sheet = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, header=None)
                    
                    if df_sheet.shape[0] == 0 or df_sheet.shape[1] == 0:
                        continue
                    
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
            print(f"⚠️ Erreur lors du chargement: {e}")
            return pd.read_excel(file_path, engine=detect_excel_engine(file_path), header=None)
    
    def _score_sheet_content(self, df: pd.DataFrame) -> int:
        """Score le contenu d'une feuille pour déterminer si elle contient des données DPGF"""
        score = 0
        
        for i in range(min(10, df.shape[0])):
            row = df.iloc[i]
            row_text = ' '.join([str(val).lower() for val in row if pd.notna(val)])
            
            # Mots-clés DPGF
            if any(word in row_text for word in ['designation', 'désignation', 'quantité', 'prix', 'unitaire', 'montant']):
                score += 5
            
            # Numéros d'article
            if any(re.match(r'^\d+(\.\d+)*$', str(val)) for val in row if pd.notna(val)):
                score += 2
            
            # Unités typiques
            if any(word in row_text for word in ['ens', 'u', 'ml', 'm2', 'm3', 'kg']):
                score += 1
        
        if 10 <= df.shape[0] <= 1000 and 3 <= df.shape[1] <= 20:
            score += 3
        
        return score

    def find_header_row_enhanced(self) -> Optional[int]:
        """Version considérablement améliorée de la détection d'en-tête"""
        
        # Patterns améliorés pour reconnaître les en-têtes
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
        
        # Parcourir les 30 premières lignes
        for i in range(min(30, len(self.df))):
            row_values = [str(val).strip().lower() if pd.notna(val) else "" for val in self.df.iloc[i].values]
            row_text = " ".join(row_values)
            
            score = 0
            found_patterns = {k: False for k in header_patterns.keys()}
            
            for col_name, patterns in header_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, row_text, re.IGNORECASE):
                        found_patterns[col_name] = True
                        score += 1
                        break
                
                if not found_patterns[col_name]:
                    for col_idx, cell_text in enumerate(row_values):
                        for pattern in patterns:
                            if re.search(f"^{pattern}$", cell_text, re.IGNORECASE):
                                found_patterns[col_name] = True
                                score += 1
                                break
                        if found_patterns[col_name]:
                            break
            
            if score >= 2 and score > best_score:
                best_score = score
                best_row = i
            
            if score >= 4:
                print(f"✓ Ligne d'en-tête trouvée (ligne {i+1}): score excellent ({score}/5)")
                return i
        
        if best_row is not None:
            print(f"✓ Ligne d'en-tête trouvée (ligne {best_row+1}): score {best_score}/5")
        else:
            print("⚠️ Aucune ligne d'en-tête trouvée")
            
        return best_row

    def detect_columns_enhanced(self, header_row_idx: Optional[int]) -> Dict[str, Optional[int]]:
        """Détection améliorée des colonnes avec stratégies multiples"""
        
        if header_row_idx is not None:
            headers = [str(val).strip() if pd.notna(val) else f"Colonne_{i}" 
                      for i, val in enumerate(self.df.iloc[header_row_idx].values)]
        else:
            headers = [f"Colonne_{i}" for i in range(len(self.df.columns))]
        
        # 1. Essayer mapping existant
        filename = Path(self.file_path).stem
        existing_mapping = self.column_mapper.get_mapping(headers, filename)
        
        if existing_mapping:
            print(f"✅ Mapping existant trouvé et appliqué")
            self.mapping_confidence = 'high'
            return existing_mapping
        
        # 2. Détection automatique par en-têtes
        if header_row_idx is not None:
            column_indices = self._detect_by_headers(header_row_idx, headers)
            confidence = self._evaluate_mapping_confidence(column_indices)
            
            if confidence >= 3:
                print(f"✅ Détection par en-têtes réussie (confiance: {confidence}/5)")
                self.mapping_confidence = 'high' if confidence >= 4 else 'medium'
                self.column_mapper.save_mapping(headers, column_indices, filename)
                return column_indices
        
        # 3. Détection par analyse du contenu
        print("🔍 Tentative de détection par analyse du contenu...")
        column_indices = self._detect_by_content_analysis()
        
        confidence = self._evaluate_content_detection_confidence(column_indices)
        if confidence >= 2:
            print(f"✅ Détection par contenu réussie (confiance: {confidence}/5)")
            self.mapping_confidence = 'medium' if confidence >= 3 else 'low'
            return column_indices
        
        # 4. Mapping manuel en dernier recours
        print("⚠️ Détection automatique insuffisante, demande de mapping manuel...")
        column_indices = self.column_mapper.interactive_mapping(headers)
        self.mapping_confidence = 'manual'
        self.column_mapper.save_mapping(headers, column_indices, filename)
        
        return column_indices

    def _detect_by_headers(self, header_row_idx: int, headers: List[str]) -> Dict[str, Optional[int]]:
        """Détection des colonnes par analyse des en-têtes"""
        column_indices = {
            'designation': None,
            'unite': None,
            'quantite': None,
            'prix_unitaire': None,
            'prix_total': None
        }
        
        header_row = [str(val).strip().lower() if pd.notna(val) else "" for val in self.df.iloc[header_row_idx].values]
        
        patterns = {
            'designation': [
                r'désignation', r'designation', r'libellé', r'libelle', r'description', r'prestation', 
                r'article', r'détail', r'detail', r'ouvrage', r'intitulé', r'intitule', r'nature',
                r'désig', r'desig', r'libel', r'descr', r'prest'
            ],
            'unite': [
                r'unité', r'unite', r'u\.?$', r'un\.?$', r'un$', r'unité de mesure', r'mesure', 
                r'unit', r'^u$', r'unités', r'mesures'
            ],
            'quantite': [
                r'quantité', r'quantite', r'qté\.?', r'qt\.?', r'quant\.?', r'qte', r'nombre', 
                r'nb\.?', r'q\.?$', r'qtés?', r'quantités', r'qtite', r'quantit'
            ],
            'prix_unitaire': [
                r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', 
                r'pu(?:\s*h\.?t\.?)?$', r'prix$', r'pu\s*ht$', r'prix\s*ht$',
                r'p\.u', r'px.*unit'
            ],
            'prix_total': [
                r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', 
                r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?',
                r'p\.t', r'px.*tot', r'mont', r'tot'
            ]
        }
        
        for col_name, col_patterns in patterns.items():
            best_match_col = None
            best_match_score = 0
            
            for col_idx, cell_text in enumerate(header_row):
                if not cell_text:
                    continue
                    
                for pattern in col_patterns:
                    if re.search(pattern, cell_text, re.IGNORECASE):
                        if re.fullmatch(pattern, cell_text, re.IGNORECASE):
                            score = 10
                        elif cell_text == pattern:
                            score = 9
                        elif pattern in cell_text:
                            score = 7
                        else:
                            score = 5
                        
                        if score > best_match_score:
                            best_match_score = score
                            best_match_col = col_idx
                        break
            
            if best_match_col is not None:
                column_indices[col_name] = best_match_col
                print(f"✓ Colonne '{col_name}' détectée: {best_match_col} ({headers[best_match_col]}) score={best_match_score}")
        
        # Compléter avec détection par contenu pour les colonnes manquantes
        missing_cols = [k for k, v in column_indices.items() if v is None]
        if missing_cols:
            content_detected = self._detect_missing_by_content(header_row_idx, missing_cols)
            for col_name, col_idx in content_detected.items():
                if column_indices[col_name] is None:
                    column_indices[col_name] = col_idx
        
        return column_indices

    def _detect_by_content_analysis(self) -> Dict[str, Optional[int]]:
        """Détection par analyse complète du contenu sans en-têtes"""
        column_indices = {
            'designation': None,
            'unite': None,
            'quantite': None,
            'prix_unitaire': None,
            'prix_total': None
        }
        
        # 1. Détecter la désignation (colonne avec du texte long)
        for col_idx in range(min(8, len(self.df.columns))):
            text_lengths = []
            text_count = 0
            for i in range(min(30, len(self.df))):
                if pd.notna(self.df.iloc[i, col_idx]):
                    text = str(self.df.iloc[i, col_idx]).strip()
                    if len(text) > 5 and not text.replace('.', '').replace(',', '').replace(' ', '').isdigit():
                        text_lengths.append(len(text))
                        text_count += 1
            
            if text_lengths and len(text_lengths) > 5:
                avg_length = np.mean(text_lengths)
                if avg_length > 20:
                    column_indices['designation'] = col_idx
                    print(f"✓ Colonne désignation: {col_idx} (texte moyen: {avg_length:.1f} chars)")
                    break
        
        # 2. Analyser les colonnes numériques
        numeric_analysis = []
        for col_idx in range(len(self.df.columns)):
            if col_idx == column_indices['designation']:
                continue
            
            values = []
            for i in range(min(50, len(self.df))):
                if pd.notna(self.df.iloc[i, col_idx]):
                    try:
                        val = self.safe_convert_to_float(self.df.iloc[i, col_idx])
                        if val >= 0:
                            values.append(val)
                    except:
                        pass
            
            if len(values) > 5:
                non_zero_values = [v for v in values if v > 0]
                if non_zero_values:
                    numeric_analysis.append({
                        'col_idx': col_idx,
                        'avg_val': np.mean(non_zero_values),
                        'median_val': np.median(non_zero_values),
                        'max_val': max(non_zero_values),
                        'count': len(non_zero_values)
                    })
        
        # 3. Assigner les colonnes numériques selon leurs caractéristiques
        if len(numeric_analysis) >= 3:
            # Quantité : petites valeurs
            quantity_candidates = [col for col in numeric_analysis 
                                   if col['avg_val'] < 1000 and col['median_val'] < 100]
            if quantity_candidates:
                column_indices['quantite'] = quantity_candidates[0]['col_idx']
            
            # Prix total : grandes valeurs
            total_candidates = [col for col in numeric_analysis 
                               if col['avg_val'] > 100 and col['max_val'] > 1000]
            if total_candidates:
                total_col = max(total_candidates, key=lambda x: x['avg_val'])
                column_indices['prix_total'] = total_col['col_idx']
            
            # Prix unitaire : ce qui reste
            assigned_cols = {column_indices['quantite'], column_indices['prix_total']}
            for col in numeric_analysis:
                if col['col_idx'] not in assigned_cols and column_indices['prix_unitaire'] is None:
                    column_indices['prix_unitaire'] = col['col_idx']
                    break
                    
        elif len(numeric_analysis) == 2:
            col1, col2 = numeric_analysis[0], numeric_analysis[1]
            
            if col1['avg_val'] < col2['avg_val'] / 10:
                column_indices['quantite'] = col1['col_idx']
                column_indices['prix_total'] = col2['col_idx']
            elif col2['avg_val'] < col1['avg_val'] / 10:
                column_indices['quantite'] = col2['col_idx']
                column_indices['prix_total'] = col1['col_idx']
            else:
                if col1['avg_val'] < col2['avg_val']:
                    column_indices['prix_unitaire'] = col1['col_idx']
                    column_indices['prix_total'] = col2['col_idx']
                else:
                    column_indices['prix_unitaire'] = col2['col_idx']
                    column_indices['prix_total'] = col1['col_idx']
                    
        elif len(numeric_analysis) == 1:
            col = numeric_analysis[0]
            if col['avg_val'] > 100:
                column_indices['prix_total'] = col['col_idx']
            else:
                column_indices['prix_unitaire'] = col['col_idx']
        
        # 4. Détecter l'unité
        if column_indices['designation'] is not None:
            for col_idx in range(column_indices['designation'] + 1, min(column_indices['designation'] + 5, len(self.df.columns))):
                if col_idx in [col['col_idx'] for col in numeric_analysis]:
                    continue
                
                unit_indicators = 0
                total_cells = 0
                
                for i in range(min(40, len(self.df))):
                    if pd.notna(self.df.iloc[i, col_idx]):
                        text = str(self.df.iloc[i, col_idx]).strip().lower()
                        if text and len(text) <= 15:
                            total_cells += 1
                            if any(unit in text for unit in ['m2', 'm²', 'ml', 'u', 'ens', 'kg', 'h', 'j', 'forfait', 'ft']):
                                unit_indicators += 1
                
                if total_cells > 5 and unit_indicators / total_cells > 0.3:
                    column_indices['unite'] = col_idx
                    print(f"✓ Colonne unité: {col_idx} (ratio: {unit_indicators/total_cells:.1%})")
                    break
        
        return column_indices

    def _detect_missing_by_content(self, header_row_idx: int, missing_cols: List[str]) -> Dict[str, int]:
        """Détecte les colonnes manquantes par analyse du contenu"""
        detected = {}
        start_row = header_row_idx + 1 if header_row_idx is not None else 0
        
        for col_name in missing_cols:
            if col_name == 'unite':
                for col_idx in range(len(self.df.columns)):
                    unit_score = 0
                    total_score = 0
                    
                    for i in range(start_row, min(start_row + 30, len(self.df))):
                        if pd.notna(self.df.iloc[i, col_idx]):
                            text = str(self.df.iloc[i, col_idx]).strip().lower()
                            if text and len(text) <= 15:
                                total_score += 1
                                if any(unit in text for unit in ['m2', 'm²', 'ml', 'u', 'ens', 'kg', 'h', 'j', 'forfait', 'ft']):
                                    unit_score += 1
                    
                    if total_score > 5 and unit_score / total_score > 0.4:
                        detected['unite'] = col_idx
                        break
        
        return detected

    def _evaluate_mapping_confidence(self, column_indices: Dict[str, Optional[int]]) -> int:
        """Évalue la confiance du mapping (0-5)"""
        score = 0
        essential_cols = ['designation', 'prix_unitaire']
        
        for col in essential_cols:
            if column_indices[col] is not None:
                score += 2
        
        optional_cols = ['unite', 'quantite', 'prix_total']
        for col in optional_cols:
            if column_indices[col] is not None:
                score += 1
        
        return min(score, 5)

    def _evaluate_content_detection_confidence(self, column_indices: Dict[str, Optional[int]]) -> int:
        """Évalue la confiance de la détection par contenu (0-5)"""
        score = 0
        
        if column_indices['designation'] is not None:
            score += 2
        
        numeric_cols = [column_indices['quantite'], column_indices['prix_unitaire'], column_indices['prix_total']]
        numeric_count = sum(1 for col in numeric_cols if col is not None)
        score += numeric_count
        
        if column_indices['unite'] is not None:
            score += 1
        
        return min(score, 5)

    def safe_convert_to_float(self, value) -> float:
        """Convertit une valeur en float de façon sécurisée"""
        if pd.isna(value):
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            val_str = str(value).strip()
            val_str = re.sub(r'[€$£¥\s]', '', val_str)
            val_str = val_str.replace(',', '.')
            val_str = re.sub(r'[^\d\.\-]', '', val_str)
            
            if not val_str or val_str == '.':
                return 0.0
            
            return float(val_str)
        except (ValueError, TypeError):
            return 0.0

    def detect_sections_and_elements_enhanced(self, header_row: Optional[int] = None) -> List[Dict]:
        """Version considérablement améliorée de la détection des sections et éléments"""
        results = []
        
        print("🔍 === DÉTECTION AVANCÉE DES SECTIONS ET ÉLÉMENTS ===")
        
        # Détecter les colonnes si pas encore fait
        if not self.headers_detected:
            if header_row is None:
                header_row = self.find_header_row_enhanced()
            
            column_indices = self.detect_columns_enhanced(header_row)
            self._store_column_indices(column_indices)
        
        # S'assurer qu'on a au moins une colonne de désignation
        if self.col_designation is None:
            self.col_designation = 0
            print("⚠️ Colonne de désignation non détectée, utilisation de la colonne 0")
        
        print(f"📊 Colonnes utilisées:")
        print(f"   Désignation: {self.col_designation}")
        print(f"   Unité: {self.col_unite}")
        print(f"   Quantité: {self.col_quantite}")
        print(f"   Prix unitaire: {self.col_prix_unitaire}")
        print(f"   Prix total: {self.col_prix_total}")
        
        # Patterns améliorés pour sections
        section_patterns = {
            'numbered_standard': re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)'),
            'numbered_punctuated': re.compile(r'^(\d+(?:\.\d+)*)[.-]\s*(.+)'),
            'uppercase_title': re.compile(r'^([A-Z][A-Z\s\d\.\-\_\&\']{4,})$'),
            'roman_numeral': re.compile(r'^([IVX]{1,5})[.\-\s]\s*(.+)'),
            'letter_numeral': re.compile(r'^([A-H])[.\-\s]\s*(.+)'),
            'prefixed_section': re.compile(r'^(CHAPITRE|LOT|PARTIE|SECTION|SOUS-SECTION)\s+([A-Z0-9]+)[\s\:]*(.*)'),
            'total_section': re.compile(r'^(SOUS[\-\s]*TOTAL|TOTAL|MONTANT\s+TOTAL)[\s\:]*(.*)'),
            'sharepoint_numbered': re.compile(r'^(\d+\.\d+(?:\.\d+)*)\s*(.*)'),
            'complex_article': re.compile(r'^([A-Z]?\d{1,2}(?:\.\d{1,2}){2,})\s+(.+)'),
            'dash_section': re.compile(r'^\s*[-•]\s+([A-Z].{5,})$')
        }
        
        current_section = None
        start_row = header_row + 1 if header_row is not None else 0
        
        sections_count = 0
        elements_count = 0
        
        for i in range(start_row, len(self.df)):
            row = self.df.iloc[i]
            
            if all(pd.isna(val) for val in row.values):
                continue
            
            if pd.notna(row.iloc[self.col_designation]):
                cell_text = str(row.iloc[self.col_designation]).strip()
                section_detected = False
                
                # Essayer tous les patterns de section
                for pattern_name, pattern in section_patterns.items():
                    match = pattern.match(cell_text)
                    if match:
                        section_data = self._extract_section_from_match(match, pattern_name, cell_text)
                        
                        if section_data:
                            niveau = self._calculate_hierarchical_level(section_data['numero_section'], pattern_name)
                            section_data['niveau_hierarchique'] = niveau
                            
                            current_section = section_data
                            
                            results.append({
                                'type': 'section',
                                'data': current_section,
                                'row': i
                            })
                            sections_count += 1
                            section_detected = True
                            print(f"✓ Section détectée (ligne {i+1}): {section_data['numero_section']} - {section_data['titre_section'][:50]}...")
                            break
                
                if not section_detected:
                    # Analyser si c'est un élément
                    element_analysis = self._analyze_potential_element(row, cell_text, i)
                    
                    if element_analysis['is_element']:
                        if current_section is None:
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
                            sections_count += 1
                            print("📝 Section par défaut créée pour les éléments")
                        
                        element_data = self._create_element_data(row, element_analysis, cell_text)
                        
                        results.append({
                            'type': 'element',
                            'data': element_data,
                            'row': i
                        })
                        elements_count += 1
        
        print(f"✅ Détection terminée: {sections_count} sections, {elements_count} éléments")
        return results

    def _extract_section_from_match(self, match, pattern_name: str, original_text: str) -> Optional[Dict]:
        """Extrait les données de section selon le pattern"""
        try:
            if pattern_name == 'uppercase_title':
                titre_section = match.group(1).strip()
                section_hash = abs(hash(titre_section)) % 10000
                numero_section = f"S{section_hash:04d}"
                
            elif pattern_name in ['numbered_standard', 'numbered_punctuated', 'sharepoint_numbered']:
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else f"Section {numero_section}"
                
            elif pattern_name in ['roman_numeral', 'letter_numeral']:
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name == 'prefixed_section':
                prefix = match.group(1).strip()
                number = match.group(2).strip()
                title = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
                numero_section = f"{prefix} {number}"
                titre_section = title if title else numero_section
                
            elif pattern_name == 'total_section':
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else numero_section
                
            elif pattern_name == 'complex_article':
                numero_section = match.group(1).strip()
                titre_section = match.group(2).strip()
                
            elif pattern_name == 'dash_section':
                titre_section = match.group(1).strip()
                numero_section = f"SEC_{abs(hash(titre_section)) % 1000:03d}"
                
            else:
                return None
            
            if len(numero_section) > 50:
                numero_section = numero_section[:47] + "..."
            
            return {
                'numero_section': numero_section,
                'titre_section': titre_section
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction de section: {e}")
            return None

    def _calculate_hierarchical_level(self, numero_section: str, pattern_name: str) -> int:
        """Calcule le niveau hiérarchique d'une section"""
        if pattern_name in ['numbered_standard', 'numbered_punctuated', 'sharepoint_numbered']:
            return numero_section.count('.') + 1
        elif pattern_name == 'uppercase_title':
            return 1
        elif pattern_name in ['roman_numeral', 'letter_numeral']:
            return 1
        elif pattern_name == 'prefixed_section':
            return 1
        elif pattern_name == 'total_section':
            return 1
        elif pattern_name == 'complex_article':
            return numero_section.count('.') + 1
        elif pattern_name == 'dash_section':
            return 2
        else:
            return 1

    def _analyze_potential_element(self, row, cell_text: str, row_index: int) -> Dict:
        """Analyse améliorée pour déterminer si une ligne est un élément"""
        analysis = {
            'is_element': False,
            'has_price_data': False,
            'has_unit_data': False,
            'has_designation_data': False,
            'has_article_number': False,
            'confidence_score': 0
        }
        
        # 1. Vérifier la qualité de la désignation
        if len(cell_text) > 3:
            analysis['has_designation_data'] = True
            analysis['confidence_score'] += 1
            
            # Bonus pour désignations typiques
            work_keywords = [
                'fourniture', 'pose', 'installation', 'montage', 'démontage', 'réalisation',
                'construction', 'maçonnerie', 'peinture', 'carrelage', 'plomberie', 'électricité',
                'menuiserie', 'couverture', 'charpente', 'isolation', 'cloisons', 'revêtement'
            ]
            if any(word in cell_text.lower() for word in work_keywords):
                analysis['confidence_score'] += 2
        
        # 2. Vérifier unité
        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
            unit_text = str(row.iloc[self.col_unite]).strip().lower()
            if unit_text and unit_text not in ['', '0', 'nan']:
                analysis['has_unit_data'] = True
                analysis['confidence_score'] += 1
                
                if any(unit in unit_text for unit in ['m2', 'm²', 'ml', 'u', 'ens', 'kg', 'h', 'j', 'forfait', 'ft']):
                    analysis['confidence_score'] += 1
        
        # 3. Vérifier données numériques
        numeric_cols_with_data = 0
        
        for col_attr in ['col_prix_total', 'col_prix_unitaire', 'col_quantite']:
            col_idx = getattr(self, col_attr, None)
            if col_idx is not None and col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                try:
                    val = self.safe_convert_to_float(row.iloc[col_idx])
                    if val > 0:
                        analysis['has_price_data'] = True
                        numeric_cols_with_data += 1
                        analysis['confidence_score'] += 1 if col_attr == 'col_quantite' else 2
                except:
                    pass
        
        # 4. Détecter numérotation d'articles
        if cell_text:
            words = cell_text.split()
            if words:
                first_word = words[0]
                if re.match(r'^[A-Z]?\d+(?:\.\d+)*$', first_word):
                    analysis['has_article_number'] = True
                    analysis['confidence_score'] += 1
                elif re.match(r'^\d{1,3}$', first_word) and len(cell_text) > 10:
                    analysis['has_article_number'] = True
                    analysis['confidence_score'] += 1
        
        # 5. Indicateurs d'éléments dans le texte
        element_indicators = [
            'fourniture et pose', 'f et p', 'y compris', 'comprise', 'inclus',
            'main d\'œuvre', 'main d\'oeuvre', 'mo', 'm.o.', 'matériau', 'materiaux'
        ]
        
        if any(indicator in cell_text.lower() for indicator in element_indicators):
            analysis['confidence_score'] += 1
        
        # Décision finale
        min_score = 2
        criteria_met = (
            analysis['has_designation_data'] and (
                analysis['has_price_data'] or 
                analysis['has_unit_data'] or 
                analysis['has_article_number'] or
                numeric_cols_with_data >= 1
            )
        )
        
        analysis['is_element'] = criteria_met and analysis['confidence_score'] >= min_score
        
        return analysis

    def _create_element_data(self, row, analysis: Dict, designation: str) -> Dict:
        """Crée les données d'un élément d'ouvrage"""
        unite = ""
        if self.col_unite is not None and self.col_unite < len(row) and pd.notna(row.iloc[self.col_unite]):
            unite = str(row.iloc[self.col_unite]).strip()
        
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
            prix_total = quantite * prix_unitaire
        
        if prix_total > 0:
            if prix_unitaire == 0 and quantite > 0:
                prix_unitaire = prix_total / quantite
            elif quantite == 0 and prix_unitaire > 0:
                quantite = prix_total / prix_unitaire
        
        return {
            'designation_exacte': designation,
            'unite': unite[:10] if unite else "",
            'quantite': quantite,
            'prix_unitaire_ht': prix_unitaire,
            'prix_total_ht': prix_total,
        }

    def _store_column_indices(self, column_indices: Dict[str, Optional[int]]):
        """Stocke les indices des colonnes dans l'instance"""
        self.col_designation = column_indices['designation']
        self.col_unite = column_indices['unite']
        self.col_quantite = column_indices['quantite']
        self.col_prix_unitaire = column_indices['prix_unitaire']
        self.col_prix_total = column_indices['prix_total']
        self.headers_detected = True

    def find_lot_headers_enhanced(self) -> List[Tuple[str, str]]:
        """Détection améliorée des lots"""
        lots = []
        
        # 1. Priorité au nom de fichier (plus fiable)
        filename_lot = self.extract_lot_from_filename_enhanced()
        if filename_lot:
            print(f"✅ Lot détecté depuis le nom de fichier: {filename_lot[0]} - {filename_lot[1]}")
            return [filename_lot]
        
        # 2. Recherche dans le contenu
        pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
        
        for i in range(min(15, len(self.df))):
            for col in range(len(self.df.columns)):
                if col < len(self.df.columns):
                    cell_value = self.df.iloc[i, col]
                    if pd.notna(cell_value):
                        cell_str = str(cell_value).strip()
                        match = pattern.search(cell_str)
                        if match:
                            numero_lot = match.group(1).strip()
                            nom_lot = match.group(2).strip()
                            lots.append((numero_lot, nom_lot))
                            print(f"✅ Lot détecté dans le contenu: {numero_lot} - {nom_lot}")
        
        if not lots:
            print("⚠️ Aucun lot détecté")
        
        return lots

    def extract_lot_from_filename_enhanced(self) -> Optional[Tuple[str, str]]:
        """Version améliorée d'extraction de lot depuis le nom de fichier"""
        filename = Path(self.file_path).stem
        
        patterns = [
            (r'lot\s*(\d{1,2})\s*-\s*(?:dpgf|devis|bpu|dqe)\s*-\s*([\w\s\-&°\'\.]+)', 'LOT XX - DPGF - NOM'),
            (r'dpgf\s*[-_]?\s*lot\s*(\d{1,2})\s+([\w\s\-&°\'\.]+)', 'DPGF-Lot XX NOM'),
            (r'lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)', 'LOT XX - NOM'),
            (r'^\d+\s+dpgf\s+lot\s*(\d{1,2})\s*-\s*([\w\s\-&°\'\.]+)', 'XXX DPGF Lot X - NOM'),
            (r'lot\s*(\d{1,2})[_\-\s]+([\w\s\-&°\'\.]+)', 'LotXX_NOM'),
            (r'(\d{1,2})\s*[-_]\s*([\w\s\-&°\'\.]+)', 'XX - NOM'),
            (r'-\s*dpgf\s*-?\s*lot\s*(\d{1,2})', 'XXX - DPGF -LotX'),
            (r'lot\s*(\d{1,2})(?!\d)', 'LotX'),
        ]
        
        for pattern, description in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    numero_lot = match.group(1).strip()
                    
                    if len(match.groups()) > 1 and match.group(2):
                        nom_lot = match.group(2).strip()
                        nom_lot = self._clean_lot_name(nom_lot)
                        if not nom_lot:
                            nom_lot = f"Lot {numero_lot}"
                    else:
                        nom_lot = self._infer_lot_name_from_filename(filename, numero_lot)
                    
                    return (numero_lot, nom_lot)
                except Exception as e:
                    continue
        
        # Essai de dernière chance
        keywords = ['lot', 'dpgf', 'bpu', 'dqe', 'devis', 'bordereau']
        if any(keyword in filename.lower() for keyword in keywords):
            digit_matches = list(re.finditer(r'(\d{1,2})', filename))
            if digit_matches:
                for match in digit_matches:
                    numero = match.group(1)
                    try:
                        num_val = int(numero)
                        if 1 <= num_val <= 99:
                            nom_lot = self._infer_lot_name_from_filename(filename, numero)
                            return (numero, nom_lot)
                    except ValueError:
                        continue
        
        return None

    def _clean_lot_name(self, name: str) -> str:
        """Nettoie le nom d'un lot"""
        if not name:
            return ""
        
        name = re.sub(r'\.(xlsx?|xls|csv)$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[_\-\.]+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        parasites = ['dpgf', 'bpu', 'dqe', 'devis', 'bordereau', 'prix', 'unitaire']
        words = name.split()
        cleaned_words = [w for w in words if w.lower() not in parasites and len(w) > 1]
        
        result = ' '.join(cleaned_words)
        
        if len(result) < 5 and len(words) > 0:
            for word in words:
                if len(word) > 2 and word.lower() not in ['lot', 'de', 'du', 'la', 'le', 'et']:
                    return word.capitalize()
        
        return result

    def _infer_lot_name_from_filename(self, filename: str, numero_lot: str) -> str:
        """Infère le nom du lot à partir du nom de fichier"""
        metiers = {
            'menuiserie': ['menuiserie', 'menuiser', 'bois', 'porte', 'fenetre', 'fenêtre'],
            'plomberie': ['plomberie', 'plomb', 'eau', 'sanitaire', 'wc', 'salle de bain'],
            'électricité': ['electricite', 'electrique', 'elec', 'courant', 'tableau', 'prise'],
            'carrelage': ['carrelage', 'carrel', 'faience', 'faïence', 'sol', 'mur'],
            'peinture': ['peinture', 'peint', 'finition', 'decoration', 'décoration'],
            'maçonnerie': ['maconnerie', 'macon', 'beton', 'béton', 'mur', 'cloison'],
            'métallerie': ['metallerie', 'metal', 'métal', 'serrurerie', 'fer', 'acier'],
        }
        
        filename_lower = filename.lower()
        
        for metier, keywords in metiers.items():
            if any(keyword in filename_lower for keyword in keywords):
                return metier.capitalize()
        
        cleaned_filename = re.sub(rf'lot\s*{numero_lot}', '', filename_lower)
        cleaned_filename = re.sub(r'[_\-\.\(\)]', ' ', cleaned_filename)
        cleaned_filename = re.sub(r'\s+', ' ', cleaned_filename)
        
        words = cleaned_filename.split()
        significant_words = []
        
        parasites = ['dpgf', 'bpu', 'dqe', 'devis', 'bordereau', 'prix', 'unitaire', 'projet', 'chantier', 'travaux']
        
        for word in words:
            if (len(word) > 3 and 
                word not in parasites and 
                not word.isdigit() and 
                not re.match(r'^\d+$', word)):
                significant_words.append(word.capitalize())
        
        if significant_words:
            return ' '.join(significant_words[:2])
        
        return f"Lot {numero_lot}"


def main():
    """Fonction principale avec interface en ligne de commande améliorée"""
    parser = argparse.ArgumentParser(description='Import DPGF amélioré avec détection adaptative')
    parser.add_argument('file_path', help='Chemin vers le fichier Excel DPGF')
    parser.add_argument('--dry-run', action='store_true', help='Analyse sans import en base')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    parser.add_argument('--confidence-threshold', type=int, default=2, 
                        help='Seuil de confiance minimum (1-5, défaut: 2)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"❌ Fichier non trouvé: {args.file_path}")
        return 1
    
    try:
        print("🚀 === IMPORT DPGF AMÉLIORÉ ===")
        print(f"📁 Fichier: {args.file_path}")
        print(f"🔍 Mode: {'Analyse seule' if args.dry_run else 'Import complet'}")
        
        # Initialiser les composants
        column_mapper = ColumnMapping()
        error_reporter = ErrorReporter()
        
        # Créer le parser amélioré
        parser = EnhancedExcelParser(
            file_path=args.file_path,
            column_mapper=column_mapper,
            error_reporter=error_reporter,
            dry_run=args.dry_run
        )
        
        # Détecter le client
        client_detector = ClientDetector()
        client_name = client_detector.detect_client(args.file_path)
        
        # Détecter les lots
        lots = parser.find_lot_headers_enhanced()
        
        # Détecter les sections et éléments
        items = parser.detect_sections_and_elements_enhanced()
        
        # Afficher les résultats
        sections = [item for item in items if item['type'] == 'section']
        elements = [item for item in items if item['type'] == 'element']
        
        print(f"\n📊 === RÉSULTATS DE L'ANALYSE ===")
        print(f"👤 Client détecté: {client_name or 'Non détecté'}")
        print(f"📦 Lots détectés: {len(lots)}")
        for lot_num, lot_name in lots:
            print(f"   Lot {lot_num}: {lot_name}")
        print(f"📋 Sections détectées: {len(sections)}")
        print(f"🔧 Éléments détectés: {len(elements)}")
        print(f"🎯 Confiance mapping: {parser.mapping_confidence}")
        
        if args.debug:
            print(f"\n🔍 === DÉTAILS DEBUG ===")
            for i, section in enumerate(sections[:5]):  # Limiter à 5 pour éviter le spam
                data = section['data']
                print(f"Section {i+1}: {data['numero_section']} - {data['titre_section'][:50]}...")
            
            for i, element in enumerate(elements[:10]):  # Limiter à 10
                data = element['data']
                print(f"Élément {i+1}: {data['designation_exacte'][:50]}... (Q:{data['quantite']}, PU:{data['prix_unitaire_ht']})")
        
        # Sauvegarder le rapport d'erreurs
        error_reporter.save_report()
        
        print(f"\n✅ Analyse terminée avec succès!")
        return 0
        
    except Exception as e:
        print(f"❌ Erreur lors de l'import: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
