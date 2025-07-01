#!/usr/bin/env python3
"""
Analyseur des logs d'orchestrateur pour identifier les problèmes d'import DPGF.
Recherche les messages "Import technique réussi mais AUCUNE DONNÉE" et autres problèmes.
"""

import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

class OrchestratorLogAnalyzer:
    """Analyseur des logs d'orchestrateur"""
    
    def __init__(self):
        self.log_files = []
        self.issues = []
        self.stats = defaultdict(int)
        self.file_details = {}
        
    def find_log_files(self) -> List[Path]:
        """Trouve tous les fichiers de logs de l'orchestrateur"""
        
        current_dir = Path(".")
        log_patterns = [
            "orchestration*.log",
            "dpgf_workflow*.log",
            "workflow*.log",
            "*.log"
        ]
        
        log_files = []
        for pattern in log_patterns:
            log_files.extend(current_dir.glob(pattern))
            
        # Filtrer pour garder uniquement les logs pertinents
        relevant_logs = []
        for log_file in log_files:
            if self.is_orchestrator_log(log_file):
                relevant_logs.append(log_file)
                
        return sorted(relevant_logs, key=lambda x: x.stat().st_mtime, reverse=True)
        
    def is_orchestrator_log(self, log_file: Path) -> bool:
        """Vérifie si un fichier de log est un log d'orchestrateur"""
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Lire les premières lignes pour identifier le type de log
                first_lines = [f.readline() for _ in range(10)]
                content = '\n'.join(first_lines).lower()
                
                # Chercher des indicateurs d'orchestrateur
                indicators = [
                    'orchestrat',
                    'workflow',
                    'dpgf',
                    'import technique',
                    'sharepoint',
                    'identified_files'
                ]
                
                return any(indicator in content for indicator in indicators)
                
        except Exception:
            return False
            
    def analyze_logs(self):
        """Analyse tous les logs d'orchestrateur trouvés"""
        
        self.log_files = self.find_log_files()
        
        if not self.log_files:
            print("❌ Aucun fichier de log d'orchestrateur trouvé")
            return
            
        print(f"📊 Analyse de {len(self.log_files)} fichiers de logs...")
        
        for log_file in self.log_files:
            print(f"🔍 Analyse: {log_file.name}")
            try:
                self.analyze_single_log(log_file)
            except Exception as e:
                print(f"❌ Erreur lors de l'analyse de {log_file}: {e}")
                
    def analyze_single_log(self, log_file: Path):
        """Analyse un seul fichier de log"""
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        self.stats[f'log_files_analyzed'] += 1
        self.stats[f'total_lines'] += len(lines)
        
        # Patterns à rechercher
        patterns = {
            'import_technique_sans_donnees': r'Import technique réussi mais AUCUNE DONNÉE.*?([^/\s]+\.(xls|xlsx|xlsm))',
            'echec_import': r'Échec import.*?([^/\s]+\.(xls|xlsx|xlsm))',
            'import_reussi': r'Import réussi.*?([^/\s]+\.(xls|xlsx|xlsm))',
            'fichier_identifie': r'Fichier identifié.*?([^/\s]+\.(xls|xlsx|xlsm))',
            'structure_non_reconnue': r'structure non reconnue.*?([^/\s]+\.(xls|xlsx|xlsm))',
            'lots_sections_elements': r'(\d+) lots?,\s*(\d+) sections?,\s*(\d+) éléments',
            'timeout_sharepoint': r'timeout.*sharepoint',
            'erreur_reseau': r'erreur.*réseau|network.*error|connection.*error'
        }
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Analyser chaque pattern
            for pattern_name, pattern in patterns.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                
                for match in matches:
                    self.stats[pattern_name] += 1
                    
                    if pattern_name == 'import_technique_sans_donnees':
                        file_name = match.group(1)
                        self.issues.append({
                            'type': 'import_technique_sans_donnees',
                            'file_name': file_name,
                            'log_file': log_file.name,
                            'line_number': i + 1,
                            'message': line.strip(),
                            'severity': 'warning'
                        })
                        self.record_file_issue(file_name, 'import_technique_sans_donnees')
                        
                    elif pattern_name == 'echec_import':
                        file_name = match.group(1)
                        self.issues.append({
                            'type': 'echec_import',
                            'file_name': file_name,
                            'log_file': log_file.name, 
                            'line_number': i + 1,
                            'message': line.strip(),
                            'severity': 'error'
                        })
                        self.record_file_issue(file_name, 'echec_import')
                        
                    elif pattern_name == 'import_reussi':
                        file_name = match.group(1)
                        self.record_file_issue(file_name, 'import_reussi')
                        
                    elif pattern_name == 'lots_sections_elements':
                        lots = int(match.group(1))
                        sections = int(match.group(2))
                        elements = int(match.group(3))
                        
                        # Chercher le nom du fichier dans les lignes précédentes
                        context_lines = lines[max(0, i-3):i+1]
                        context = '\n'.join(context_lines)
                        
                        file_match = re.search(r'([^/\s]+\.(xls|xlsx|xlsm))', context, re.IGNORECASE)
                        if file_match:
                            file_name = file_match.group(1)
                            self.record_file_stats(file_name, lots, sections, elements)
                            
    def record_file_issue(self, file_name: str, issue_type: str):
        """Enregistre un problème pour un fichier"""
        
        if file_name not in self.file_details:
            self.file_details[file_name] = {
                'issues': [],
                'lots': 0,
                'sections': 0,
                'elements': 0,
                'status': 'unknown'
            }
            
        self.file_details[file_name]['issues'].append(issue_type)
        
        if issue_type == 'import_technique_sans_donnees':
            self.file_details[file_name]['status'] = 'import_technique'
        elif issue_type == 'echec_import':
            self.file_details[file_name]['status'] = 'echec'
        elif issue_type == 'import_reussi':
            self.file_details[file_name]['status'] = 'reussi'
            
    def record_file_stats(self, file_name: str, lots: int, sections: int, elements: int):
        """Enregistre les statistiques d'import pour un fichier"""
        
        if file_name not in self.file_details:
            self.file_details[file_name] = {
                'issues': [],
                'lots': 0,
                'sections': 0,
                'elements': 0,
                'status': 'unknown'
            }
            
        self.file_details[file_name]['lots'] = lots
        self.file_details[file_name]['sections'] = sections  
        self.file_details[file_name]['elements'] = elements
        
    def generate_summary(self) -> Dict:
        """Génère un résumé de l'analyse"""
        
        # Analyser les fichiers par statut
        files_by_status = defaultdict(list)
        problematic_files = []
        
        for file_name, details in self.file_details.items():
            status = details['status']
            files_by_status[status].append(file_name)
            
            # Identifier les fichiers problématiques
            if (status == 'import_technique' or 
                (details['lots'] == 0 and details['sections'] == 0 and status != 'echec')):
                problematic_files.append({
                    'file_name': file_name,
                    'status': status,
                    'lots': details['lots'],
                    'sections': details['sections'],
                    'elements': details['elements'],
                    'issues': details['issues']
                })
                
        summary = {
            'timestamp': datetime.now().isoformat(),
            'logs_analyzed': len(self.log_files),
            'statistics': dict(self.stats),
            'files_by_status': {k: len(v) for k, v in files_by_status.items()},
            'problematic_files': problematic_files,
            'top_issues': self.get_top_issues(),
            'recommendations': self.generate_recommendations(problematic_files)
        }
        
        return summary
        
    def get_top_issues(self) -> List[Dict]:
        """Identifie les problèmes les plus fréquents"""
        
        issue_counter = Counter()
        for issue in self.issues:
            issue_counter[issue['type']] += 1
            
        return [{'type': issue_type, 'count': count} 
                for issue_type, count in issue_counter.most_common(10)]
                
    def generate_recommendations(self, problematic_files: List[Dict]) -> List[str]:
        """Génère des recommandations basées sur l'analyse"""
        
        recommendations = []
        
        if self.stats['import_technique_sans_donnees'] > 0:
            recommendations.append(
                f"🔍 {self.stats['import_technique_sans_donnees']} fichiers DPGF produisent des imports techniques sans données. "
                "Ces fichiers sont identifiés comme DPGF mais leur structure n'est pas reconnue par l'importeur."
            )
            
        if self.stats['echec_import'] > 0:
            recommendations.append(
                f"❌ {self.stats['echec_import']} échecs d'import détectés. "
                "Vérifiez les problèmes d'accès aux fichiers, corruption, ou erreurs de format."
            )
            
        if problematic_files:
            recommendations.append(
                f"🎯 {len(problematic_files)} fichiers nécessitent une analyse individuelle. "
                "Utilisez l'outil analyze_dpgf_file.py pour comprendre leur structure."
            )
            
        if self.stats['timeout_sharepoint'] > 0:
            recommendations.append(
                f"⏱️ {self.stats['timeout_sharepoint']} timeouts SharePoint détectés. "
                "Considérez augmenter les timeouts ou améliorer la connexion réseau."
            )
            
        # Analyse du taux de succès
        total_attempts = (self.stats.get('import_reussi', 0) + 
                         self.stats.get('import_technique_sans_donnees', 0) + 
                         self.stats.get('echec_import', 0))
                         
        if total_attempts > 0:
            success_rate = (self.stats.get('import_reussi', 0) / total_attempts) * 100
            recommendations.append(
                f"📊 Taux de succès d'import: {success_rate:.1f}% "
                f"({self.stats.get('import_reussi', 0)}/{total_attempts})"
            )
            
        return recommendations
        
    def print_summary(self, summary: Dict):
        """Affiche le résumé de l'analyse"""
        
        print("\n" + "="*80)
        print("📊 ANALYSE DES LOGS D'ORCHESTRATEUR")
        print("="*80)
        
        print(f"\n📈 STATISTIQUES GÉNÉRALES:")
        print(f"   Fichiers de logs analysés: {summary['logs_analyzed']}")
        print(f"   Lignes totales analysées: {summary['statistics'].get('total_lines', 0)}")
        
        print(f"\n🔍 PROBLÈMES IDENTIFIÉS:")
        for issue in summary['top_issues']:
            print(f"   {issue['type']}: {issue['count']} occurrences")
            
        print(f"\n📁 FICHIERS PAR STATUT:")
        for status, count in summary['files_by_status'].items():
            print(f"   {status}: {count} fichiers")
            
        print(f"\n🎯 FICHIERS PROBLÉMATIQUES ({len(summary['problematic_files'])}):")
        for file_info in summary['problematic_files'][:10]:  # Top 10
            print(f"   {file_info['file_name']}: {file_info['status']} "
                  f"({file_info['lots']}L/{file_info['sections']}S/{file_info['elements']}E)")
                  
        print(f"\n💡 RECOMMANDATIONS:")
        for i, recommendation in enumerate(summary['recommendations'], 1):
            print(f"   {i}. {recommendation}")
            
        print("\n" + "="*80)
        
    def save_detailed_report(self, summary: Dict, output_file: str = None):
        """Sauvegarde un rapport détaillé"""
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"orchestrator_log_analysis_{timestamp}.json"
            
        # Ajouter les détails complets
        detailed_summary = {**summary}
        detailed_summary['detailed_issues'] = self.issues
        detailed_summary['file_details'] = self.file_details
        detailed_summary['analyzed_logs'] = [str(f) for f in self.log_files]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_summary, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Rapport détaillé sauvegardé: {output_file}")
        return output_file

def main():
    """Point d'entrée principal"""
    
    print("🔍 ANALYSEUR DES LOGS D'ORCHESTRATEUR")
    print("=" * 60)
    
    try:
        analyzer = OrchestratorLogAnalyzer()
        analyzer.analyze_logs()
        summary = analyzer.generate_summary()
        analyzer.print_summary(summary)
        output_file = analyzer.save_detailed_report(summary)
        
        print(f"\n🎯 ACTIONS RECOMMANDÉES:")
        print(f"   1. Consultez le rapport détaillé: {output_file}")
        print(f"   2. Analysez les fichiers problématiques avec:")
        print(f"      python analyze_dpgf_file.py <chemin_fichier>")
        print(f"   3. Pour les imports techniques sans données, vérifiez:")
        print(f"      - La structure Excel (feuilles, colonnes)")
        print(f"      - Les mots-clés DPGF dans le contenu")
        print(f"      - Les patterns de reconnaissance")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
