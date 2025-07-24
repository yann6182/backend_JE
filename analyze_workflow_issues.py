#!/usr/bin/env python3
"""
Analyseur des problèmes d'import dans les rapports de workflow.
Identifie les fichiers DPGF identifiés mais non importés ou avec des imports techniques.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

class WorkflowIssueAnalyzer:
    """Analyseur des problèmes d'import des workflows"""
    
    def __init__(self):
        self.reports_dir = Path("reports")
        self.issues = []
        self.stats = defaultdict(int)
        
    def analyze_all_reports(self) -> Dict:
        """Analyse tous les rapports de workflow disponibles"""
        
        if not self.reports_dir.exists():
            print("❌ Répertoire 'reports' non trouvé")
            return {}
            
        report_files = list(self.reports_dir.glob("workflow_progress_*.json"))
        
        if not report_files:
            print("❌ Aucun rapport de workflow trouvé")
            return {}
            
        print(f"📊 Analyse de {len(report_files)} rapports...")
        
        # Analyser chaque rapport
        for report_file in sorted(report_files):
            try:
                self.analyze_single_report(report_file)
            except Exception as e:
                print(f"❌ Erreur lors de l'analyse de {report_file}: {e}")
                
        # Générer le rapport de synthèse
        return self.generate_summary()
        
    def analyze_single_report(self, report_file: Path):
        """Analyse un seul rapport de workflow"""
        
        print(f"\n🔍 Analyse du rapport: {report_file.name}")
        
        with open(report_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        metadata = data.get('metadata', {})
        statistics = data.get('statistics', {})
        detailed_results = data.get('detailed_results', [])
        
        print(f"   📅 Généré le: {metadata.get('generated_at', 'N/A')}")
        print(f"   📈 Fichiers identifiés: {statistics.get('total_identified_files', 0)}")
        print(f"   ✅ Fichiers importés: {statistics.get('total_imported_files', 0)}")
        
        # Analyser les résultats détaillés
        for folder_result in detailed_results:
            identified_files = folder_result.get('identified_files', [])
            
            for file_info in identified_files:
                file_path = file_info.get('path', '')
                file_name = file_info.get('name', '')
                file_type = file_info.get('type', '')
                confidence = file_info.get('confidence', 0)
                
                # Vérifier si le fichier a été importé avec succès
                import_info = file_info.get('import_info', {})
                import_status = import_info.get('status', 'unknown')
                
                self.stats['total_identified'] += 1
                
                if file_type == 'DPGF':
                    self.stats['dpgf_identified'] += 1
                    
                    if import_status == 'success':
                        # Vérifier si c'est un import technique sans données
                        lots_imported = import_info.get('lots_imported', 0)
                        sections_imported = import_info.get('sections_imported', 0)
                        elements_imported = import_info.get('elements_imported', 0)
                        
                        if lots_imported == 0 and sections_imported == 0 and elements_imported == 0:
                            # Import technique sans données
                            self.issues.append({
                                'type': 'import_technique_sans_donnees',
                                'file_path': file_path,
                                'file_name': file_name,
                                'confidence': confidence,
                                'report_file': report_file.name,
                                'folder': folder_result.get('folder_path', ''),
                                'message': 'Fichier identifié comme DPGF mais import technique sans lots/sections/éléments'
                            })
                            self.stats['dpgf_import_technique'] += 1
                        else:
                            self.stats['dpgf_import_success'] += 1
                            
                    elif import_status == 'failed':
                        # Import échoué
                        self.issues.append({
                            'type': 'import_echec',
                            'file_path': file_path,
                            'file_name': file_name,
                            'confidence': confidence,
                            'report_file': report_file.name,
                            'folder': folder_result.get('folder_path', ''),
                            'error': import_info.get('error', 'Erreur non spécifiée'),
                            'message': 'Échec d\'import du fichier DPGF'
                        })
                        self.stats['dpgf_import_failed'] += 1
                        
                    elif import_status == 'unknown' or import_status == 'not_attempted':
                        # Import non tenté ou statut inconnu
                        self.issues.append({
                            'type': 'import_non_tente',
                            'file_path': file_path,
                            'file_name': file_name,
                            'confidence': confidence,
                            'report_file': report_file.name,
                            'folder': folder_result.get('folder_path', ''),
                            'message': 'Fichier DPGF identifié mais import non tenté'
                        })
                        self.stats['dpgf_import_not_attempted'] += 1
                        
    def generate_summary(self) -> Dict:
        """Génère un rapport de synthèse des problèmes"""
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'statistics': dict(self.stats),
            'issues_by_type': defaultdict(list),
            'top_problematic_files': [],
            'recommendations': []
        }
        
        # Grouper les problèmes par type
        for issue in self.issues:
            issue_type = issue['type']
            summary['issues_by_type'][issue_type].append(issue)
            
        # Identifier les fichiers les plus problématiques
        file_problem_count = defaultdict(int)
        for issue in self.issues:
            file_problem_count[issue['file_name']] += 1
            
        summary['top_problematic_files'] = [
            {'file_name': name, 'problem_count': count}
            for name, count in sorted(file_problem_count.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Générer des recommandations
        summary['recommendations'] = self.generate_recommendations()
        
        return summary
        
    def generate_recommendations(self) -> List[str]:
        """Génère des recommandations basées sur l'analyse"""
        
        recommendations = []
        
        if self.stats['dpgf_import_technique'] > 0:
            recommendations.append(
                f"🔍 {self.stats['dpgf_import_technique']} fichiers DPGF identifiés produisent des imports techniques sans données. "
                "Vérifiez la structure Excel de ces fichiers avec l'outil analyze_dpgf_file.py"
            )
            
        if self.stats['dpgf_import_failed'] > 0:
            recommendations.append(
                f"❌ {self.stats['dpgf_import_failed']} fichiers DPGF ont échoué à l'import. "
                "Consultez les logs d'erreur pour identifier les causes (accès fichier, corruption, etc.)"
            )
            
        if self.stats['dpgf_import_not_attempted'] > 0:
            recommendations.append(
                f"⏭️ {self.stats['dpgf_import_not_attempted']} fichiers DPGF identifiés n'ont pas été importés. "
                "Vérifiez la configuration auto_import de l'orchestrateur"
            )
            
        # Calculer le taux de succès
        total_dpgf = self.stats['dpgf_identified']
        if total_dpgf > 0:
            success_rate = (self.stats['dpgf_import_success'] / total_dpgf) * 100
            recommendations.append(
                f"📊 Taux de succès d'import DPGF: {success_rate:.1f}% "
                f"({self.stats['dpgf_import_success']}/{total_dpgf})"
            )
            
        if success_rate < 80:
            recommendations.append(
                "⚠️ Le taux de succès d'import est faible. Considérez :\n"
                "   - Améliorer la détection des patterns DPGF\n"
                "   - Vérifier les critères d'identification\n"
                "   - Analyser les structures Excel non reconnues"
            )
            
        return recommendations
        
    def print_summary(self, summary: Dict):
        """Affiche le résumé de l'analyse"""
        
        print("\n" + "="*80)
        print("📊 RAPPORT D'ANALYSE DES PROBLÈMES D'IMPORT")
        print("="*80)
        
        # Statistiques générales
        print(f"\n📈 STATISTIQUES GÉNÉRALES:")
        print(f"   Total fichiers identifiés: {summary['statistics']['total_identified']}")
        print(f"   Fichiers DPGF identifiés: {summary['statistics']['dpgf_identified']}")
        print(f"   Imports DPGF réussis: {summary['statistics']['dpgf_import_success']}")
        print(f"   Imports DPGF techniques (sans données): {summary['statistics']['dpgf_import_technique']}")
        print(f"   Imports DPGF échoués: {summary['statistics']['dpgf_import_failed']}")
        print(f"   Imports DPGF non tentés: {summary['statistics']['dpgf_import_not_attempted']}")
        
        # Problèmes par type
        print(f"\n🔍 PROBLÈMES IDENTIFIÉS:")
        for issue_type, issues in summary['issues_by_type'].items():
            print(f"   {issue_type}: {len(issues)} fichiers")
            
        # Fichiers les plus problématiques
        if summary['top_problematic_files']:
            print(f"\n🎯 FICHIERS LES PLUS PROBLÉMATIQUES:")
            for file_info in summary['top_problematic_files'][:5]:
                print(f"   {file_info['file_name']}: {file_info['problem_count']} problèmes")
                
        # Recommandations
        print(f"\n💡 RECOMMANDATIONS:")
        for i, recommendation in enumerate(summary['recommendations'], 1):
            print(f"   {i}. {recommendation}")
            
        print("\n" + "="*80)
        
    def save_detailed_report(self, summary: Dict, output_file: str = None):
        """Sauvegarde un rapport détaillé"""
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"workflow_issues_analysis_{timestamp}.json"
            
        # Ajouter les détails des problèmes
        detailed_summary = {**summary}
        detailed_summary['detailed_issues'] = self.issues
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_summary, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Rapport détaillé sauvegardé: {output_file}")
        return output_file

def main():
    """Point d'entrée principal"""
    
    print("🔍 ANALYSEUR DES PROBLÈMES D'IMPORT WORKFLOW")
    print("=" * 60)
    
    try:
        analyzer = WorkflowIssueAnalyzer()
        summary = analyzer.analyze_all_reports()
        
        if summary:
            analyzer.print_summary(summary)
            output_file = analyzer.save_detailed_report(summary)
            
            print(f"\n🎯 ACTIONS RECOMMANDÉES:")
            print(f"   1. Consultez le rapport détaillé: {output_file}")
            print(f"   2. Analysez les fichiers problématiques avec: python analyze_dpgf_file.py <fichier>")
            print(f"   3. Vérifiez les logs d'orchestrateur pour plus de détails")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
