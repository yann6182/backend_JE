"""
Module de journalisation amélioré pour le suivi des opérations d'import DPGF.
Permet un diagnostic précis des problèmes de détection de lots et sections.
"""

import os
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Configuration du logger
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Nom du fichier de log avec timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"dpgf_import_{timestamp}.log"
log_path = log_dir / log_filename

# Configuration du format de log
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Configurer le logger principal
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Créer un logger spécifique pour l'import DPGF
dpgf_logger = logging.getLogger("DPGF_Import")
dpgf_logger.setLevel(logging.DEBUG)

# Ajouter un handler pour les logs détaillés dans un fichier séparé
detailed_log_path = log_dir / f"dpgf_import_detailed_{timestamp}.log"
detailed_handler = logging.FileHandler(detailed_log_path, encoding='utf-8')
detailed_handler.setLevel(logging.DEBUG)
detailed_handler.setFormatter(logging.Formatter(LOG_FORMAT))
dpgf_logger.addHandler(detailed_handler)


class ImportLogger:
    """Gestionnaire de logs amélioré pour l'import DPGF"""
    
    def __init__(self, file_path: str):
        """
        Initialise le logger pour un fichier d'import spécifique
        
        Args:
            file_path: Chemin du fichier DPGF en cours d'import
        """
        self.file_path = file_path
        self.filename = Path(file_path).name
        self.log_context = {"file": self.filename}
        
        # Créer un sous-dossier pour les logs propres à ce fichier
        self.file_log_dir = log_dir / Path(self.filename).stem
        self.file_log_dir.mkdir(exist_ok=True)
        
        # Fichier de log spécifique pour ce fichier
        self.file_log_path = self.file_log_dir / f"import_{timestamp}.log"
        self.file_handler = logging.FileHandler(self.file_log_path, encoding='utf-8')
        self.file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        
        self.file_logger = logging.getLogger(f"DPGF_Import_{Path(self.filename).stem}")
        self.file_logger.setLevel(logging.DEBUG)
        self.file_logger.addHandler(self.file_handler)
        
        # Fichier JSON pour les détails d'analyse
        self.analysis_path = self.file_log_dir / f"analysis_{timestamp}.json"
        
        self.info(f"Démarrage import pour {self.filename}")
    
    def info(self, message: str):
        """Log un message d'information"""
        dpgf_logger.info(f"[{self.filename}] {message}")
        self.file_logger.info(message)
    
    def debug(self, message: str):
        """Log un message de debug"""
        dpgf_logger.debug(f"[{self.filename}] {message}")
        self.file_logger.debug(message)
    
    def warning(self, message: str):
        """Log un avertissement"""
        dpgf_logger.warning(f"[{self.filename}] {message}")
        self.file_logger.warning(message)
    
    def error(self, message: str):
        """Log une erreur"""
        dpgf_logger.error(f"[{self.filename}] {message}")
        self.file_logger.error(message)
    
    def critical(self, message: str):
        """Log une erreur critique"""
        dpgf_logger.critical(f"[{self.filename}] {message}")
        self.file_logger.critical(message)
    
    def log_lot_detection(self, method: str, success: bool, lot_info: Optional[Tuple[str, str]] = None, 
                          pattern: str = None, error: str = None):
        """
        Log détaillé du processus de détection de lot
        
        Args:
            method: Méthode utilisée ('filename', 'gemini', 'content', 'fallback')
            success: Si la détection a réussi
            lot_info: Tuple (numero_lot, nom_lot) si détecté
            pattern: Pattern utilisé pour la détection
            error: Message d'erreur si échec
        """
        if success and lot_info:
            self.info(f"LOT DÉTECTÉ - Méthode: {method} - Lot: {lot_info[0]} - {lot_info[1]}")
            if pattern:
                self.debug(f"Pattern utilisé: {pattern}")
        else:
            self.warning(f"LOT NON DÉTECTÉ - Méthode: {method}" + (f" - Erreur: {error}" if error else ""))
    
    def log_lot_creation(self, lot_num: str, lot_name: str, source: str, default: bool = False):
        """
        Log la création d'un lot
        
        Args:
            lot_num: Numéro du lot
            lot_name: Nom du lot
            source: Source du lot ('detection', 'parameter', 'default')
            default: Si c'est un lot par défaut
        """
        if default:
            self.warning(f"LOT PAR DÉFAUT CRÉÉ - Lot: {lot_num} - {lot_name} - Source: {source}")
        else:
            self.info(f"LOT CRÉÉ - Lot: {lot_num} - {lot_name} - Source: {source}")
    
    def log_section_detection(self, success: bool, row_index: int, section_info: Dict = None, 
                              pattern_type: str = None, raw_text: str = None):
        """
        Log détaillé du processus de détection de section
        
        Args:
            success: Si la détection a réussi
            row_index: Index de la ligne dans le fichier Excel
            section_info: Informations sur la section si détectée
            pattern_type: Type de pattern utilisé ('numbered', 'uppercase', 'roman', 'letter')
            raw_text: Texte brut analysé
        """
        if success and section_info:
            self.info(f"SECTION DÉTECTÉE - Ligne {row_index+1} - Numéro: {section_info.get('numero_section')} - Titre: {section_info.get('titre_section')}")
            self.debug(f"Type de pattern: {pattern_type} - Niveau: {section_info.get('niveau_hierarchique', 1)}")
        else:
            if raw_text:
                self.debug(f"SECTION NON DÉTECTÉE - Ligne {row_index+1} - Texte: '{raw_text[:50]}...' - Pas de pattern correspondant")
    
    def log_section_creation(self, section_num: str, section_title: str, niveau: int, default: bool = False):
        """
        Log la création d'une section
        
        Args:
            section_num: Numéro de la section
            section_title: Titre de la section
            niveau: Niveau hiérarchique
            default: Si c'est une section par défaut
        """
        if default:
            self.warning(f"SECTION PAR DÉFAUT CRÉÉE - Numéro: {section_num} - Titre: {section_title} - Niveau: {niveau}")
        else:
            self.info(f"SECTION CRÉÉE - Numéro: {section_num} - Titre: {section_title} - Niveau: {niveau}")
    
    def log_element_detection(self, row_index: int, designation: str, has_price: bool, has_unit: bool):
        """
        Log la détection d'un élément d'ouvrage
        
        Args:
            row_index: Index de la ligne
            designation: Désignation de l'élément
            has_price: Si l'élément a un prix
            has_unit: Si l'élément a une unité
        """
        self.debug(f"ÉLÉMENT DÉTECTÉ - Ligne {row_index+1} - '{designation[:50]}...' - Prix: {'Oui' if has_price else 'Non'} - Unité: {'Oui' if has_unit else 'Non'}")
    
    def log_element_without_section(self, row_index: int, designation: str):
        """
        Log un élément détecté sans section parente
        
        Args:
            row_index: Index de la ligne
            designation: Désignation de l'élément
        """
        self.warning(f"ÉLÉMENT SANS SECTION - Ligne {row_index+1} - '{designation[:50]}...' - Section par défaut requise")

    def close(self):
        """Ferme proprement les handlers de log"""
        self.file_handler.close()
        self.file_logger.removeHandler(self.file_handler)
        

# Fonction pour obtenir le logger
def get_import_logger(file_path: str) -> ImportLogger:
    """
    Crée et retourne un logger d'import pour un fichier spécifique
    
    Args:
        file_path: Chemin du fichier DPGF
        
    Returns:
        Logger configuré pour ce fichier
    """
    return ImportLogger(file_path)
