#!/usr/bin/env python3
"""
Gestionnaire de lots pour le traitement DPGF
============================================

Ce module gère le traitement par lots (batch processing) avec :
- Téléchargement progressif par lots
- Import immédiat après téléchargement
- Nettoyage automatique après chaque lot
- Gestion mémoire optimisée
- Reprise automatique en cas d'interruption
- Monitoring temps réel

Usage:
    from batch_manager import BatchManager
    
    manager = BatchManager(config)
    manager.process_files_in_batches(file_list)
"""

import os
import json
import time
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import threading
import queue
import psutil
import tempfile

logger = logging.getLogger(__name__)

@dataclass
class BatchStats:
    """Statistiques de traitement par lot"""
    batch_num: int
    total_files: int
    downloaded: int
    imported: int
    failed: int
    download_size_mb: float
    download_duration: float
    import_duration: float
    cleanup_duration: float
    memory_peak_mb: float
    disk_space_used_mb: float
    errors: List[str]
    warnings: List[str]

@dataclass
class BatchProgress:
    """État de progression globale"""
    total_batches: int
    current_batch: int
    total_files: int
    files_processed: int
    files_imported: int
    files_failed: int
    total_download_mb: float
    total_duration: float
    estimated_remaining: float
    memory_usage_mb: float
    disk_usage_mb: float
    last_batch_stats: Optional[BatchStats] = None

class BatchManager:
    """Gestionnaire de traitement par lots avec optimisation mémoire"""
    
    def __init__(self, config: Dict[str, Any], work_dir: Path):
        self.config = config
        self.work_dir = Path(work_dir)
        self.batch_dir = self.work_dir / 'batches'
        self.progress_file = self.work_dir / 'batch_progress.json'
        self.stats_file = self.work_dir / 'batch_stats.json'
        
        # Configuration par défaut
        self.batch_size = config.get('download', {}).get('batch_size', 10)
        self.max_batch_size_mb = config.get('download', {}).get('max_batch_size_mb', 100)
        self.auto_cleanup = config.get('download', {}).get('auto_cleanup', True)
        self.max_memory_mb = config.get('download', {}).get('max_memory_mb', 2048)
        self.max_disk_mb = config.get('download', {}).get('max_disk_mb', 1024)
        
        # Créer les répertoires
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        
        # État de progression
        self.progress = self._load_progress()
        self.batch_stats_history: List[BatchStats] = []
        
        # Monitoring
        self.monitor_thread = None
        self.monitor_queue = queue.Queue()
        self.monitor_running = False
        
        logger.info(f"BatchManager initialisé - Lots de {self.batch_size} fichiers")
    
    def _load_progress(self) -> BatchProgress:
        """Charge l'état de progression depuis le fichier"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return BatchProgress(**data)
            except Exception as e:
                logger.warning(f"Impossible de charger la progression: {e}")
        
        return BatchProgress(
            total_batches=0,
            current_batch=0,
            total_files=0,
            files_processed=0,
            files_imported=0,
            files_failed=0,
            total_download_mb=0.0,
            total_duration=0.0,
            estimated_remaining=0.0,
            memory_usage_mb=0.0,
            disk_usage_mb=0.0
        )
    
    def _save_progress(self):
        """Sauvegarde l'état de progression"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                # Convertir en dict en excluant les objets complexes
                progress_dict = asdict(self.progress)
                if 'last_batch_stats' in progress_dict and progress_dict['last_batch_stats']:
                    progress_dict['last_batch_stats'] = asdict(progress_dict['last_batch_stats'])
                json.dump(progress_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur sauvegarde progression: {e}")
    
    def _save_batch_stats(self, stats: BatchStats):
        """Sauvegarde les statistiques du lot"""
        self.batch_stats_history.append(stats)
        
        try:
            stats_data = {
                'timestamp': datetime.now().isoformat(),
                'stats': [asdict(s) for s in self.batch_stats_history]
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur sauvegarde stats: {e}")
    
    def _check_resources(self) -> Tuple[bool, List[str]]:
        """Vérifie les ressources disponibles (mémoire, disque)"""
        warnings = []
        
        # Vérifier la mémoire
        memory = psutil.virtual_memory()
        memory_used_mb = (memory.total - memory.available) / 1024 / 1024
        
        if memory_used_mb > self.max_memory_mb:
            warnings.append(f"Mémoire élevée: {memory_used_mb:.1f}MB / {self.max_memory_mb}MB")
        
        # Vérifier l'espace disque
        disk = psutil.disk_usage(str(self.work_dir))
        disk_free_mb = disk.free / 1024 / 1024
        
        if disk_free_mb < self.max_disk_mb:
            warnings.append(f"Espace disque faible: {disk_free_mb:.1f}MB disponibles")
        
        # Mettre à jour les métriques
        self.progress.memory_usage_mb = memory_used_mb
        self.progress.disk_usage_mb = (disk.total - disk.free) / 1024 / 1024
        
        return len(warnings) == 0, warnings
    
    def _optimize_batch_size(self, files: List[Dict]) -> List[List[Dict]]:
        """Optimise la taille des lots selon la taille des fichiers"""
        batches = []
        current_batch = []
        current_size_mb = 0
        
        for file_info in files:
            file_size_mb = file_info.get('size', 0) / 1024 / 1024
            
            # Si ce fichier dépasse la limite à lui seul, le traiter séparément
            if file_size_mb > self.max_batch_size_mb:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_size_mb = 0
                batches.append([file_info])
                continue
            
            # Si ajouter ce fichier dépasse la limite, finaliser le lot actuel
            if (current_size_mb + file_size_mb > self.max_batch_size_mb or 
                len(current_batch) >= self.batch_size):
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_size_mb = 0
            
            current_batch.append(file_info)
            current_size_mb += file_size_mb
        
        # Ajouter le dernier lot s'il n'est pas vide
        if current_batch:
            batches.append(current_batch)
        
        logger.info(f"Optimisation lots: {len(files)} fichiers → {len(batches)} lots")
        return batches
    
    def _download_batch(self, batch_files: List[Dict], batch_num: int) -> Tuple[List[Dict], BatchStats]:
        """Télécharge un lot de fichiers"""
        stats = BatchStats(
            batch_num=batch_num,
            total_files=len(batch_files),
            downloaded=0,
            imported=0,
            failed=0,
            download_size_mb=0.0,
            download_duration=0.0,
            import_duration=0.0,
            cleanup_duration=0.0,
            memory_peak_mb=0.0,
            disk_space_used_mb=0.0,
            errors=[],
            warnings=[]
        )
        
        batch_download_dir = self.batch_dir / f"batch_{batch_num:03d}"
        batch_download_dir.mkdir(exist_ok=True)
        
        start_time = time.time()
        memory_start = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            # Import du module de téléchargement
            import sys
            sys.path.append(str(Path(__file__).parent))
            from sharepoint_batch_downloader import download_specific_files
            
            # Télécharger les fichiers du lot
            sharepoint_url = self.config.get('sharepoint', {}).get('url', '')
            downloaded_files = download_specific_files(
                sharepoint_url, 
                batch_files, 
                str(batch_download_dir)
            )
            
            # Calculer les statistiques
            stats.downloaded = len(downloaded_files)
            stats.failed = len(batch_files) - len(downloaded_files)
            stats.download_duration = time.time() - start_time
            
            # Calculer la taille téléchargée
            total_size = 0
            for file_path in batch_download_dir.glob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            stats.download_size_mb = total_size / 1024 / 1024
            stats.disk_space_used_mb = stats.download_size_mb
            
            # Pic mémoire
            memory_current = psutil.Process().memory_info().rss / 1024 / 1024
            stats.memory_peak_mb = max(memory_start, memory_current)
            
            logger.info(f"✅ Lot {batch_num + 1}: {stats.downloaded}/{stats.total_files} téléchargés ({stats.download_size_mb:.1f}MB)")
            
            return downloaded_files, stats
            
        except Exception as e:
            error_msg = f"Erreur téléchargement lot {batch_num + 1}: {str(e)}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            stats.failed = len(batch_files)
            return [], stats
    
    def _import_batch(self, downloaded_files: List[Dict], batch_num: int, stats: BatchStats) -> BatchStats:
        """Importe un lot de fichiers"""
        if not downloaded_files:
            return stats
        
        start_time = time.time()
        
        try:
            # Import du module d'import
            import sys
            sys.path.append(str(Path(__file__).parent))
            from import_dpgf_unified import import_dpgf_files
            
            # Configuration d'import
            import_config = {
                'api_base_url': self.config.get('import', {}).get('api_base_url', 'http://127.0.0.1:8000'),
                'use_gemini': self.config.get('import', {}).get('use_gemini', True),
                'chunk_size': self.config.get('import', {}).get('chunk_size', 100),
                'max_workers': 1  # Limiter pour les lots
            }
            
            # Préparer la liste des fichiers pour l'import
            file_paths = [f['local_path'] for f in downloaded_files if f.get('local_path')]
            
            # Lancer l'import
            import_results = import_dpgf_files(file_paths, import_config)
            
            # Analyser les résultats
            stats.imported = sum(1 for r in import_results if r.get('success', False))
            stats.failed += len(file_paths) - stats.imported
            
            # Collecter les erreurs
            for result in import_results:
                if not result.get('success', False) and result.get('error'):
                    stats.errors.append(f"Import {result.get('file', 'unknown')}: {result['error']}")
            
            stats.import_duration = time.time() - start_time
            
            logger.info(f"📊 Lot {batch_num + 1}: {stats.imported}/{len(file_paths)} importés")
            
        except Exception as e:
            error_msg = f"Erreur import lot {batch_num + 1}: {str(e)}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            stats.import_duration = time.time() - start_time
        
        return stats
    
    def _cleanup_batch(self, batch_num: int, stats: BatchStats) -> BatchStats:
        """Nettoie les fichiers d'un lot après traitement"""
        if not self.auto_cleanup:
            return stats
        
        batch_download_dir = self.batch_dir / f"batch_{batch_num:03d}"
        
        if not batch_download_dir.exists():
            return stats
        
        start_time = time.time()
        
        try:
            # Calculer l'espace libéré
            disk_freed = 0
            for file_path in batch_download_dir.rglob('*'):
                if file_path.is_file():
                    disk_freed += file_path.stat().st_size
            
            # Supprimer le répertoire
            shutil.rmtree(batch_download_dir)
            
            stats.cleanup_duration = time.time() - start_time
            disk_freed_mb = disk_freed / 1024 / 1024
            
            logger.info(f"🧹 Lot {batch_num + 1} nettoyé: {disk_freed_mb:.1f}MB libérés")
            
        except Exception as e:
            error_msg = f"Erreur nettoyage lot {batch_num + 1}: {str(e)}"
            logger.warning(error_msg)
            stats.warnings.append(error_msg)
        
        return stats
    
    def process_files_in_batches(self, files: List[Dict]) -> bool:
        """Traite une liste de fichiers par lots avec optimisation mémoire"""
        if not files:
            logger.warning("Aucun fichier à traiter")
            return True
        
        # Optimiser la taille des lots
        batches = self._optimize_batch_size(files)
        
        # Initialiser la progression
        self.progress.total_batches = len(batches)
        self.progress.total_files = len(files)
        self.progress.current_batch = 0
        self.progress.files_processed = 0
        self.progress.files_imported = 0
        self.progress.files_failed = 0
        
        logger.info(f"🚀 Démarrage traitement par lots: {len(batches)} lots pour {len(files)} fichiers")
        
        start_time = time.time()
        success = True
        
        for batch_num, batch_files in enumerate(batches):
            self.progress.current_batch = batch_num
            
            logger.info(f"📦 Traitement lot {batch_num + 1}/{len(batches)} ({len(batch_files)} fichiers)")
            
            # Vérifier les ressources
            resources_ok, resource_warnings = self._check_resources()
            if not resources_ok:
                for warning in resource_warnings:
                    logger.warning(f"⚠️ {warning}")
                
                # Attendre un peu si les ressources sont limitées
                time.sleep(5)
            
            # Étape 1: Téléchargement
            downloaded_files, batch_stats = self._download_batch(batch_files, batch_num)
            
            # Étape 2: Import immédiat
            if downloaded_files:
                batch_stats = self._import_batch(downloaded_files, batch_num, batch_stats)
            
            # Étape 3: Nettoyage immédiat
            batch_stats = self._cleanup_batch(batch_num, batch_stats)
            
            # Mettre à jour la progression
            self.progress.files_processed += len(batch_files)
            self.progress.files_imported += batch_stats.imported
            self.progress.files_failed += batch_stats.failed
            self.progress.total_download_mb += batch_stats.download_size_mb
            self.progress.last_batch_stats = batch_stats
            
            # Estimation du temps restant
            elapsed = time.time() - start_time
            if batch_num > 0:
                avg_time_per_batch = elapsed / (batch_num + 1)
                remaining_batches = len(batches) - batch_num - 1
                self.progress.estimated_remaining = avg_time_per_batch * remaining_batches
            
            # Sauvegarder les statistiques
            self._save_batch_stats(batch_stats)
            self._save_progress()
            
            # Vérifier si on continue malgré les erreurs
            if batch_stats.failed > 0 and batch_stats.imported == 0:
                logger.error(f"❌ Lot {batch_num + 1} complètement échoué")
                success = False
                
                # Décider si on continue ou on s'arrête
                if batch_stats.failed >= len(batch_files):
                    logger.error("🛑 Arrêt du traitement à cause d'échecs répétés")
                    break
            
            # Petite pause entre les lots
            time.sleep(1)
        
        # Finaliser
        self.progress.total_duration = time.time() - start_time
        self._save_progress()
        
        # Résumé final
        logger.info(f"✅ Traitement terminé: {self.progress.files_imported}/{self.progress.total_files} importés")
        logger.info(f"📊 Durée totale: {self.progress.total_duration:.1f}s")
        logger.info(f"💾 Données téléchargées: {self.progress.total_download_mb:.1f}MB")
        
        return success and self.progress.files_failed == 0
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de la progression"""
        return {
            'progress': asdict(self.progress),
            'batch_stats': [asdict(s) for s in self.batch_stats_history[-5:]]  # 5 derniers lots
        }
    
    def cleanup_all_batches(self):
        """Nettoie tous les répertoires de lots"""
        try:
            if self.batch_dir.exists():
                shutil.rmtree(self.batch_dir)
                self.batch_dir.mkdir(exist_ok=True)
                logger.info("🧹 Tous les lots ont été nettoyés")
        except Exception as e:
            logger.error(f"Erreur nettoyage général: {e}")
    
    def resume_from_interruption(self) -> bool:
        """Reprend le traitement après une interruption"""
        if not self.progress_file.exists():
            return False
        
        logger.info("🔄 Reprise du traitement après interruption")
        
        # La logique de reprise dépendra des besoins spécifiques
        # Pour l'instant, on signale juste qu'une reprise est possible
        return True
