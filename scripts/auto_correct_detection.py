"""
Outil de correction automatique pour les problèmes de détection de lots et sections
dans les imports DPGF déjà effectués en base de données.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
from tqdm import tqdm
import re
import json

# Ajouter le répertoire principal au path pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.session import engine, SessionLocal
from app.db.models.element_ouvrage import ElementOuvrage
from app.db.models.section import Section
from app.db.models.lot import Lot
from app.db.models.dpgf import DPGF
from app.db.models.client import Client
from app.schemas.dpgf import DPGFCreate, DPGFUpdate
from app.schemas.lot import LotCreate, LotUpdate
from app.schemas.section import SectionCreate, SectionUpdate
from app.crud.dpgf import crud_dpgf
from app.crud.lot import crud_lot
from app.crud.section import crud_section
from app.crud.element_ouvrage import crud_element_ouvrage
from scripts.import_complete import ExcelParser, ColumnMapping, ErrorReporter, GeminiProcessor
from scripts.enhanced_logging import get_import_logger


class DPGFCorrector:
    """
    Outil de correction automatique pour les problèmes de détection
    dans les imports DPGF déjà effectués.
    """
    
    def __init__(self, fix_lots: bool = True, fix_sections: bool = True, 
                dry_run: bool = True, use_gemini: bool = False,
                log_file: str = "correction_log.json"):
        """
        Initialise le correcteur
        
        Args:
            fix_lots: Corriger les problèmes de détection de lots
            fix_sections: Corriger les problèmes de détection de sections
            dry_run: Si True, ne fait pas de modifications en base de données
            use_gemini: Utiliser l'API Google Gemini pour la détection
            log_file: Fichier de log pour les corrections effectuées
        """
        self.fix_lots = fix_lots
        self.fix_sections = fix_sections
        self.dry_run = dry_run
        self.use_gemini = use_gemini
        self.log_file = log_file
        
        # Pour les logs
        self.corrections = {
            "lots": [],
            "sections": [],
            "dry_run": dry_run
        }
        
        # Composants réutilisables
        self.column_mapper = ColumnMapping()
        self.error_reporter = ErrorReporter()
        self.gemini_processor = GeminiProcessor(cache_path="cache/gemini_patterns.pkl") if use_gemini else None
        
        # Session de base de données
        self.db = SessionLocal()
        
        print(f"📊 Correcteur initialisé (dry_run={dry_run}, fix_lots={fix_lots}, fix_sections={fix_sections})")
    
    def __del__(self):
        """Fermeture propre de la session DB"""
        if hasattr(self, 'db'):
            self.db.close()
    
    def scan_db_for_issues(self):
        """
        Scanne la base de données pour identifier les problèmes
        
        Returns:
            Tuple (problèmes de lots, problèmes de sections)
        """
        lot_issues = []
        section_issues = []
        
        print("\n🔍 Analyse de la base de données pour détecter les problèmes...")
        
        try:
            # 1. Identifier les DPGFs sans lots ou avec lots par défaut
            dpgfs = self.db.query(DPGF).all()
            print(f"📊 {len(dpgfs)} DPGFs trouvés en base de données")
            
            for dpgf in tqdm(dpgfs, desc="Analyse des DPGFs"):
                # Vérifier les lots
                lots = self.db.query(Lot).filter(Lot.dpgf_id == dpgf.id).all()
                
                # Problème de lot: aucun lot ou lot 00 (default)
                if not lots or (len(lots) == 1 and lots[0].numero == "00"):
                    # Vérifier si le fichier existe encore
                    file_path = Path(dpgf.filepath) if dpgf.filepath else None
                    
                    if file_path and file_path.exists():
                        lot_issues.append({
                            "dpgf_id": dpgf.id,
                            "dpgf_nom": dpgf.nom,
                            "file_path": str(file_path),
                            "lots": [(lot.numero, lot.nom) for lot in lots] if lots else []
                        })
                
                # Vérifier les sections
                for lot in lots:
                    # Compter les éléments sans section
                    elements_sans_section = self.db.query(ElementOuvrage).filter(
                        ElementOuvrage.lot_id == lot.id,
                        ElementOuvrage.section_id == None
                    ).count()
                    
                    # Problème: éléments sans section ou trop peu de sections
                    sections = self.db.query(Section).filter(Section.lot_id == lot.id).all()
                    if elements_sans_section > 0 or (len(sections) <= 1 and 
                                                    (not sections or sections[0].numero == "00")):
                        # Vérifier si le fichier existe encore
                        file_path = Path(dpgf.filepath) if dpgf.filepath else None
                        
                        if file_path and file_path.exists():
                            section_issues.append({
                                "dpgf_id": dpgf.id,
                                "lot_id": lot.id,
                                "lot_numero": lot.numero,
                                "dpgf_nom": dpgf.nom,
                                "file_path": str(file_path),
                                "sections_count": len(sections),
                                "elements_sans_section": elements_sans_section
                            })
            
            print(f"\n✓ Analyse terminée:")
            print(f"  - {len(lot_issues)} DPGFs avec problèmes de détection de lot")
            print(f"  - {len(section_issues)} Lots avec problèmes de détection de section")
            
            return lot_issues, section_issues
            
        except Exception as e:
            print(f"⚠️ Erreur lors de l'analyse de la base de données: {e}")
            return [], []
    
    def fix_lot_detection(self, lot_issues: List[Dict]):
        """
        Corrige les problèmes de détection de lot
        
        Args:
            lot_issues: Liste des problèmes de lot à corriger
        """
        if not lot_issues:
            print("\n✓ Aucun problème de lot à corriger")
            return
        
        print(f"\n🔧 Correction des problèmes de lots ({len(lot_issues)} DPGFs)...")
        
        for issue in tqdm(lot_issues, desc="Correction des lots"):
            dpgf_id = issue["dpgf_id"]
            file_path = issue["file_path"]
            
            try:
                # Relancer la détection de lot sur le fichier
                lots = self._redetect_lots(file_path)
                
                if not lots:
                    print(f"⚠️ Impossible de détecter un lot pour {Path(file_path).name}")
                    continue
                
                # Supprimer les lots par défaut si nécessaire
                existing_lots = self.db.query(Lot).filter(Lot.dpgf_id == dpgf_id).all()
                default_lots = [lot for lot in existing_lots if lot.numero == "00"]
                
                # Traiter les éléments rattachés aux lots par défaut
                correction = {
                    "dpgf_id": dpgf_id,
                    "file_path": file_path,
                    "old_lots": [(lot.numero, lot.nom) for lot in existing_lots],
                    "new_lots": lots,
                    "elements_moved": 0
                }
                
                if not self.dry_run:
                    for lot_num, lot_nom in lots:
                        # Créer le nouveau lot s'il n'existe pas
                        existing_lot = next((lot for lot in existing_lots if lot.numero == lot_num), None)
                        
                        if existing_lot:
                            # Mettre à jour le nom du lot si nécessaire
                            if existing_lot.nom != lot_nom:
                                existing_lot.nom = lot_nom
                                self.db.add(existing_lot)
                        else:
                            # Créer un nouveau lot
                            nouveau_lot = Lot(
                                dpgf_id=dpgf_id,
                                numero=lot_num,
                                nom=lot_nom
                            )
                            self.db.add(nouveau_lot)
                            self.db.flush()  # Pour obtenir l'ID généré
                            
                            # Si c'est le seul nouveau lot et qu'il y a un lot par défaut,
                            # déplacer les éléments du lot par défaut vers le nouveau lot
                            if len(lots) == 1 and default_lots:
                                for default_lot in default_lots:
                                    elements = self.db.query(ElementOuvrage).filter(
                                        ElementOuvrage.lot_id == default_lot.id
                                    ).all()
                                    
                                    # Déplacer les éléments vers le nouveau lot
                                    for element in elements:
                                        element.lot_id = nouveau_lot.id
                                        self.db.add(element)
                                    
                                    correction["elements_moved"] += len(elements)
                                    
                                    # Supprimer le lot par défaut
                                    self.db.delete(default_lot)
                    
                    # Commit les changements
                    self.db.commit()
                
                self.corrections["lots"].append(correction)
                
            except Exception as e:
                print(f"⚠️ Erreur lors de la correction du lot pour {Path(file_path).name}: {e}")
                self.db.rollback()
    
    def fix_section_detection(self, section_issues: List[Dict]):
        """
        Corrige les problèmes de détection de section
        
        Args:
            section_issues: Liste des problèmes de section à corriger
        """
        if not section_issues:
            print("\n✓ Aucun problème de section à corriger")
            return
        
        print(f"\n🔧 Correction des problèmes de sections ({len(section_issues)} lots)...")
        
        for issue in tqdm(section_issues, desc="Correction des sections"):
            dpgf_id = issue["dpgf_id"]
            lot_id = issue["lot_id"]
            file_path = issue["file_path"]
            
            try:
                # Récupérer les informations du lot
                lot = self.db.query(Lot).filter(Lot.id == lot_id).first()
                if not lot:
                    print(f"⚠️ Lot {lot_id} non trouvé")
                    continue
                
                # Relancer la détection de sections sur le fichier
                sections, elements = self._redetect_sections(file_path, lot.numero)
                
                if not sections:
                    print(f"⚠️ Impossible de détecter des sections pour le lot {lot.numero} dans {Path(file_path).name}")
                    continue
                
                # Récupérer les sections existantes
                existing_sections = self.db.query(Section).filter(Section.lot_id == lot_id).all()
                existing_section_ids = {s.id: s for s in existing_sections}
                
                correction = {
                    "dpgf_id": dpgf_id,
                    "lot_id": lot_id,
                    "file_path": file_path,
                    "old_sections": len(existing_sections),
                    "new_sections": len(sections),
                    "elements_reassigned": 0
                }
                
                if not self.dry_run:
                    # Supprimer les sections par défaut si nécessaire
                    default_sections = [s for s in existing_sections if s.numero == "00" or not s.numero]
                    
                    # Créer les nouvelles sections
                    section_mapping = {}  # Mappage ancien_id -> nouveau_id
                    
                    for section_data in sections:
                        # Vérifier si une section similaire existe déjà
                        existing = next((s for s in existing_sections 
                                       if s.numero == section_data["numero"] and
                                        s.titre == section_data["titre"]), None)
                        
                        if existing:
                            # Conserver l'ID existant
                            section_mapping[existing.id] = existing.id
                        else:
                            # Créer une nouvelle section
                            nouvelle_section = Section(
                                lot_id=lot_id,
                                numero=section_data["numero"],
                                titre=section_data["titre"],
                                niveau_hierarchique=section_data["niveau_hierarchique"]
                            )
                            self.db.add(nouvelle_section)
                            self.db.flush()  # Pour obtenir l'ID généré
                            
                            # Si c'est une nouvelle section, la mappage pointe vers elle-même
                            section_mapping[nouvelle_section.id] = nouvelle_section.id
                    
                    # Récupérer les éléments sans section ou avec section par défaut
                    elements_orphelins = self.db.query(ElementOuvrage).filter(
                        (ElementOuvrage.lot_id == lot_id) &
                        ((ElementOuvrage.section_id == None) |
                         (ElementOuvrage.section_id.in_([s.id for s in default_sections])))
                    ).all()
                    
                    # Assigner les éléments orphelins à la première section si elle existe
                    if sections and elements_orphelins:
                        first_section_id = self.db.query(Section).filter(
                            (Section.lot_id == lot_id) &
                            (Section.numero != "00") &
                            (Section.numero != None)
                        ).first().id
                        
                        for element in elements_orphelins:
                            element.section_id = first_section_id
                            self.db.add(element)
                        
                        correction["elements_reassigned"] = len(elements_orphelins)
                    
                    # Supprimer les sections par défaut si elles sont vides
                    for section in default_sections:
                        elements_count = self.db.query(ElementOuvrage).filter(
                            ElementOuvrage.section_id == section.id
                        ).count()
                        
                        if elements_count == 0:
                            self.db.delete(section)
                    
                    # Commit les changements
                    self.db.commit()
                
                self.corrections["sections"].append(correction)
                
            except Exception as e:
                print(f"⚠️ Erreur lors de la correction des sections pour {Path(file_path).name}: {e}")
                self.db.rollback()
    
    def _redetect_lots(self, file_path: str) -> List[Tuple[str, str]]:
        """
        Relance la détection de lot sur un fichier
        
        Args:
            file_path: Chemin vers le fichier DPGF
            
        Returns:
            Liste des lots détectés (num, nom)
        """
        logger = get_import_logger(file_path)
        
        try:
            # Créer le parser
            parser = ExcelParser(file_path, self.column_mapper, self.error_reporter, logger)
            
            # Détecter les lots
            lots = parser.find_lot_headers()
            
            return lots
        except Exception as e:
            logger.error(f"Erreur lors de la redétection des lots: {e}")
            return []
    
    def _redetect_sections(self, file_path: str, lot_numero: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Relance la détection des sections sur un fichier
        
        Args:
            file_path: Chemin vers le fichier DPGF
            lot_numero: Numéro du lot pour filtrer les sections
            
        Returns:
            Tuple (sections, elements)
        """
        logger = get_import_logger(file_path)
        
        try:
            # Créer le parser
            parser = ExcelParser(file_path, self.column_mapper, self.error_reporter, logger)
            
            # Trouver la ligne d'en-tête
            header_row = parser.find_header_row()
            
            if header_row is None:
                logger.error("Aucune ligne d'en-tête trouvée")
                return [], []
            
            # Détecter les colonnes
            parser.detect_column_indices(header_row)
            
            # Détecter les sections et éléments
            items = parser.detect_sections_and_elements(header_row)
            
            # Séparer les sections et éléments
            sections = [item["data"] for item in items if item["type"] == "section"]
            elements = [item["data"] for item in items if item["type"] == "element"]
            
            return sections, elements
        except Exception as e:
            logger.error(f"Erreur lors de la redétection des sections: {e}")
            return [], []
    
    def save_corrections_log(self):
        """
        Sauvegarde le log des corrections effectuées
        """
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.corrections, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Log des corrections sauvegardé dans {self.log_file}")
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde du log: {e}")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Correction automatique des problèmes d'import DPGF")
    parser.add_argument('--fix-lots', action='store_true', 
                       help="Corriger les problèmes de détection de lot")
    parser.add_argument('--fix-sections', action='store_true',
                       help="Corriger les problèmes de détection de section")
    parser.add_argument('--use-gemini', action='store_true',
                       help="Utiliser l'API Google Gemini pour la détection")
    parser.add_argument('--apply', action='store_true',
                       help="Appliquer les corrections (sinon, mode simulation)")
    parser.add_argument('--log-file', type=str, default="correction_log.json",
                       help="Fichier de log pour les corrections")
    
    args = parser.parse_args()
    
    # Si aucune option n'est spécifiée, activer les deux par défaut
    if not args.fix_lots and not args.fix_sections:
        args.fix_lots = True
        args.fix_sections = True
    
    dry_run = not args.apply
    if dry_run:
        print("\n⚠️ MODE SIMULATION: aucune modification ne sera appliquée à la base de données")
        print("Utilisez --apply pour appliquer les modifications")
    
    try:
        corrector = DPGFCorrector(
            fix_lots=args.fix_lots,
            fix_sections=args.fix_sections,
            dry_run=dry_run,
            use_gemini=args.use_gemini,
            log_file=args.log_file
        )
        
        # Scanner la base de données pour les problèmes
        lot_issues, section_issues = corrector.scan_db_for_issues()
        
        # Appliquer les corrections
        if args.fix_lots:
            corrector.fix_lot_detection(lot_issues)
        
        if args.fix_sections:
            corrector.fix_section_detection(section_issues)
        
        # Sauvegarder le log des corrections
        corrector.save_corrections_log()
        
        print("\n✅ Traitement terminé avec succès!")
        
    except Exception as e:
        print(f"⚠️ Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
