#!/usr/bin/env python3
"""
Moniteur en temps réel pour le workflow DPGF
============================================

Ce script surveille la progression du traitement par lots en temps réel
et affiche des statistiques détaillées.

Usage:
    python monitor_batch_progress.py [--work-dir PATH] [--refresh-rate SECONDS]

Fonctionnalités:
    - Affichage temps réel de la progression
    - Statistiques détaillées par lot
    - Graphiques de performance
    - Alertes en cas de problème
    - Export des métriques
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import signal

# Pour l'affichage enrichi
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️ Package 'rich' non disponible - affichage basique")

class BatchMonitor:
    """Moniteur de progression des lots"""
    
    def __init__(self, work_dir: str = "dpgf_workflow", refresh_rate: float = 2.0):
        self.work_dir = Path(work_dir)
        self.refresh_rate = refresh_rate
        self.progress_file = self.work_dir / 'batch_progress.json'
        self.stats_file = self.work_dir / 'batch_stats.json'
        
        self.console = Console() if RICH_AVAILABLE else None
        self.running = False
        self.start_time = time.time()
        
        # Historique pour les graphiques
        self.progress_history = []
        self.last_progress = None
        
    def load_progress(self) -> Optional[Dict[str, Any]]:
        """Charge les données de progression actuelles"""
        if not self.progress_file.exists():
            return None
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Erreur lecture progression: {e}[/red]")
            return None
    
    def load_batch_stats(self) -> List[Dict[str, Any]]:
        """Charge l'historique des statistiques de lots"""
        if not self.stats_file.exists():
            return []
        
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('stats', [])
        except Exception:
            return []
    
    def format_duration(self, seconds: float) -> str:
        """Formate une durée en secondes"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}min"
        else:
            return f"{seconds/3600:.1f}h"
    
    def format_size(self, bytes_size: float) -> str:
        """Formate une taille en octets"""
        if bytes_size < 1024:
            return f"{bytes_size:.0f}B"
        elif bytes_size < 1024**2:
            return f"{bytes_size/1024:.1f}KB"
        elif bytes_size < 1024**3:
            return f"{bytes_size/1024**2:.1f}MB"
        else:
            return f"{bytes_size/1024**3:.1f}GB"
    
    def calculate_speed(self, progress: Dict[str, Any]) -> Dict[str, float]:
        """Calcule les vitesses de traitement"""
        if not self.last_progress:
            return {'files_per_sec': 0.0, 'mb_per_sec': 0.0}
        
        time_diff = time.time() - self.last_progress.get('timestamp', 0)
        if time_diff <= 0:
            return {'files_per_sec': 0.0, 'mb_per_sec': 0.0}
        
        files_diff = progress.get('files_processed', 0) - self.last_progress.get('files_processed', 0)
        mb_diff = progress.get('total_download_mb', 0) - self.last_progress.get('total_download_mb', 0)
        
        return {
            'files_per_sec': files_diff / time_diff,
            'mb_per_sec': mb_diff / time_diff
        }
    
    def create_progress_table(self, progress: Dict[str, Any], speeds: Dict[str, float]) -> Table:
        """Crée un tableau de progression"""
        table = Table(title="📊 Progression du Workflow DPGF", show_header=True)
        
        table.add_column("Métrique", style="cyan", no_wrap=True)
        table.add_column("Valeur", style="magenta")
        table.add_column("Détails", style="green")
        
        # Progression générale
        current_batch = progress.get('current_batch', 0)
        total_batches = progress.get('total_batches', 0)
        files_processed = progress.get('files_processed', 0)
        total_files = progress.get('total_files', 0)
        
        if total_batches > 0:
            batch_progress = (current_batch / total_batches) * 100
            table.add_row("Progression lots", f"{current_batch}/{total_batches}", f"{batch_progress:.1f}%")
        
        if total_files > 0:
            file_progress = (files_processed / total_files) * 100
            table.add_row("Progression fichiers", f"{files_processed}/{total_files}", f"{file_progress:.1f}%")
        
        # Import
        files_imported = progress.get('files_imported', 0)
        files_failed = progress.get('files_failed', 0)
        
        if files_processed > 0:
            success_rate = (files_imported / files_processed) * 100
            table.add_row("Taux de succès", f"{files_imported} réussis", f"{success_rate:.1f}%")
        
        if files_failed > 0:
            table.add_row("Échecs", f"{files_failed}", "⚠️")
        
        # Données
        total_mb = progress.get('total_download_mb', 0)
        table.add_row("Données traitées", self.format_size(total_mb * 1024 * 1024), "")
        
        # Temps
        total_duration = progress.get('total_duration', 0)
        estimated_remaining = progress.get('estimated_remaining', 0)
        
        table.add_row("Temps écoulé", self.format_duration(total_duration), "")
        if estimated_remaining > 0:
            table.add_row("Temps restant", self.format_duration(estimated_remaining), "🕐")
        
        # Vitesses
        if speeds['files_per_sec'] > 0:
            table.add_row("Vitesse", f"{speeds['files_per_sec']:.1f} fichiers/s", f"{speeds['mb_per_sec']:.1f} MB/s")
        
        # Ressources
        memory_mb = progress.get('memory_usage_mb', 0)
        disk_mb = progress.get('disk_usage_mb', 0)
        
        if memory_mb > 0:
            table.add_row("Mémoire", self.format_size(memory_mb * 1024 * 1024), "🧠")
        if disk_mb > 0:
            table.add_row("Disque", self.format_size(disk_mb * 1024 * 1024), "💾")
        
        return table
    
    def create_batch_stats_table(self, batch_stats: List[Dict[str, Any]]) -> Table:
        """Crée un tableau des statistiques par lot"""
        table = Table(title="📦 Statistiques des Derniers Lots", show_header=True)
        
        table.add_column("Lot", style="cyan", no_wrap=True)
        table.add_column("Fichiers", style="yellow")
        table.add_column("Import", style="green")
        table.add_column("Taille", style="blue")
        table.add_column("Durée", style="magenta")
        table.add_column("Statut", style="red")
        
        # Afficher les 10 derniers lots
        recent_stats = batch_stats[-10:] if len(batch_stats) > 10 else batch_stats
        
        for stat in recent_stats:
            batch_num = stat.get('batch_num', 0)
            total_files = stat.get('total_files', 0)
            downloaded = stat.get('downloaded', 0)
            imported = stat.get('imported', 0)
            failed = stat.get('failed', 0)
            size_mb = stat.get('download_size_mb', 0)
            duration = stat.get('download_duration', 0) + stat.get('import_duration', 0)
            
            # Statut
            if failed == 0:
                status = "✅"
            elif imported > 0:
                status = "⚠️"
            else:
                status = "❌"
            
            table.add_row(
                f"#{batch_num + 1}",
                f"{downloaded}/{total_files}",
                f"{imported}",
                f"{size_mb:.1f}MB",
                self.format_duration(duration),
                status
            )
        
        return table
    
    def display_simple(self, progress: Dict[str, Any], batch_stats: List[Dict[str, Any]]):
        """Affichage simple sans rich"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("="*60)
        print("📊 MONITEUR WORKFLOW DPGF")
        print("="*60)
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
        print()
        
        # Progression
        current_batch = progress.get('current_batch', 0)
        total_batches = progress.get('total_batches', 0)
        files_processed = progress.get('files_processed', 0)
        total_files = progress.get('total_files', 0)
        files_imported = progress.get('files_imported', 0)
        files_failed = progress.get('files_failed', 0)
        
        if total_batches > 0:
            batch_pct = (current_batch / total_batches) * 100
            print(f"📦 Lots: {current_batch}/{total_batches} ({batch_pct:.1f}%)")
        
        if total_files > 0:
            file_pct = (files_processed / total_files) * 100
            print(f"📄 Fichiers: {files_processed}/{total_files} ({file_pct:.1f}%)")
        
        print(f"✅ Importés: {files_imported}")
        if files_failed > 0:
            print(f"❌ Échecs: {files_failed}")
        
        total_mb = progress.get('total_download_mb', 0)
        print(f"💾 Données: {self.format_size(total_mb * 1024 * 1024)}")
        
        # Temps
        total_duration = progress.get('total_duration', 0)
        estimated_remaining = progress.get('estimated_remaining', 0)
        
        print(f"⏱️ Durée: {self.format_duration(total_duration)}")
        if estimated_remaining > 0:
            print(f"🕐 Restant: {self.format_duration(estimated_remaining)}")
        
        # Derniers lots
        if batch_stats:
            print("\n📦 DERNIERS LOTS:")
            print("-" * 40)
            recent_stats = batch_stats[-5:]
            for stat in recent_stats:
                batch_num = stat.get('batch_num', 0)
                imported = stat.get('imported', 0)
                failed = stat.get('failed', 0)
                status = "✅" if failed == 0 else ("⚠️" if imported > 0 else "❌")
                print(f"  Lot #{batch_num + 1}: {imported} importés {status}")
    
    def display_rich(self, progress: Dict[str, Any], batch_stats: List[Dict[str, Any]], speeds: Dict[str, float]):
        """Affichage enrichi avec rich"""
        layout = Layout()
        
        layout.split_column(
            Layout(self.create_progress_table(progress, speeds), name="progress"),
            Layout(self.create_batch_stats_table(batch_stats), name="stats")
        )
        
        return Panel(layout, title=f"🚀 Moniteur DPGF - {datetime.now().strftime('%H:%M:%S')}")
    
    def monitor_loop(self):
        """Boucle principale de monitoring"""
        if RICH_AVAILABLE:
            with Live(refresh_per_second=1/self.refresh_rate) as live:
                while self.running:
                    progress = self.load_progress()
                    batch_stats = self.load_batch_stats()
                    
                    if progress:
                        # Calculer les vitesses
                        speeds = self.calculate_speed(progress)
                        
                        # Mettre à jour l'historique
                        progress['timestamp'] = time.time()
                        self.progress_history.append(progress.copy())
                        self.last_progress = progress.copy()
                        
                        # Limiter l'historique
                        if len(self.progress_history) > 100:
                            self.progress_history.pop(0)
                        
                        # Afficher
                        live.update(self.display_rich(progress, batch_stats, speeds))
                    else:
                        live.update(Panel("⏳ En attente du démarrage du workflow..."))
                    
                    time.sleep(self.refresh_rate)
        else:
            while self.running:
                progress = self.load_progress()
                batch_stats = self.load_batch_stats()
                
                if progress:
                    self.display_simple(progress, batch_stats)
                else:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print("⏳ En attente du démarrage du workflow...")
                
                time.sleep(self.refresh_rate)
    
    def start(self):
        """Démarre le monitoring"""
        self.running = True
        
        # Gestionnaire d'arrêt propre
        def signal_handler(sig, frame):
            print("\n🛑 Arrêt du moniteur...")
            self.running = False
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        print(f"🚀 Démarrage du moniteur DPGF - Répertoire: {self.work_dir}")
        print("📊 Appuyez sur Ctrl+C pour arrêter")
        print()
        
        try:
            self.monitor_loop()
        except KeyboardInterrupt:
            self.running = False
            print("\n🛑 Moniteur arrêté")

def main():
    parser = argparse.ArgumentParser(description="Moniteur temps réel du workflow DPGF")
    parser.add_argument('--work-dir', default='dpgf_workflow', help='Répertoire de travail')
    parser.add_argument('--refresh-rate', type=float, default=2.0, help='Taux de rafraîchissement (secondes)')
    
    args = parser.parse_args()
    
    monitor = BatchMonitor(args.work_dir, args.refresh_rate)
    monitor.start()

if __name__ == "__main__":
    main()
