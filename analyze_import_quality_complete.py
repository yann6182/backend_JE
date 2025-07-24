#!/usr/bin/env python3
"""
Analyseur de qualité des imports DPGF.

Ce script analyse les logs et rapports d'import pour identifier les patterns
récurrents d'échec et proposer des améliorations.

Fonctionnalités :
- Analyse des logs d'orchestrateur
- Détection des fichiers problématiques récurrents
- Identification des causes d'échec communes
- Suggestions d'amélioration
- Rapport de qualité consolidé

Auteur: Assistant IA
Date: 2024
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from collections import Counter, defaultdict
import pandas as pd

# Configuration de l'encodage pour Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class ImportQualityAnalyzer:
    """Analyseur de qualité des imports DPGF"""
    
    def __init__(self):
        self.setup_logging()
        self.patterns = self._initialize_patterns()
        self.quality_metrics = {}
        self.recommendations = []
        
    def setup_logging(self):
        """Configuration du logging"""
        log_dir = Path("quality_analysis")
        log_dir.mkdir(exist_ok=True)
        
        self.log_file = log_dir / f"quality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _initialize_patterns(self) -> Dict:
        """Initialise les patterns de détection d'erreurs"""
        return {
            'import_technique': [
                r'import technique.*aucune donnée',
                r'fichier.*traité.*0 lots.*0 sections.*0 éléments',
                r'traitement.*terminé.*sans données utiles'
            ],
            'erreur_excel': [
                r'erreur.*lecture.*excel',
                r'xlrd.*error',
                r'openpyxl.*error',
                r'engine.*not.*supported'
            ],
            'erreur_reseau': [
                r'timeout',
                r'connection.*error',
                r'network.*error',
                r'sharepoint.*inaccessible'
            ],
            'erreur_structure': [
                r'structure.*non.*reconnue',
                r'colonnes.*manquantes',
                r'format.*invalide',
                r'en-têtes.*introuvables'
            ],
            'erreur_donnees': [
                r'données.*corrompues',
                r'valeurs.*manquantes',
                r'format.*prix.*invalide',
                r'quantités.*invalides'
            ],
            'succes_import': [
                r'import.*réussi',
                r'lots.*créés.*\d+',
                r'sections.*créées.*\d+',
                r'éléments.*créés.*\d+'
            ]
        }
        
    def analyze_log_file(self, log_path: Path) -> Dict:
        """Analyse un fichier de log spécifique"""
        self.logger.info(f"Analyse du fichier: {log_path}")
        
        analysis = {
            'file_path': str(log_path),
            'timestamp': datetime.fromtimestamp(log_path.stat().st_mtime).isoformat(),
            'size': log_path.stat().st_size,
            'lines_count': 0,
            'error_patterns': defaultdict(int),
            'files_processed': [],
            'import_stats': {
                'total_files': 0,
                'successful_imports': 0,
                'technical_imports': 0,
                'failed_imports': 0
            }
        }
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                analysis['lines_count'] = len(lines)
                
                # Analyse des patterns d'erreur
                for category, patterns in self.patterns.items():
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        analysis['error_patterns'][category] += len(matches)
                        
                # Extraction des noms de fichiers traités
                file_pattern = r'(?:traitement|analyse|import).*?([A-Za-z0-9_\-\.]+\.xlsx?)'
                files = re.findall(file_pattern, content, re.IGNORECASE)
                analysis['files_processed'] = list(set(files))
                analysis['import_stats']['total_files'] = len(analysis['files_processed'])
                
                # Calcul des statistiques d'import
                analysis['import_stats']['successful_imports'] = analysis['error_patterns']['succes_import']
                analysis['import_stats']['technical_imports'] = analysis['error_patterns']['import_technique']
                analysis['import_stats']['failed_imports'] = (
                    analysis['import_stats']['total_files'] - 
                    analysis['import_stats']['successful_imports'] - 
                    analysis['import_stats']['technical_imports']
                )
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {log_path}: {e}")
            analysis['error'] = str(e)
            
        return analysis
        
    def analyze_json_report(self, json_path: Path) -> Dict:
        """Analyse un rapport JSON"""
        self.logger.info(f"Analyse du rapport JSON: {json_path}")
        
        analysis = {
            'file_path': str(json_path),
            'timestamp': datetime.fromtimestamp(json_path.stat().st_mtime).isoformat(),
            'valid': False,
            'summary': {}
        }
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                analysis['valid'] = True
                
                # Extraction des métriques clés
                if isinstance(data, dict):
                    # Résumé de session
                    if 'session_summary' in data:
                        summary = data['session_summary']
                        analysis['summary'] = {
                            'total_folders': summary.get('total_folders_scanned', 0),
                            'total_files': summary.get('total_files_found', 0),
                            'successful_imports': summary.get('successful_imports', 0),
                            'technical_imports': summary.get('technical_imports', 0),
                            'failed_imports': summary.get('failed_imports', 0)
                        }
                        
                    # Statistiques par dossier
                    if 'folder_results' in data:
                        folder_stats = []
                        for folder_data in data['folder_results']:
                            folder_stats.append({
                                'folder': folder_data.get('folder_name', 'unknown'),
                                'files_count': len(folder_data.get('files', [])),
                                'success_rate': self._calculate_success_rate(folder_data)
                            })
                        analysis['folder_stats'] = folder_stats
                        
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {json_path}: {e}")
            analysis['error'] = str(e)
            
        return analysis
        
    def _calculate_success_rate(self, folder_data: Dict) -> float:
        """Calcule le taux de succès pour un dossier"""
        files = folder_data.get('files', [])
        if not files:
            return 0.0
            
        successful = sum(1 for f in files if f.get('import_status') == 'success')
        return (successful / len(files)) * 100
        
    def scan_all_logs(self) -> Dict:
        """Scan tous les logs disponibles"""
        self.logger.info("🔍 Scan de tous les logs disponibles")
        
        scan_results = {
            'scan_timestamp': datetime.now().isoformat(),
            'directories_scanned': [],
            'log_files': [],
            'json_reports': [],
            'total_files': 0
        }
        
        # Répertoires à scanner
        log_directories = [
            Path("logs"),
            Path("logs_orchestrator"),
            Path("logs_production"),
            Path("logs_test"),
            Path("reports"),
            Path("reports_orchestrator"),
            Path("reports_production"),
            Path("reports_test"),
            Path("quality_analysis"),
            Path("logs_robustness")
        ]
        
        for log_dir in log_directories:
            if log_dir.exists():
                scan_results['directories_scanned'].append(str(log_dir))
                
                # Fichiers de log
                for log_file in log_dir.glob("*.log"):
                    analysis = self.analyze_log_file(log_file)
                    scan_results['log_files'].append(analysis)
                    scan_results['total_files'] += 1
                    
                # Rapports JSON
                for json_file in log_dir.glob("*.json"):
                    analysis = self.analyze_json_report(json_file)
                    scan_results['json_reports'].append(analysis)
                    scan_results['total_files'] += 1
                    
        self.logger.info(f"📊 Scan terminé: {scan_results['total_files']} fichiers analysés")
        return scan_results
        
    def generate_quality_metrics(self, scan_results: Dict) -> Dict:
        """Génère les métriques de qualité"""
        self.logger.info("📈 Génération des métriques de qualité")
        
        metrics = {
            'global_stats': {
                'total_log_files': len(scan_results['log_files']),
                'total_json_reports': len(scan_results['json_reports']),
                'analysis_period': self._calculate_analysis_period(scan_results)
            },
            'error_distribution': defaultdict(int),
            'problematic_files': Counter(),
            'success_rates': [],
            'recommendations': []
        }
        
        # Agrégation des erreurs
        for log_analysis in scan_results['log_files']:
            for error_type, count in log_analysis.get('error_patterns', {}).items():
                metrics['error_distribution'][error_type] += count
                
        # Identification des fichiers problématiques
        for log_analysis in scan_results['log_files']:
            for file_name in log_analysis.get('files_processed', []):
                # Vérifier si le fichier a des erreurs
                if (log_analysis.get('error_patterns', {}).get('erreur_excel', 0) > 0 or
                    log_analysis.get('error_patterns', {}).get('erreur_structure', 0) > 0):
                    metrics['problematic_files'][file_name] += 1
                    
        # Calcul des taux de succès
        for json_analysis in scan_results['json_reports']:
            if json_analysis.get('valid', False):
                summary = json_analysis.get('summary', {})
                total = summary.get('total_files', 0)
                successful = summary.get('successful_imports', 0)
                if total > 0:
                    success_rate = (successful / total) * 100
                    metrics['success_rates'].append(success_rate)
                    
        # Calcul des moyennes
        if metrics['success_rates']:
            metrics['global_stats']['average_success_rate'] = sum(metrics['success_rates']) / len(metrics['success_rates'])
        else:
            metrics['global_stats']['average_success_rate'] = 0.0
            
        return metrics
        
    def _calculate_analysis_period(self, scan_results: Dict) -> Dict:
        """Calcule la période d'analyse"""
        timestamps = []
        
        for log_analysis in scan_results['log_files']:
            if 'timestamp' in log_analysis:
                timestamps.append(datetime.fromisoformat(log_analysis['timestamp']))
                
        for json_analysis in scan_results['json_reports']:
            if 'timestamp' in json_analysis:
                timestamps.append(datetime.fromisoformat(json_analysis['timestamp']))
                
        if timestamps:
            return {
                'start_date': min(timestamps).isoformat(),
                'end_date': max(timestamps).isoformat(),
                'duration_days': (max(timestamps) - min(timestamps)).days
            }
        else:
            return {'start_date': None, 'end_date': None, 'duration_days': 0}
            
    def generate_recommendations(self, metrics: Dict) -> List[Dict]:
        """Génère des recommandations d'amélioration"""
        self.logger.info("💡 Génération des recommandations")
        
        recommendations = []
        
        # Recommandations basées sur les erreurs
        error_dist = metrics['error_distribution']
        
        if error_dist['erreur_excel'] > 0:
            recommendations.append({
                'type': 'excel_handling',
                'priority': 'high',
                'title': 'Améliorer la gestion des fichiers Excel',
                'description': f"{error_dist['erreur_excel']} erreurs Excel détectées",
                'actions': [
                    'Vérifier l\'installation des modules xlrd et openpyxl',
                    'Améliorer la détection automatique du moteur Excel',
                    'Ajouter une validation des fichiers avant traitement'
                ]
            })
            
        if error_dist['import_technique'] > 0:
            recommendations.append({
                'type': 'data_quality',
                'priority': 'medium',
                'title': 'Réduire les imports techniques sans données',
                'description': f"{error_dist['import_technique']} imports techniques détectés",
                'actions': [
                    'Améliorer la pré-validation des fichiers',
                    'Ajouter des critères de filtrage plus stricts',
                    'Développer un système de scoring des fichiers'
                ]
            })
            
        if error_dist['erreur_reseau'] > 0:
            recommendations.append({
                'type': 'network_robustness',
                'priority': 'high',
                'title': 'Renforcer la robustesse réseau',
                'description': f"{error_dist['erreur_reseau']} erreurs réseau détectées",
                'actions': [
                    'Implémenter un système de retry automatique',
                    'Ajouter des timeouts configurables',
                    'Développer un mode de récupération d\'erreur'
                ]
            })
            
        # Recommandations basées sur les taux de succès
        if metrics['global_stats']['average_success_rate'] < 80:
            recommendations.append({
                'type': 'success_rate',
                'priority': 'high',
                'title': 'Améliorer le taux de succès global',
                'description': f"Taux de succès moyen: {metrics['global_stats']['average_success_rate']:.1f}%",
                'actions': [
                    'Analyser les causes d\'échec les plus fréquentes',
                    'Améliorer la validation des données d\'entrée',
                    'Optimiser les algorithmes de détection'
                ]
            })
            
        # Recommandations basées sur les fichiers problématiques
        problematic_count = len(metrics['problematic_files'])
        if problematic_count > 0:
            recommendations.append({
                'type': 'problematic_files',
                'priority': 'medium',
                'title': 'Traiter les fichiers problématiques récurrents',
                'description': f"{problematic_count} fichiers problématiques identifiés",
                'actions': [
                    'Créer une liste de fichiers à traiter manuellement',
                    'Développer des règles spécifiques pour ces fichiers',
                    'Améliorer la documentation des formats supportés'
                ]
            })
            
        return recommendations
        
    def generate_quality_report(self) -> Dict:
        """Génère le rapport de qualité complet"""
        self.logger.info("📋 Génération du rapport de qualité complet")
        
        # Scan des logs
        scan_results = self.scan_all_logs()
        
        # Génération des métriques
        metrics = self.generate_quality_metrics(scan_results)
        
        # Génération des recommandations
        recommendations = self.generate_recommendations(metrics)
        
        # Rapport final
        report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'version': '1.0',
                'analyzer': 'ImportQualityAnalyzer'
            },
            'scan_results': scan_results,
            'quality_metrics': metrics,
            'recommendations': recommendations,
            'summary': {
                'total_files_analyzed': scan_results['total_files'],
                'average_success_rate': metrics['global_stats']['average_success_rate'],
                'most_common_errors': dict(Counter(metrics['error_distribution']).most_common(5)),
                'recommendation_count': len(recommendations)
            }
        }
        
        return report
        
    def save_report(self, report: Dict) -> Path:
        """Sauvegarde le rapport"""
        report_dir = Path("quality_analysis")
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"📄 Rapport sauvegardé: {report_file}")
        return report_file
        
    def print_summary(self, report: Dict):
        """Affiche un résumé du rapport"""
        summary = report['summary']
        
        print(f"\n{'='*60}")
        print(f"📊 RAPPORT DE QUALITÉ DES IMPORTS DPGF")
        print(f"{'='*60}")
        print(f"Fichiers analysés: {summary['total_files_analyzed']}")
        print(f"Taux de succès moyen: {summary['average_success_rate']:.1f}%")
        print(f"Recommandations: {summary['recommendation_count']}")
        
        print(f"\n🔍 ERREURS LES PLUS FRÉQUENTES:")
        for error_type, count in summary['most_common_errors'].items():
            print(f"  • {error_type}: {count}")
            
        print(f"\n💡 RECOMMANDATIONS PRINCIPALES:")
        high_priority = [r for r in report['recommendations'] if r['priority'] == 'high']
        for i, rec in enumerate(high_priority[:3], 1):
            print(f"  {i}. {rec['title']}")
            print(f"     {rec['description']}")
            
        print(f"\n📄 Rapport détaillé disponible dans le fichier JSON")


def main():
    """Point d'entrée principal"""
    print("🔧 Analyseur de qualité des imports DPGF")
    print("=" * 50)
    
    analyzer = ImportQualityAnalyzer()
    
    # Génération du rapport
    report = analyzer.generate_quality_report()
    
    # Sauvegarde
    report_file = analyzer.save_report(report)
    
    # Affichage du résumé
    analyzer.print_summary(report)
    
    print(f"\n📋 Rapport complet: {report_file}")
    print(f"📋 Log détaillé: {analyzer.log_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
