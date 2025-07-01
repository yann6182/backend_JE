"""
Orchestrateur SharePoint pour l'import automatique des fichiers DPGF
avec monitoring des logs et gestion des erreurs.
"""

import sys
import os
import time
import traceback
import logging
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import pandas as pd
import schedule

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent))

from app.services.dpgf_import import DPGFImportService
from app.core.config import settings
from app.db.session import SessionLocal

class SharePointOrchestrator:
    """Orchestrateur pour l'import automatique depuis SharePoint"""
    
    def __init__(self, sharepoint_url: str, username: str, password: str):
        self.sharepoint_url = sharepoint_url
        self.username = username
        self.password = password
        self.ctx = None
        self.import_service = DPGFImportService()
        
        # Configuration des logs
        self.setup_logging()
        
        # Statistiques
        self.stats = {
            'files_processed': 0,
            'files_success': 0,
            'files_failed': 0,
            'lots_created': 0,
            'sections_created': 0,
            'elements_created': 0,
            'errors': []
        }
        
    def setup_logging(self):
        """Configuration du système de logs"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configuration du logger principal
        self.logger = logging.getLogger('sharepoint_orchestrator')
        self.logger.setLevel(logging.DEBUG)
        
        # Handler pour fichier général
        file_handler = logging.FileHandler(
            log_dir / f"sharepoint_orchestrator_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Handler pour erreurs critiques
        error_handler = logging.FileHandler(
            log_dir / f"sharepoint_errors_{datetime.now().strftime('%Y%m%d')}.log"
        )
        error_handler.setLevel(logging.ERROR)
        
        # Handler pour console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Format des logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(console_handler)
        
    def connect_sharepoint(self) -> bool:
        """Connexion à SharePoint"""
        try:
            self.logger.info("🔗 Connexion à SharePoint...")
            auth_ctx = AuthenticationContext(self.sharepoint_url)
            auth_ctx.acquire_token_for_user(self.username, self.password)
            self.ctx = ClientContext(self.sharepoint_url, auth_ctx)
            
            # Test de connexion
            web = self.ctx.web
            self.ctx.load(web)
            self.ctx.execute_query()
            
            self.logger.info(f"✅ Connecté à SharePoint: {web.properties['Title']}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur de connexion SharePoint: {str(e)}")
            return False
    
    def get_new_files(self, library_name: str, last_check: datetime = None) -> List[Dict]:
        """Récupère les nouveaux fichiers DPGF depuis une bibliothèque SharePoint"""
        try:
            if not last_check:
                last_check = datetime.now() - timedelta(hours=24)
            
            self.logger.info(f"📂 Recherche de nouveaux fichiers dans '{library_name}'...")
            
            # Accès à la bibliothèque
            doc_lib = self.ctx.web.lists.get_by_title(library_name)
            
            # Requête CAML pour filtrer les fichiers récents
            caml_query = f"""
            <View>
                <Query>
                    <Where>
                        <And>
                            <Geq>
                                <FieldRef Name='Modified'/>
                                <Value Type='DateTime'>{last_check.isoformat()}</Value>
                            </Geq>
                            <Or>
                                <Contains>
                                    <FieldRef Name='FileLeafRef'/>
                                    <Value Type='Text'>.xlsx</Value>
                                </Contains>
                                <Contains>
                                    <FieldRef Name='FileLeafRef'/>
                                    <Value Type='Text'>.xls</Value>
                                </Contains>
                            </Or>
                        </And>
                    </Where>
                </Query>
            </View>
            """
            
            items = doc_lib.get_items(caml_query)
            self.ctx.load(items)
            self.ctx.execute_query()
            
            files_info = []
            for item in items:
                file_info = {
                    'name': item.properties['FileLeafRef'],
                    'url': item.properties['FileRef'],
                    'modified': item.properties['Modified'],
                    'size': item.properties.get('File_x0020_Size', 0),
                    'author': item.properties.get('Author', {}).get('Title', 'Unknown')
                }
                files_info.append(file_info)
            
            self.logger.info(f"📄 {len(files_info)} nouveaux fichiers trouvés")
            return files_info
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la recherche de fichiers: {str(e)}")
            return []
    
    def download_file(self, file_url: str, local_path: Path) -> bool:
        """Télécharge un fichier depuis SharePoint"""
        try:
            self.logger.info(f"⬇️ Téléchargement: {file_url}")
            
            file_obj = self.ctx.web.get_file_by_server_relative_url(file_url)
            
            with open(local_path, 'wb') as local_file:
                file_obj.download(local_file)
                self.ctx.execute_query()
            
            self.logger.info(f"✅ Fichier téléchargé: {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur de téléchargement {file_url}: {str(e)}")
            return False
    
    def process_file(self, file_path: Path, file_info: Dict) -> Dict:
        """Traite un fichier DPGF avec logging détaillé"""
        result = {
            'success': False,
            'file_name': file_info['name'],
            'lots_created': 0,
            'sections_created': 0,
            'elements_created': 0,
            'errors': [],
            'processing_time': 0
        }
        
        start_time = time.time()
        
        try:
            self.logger.info(f"🔄 Traitement: {file_info['name']}")
            
            # Import du fichier
            with SessionLocal() as db:
                import_result = self.import_service.import_dpgf_file(
                    file_path=str(file_path),
                    db=db
                )
                
                if import_result.get('success', False):
                    result['success'] = True
                    result['lots_created'] = len(import_result.get('lots', []))
                    result['sections_created'] = len(import_result.get('sections', []))
                    result['elements_created'] = len(import_result.get('elements', []))
                    
                    self.logger.info(
                        f"✅ Import réussi: {result['lots_created']} lots, "
                        f"{result['sections_created']} sections, "
                        f"{result['elements_created']} éléments"
                    )
                    
                    # Mise à jour des statistiques globales
                    self.stats['lots_created'] += result['lots_created']
                    self.stats['sections_created'] += result['sections_created']
                    self.stats['elements_created'] += result['elements_created']
                    
                else:
                    result['errors'] = import_result.get('errors', ['Erreur inconnue'])
                    self.logger.error(f"❌ Échec import: {result['errors']}")
                    
        except Exception as e:
            error_msg = f"Erreur lors du traitement: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(f"❌ {error_msg}")
            self.logger.error(traceback.format_exc())
            
        finally:
            result['processing_time'] = time.time() - start_time
            
        return result
    
    def send_notification(self, message: str, level: str = "info"):
        """Envoie une notification (email, Slack, Teams, etc.)"""
        try:
            # Ici vous pouvez implémenter vos notifications
            # Exemple avec un webhook Teams/Slack
            webhook_url = os.getenv('NOTIFICATION_WEBHOOK_URL')
            
            if webhook_url:
                payload = {
                    'text': f"[DPGF Orchestrator] {message}",
                    'level': level,
                    'timestamp': datetime.now().isoformat()
                }
                
                response = requests.post(webhook_url, json=payload, timeout=10)
                if response.status_code == 200:
                    self.logger.info("📧 Notification envoyée")
                    
        except Exception as e:
            self.logger.error(f"❌ Erreur notification: {str(e)}")
    
    def generate_report(self) -> Dict:
        """Génère un rapport d'exécution"""
        return {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats.copy(),
            'success_rate': (
                self.stats['files_success'] / max(self.stats['files_processed'], 1) * 100
            ),
            'total_entities': (
                self.stats['lots_created'] + 
                self.stats['sections_created'] + 
                self.stats['elements_created']
            )
        }
    
    def save_report(self, report: Dict):
        """Sauvegarde le rapport"""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"sharepoint_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"📊 Rapport sauvegardé: {report_file}")
    
    def run_import_cycle(self, library_name: str, download_dir: str = "downloads"):
        """Exécute un cycle complet d'import"""
        try:
            self.logger.info("🚀 Démarrage du cycle d'import SharePoint")
            
            # Connexion SharePoint
            if not self.connect_sharepoint():
                self.send_notification("Échec de connexion SharePoint", "error")
                return
            
            # Création du dossier de téléchargement
            download_path = Path(download_dir)
            download_path.mkdir(exist_ok=True)
            
            # Récupération des nouveaux fichiers
            last_check = datetime.now() - timedelta(hours=1)  # Dernière heure
            new_files = self.get_new_files(library_name, last_check)
            
            if not new_files:
                self.logger.info("📭 Aucun nouveau fichier à traiter")
                return
            
            # Traitement des fichiers
            for file_info in new_files:
                self.stats['files_processed'] += 1
                
                # Téléchargement
                local_file = download_path / file_info['name']
                if not self.download_file(file_info['url'], local_file):
                    self.stats['files_failed'] += 1
                    continue
                
                # Traitement
                result = self.process_file(local_file, file_info)
                
                if result['success']:
                    self.stats['files_success'] += 1
                    self.logger.info(f"✅ Fichier traité avec succès: {file_info['name']}")
                else:
                    self.stats['files_failed'] += 1
                    self.stats['errors'].extend(result['errors'])
                    self.logger.error(f"❌ Échec traitement: {file_info['name']}")
                
                # Nettoyage du fichier temporaire
                try:
                    local_file.unlink()
                except:
                    pass
            
            # Génération du rapport
            report = self.generate_report()
            self.save_report(report)
            
            # Notification de fin
            summary = (
                f"Cycle terminé: {self.stats['files_success']}/{self.stats['files_processed']} "
                f"fichiers traités avec succès. "
                f"Entités créées: {report['total_entities']}"
            )
            
            self.logger.info(f"🎯 {summary}")
            self.send_notification(summary)
            
        except Exception as e:
            error_msg = f"Erreur critique dans le cycle d'import: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self.send_notification(error_msg, "error")


def main():
    """Fonction principale pour l'orchestrateur"""
    
    # Configuration SharePoint (à adapter selon votre environnement)
    SHAREPOINT_URL = os.getenv('SHAREPOINT_URL', 'https://votreentreprise.sharepoint.com/sites/votresite')
    SHAREPOINT_USERNAME = os.getenv('SHAREPOINT_USERNAME')
    SHAREPOINT_PASSWORD = os.getenv('SHAREPOINT_PASSWORD')
    LIBRARY_NAME = os.getenv('SHAREPOINT_LIBRARY', 'Documents DPGF')
    
    if not SHAREPOINT_USERNAME or not SHAREPOINT_PASSWORD:
        print("❌ Erreur: Variables d'environnement SharePoint manquantes")
        print("Définissez SHAREPOINT_USERNAME et SHAREPOINT_PASSWORD")
        return
    
    # Création de l'orchestrateur
    orchestrator = SharePointOrchestrator(
        sharepoint_url=SHAREPOINT_URL,
        username=SHAREPOINT_USERNAME,
        password=SHAREPOINT_PASSWORD
    )
    
    # Mode d'exécution
    mode = sys.argv[1] if len(sys.argv) > 1 else 'once'
    
    if mode == 'once':
        # Exécution unique
        print("🔄 Exécution unique de l'orchestrateur...")
        orchestrator.run_import_cycle(LIBRARY_NAME)
        
    elif mode == 'scheduled':
        # Exécution planifiée
        print("⏰ Démarrage de l'orchestrateur en mode planifié...")
        
        # Planification (toutes les heures)
        schedule.every().hour.do(orchestrator.run_import_cycle, LIBRARY_NAME)
        
        # Planification quotidienne à 8h pour rapport complet
        schedule.every().day.at("08:00").do(
            lambda: orchestrator.send_notification("Rapport quotidien disponible")
        )
        
        print("⏰ Planification active. Ctrl+C pour arrêter.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Vérification chaque minute
                
        except KeyboardInterrupt:
            print("\n🛑 Arrêt de l'orchestrateur planifié")
            
    elif mode == 'monitor':
        # Mode monitoring en continu
        print("👁️ Démarrage du monitoring en continu...")
        
        try:
            while True:
                orchestrator.run_import_cycle(LIBRARY_NAME)
                print("😴 Attente 10 minutes avant le prochain cycle...")
                time.sleep(600)  # 10 minutes
                
        except KeyboardInterrupt:
            print("\n🛑 Arrêt du monitoring")
    
    else:
        print("❌ Mode invalide. Utilisez: 'once', 'scheduled', ou 'monitor'")


if __name__ == "__main__":
    main()
