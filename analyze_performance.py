"""
Script d'analyse des performances et d'amélioration du workflow DPGF.
Ce script identifie les goulots d'étranglement et propose des optimisations.
"""

import sys
import os
import time
import traceback
import psutil
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import json

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from scripts.import_complete import DPGFImporter, ExcelParser
from scripts.identify_relevant_files_sharepoint import SharePointClient


class PerformanceAnalyzer:
    """Analyseur de performance pour identifier les goulots d'étranglement"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.results = []
        
    def analyze_file_performance(self, file_path: str, sharepoint_client: SharePointClient = None) -> Dict:
        """Analyse les performances d'import d'un fichier spécifique"""
        start_time = time.time()
        file_size = 0
        sheet_count = 0
        row_count = 0
        col_count = 0
        memory_before = psutil.virtual_memory().percent
        
        result = {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'success': False,
            'error': None,
            'timing': {},
            'memory': {},
            'file_stats': {},
            'processing_stats': {}
        }
        
        try:
            # 1. Analyse initiale du fichier
            parse_start = time.time()
            
            if sharepoint_client and file_path.startswith('http'):
                # Télécharger depuis SharePoint
                temp_file = sharepoint_client.download_file(file_path, "temp_analysis.xlsx")
                analysis_file = temp_file
            else:
                analysis_file = file_path
                
            # Obtenir les stats du fichier
            if os.path.exists(analysis_file):
                file_size = os.path.getsize(analysis_file)
                
                # Analyser la structure Excel
                excel_file = pd.ExcelFile(analysis_file)
                sheet_count = len(excel_file.sheet_names)
                
                # Analyser la taille de chaque feuille
                largest_sheet_rows = 0
                largest_sheet_cols = 0
                for sheet in excel_file.sheet_names:
                    try:
                        df = pd.read_excel(analysis_file, sheet_name=sheet, nrows=5)  # Échantillon
                        if len(df) > 0:
                            # Estimer la taille totale
                            full_df = pd.read_excel(analysis_file, sheet_name=sheet)
                            sheet_rows = len(full_df)
                            sheet_cols = len(full_df.columns)
                            
                            if sheet_rows > largest_sheet_rows:
                                largest_sheet_rows = sheet_rows
                                largest_sheet_cols = sheet_cols
                    except Exception as e:
                        print(f"   ⚠️ Erreur analyse feuille {sheet}: {e}")
                
                row_count = largest_sheet_rows
                col_count = largest_sheet_cols
                
            parse_time = time.time() - parse_start
            
            # 2. Test de parsing avec ExcelParser
            parser_start = time.time()
            try:
                parser = ExcelParser(analysis_file, None, None, dry_run=True)
                header_row = parser.find_header_row()
                col_indices = parser.detect_column_indices(header_row) if header_row is not None else {}
                items = parser.detect_sections_and_elements(header_row) if header_row is not None else []
                
                parser_time = time.time() - parser_start
                
                result['processing_stats'] = {
                    'header_row_found': header_row is not None,
                    'header_row_index': header_row,
                    'columns_detected': len(col_indices),
                    'items_detected': len(items),
                    'sections_count': sum(1 for item in items if item.get('type') == 'section'),
                    'elements_count': sum(1 for item in items if item.get('type') == 'element')
                }
                
            except Exception as e:
                parser_time = time.time() - parser_start
                result['error'] = f"Erreur parsing: {str(e)}"
                print(f"   ❌ Erreur parsing: {e}")
                
            # 3. Statistiques finales
            total_time = time.time() - start_time
            memory_after = psutil.virtual_memory().percent
            
            result.update({
                'success': True,
                'timing': {
                    'total_time': total_time,
                    'parse_time': parse_time,
                    'parser_time': parser_time,
                    'time_per_row': parser_time / max(row_count, 1) if row_count > 0 else 0
                },
                'memory': {
                    'before_percent': memory_before,
                    'after_percent': memory_after,
                    'delta_percent': memory_after - memory_before
                },
                'file_stats': {
                    'size_bytes': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'sheet_count': sheet_count,
                    'row_count': row_count,
                    'col_count': col_count
                }
            })
            
            # Nettoyer le fichier temporaire si nécessaire
            if sharepoint_client and file_path.startswith('http') and os.path.exists(analysis_file):
                try:
                    os.remove(analysis_file)
                except:
                    pass
                    
        except Exception as e:
            total_time = time.time() - start_time
            result.update({
                'success': False,
                'error': str(e),
                'timing': {'total_time': total_time}
            })
            
        return result
    
    def analyze_api_performance(self) -> Dict:
        """Teste les performances de l'API"""
        print("🔍 Test performances API...")
        
        api_results = {
            'base_url': self.base_url,
            'connectivity': False,
            'response_times': {},
            'errors': []
        }
        
        # Test de connectivité
        try:
            start = time.time()
            response = requests.get(f"{self.base_url}/docs", timeout=10)
            api_results['connectivity'] = response.status_code == 200
            api_results['response_times']['docs'] = time.time() - start
        except Exception as e:
            api_results['errors'].append(f"Connectivité: {str(e)}")
        
        # Test des endpoints principaux
        endpoints = [
            '/api/v1/clients/',
            '/api/v1/dpgfs/',
            '/api/v1/lots/',
            '/api/v1/sections/',
            '/api/v1/elements/'
        ]
        
        for endpoint in endpoints:
            try:
                start = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                api_results['response_times'][endpoint] = time.time() - start
                if response.status_code not in [200, 404]:  # 404 peut être normal si pas de données
                    api_results['errors'].append(f"{endpoint}: HTTP {response.status_code}")
            except Exception as e:
                api_results['errors'].append(f"{endpoint}: {str(e)}")
        
        return api_results
    
    def generate_performance_report(self, file_results: List[Dict], api_results: Dict) -> str:
        """Génère un rapport de performance complet"""
        report_lines = [
            "# RAPPORT D'ANALYSE DE PERFORMANCE DPGF",
            f"Généré le: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## RÉSUMÉ EXÉCUTIF"
        ]
        
        # Statistiques globales
        total_files = len(file_results)
        successful_files = sum(1 for r in file_results if r['success'])
        failed_files = total_files - successful_files
        
        if total_files > 0:
            avg_time = sum(r['timing']['total_time'] for r in file_results if 'timing' in r) / total_files
            avg_size = sum(r['file_stats']['size_mb'] for r in file_results if 'file_stats' in r) / total_files
            
            report_lines.extend([
                f"- **Fichiers analysés**: {total_files}",
                f"- **Succès**: {successful_files} ({successful_files/total_files*100:.1f}%)",
                f"- **Échecs**: {failed_files} ({failed_files/total_files*100:.1f}%)",
                f"- **Temps moyen par fichier**: {avg_time:.2f}s",
                f"- **Taille moyenne**: {avg_size:.2f} MB",
                ""
            ])
        
        # Performance API
        report_lines.extend([
            "## PERFORMANCE API",
            f"- **URL**: {api_results['base_url']}",
            f"- **Connectivité**: {'✅ OK' if api_results['connectivity'] else '❌ ERREUR'}",
            ""
        ])
        
        if api_results['response_times']:
            report_lines.append("### Temps de réponse par endpoint:")
            for endpoint, time_ms in api_results['response_times'].items():
                status = "✅" if time_ms < 1.0 else "⚠️" if time_ms < 5.0 else "❌"
                report_lines.append(f"- `{endpoint}`: {time_ms:.3f}s {status}")
            report_lines.append("")
        
        if api_results['errors']:
            report_lines.append("### Erreurs API:")
            for error in api_results['errors']:
                report_lines.append(f"- ❌ {error}")
            report_lines.append("")
        
        # Analyse détaillée des fichiers
        if file_results:
            report_lines.extend([
                "## ANALYSE DÉTAILLÉE DES FICHIERS",
                ""
            ])
            
            # Fichiers problématiques
            slow_files = [r for r in file_results if r.get('timing', {}).get('total_time', 0) > 30]
            if slow_files:
                report_lines.extend([
                    "### ⚠️ Fichiers lents (>30s):",
                    ""
                ])
                for result in slow_files:
                    time_taken = result['timing']['total_time']
                    size_mb = result.get('file_stats', {}).get('size_mb', 0)
                    report_lines.append(f"- **{result['file_name']}**: {time_taken:.1f}s ({size_mb:.1f}MB)")
                report_lines.append("")
            
            # Fichiers en erreur
            error_files = [r for r in file_results if not r['success']]
            if error_files:
                report_lines.extend([
                    "### ❌ Fichiers en erreur:",
                    ""
                ])
                for result in error_files:
                    error = result.get('error', 'Erreur inconnue')
                    report_lines.append(f"- **{result['file_name']}**: {error}")
                report_lines.append("")
        
        # Recommandations
        report_lines.extend([
            "## RECOMMANDATIONS",
            ""
        ])
        
        if failed_files > 0:
            report_lines.append("### Gestion des erreurs:")
            report_lines.append("- Implémenter un retry automatique avec backoff exponentiel")
            report_lines.append("- Ajouter une gestion spécifique des timeouts")
            report_lines.append("- Améliorer la détection des fichiers corrompus")
            report_lines.append("")
        
        if slow_files:
            report_lines.append("### Optimisation des performances:")
            report_lines.append("- Augmenter les timeouts pour les gros fichiers")
            report_lines.append("- Implémenter un processing par chunks plus petit")
            report_lines.append("- Considérer un processing asynchrone avec queue")
            report_lines.append("")
        
        if not api_results['connectivity']:
            report_lines.append("### API:")
            report_lines.append("- Vérifier que l'API est démarrée")
            report_lines.append("- Vérifier la connectivité réseau")
            report_lines.append("")
        
        return "\\n".join(report_lines)


def main():
    """Test de performance sur quelques fichiers représentatifs"""
    print("🔍 ANALYSE DE PERFORMANCE DPGF")
    print("=" * 50)
    
    analyzer = PerformanceAnalyzer()
    
    # 1. Test API
    print("\\n1️⃣ Test performance API...")
    api_results = analyzer.analyze_api_performance()
    
    if api_results['connectivity']:
        print("   ✅ API accessible")
        for endpoint, time_taken in api_results['response_times'].items():
            status = "✅" if time_taken < 1.0 else "⚠️" if time_taken < 5.0 else "❌"
            print(f"   {status} {endpoint}: {time_taken:.3f}s")
    else:
        print("   ❌ API non accessible")
        for error in api_results['errors']:
            print(f"      {error}")
    
    # 2. Test fichiers SharePoint
    print("\\n2️⃣ Test performance fichiers SharePoint...")
    try:
        sharepoint_client = SharePointClient()
        
        # Quelques fichiers test représentatifs
        test_files = [
            "3296-DCE-DPGF-Lot 08 MOBILIERS.xlsx",  # Fichier moyen
            "DPGF-Lot 06 Métallerie-Serrurerie - Nov 2024.xlsx",  # Fichier complexe
        ]
        
        file_results = []
        
        for filename in test_files:
            print(f"\\n   📁 Analyse: {filename}")
            
            # Trouver le fichier dans SharePoint
            sharepoint_path = None
            try:
                items = sharepoint_client.list_files("", recursive=True, limit=1000)
                for item in items:
                    if item['name'] == filename:
                        sharepoint_path = item['download_url']
                        break
                
                if sharepoint_path:
                    result = analyzer.analyze_file_performance(sharepoint_path, sharepoint_client)
                    file_results.append(result)
                    
                    if result['success']:
                        timing = result['timing']
                        stats = result['file_stats']
                        processing = result['processing_stats']
                        
                        print(f"      ✅ Succès en {timing['total_time']:.1f}s")
                        print(f"         Taille: {stats['size_mb']:.1f}MB, {stats['row_count']} lignes")
                        print(f"         Détecté: {processing['sections_count']} sections, {processing['elements_count']} éléments")
                        
                        if timing['total_time'] > 30:
                            print(f"      ⚠️ LENT: {timing['total_time']:.1f}s")
                        
                    else:
                        print(f"      ❌ Erreur: {result['error']}")
                else:
                    print(f"      ⚠️ Fichier non trouvé dans SharePoint")
                    
            except Exception as e:
                print(f"      ❌ Erreur analyse: {e}")
                file_results.append({
                    'file_name': filename,
                    'success': False,
                    'error': str(e)
                })
        
        # 3. Générer le rapport
        print("\\n3️⃣ Génération du rapport...")
        report = analyzer.generate_performance_report(file_results, api_results)
        
        # Sauvegarder le rapport
        report_file = "performance_analysis_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"   ✅ Rapport sauvegardé: {report_file}")
        
        # Afficher un résumé
        if file_results:
            successful = sum(1 for r in file_results if r['success'])
            total = len(file_results)
            print(f"\\n📊 RÉSUMÉ: {successful}/{total} fichiers analysés avec succès")
            
            if successful > 0:
                avg_time = sum(r['timing']['total_time'] for r in file_results if r['success']) / successful
                print(f"   ⏱️ Temps moyen: {avg_time:.1f}s")
                
                slow_files = [r for r in file_results if r['success'] and r['timing']['total_time'] > 30]
                if slow_files:
                    print(f"   ⚠️ {len(slow_files)} fichier(s) lent(s) (>30s)")
    
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
