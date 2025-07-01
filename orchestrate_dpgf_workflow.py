#!/usr/bin/env python3
"""
Orchestrateur optimisé pour le workflow d'identification et d'import de fichiers DPGF/BPU/DQE.

Ce script traite dossier par dossier pour éviter les timeouts et utilise la même logique
de détection robuste que dans identify_relevant_files_sharepoint.py.

Fonctionnalités :
- Traitement progressif dossier par dossier
- Utilisation de la logique de détection robuste (nom + contenu Excel)
- Import automatique au fil de l'eau
- Rapports progressifs et consolidés
- Gestion des erreurs et reprise sur échec
- Options de filtrage et limitation

Auteur: Assistant IA
Date: 2024
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import tempfile
import shutil
import subprocess
from collections import Counter, defaultdict

# Configuration de l'encodage pour Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    # Forcer l'encodage UTF-8 pour les sous-processus
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Ajouter le répertoire scripts au path pour importer les modules
scripts_dir = Path(__file__).parent / "scripts"
if scripts_dir.exists():
    sys.path.insert(0, str(scripts_dir))

try:
    from identify_relevant_files_sharepoint import (
        FileIdentifier, SharePointClient, detect_document_type_from_filename,
        scan_excel_content, EXCEL_EXTENSIONS, setup_logging
    )
except ImportError as e:
    print(f"❌ Erreur d'import des modules SharePoint: {e}")
    print("💡 Assurez-vous que identify_relevant_files_sharepoint.py est dans scripts/")
    sys.exit(1)

# Configuration par défaut
DEFAULT_SHAREPOINT_BASE = "https://sef92230.sharepoint.com/sites/etudes"
DEFAULT_ROOT_FOLDER = "/"
DEFAULT_MIN_CONFIDENCE = 0.3
DEFAULT_BATCH_SIZE = 5  # Nombre de dossiers traités en parallèle
DEFAULT_MAX_FILES_PER_FOLDER = 50  # Limite par dossier pour éviter les timeouts

class FolderProcessor:
    """Classe pour traiter un dossier SharePoint individuellement"""
    
    def __init__(self, sharepoint_client: SharePointClient, min_confidence: float = 0.3, 
                 max_files_per_folder: int = None, deep_scan: bool = False):
        self.sharepoint_client = sharepoint_client
        self.min_confidence = min_confidence
        self.max_files_per_folder = max_files_per_folder
        self.deep_scan = deep_scan
        self.logger = logging.getLogger(__name__)
        
    def process_folder(self, folder_path: str, folder_name: str = None, max_retries: int = 2) -> Dict:
        """
        Traite un dossier spécifique et retourne les résultats avec gestion robuste des erreurs
        
        Args:
            folder_path: Chemin SharePoint du dossier
            folder_name: Nom du dossier (pour affichage)
            max_retries: Nombre de tentatives en cas d'erreur réseau
            
        Returns:
            Dict: Résultats de l'analyse du dossier
        """
        folder_name = folder_name or folder_path.split('/')[-1] or 'racine'
        
        result = {
            'folder_path': folder_path,
            'folder_name': folder_name,
            'processed_at': datetime.now().isoformat(),
            'status': 'started',
            'files_found': 0,
            'excel_files': 0,
            'identified_files': [],
            'errors': [],
            'processing_time': 0,
            'retry_count': 0
        }
        
        start_time = time.time()
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.info(f"   🔄 Nouvelle tentative {attempt + 1}/{max_retries} pour {folder_name}")
                    result['retry_count'] = attempt
                    time.sleep(1)  # Pause courte entre tentatives
                
                self.logger.info(f"🔍 Traitement du dossier: {folder_name} ({folder_path})")
                
                # Lister les fichiers du dossier avec gestion d'encodage améliorée
                all_files = self.sharepoint_client.list_files_in_folder(folder_path, recursive=True)
                result['files_found'] = len(all_files)
                
                # Filtrer les fichiers Excel
                excel_files = [f for f in all_files 
                              if any(f['name'].lower().endswith(ext) for ext in EXCEL_EXTENSIONS)]
                result['excel_files'] = len(excel_files)
                
                self.logger.info(f"   📊 {len(all_files)} fichiers total, {len(excel_files)} Excel")
                
                if not excel_files:
                    result['status'] = 'completed'
                    result['processing_time'] = time.time() - start_time
                    return result
                
                # Limiter le nombre de fichiers si spécifié
                if self.max_files_per_folder and len(excel_files) > self.max_files_per_folder:
                    self.logger.info(f"   🚀 Limitation à {self.max_files_per_folder} fichiers Excel")
                    excel_files = excel_files[:self.max_files_per_folder]
                
                # Analyser chaque fichier Excel
                identified_files = []
                temp_dir = tempfile.mkdtemp(prefix=f"sharepoint_analysis_{folder_name}_")
                
                try:
                    for file_info in excel_files:
                        try:
                            # Analyse du nom de fichier
                            filename_scores = detect_document_type_from_filename(file_info['name'])
                            max_filename_score = max(filename_scores.values()) if filename_scores.values() else 0.0
                            
                            # Analyse du contenu si nécessaire
                            content_scores = {'DPGF': 0.0, 'BPU': 0.0, 'DQE': 0.0}
                            if self.deep_scan or max_filename_score >= self.min_confidence * 0.5:
                                # Télécharger temporairement pour analyser le contenu
                                temp_file_path = os.path.join(temp_dir, file_info['name'])
                                
                                # Tentative de téléchargement avec gestion d'erreur
                                download_success = False
                                for dl_attempt in range(2):  # 2 tentatives max par fichier
                                    try:
                                        if self.sharepoint_client.download_file(file_info['id'], temp_file_path):
                                            download_success = True
                                            break
                                    except Exception as dl_error:
                                        if dl_attempt == 0:  # Première tentative échouée
                                            self.logger.debug(f"     ⚠️ Échec téléchargement {file_info['name']}, nouvelle tentative...")
                                            time.sleep(0.5)
                                        else:
                                            self.logger.warning(f"     ❌ Échec téléchargement définitif: {file_info['name']}")
                                
                                if download_success:
                                    content_scores = scan_excel_content(temp_file_path, self.deep_scan)
                                    
                                    # Nettoyer le fichier temporaire
                                    try:
                                        os.remove(temp_file_path)
                                    except:
                                        pass
                            
                            # Combinaison des scores (même logique que le script principal)
                            combined_scores = {}
                            for doc_type in filename_scores.keys():
                                combined_scores[doc_type] = filename_scores[doc_type] + content_scores[doc_type]
                            
                            max_score = max(combined_scores.values()) if combined_scores.values() else 0.0
                            
                            # Garder si score suffisant
                            if max_score >= self.min_confidence:
                                best_type = max(combined_scores, key=combined_scores.get)
                                
                                file_result = {
                                    'path': file_info['path'],
                                    'name': file_info['name'],
                                    'type': best_type,
                                    'confidence': max_score,
                                    'scores': combined_scores,
                                    'size': file_info['size'],
                                    'modified': file_info['modified'],
                                    'created': file_info['created'],
                                    'sharepoint_id': file_info['id'],
                                    'web_url': file_info.get('web_url', ''),
                                    'source': 'sharepoint',
                                    'folder': folder_path
                                }
                                identified_files.append(file_result)
                                
                        except Exception as e:
                            error_msg = f"Erreur lors de l'analyse de {file_info['name']}: {str(e)}"
                            self.logger.warning(error_msg)
                            result['errors'].append(error_msg)
                
                finally:
                    # Nettoyer le répertoire temporaire
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass
                
                result['identified_files'] = identified_files
                result['status'] = 'completed'
                
                if identified_files:
                    self.logger.info(f"   ✅ {len(identified_files)} fichiers DPGF/BPU/DQE identifiés")
                    for file_info in identified_files:
                        self.logger.info(f"      • {file_info['name']} ({file_info['type']}, {file_info['confidence']:.2f})")
                else:
                    self.logger.info(f"   ⭕ Aucun fichier DPGF/BPU/DQE identifié")
                
                # Si on arrive ici, c'est que tout s'est bien passé
                result['processing_time'] = time.time() - start_time
                return result
                
            except Exception as e:
                error_msg = f"Erreur lors du traitement du dossier {folder_name} (tentative {attempt + 1}): {str(e)}"
                self.logger.warning(error_msg)
                
                # Vérifier si c'est une erreur de connexion réseau
                is_network_error = any(keyword in str(e).lower() for keyword in [
                    'connection', 'timeout', 'remote', 'network', 'disconnected', 'aborted'
                ])
                
                if is_network_error and attempt < max_retries - 1:
                    # Attendre avant de réessayer
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    self.logger.info(f"   ⏳ Attente de {wait_time}s avant nouvelle tentative...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Erreur définitive
                    result['errors'].append(error_msg)
                    result['status'] = 'error'
                    result['processing_time'] = time.time() - start_time
                    return result
        
        # Ne devrait jamais arriver
        result['status'] = 'error'
        result['errors'].append("Toutes les tentatives ont échoué")
        result['processing_time'] = time.time() - start_time
        return result

class WorkflowOrchestrator:
    """Orchestrateur principal du workflow optimisé"""
    
    def __init__(self, min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                 max_files_per_folder: int = DEFAULT_MAX_FILES_PER_FOLDER,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 deep_scan: bool = False,
                 auto_import: bool = False,
                 import_script_path: str = None,
                 gemini_key: str = None,
                 use_gemini: bool = True,
                 chunk_size: int = 20,
                 debug_import: bool = False):
        """
        Initialise l'orchestrateur
        
        Args:
            min_confidence: Score minimum pour identifier un fichier
            max_files_per_folder: Limite de fichiers Excel par dossier
            batch_size: Nombre de dossiers traités en parallèle
            deep_scan: Analyse approfondie du contenu
            auto_import: Import automatique des fichiers identifiés
            import_script_path: Chemin vers le script d'import
            gemini_key: Clé API Google Gemini pour analyse avancée
            use_gemini: Utiliser Gemini si clé disponible
            chunk_size: Taille des chunks pour Gemini
            debug_import: Mode debug pour l'import
        """
        self.min_confidence = min_confidence
        self.max_files_per_folder = max_files_per_folder
        self.batch_size = batch_size
        self.deep_scan = deep_scan
        self.auto_import = auto_import
        self.import_script_path = import_script_path
        self.gemini_key = gemini_key
        self.use_gemini = use_gemini and gemini_key is not None
        self.chunk_size = chunk_size
        self.debug_import = debug_import
        
        self.logger = logging.getLogger(__name__)
        self.sharepoint_client = None
        self.folder_processor = None
        
        # Statistiques globales
        self.stats = {
            'folders_processed': 0,
            'folders_with_files': 0,
            'total_files_found': 0,
            'total_excel_files': 0,
            'total_identified_files': 0,
            'total_imported_files': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        # Résultats détaillés
        self.detailed_results = []
        
    def initialize(self):
        """Initialise les composants nécessaires"""
        if not self.sharepoint_client:
            self.sharepoint_client = SharePointClient()
            
        if not self.folder_processor:
            self.folder_processor = FolderProcessor(
                self.sharepoint_client,
                min_confidence=self.min_confidence,
                max_files_per_folder=self.max_files_per_folder,
                deep_scan=self.deep_scan
            )
    
    def get_folders_to_process(self, root_folder: str = DEFAULT_ROOT_FOLDER, 
                             folder_filters: List[str] = None, max_retries: int = 3) -> List[Dict]:
        """
        Obtient la liste des dossiers à traiter avec gestion robuste des erreurs réseau
        
        Args:
            root_folder: Dossier racine SharePoint
            folder_filters: Filtres optionnels sur les noms de dossier
            max_retries: Nombre maximum de tentatives en cas d'erreur réseau
            
        Returns:
            List[Dict]: Liste des dossiers avec leurs métadonnées
        """
        self.logger.info(f"🔍 Récupération de la liste des dossiers depuis: {root_folder}")
        
        for attempt in range(max_retries):
            try:
                # Réinitialiser la connexion SharePoint à chaque tentative
                if attempt > 0:
                    self.logger.info(f"🔄 Tentative {attempt + 1}/{max_retries} après erreur réseau")
                    self.sharepoint_client = SharePointClient()
                    time.sleep(2)  # Attendre un peu entre les tentatives
                
                # Lister les éléments du dossier racine avec timeout plus court
                root_items = self.sharepoint_client.list_files_in_folder(root_folder, recursive=False)
                
                # Filtrer seulement les dossiers
                folders = [item for item in root_items if item.get('type') == 'folder']
                
                self.logger.info(f"📊 {len(folders)} dossiers trouvés dans {root_folder}")
                
                # Appliquer les filtres si spécifiés
                if folder_filters:
                    filtered_folders = []
                    for folder in folders:
                        for filter_pattern in folder_filters:
                            if filter_pattern.lower() in folder['name'].lower():
                                filtered_folders.append(folder)
                                break
                    
                    folders = filtered_folders
                    self.logger.info(f"🎯 {len(folders)} dossiers après filtrage")
                
                # Enrichir avec les chemins complets
                enriched_folders = []
                for folder in folders:
                    folder_path = f"{root_folder.rstrip('/')}/{folder['name']}"
                    enriched_folder = folder.copy()
                    enriched_folder['full_path'] = folder_path
                    enriched_folders.append(enriched_folder)
                
                return enriched_folders
                
            except Exception as e:
                error_msg = f"Erreur lors de la récupération des dossiers (tentative {attempt + 1}): {str(e)}"
                self.logger.warning(error_msg)
                
                # Si c'est une erreur de connexion réseau, on peut réessayer
                if any(keyword in str(e).lower() for keyword in [
                    'connection', 'timeout', 'remote', 'network', 'disconnected', 'aborted'
                ]):
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2  # Backoff exponentiel: 2s, 4s, 8s
                        self.logger.info(f"⏳ Attente de {wait_time}s avant nouvelle tentative...")
                        time.sleep(wait_time)
                        continue
                
                # Si ce n'est pas une erreur réseau ou si on a épuisé les tentatives
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ Échec définitif après {max_retries} tentatives")
                    raise
        
        # Ne devrait jamais arriver
        raise Exception("Erreur inattendue dans get_folders_to_process")
    
    def process_folders_batch(self, folders: List[Dict]) -> List[Dict]:
        """
        Traite un lot de dossiers
        
        Args:
            folders: Liste des dossiers à traiter
            
        Returns:
            List[Dict]: Résultats du traitement
        """
        batch_results = []
        
        for folder in folders:
            try:
                result = self.folder_processor.process_folder(
                    folder['full_path'], 
                    folder['name']
                )
                batch_results.append(result)
                
                # Mettre à jour les statistiques
                self.stats['folders_processed'] += 1
                self.stats['total_files_found'] += result['files_found']
                self.stats['total_excel_files'] += result['excel_files']
                self.stats['total_identified_files'] += len(result['identified_files'])
                
                if result['identified_files']:
                    self.stats['folders_with_files'] += 1
                
                # Import automatique si configuré et des fichiers identifiés
                if self.auto_import and result['identified_files']:
                    import_result = self.import_files_from_result(result)
                    result['import_result'] = import_result
                    if import_result.get('success', False):
                        self.stats['total_imported_files'] += import_result.get('imported_count', 0)
                
            except Exception as e:
                error_msg = f"Erreur lors du traitement du dossier {folder['name']}: {str(e)}"
                self.logger.error(error_msg)
                self.stats['errors'].append(error_msg)
                
                # Créer un résultat d'erreur
                error_result = {
                    'folder_path': folder['full_path'],
                    'folder_name': folder['name'],
                    'status': 'error',
                    'errors': [error_msg],
                    'files_found': 0,
                    'excel_files': 0,
                    'identified_files': [],
                    'processing_time': 0
                }
                batch_results.append(error_result)
        
        return batch_results
    
    def import_files_from_result(self, folder_result: Dict) -> Dict:
        """
        Lance l'import des fichiers identifiés pour un dossier
        
        Args:
            folder_result: Résultat du traitement d'un dossier
            
        Returns:
            Dict: Résultat de l'import
        """
        identified_files = folder_result.get('identified_files', [])
        if not identified_files:
            return {'success': True, 'imported_count': 0, 'message': 'Aucun fichier à importer'}
        
        # Déterminer le script d'import
        import_script = self.import_script_path
        if not import_script:
            # Auto-détection - utiliser import_complete.py en priorité
            possible_paths = [
                  # Windows path
                "scripts/import_complete.py",  # Fallback
                "import_complete.py",
                "../scripts/import_complete.py"
            ]
            
            for path in possible_paths:
                if Path(path).exists():
                    import_script = str(Path(path).resolve())  # Résoudre le chemin absolu
                    break
        
        if not import_script or not Path(import_script).exists():
            error_msg = "Script d'import non trouvé (import_complete.py recommandé ou import_dpgf_unified.py)"
            self.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        
        # Télécharger temporairement les fichiers pour l'import
        temp_dir = tempfile.mkdtemp(prefix=f"import_{folder_result['folder_name']}_")
        downloaded_files = []
        
        try:
            self.logger.info(f"📥 Téléchargement de {len(identified_files)} fichiers pour import...")
            
            for file_info in identified_files:
                try:
                    # Créer un nom de fichier sûr tout en préservant les caractères importants
                    # Garder les caractères alphanumériques, espaces, tirets, underscores, points
                    # et quelques caractères spéciaux souvent présents dans les noms DPGF
                    import unicodedata
                    
                    original_name = file_info['name']
                    # Normaliser les caractères Unicode (convertir les accents)
                    normalized_name = unicodedata.normalize('NFD', original_name)
                    # Supprimer les accents mais garder les caractères de base
                    ascii_name = ''.join(c for c in normalized_name if not unicodedata.combining(c))
                    
                    # Nettoyer en gardant plus de caractères spéciaux courants dans les noms DPGF
                    safe_filename = "".join(c for c in ascii_name 
                                           if c.isalnum() or c in (' ', '-', '_', '.', '(', ')', '&', '\'', '°', '+', '=', ',', ';')).rstrip()
                    
                    # S'assurer que le nom n'est pas vide et a une extension Excel valide
                    if not safe_filename.strip():
                        # Extension basée sur le fichier original
                        original_ext = Path(original_name).suffix.lower()
                        if original_ext in ['.xls', '.xlsx', '.xlsm']:
                            safe_filename = f"file_{hash(original_name) % 10000}{original_ext}"
                        else:
                            safe_filename = f"file_{hash(original_name) % 10000}.xlsx"
                    elif not any(safe_filename.lower().endswith(ext) for ext in ['.xls', '.xlsx', '.xlsm']):
                        # Préserver l'extension originale
                        original_ext = Path(original_name).suffix.lower()
                        if original_ext in ['.xls', '.xlsx', '.xlsm']:
                            safe_filename += original_ext
                        else:
                            safe_filename += '.xlsx'
                    
                    temp_file_path = os.path.join(temp_dir, safe_filename)
                    
                    # Log pour debug: afficher le nom original vs nettoyé
                    if original_name != safe_filename:
                        self.logger.debug(f"   📝 Nom nettoyé: '{original_name}' -> '{safe_filename}'")
                    
                    if self.sharepoint_client.download_file(file_info['sharepoint_id'], temp_file_path):
                        downloaded_files.append({
                            'temp_path': temp_file_path,
                            'original_name': original_name,
                            'safe_name': safe_filename
                        })
                        self.logger.debug(f"   ✅ {file_info['name']}")
                    else:
                        self.logger.warning(f"   ❌ Échec téléchargement: {file_info['name']}")
                        
                except Exception as e:
                    self.logger.warning(f"   ❌ Erreur téléchargement {file_info['name']}: {str(e)}")
            
            if not downloaded_files:
                return {'success': False, 'error': 'Aucun fichier téléchargé'}
            
            # Lancer le script d'import
            self.logger.info(f"🔄 Lancement de l'import pour {len(downloaded_files)} fichiers...")
            
            # Le script import_complete.py utilise --file pour chaque fichier
            import_success_count = 0
            script_name = Path(import_script).name
            
            for file_info in downloaded_files:
                file_path = file_info['temp_path']
                original_name = file_info['original_name']
                safe_name = file_info['safe_name']
                
                # Adapter la commande selon le script utilisé
                if 'import_complete.py' in script_name:
                    cmd = [sys.executable, import_script, '--file', file_path]
                    
                    # Passer le nom original du fichier pour une meilleure détection
                    cmd.extend(['--original-filename', original_name])
                    
                    # Ajouter les paramètres Gemini si disponibles
                    if self.use_gemini and self.gemini_key:
                        cmd.extend(['--gemini-key', self.gemini_key])
                        cmd.extend(['--chunk-size', str(self.chunk_size)])
                        
                        if not self.use_gemini:
                            cmd.append('--no-gemini')
                    else:
                        cmd.append('--no-gemini')
                    
                    # Mode debug si activé
                    if self.debug_import:
                        cmd.append('--debug')
                        
                else:  # fallback pour import_dpgf_unified.py
                    cmd = [sys.executable, import_script, '--file', file_path]
                
                try:
                    # Log de la commande en mode debug
                    if self.debug_import:
                        self.logger.debug(f"   🔧 Commande: {' '.join(cmd)}")
                        self.logger.debug(f"   📁 Répertoire: {Path(__file__).parent}")
                        self.logger.debug(f"   📄 Fichier: {original_name} -> {safe_name}")
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',  # Remplacer les caractères non décodables
                        timeout=600,  # 10 minutes par fichier
                        cwd=Path(__file__).parent,  # Utiliser le répertoire de l'orchestrateur comme base
                        env={
                            **os.environ, 
                            'PYTHONIOENCODING': 'utf-8',
                            'PYTHONPATH': str(Path(__file__).parent)  # Ajouter le répertoire courant au PYTHONPATH
                        }
                    )
                    
                    if result.returncode == 0:
                        import_success_count += 1
                        
                        # Analyser le résultat pour comprendre ce qui a été importé
                        imported_stats = self._parse_import_output(result.stdout)
                        
                        if imported_stats['lots_imported'] > 0 or imported_stats['sections_imported'] > 0:
                            self.logger.info(f"   ✅ Import réussi: {original_name}")
                            self.logger.info(f"      📊 {imported_stats['lots_imported']} lots, {imported_stats['sections_imported']} sections, {imported_stats['elements_imported']} éléments")
                        else:
                            self.logger.warning(f"   ⚠️ Import technique réussi mais AUCUNE DONNÉE: {original_name}")
                            self.logger.warning(f"      🔍 Fichier identifié comme DPGF mais structure non reconnue")
                            # TOUJOURS afficher la sortie pour comprendre le problème
                            self.logger.warning(f"      📋 Sortie complète: {result.stdout}")
                        
                        # Log de la sortie en mode debug pour voir les détails
                        if self.debug_import and result.stdout:
                            output_lines = result.stdout.strip().split('\n')[-10:]  # Dernières lignes
                            self.logger.debug(f"      Dernières lignes de sortie: {output_lines}")
                            
                    else:
                        self.logger.warning(f"   ❌ Échec import: {original_name} (code {result.returncode})")
                        if result.stderr:
                            self.logger.warning(f"      Erreur stderr: {result.stderr[:500]}")
                        if result.stdout:
                            self.logger.warning(f"      Sortie stdout: {result.stdout[-500:]}")
                        
                        # En mode debug, logger la commande exacte qui a échoué
                        if self.debug_import:
                            self.logger.debug(f"      Commande échouée: {' '.join(cmd)}")
                            self.logger.debug(f"      Répertoire de travail: {Path(__file__).parent}")
                            self.logger.debug(f"      Fichier source original: {original_name}")
                            self.logger.debug(f"      Fichier temporaire: {file_path}")
                            
                            # Vérifier si le fichier temporaire existe et est lisible
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                self.logger.debug(f"      Taille fichier temp: {file_size} bytes")
                            else:
                                self.logger.debug(f"      ⚠️ Fichier temporaire n'existe pas!")
                            
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"   ⏰ Timeout import: {Path(file_path).name}")
                except Exception as e:
                    self.logger.warning(f"   💥 Erreur import: {Path(file_path).name} - {str(e)}")
            
            if import_success_count > 0:
                self.logger.info(f"✅ Import terminé: {import_success_count}/{len(downloaded_files)} fichiers importés")
                return {
                    'success': True,
                    'imported_count': import_success_count,
                    'total_files': len(downloaded_files),
                    'message': f"{import_success_count}/{len(downloaded_files)} fichiers importés"
                }
            else:
                error_msg = f"Aucun fichier importé sur {len(downloaded_files)}"
                self.logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'imported_count': 0,
                    'total_files': len(downloaded_files)
                }
        
        except subprocess.TimeoutExpired:
            error_msg = "Timeout lors de l'import (> 30 min)"
            self.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        
        except Exception as e:
            error_msg = f"Erreur lors de l'import: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg}
        
        finally:
            # Nettoyer les fichiers temporaires
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def _parse_import_output(self, output: str) -> Dict:
        """
        Analyse la sortie du script d'import pour extraire les statistiques
        
        Args:
            output: Sortie du script d'import
            
        Returns:
            Dict: Statistiques d'import extraites
        """
        stats = {
            'lots_imported': 0,
            'sections_imported': 0,
            'elements_imported': 0,
            'has_data': False
        }
        
        if not output:
            return stats
        
        lines = output.strip().split('\n')
        
        # Chercher les patterns de succès d'import
        import_patterns = [
            r'(\d+)\s+lots?\s+import',
            r'(\d+)\s+sections?\s+import',
            r'(\d+)\s+éléments?\s+import',
            r'(\d+)\s+lignes?\s+import',
            r'Imported\s+(\d+)\s+lots?',
            r'Imported\s+(\d+)\s+sections?',
            r'Imported\s+(\d+)\s+elements?',
            r'Successfully\s+imported\s+(\d+)',
            # Nouveaux patterns pour le script import_complete.py
            r'Lots\s+créés:\s*(\d+)',
            r'Sections\s+créées:\s*(\d+)',
            r'Éléments\s+créés:\s*(\d+)',
            r'- Lots créés:\s*(\d+)',
            r'- Sections créées:\s*(\d+)',
            r'- Éléments créés:\s*(\d+)'
        ]
        
        import re
        
        for line in lines:
            line_lower = line.lower()
            
            # Chercher des indicateurs de succès spécifiques
            for pattern in import_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    count = int(match.group(1))
                    pattern_lower = pattern.lower()
                    
                    if any(keyword in pattern_lower for keyword in ['lot']):
                        stats['lots_imported'] = max(stats['lots_imported'], count)
                        stats['has_data'] = True
                    elif any(keyword in pattern_lower for keyword in ['section']):
                        stats['sections_imported'] = max(stats['sections_imported'], count)
                        stats['has_data'] = True
                    elif any(keyword in pattern_lower for keyword in ['élément', 'element', 'ligne']):
                        stats['elements_imported'] = max(stats['elements_imported'], count)
                        stats['has_data'] = True
            
            # Chercher des messages d'erreur spécifiques
            if any(keyword in line_lower for keyword in [
                'no data found', 'aucune donnée', 'empty file', 'fichier vide',
                'no valid structure', 'structure invalide', 'no dpgf data'
            ]):
                stats['has_data'] = False
        
        return stats
    
    def generate_progress_report(self, output_dir: str = "reports") -> str:
        """
        Génère un rapport de progression
        
        Args:
            output_dir: Répertoire de sortie
            
        Returns:
            str: Chemin du fichier de rapport généré
        """
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(output_dir, f"workflow_progress_{timestamp}.json")
        
        # Préparer les données du rapport
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'workflow_type': 'optimized_folder_by_folder',
                'configuration': {
                    'min_confidence': self.min_confidence,
                    'max_files_per_folder': self.max_files_per_folder,
                    'batch_size': self.batch_size,
                    'deep_scan': self.deep_scan,
                    'auto_import': self.auto_import
                }
            },
            'statistics': self.stats,
            'detailed_results': self.detailed_results
        }
        
        # Calculer le temps total
        if self.stats['start_time'] and self.stats['end_time']:
            total_time = (datetime.fromisoformat(self.stats['end_time']) - 
                         datetime.fromisoformat(self.stats['start_time'])).total_seconds()
            report_data['statistics']['total_processing_time'] = total_time
        
        # Sauvegarder le rapport
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return report_file
    
    def run_workflow(self, root_folder: str = DEFAULT_ROOT_FOLDER,
                    folder_filters: List[str] = None,
                    max_folders: int = None) -> Dict:
        """
        Lance le workflow complet
        
        Args:
            root_folder: Dossier racine SharePoint
            folder_filters: Filtres optionnels sur les noms de dossier
            max_folders: Nombre maximum de dossiers à traiter
            
        Returns:
            Dict: Résumé des résultats
        """
        self.stats['start_time'] = datetime.now().isoformat()
        
        try:
            # Initialiser
            self.initialize()
            
            # Obtenir la liste des dossiers
            folders_to_process = self.get_folders_to_process(root_folder, folder_filters)
            
            if max_folders and len(folders_to_process) > max_folders:
                self.logger.info(f"🚫 Limitation à {max_folders} dossiers")
                folders_to_process = folders_to_process[:max_folders]
            
            total_folders = len(folders_to_process)
            self.logger.info(f"🎯 {total_folders} dossiers à traiter")
            
            if total_folders == 0:
                self.logger.warning("❌ Aucun dossier à traiter")
                return self.stats
            
            # Traiter par lots
            for i in range(0, total_folders, self.batch_size):
                batch = folders_to_process[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (total_folders + self.batch_size - 1) // self.batch_size
                
                self.logger.info(f"📦 Traitement du lot {batch_num}/{total_batches} ({len(batch)} dossiers)")
                
                # Traiter le lot
                batch_results = self.process_folders_batch(batch)
                self.detailed_results.extend(batch_results)
                
                # Afficher un résumé du lot
                batch_identified = sum(len(r.get('identified_files', [])) for r in batch_results)
                if batch_identified > 0:
                    self.logger.info(f"   ✅ Lot {batch_num}: {batch_identified} fichiers DPGF/BPU/DQE identifiés")
                else:
                    self.logger.info(f"   ⭕ Lot {batch_num}: aucun fichier identifié")
            
            # Finaliser les statistiques
            self.stats['end_time'] = datetime.now().isoformat()
            
            # Résumé final
            self.logger.info("🎉 Workflow terminé!")
            self.logger.info(f"   📁 {self.stats['folders_processed']} dossiers traités")
            self.logger.info(f"   📊 {self.stats['total_files_found']} fichiers analysés")
            self.logger.info(f"   📋 {self.stats['total_excel_files']} fichiers Excel")
            self.logger.info(f"   🎯 {self.stats['total_identified_files']} fichiers DPGF/BPU/DQE identifiés")
            
            if self.auto_import:
                self.logger.info(f"   💾 {self.stats['total_imported_files']} fichiers importés")
            
            if self.stats['errors']:
                self.logger.warning(f"   ⚠️  {len(self.stats['errors'])} erreurs rencontrées")
            
            return self.stats
            
        except Exception as e:
            self.logger.error(f"❌ Erreur fatale du workflow: {str(e)}")
            self.stats['end_time'] = datetime.now().isoformat()
            self.stats['errors'].append(f"Erreur fatale: {str(e)}")
            raise

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Orchestrateur optimisé pour le workflow d'identification et d'import DPGF/BPU/DQE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:

  # Test rapide sur 3 dossiers
  python orchestrate_dpgf_workflow_optimized.py --max-folders 3 --max-files-per-folder 10

  # Workflow complet avec import automatique
  python orchestrate_dpgf_workflow_optimized.py --auto-import --deep-scan

  # Traitement de dossiers spécifiques (par exemple ceux contenant "2024")
  python orchestrate_dpgf_workflow_optimized.py --folder-filters "2024,LOT" --max-folders 10

  # Mode production avec toutes les options
  python orchestrate_dpgf_workflow_optimized.py \\
    --deep-scan \\
    --auto-import \\
    --batch-size 3 \\
    --max-files-per-folder 100 \\
    --reports-dir "reports_production"
        """
    )
    
    # Configuration générale
    parser.add_argument('--root-folder', type=str, default=DEFAULT_ROOT_FOLDER,
                       help=f'Dossier racine SharePoint (défaut: {DEFAULT_ROOT_FOLDER})')
    parser.add_argument('--sharepoint-base', type=str, default=DEFAULT_SHAREPOINT_BASE,
                       help=f'URL de base SharePoint (défaut: {DEFAULT_SHAREPOINT_BASE})')
    
    # Filtres et limitations
    parser.add_argument('--folder-filters', type=str,
                       help='Filtres sur les noms de dossier (séparés par virgules)')
    parser.add_argument('--max-folders', type=int,
                       help='Nombre maximum de dossiers à traiter')
    parser.add_argument('--max-files-per-folder', type=int, default=DEFAULT_MAX_FILES_PER_FOLDER,
                       help=f'Limite de fichiers Excel par dossier (défaut: {DEFAULT_MAX_FILES_PER_FOLDER})')
    
    # Configuration de l'analyse
    parser.add_argument('--min-confidence', type=float, default=DEFAULT_MIN_CONFIDENCE,
                       help=f'Score de confiance minimum (défaut: {DEFAULT_MIN_CONFIDENCE})')
    parser.add_argument('--deep-scan', action='store_true',
                       help='Analyse approfondie du contenu Excel (plus lent mais plus précis)')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                       help=f'Nombre de dossiers traités en parallèle (défaut: {DEFAULT_BATCH_SIZE})')
    
    # Import automatique
    parser.add_argument('--auto-import', action='store_true',
                       help='Import automatique des fichiers identifiés')
    parser.add_argument('--import-script', type=str,
                       help='Chemin vers le script d\'import (auto-détecté si omis)')
    
    # Configuration Gemini pour import de haute qualité
    parser.add_argument('--gemini-key', type=str,
                       help='Clé API Google Gemini pour analyse avancée des fichiers Excel (recommandé)')
    parser.add_argument('--no-gemini', action='store_true',
                       help='Désactiver Gemini même si la clé est fournie')
    parser.add_argument('--chunk-size', type=int, default=20,
                       help='Taille des chunks pour l\'analyse Gemini (défaut: 20)')
    parser.add_argument('--debug-import', action='store_true',
                       help='Mode debug pour l\'import (plus de logs)')
    
    # Rapports et logs
    parser.add_argument('--reports-dir', type=str, default='reports',
                       help='Répertoire pour les rapports (défaut: reports/)')
    parser.add_argument('--logs-dir', type=str, default='logs',
                       help='Répertoire pour les logs (défaut: logs/)')
    
    # Mode test
    parser.add_argument('--test-mode', action='store_true',
                       help='Mode test: limite automatiquement à 3 dossiers et 5 fichiers par dossier')
    
    args = parser.parse_args()
    
    # Appliquer les limitations du mode test
    if args.test_mode:
        args.max_folders = min(args.max_folders or 999, 3)
        args.max_files_per_folder = min(args.max_files_per_folder or 999, 5)
        args.batch_size = 1
        print("🧪 Mode test activé: 3 dossiers max, 5 fichiers par dossier")
    
    # Configuration du logging
    logger = setup_logging(args.logs_dir)
    
    # Traiter les filtres de dossier
    folder_filters = None
    if args.folder_filters:
        folder_filters = [f.strip() for f in args.folder_filters.split(',')]
    
    logger.info("🚀 Démarrage du workflow optimisé")
    logger.info(f"   Dossier racine: {args.root_folder}")
    logger.info(f"   Confiance minimum: {args.min_confidence}")
    logger.info(f"   Fichiers max par dossier: {args.max_files_per_folder}")
    logger.info(f"   Taille des lots: {args.batch_size}")
    logger.info(f"   Analyse approfondie: {args.deep_scan}")
    logger.info(f"   Import automatique: {args.auto_import}")
    
    # Valider et afficher la configuration Gemini
    use_gemini = args.gemini_key is not None and not args.no_gemini
    if use_gemini:
        logger.info(f"   🧠 Gemini activé avec chunks de {args.chunk_size} lignes")
    else:
        logger.info(f"   🔄 Mode analyse classique (sans Gemini)")
    
    if args.debug_import:
        logger.info(f"   🐛 Mode debug import activé")
    
    if folder_filters:
        logger.info(f"   Filtres de dossier: {folder_filters}")
    if args.max_folders:
        logger.info(f"   Dossiers maximum: {args.max_folders}")
    
    try:
        # Créer l'orchestrateur
        orchestrator = WorkflowOrchestrator(
            min_confidence=args.min_confidence,
            max_files_per_folder=args.max_files_per_folder,
            batch_size=args.batch_size,
            deep_scan=args.deep_scan,
            auto_import=args.auto_import,
            import_script_path=args.import_script,
            gemini_key=args.gemini_key,
            use_gemini=use_gemini,
            chunk_size=args.chunk_size,
            debug_import=args.debug_import
        )
        
        # Lancer le workflow
        results = orchestrator.run_workflow(
            root_folder=args.root_folder,
            folder_filters=folder_filters,
            max_folders=args.max_folders
        )
        
        # Générer le rapport de progression
        report_file = orchestrator.generate_progress_report(args.reports_dir)
        logger.info(f"📄 Rapport détaillé généré: {report_file}")
        
        # Afficher le résumé final
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DU WORKFLOW")
        print("="*60)
        print(f"✅ Dossiers traités: {results['folders_processed']}")
        print(f"📁 Dossiers avec fichiers DPGF/BPU/DQE: {results['folders_with_files']}")
        print(f"📊 Total fichiers analysés: {results['total_files_found']}")
        print(f"📋 Fichiers Excel: {results['total_excel_files']}")
        print(f"🎯 Fichiers DPGF/BPU/DQE identifiés: {results['total_identified_files']}")
        
        if args.auto_import:
            print(f"💾 Fichiers importés: {results['total_imported_files']}")
        
        if results['errors']:
            print(f"⚠️  Erreurs: {len(results['errors'])}")
            
        print(f"📄 Rapport détaillé: {report_file}")
        print("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("❌ Workflow interrompu par l'utilisateur")
        return 1
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
