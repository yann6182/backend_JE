#!/usr/bin/env python3
"""
Système de maintenance automatique pour l'orchestrateur DPGF.

Ce script effectue des tâches de maintenance automatique pour optimiser
les performances, nettoyer les logs, résoudre les problèmes récurrents
et maintenir la santé globale du système.

Fonctionnalités :
- Nettoyage automatique des logs anciens
- Optimisation de la base de données
- Résolution automatique des problèmes courants
- Mise à jour des configurations
- Archivage des rapports
- Vérification et réparation des fichiers corrompus

Auteur: Assistant IA
Date: 2024
"""

import os
import sys
import json
import time
import shutil
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple, Any
import argparse
import subprocess
import zipfile
import hashlib
from dataclasses import dataclass
from enum import Enum

# Configuration de l'encodage pour Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class MaintenanceTaskType(Enum):
    """Types de tâches de maintenance"""
    CLEANUP = "cleanup"
    OPTIMIZATION = "optimization"
    REPAIR = "repair"
    ARCHIVE = "archive"
    UPDATE = "update"

@dataclass
class MaintenanceTask:
    """Tâche de maintenance"""
    name: str
    task_type: MaintenanceTaskType
    description: str
    priority: int  # 1=critical, 2=high, 3=medium, 4=low
    estimated_duration: int  # en secondes
    auto_executable: bool = True
    
class AutomaticMaintenance:
    """Système de maintenance automatique"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.setup_logging()
        
        # Statistiques de maintenance
        self.maintenance_stats = {
            "tasks_executed": 0,
            "files_cleaned": 0,
            "space_freed": 0,
            "errors_fixed": 0,
            "start_time": None,
            "end_time": None
        }
        
        # Tâches de maintenance disponibles
        self.available_tasks = self._initialize_maintenance_tasks()
        
    def _load_config(self, config_file: Optional[str]) -> Dict:
        """Charge la configuration"""
        default_config = {
            "log_retention_days": 30,
            "report_retention_days": 90,
            "archive_threshold_days": 7,
            "max_log_size_mb": 100,
            "cleanup_schedule": "daily",
            "auto_cleanup": True,
            "auto_optimization": True,
            "auto_repair": False,  # Plus conservateur
            "directories": {
                "logs": ["logs", "logs_orchestrator", "logs_production", "logs_test"],
                "reports": ["reports", "reports_orchestrator", "reports_production", "reports_test"],
                "cache": ["cache", "temp", "__pycache__"],
                "archives": ["archives"]
            },
            "database": {
                "auto_vacuum": True,
                "analyze_frequency": "weekly",
                "backup_before_maintenance": True
            },
            "performance": {
                "optimize_imports": True,
                "clean_temp_files": True,
                "update_statistics": True
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Erreur lors du chargement de la configuration: {e}")
                
        return default_config
        
    def setup_logging(self):
        """Configuration du système de logging"""
        log_dir = Path("maintenance")
        log_dir.mkdir(exist_ok=True)
        
        self.log_file = log_dir / f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _initialize_maintenance_tasks(self) -> List[MaintenanceTask]:
        """Initialise les tâches de maintenance disponibles"""
        tasks = []
        
        # Tâches de nettoyage
        tasks.extend([
            MaintenanceTask(
                name="clean_old_logs",
                task_type=MaintenanceTaskType.CLEANUP,
                description="Nettoyer les logs anciens",
                priority=3,
                estimated_duration=30
            ),
            MaintenanceTask(
                name="clean_old_reports",
                task_type=MaintenanceTaskType.CLEANUP,
                description="Nettoyer les rapports anciens",
                priority=3,
                estimated_duration=20
            ),
            MaintenanceTask(
                name="clean_cache_files",
                task_type=MaintenanceTaskType.CLEANUP,
                description="Nettoyer les fichiers cache",
                priority=4,
                estimated_duration=10
            ),
            MaintenanceTask(
                name="clean_temp_files",
                task_type=MaintenanceTaskType.CLEANUP,
                description="Nettoyer les fichiers temporaires",
                priority=3,
                estimated_duration=15
            )
        ])
        
        # Tâches d'optimisation
        tasks.extend([
            MaintenanceTask(
                name="optimize_database",
                task_type=MaintenanceTaskType.OPTIMIZATION,
                description="Optimiser la base de données",
                priority=2,
                estimated_duration=60
            ),
            MaintenanceTask(
                name="update_database_statistics",
                task_type=MaintenanceTaskType.OPTIMIZATION,
                description="Mettre à jour les statistiques de la base",
                priority=3,
                estimated_duration=30
            ),
            MaintenanceTask(
                name="compress_large_logs",
                task_type=MaintenanceTaskType.OPTIMIZATION,
                description="Compresser les gros fichiers de logs",
                priority=3,
                estimated_duration=45
            )
        ])
        
        # Tâches d'archivage
        tasks.extend([
            MaintenanceTask(
                name="archive_old_data",
                task_type=MaintenanceTaskType.ARCHIVE,
                description="Archiver les anciennes données",
                priority=4,
                estimated_duration=120
            ),
            MaintenanceTask(
                name="backup_configuration",
                task_type=MaintenanceTaskType.ARCHIVE,
                description="Sauvegarder la configuration",
                priority=2,
                estimated_duration=10
            )
        ])
        
        # Tâches de réparation
        tasks.extend([
            MaintenanceTask(
                name="fix_critical_import_errors",
                task_type=MaintenanceTaskType.REPAIR,
                description="Corriger les erreurs critiques d'import (ex: mapping_confidence)",
                priority=1,
                estimated_duration=30
            ),
            MaintenanceTask(
                name="check_file_integrity",
                task_type=MaintenanceTaskType.REPAIR,
                description="Vérifier l'intégrité des fichiers",
                priority=2,
                estimated_duration=90,
                auto_executable=False  # Nécessite confirmation
            ),
            MaintenanceTask(
                name="repair_database_issues",
                task_type=MaintenanceTaskType.REPAIR,
                description="Réparer les problèmes de base de données",
                priority=1,
                estimated_duration=300,
                auto_executable=False
            )
        ])
        
        return tasks
        
    def run_maintenance(self, task_names: Optional[List[str]] = None, 
                       auto_only: bool = False, max_duration: Optional[int] = None) -> Dict:
        """Exécute les tâches de maintenance"""
        self.maintenance_stats["start_time"] = datetime.now()
        self.logger.info("🔧 Démarrage de la maintenance automatique")
        
        # Sélectionner les tâches à exécuter
        if task_names:
            tasks_to_run = [task for task in self.available_tasks if task.name in task_names]
        else:
            tasks_to_run = self.available_tasks.copy()
            
        if auto_only:
            tasks_to_run = [task for task in tasks_to_run if task.auto_executable]
            
        # Trier par priorité (1=plus important)
        tasks_to_run.sort(key=lambda t: t.priority)
        
        # Filtrer par durée maximale si spécifiée
        if max_duration:
            filtered_tasks = []
            total_duration = 0
            for task in tasks_to_run:
                if total_duration + task.estimated_duration <= max_duration:
                    filtered_tasks.append(task)
                    total_duration += task.estimated_duration
                else:
                    break
            tasks_to_run = filtered_tasks
            
        # Exécuter les tâches
        results = {}
        for task in tasks_to_run:
            try:
                self.logger.info(f"🔄 Exécution: {task.description}")
                result = self._execute_task(task)
                results[task.name] = result
                self.maintenance_stats["tasks_executed"] += 1
                
                if result.get("success", False):
                    self.logger.info(f"✅ {task.description} - Terminé")
                else:
                    self.logger.warning(f"⚠️ {task.description} - Échec partiel")
                    
            except Exception as e:
                self.logger.error(f"❌ Erreur lors de {task.description}: {e}")
                results[task.name] = {"success": False, "error": str(e)}
                
        self.maintenance_stats["end_time"] = datetime.now()
        
        # Générer le rapport final
        report = self._generate_maintenance_report(results)
        self._save_maintenance_report(report)
        
        return report
        
    def _execute_task(self, task: MaintenanceTask) -> Dict:
        """Exécute une tâche de maintenance spécifique"""
        method_name = f"_task_{task.name}"
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            return method()
        else:
            return {"success": False, "error": f"Méthode {method_name} non trouvée"}
            
    def _task_clean_old_logs(self) -> Dict:
        """Nettoie les logs anciens"""
        result = {"success": True, "files_removed": 0, "space_freed": 0}
        
        cutoff_date = datetime.now() - timedelta(days=self.config["log_retention_days"])
        
        for log_dir_name in self.config["directories"]["logs"]:
            log_dir = Path(log_dir_name)
            if not log_dir.exists():
                continue
                
            for log_file in log_dir.glob("*.log"):
                try:
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        result["files_removed"] += 1
                        result["space_freed"] += file_size
                        self.maintenance_stats["files_cleaned"] += 1
                        self.maintenance_stats["space_freed"] += file_size
                except Exception as e:
                    self.logger.warning(f"Impossible de supprimer {log_file}: {e}")
                    
        return result
        
    def _task_clean_old_reports(self) -> Dict:
        """Nettoie les rapports anciens"""
        result = {"success": True, "files_removed": 0, "space_freed": 0}
        
        cutoff_date = datetime.now() - timedelta(days=self.config["report_retention_days"])
        
        for report_dir_name in self.config["directories"]["reports"]:
            report_dir = Path(report_dir_name)
            if not report_dir.exists():
                continue
                
            for report_file in report_dir.glob("*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        file_size = report_file.stat().st_size
                        report_file.unlink()
                        result["files_removed"] += 1
                        result["space_freed"] += file_size
                        self.maintenance_stats["files_cleaned"] += 1
                        self.maintenance_stats["space_freed"] += file_size
                except Exception as e:
                    self.logger.warning(f"Impossible de supprimer {report_file}: {e}")
                    
        return result
        
    def _task_clean_cache_files(self) -> Dict:
        """Nettoie les fichiers cache"""
        result = {"success": True, "files_removed": 0, "space_freed": 0}
        
        for cache_dir_name in self.config["directories"]["cache"]:
            cache_dir = Path(cache_dir_name)
            if not cache_dir.exists():
                continue
                
            for cache_file in cache_dir.rglob("*"):
                if cache_file.is_file():
                    try:
                        file_size = cache_file.stat().st_size
                        cache_file.unlink()
                        result["files_removed"] += 1
                        result["space_freed"] += file_size
                        self.maintenance_stats["files_cleaned"] += 1
                        self.maintenance_stats["space_freed"] += file_size
                    except Exception as e:
                        self.logger.warning(f"Impossible de supprimer {cache_file}: {e}")
                        
        return result
        
    def _task_clean_temp_files(self) -> Dict:
        """Nettoie les fichiers temporaires"""
        result = {"success": True, "files_removed": 0, "space_freed": 0}
        
        # Nettoyer les fichiers temporaires dans le répertoire courant
        for pattern in ["*.tmp", "*.temp", "~*", ".~*"]:
            for temp_file in Path(".").glob(pattern):
                if temp_file.is_file():
                    try:
                        file_size = temp_file.stat().st_size
                        temp_file.unlink()
                        result["files_removed"] += 1
                        result["space_freed"] += file_size
                        self.maintenance_stats["files_cleaned"] += 1
                        self.maintenance_stats["space_freed"] += file_size
                    except Exception as e:
                        self.logger.warning(f"Impossible de supprimer {temp_file}: {e}")
                        
        return result
        
    def _task_compress_large_logs(self) -> Dict:
        """Compresse les gros fichiers de logs"""
        result = {"success": True, "files_compressed": 0, "space_saved": 0}
        
        max_size = self.config["max_log_size_mb"] * 1024 * 1024  # Convertir en bytes
        
        for log_dir_name in self.config["directories"]["logs"]:
            log_dir = Path(log_dir_name)
            if not log_dir.exists():
                continue
                
            for log_file in log_dir.glob("*.log"):
                try:
                    if log_file.stat().st_size > max_size:
                        # Créer une archive zip
                        zip_path = log_file.with_suffix('.log.zip')
                        
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            zipf.write(log_file, log_file.name)
                            
                        # Vérifier que la compression a fonctionné
                        if zip_path.exists():
                            original_size = log_file.stat().st_size
                            compressed_size = zip_path.stat().st_size
                            space_saved = original_size - compressed_size
                            
                            log_file.unlink()  # Supprimer l'original
                            
                            result["files_compressed"] += 1
                            result["space_saved"] += space_saved
                            self.maintenance_stats["space_freed"] += space_saved
                            
                except Exception as e:
                    self.logger.warning(f"Impossible de compresser {log_file}: {e}")
                    
        return result
        
    def _task_optimize_database(self) -> Dict:
        """Optimise la base de données"""
        result = {"success": True, "operations": []}
        
        # Chercher les bases de données SQLite
        for db_file in Path(".").glob("*.db"):
            try:
                self.logger.info(f"Optimisation de la base {db_file}")
                
                with sqlite3.connect(db_file) as conn:
                    # VACUUM pour défragmenter
                    if self.config["database"]["auto_vacuum"]:
                        conn.execute("VACUUM")
                        result["operations"].append(f"VACUUM sur {db_file}")
                        
                    # ANALYZE pour mettre à jour les statistiques
                    conn.execute("ANALYZE")
                    result["operations"].append(f"ANALYSE sur {db_file}")
                    
                    conn.commit()
                    
            except Exception as e:
                self.logger.warning(f"Erreur lors de l'optimisation de {db_file}: {e}")
                result["success"] = False
                
        return result
        
    def _task_update_database_statistics(self) -> Dict:
        """Met à jour les statistiques de la base de données"""
        result = {"success": True, "databases_updated": 0}
        
        for db_file in Path(".").glob("*.db"):
            try:
                with sqlite3.connect(db_file) as conn:
                    conn.execute("ANALYZE")
                    conn.commit()
                    result["databases_updated"] += 1
                    
            except Exception as e:
                self.logger.warning(f"Erreur lors de la mise à jour des statistiques de {db_file}: {e}")
                
        return result
        
    def _task_archive_old_data(self) -> Dict:
        """Archive les anciennes données"""
        result = {"success": True, "archives_created": 0}
        
        archive_dir = Path(self.config["directories"]["archives"][0])
        archive_dir.mkdir(exist_ok=True)
        
        cutoff_date = datetime.now() - timedelta(days=self.config["archive_threshold_days"])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Archiver les logs anciens
        logs_to_archive = []
        for log_dir_name in self.config["directories"]["logs"]:
            log_dir = Path(log_dir_name)
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        logs_to_archive.append(log_file)
                        
        if logs_to_archive:
            archive_path = archive_dir / f"logs_archive_{timestamp}.zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for log_file in logs_to_archive:
                    zipf.write(log_file, f"logs/{log_file.name}")
                    log_file.unlink()  # Supprimer après archivage
                    
            result["archives_created"] += 1
            
        return result
        
    def _task_backup_configuration(self) -> Dict:
        """Sauvegarde la configuration"""
        result = {"success": True, "files_backed_up": 0}
        
        backup_dir = Path("backups/config")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Fichiers de configuration à sauvegarder
        config_files = [
            "sharepoint_config.json",
            ".env",
            "workflow_config.json",
            "requirements.txt"
        ]
        
        backup_zip = backup_dir / f"config_backup_{timestamp}.zip"
        
        with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    zipf.write(config_path, config_file)
                    result["files_backed_up"] += 1
                    
        return result
        
    def _task_fix_critical_import_errors(self) -> Dict:
        """Corrige les erreurs critiques d'import comme mapping_confidence manquant"""
        result = {"success": True, "fixes_applied": [], "errors_checked": 0}
        
        try:
            # Lire le fichier d'erreurs d'import
            error_file = Path("import_errors.csv")
            if not error_file.exists():
                result["message"] = "Aucun fichier d'erreurs trouvé"
                return result
            
            # Analyser les erreurs critiques
            critical_errors = []
            with open(error_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'mapping_confidence' in line and 'CRITICAL_ERROR' in line:
                        critical_errors.append(line.strip())
            
            result["errors_checked"] = len(critical_errors)
            
            if critical_errors:
                # Vérifier que la correction a été appliquée
                try:
                    scripts_dir = Path("scripts")
                    import_script = scripts_dir / "import_complete.py"
                    
                    if import_script.exists():
                        with open(import_script, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Vérifier que la correction est présente
                        if "self.mapping_confidence = 'unknown'" in content:
                            result["fixes_applied"].append("Correction mapping_confidence confirmée dans import_complete.py")
                        else:
                            result["fixes_applied"].append("⚠️ Correction mapping_confidence manquante dans import_complete.py")
                            result["success"] = False
                            
                        # Vérifier l'initialisation SharePoint
                        if "self.mapping_confidence = 'sharepoint'" in content:
                            result["fixes_applied"].append("Correction SharePoint mapping_confidence confirmée")
                        else:
                            result["fixes_applied"].append("⚠️ Correction SharePoint mapping_confidence manquante")
                            result["success"] = False
                            
                    else:
                        result["fixes_applied"].append("❌ Fichier import_complete.py non trouvé")
                        result["success"] = False
                        
                except Exception as e:
                    result["fixes_applied"].append(f"❌ Erreur lors de la vérification: {e}")
                    result["success"] = False
                    
                # Recommander un test
                result["fixes_applied"].append("💡 Recommandation: Exécuter test_mapping_confidence_fix.py pour valider")
                
            else:
                result["message"] = "Aucune erreur mapping_confidence détectée"
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la correction des erreurs critiques: {e}")
            result["success"] = False
            result["error"] = str(e)
            
        return result

    def _task_check_file_integrity(self) -> Dict:
        """Vérifie l'intégrité des fichiers"""
        result = {"success": True, "files_checked": 0, "corrupted_files": []}
        
        # Vérifier les fichiers critiques
        critical_files = [
            "orchestrate_dpgf_workflow_optimized.py",
            "scripts/import_complete.py",
            "scripts/identify_relevant_files_sharepoint.py"
        ]
        
        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                try:
                    # Vérifier que le fichier peut être lu
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Vérifications basiques de syntaxe pour les fichiers Python
                    if path.suffix == '.py':
                        try:
                            compile(content, str(path), 'exec')
                        except SyntaxError as e:
                            result["corrupted_files"].append({
                                "file": str(path),
                                "error": f"Erreur de syntaxe: {e}"
                            })
                            
                    result["files_checked"] += 1
                    
                except Exception as e:
                    result["corrupted_files"].append({
                        "file": str(path),
                        "error": str(e)
                    })
                    
        if result["corrupted_files"]:
            result["success"] = False
            
        return result
        
    def _task_repair_database_issues(self) -> Dict:
        """Répare les problèmes de base de données"""
        result = {"success": True, "repairs": []}
        
        for db_file in Path(".").glob("*.db"):
            try:
                self.logger.info(f"Vérification de {db_file}")
                
                with sqlite3.connect(db_file) as conn:
                    # Vérifier l'intégrité
                    cursor = conn.execute("PRAGMA integrity_check")
                    integrity_result = cursor.fetchone()[0]
                    
                    if integrity_result != "ok":
                        # Tenter une réparation
                        self.logger.warning(f"Problème d'intégrité détecté dans {db_file}")
                        
                        # Créer une sauvegarde avant réparation
                        backup_path = db_file.with_suffix('.backup.db')
                        shutil.copy2(db_file, backup_path)
                        
                        # Essayer de réparer avec VACUUM
                        try:
                            conn.execute("VACUUM")
                            conn.commit()
                            result["repairs"].append(f"VACUUM appliqué sur {db_file}")
                        except Exception as e:
                            result["repairs"].append(f"Échec de réparation de {db_file}: {e}")
                            result["success"] = False
                            
            except Exception as e:
                self.logger.error(f"Erreur lors de la vérification de {db_file}: {e}")
                result["success"] = False
                
        return result
        
    def _generate_maintenance_report(self, task_results: Dict) -> Dict:
        """Génère le rapport de maintenance"""
        duration = None
        if self.maintenance_stats["start_time"] and self.maintenance_stats["end_time"]:
            duration = (self.maintenance_stats["end_time"] - self.maintenance_stats["start_time"]).total_seconds()
            
        report = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "statistics": self.maintenance_stats.copy(),
            "task_results": task_results,
            "summary": {
                "tasks_executed": self.maintenance_stats["tasks_executed"],
                "total_files_cleaned": self.maintenance_stats["files_cleaned"],
                "total_space_freed_mb": round(self.maintenance_stats["space_freed"] / (1024 * 1024), 2),
                "success_rate": self._calculate_success_rate(task_results)
            },
            "recommendations": self._generate_maintenance_recommendations(task_results)
        }
        
        return report
        
    def _calculate_success_rate(self, task_results: Dict) -> float:
        """Calcule le taux de succès des tâches"""
        if not task_results:
            return 0.0
            
        successful_tasks = sum(1 for result in task_results.values() 
                              if result.get("success", False))
        return successful_tasks / len(task_results)
        
    def _generate_maintenance_recommendations(self, task_results: Dict) -> List[Dict]:
        """Génère des recommandations basées sur les résultats"""
        recommendations = []
        
        # Analyser les résultats pour générer des recommandations
        for task_name, result in task_results.items():
            if not result.get("success", True):
                recommendations.append({
                    "type": "task_failure",
                    "priority": "medium",
                    "title": f"Échec de la tâche {task_name}",
                    "description": f"La tâche {task_name} a échoué",
                    "action": f"Vérifier et corriger les problèmes avec {task_name}"
                })
                
        # Recommandations basées sur l'espace libéré
        space_freed_mb = self.maintenance_stats["space_freed"] / (1024 * 1024)
        if space_freed_mb > 100:
            recommendations.append({
                "type": "storage_optimization",
                "priority": "low",
                "title": "Optimisation de l'espace réussie",
                "description": f"{space_freed_mb:.1f} MB d'espace libéré",
                "action": "Continuer la maintenance régulière"
            })
        elif space_freed_mb < 10:
            recommendations.append({
                "type": "storage_check",
                "priority": "medium",
                "title": "Peu d'espace libéré",
                "description": f"Seulement {space_freed_mb:.1f} MB libéré",
                "action": "Vérifier s'il y a d'autres fichiers à nettoyer"
            })
            
        return recommendations
        
    def _save_maintenance_report(self, report: Dict):
        """Sauvegarde le rapport de maintenance"""
        maintenance_dir = Path("maintenance/reports")
        maintenance_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = maintenance_dir / f"maintenance_report_{timestamp}.json"
        
        # Convertir les objets datetime en strings pour la sérialisation JSON
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj
        
        serializable_report = convert_datetime(report)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_report, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"📊 Rapport de maintenance sauvegardé: {report_file}")
        
    def get_maintenance_schedule(self) -> Dict:
        """Retourne le planning de maintenance recommandé"""
        return {
            "daily": [
                "clean_temp_files",
                "clean_cache_files"
            ],
            "weekly": [
                "clean_old_logs",
                "update_database_statistics",
                "backup_configuration"
            ],
            "monthly": [
                "clean_old_reports",
                "compress_large_logs",
                "optimize_database",
                "archive_old_data"
            ],
            "on_demand": [
                "check_file_integrity",
                "repair_database_issues"
            ]
        }


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Système de maintenance automatique pour l'orchestrateur DPGF"
    )
    
    parser.add_argument('--config', type=str,
                       help='Fichier de configuration JSON')
    parser.add_argument('--tasks', nargs='+',
                       help='Tâches spécifiques à exécuter')
    parser.add_argument('--auto-only', action='store_true',
                       help='Exécuter seulement les tâches automatiques')
    parser.add_argument('--max-duration', type=int,
                       help='Durée maximale en secondes')
    parser.add_argument('--list-tasks', action='store_true',
                       help='Lister les tâches disponibles')
    parser.add_argument('--schedule', action='store_true',
                       help='Afficher le planning de maintenance')
    
    args = parser.parse_args()
    
    maintenance = AutomaticMaintenance(args.config)
    
    if args.list_tasks:
        print("🔧 TÂCHES DE MAINTENANCE DISPONIBLES:")
        print("=" * 50)
        for task in maintenance.available_tasks:
            auto_flag = "✅" if task.auto_executable else "⚠️"
            print(f"{auto_flag} {task.name}")
            print(f"   Type: {task.task_type.value}")
            print(f"   Description: {task.description}")
            print(f"   Priorité: {task.priority}")
            print(f"   Durée estimée: {task.estimated_duration}s")
            print()
        return 0
        
    if args.schedule:
        schedule = maintenance.get_maintenance_schedule()
        print("📅 PLANNING DE MAINTENANCE RECOMMANDÉ:")
        print("=" * 50)
        for frequency, task_names in schedule.items():
            print(f"\n{frequency.upper()}:")
            for task_name in task_names:
                print(f"  • {task_name}")
        return 0
        
    # Exécuter la maintenance
    print("🔧 Démarrage de la maintenance automatique...")
    
    report = maintenance.run_maintenance(
        task_names=args.tasks,
        auto_only=args.auto_only,
        max_duration=args.max_duration
    )
    
    # Afficher le résumé
    summary = report["summary"]
    print(f"\n{'='*50}")
    print(f"📊 RÉSUMÉ DE LA MAINTENANCE")
    print(f"{'='*50}")
    print(f"Tâches exécutées: {summary['tasks_executed']}")
    print(f"Fichiers nettoyés: {summary['total_files_cleaned']}")
    print(f"Espace libéré: {summary['total_space_freed_mb']} MB")
    print(f"Taux de succès: {summary['success_rate']:.1%}")
    
    if report["recommendations"]:
        print(f"\n💡 RECOMMANDATIONS:")
        for rec in report["recommendations"]:
            print(f"  • {rec['title']}: {rec['action']}")
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
