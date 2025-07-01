"""
Script d'analyse de logs pour diagnostiquer les problèmes d'import DPGF.
Ce script analyse les logs générés pendant l'import DPGF et aide à identifier
les causes des problèmes de détection de lots et sections.
"""

import os
import re
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import csv

LOG_DIR = Path("logs")


class LogAnalyzer:
    """Analyseur de logs pour diagnostiquer les problèmes d'import DPGF"""
    
    def __init__(self, log_dir: Path = LOG_DIR):
        """
        Initialise l'analyseur de logs
        
        Args:
            log_dir: Répertoire des logs
        """
        self.log_dir = log_dir
        self.log_files = []
        self.detailed_logs = []
        self.import_logs = []
        self.problems = {}  # Fichier -> problèmes
        
        # Assurez-vous que le répertoire existe
        if not self.log_dir.exists():
            print(f"⚠️ Répertoire de logs '{self.log_dir}' non trouvé.")
            return
        
        # Trouver tous les fichiers de log
        for f in self.log_dir.glob("dpgf_import_*.log"):
            if "detailed" in f.name:
                self.detailed_logs.append(f)
            else:
                self.import_logs.append(f)
        
        # Trouver tous les sous-répertoires de fichier
        self.file_logs = {}
        for d in self.log_dir.iterdir():
            if d.is_dir():
                file_logs = list(d.glob("import_*.log"))
                if file_logs:
                    self.file_logs[d.name] = file_logs
    
    def list_log_files(self):
        """Liste tous les fichiers de log disponibles"""
        print(f"\n=== LOGS D'IMPORT DISPONIBLES ===")
        for log in sorted(self.import_logs, key=lambda x: x.stat().st_mtime, reverse=True):
            timestamp = datetime.fromtimestamp(log.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = log.stat().st_size / 1024  # en Ko
            print(f"- {log.name} ({timestamp}, {size:.1f} Ko)")
        
        print(f"\n=== LOGS DÉTAILLÉS DISPONIBLES ===")
        for log in sorted(self.detailed_logs, key=lambda x: x.stat().st_mtime, reverse=True):
            timestamp = datetime.fromtimestamp(log.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = log.stat().st_size / 1024  # en Ko
            print(f"- {log.name} ({timestamp}, {size:.1f} Ko)")
        
        print(f"\n=== LOGS PAR FICHIER DPGF ===")
        for file, logs in self.file_logs.items():
            latest_log = max(logs, key=lambda x: x.stat().st_mtime)
            timestamp = datetime.fromtimestamp(latest_log.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"- {file} ({len(logs)} logs, dernier import: {timestamp})")
    
    def analyze_import_log(self, log_path: Path) -> Dict:
        """
        Analyse un fichier de log principal
        
        Args:
            log_path: Chemin du fichier de log
        
        Returns:
            Résultats de l'analyse
        """
        print(f"\n=== ANALYSE DU LOG: {log_path.name} ===")
        
        results = {
            "files_processed": 0,
            "files_with_lot_issues": 0,
            "files_with_section_issues": 0,
            "lot_detection_methods": {"filename": 0, "gemini": 0, "content": 0, "fallback": 0},
            "default_lots_created": 0,
            "default_sections_created": 0,
            "problems": {}
        }
        
        current_file = None
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Détecter le fichier en cours de traitement
                if '[' in line and ']' in line:
                    file_match = re.search(r'\[(.*?)\]', line)
                    if file_match and ".xls" in file_match.group(1):
                        current_file = file_match.group(1)
                        if current_file not in results["problems"]:
                            results["files_processed"] += 1
                            results["problems"][current_file] = []
                
                if not current_file:
                    continue
                
                # Détecter les problèmes de lot
                if "LOT NON DÉTECTÉ" in line:
                    results["problems"][current_file].append(f"Lot non détecté: {line.strip()}")
                    results["files_with_lot_issues"] += 1
                
                # Méthodes de détection de lot
                if "LOT DÉTECTÉ - Méthode:" in line:
                    if "Méthode: filename" in line:
                        results["lot_detection_methods"]["filename"] += 1
                    elif "Méthode: gemini" in line:
                        results["lot_detection_methods"]["gemini"] += 1
                    elif "Méthode: content" in line:
                        results["lot_detection_methods"]["content"] += 1
                
                # Lots par défaut
                if "LOT PAR DÉFAUT CRÉÉ" in line:
                    results["default_lots_created"] += 1
                    results["problems"][current_file].append(f"Lot par défaut créé: {line.strip()}")
                
                # Sections par défaut
                if "SECTION PAR DÉFAUT CRÉÉE" in line:
                    results["default_sections_created"] += 1
                    results["problems"][current_file].append(f"Section par défaut créée: {line.strip()}")
                
                # Problèmes de section
                if "Aucune section détectée" in line:
                    results["files_with_section_issues"] += 1
                    results["problems"][current_file].append(f"Problème de section: {line.strip()}")
        
        # Afficher un résumé
        print(f"Fichiers traités: {results['files_processed']}")
        print(f"Fichiers avec problèmes de lot: {results['files_with_lot_issues']}")
        print(f"Fichiers avec problèmes de section: {results['files_with_section_issues']}")
        print(f"Lots par défaut créés: {results['default_lots_created']}")
        print(f"Sections par défaut créées: {results['default_sections_created']}")
        print("\nMéthodes de détection de lot utilisées:")
        for method, count in results["lot_detection_methods"].items():
            print(f"  - {method}: {count}")
        
        return results
    
    def analyze_file_log(self, file_name: str) -> Dict:
        """
        Analyse les logs d'un fichier DPGF spécifique
        
        Args:
            file_name: Nom du fichier DPGF
        
        Returns:
            Résultats de l'analyse
        """
        if file_name not in self.file_logs:
            print(f"❌ Aucun log trouvé pour le fichier: {file_name}")
            return {}
        
        logs = sorted(self.file_logs[file_name], key=lambda x: x.stat().st_mtime, reverse=True)
        latest_log = logs[0]
        
        print(f"\n=== ANALYSE DES LOGS POUR: {file_name} ===")
        print(f"Nombre d'imports: {len(logs)}")
        print(f"Dernier import: {datetime.fromtimestamp(latest_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {
            "file": file_name,
            "imports": len(logs),
            "latest_import": datetime.fromtimestamp(latest_log.stat().st_mtime).isoformat(),
            "lot_detection": [],
            "section_detection": [],
            "problems": []
        }
        
        # Analyser le log le plus récent
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # Chercher les informations sur la détection de lot
            lot_section = False
            section_section = False
            
            for i, line in enumerate(lines):
                if "==== DÉTECTION DE LOT ====" in line:
                    lot_section = True
                    section_section = False
                    continue
                
                if "==== DÉTECTION DES SECTIONS ET ÉLÉMENTS ====" in line:
                    lot_section = False
                    section_section = True
                    continue
                
                # Détection de lot
                if lot_section:
                    if "LOT DÉTECTÉ" in line:
                        results["lot_detection"].append({
                            "status": "detected",
                            "info": line.strip()
                        })
                    elif "LOT NON DÉTECTÉ" in line:
                        results["lot_detection"].append({
                            "status": "not_detected",
                            "info": line.strip()
                        })
                        results["problems"].append({
                            "type": "lot_detection",
                            "info": line.strip()
                        })
                    elif "ÉCHEC DE DÉTECTION" in line:
                        results["problems"].append({
                            "type": "lot_detection",
                            "info": line.strip()
                        })
                
                # Détection de section
                if section_section:
                    if "SECTION DÉTECTÉE" in line:
                        results["section_detection"].append({
                            "status": "detected",
                            "info": line.strip()
                        })
                    elif "SECTION NON DÉTECTÉE" in line:
                        results["section_detection"].append({
                            "status": "not_detected",
                            "info": line.strip()
                        })
                    elif "SECTION PAR DÉFAUT CRÉÉE" in line:
                        results["section_detection"].append({
                            "status": "default_created",
                            "info": line.strip()
                        })
                        results["problems"].append({
                            "type": "section_detection",
                            "info": line.strip()
                        })
        
        # Afficher un résumé des problèmes
        lot_problems = [p for p in results["problems"] if p["type"] == "lot_detection"]
        section_problems = [p for p in results["problems"] if p["type"] == "section_detection"]
        
        print(f"\nProblèmes de détection de lot: {len(lot_problems)}")
        for p in lot_problems:
            print(f"  - {p['info']}")
        
        print(f"\nProblèmes de détection de section: {len(section_problems)}")
        for p in section_problems:
            print(f"  - {p['info']}")
        
        return results
    
    def generate_problem_report(self, output_file: str = "dpgf_import_problems.csv"):
        """
        Génère un rapport CSV des problèmes d'import
        
        Args:
            output_file: Fichier de sortie CSV
        """
        problems = []
        
        # Analyser tous les logs de fichiers
        for file_name in self.file_logs:
            file_results = self.analyze_file_log(file_name)
            if file_results.get("problems"):
                for problem in file_results["problems"]:
                    problems.append({
                        "fichier": file_name,
                        "type_probleme": problem["type"],
                        "description": problem["info"]
                    })
        
        if not problems:
            print("Aucun problème détecté pour générer un rapport.")
            return
        
        # Écrire dans un CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["fichier", "type_probleme", "description"])
            writer.writeheader()
            writer.writerows(problems)
        
        print(f"\n✅ Rapport généré: {output_file} ({len(problems)} problèmes)")


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description="Analyse des logs d'import DPGF pour diagnostiquer les problèmes")
    parser.add_argument("--log-dir", default="logs", help="Répertoire des logs (défaut: logs)")
    parser.add_argument("--list", action="store_true", help="Lister les fichiers de log disponibles")
    parser.add_argument("--analyze-log", help="Analyser un fichier de log global spécifique")
    parser.add_argument("--analyze-file", help="Analyser les logs pour un fichier DPGF spécifique")
    parser.add_argument("--report", action="store_true", help="Générer un rapport CSV des problèmes")
    parser.add_argument("--output", default="dpgf_import_problems.csv", help="Fichier de sortie pour le rapport")
    
    args = parser.parse_args()
    
    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        print(f"❌ Répertoire de logs non trouvé: {args.log_dir}")
        sys.exit(1)
    
    analyzer = LogAnalyzer(log_dir)
    
    if args.list or (not args.analyze_log and not args.analyze_file and not args.report):
        analyzer.list_log_files()
    
    if args.analyze_log:
        log_path = log_dir / args.analyze_log
        if not log_path.exists():
            print(f"❌ Fichier de log non trouvé: {args.analyze_log}")
            sys.exit(1)
        analyzer.analyze_import_log(log_path)
    
    if args.analyze_file:
        analyzer.analyze_file_log(args.analyze_file)
    
    if args.report:
        analyzer.generate_problem_report(args.output)


if __name__ == "__main__":
    main()
