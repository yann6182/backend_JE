"""
Script d'import DPGF complet amélioré:
- Détection automatique du client
- Import de lots
- Import des sections et sous-sections
- Import des éléments d'ouvrage
- Détection dynamique des colonnes de prix et quantités
- Gestion intelligente des erreurs et des doublons
- Classification avancée avec l'API Google Gemini (optionnelle)
"""

import argparse
import sys
import json
import os
import re
import hashlib
import pickle
from typing import Optional, Dict, List, Tuple, Generator
from datetime import date
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm

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
            # Lire seulement les premières lignes (augmenté à 15 pour une meilleure couverture)
            df = pd.read_excel(file_path, engine='openpyxl', nrows=15, header=None)
            
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
                    return client_name
        
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
        Recherche dans les 15 premières lignes les intitulés de lot au format
        « LOT <numéro> – <libellé> » (maj/min indifférent).
        
        Returns:
            Liste de tuples (numero_lot, nom_lot)
        """
        lots = []
        pattern = re.compile(r'lot\s+([^\s–-]+)\s*[–-]\s*(.+)', re.IGNORECASE)
        
        # Parcourir les 15 premières lignes
        for i in range(min(15, len(self.df))):
            for col in self.df.columns:
                cell_value = self.df.iloc[i, col]
                if pd.notna(cell_value):
                    cell_str = str(cell_value).strip()
                    match = pattern.search(cell_str)
                    if match:
                        numero_lot = match.group(1).strip()
                        nom_lot = match.group(2).strip()
                        lots.append((numero_lot, nom_lot))
        
        # Si aucun lot trouvé dans le contenu, essayer depuis le nom de fichier
        if not lots:
            filename_lot = self.extract_lot_from_filename()
            if filename_lot:
                lots.append(filename_lot)
        
        return lots
    
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
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    numero_lot = match.group(1).strip()
                    # Si on a un deuxième groupe de capture, c'est le nom du lot
                    if len(match.groups()) > 1 and match.group(2):
                        nom_lot = match.group(2).strip()
                    else:
                        nom_lot = f"Lot {numero_lot}"
                    
                    print(f"✓ Lot détecté depuis le nom du fichier: {numero_lot} - {nom_lot}")
                    return (numero_lot, nom_lot)
                except:
                    pass
                    
        # Essai de dernière chance: chercher juste un nombre dans le nom de fichier
        digit_match = re.search(r'(\d{1,2})', filename)
        if digit_match:
            numero = digit_match.group(1)
            if 1 <= int(numero) <= 99:  # Les numéros de lot sont généralement entre 1 et 99
                print(f"✓ Numéro de lot détecté depuis le nom de fichier: {numero}")
                return (numero, f"Lot {numero}")
        
        return None
        
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
        
        Returns:
            Index de la ligne d'en-tête ou None si non trouvée
        """
        # Patterns pour reconnaître les en-têtes (français et autres variations)
        header_patterns = {
            'designation': [r'désignation', r'libellé', r'description', r'prestation', r'article', r'détail', r'ouvrage', r'intitulé', r'nature'],
            'unite': [r'unité', r'u\.', r'un\.', r'un$', r'unité de mesure', r'mesure'],
            'quantite': [r'quantité', r'qté\.?', r'qt\.?', r'quant\.?', r'qte'],
            'prix_unitaire': [r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', r'pu(?:\s*h\.?t\.?)?'],
            'prix_total': [r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?']
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
            
            # Si on a trouvé au moins 3 des 5 en-têtes attendus, c'est probablement la bonne ligne
            if score >= 3:
                if score > best_score:
                    best_score = score
                    best_row = i
            
            # Si on a trouvé tous les en-têtes, on arrête la recherche
            if score == 5:
                print(f"✓ Ligne d'en-tête trouvée (ligne {i+1}): score parfait")
                return i
        
        if best_row is not None:
            print(f"✓ Ligne d'en-tête trouvée (ligne {best_row+1}): score {best_score}/5")
        else:
            print("⚠️ Aucune ligne d'en-tête trouvée, l'analyse pourrait être moins précise")
            
        return best_row
    
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
            'designation': [r'désignation', r'libellé', r'description', r'prestation', r'article', r'détail', r'ouvrage', r'intitulé', r'nature'],
            'unite': [r'unité', r'u\.', r'un\.', r'un$', r'unité de mesure', r'mesure'],
            'quantite': [r'quantité', r'qté\.?', r'qt\.?', r'quant\.?', r'qte'],
            'prix_unitaire': [r'prix\s*(?:unitaire|unit\.?)(?:\s*h\.?t\.?)?', r'p\.u\.(?:\s*h\.?t\.?)?', r'pu(?:\s*h\.?t\.?)?'],
            'prix_total': [r'prix\s*(?:total|tot\.?)(?:\s*h\.?t\.?)?', r'montant(?:\s*h\.?t\.?)?', r'p\.t\.(?:\s*h\.?t\.?)?', r'pt(?:\s*h\.?t\.?)?', r'total(?:\s*h\.?t\.?)?']
        }
        
        # Chercher chaque pattern dans les cellules de la ligne d'en-tête
        for col_name, col_patterns in patterns.items():
            for col_idx, cell_text in enumerate(header_row):
                cell_text = cell_text.lower()
                for pattern in col_patterns:
                    if re.search(pattern, cell_text, re.IGNORECASE):
                        column_indices[col_name] = col_idx
                        print(f"Colonne '{col_name}' détectée: indice {col_idx}, valeur: '{cell_text}'")
                        break
                if column_indices[col_name] is not None:
                    break
        
        # Si la désignation n'est pas trouvée, on peut supposer que c'est la première colonne
        if column_indices['designation'] is None:
            column_indices['designation'] = 0
            print(f"⚠️ Colonne 'designation' non détectée, supposée être à l'indice 0")
        
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
        
        # Si on a trouvé prix unitaire mais pas quantité, on cherche juste avant
        if column_indices['prix_unitaire'] is not None and column_indices['quantite'] is None:
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
        
        # Stocker dans l'instance
        self.col_designation = column_indices['designation']
        self.col_unite = column_indices['unite']
        self.col_quantite = column_indices['quantite']
        self.col_prix_unitaire = column_indices['prix_unitaire']
        self.col_prix_total = column_indices['prix_total']
        self.headers_detected = True
        
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
                    
                    # Générer un numéro unique pour cette section
                    # En utilisant un hash simple pour avoir un numéro unique
                    section_hash = abs(hash(titre_section)) % 10000
                    numero_section = f"S{section_hash}"
                    
                    # Stocker la section
                    current_section = {
                        'numero_section': numero_section,
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
                if current_section:
                    has_price_data = False
                    if self.col_prix_total is not None and self.col_prix_total < len(row) and pd.notna(row.iloc[self.col_prix_total]):
                        has_price_data = True
                    elif self.col_prix_unitaire is not None and self.col_quantite is not None:
                        if (self.col_prix_unitaire < len(row) and pd.notna(row.iloc[self.col_prix_unitaire]) and 
                            self.col_quantite < len(row) and pd.notna(row.iloc[self.col_quantite])):
                            has_price_data = True
                    
                    if has_price_data:
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
                                'prix_total_ht': prix_total,
                            },
                            'row': i
                        })
                        continue
        
        print(f"Total éléments/sections détectés: {len(results)}")
        return results


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
    
    def read_excel_chunks(self, file_path: str) -> Generator[pd.DataFrame, None, None]:
        """Lit un fichier Excel par chunks pour économiser la mémoire"""
        print(f"Lecture du fichier par chunks de {self.chunk_size} lignes...")
        
        # Lire par chunks
        skip_rows = 0
        while True:
            try:
                chunk = pd.read_excel(
                    file_path, 
                    engine='openpyxl',
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
        """Classifie un chunk avec Gemini + cache"""
        
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
        
        if result:
            # Mettre en cache (avec les numéros de ligne relatifs)
            cache_result = []
            for item in result:
                cache_item = item.copy()
                cache_item['row'] -= chunk_offset  
                cache_result.append(cache_item)
            self.cache.set(chunk_rows, cache_result)
        
        return result
    
    def _call_gemini_api(self, chunk_rows: List[str], chunk_offset: int) -> List[Dict]:
        """Appel direct à l'API Gemini"""
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
            print(f"Erreur Gemini pour chunk: {e}")
            return []


class DPGFImporter:
    """Importeur complet de DPGF avec détection intelligente des colonnes"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000", gemini_key: Optional[str] = None, 
                 use_gemini: bool = False, chunk_size: int = 20, debug: bool = False):
        self.base_url = base_url
        self.stats = ImportStats()
        self.gemini_key = gemini_key
        self.use_gemini = use_gemini and gemini_key and GEMINI_AVAILABLE
        self.chunk_size = chunk_size
        self.debug = debug
        
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
    
    def create_element(self, section_id: int, element_data: Dict):
        """Crée un élément d'ouvrage"""
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
            print(f"❌ Erreur création élément: {e}")
            if e.response.status_code == 500:
                error_details = e.response.text
                print(f"Erreur 500 détaillée: {error_details}")
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
            
    def import_file(self, file_path: str, dpgf_id: Optional[int] = None, lot_num: Optional[str] = None):
        """Import complet d'un fichier DPGF Excel"""
        print(f"\n📁 Import DPGF: {file_path}")
        print(f"Mode traitement: {'Gemini AI' if self.use_gemini else 'Analyse classique'}")
        print(f"Mode debug: {'Activé' if self.debug else 'Désactivé'}")
        
        try:
            parser = ExcelParser(file_path)
            client_detector = ClientDetector()
            
            # 1. Détecter le client si nécessaire
            client_name = client_detector.detect_client(file_path)
            if not client_name:
                client_name = "Client par défaut"
                print(f"⚠️ Utilisation d'un nom de client par défaut: {client_name}")
            
            client_id = self.get_or_create_client(client_name)
            
            # 2. Obtenir ou créer le DPGF
            if not dpgf_id:
                project_name = parser.detect_project_name(client_name)
                dpgf_id = self.get_or_create_dpgf(client_id, project_name, file_path)
            
            # 3. Détecter ou utiliser le lot spécifié
            if lot_num:
                # Utiliser un nom générique pour le lot spécifié
                lot_id = self.get_or_create_lot(dpgf_id, lot_num, f"Lot {lot_num}")
            else:
                # Rechercher dans le fichier
                lots = parser.find_lot_headers()
                if not lots:
                    raise ValueError("Aucun lot trouvé dans le fichier et aucun numéro de lot spécifié")
                
                # Utiliser le premier lot trouvé
                lot_num, lot_name = lots[0]
                lot_id = self.get_or_create_lot(dpgf_id, lot_num, lot_name)
            
            # 4. Extraire les sections et éléments
            if self.use_gemini:
                # Utiliser Gemini pour la classification avancée
                items = []
                for chunk_num, df_chunk in enumerate(self.gemini.read_excel_chunks(file_path)):
                    print(f"\nTraitement chunk {chunk_num + 1} (lignes {chunk_num*self.chunk_size}-{chunk_num*self.chunk_size + len(df_chunk)})")
                    classified_rows = self.gemini.classify_chunk(df_chunk, chunk_num*self.chunk_size)
                    items.extend(classified_rows)
                    
                # Mettre à jour les statistiques depuis Gemini
                self.stats.cache_hits = self.gemini.stats.cache_hits
                self.stats.gemini_calls = self.gemini.stats.gemini_calls
            else:
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
                items = parser.detect_sections_and_elements(header_row)
            
            # Filtrer les items ignorés
            items = [item for item in items if item.get('type') != 'ignore']
            print(f"🔍 {len(items)} items détectés ({sum(1 for i in items if i.get('type') == 'section')} sections, {sum(1 for i in items if i.get('type') == 'element')} éléments)")
            
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
                        if GEMINI_AVAILABLE:
                            description = item['data'].get('designation_exacte', '')
                            classification = self.classify_with_gemini(description)
                            item['data']['classification'] = classification
                        
                        self.create_element(current_section_id, item['data'])
                    except Exception as e:
                        print(f"❌ Erreur élément ligne {item['row']}: {e}")
                        self.stats.errors += 1
            
            # 6. Afficher les statistiques
            print(f"\n✅ Import terminé:")
            print(f"   - Lots créés: {self.stats.lots_created}, réutilisés: {self.stats.lots_reused}")
            print(f"   - Sections créées: {self.stats.sections_created}, réutilisées: {self.stats.sections_reused}")
            print(f"   - Éléments créés: {self.stats.elements_created}")
            print(f"   - Erreurs: {self.stats.errors}")
            
            if self.use_gemini:
                print(f"   - Appels Gemini: {self.stats.gemini_calls}")
                print(f"   - Cache hits: {self.stats.cache_hits}")
            
            return dpgf_id
            
        except Exception as e:
            print(f"❌ Erreur critique: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Point d'entrée du script"""
    parser = argparse.ArgumentParser(description="Import complet d'un fichier DPGF")
    parser.add_argument("--file", required=True, help="Chemin du fichier Excel DPGF")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de l'API")
    parser.add_argument("--dpgf-id", type=int, help="ID du DPGF existant (optionnel)")
    parser.add_argument("--lot-num", help="Numéro du lot (optionnel)")
    parser.add_argument("--gemini-key", help="Clé API Google Gemini pour la classification avancée")
    parser.add_argument("--chunk-size", type=int, default=20, help="Taille des chunks pour l'analyse Gemini (défaut: 20)")
    parser.add_argument("--no-gemini", action="store_true", help="Désactiver l'utilisation de Gemini même si la clé est fournie")
    parser.add_argument("--debug", action="store_true", help="Activer le mode debug pour plus d'informations")
    
    args = parser.parse_args()
    
    # Déterminer si on utilise Gemini
    use_gemini = args.gemini_key is not None and not args.no_gemini
    
    importer = DPGFImporter(
        base_url=args.base_url,
        gemini_key=args.gemini_key,
        use_gemini=use_gemini,
        chunk_size=args.chunk_size,
        debug=args.debug
    )
    
    importer.import_file(
        file_path=args.file,
        dpgf_id=args.dpgf_id,
        lot_num=args.lot_num
    )


if __name__ == "__main__":
    main()
