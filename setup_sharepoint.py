"""
Script de configuration pour l'orchestrateur SharePoint DPGF.
Configure l'environnement et démarre les services.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List
import json

class SharePointConfig:
    """Configuration de l'orchestrateur SharePoint"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_file = self.project_root / "sharepoint_config.json"
        
    def create_env_file(self):
        """Crée un fichier .env avec les variables nécessaires"""
        env_content = """# Configuration SharePoint DPGF Orchestrator

# SharePoint Configuration
SHAREPOINT_URL=https://votreentreprise.sharepoint.com/sites/votresite
SHAREPOINT_USERNAME=votre.email@entreprise.com
SHAREPOINT_PASSWORD=votre_mot_de_passe
SHAREPOINT_LIBRARY=Documents DPGF

# Database Configuration (si différente de settings.py)
DATABASE_URL=postgresql://username:password@localhost/dpgf_db

# Notification Configuration (optionnel)
NOTIFICATION_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
NOTIFICATION_EMAIL=admin@entreprise.com

# Monitoring Configuration
LOG_LEVEL=INFO
MAX_LOG_FILES=30
LOG_ROTATION_DAYS=7

# Import Configuration
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=.xlsx,.xls
DOWNLOAD_TIMEOUT_SECONDS=300
PROCESSING_TIMEOUT_SECONDS=600
"""
        
        env_path = self.project_root / ".env"
        
        if not env_path.exists():
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            print(f"✅ Fichier .env créé: {env_path}")
            print("⚠️ Modifiez les valeurs selon votre configuration")
        else:
            print(f"ℹ️ Fichier .env existe déjà: {env_path}")
    
    def install_dependencies(self):
        """Installe les dépendances supplémentaires"""
        additional_deps = [
            "Office365-REST-Python-Client==2.3.11",
            "schedule==1.2.0",
            "python-dotenv==1.0.0",
            "psutil==5.9.5"
        ]
        
        print("📦 Installation des dépendances SharePoint...")
        
        for dep in additional_deps:
            try:
                subprocess.run([
                    sys.executable, "-m", "pip", "install", dep
                ], check=True, capture_output=True)
                print(f"✅ {dep}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Erreur installation {dep}: {e}")
    
    def create_directories(self):
        """Crée les dossiers nécessaires"""
        directories = [
            "logs",
            "reports",
            "downloads",
            "temp",
            "backups"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            print(f"📁 Dossier créé: {directory}")
    
    def create_config_file(self):
        """Crée un fichier de configuration JSON"""
        config = {
            "orchestrator": {
                "name": "DPGF SharePoint Orchestrator",
                "version": "1.0.0",
                "description": "Orchestrateur automatique pour l'import de fichiers DPGF depuis SharePoint"
            },
            "sharepoint": {
                "library_name": "Documents DPGF",
                "file_filters": [".xlsx", ".xls"],
                "check_interval_minutes": 60,
                "max_file_size_mb": 50
            },
            "processing": {
                "timeout_seconds": 600,
                "retry_attempts": 3,
                "concurrent_files": 1
            },
            "monitoring": {
                "log_level": "INFO",
                "max_log_files": 30,
                "send_notifications": True,
                "notification_on_error": True,
                "daily_report": True,
                "daily_report_time": "08:00"
            },
            "database": {
                "connection_pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Configuration créée: {self.config_file}")
    
    def create_startup_scripts(self):
        """Crée les scripts de démarrage"""
        
        # Script Windows
        windows_script = """@echo off
echo Starting DPGF SharePoint Orchestrator...

REM Activation de l'environnement virtuel (si applicable)
REM call venv\\Scripts\\activate

REM Démarrage de l'API backend
echo Starting API backend...
start "API Backend" python start_api_server.py

REM Attente de 10 secondes pour que l'API démarre
timeout /t 10

REM Démarrage de l'orchestrateur en mode planifié
echo Starting SharePoint Orchestrator...
python sharepoint_orchestrator.py scheduled

pause
"""
        
        windows_path = self.project_root / "start_orchestrator.bat"
        with open(windows_path, 'w', encoding='utf-8') as f:
            f.write(windows_script)
        
        # Script Linux/Mac
        linux_script = """#!/bin/bash
echo "Starting DPGF SharePoint Orchestrator..."

# Activation de l'environnement virtuel (si applicable)
# source venv/bin/activate

# Démarrage de l'API backend
echo "Starting API backend..."
python start_api_server.py &
API_PID=$!

# Attente de 10 secondes pour que l'API démarre
sleep 10

# Démarrage de l'orchestrateur en mode planifié
echo "Starting SharePoint Orchestrator..."
python sharepoint_orchestrator.py scheduled

# Nettoyage à la fin
kill $API_PID 2>/dev/null
"""
        
        linux_path = self.project_root / "start_orchestrator.sh"
        with open(linux_path, 'w', encoding='utf-8') as f:
            f.write(linux_script)
        
        # Rendre le script Linux exécutable
        try:
            os.chmod(linux_path, 0o755)
        except:
            pass
        
        print(f"✅ Scripts de démarrage créés:")
        print(f"   Windows: {windows_path}")
        print(f"   Linux/Mac: {linux_path}")
    
    def create_systemd_service(self):
        """Crée un service systemd pour Linux"""
        service_content = f"""[Unit]
Description=DPGF SharePoint Orchestrator
After=network.target

[Service]
Type=simple
User=dpgf
WorkingDirectory={self.project_root}
ExecStart={sys.executable} sharepoint_orchestrator.py scheduled
Restart=always
RestartSec=10
Environment=PYTHONPATH={self.project_root}

[Install]
WantedBy=multi-user.target
"""
        
        service_path = self.project_root / "dpgf-orchestrator.service"
        with open(service_path, 'w', encoding='utf-8') as f:
            f.write(service_content)
        
        print(f"✅ Service systemd créé: {service_path}")
        print("Pour installer le service:")
        print(f"  sudo cp {service_path} /etc/systemd/system/")
        print("  sudo systemctl daemon-reload")
        print("  sudo systemctl enable dpgf-orchestrator")
        print("  sudo systemctl start dpgf-orchestrator")
    
    def create_monitoring_script(self):
        """Crée un script de monitoring simple"""
        monitoring_script = """#!/usr/bin/env python3
\"\"\"
Script de monitoring pour l'orchestrateur SharePoint DPGF.
Vérifie l'état du service et envoie des alertes si nécessaire.
\"\"\"

import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

def check_api_health():
    \"\"\"Vérifie la santé de l'API\"\"\"
    try:
        response = requests.get('http://127.0.0.1:8000/docs', timeout=10)
        return response.status_code == 200
    except:
        return False

def check_recent_logs():
    \"\"\"Vérifie s'il y a des logs récents\"\"\"
    logs_dir = Path('logs')
    if not logs_dir.exists():
        return False
    
    # Cherche des logs des dernières 2 heures
    cutoff = datetime.now() - timedelta(hours=2)
    
    for log_file in logs_dir.glob('sharepoint_orchestrator_*.log'):
        if log_file.stat().st_mtime > cutoff.timestamp():
            return True
    
    return False

def send_alert(message):
    \"\"\"Envoie une alerte (adaptez selon vos besoins)\"\"\"
    print(f"🚨 ALERTE: {message}")
    # Ici vous pouvez ajouter l'envoi d'email, notification Slack, etc.

def main():
    print(f"🔍 Monitoring - {datetime.now()}")
    
    # Vérification API
    if not check_api_health():
        send_alert("API DPGF non accessible")
    else:
        print("✅ API accessible")
    
    # Vérification logs récents
    if not check_recent_logs():
        send_alert("Aucun log récent détecté - Orchestrateur possiblement arrêté")
    else:
        print("✅ Logs récents détectés")

if __name__ == "__main__":
    main()
"""
        
        monitoring_path = self.project_root / "monitor_orchestrator.py"
        with open(monitoring_path, 'w', encoding='utf-8') as f:
            f.write(monitoring_script)
        
        print(f"✅ Script de monitoring créé: {monitoring_path}")
    
    def setup_complete(self):
        """Configuration complète"""
        print("🚀 Configuration de l'orchestrateur SharePoint DPGF\n")
        
        print("1. Création des dossiers...")
        self.create_directories()
        
        print("\n2. Installation des dépendances...")
        self.install_dependencies()
        
        print("\n3. Création du fichier .env...")
        self.create_env_file()
        
        print("\n4. Création de la configuration...")
        self.create_config_file()
        
        print("\n5. Création des scripts de démarrage...")
        self.create_startup_scripts()
        
        print("\n6. Création du service systemd...")
        self.create_systemd_service()
        
        print("\n7. Création du script de monitoring...")
        self.create_monitoring_script()
        
        print("\n" + "="*60)
        print("✅ CONFIGURATION TERMINÉE")
        print("="*60)
        
        print("\n📋 ÉTAPES SUIVANTES:")
        print("1. Modifiez le fichier .env avec vos paramètres SharePoint")
        print("2. Testez la connexion: python sharepoint_orchestrator.py once")
        print("3. Lancez en mode planifié: python sharepoint_orchestrator.py scheduled")
        print("4. Analysez les logs: python log_analyzer.py")
        print("5. Monitoring: python monitor_orchestrator.py")
        
        print("\n🔧 COMMANDES UTILES:")
        print("• Test unique: python sharepoint_orchestrator.py once")
        print("• Mode planifié: python sharepoint_orchestrator.py scheduled")
        print("• Monitoring continu: python sharepoint_orchestrator.py monitor")
        print("• Analyse des logs: python log_analyzer.py --date 20250630")
        print("• Monitoring système: python monitor_orchestrator.py")


def main():
    """Fonction principale"""
    config = SharePointConfig()
    config.setup_complete()


if __name__ == "__main__":
    main()
