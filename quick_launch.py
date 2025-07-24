"""
Script de configuration et lancement rapide de l'orchestrateur DPGF
Fournit des profils prédéfinis et une interface simple
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import argparse

# Profils de configuration prédéfinis
CONFIGURATION_PROFILES = {
    "test": {
        "name": "Mode Test",
        "description": "Test rapide sur quelques dossiers",
        "params": {
            "test_mode": True,
            "max_folders": 3,
            "max_files_per_folder": 5,
            "batch_size": 1,
            "deep_scan": False,
            "auto_import": False
        }
    },
    "dev": {
        "name": "Mode Développement",
        "description": "Développement avec debug et analyse approfondie",
        "params": {
            "max_folders": 10,
            "max_files_per_folder": 20,
            "batch_size": 2,
            "deep_scan": True,
            "auto_import": True,
            "debug_import": True
        }
    },
    "production": {
        "name": "Mode Production",
        "description": "Traitement complet avec import automatique",
        "params": {
            "batch_size": 3,
            "max_files_per_folder": 100,
            "deep_scan": True,
            "auto_import": True,
            "min_confidence": 0.8
        }
    },
    "scan_only": {
        "name": "Scan Seulement",
        "description": "Identification des fichiers sans import",
        "params": {
            "max_folders": 50,
            "max_files_per_folder": 50,
            "batch_size": 5,
            "deep_scan": True,
            "auto_import": False
        }
    },
    "import_focused": {
        "name": "Import Focalisé",
        "description": "Import avec analyse Gemini pour qualité maximale",
        "params": {
            "max_folders": 20,
            "max_files_per_folder": 30,
            "batch_size": 2,
            "deep_scan": True,
            "auto_import": True,
            "chunk_size": 15,
            "debug_import": True
        }
    }
}

class OrchestratorConfig:
    """Gestionnaire de configuration pour l'orchestrateur"""
    
    def __init__(self):
        self.config_file = Path("orchestrator_config.json")
        self.load_saved_config()
    
    def load_saved_config(self):
        """Charge la configuration sauvegardée"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.saved_config = json.load(f)
            except:
                self.saved_config = {}
        else:
            self.saved_config = {}
    
    def save_config(self, config: Dict):
        """Sauvegarde la configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Impossible de sauvegarder la configuration: {str(e)}")
    
    def get_profile_config(self, profile_name: str) -> Dict:
        """Récupère la configuration d'un profil"""
        if profile_name in CONFIGURATION_PROFILES:
            return CONFIGURATION_PROFILES[profile_name]["params"].copy()
        else:
            raise ValueError(f"Profil '{profile_name}' non trouvé")
    
    def list_profiles(self):
        """Affiche la liste des profils disponibles"""
        print("📋 PROFILS DE CONFIGURATION DISPONIBLES:")
        print("="*60)
        
        for profile_id, profile_info in CONFIGURATION_PROFILES.items():
            print(f"\n🔖 {profile_id}")
            print(f"   Nom: {profile_info['name']}")
            print(f"   Description: {profile_info['description']}")
            
            # Afficher les paramètres principaux
            params = profile_info['params']
            key_params = ['max_folders', 'auto_import', 'deep_scan', 'test_mode']
            param_summary = []
            for key in key_params:
                if key in params:
                    param_summary.append(f"{key}={params[key]}")
            
            if param_summary:
                print(f"   Paramètres: {', '.join(param_summary)}")
    
    def interactive_config(self) -> Dict:
        """Configuration interactive"""
        print("🔧 CONFIGURATION INTERACTIVE")
        print("="*40)
        
        config = {}
        
        # Choix du mode de base
        print("\n1️⃣ Choisir le mode de base:")
        print("   1. Test rapide (3 dossiers)")
        print("   2. Développement (debug activé)")
        print("   3. Production (traitement complet)")
        print("   4. Scan seulement (pas d'import)")
        print("   5. Configuration personnalisée")
        
        try:
            choice = input("\nVotre choix (1-5): ").strip()
            
            if choice == "1":
                config = self.get_profile_config("test")
            elif choice == "2":
                config = self.get_profile_config("dev")
            elif choice == "3":
                config = self.get_profile_config("production")
            elif choice == "4":
                config = self.get_profile_config("scan_only")
            elif choice == "5":
                config = self._custom_config()
            else:
                print("❌ Choix invalide, utilisation du mode test")
                config = self.get_profile_config("test")
        
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Configuration annulée")
            return {}
        
        # Options supplémentaires
        try:
            print("\n2️⃣ Options supplémentaires:")
            
            # Clé Gemini
            if input("   Utiliser Gemini pour l'analyse avancée? (o/N): ").strip().lower() in ['o', 'oui', 'y', 'yes']:
                gemini_key = input("   Clé API Gemini: ").strip()
                if gemini_key:
                    config['gemini_key'] = gemini_key
                    config['chunk_size'] = config.get('chunk_size', 20)
            
            # Filtres de dossier
            folder_filters = input("   Filtres de dossier (ex: 2024,LOT) [optionnel]: ").strip()
            if folder_filters:
                config['folder_filters'] = folder_filters
            
            # Limite de dossiers
            if not config.get('test_mode'):
                max_folders = input("   Nombre maximum de dossiers [illimité]: ").strip()
                if max_folders.isdigit():
                    config['max_folders'] = int(max_folders)
        
        except (KeyboardInterrupt, EOFError):
            print("\n⚠️ Configuration de base utilisée")
        
        return config
    
    def _custom_config(self) -> Dict:
        """Configuration personnalisée complète"""
        config = {}
        
        try:
            print("\n🔧 Configuration personnalisée:")
            
            # Paramètres de base
            max_folders = input("   Nombre max de dossiers [illimité]: ").strip()
            if max_folders.isdigit():
                config['max_folders'] = int(max_folders)
            
            max_files = input("   Fichiers max par dossier [50]: ").strip()
            config['max_files_per_folder'] = int(max_files) if max_files.isdigit() else 50
            
            batch_size = input("   Taille des lots [3]: ").strip()
            config['batch_size'] = int(batch_size) if batch_size.isdigit() else 3
            
            # Options booléennes
            config['deep_scan'] = input("   Analyse approfondie? (o/N): ").strip().lower() in ['o', 'oui', 'y', 'yes']
            config['auto_import'] = input("   Import automatique? (o/N): ").strip().lower() in ['o', 'oui', 'y', 'yes']
            
            if config['auto_import']:
                config['debug_import'] = input("   Debug import? (o/N): ").strip().lower() in ['o', 'oui', 'y', 'yes']
            
        except (KeyboardInterrupt, EOFError):
            print("\n⚠️ Configuration par défaut utilisée")
            config = self.get_profile_config("test")
        
        return config
    
    def validate_config(self, config: Dict) -> Dict:
        """Valide et corrige la configuration"""
        validated = config.copy()
        
        # Valeurs par défaut et limites
        if 'max_files_per_folder' not in validated:
            validated['max_files_per_folder'] = 50
        
        if 'batch_size' not in validated:
            validated['batch_size'] = 3
        
        # Limites de sécurité
        if validated.get('max_files_per_folder', 0) > 200:
            print("⚠️ Limite de fichiers par dossier réduite à 200")
            validated['max_files_per_folder'] = 200
        
        if validated.get('batch_size', 0) > 10:
            print("⚠️ Taille de lot réduite à 10")
            validated['batch_size'] = 10
        
        return validated


def launch_orchestrator_with_config(config: Dict) -> int:
    """Lance l'orchestrateur avec la configuration spécifiée"""
    print("🚀 LANCEMENT DE L'ORCHESTRATEUR")
    print("="*40)
    
    # Afficher la configuration
    print("\n📋 Configuration utilisée:")
    for key, value in config.items():
        if key != 'gemini_key':  # Ne pas afficher la clé
            print(f"   {key}: {value}")
        else:
            print(f"   {key}: {'***configuré***' if value else 'non configuré'}")
    
    # Construire la commande
    cmd = [sys.executable, "launch_orchestrator.py"]
    
    # Ajouter les arguments
    for key, value in config.items():
        if isinstance(value, bool) and value:
            cmd.append(f"--{key.replace('_', '-')}")
        elif not isinstance(value, bool) and value is not None:
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])
    
    print(f"\n🔧 Commande: {' '.join(cmd[:3])} [... {len(cmd)-3} arguments]")
    
    # Confirmation
    try:
        confirm = input("\n▶️ Lancer l'orchestrateur? (O/n): ").strip()
        if confirm.lower() in ['n', 'non', 'no']:
            print("❌ Lancement annulé")
            return 1
    except (KeyboardInterrupt, EOFError):
        print("\n❌ Lancement annulé")
        return 1
    
    # Lancer
    try:
        print("\n🚀 Lancement en cours...")
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except Exception as e:
        print(f"❌ Erreur lors du lancement: {str(e)}")
        return 1


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Configuration et lancement rapide de l'orchestrateur DPGF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:

  # Lancement avec profil prédéfini
  python quick_launch.py --profile test

  # Configuration interactive
  python quick_launch.py --interactive

  # Lister les profils disponibles
  python quick_launch.py --list-profiles

  # Lancement direct avec paramètres
  python quick_launch.py --profile production --gemini-key "votre_clé"

  # Diagnostic rapide avant lancement
  python quick_launch.py --health-check
        """
    )
    
    # Mode d'opération
    parser.add_argument('--profile', type=str, choices=list(CONFIGURATION_PROFILES.keys()),
                       help='Utiliser un profil de configuration prédéfini')
    parser.add_argument('--interactive', action='store_true',
                       help='Configuration interactive')
    parser.add_argument('--list-profiles', action='store_true',
                       help='Lister les profils disponibles')
    parser.add_argument('--health-check', action='store_true',
                       help='Vérification rapide de l\'état du système avant lancement')
    
    # Options supplémentaires
    parser.add_argument('--gemini-key', type=str,
                       help='Clé API Google Gemini')
    parser.add_argument('--folder-filters', type=str,
                       help='Filtres de dossier (séparés par virgules)')
    parser.add_argument('--max-folders', type=int,
                       help='Nombre maximum de dossiers')
    parser.add_argument('--no-launch', action='store_true',
                       help='Configurer seulement, ne pas lancer')
    
    args = parser.parse_args()
    
    # Créer le gestionnaire de configuration
    config_manager = OrchestratorConfig()
    
    try:
        # Lister les profils si demandé
        if args.list_profiles:
            config_manager.list_profiles()
            return 0
        
        # Vérification de santé si demandée
        if args.health_check:
            print("🩺 VÉRIFICATION RAPIDE DU SYSTÈME")
            print("="*40)
            
            # Lancer le diagnostic rapide
            try:
                result = subprocess.run([
                    sys.executable, "import_diagnostics.py", "--health-check"
                ], cwd=Path(__file__).parent, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(result.stdout)
                else:
                    print("⚠️ Problèmes détectés lors de la vérification")
                    print(result.stderr)
                
                confirm = input("\n▶️ Continuer malgré les problèmes? (o/N): ").strip()
                if confirm.lower() not in ['o', 'oui', 'y', 'yes']:
                    print("❌ Lancement annulé")
                    return 1
                    
            except Exception as e:
                print(f"⚠️ Impossible de faire la vérification: {str(e)}")
        
        # Déterminer la configuration à utiliser
        config = {}
        
        if args.profile:
            print(f"📋 Utilisation du profil: {args.profile}")
            config = config_manager.get_profile_config(args.profile)
            profile_info = CONFIGURATION_PROFILES[args.profile]
            print(f"   {profile_info['name']}: {profile_info['description']}")
            
        elif args.interactive:
            config = config_manager.interactive_config()
            if not config:
                return 1
        else:
            # Configuration par défaut ou paramètres en ligne de commande
            print("📋 Configuration par défaut (mode test)")
            config = config_manager.get_profile_config("test")
        
        # Appliquer les options supplémentaires de la ligne de commande
        if args.gemini_key:
            config['gemini_key'] = args.gemini_key
        if args.folder_filters:
            config['folder_filters'] = args.folder_filters
        if args.max_folders:
            config['max_folders'] = args.max_folders
        
        # Valider la configuration
        config = config_manager.validate_config(config)
        
        # Sauvegarder la configuration
        config_manager.save_config({
            'last_used': datetime.now().isoformat(),
            'config': config
        })
        
        # Lancer l'orchestrateur si demandé
        if not args.no_launch:
            return launch_orchestrator_with_config(config)
        else:
            print("✅ Configuration sauvegardée sans lancement")
            return 0
        
    except KeyboardInterrupt:
        print("\n❌ Opération annulée par l'utilisateur")
        return 1
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
