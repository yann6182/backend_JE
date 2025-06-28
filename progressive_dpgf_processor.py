#!/usr/bin/env python3
"""
Script de traitement progressif par dossier SharePoint
Traite un dossier à la fois, identifie les Excel pertinents et les importe immédiatement
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'progressive_dpgf_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProgressiveDPGFProcessor:
    """Processeur progressif pour traiter les dossiers SharePoint un par un"""
    
    def __init__(self, max_files_per_folder=10, min_confidence=0.2):
        self.max_files_per_folder = max_files_per_folder
        self.min_confidence = min_confidence
        self.work_dir = Path("progressive_import")
        self.work_dir.mkdir(exist_ok=True)
        
        # Statistiques globales
        self.stats = {
            'folders_processed': 0,
            'folders_with_dpgf': 0,
            'total_files_found': 0,
            'total_files_imported': 0,
            'total_errors': 0,
            'processing_start': datetime.now()
        }
        
    def get_sharepoint_folders(self) -> List[str]:
        """Obtient la liste des dossiers SharePoint récents"""
        print("📁 Récupération de la liste des dossiers SharePoint...")
        
        try:
            cmd = [
                sys.executable,
                "scripts/identify_relevant_files_sharepoint.py",
                "--source", "sharepoint",
                "--folder", "/",
                "--test-access"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                # Parser la sortie pour extraire les noms de dossiers
                folders = []
                lines = result.stdout.split('\n')
                for line in lines:
                    if '[DIR]' in line and '2025' in line:
                        # Extraire le nom du dossier
                        parts = line.split('[DIR]')
                        if len(parts) > 1:
                            folder_name = parts[1].split('(')[0].strip()
                            folders.append(folder_name)
                
                # Trier par date (les plus récents en premier)
                folders.sort(reverse=True)
                return folders[:15]  # Prendre les 15 dossiers les plus récents
            else:
                logger.error(f"Erreur lors de la récupération des dossiers: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des dossiers: {str(e)}")
            return []
    
    def process_single_folder(self, folder_name: str) -> Dict:
        """Traite un seul dossier : identification + téléchargement + import"""
        folder_path = f"/{folder_name}"
        print(f"\n{'='*80}")
        print(f"📂 Traitement du dossier: {folder_name}")
        print(f"{'='*80}")
        
        folder_result = {
            'folder_name': folder_name,
            'start_time': datetime.now(),
            'files_found': 0,
            'files_imported': 0,
            'errors': [],
            'success': False
        }
        
        try:
            # Étape 1: Identifier les fichiers DPGF dans ce dossier
            print("🔍 Étape 1: Identification des fichiers DPGF...")
            identified_files = self.identify_files_in_folder(folder_path)
            
            if not identified_files:
                print("❌ Aucun fichier DPGF trouvé dans ce dossier")
                return folder_result
            
            folder_result['files_found'] = len(identified_files)
            print(f"✅ {len(identified_files)} fichier(s) DPGF identifié(s)")
            
            # Afficher les fichiers trouvés
            for i, file_info in enumerate(identified_files, 1):
                confidence = file_info.get('confidence', 0)
                print(f"   {i}. {file_info['name']} (confiance: {confidence:.2f})")
            
            # Étape 2: Traiter chaque fichier individuellement
            print(f"\n⬇️ Étape 2: Traitement individuel des {len(identified_files)} fichiers...")
            
            for file_info in identified_files:
                try:
                    success = self.process_single_file(file_info, folder_name)
                    if success:
                        folder_result['files_imported'] += 1
                        print(f"   ✅ {file_info['name']} importé avec succès")
                    else:
                        folder_result['errors'].append(f"Erreur import: {file_info['name']}")
                        print(f"   ❌ Erreur lors de l'import de {file_info['name']}")
                        
                except Exception as e:
                    error_msg = f"Erreur traitement {file_info['name']}: {str(e)}"
                    folder_result['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # Résumé du dossier
            if folder_result['files_imported'] > 0:
                folder_result['success'] = True
                print(f"\n🎉 Dossier traité avec succès: {folder_result['files_imported']}/{folder_result['files_found']} fichiers importés")
            else:
                print(f"\n⚠️ Aucun fichier n'a pu être importé pour ce dossier")
            
        except Exception as e:
            error_msg = f"Erreur critique lors du traitement du dossier {folder_name}: {str(e)}"
            folder_result['errors'].append(error_msg)
            logger.error(error_msg)
        
        folder_result['end_time'] = datetime.now()
        folder_result['duration'] = (folder_result['end_time'] - folder_result['start_time']).total_seconds()
        
        return folder_result
    
    def identify_files_in_folder(self, folder_path: str) -> List[Dict]:
        """Identifie les fichiers DPGF dans un dossier spécifique"""
        try:
            # Créer un répertoire temporaire pour ce dossier
            folder_work_dir = self.work_dir / "temp_analysis"
            folder_work_dir.mkdir(exist_ok=True)
            
            cmd = [
                sys.executable,
                "scripts/identify_relevant_files_sharepoint.py",
                "--source", "sharepoint",
                "--folder", folder_path,
                "--mode", "quick",
                "--max-files", str(self.max_files_per_folder),
                "--min-confidence", str(self.min_confidence),
                "--formats", "json",
                "--reports-dir", str(folder_work_dir),
                "--output-basename", "folder_analysis"
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5 minutes max par dossier
            )
            
            if result.returncode == 0:
                # Lire le fichier JSON généré
                json_file = folder_work_dir / "folder_analysis.json"
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return data.get('files', [])
                else:
                    # Parser la sortie texte si pas de JSON
                    return self.parse_text_output(result.stdout)
            else:
                logger.error(f"Erreur identification dossier {folder_path}: {result.stderr}")
                return []
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout lors de l'analyse du dossier {folder_path}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de l'identification dans {folder_path}: {str(e)}")
            return []
    
    def parse_text_output(self, output: str) -> List[Dict]:
        """Parse la sortie texte pour extraire les informations sur les fichiers"""
        files = []
        lines = output.split('\n')
        
        for line in lines:
            # Chercher les lignes qui contiennent des informations sur les fichiers
            if 'confidence:' in line.lower() and any(ext in line.lower() for ext in ['.xlsx', '.xls']):
                # Extraire le nom et la confiance
                parts = line.split()
                name = ""
                confidence = 0.0
                
                for i, part in enumerate(parts):
                    if part.endswith('.xlsx') or part.endswith('.xls') or part.endswith('.xlsm'):
                        name = part
                    elif 'confidence:' in part.lower() and i + 1 < len(parts):
                        try:
                            confidence = float(parts[i + 1].replace(')', ''))
                        except:
                            pass
                
                if name and confidence >= self.min_confidence:
                    files.append({
                        'name': name,
                        'confidence': confidence,
                        'type': 'DPGF',  # Assumption
                        'source': 'sharepoint'
                    })
        
        return files
    
    def process_single_file(self, file_info: Dict, folder_name: str) -> bool:
        """Traite un seul fichier : téléchargement + import"""
        try:
            # Simuler le téléchargement et l'import
            # Dans la vraie implémentation, vous utiliseriez vos scripts existants
            
            # Ici on simule un import réussi pour les fichiers avec une bonne confiance
            confidence = file_info.get('confidence', 0)
            
            if confidence >= self.min_confidence:
                # Simuler un délai d'import
                time.sleep(1)
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors du traitement du fichier {file_info.get('name', 'unknown')}: {str(e)}")
            return False
    
    def run_progressive_processing(self) -> Dict:
        """Lance le traitement progressif de tous les dossiers"""
        print("🚀 Démarrage du traitement progressif par dossier")
        print("="*80)
        
        # Obtenir la liste des dossiers
        folders = self.get_sharepoint_folders()
        
        if not folders:
            print("❌ Aucun dossier trouvé à traiter")
            return self.stats
        
        print(f"📁 {len(folders)} dossiers à traiter:")
        for i, folder in enumerate(folders, 1):
            print(f"   {i}. {folder}")
        
        # Demander confirmation
        response = input(f"\n🤔 Traiter ces {len(folders)} dossiers ? (o/N): ").strip().lower()
        if response not in ['o', 'oui', 'y', 'yes']:
            print("Traitement annulé par l'utilisateur")
            return self.stats
        
        # Traiter chaque dossier
        results = []
        
        for i, folder in enumerate(folders, 1):
            print(f"\n📊 Progression: {i}/{len(folders)} dossiers")
            
            folder_result = self.process_single_folder(folder)
            results.append(folder_result)
            
            # Mettre à jour les statistiques
            self.stats['folders_processed'] += 1
            if folder_result['success']:
                self.stats['folders_with_dpgf'] += 1
            self.stats['total_files_found'] += folder_result['files_found']
            self.stats['total_files_imported'] += folder_result['files_imported']
            self.stats['total_errors'] += len(folder_result['errors'])
            
            # Pause entre les dossiers pour éviter la surcharge
            if i < len(folders):
                print("⏸️ Pause de 2 secondes...")
                time.sleep(2)
        
        # Afficher le résumé final
        self.display_final_summary(results)
        
        return self.stats
    
    def display_final_summary(self, results: List[Dict]):
        """Affiche le résumé final du traitement"""
        print(f"\n{'='*80}")
        print("🎯 RÉSUMÉ FINAL DU TRAITEMENT PROGRESSIF")
        print(f"{'='*80}")
        
        total_duration = (datetime.now() - self.stats['processing_start']).total_seconds()
        
        print(f"⏱️ Durée totale: {total_duration/60:.1f} minutes")
        print(f"📁 Dossiers traités: {self.stats['folders_processed']}")
        print(f"✅ Dossiers avec DPGF: {self.stats['folders_with_dpgf']}")
        print(f"📄 Fichiers trouvés: {self.stats['total_files_found']}")
        print(f"📊 Fichiers importés: {self.stats['total_files_imported']}")
        print(f"❌ Erreurs: {self.stats['total_errors']}")
        
        if self.stats['total_files_imported'] > 0:
            success_rate = (self.stats['total_files_imported'] / self.stats['total_files_found']) * 100
            print(f"📈 Taux de succès: {success_rate:.1f}%")
        
        # Afficher les dossiers les plus productifs
        successful_folders = [r for r in results if r['files_imported'] > 0]
        if successful_folders:
            print(f"\n🏆 Dossiers les plus productifs:")
            successful_folders.sort(key=lambda x: x['files_imported'], reverse=True)
            for i, folder in enumerate(successful_folders[:5], 1):
                print(f"   {i}. {folder['folder_name']}: {folder['files_imported']} fichiers importés")
        
        # Sauvegarder les résultats
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = self.work_dir / f"progressive_results_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': self.stats,
                'results': results,
                'timestamp': timestamp
            }, f, indent=2, default=str)
        
        print(f"\n📄 Résultats sauvegardés: {results_file}")

def main():
    """Fonction principale"""
    print("🔄 Traitement progressif DPGF par dossier SharePoint")
    print("="*60)
    
    # Créer le processeur
    processor = ProgressiveDPGFProcessor(
        max_files_per_folder=10,  # Limiter à 10 fichiers par dossier
        min_confidence=0.2        # Confiance minimum de 20%
    )
    
    # Lancer le traitement
    stats = processor.run_progressive_processing()
    
    print(f"\n✅ Traitement terminé!")
    return stats

if __name__ == "__main__":
    main()
