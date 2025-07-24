#!/usr/bin/env python3
"""
Système de surveillance et d'amélioration continue de l'orchestrateur DPGF.

Ce script surveille les performances, détecte les patterns d'erreur récurrents,
et propose automatiquement des optimisations pour améliorer la fiabilité
et les performances de l'orchestrateur.

Fonctionnalités :
- Surveillance en temps réel des logs
- Détection automatique des problèmes récurrents
- Analyse des tendances de performance
- Suggestions d'optimisation automatiques
- Rapports de santé du système
- Alertes proactives

Auteur: Assistant IA
Date: 2024
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict, deque
import argparse
import subprocess
import re
from dataclasses import dataclass
from enum import Enum

# Configuration de l'encodage pour Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

class AlertLevel(Enum):
    """Niveaux d'alerte"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class PerformanceMetric:
    """Métrique de performance"""
    name: str
    value: float
    timestamp: datetime
    context: Dict[str, Any] = None

@dataclass
class Alert:
    """Alerte système"""
    level: AlertLevel
    title: str
    description: str
    timestamp: datetime
    context: Dict[str, Any] = None
    resolved: bool = False

class ContinuousMonitor:
    """Surveillant continu de l'orchestrateur DPGF"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.setup_logging()
        
        # Métriques de performance
        self.metrics_history = defaultdict(deque)
        self.alerts = deque(maxlen=1000)  # Garder les 1000 dernières alertes
        
        # État de surveillance
        self.monitoring = False
        self.last_analysis = None
        
        # Threads de surveillance
        self.monitor_thread = None
        self.analysis_thread = None
        
        # Patterns d'erreur connus
        self.error_patterns = self._initialize_error_patterns()
        
        # Cache des recommandations
        self.recommendations_cache = {}
        
    def _load_config(self, config_file: Optional[str]) -> Dict:
        """Charge la configuration"""
        default_config = {
            "monitor_interval": 30,  # secondes
            "analysis_interval": 300,  # secondes (5 minutes)
            "max_metrics_history": 1000,
            "log_directories": [
                "logs",
                "logs_orchestrator", 
                "logs_production",
                "reports",
                "reports_orchestrator"
            ],
            "performance_thresholds": {
                "max_processing_time": 300,  # secondes
                "min_success_rate": 0.8,     # 80%
                "max_error_rate": 0.1        # 10%
            },
            "alert_settings": {
                "email_alerts": False,
                "console_alerts": True,
                "log_alerts": True
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
        log_dir = Path("monitoring")
        log_dir.mkdir(exist_ok=True)
        
        self.log_file = log_dir / f"continuous_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _initialize_error_patterns(self) -> Dict:
        """Initialise les patterns d'erreur connus"""
        return {
            'sharepoint_connection': [
                r'sharepoint.*connection.*error',
                r'authentication.*failed',
                r'access.*denied.*sharepoint'
            ],
            'excel_processing': [
                r'excel.*error',
                r'xlrd.*error',
                r'openpyxl.*error',
                r'engine.*not.*supported'
            ],
            'timeout_issues': [
                r'timeout',
                r'connection.*timed.*out',
                r'request.*timeout'
            ],
            'memory_issues': [
                r'memory.*error',
                r'out.*of.*memory',
                r'memoryerror'
            ],
            'import_failures': [
                r'import.*failed',
                r'import.*error',
                r'database.*error'
            ]
        }
        
    def start_monitoring(self):
        """Démarre la surveillance continue"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.logger.info("🔍 Démarrage de la surveillance continue")
        
        # Thread de surveillance des logs
        self.monitor_thread = threading.Thread(target=self._monitor_logs, daemon=True)
        self.monitor_thread.start()
        
        # Thread d'analyse périodique
        self.analysis_thread = threading.Thread(target=self._periodic_analysis, daemon=True)
        self.analysis_thread.start()
        
    def stop_monitoring(self):
        """Arrête la surveillance"""
        self.monitoring = False
        self.logger.info("⏹️ Arrêt de la surveillance continue")
        
    def _monitor_logs(self):
        """Surveillance continue des logs"""
        self.logger.info("📊 Démarrage de la surveillance des logs")
        
        # Garder une trace des fichiers déjà analysés
        processed_files = set()
        
        while self.monitoring:
            try:
                current_files = set()
                
                # Scanner tous les répertoires de logs
                for log_dir_name in self.config["log_directories"]:
                    log_dir = Path(log_dir_name)
                    if log_dir.exists():
                        for log_file in log_dir.glob("*.log"):
                            current_files.add(log_file)
                            
                            # Analyser les nouveaux fichiers
                            if log_file not in processed_files:
                                self._analyze_log_file(log_file)
                                processed_files.add(log_file)
                                
                            # Analyser les fichiers modifiés récemment
                            elif self._is_recently_modified(log_file):
                                self._analyze_log_file_incremental(log_file)
                                
                # Nettoyer les fichiers supprimés
                processed_files &= current_files
                
                time.sleep(self.config["monitor_interval"])
                
            except Exception as e:
                self.logger.error(f"Erreur dans la surveillance des logs: {e}")
                time.sleep(30)  # Attendre plus longtemps en cas d'erreur
                
    def _is_recently_modified(self, file_path: Path) -> bool:
        """Vérifie si un fichier a été modifié récemment"""
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return datetime.now() - mtime < timedelta(seconds=self.config["monitor_interval"] * 2)
        except:
            return False
            
    def _analyze_log_file(self, log_file: Path):
        """Analyse complète d'un fichier de log"""
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            self._extract_metrics_from_content(content, log_file)
            self._detect_errors_in_content(content, log_file)
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {log_file}: {e}")
            
    def _analyze_log_file_incremental(self, log_file: Path):
        """Analyse incrémentale d'un fichier de log (nouvelles lignes seulement)"""
        # Implémentation simplifiée - pour une version complète, il faudrait 
        # garder une trace de la position de lecture
        self._analyze_log_file(log_file)
        
    def _extract_metrics_from_content(self, content: str, source_file: Path):
        """Extrait les métriques de performance du contenu"""
        timestamp = datetime.now()
        
        # Extraire les temps de traitement
        processing_time_pattern = r'traitement.*terminé.*en.*(\d+(?:\.\d+)?)\s*secondes?'
        for match in re.finditer(processing_time_pattern, content, re.IGNORECASE):
            processing_time = float(match.group(1))
            metric = PerformanceMetric(
                name="processing_time",
                value=processing_time,
                timestamp=timestamp,
                context={"source_file": str(source_file)}
            )
            self._add_metric(metric)
            
        # Extraire les taux de succès
        success_pattern = r'(\d+)\s*fichiers?\s*traités?\s*avec\s*succès'
        total_pattern = r'total\s*de\s*(\d+)\s*fichiers?'
        
        success_matches = re.findall(success_pattern, content, re.IGNORECASE)
        total_matches = re.findall(total_pattern, content, re.IGNORECASE)
        
        if success_matches and total_matches:
            success_count = int(success_matches[-1])  # Prendre le dernier
            total_count = int(total_matches[-1])
            
            if total_count > 0:
                success_rate = success_count / total_count
                metric = PerformanceMetric(
                    name="success_rate",
                    value=success_rate,
                    timestamp=timestamp,
                    context={
                        "source_file": str(source_file),
                        "success_count": success_count,
                        "total_count": total_count
                    }
                )
                self._add_metric(metric)
                
        # Compter les erreurs
        error_count = len(re.findall(r'\berror\b|\berreur\b', content, re.IGNORECASE))
        if error_count > 0:
            metric = PerformanceMetric(
                name="error_count",
                value=error_count,
                timestamp=timestamp,
                context={"source_file": str(source_file)}
            )
            self._add_metric(metric)
            
    def _detect_errors_in_content(self, content: str, source_file: Path):
        """Détecte les erreurs dans le contenu"""
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    self._create_alert(
                        level=AlertLevel.WARNING,
                        title=f"Erreur détectée: {error_type}",
                        description=f"{len(matches)} occurrence(s) trouvée(s) dans {source_file.name}",
                        context={
                            "error_type": error_type,
                            "source_file": str(source_file),
                            "matches": matches[:5]  # Limiter à 5 exemples
                        }
                    )
                    
    def _add_metric(self, metric: PerformanceMetric):
        """Ajoute une métrique à l'historique"""
        history = self.metrics_history[metric.name]
        history.append(metric)
        
        # Limiter la taille de l'historique
        while len(history) > self.config["max_metrics_history"]:
            history.popleft()
            
        # Vérifier les seuils
        self._check_metric_thresholds(metric)
        
    def _check_metric_thresholds(self, metric: PerformanceMetric):
        """Vérifie si une métrique dépasse les seuils"""
        thresholds = self.config["performance_thresholds"]
        
        if metric.name == "processing_time":
            if metric.value > thresholds["max_processing_time"]:
                self._create_alert(
                    level=AlertLevel.WARNING,
                    title="Temps de traitement élevé",
                    description=f"Traitement de {metric.value:.1f}s (seuil: {thresholds['max_processing_time']}s)",
                    context=metric.context
                )
                
        elif metric.name == "success_rate":
            if metric.value < thresholds["min_success_rate"]:
                self._create_alert(
                    level=AlertLevel.ERROR,
                    title="Taux de succès faible",
                    description=f"Taux de succès: {metric.value:.1%} (seuil: {thresholds['min_success_rate']:.1%})",
                    context=metric.context
                )
                
    def _create_alert(self, level: AlertLevel, title: str, description: str, context: Dict = None):
        """Crée une nouvelle alerte"""
        alert = Alert(
            level=level,
            title=title,
            description=description,
            timestamp=datetime.now(),
            context=context or {}
        )
        
        self.alerts.append(alert)
        
        # Envoyer l'alerte selon la configuration
        if self.config["alert_settings"]["console_alerts"]:
            self._send_console_alert(alert)
            
        if self.config["alert_settings"]["log_alerts"]:
            self._send_log_alert(alert)
            
    def _send_console_alert(self, alert: Alert):
        """Envoie une alerte sur la console"""
        level_icons = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        icon = level_icons.get(alert.level, "📢")
        print(f"\n{icon} ALERTE {alert.level.value.upper()}: {alert.title}")
        print(f"   {alert.description}")
        print(f"   Heure: {alert.timestamp.strftime('%H:%M:%S')}")
        
    def _send_log_alert(self, alert: Alert):
        """Enregistre une alerte dans les logs"""
        if alert.level == AlertLevel.CRITICAL:
            self.logger.critical(f"ALERTE: {alert.title} - {alert.description}")
        elif alert.level == AlertLevel.ERROR:
            self.logger.error(f"ALERTE: {alert.title} - {alert.description}")
        elif alert.level == AlertLevel.WARNING:
            self.logger.warning(f"ALERTE: {alert.title} - {alert.description}")
        else:
            self.logger.info(f"ALERTE: {alert.title} - {alert.description}")
            
    def _periodic_analysis(self):
        """Analyse périodique complète"""
        self.logger.info("📈 Démarrage de l'analyse périodique")
        
        while self.monitoring:
            try:
                self._perform_comprehensive_analysis()
                time.sleep(self.config["analysis_interval"])
            except Exception as e:
                self.logger.error(f"Erreur dans l'analyse périodique: {e}")
                time.sleep(60)
                
    def _perform_comprehensive_analysis(self):
        """Effectue une analyse complète du système"""
        self.logger.info("🔍 Analyse complète en cours...")
        
        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": self._summarize_metrics(),
            "recent_alerts": self._get_recent_alerts(),
            "recommendations": self._generate_recommendations(),
            "system_health": self._assess_system_health()
        }
        
        # Sauvegarder l'analyse
        self._save_analysis_result(analysis_result)
        
        # Générer des alertes si nécessaire
        self._check_system_health(analysis_result)
        
        self.last_analysis = analysis_result
        
    def _summarize_metrics(self) -> Dict:
        """Résume les métriques actuelles"""
        summary = {}
        
        for metric_name, history in self.metrics_history.items():
            if not history:
                continue
                
            values = [m.value for m in history]
            recent_values = [m.value for m in history if 
                           datetime.now() - m.timestamp < timedelta(hours=1)]
                           
            summary[metric_name] = {
                "total_count": len(values),
                "recent_count": len(recent_values),
                "average": sum(values) / len(values) if values else 0,
                "recent_average": sum(recent_values) / len(recent_values) if recent_values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "last_value": values[-1] if values else 0
            }
            
        return summary
        
    def _get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Récupère les alertes récentes"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_alerts = [
            {
                "level": alert.level.value,
                "title": alert.title,
                "description": alert.description,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved
            }
            for alert in self.alerts
            if alert.timestamp > cutoff
        ]
        
        return recent_alerts
        
    def _generate_recommendations(self) -> List[Dict]:
        """Génère des recommandations d'amélioration"""
        recommendations = []
        
        # Analyser les métriques de performance
        metrics_summary = self._summarize_metrics()
        
        # Recommandations basées sur le temps de traitement
        if "processing_time" in metrics_summary:
            avg_time = metrics_summary["processing_time"]["average"]
            if avg_time > self.config["performance_thresholds"]["max_processing_time"]:
                recommendations.append({
                    "type": "performance",
                    "priority": "medium",
                    "title": "Optimiser les temps de traitement",
                    "description": f"Temps moyen: {avg_time:.1f}s (seuil: {self.config['performance_thresholds']['max_processing_time']}s)",
                    "actions": [
                        "Augmenter la taille des lots de traitement",
                        "Optimiser les requêtes SharePoint",
                        "Utiliser le traitement parallèle"
                    ]
                })
                
        # Recommandations basées sur le taux de succès
        if "success_rate" in metrics_summary:
            avg_success = metrics_summary["success_rate"]["average"]
            if avg_success < self.config["performance_thresholds"]["min_success_rate"]:
                recommendations.append({
                    "type": "reliability",
                    "priority": "high",
                    "title": "Améliorer la fiabilité",
                    "description": f"Taux de succès moyen: {avg_success:.1%}",
                    "actions": [
                        "Améliorer la gestion des erreurs",
                        "Ajouter des mécanismes de retry",
                        "Renforcer la validation des données"
                    ]
                })
                
        # Recommandations basées sur les alertes récentes
        recent_alerts = self._get_recent_alerts(hours=24)
        error_types = {}
        for alert in recent_alerts:
            error_type = alert.get("context", {}).get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
        if error_types:
            most_common_error = max(error_types, key=error_types.get)
            recommendations.append({
                "type": "error_handling",
                "priority": "medium",
                "title": f"Traiter les erreurs {most_common_error}",
                "description": f"{error_types[most_common_error]} occurrences dans les dernières 24h",
                "actions": [
                    f"Analyser la cause racine des erreurs {most_common_error}",
                    "Améliorer la gestion de ce type d'erreur",
                    "Ajouter des logs plus détaillés"
                ]
            })
            
        return recommendations
        
    def _assess_system_health(self) -> Dict:
        """Évalue la santé globale du système"""
        health = {
            "score": 100,  # Score sur 100
            "status": "healthy",  # healthy, warning, critical
            "issues": []
        }
        
        metrics_summary = self._summarize_metrics()
        recent_alerts = self._get_recent_alerts(hours=1)
        
        # Pénaliser pour les erreurs récentes
        error_alerts = [a for a in recent_alerts if a["level"] in ["error", "critical"]]
        if error_alerts:
            health["score"] -= len(error_alerts) * 10
            health["issues"].append(f"{len(error_alerts)} erreurs dans la dernière heure")
            
        # Pénaliser pour les performances dégradées
        if "processing_time" in metrics_summary:
            avg_time = metrics_summary["processing_time"]["recent_average"]
            if avg_time > self.config["performance_thresholds"]["max_processing_time"]:
                health["score"] -= 20
                health["issues"].append(f"Temps de traitement élevé: {avg_time:.1f}s")
                
        # Pénaliser pour le taux de succès faible
        if "success_rate" in metrics_summary:
            recent_success = metrics_summary["success_rate"]["recent_average"]
            if recent_success < self.config["performance_thresholds"]["min_success_rate"]:
                health["score"] -= 30
                health["issues"].append(f"Taux de succès faible: {recent_success:.1%}")
                
        # Déterminer le statut
        if health["score"] >= 80:
            health["status"] = "healthy"
        elif health["score"] >= 60:
            health["status"] = "warning"
        else:
            health["status"] = "critical"
            
        return health
        
    def _check_system_health(self, analysis_result: Dict):
        """Vérifie la santé du système et génère des alertes si nécessaire"""
        health = analysis_result["system_health"]
        
        if health["status"] == "critical":
            self._create_alert(
                level=AlertLevel.CRITICAL,
                title="Santé du système critique",
                description=f"Score de santé: {health['score']}/100. Issues: {', '.join(health['issues'])}",
                context={"health_details": health}
            )
        elif health["status"] == "warning":
            self._create_alert(
                level=AlertLevel.WARNING,
                title="Santé du système dégradée",
                description=f"Score de santé: {health['score']}/100. Issues: {', '.join(health['issues'])}",
                context={"health_details": health}
            )
            
    def _save_analysis_result(self, analysis_result: Dict):
        """Sauvegarde le résultat de l'analyse"""
        analysis_dir = Path("monitoring/analysis")
        analysis_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = analysis_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"📊 Analyse sauvegardée: {file_path}")
        
    def get_current_status(self) -> Dict:
        """Retourne le statut actuel du système"""
        return {
            "monitoring_active": self.monitoring,
            "last_analysis": self.last_analysis["timestamp"] if self.last_analysis else None,
            "metrics_count": {name: len(history) for name, history in self.metrics_history.items()},
            "recent_alerts_count": len(self._get_recent_alerts(hours=1)),
            "system_health": self.last_analysis["system_health"] if self.last_analysis else None
        }
        
    def generate_report(self) -> str:
        """Génère un rapport de statut"""
        status = self.get_current_status()
        
        report = []
        report.append("🔍 RAPPORT DE SURVEILLANCE CONTINUE")
        report.append("=" * 50)
        
        if status["monitoring_active"]:
            report.append("✅ Surveillance active")
        else:
            report.append("❌ Surveillance inactive")
            
        if status["last_analysis"]:
            report.append(f"📊 Dernière analyse: {status['last_analysis']}")
        else:
            report.append("📊 Aucune analyse effectuée")
            
        report.append("\n📈 MÉTRIQUES:")
        for metric_name, count in status["metrics_count"].items():
            report.append(f"  • {metric_name}: {count} points de données")
            
        report.append(f"\n🚨 Alertes récentes (1h): {status['recent_alerts_count']}")
        
        if status["system_health"]:
            health = status["system_health"]
            report.append(f"\n💊 SANTÉ DU SYSTÈME:")
            report.append(f"  • Score: {health['score']}/100")
            report.append(f"  • Statut: {health['status']}")
            if health["issues"]:
                report.append("  • Issues:")
                for issue in health["issues"]:
                    report.append(f"    - {issue}")
                    
        return "\n".join(report)


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Système de surveillance continue de l'orchestrateur DPGF"
    )
    
    parser.add_argument('--config', type=str,
                       help='Fichier de configuration JSON')
    parser.add_argument('--daemon', action='store_true',
                       help='Lancer en mode daemon (surveillance continue)')
    parser.add_argument('--status', action='store_true',
                       help='Afficher le statut actuel')
    parser.add_argument('--report', action='store_true',
                       help='Générer un rapport de surveillance')
    
    args = parser.parse_args()
    
    monitor = ContinuousMonitor(args.config)
    
    if args.status:
        print(monitor.generate_report())
        return 0
        
    if args.report:
        print(monitor.generate_report())
        return 0
        
    if args.daemon:
        print("🔍 Démarrage de la surveillance continue...")
        print("Appuyez sur Ctrl+C pour arrêter")
        
        monitor.start_monitoring()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️ Arrêt de la surveillance...")
            monitor.stop_monitoring()
            
    else:
        # Analyse ponctuelle
        print("🔍 Analyse ponctuelle en cours...")
        monitor._perform_comprehensive_analysis()
        print("\n" + monitor.generate_report())
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
