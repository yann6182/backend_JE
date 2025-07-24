"""
Évaluateur des capacités de détection des lots et sections dans les fichiers DPGF.
Ce script teste et analyse les patterns existants, puis suggère des améliorations 
ou de nouveaux patterns à ajouter pour améliorer la détection.
"""

import os
import sys
import json
import argparse
import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from tqdm import tqdm
import matplotlib.pyplot as plt

# Ajouter le répertoire principal au path pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.import_complete import ExcelParser, ColumnMapping, ErrorReporter, GeminiProcessor
from scripts.enhanced_logging import get_import_logger, ImportLogger

# Désactiver les avertissements Pandas
pd.options.mode.chained_assignment = None


class DetectionPatternEvaluator:
    """
    Évaluateur des patterns de détection de lots et sections dans les fichiers DPGF.
    Permet d'analyser l'efficacité des patterns existants et de suggérer des améliorations.
    """
    
    def __init__(self, directory: str, use_gemini: bool = False):
        """
        Initialise l'évaluateur
        
        Args:
            directory: Répertoire contenant les fichiers DPGF à analyser
            use_gemini: Utiliser l'API Google Gemini pour la détection
        """
        self.directory = Path(directory)
        self.files = [f for f in self.directory.glob("*.xlsx") if not f.name.startswith("~$")]
        self.total_files = len(self.files)
        self.use_gemini = use_gemini
        self.test_results = []
        self.lot_patterns_used = {}
        self.section_patterns_used = {}
        self.missed_lot_examples = []
        self.missed_section_examples = []
        self.suggested_lot_patterns = []
        self.suggested_section_patterns = []
        
        # Composants réutilisables
        self.column_mapper = ColumnMapping()
        self.error_reporter = ErrorReporter()
        
        print(f"📊 Évaluateur initialisé avec {self.total_files} fichiers DPGF")
    
    def analyze_all_files(self):
        """
        Analyse tous les fichiers pour évaluer la détection
        """
        print("\n🔍 Analyse des capacités de détection sur les fichiers DPGF...")
        
        for file_path in tqdm(self.files, desc="Évaluation des fichiers"):
            try:
                self._analyze_single_file(str(file_path))
            except Exception as e:
                print(f"⚠️ Erreur lors de l'analyse du fichier {file_path.name}: {e}")
    
    def _analyze_single_file(self, file_path: str):
        """
        Analyse un fichier spécifique pour évaluer la détection
        
        Args:
            file_path: Chemin complet vers le fichier DPGF
        """
        # Logger pour ce fichier
        logger = get_import_logger(file_path)
        
        # Créer le parser avec logging amélioré
        parser = ExcelParser(file_path, self.column_mapper, self.error_reporter, logger)
        gemini_processor = GeminiProcessor(cache_path="cache/gemini_patterns.pkl") if self.use_gemini else None
        
        # Récupérer les patterns existants pour les comparer
        lot_pattern_extractor = LotPatternExtractor(parser, gemini_processor, logger)
        section_pattern_extractor = SectionPatternExtractor(parser, logger)
        
        # 1. Tester la détection de lot
        lots = parser.find_lot_headers()
        lot_detection_result = lot_pattern_extractor.evaluate_detection()
        
        # 2. Tester la détection des sections
        header_row = parser.find_header_row()
        
        # Détecter les colonnes si pas encore fait
        if not parser.headers_detected:
            parser.detect_column_indices(header_row)
        
        # Évaluer la détection des sections
        items = parser.detect_sections_and_elements(header_row)
        sections = [item for item in items if item['type'] == 'section']
        elements = [item for item in items if item['type'] == 'element']
        
        section_detection_result = section_pattern_extractor.evaluate_detection(
            items, header_row, parser.df
        )
        
        # Enregistrer les résultats pour cette analyse
        file_result = {
            "file": Path(file_path).name,
            "lot_detection": {
                "success": bool(lots),
                "lots_found": lots,
                "patterns_used": lot_detection_result["patterns_used"],
                "patterns_missed": lot_detection_result["patterns_missed"],
                "examples_missed": lot_detection_result["missed_examples"]
            },
            "section_detection": {
                "success": len(sections) > 0,
                "sections_found": len(sections),
                "elements_found": len(elements),
                "patterns_used": section_detection_result["patterns_used"],
                "patterns_missed": section_detection_result["patterns_missed"],
                "examples_missed": section_detection_result["missed_examples"],
                "false_positives": section_detection_result["false_positives"]
            }
        }
        
        # Mettre à jour les stats globales
        self.test_results.append(file_result)
        
        # Mettre à jour les compteurs de patterns utilisés
        for pattern_name in file_result["lot_detection"]["patterns_used"]:
            self.lot_patterns_used[pattern_name] = self.lot_patterns_used.get(pattern_name, 0) + 1
        
        for pattern_name in file_result["section_detection"]["patterns_used"]:
            self.section_patterns_used[pattern_name] = self.section_patterns_used.get(pattern_name, 0) + 1
        
        # Collecter les exemples manqués
        self.missed_lot_examples.extend(file_result["lot_detection"]["examples_missed"])
        self.missed_section_examples.extend(file_result["section_detection"]["examples_missed"])
    
    def generate_report(self, output_file: str = "detection_evaluation_report.json"):
        """
        Génère un rapport complet sur les performances de détection
        
        Args:
            output_file: Fichier de sortie pour le rapport JSON
        """
        if not self.test_results:
            print("⚠️ Aucun résultat d'analyse disponible. Exécutez d'abord analyze_all_files().")
            return
        
        # Statistiques générales
        lot_success = sum(1 for r in self.test_results if r["lot_detection"]["success"])
        section_success = sum(1 for r in self.test_results if r["section_detection"]["success"])
        
        # Calculer les recommandations
        self._generate_pattern_recommendations()
        
        report = {
            "summary": {
                "files_analyzed": self.total_files,
                "lot_detection_success_rate": round(lot_success / self.total_files * 100, 2),
                "section_detection_success_rate": round(section_success / self.total_files * 100, 2)
            },
            "lot_patterns": {
                "patterns_used": self.lot_patterns_used,
                "examples_missed": self.missed_lot_examples[:20],  # Limité aux 20 premiers exemples
                "suggested_patterns": self.suggested_lot_patterns
            },
            "section_patterns": {
                "patterns_used": self.section_patterns_used,
                "examples_missed": self.missed_section_examples[:20],
                "suggested_patterns": self.suggested_section_patterns
            },
            "file_details": self.test_results
        }
        
        # Sauvegarder le rapport JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # Afficher un résumé
        print(f"\n📊 RÉSUMÉ D'ÉVALUATION DE LA DÉTECTION")
        print(f"Fichiers analysés: {self.total_files}")
        print(f"Détection de lot réussie: {lot_success}/{self.total_files} ({lot_success/self.total_files*100:.1f}%)")
        print(f"Détection de sections réussie: {section_success}/{self.total_files} ({section_success/self.total_files*100:.1f}%)")
        
        print("\n🔍 PATTERNS DE LOT LES PLUS UTILISÉS:")
        for pattern, count in sorted(self.lot_patterns_used.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"- {pattern}: {count} occurrences ({count/self.total_files*100:.1f}%)")
        
        print("\n🔍 PATTERNS DE SECTION LES PLUS UTILISÉS:")
        for pattern, count in sorted(self.section_patterns_used.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"- {pattern}: {count} occurrences")
        
        print(f"\n📋 Rapport complet sauvegardé dans {output_file}")
        
        # Générer des visualisations
        self._generate_visualizations()
    
    def _generate_pattern_recommendations(self):
        """
        Génère des recommandations de nouveaux patterns basés sur les exemples manqués
        """
        # Pour les lots
        if self.missed_lot_examples:
            lot_pattern_gen = LotPatternRecommender(self.missed_lot_examples)
            self.suggested_lot_patterns = lot_pattern_gen.generate_recommendations()
        
        # Pour les sections
        if self.missed_section_examples:
            section_pattern_gen = SectionPatternRecommender(self.missed_section_examples)
            self.suggested_section_patterns = section_pattern_gen.generate_recommendations()
    
    def _generate_visualizations(self):
        """
        Génère des graphiques pour visualiser les résultats
        """
        try:
            # Graphique pour la détection de lots
            plt.figure(figsize=(10, 6))
            patterns = list(self.lot_patterns_used.keys())
            counts = list(self.lot_patterns_used.values())
            
            if patterns:  # Vérifier qu'il y a des données à afficher
                plt.bar(range(len(patterns)), counts)
                plt.xticks(range(len(patterns)), patterns, rotation=45, ha='right')
                plt.title('Utilisation des patterns de détection de lot')
                plt.tight_layout()
                plt.savefig('lot_pattern_usage.png')
                print("📊 Graphique d'utilisation des patterns de lot sauvegardé (lot_pattern_usage.png)")
            
            # Graphique pour la détection de sections
            plt.figure(figsize=(10, 6))
            patterns = list(self.section_patterns_used.keys())
            counts = list(self.section_patterns_used.values())
            
            if patterns:
                plt.bar(range(len(patterns)), counts)
                plt.xticks(range(len(patterns)), patterns, rotation=45, ha='right')
                plt.title('Utilisation des patterns de détection de section')
                plt.tight_layout()
                plt.savefig('section_pattern_usage.png')
                print("📊 Graphique d'utilisation des patterns de section sauvegardé (section_pattern_usage.png)")
        
        except Exception as e:
            print(f"⚠️ Erreur lors de la génération des graphiques: {e}")


class LotPatternExtractor:
    """
    Extracteur et évaluateur des patterns de détection de lot
    """
    
    def __init__(self, parser, gemini_processor, logger):
        """
        Initialise l'extracteur
        
        Args:
            parser: ExcelParser pour accéder aux méthodes de détection
            gemini_processor: Processeur Gemini ou None si non activé
            logger: Logger pour le suivi des opérations
        """
        self.parser = parser
        self.gemini_processor = gemini_processor
        self.logger = logger
        self.file_path = parser.file_path
        self.filename = Path(parser.file_path).name
        
        # Les patterns existants dans ExcelParser.extract_lot_from_filename
        self.filename_patterns = [
            ("LOT XX - DPGF - NOM", r'lot\s*(\d{1,2})\s*-\s*(?:dpgf|devis|bpu|dqe)\s*-\s*([\w\s\-&°]+)'),
            ("DPGF-Lot XX NOM", r'dpgf\s*[-_]?\s*lot\s*(\d{1,2})\s+([\w\s\-&°]+)'),
            ("LOT XX - NOM", r'lot\s*(\d{1,2})\s*-\s*([\w\s\-&°]+)'),
            ("XXX DPGF Lot X - NOM", r'^\d+\s+dpgf\s+lot\s*(\d{1,2})\s*-\s*([\w\s\-&°]+)'),
            ("DPGF Lot X - NOM", r'dpgf\s+lot\s*(\d{1,2})\s*-\s*([\w\s\-&°]+)'),
            ("LotXX_NOM", r'lot\s*(\d{1,2})[_\-\s]+([\w\s\-&°]+)'),
            ("XXX - DPGF -LotX", r'-\s*dpgf\s*-?\s*lot\s*(\d{1,2})'),
            ("LotX", r'lot\s*(\d{1,2})(?!\d)')
        ]
    
    def evaluate_detection(self) -> Dict:
        """
        Évalue la détection de lot sur le fichier
        
        Returns:
            Résultat de l'évaluation
        """
        # Patterns détectés
        patterns_used = []
        patterns_missed = []
        missed_examples = []
        
        # 1. Tester les patterns de nom de fichier
        filename = Path(self.file_path).stem
        found_from_filename = False
        
        for pattern_name, pattern in self.filename_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                patterns_used.append(f"filename:{pattern_name}")
                found_from_filename = True
                break
        
        if not found_from_filename:
            patterns_missed.append("filename")
            missed_examples.append({"type": "filename", "text": filename})
        
        # 2. Tester la détection par contenu
        if not found_from_filename:
            content_lots = self._find_lots_in_content()
            if content_lots:
                patterns_used.append("content")
            else:
                patterns_missed.append("content")
                
                # Ajouter des exemples de contenu pour analyse
                try:
                    df = self.parser.df.iloc[:20]  # Les 20 premières lignes
                    for _, row in df.iterrows():
                        row_text = ' '.join(str(cell) for cell in row if pd.notna(cell))
                        if row_text and re.search(r'lot|devis|dpgf', row_text.lower()):
                            missed_examples.append({"type": "content", "text": row_text})
                except Exception:
                    pass
        
        # 3. Tester la détection par Gemini si disponible
        if self.gemini_processor and not (found_from_filename or content_lots):
            try:
                gemini_result = self.gemini_processor.detect_lot_info(self.file_path, self.filename)
                if gemini_result:
                    patterns_used.append("gemini")
                else:
                    patterns_missed.append("gemini")
            except Exception:
                patterns_missed.append("gemini")
        
        return {
            "patterns_used": patterns_used,
            "patterns_missed": patterns_missed,
            "missed_examples": missed_examples
        }
    
    def _find_lots_in_content(self) -> List[Tuple[str, str]]:
        """
        Recherche des lots dans le contenu du fichier
        
        Returns:
            Liste des lots trouvés (num, nom)
        """
        try:
            # Extraire les patterns du code existant
            df = self.parser.df
            
            # Recherche simple de "LOT X" dans les premières lignes
            for i in range(min(10, len(df))):
                for col in range(min(5, df.shape[1])):
                    cell = str(df.iloc[i, col]).strip() if pd.notna(df.iloc[i, col]) else ""
                    if cell and re.search(r'lot\s*\d+', cell.lower()):
                        return [(cell, cell)]  # Tuple simpliste pour la détection
            
            return []
        except Exception:
            return []


class SectionPatternExtractor:
    """
    Extracteur et évaluateur des patterns de détection de section
    """
    
    def __init__(self, parser, logger):
        """
        Initialise l'extracteur
        
        Args:
            parser: ExcelParser pour accéder aux méthodes de détection
            logger: Logger pour le suivi des opérations
        """
        self.parser = parser
        self.logger = logger
        
        # Les patterns de section connus (extraits de l'implémentation existante)
        self.section_patterns = [
            ("Décimal", r'^\s*(\d+\.\d+(?:\.\d+)*)\s+(.+)$'),
            ("Numéro", r'^\s*(\d+)\s+(.+)$'),
            ("Romain", r'^\s*(I{1,3}|IV|VI{1,3}|IX|X)\s*[-\.]\s*(.+)$'),
            ("Lettre", r'^\s*([A-Z])\s*[-\.]\s*(.+)$'),
            ("Majuscule", r'^([A-Z][A-Z\s\-\':]+[A-Z])$'),
            ("Tiret", r'^\s*[-•]\s+(.+)$'),
            ("Capitalisé", r'^([A-Z][a-z].{5,})$')
        ]
    
    def evaluate_detection(self, items: List[Dict], header_row: int, df: pd.DataFrame) -> Dict:
        """
        Évalue la détection des sections sur le fichier
        
        Args:
            items: Liste des items (sections et éléments) détectés
            header_row: Indice de la ligne d'en-tête
            df: DataFrame du fichier Excel
            
        Returns:
            Résultat de l'évaluation
        """
        # Patterns détectés
        patterns_used = set()
        patterns_missed = []
        missed_examples = []
        false_positives = []
        
        # Récupérer toutes les sections détectées
        sections = [item for item in items if item['type'] == 'section']
        
        # Si aucune section, analyser les lignes pour voir ce qui aurait pu être manqué
        if not sections:
            self._analyze_missed_sections(df, header_row, missed_examples)
            patterns_missed = ["Tous"]
        else:
            # Pour chaque section, déterminer quel pattern a été utilisé
            for section in sections:
                section_text = str(section['data'].get('titre_section', ''))
                row_idx = section['row']
                row_text = ' '.join(str(cell) for cell in df.iloc[row_idx] if pd.notna(cell))
                
                pattern_found = False
                for pattern_name, pattern in self.section_patterns:
                    if re.search(pattern, row_text):
                        patterns_used.add(pattern_name)
                        pattern_found = True
                        break
                
                if not pattern_found:
                    missed_examples.append({
                        "type": "section_pattern",
                        "text": row_text,
                        "detected_as": "section"
                    })
            
            # Identifier des sections potentielles qui n'ont pas été détectées
            self._analyze_missed_sections(df, header_row, missed_examples, exclude_rows=set(item['row'] for item in sections))
        
        return {
            "patterns_used": list(patterns_used),
            "patterns_missed": patterns_missed,
            "missed_examples": missed_examples,
            "false_positives": false_positives
        }
    
    def _analyze_missed_sections(self, df: pd.DataFrame, header_row: int, 
                                missed_examples: List[Dict], exclude_rows: Set[int] = None):
        """
        Analyse les lignes non détectées comme sections mais qui pourraient l'être
        
        Args:
            df: DataFrame du fichier
            header_row: Indice de la ligne d'en-tête
            missed_examples: Liste à remplir avec les exemples manqués
            exclude_rows: Ensemble des indices de lignes à exclure
        """
        if exclude_rows is None:
            exclude_rows = set()
        
        if header_row is None:
            start_row = 0
        else:
            start_row = header_row + 1
        
        # Vérifier les 30 premières lignes après l'en-tête
        for i in range(start_row, min(start_row + 30, len(df))):
            if i in exclude_rows:
                continue
                
            row_text = ' '.join(str(cell) for cell in df.iloc[i] if pd.notna(cell))
            
            # Caractéristiques potentielles d'une section
            if row_text and len(row_text) > 5:
                # Indices que cette ligne pourrait être une section
                if (row_text.isupper() or 
                    re.search(r'^\s*\d+\.\d+', row_text) or 
                    re.search(r'^\s*[A-Z]\s*[-\.]\s+', row_text) or
                    re.search(r'^\s*[IVX]{1,4}\s*[-\.]\s+', row_text)):
                    
                    missed_examples.append({
                        "type": "potential_section",
                        "row": i,
                        "text": row_text
                    })


class LotPatternRecommender:
    """
    Générateur de recommandations de patterns pour la détection de lots
    """
    
    def __init__(self, missed_examples: List[Dict]):
        """
        Initialise le recommandeur
        
        Args:
            missed_examples: Exemples de lots non détectés
        """
        self.missed_examples = missed_examples
    
    def generate_recommendations(self) -> List[Dict]:
        """
        Génère des recommandations de nouveaux patterns de détection
        
        Returns:
            Liste de recommandations avec patterns suggérés
        """
        recommendations = []
        
        # Traiter les exemples de noms de fichier manqués
        filename_examples = [ex["text"] for ex in self.missed_examples 
                            if ex["type"] == "filename"]
        
        if filename_examples:
            for ex in filename_examples:
                # Rechercher des patterns spécifiques non couverts
                if re.search(r'lot.*n[o°]?\s*\d+', ex.lower()):
                    recommendations.append({
                        "type": "filename",
                        "pattern": r'lot.*n[o°]?\s*(\d+)',
                        "description": "Lot n° X ou Lot no X",
                        "example": ex
                    })
                elif re.search(r'lot.*[\[\(]?\s*\d+\s*[\]\)]?', ex.lower()):
                    recommendations.append({
                        "type": "filename",
                        "pattern": r'lot.*[\[\(]?\s*(\d+)\s*[\]\)]?',
                        "description": "Lot [X] ou Lot (X)",
                        "example": ex
                    })
        
        # Traiter les exemples de contenu manqués
        content_examples = [ex["text"] for ex in self.missed_examples 
                           if ex["type"] == "content"]
        
        if content_examples:
            for ex in content_examples:
                # Rechercher des mentions de lots dans le contenu
                if re.search(r'lot.*n[o°]?\s*\d+', ex.lower()):
                    recommendations.append({
                        "type": "content",
                        "pattern": r'lot.*n[o°]?\s*(\d+)',
                        "description": "Lot n° X ou Lot no X dans le contenu",
                        "example": ex
                    })
        
        return recommendations


class SectionPatternRecommender:
    """
    Générateur de recommandations de patterns pour la détection de sections
    """
    
    def __init__(self, missed_examples: List[Dict]):
        """
        Initialise le recommandeur
        
        Args:
            missed_examples: Exemples de sections non détectées
        """
        self.missed_examples = missed_examples
    
    def generate_recommendations(self) -> List[Dict]:
        """
        Génère des recommandations de nouveaux patterns de détection
        
        Returns:
            Liste de recommandations avec patterns suggérés
        """
        recommendations = []
        
        # Traiter les exemples de sections potentielles manquées
        potential_sections = [ex["text"] for ex in self.missed_examples 
                             if ex["type"] == "potential_section"]
        
        if potential_sections:
            for ex in potential_sections:
                # Rechercher des patterns spécifiques non couverts
                if re.search(r'^\s*\d+\s*\-\s*\d+\s*\-\s*\d+', ex):
                    recommendations.append({
                        "type": "section",
                        "pattern": r'^\s*(\d+\s*\-\s*\d+\s*\-\s*\d+)\s+(.+)$',
                        "description": "Format X-X-X Titre (ex: 1-2-3 Installation)",
                        "example": ex
                    })
                elif re.search(r'^\s*[A-Za-z]+\.\d+', ex):
                    recommendations.append({
                        "type": "section",
                        "pattern": r'^\s*([A-Za-z]+\.\d+)\s+(.+)$',
                        "description": "Format Alpha.Num (ex: A.1 Installation)",
                        "example": ex
                    })
        
        return recommendations


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Évaluateur des capacités de détection des lots et sections")
    parser.add_argument('--dir', '-d', type=str, default='test_data', 
                       help="Répertoire contenant les fichiers DPGF à analyser")
    parser.add_argument('--output', '-o', type=str, default='detection_evaluation_report.json',
                       help="Fichier de sortie pour le rapport JSON")
    parser.add_argument('--use-gemini', '-g', action='store_true',
                       help="Utiliser l'API Google Gemini pour la détection")
    
    args = parser.parse_args()
    
    evaluator = DetectionPatternEvaluator(args.dir, args.use_gemini)
    evaluator.analyze_all_files()
    evaluator.generate_report(args.output)


if __name__ == "__main__":
    main()
