"""
Script d'amélioration des performances et de gestion des timeouts pour l'import DPGF.
Ce script propose des optimisations concrètes basées sur l'analyse des performances.
"""

import os
import sys
import time
import argparse
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('performance_optimization.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TimeoutOptimizer:
    """Gestionnaire d'optimisation des timeouts et retry logic"""
    
    def __init__(self, base_timeout: int = 600, max_retries: int = 3):
        self.base_timeout = base_timeout
        self.max_retries = max_retries
        self.stats = {
            'successful_imports': 0,
            'timeout_retries': 0,
            'permanent_failures': 0,
            'total_time_saved': 0
        }
    
    def calculate_adaptive_timeout(self, file_size_mb: float, complexity_score: float = 1.0) -> int:
        """
        Calcule un timeout adaptatif basé sur la taille du fichier et sa complexité
        
        Args:
            file_size_mb: Taille du fichier en MB
            complexity_score: Score de complexité (1.0 = normal, 2.0 = complexe)
        
        Returns:
            Timeout en secondes
        """
        # Formule adaptative: 60s de base + 30s par MB + multiplicateur de complexité
        adaptive_timeout = int(60 + (file_size_mb * 30) + (complexity_score * 120))
        
        # Limites raisonnables
        return max(180, min(adaptive_timeout, 1800))  # Entre 3 min et 30 min
    
    def import_with_retry(self, import_cmd: List[str], file_path: str, 
                         timeout: Optional[int] = None) -> Tuple[bool, str, Dict]:
        """
        Exécute l'import avec retry et gestion intelligente des timeouts
        
        Returns:
            (success, error_message, stats)
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
        
        if timeout is None:
            timeout = self.calculate_adaptive_timeout(file_size_mb)
        
        attempt_stats = {
            'attempts': [],
            'total_time': 0,
            'final_timeout': timeout
        }
        
        for attempt in range(1, self.max_retries + 1):
            attempt_start = time.time()
            
            logger.info(f"   Tentative {attempt}/{self.max_retries} - Timeout: {timeout}s")
            
            try:
                result = subprocess.run(
                    import_cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=timeout,
                    cwd=Path(__file__).parent,
                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
                )
                
                attempt_time = time.time() - attempt_start
                attempt_stats['attempts'].append({
                    'attempt': attempt,
                    'duration': attempt_time,
                    'timeout_used': timeout,
                    'return_code': result.returncode,
                    'success': result.returncode == 0
                })
                
                if result.returncode == 0:
                    attempt_stats['total_time'] = sum(a['duration'] for a in attempt_stats['attempts'])
                    self.stats['successful_imports'] += 1
                    logger.info(f"   ✅ Import réussi en {attempt_time:.1f}s (tentative {attempt})")
                    return True, "", attempt_stats
                else:
                    logger.warning(f"   ❌ Tentative {attempt} échouée (code {result.returncode})")
                    if result.stderr:
                        logger.warning(f"      Erreur: {result.stderr[:300]}")
                    
                    # Si c'est pas la dernière tentative, continuer
                    if attempt < self.max_retries:
                        # Augmenter le timeout pour la prochaine tentative
                        timeout = int(timeout * 1.5)
                        logger.info(f"   ⏳ Augmentation du timeout à {timeout}s pour la prochaine tentative")
                        time.sleep(5)  # Pause avant retry
                        continue
            
            except subprocess.TimeoutExpired:
                attempt_time = time.time() - attempt_start
                attempt_stats['attempts'].append({
                    'attempt': attempt,
                    'duration': attempt_time,
                    'timeout_used': timeout,
                    'return_code': 'TIMEOUT',
                    'success': False
                })
                
                self.stats['timeout_retries'] += 1
                logger.warning(f"   ⏰ Timeout tentative {attempt} après {timeout}s")
                
                if attempt < self.max_retries:
                    # Stratégie d'augmentation du timeout
                    if file_size_mb > 5:  # Gros fichiers
                        timeout = int(timeout * 2.0)  # Doubler le timeout
                    else:
                        timeout = int(timeout * 1.5)  # Augmentation modérée
                    
                    logger.info(f"   ⏳ Retry avec timeout étendu: {timeout}s")
                    time.sleep(10)  # Pause plus longue après timeout
                    continue
            
            except Exception as e:
                attempt_time = time.time() - attempt_start
                attempt_stats['attempts'].append({
                    'attempt': attempt,
                    'duration': attempt_time,
                    'timeout_used': timeout,
                    'return_code': 'ERROR',
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"   💥 Erreur tentative {attempt}: {e}")
                break
        
        # Toutes les tentatives ont échoué
        attempt_stats['total_time'] = sum(a['duration'] for a in attempt_stats['attempts'])
        self.stats['permanent_failures'] += 1
        
        return False, "Échec après toutes les tentatives", attempt_stats


class ImportOptimizer:
    """Optimiseur principal pour l'import DPGF"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.timeout_optimizer = TimeoutOptimizer()
        self.performance_data = []
    
    def analyze_file_complexity(self, file_path: str) -> float:
        """
        Analyse la complexité d'un fichier pour ajuster les timeouts
        
        Returns:
            Score de complexité (1.0 = normal, 2.0+ = complexe)
        """
        try:
            import pandas as pd
            
            # Analyser la structure du fichier
            excel_file = pd.ExcelFile(file_path)
            sheet_count = len(excel_file.sheet_names)
            
            complexity_score = 1.0
            
            # Facteurs de complexité
            if sheet_count > 5:
                complexity_score += 0.3  # Nombreuses feuilles
            
            # Analyser la taille des données dans chaque feuille
            total_cells = 0
            for sheet in excel_file.sheet_names[:3]:  # Analyser max 3 feuilles
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet, nrows=10)
                    if len(df) > 0:
                        # Estimer la taille totale
                        full_df = pd.read_excel(file_path, sheet_name=sheet)
                        cells_in_sheet = len(full_df) * len(full_df.columns)
                        total_cells += cells_in_sheet
                        
                        if len(full_df) > 1000:  # Beaucoup de lignes
                            complexity_score += 0.2
                        if len(full_df.columns) > 20:  # Beaucoup de colonnes
                            complexity_score += 0.2
                except:
                    complexity_score += 0.1  # Feuille problématique
            
            # Facteur basé sur le nombre total de cellules
            if total_cells > 50000:
                complexity_score += 0.5
            elif total_cells > 10000:
                complexity_score += 0.3
            
            # Analyser le nom du fichier pour détecter certains patterns
            filename = Path(file_path).name.lower()
            complex_patterns = ['metallerie', 'serrurerie', 'menuiserie', 'annexe', 'complex']
            if any(pattern in filename for pattern in complex_patterns):
                complexity_score += 0.2
            
            return min(complexity_score, 3.0)  # Plafond à 3.0
            
        except Exception as e:
            logger.warning(f"Erreur analyse complexité {file_path}: {e}")
            return 1.5  # Score de sécurité en cas d'erreur
    
    def optimize_import_batch(self, file_list: List[str], output_dir: str = "optimized_imports") -> Dict:
        """
        Optimise l'import d'un batch de fichiers avec gestion intelligente des timeouts
        """
        os.makedirs(output_dir, exist_ok=True)
        
        results = {
            'total_files': len(file_list),
            'successful': 0,
            'failed': 0,
            'timeout_optimizations': 0,
            'time_saved_estimate': 0,
            'detailed_results': []
        }
        
        logger.info(f"🚀 Début de l'import optimisé de {len(file_list)} fichiers")
        
        for i, file_path in enumerate(file_list, 1):
            file_name = Path(file_path).name
            logger.info(f"\\n📁 [{i}/{len(file_list)}] {file_name}")
            
            start_time = time.time()
            
            # Analyser la complexité du fichier
            complexity_score = self.analyze_file_complexity(file_path)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            logger.info(f"   📊 Taille: {file_size_mb:.1f}MB, Complexité: {complexity_score:.1f}")
            
            # Calculer le timeout optimisé
            optimized_timeout = self.timeout_optimizer.calculate_adaptive_timeout(
                file_size_mb, complexity_score
            )
            
            # Préparer la commande d'import
            import_cmd = [
                sys.executable, "scripts/import_complete.py",
                "--file", file_path,
                "--base-url", self.base_url
            ]
            
            # Import avec retry intelligent
            success, error, attempt_stats = self.timeout_optimizer.import_with_retry(
                import_cmd, file_path, optimized_timeout
            )
            
            total_time = time.time() - start_time
            
            # Calculer le temps économisé par rapport à un timeout fixe
            fixed_timeout_estimate = 600  # Timeout fixe de 10 min
            if success and total_time < fixed_timeout_estimate:
                time_saved = fixed_timeout_estimate - total_time
                results['time_saved_estimate'] += time_saved
            
            file_result = {
                'file_name': file_name,
                'file_path': file_path,
                'file_size_mb': file_size_mb,
                'complexity_score': complexity_score,
                'optimized_timeout': optimized_timeout,
                'success': success,
                'error': error,
                'total_time': total_time,
                'attempt_stats': attempt_stats
            }
            
            if success:
                results['successful'] += 1
                if len(attempt_stats['attempts']) > 1:
                    results['timeout_optimizations'] += 1
            else:
                results['failed'] += 1
            
            results['detailed_results'].append(file_result)
            
            # Sauvegarder les résultats partiels
            if i % 5 == 0:  # Tous les 5 fichiers
                self.save_optimization_report(results, f"{output_dir}/partial_results_{i}.json")
        
        # Rapport final
        logger.info(f"\\n✅ Import optimisé terminé:")
        logger.info(f"   Succès: {results['successful']}/{results['total_files']}")
        logger.info(f"   Échecs: {results['failed']}")
        logger.info(f"   Optimisations timeout: {results['timeout_optimizations']}")
        logger.info(f"   Temps économisé estimé: {results['time_saved_estimate']:.1f}s")
        
        # Sauvegarder le rapport final
        final_report_path = f"{output_dir}/optimization_report_final.json"
        self.save_optimization_report(results, final_report_path)
        
        return results
    
    def save_optimization_report(self, results: Dict, file_path: str):
        """Sauvegarde le rapport d'optimisation"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"   📄 Rapport sauvegardé: {file_path}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde rapport: {e}")
    
    def generate_recommendations(self, results: Dict) -> List[str]:
        """Génère des recommandations basées sur les résultats"""
        recommendations = []
        
        if results['failed'] > 0:
            failure_rate = results['failed'] / results['total_files']
            if failure_rate > 0.2:  # Plus de 20% d'échecs
                recommendations.extend([
                    "🔧 Taux d'échec élevé détecté:",
                    "   • Augmenter les timeouts de base dans l'orchestrateur",
                    "   • Vérifier la disponibilité de la base de données",
                    "   • Considérer l'ajout de plus de mémoire système"
                ])
        
        if results['timeout_optimizations'] > 0:
            recommendations.extend([
                f"⚡ {results['timeout_optimizations']} fichiers ont bénéficié de l'optimisation timeout",
                "   • L'adaptation dynamique des timeouts améliore les performances",
                "   • Implémenter cette logique dans l'orchestrateur principal"
            ])
        
        if results['time_saved_estimate'] > 300:  # Plus de 5 min économisées
            recommendations.extend([
                f"🚀 Temps économisé estimé: {results['time_saved_estimate']:.1f}s",
                "   • Les timeouts adaptatifs réduisent les attentes inutiles",
                "   • Gain de productivité significatif identifié"
            ])
        
        # Analyser les échecs récurrents
        failed_files = [r for r in results['detailed_results'] if not r['success']]
        if failed_files:
            large_failures = [f for f in failed_files if f['file_size_mb'] > 5]
            if large_failures:
                recommendations.append("📊 Gros fichiers problématiques détectés - considérer le chunking")
        
        return recommendations


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description="Optimisation des performances d'import DPGF")
    parser.add_argument("--test-files", nargs="+", help="Liste des fichiers à tester")
    parser.add_argument("--test-dir", help="Répertoire contenant les fichiers de test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de l'API")
    parser.add_argument("--output-dir", default="performance_optimization_results", help="Répertoire de sortie")
    
    args = parser.parse_args()
    
    optimizer = ImportOptimizer(args.base_url)
    
    # Déterminer la liste des fichiers
    if args.test_files:
        test_files = args.test_files
    elif args.test_dir:
        test_dir = Path(args.test_dir)
        test_files = list(test_dir.glob("*.xlsx")) + list(test_dir.glob("*.xls"))
        test_files = [str(f) for f in test_files]
    else:
        # Utiliser les fichiers de test par défaut
        test_dir = Path("test_data")
        if test_dir.exists():
            test_files = list(test_dir.glob("*.xlsx")) + list(test_dir.glob("*.xls"))
            test_files = [str(f) for f in test_files[:3]]  # Limiter à 3 pour les tests
        else:
            logger.error("Aucun fichier de test trouvé. Spécifiez --test-files ou --test-dir")
            return
    
    if not test_files:
        logger.error("Aucun fichier à traiter")
        return
    
    logger.info(f"🎯 Fichiers sélectionnés pour optimisation: {len(test_files)}")
    for f in test_files:
        logger.info(f"   • {Path(f).name}")
    
    # Lancer l'optimisation
    results = optimizer.optimize_import_batch(test_files, args.output_dir)
    
    # Générer les recommandations
    recommendations = optimizer.generate_recommendations(results)
    
    logger.info("\\n💡 RECOMMANDATIONS:")
    for rec in recommendations:
        logger.info(rec)


if __name__ == "__main__":
    main()
