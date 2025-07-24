"""
Module d'amélioration des patterns de détection pour les lots et sections DPGF.
Ce script utilise les recommandations générées par detection_evaluator.py pour
mettre à jour la logique de détection dans import_complete.py.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil

# Le chemin du fichier import_complete.py
IMPORT_COMPLETE_PATH = Path("scripts/import_complete.py")


class PatternUpdater:
    """
    Met à jour les patterns de détection dans le code source
    """
    
    def __init__(self, evaluation_report: str):
        """
        Initialise le modifieur de patterns
        
        Args:
            evaluation_report: Chemin du rapport d'évaluation JSON
        """
        self.report_path = Path(evaluation_report)
        self.lot_patterns_to_add = []
        self.section_patterns_to_add = []
        self.report_data = None
        
        # Charger le rapport d'évaluation
        if self.report_path.exists():
            try:
                with open(self.report_path, 'r', encoding='utf-8') as f:
                    self.report_data = json.load(f)
                print(f"✓ Rapport d'évaluation chargé: {self.report_path}")
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement du rapport: {e}")
                sys.exit(1)
        else:
            print(f"⚠️ Rapport d'évaluation non trouvé: {self.report_path}")
            sys.exit(1)
        
        # Extraire les recommandations
        self._extract_recommendations()
    
    def _extract_recommendations(self):
        """
        Extrait les recommandations de patterns du rapport
        """
        if not self.report_data:
            return
        
        # Récupérer les recommandations de lot
        lot_recommendations = self.report_data.get("lot_patterns", {}).get("suggested_patterns", [])
        for rec in lot_recommendations:
            pattern_type = rec.get("type")
            pattern = rec.get("pattern")
            description = rec.get("description")
            
            if pattern_type and pattern and description:
                self.lot_patterns_to_add.append({
                    "type": pattern_type,
                    "pattern": pattern,
                    "description": description
                })
        
        # Récupérer les recommandations de section
        section_recommendations = self.report_data.get("section_patterns", {}).get("suggested_patterns", [])
        for rec in section_recommendations:
            pattern_type = rec.get("type")
            pattern = rec.get("pattern")
            description = rec.get("description")
            
            if pattern_type and pattern and description:
                self.section_patterns_to_add.append({
                    "type": pattern_type,
                    "pattern": pattern,
                    "description": description
                })
        
        print(f"✓ {len(self.lot_patterns_to_add)} patterns de lot et {len(self.section_patterns_to_add)} patterns de section recommandés")
    
    def update_patterns(self, backup: bool = True):
        """
        Met à jour les patterns dans le fichier import_complete.py
        
        Args:
            backup: Si True, crée une sauvegarde du fichier avant modification
        """
        if not IMPORT_COMPLETE_PATH.exists():
            print(f"⚠️ Fichier import_complete.py non trouvé: {IMPORT_COMPLETE_PATH}")
            return False
        
        # Créer une sauvegarde
        if backup:
            backup_path = IMPORT_COMPLETE_PATH.with_suffix('.py.bak')
            try:
                shutil.copy2(IMPORT_COMPLETE_PATH, backup_path)
                print(f"✓ Sauvegarde créée: {backup_path}")
            except Exception as e:
                print(f"⚠️ Erreur lors de la création de la sauvegarde: {e}")
                return False
        
        # Lire le contenu du fichier
        try:
            with open(IMPORT_COMPLETE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"⚠️ Erreur de lecture du fichier source: {e}")
            return False
        
        # Mise à jour des patterns de lot
        if self.lot_patterns_to_add:
            content = self._update_lot_patterns(content)
        
        # Mise à jour des patterns de section
        if self.section_patterns_to_add:
            content = self._update_section_patterns(content)
        
        # Écrire le contenu mis à jour
        try:
            with open(IMPORT_COMPLETE_PATH, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fichier mis à jour: {IMPORT_COMPLETE_PATH}")
            return True
        except Exception as e:
            print(f"⚠️ Erreur d'écriture du fichier: {e}")
            return False
    
    def _update_lot_patterns(self, content: str) -> str:
        """
        Met à jour les patterns de détection de lot
        
        Args:
            content: Contenu du fichier source
            
        Returns:
            Contenu mis à jour
        """
        # Identifier la section des patterns de lot (extract_lot_from_filename)
        lot_patterns_marker = "patterns = ["
        lot_patterns_end = "]"
        
        # Trouver la position de la liste des patterns de lot
        function_start = content.find("def extract_lot_from_filename")
        patterns_start = content.find(lot_patterns_marker, function_start)
        
        if patterns_start == -1:
            print("⚠️ Section des patterns de lot non trouvée")
            return content
        
        # Trouver la fin de la liste des patterns
        patterns_start += len(lot_patterns_marker)
        patterns_end = content.find(lot_patterns_end, patterns_start)
        
        if patterns_end == -1:
            print("⚠️ Fin de la liste des patterns de lot non trouvée")
            return content
        
        # Extraire la liste des patterns existants
        existing_patterns = content[patterns_start:patterns_end].strip()
        
        # Ajouter les nouveaux patterns
        new_patterns = existing_patterns
        for pattern in self.lot_patterns_to_add:
            pattern_desc = pattern["description"]
            pattern_regex = pattern["pattern"]
            
            # Vérifier que le pattern n'existe pas déjà (vérification simple)
            if pattern_regex not in new_patterns:
                new_pattern = f',\n            # {pattern_desc}\n            r\'{pattern_regex}\''
                new_patterns += new_pattern
                print(f"+ Ajout du pattern de lot: {pattern_desc}")
        
        # Remplacer la liste des patterns
        updated_content = content[:patterns_start] + new_patterns + content[patterns_end:]
        
        return updated_content
    
    def _update_section_patterns(self, content: str) -> str:
        """
        Met à jour les patterns de détection de section
        
        Args:
            content: Contenu du fichier source
            
        Returns:
            Contenu mis à jour
        """
        # Identifier la section des patterns de section (dans detect_sections_and_elements)
        section_marker = "section_patterns = ["
        section_end = "]"
        
        # Trouver la position de la liste des patterns de section
        function_start = content.find("def detect_sections_and_elements")
        patterns_start = content.find(section_marker, function_start)
        
        if patterns_start == -1:
            print("⚠️ Section des patterns de section non trouvée")
            return content
        
        # Trouver la fin de la liste des patterns
        patterns_start += len(section_marker)
        patterns_end = content.find(section_end, patterns_start)
        
        if patterns_end == -1:
            print("⚠️ Fin de la liste des patterns de section non trouvée")
            return content
        
        # Extraire la liste des patterns existants
        existing_patterns = content[patterns_start:patterns_end].strip()
        
        # Ajouter les nouveaux patterns
        new_patterns = existing_patterns
        for pattern in self.section_patterns_to_add:
            pattern_desc = pattern["description"]
            pattern_regex = pattern["pattern"]
            
            # Vérifier que le pattern n'existe pas déjà (vérification simple)
            if pattern_regex not in new_patterns:
                new_pattern = f',\n            # {pattern_desc}\n            r\'{pattern_regex}\''
                new_patterns += new_pattern
                print(f"+ Ajout du pattern de section: {pattern_desc}")
        
        # Remplacer la liste des patterns
        updated_content = content[:patterns_start] + new_patterns + content[patterns_end:]
        
        return updated_content


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Mise à jour des patterns de détection DPGF")
    parser.add_argument('--report', '-r', type=str, required=True,
                       help="Chemin du rapport d'évaluation JSON")
    parser.add_argument('--no-backup', action='store_true',
                       help="Ne pas créer de sauvegarde du fichier original")
    
    args = parser.parse_args()
    
    updater = PatternUpdater(args.report)
    updater.update_patterns(backup=not args.no_backup)


if __name__ == "__main__":
    main()
