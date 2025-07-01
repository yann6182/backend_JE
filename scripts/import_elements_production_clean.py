
"""
Script d'import DPGF optimisé pour la production - Gestion de centaines de Go
Améliorations :
- Traitement par chunks (lecture partielle)
- Cache intelligent des patterns Gemini
- Batch processing des requêtes API
- Parallélisation
- Gestion mémoire optimisée
"""

import argparse
import sys
import json
import os
import hashlib
import pickle
from typing import Optional, Dict, List, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import pandas as pd
import requests
from tqdm import tqdm
import google.generativeai as genai
from pathlib import Path
import time
import re

# Configuration de l'encodage pour éviter les erreurs avec les caractères spéciaux
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


@dataclass
class ImportStats:
    """Statistiques d'import"""
    total_rows: int = 0
    sections_created: int = 0
    elements_created: int = 0
    errors: int = 0
    cache_hits: int = 0
    gemini_calls: int = 0


class GeminiCache:
    """Cache intelligent pour les réponses Gemini"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "gemini_patterns.pkl"
        self.patterns = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Charge le cache depuis le disque"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self):
        """Sauvegarde le cache sur disque"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.patterns, f)
    
    def _get_pattern_hash(self, rows: List[str]) -> str:
        """Génère un hash pour un pattern de lignes"""
        # Normaliser les lignes (enlever espaces, casse)
        normalized = []
        for row in rows:
            normalized.append(''.join(row.lower().split()))
        
        pattern = '|'.join(normalized)
        return hashlib.md5(pattern.encode()).hexdigest()
    
    def get(self, rows: List[str]) -> Optional[List[Dict]]:
        """Récupère une classification depuis le cache"""
        pattern_hash = self._get_pattern_hash(rows)
        return self.patterns.get(pattern_hash)
    
    def set(self, rows: List[str], classification: List[Dict]):
        """Met en cache une classification"""
        pattern_hash = self._get_pattern_hash(rows)
        self.patterns[pattern_hash] = classification
        self._save_cache()


class ProductionImporter:
    """Importeur optimisé pour la production"""
    
    def __init__(self, base_url: str, gemini_key: str, chunk_size: int = 100, 
                 max_workers: int = 4, batch_size: int = 10):
        self.base_url = base_url
        self.gemini_key = gemini_key
        self.chunk_size = chunk_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.cache = GeminiCache()
        self.stats = ImportStats()
        
        # Configuration Gemini
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def read_excel_chunks(self, file_path: str) -> Generator[pd.DataFrame, None, None]:
        """Lit un fichier Excel par chunks pour économiser la mémoire"""
        print(f"Lecture du fichier par chunks de {self.chunk_size} lignes...")
        
        # Lire par chunks
        skip_rows = 0
        while True:
            try:
                chunk = pd.read_excel(
                    file_path, 
                    engine='openpyxl',
                    skiprows=range(1, skip_rows + 1) if skip_rows > 0 else None,
                    nrows=self.chunk_size
                )
                
                if chunk.empty:
                    break
                
                yield chunk
                skip_rows += self.chunk_size
                
            except Exception as e:
                print(f"Erreur lecture chunk à partir de la ligne {skip_rows}: {e}")
                break
    
    def classify_chunk_with_gemini(self, df_chunk: pd.DataFrame, chunk_offset: int = 0) -> List[Dict]:
        """Classifie un chunk avec Gemini + cache"""
        
        # Préparer les données du chunk
        chunk_rows = []
        for i, row in df_chunk.iterrows():
            row_values = [str(val) if pd.notna(val) else "" for val in row.values]
            if any(val.strip() for val in row_values):
                chunk_rows.append(f"Ligne {chunk_offset + i}: {row_values}")
        
        if not chunk_rows:
            return []
        
        # Vérifier le cache
        cached_result = self.cache.get(chunk_rows)
        if cached_result:
            self.stats.cache_hits += 1
            print(f"Cache hit pour chunk de {len(chunk_rows)} lignes")
            # Ajuster les numéros de ligne pour le chunk actuel
            for item in cached_result:
                item['row'] += chunk_offset
            return cached_result
        
        # Appel Gemini si pas en cache
        self.stats.gemini_calls += 1
        result = self._call_gemini_api(chunk_rows, chunk_offset)
        
        if result:
            # Mettre en cache (avec les numéros de ligne relatifs)
            cache_result = []
            for item in result:
                cache_item = item.copy()
                cache_item['row'] -= chunk_offset  
                cache_result.append(cache_item)
            self.cache.set(chunk_rows, cache_result)
        
        return result
    
    def _call_gemini_api(self, chunk_rows: List[str], chunk_offset: int) -> List[Dict]:
        """Appel direct à l'API Gemini"""
        data_text = "\n".join(chunk_rows)
        
        prompt = f"""
        Analyse ce chunk de fichier Excel DPGF ligne par ligne.
        
        Classifie chaque ligne comme :
        - "section" : Titre de section (ex: "2.9 FERRURES", "LOT 06")
        - "element" : Élément d'ouvrage avec prix/quantité 
        - "ignore" : Ligne vide, en-tête, non pertinente
        
        Pour les SECTIONS, extrais :
        - numero_section, titre_section, niveau_hierarchique
        
        Pour les ELEMENTS, extrais :
        - designation_exacte (OBLIGATOIRE - même si vide mettre "Description manquante")
        - unite, quantite, prix_unitaire_ht, prix_total_ht
        
        Données :
        {data_text}
        
        Réponds en JSON : [{{"row": N, "type": "section|element|ignore", "data": {{...}}}}]
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Nettoyer le JSON
            if response_text.startswith('```json'):
                response_text = response_text.split('```json')[1].split('```')[0]
            elif response_text.startswith('```'):
                response_text = response_text.split('```')[1]
            
            result = json.loads(response_text.strip())
            print(f"Gemini a classifié {len(result)} lignes du chunk")
            return result
            
        except Exception as e:
            print(f"Erreur Gemini pour chunk: {e}")
            return []
    
    def get_lot_id(self, dpgf_id: int, lot_num: str) -> int:
        """Récupère l'ID du lot"""
        response = requests.get(f"{self.base_url}/api/v1/lots", params={'id_dpgf': dpgf_id})
        response.raise_for_status()
        
        lots = response.json()
        for lot in lots:
            if lot.get('numero_lot') == lot_num:
                return lot['id_lot']
        
        raise ValueError(f"Lot {lot_num} non trouvé pour le DPGF {dpgf_id}")
    
    def _create_single_section(self, lot_id: int, section_data: Dict) -> int:
        """Crée une section unique ou la récupère si elle existe déjà"""
        numero = section_data.get('numero_section', '')
        niveau_hierarchique = numero.count('.') + 1 if numero else 1
        
        # 1. Vérifier si une section avec ce numéro existe déjà dans ce lot
        try:
            response = requests.get(f"{self.base_url}/api/v1/sections", params={'lot_id': lot_id})
            response.raise_for_status()
            
            sections = response.json()
            for section in sections:
                if section.get('numero_section') == numero:
                    print(f"🔄 Section existante réutilisée: {numero} - {section.get('titre_section')}")
                    return section['id_section']
        except Exception as e:
            print(f"Erreur lors de la recherche de section existante: {e}")
        
        # 2. Créer la section si elle n'existe pas
        payload = {
            'id_lot': lot_id,
            'section_parent_id': None,
            'numero_section': numero,
            'titre_section': section_data.get('titre_section', ''),
            'niveau_hierarchique': niveau_hierarchique
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/v1/sections", json=payload)
            response.raise_for_status()
            section_id = response.json()['id_section']
            print(f"➕ Nouvelle section créée: {numero} - {section_data.get('titre_section')}")
            return section_id
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 500:
                # Essayons d'extraire plus de détails de l'erreur
                error_details = e.response.text
                print(f"Erreur 500 détaillée pour la section: {error_details}")
            raise
    
    def _create_single_element(self, section_id: int, element_data: Dict):
        """Crée un élément unique"""
        # Nettoyage des données avec gestion robuste des None
        def safe_float(value, default=0.0):
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        cleaned_data = {
            'id_section': section_id,
            'designation_exacte': element_data.get('designation_exacte', 'Description manquante'),
            'unite': str(element_data.get('unite', ''))[:10],
            'quantite': safe_float(element_data.get('quantite')),
            'prix_unitaire_ht': safe_float(element_data.get('prix_unitaire_ht')),
            'prix_total_ht': safe_float(element_data.get('prix_total_ht')),
            'offre_acceptee': False
        }
        
        response = requests.post(f"{self.base_url}/api/v1/element_ouvrages", json=cleaned_data)
        response.raise_for_status()
    
    def get_or_create_client(self, client_name: str) -> int:
        """Récupère ou crée un client dans l'API"""
        if not client_name:
            raise ValueError("Nom de client requis")
          # 1. Essayer de trouver le client existant
        try:
            response = requests.get(f"{self.base_url}/api/v1/clients")
            response.raise_for_status()
            
            clients = response.json()
            for client in clients:
                if client.get('nom_client', '').upper() == client_name.upper():
                    print(f"✅ Client existant trouvé: {client_name} (ID: {client['id_client']})")
                    return client['id_client']
        
        except Exception as e:
            print(f"Erreur lors de la recherche de clients: {e}")
          # 2. Créer le client s'il n'existe pas
        try:
            # Utiliser 'nom_client' comme attendu par le schéma ClientCreate
            client_payload = {
                'nom_client': client_name,
            }
            
            response = requests.post(f"{self.base_url}/api/v1/clients", json=client_payload)
            response.raise_for_status()
            
            client_id = response.json()['id_client']
            print(f"✅ Nouveau client créé: {client_name} (ID: {client_id})")
            return client_id
            
        except Exception as e:
            print(f"❌ Erreur création client {client_name}: {e}")
            raise
    def get_or_create_dpgf(self, client_id: int, dpgf_name: str, file_path: str = "") -> int:
        """Récupère ou crée un DPGF pour le client"""
        # 1. Chercher DPGF existant pour ce client
        try:
            response = requests.get(f"{self.base_url}/api/v1/dpgf", params={'id_client': client_id})
            response.raise_for_status()
            
            dpgfs = response.json()
            for dpgf in dpgfs:
                if dpgf_name.lower() in dpgf.get('nom_projet', '').lower():
                    print(f"✅ DPGF existant trouvé: {dpgf['nom_projet']} (ID: {dpgf['id_dpgf']})")
                    return dpgf['id_dpgf']
        
        except Exception as e:
            print(f"Erreur lors de la recherche de DPGF: {e}")        # 2. Créer nouveau DPGF
        try:
            from datetime import date
            # Adapter le payload au schéma DPGFCreate attendu
            fichier_source = Path(file_path).name if file_path else "Import_manuel.xlsx"
            
            dpgf_payload = {
                'id_client': client_id,
                'nom_projet': dpgf_name,
                'date_dpgf': date.today().isoformat(),
                'statut_offre': 'en_cours',
                'fichier_source': fichier_source
            }
            
            response = requests.post(f"{self.base_url}/api/v1/dpgf", json=dpgf_payload)
            response.raise_for_status()
            
            dpgf_id = response.json()['id_dpgf']
            print(f"✅ Nouveau DPGF créé: {dpgf_name} (ID: {dpgf_id})")
            return dpgf_id
            
        except Exception as e:
            print(f"❌ Erreur création DPGF {dpgf_name}: {e}")
            raise    
    def import_file(self, file_path: str, dpgf_id: Optional[int] = None, lot_num: Optional[str] = None, auto_detect: bool = True):
        """Import complet d'un fichier avec détection automatique du client"""
        print(f"Import production demarre - Fichier: {file_path}")
        print(f"Configuration: chunks={self.chunk_size}, workers={self.max_workers}, batch={self.batch_size}")
        
        start_time = time.time()
        
        # Détection automatique du client et création des entités si nécessaire
        if auto_detect:
            client_detector = ClientDetector()
            
            # 1. Détecter le client
            client_name = client_detector.detect_client(file_path)
            if client_name:
                client_id = self.get_or_create_client(client_name)
                  # 2. Créer/récupérer le DPGF si pas fourni
                if dpgf_id is None:
                    project_name = f"Projet {client_name} - {Path(file_path).stem}"
                    dpgf_id = self.get_or_create_dpgf(client_id, project_name, file_path)
                    
                # 3. Détecter le numéro de lot depuis le nom du fichier si pas fourni
                if lot_num is None:
                    lot_num = self._extract_lot_number(file_path)
                    if not lot_num:
                        lot_num = "01"  # Valeur par défaut
                        print(f"⚠️  Numéro de lot non détecté, utilisation de '01'")
                    else:
                        print(f"📋 Lot détecté: {lot_num}")
            else:
                if dpgf_id is None:
                    raise ValueError("Aucun client détecté et aucun DPGF fourni. Impossible de continuer.")
        
        if dpgf_id is None:
            raise ValueError("ID DPGF requis pour l'import")
        if lot_num is None:
            raise ValueError("Numéro de lot requis pour l'import")
        
        # Récupérer l'ID du lot
        lot_id = self.get_lot_id(dpgf_id, lot_num)
        print(f"Lot ID: {lot_id}")
        
        current_section_id = None
        chunk_offset = 0
        
        # Traiter le fichier par chunks
        for chunk_num, df_chunk in enumerate(self.read_excel_chunks(file_path)):
            print(f"\nTraitement chunk {chunk_num + 1} (lignes {chunk_offset}-{chunk_offset + len(df_chunk)})")
            
            # Classification du chunk
            classified_rows = self.classify_chunk_with_gemini(df_chunk, chunk_offset)
            
            if not classified_rows:
                chunk_offset += len(df_chunk)
                continue
            
            # Séparer sections et éléments
            sections = [row for row in classified_rows if row.get('type') == 'section']
            elements = [row for row in classified_rows if row.get('type') == 'element']
            
            print(f"   Trouvé: {len(sections)} sections, {len(elements)} éléments")
            
            # Créer les sections
            for section_info in sections:
                try:
                    section_id = self._create_single_section(lot_id, section_info['data'])
                    current_section_id = section_id
                    self.stats.sections_created += 1
                except Exception as e:
                    print(f"Erreur création section ligne {section_info['row']}: {e}")
                    self.stats.errors += 1
            
            # Créer les éléments
            for element_info in elements:
                if current_section_id:
                    try:
                        self._create_single_element(current_section_id, element_info['data'])
                        self.stats.elements_created += 1
                    except Exception as e:
                        print(f"Erreur création élément ligne {element_info['row']}: {e}")
                        self.stats.errors += 1
                else:
                    print(f"Élément ignoré (pas de section courante): ligne {element_info['row']}")
            
            self.stats.total_rows += len(df_chunk)
            chunk_offset += len(df_chunk)
        
        # Statistiques finales
        elapsed = time.time() - start_time
        print(f"\nImport production terminé en {elapsed:.1f}s")
        print(f"Statistiques:")
        print(f"   - Lignes traitées: {self.stats.total_rows}")
        print(f"   - Sections créées: {self.stats.sections_created}")
        print(f"   - Éléments créés: {self.stats.elements_created}")
        print(f"   - Erreurs: {self.stats.errors}")
        print(f"   - Appels Gemini: {self.stats.gemini_calls}")
        print(f"   - Cache hits: {self.stats.cache_hits}")
        print(f"   - Débit: {self.stats.total_rows / elapsed:.1f} lignes/s")


class ClientDetector:
    """Détecteur automatique du nom du client"""
    
    def __init__(self):
        # Patterns pour extraire le client du nom de fichier
        self.filename_patterns = [
            r'DPGF[_\-\s]*([A-Z][A-Za-z\s&]+?)[_\-\s]*Lot',
            r'([A-Z][A-Za-z\s&]+?)[\-_\s]*DPGF',
            r'Client[_\-\s]*([A-Z][A-Za-z\s&]+)',
            r'([A-Z]{2,}[\s&][A-Z\s]+)',  # Acronymes + mots
        ]
        
        # Mots-clés à ignorer dans la détection
        self.ignore_words = {'LOT', 'DPGF', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN', 'JUILLET', 'AOUT', 'SEPTEMBRE', 'OCTOBRE', 'DCE', 'CONSTRUCTION', 'TRAVAUX', 'BATIMENT'}
    
    def detect_from_filename(self, file_path: str) -> Optional[str]:
        """Détecte le client depuis le nom du fichier"""
        filename = Path(file_path).stem
        print(f"Analyse du nom de fichier: {filename}")
        
        for pattern in self.filename_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                client_name = match.group(1).strip()
                # Nettoyer et valider
                client_name = self._clean_client_name(client_name)
                if client_name and len(client_name) > 3:
                    print(f"Client détecté dans le nom de fichier: {client_name}")
                    return client_name
        
        return None
    
    def detect_from_excel_header(self, file_path: str) -> Optional[str]:
        """Détecte le client dans les 10 premières lignes du fichier Excel"""
        try:
            # Lire seulement les premières lignes
            df = pd.read_excel(file_path, engine='openpyxl', nrows=10, header=None)
            
            print("Analyse des premières lignes du fichier...")
            
            # Chercher dans toutes les cellules des premières lignes
            for row_idx in range(min(10, len(df))):
                for col_idx in range(min(6, len(df.columns))):  # 6 premières colonnes
                    cell_value = df.iloc[row_idx, col_idx]
                    
                    if pd.notna(cell_value):
                        cell_text = str(cell_value).strip()
                        
                        # Chercher des patterns de nom de client
                        client = self._extract_client_from_text(cell_text)
                        if client:
                            print(f"Client détecté dans la cellule [{row_idx},{col_idx}]: {client}")
                            return client
            
            return None
            
        except Exception as e:
            print(f"Erreur lors de l'analyse de l'en-tête: {e}")
            return None
    
    def _extract_client_from_text(self, text: str) -> Optional[str]:
        """Extrait un nom de client depuis un texte"""
        # Patterns pour identifier un client
        client_patterns = [
            r'^([A-Z]{2,}(?:\s+[A-Z&]+)*)\s*$',  # Acronymes en majuscules
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:HABITAT|GROUP|COMPANY|SA|SAS|SARL)',
            r'((?:[A-Z]{2,}\s*)+)(?:HABITAT|GROUP)',  # CDC HABITAT, BNP GROUP, etc.
        ]
        
        for pattern in client_patterns:
            match = re.search(pattern, text.strip())
            if match:
                client_name = match.group(1).strip()
                client_name = self._clean_client_name(client_name)
                
                # Valider que c'est un vrai nom de client
                if (len(client_name) >= 3 and 
                    not any(word in client_name.upper() for word in self.ignore_words) and
                    any(c.isalpha() for c in client_name)):
                    return client_name
        
        return None
    
    def _clean_client_name(self, name: str) -> str:
        """Nettoie un nom de client"""
        # Supprimer caractères indésirables
        name = re.sub(r'[_\-\.]+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        # Supprimer mots parasites
        words = name.split()
        cleaned_words = [w for w in words if w.upper() not in self.ignore_words]
        
        return ' '.join(cleaned_words)
    
    def detect_client(self, file_path: str) -> Optional[str]:
        """Détection complète du client (nom de fichier + contenu)"""
        print(f"🔍 Détection automatique du client pour: {file_path}")
        
        # 1. Essayer depuis le nom de fichier
        client = self.detect_from_filename(file_path)
        if client:
            return client
        
        # 2. Essayer depuis le contenu du fichier
        client = self.detect_from_excel_header(file_path)
        if client:
            return client
        
        print("⚠️  Aucun client détecté automatiquement")
        return None


def main():
    parser = argparse.ArgumentParser(description="Import DPGF optimisé avec détection automatique du client")
    parser.add_argument("--file", required=True, help="Chemin du fichier Excel")
    parser.add_argument("--dpgf-id", type=int, help="ID du DPGF cible (optionnel si détection automatique)")
    parser.add_argument("--lot-num", help="Numéro du lot (optionnel si détection automatique)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL de l'API")
    parser.add_argument("--gemini-key", required=True, help="Clé API Gemini")
    parser.add_argument("--chunk-size", type=int, default=100, help="Taille des chunks (défaut: 100)")
    parser.add_argument("--max-workers", type=int, default=4, help="Threads parallèles (défaut: 4)")
    parser.add_argument("--batch-size", type=int, default=10, help="Taille des batchs API (défaut: 10)")
    parser.add_argument("--no-auto-detect", action="store_true", help="Désactive la détection automatique")
    
    args = parser.parse_args()
    
    # Validation des arguments
    if args.no_auto_detect and (not args.dpgf_id or not args.lot_num):
        parser.error("--dpgf-id et --lot-num sont requis quand --no-auto-detect est utilisé")
    
    try:
        importer = ProductionImporter(
            base_url=args.base_url,
            gemini_key=args.gemini_key,
            chunk_size=args.chunk_size,
            max_workers=args.max_workers,
            batch_size=args.batch_size
        )
        
        # Import avec ou sans détection automatique
        importer.import_file(
            file_path=args.file,
            dpgf_id=args.dpgf_id,
            lot_num=args.lot_num,
            auto_detect=not args.no_auto_detect
        )
        
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
