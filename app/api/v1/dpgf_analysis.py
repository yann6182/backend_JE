"""
API routes pour l'analyse interactive des fichiers DPGF
Permet le téléchargement, l'analyse et l'affichage des correspondances
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.api.deps import get_db
import os
import shutil
import tempfile
import pandas as pd
from datetime import datetime
from pydantic import BaseModel
import traceback

# Import des services d'analyse et modèles
from app.services.dpgf_import import DPGFImportService
from app.crud import element_ouvrage as element_crud
from app.crud import section as section_crud
from app.crud import lot as lot_crud
from app.crud import dpgf as dpgf_crud
from app.db.models.element_ouvrage import ElementOuvrage
from app.db.models.section import Section
from app.db.models.dpgf import DPGF

router = APIRouter(prefix='/dpgf-analysis', tags=['dpgf-analysis'])

# Modèles Pydantic pour les réponses
class MatchResult(BaseModel):
    element_id: int
    libelle: str
    prix_unitaire: float
    quantite: float
    unite: Optional[str] = None
    score: float  # Score de correspondance (0-100%)
    dpgf_source: str  # Nom du DPGF source
    lot: str  # Nom du lot
    section: str  # Chemin complet de la section
    
class AnalysisResult(BaseModel):
    success: bool
    elements_count: int
    matches: List[MatchResult]
    error: Optional[str] = None

@router.post('/upload-analyze', response_model=AnalysisResult)
async def upload_and_analyze_dpgf(
    file: UploadFile = File(...),
    threshold: float = Query(70.0, description="Seuil de correspondance (pourcentage 0-100)"),
    db: Session = Depends(get_db)
):
    """
    Télécharge un fichier DPGF, l'analyse et retourne les correspondances trouvées
    dans la base de données
    
    - Le fichier est analysé sans être importé en base
    - Les correspondances sont cherchées parmi les éléments d'ouvrage existants
    - Les résultats sont retournés triés par score de correspondance
    """
    temp_dir = None
    
    try:
        # 1. Sauvegarder le fichier temporairement
        print(f"Réception du fichier pour analyse: {file.filename}")
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        print(f"Fichier sauvegardé pour analyse à: {file_path}")
        
        # 2. Récupérer la clé Gemini pour l'analyse avancée
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        use_gemini = bool(gemini_key)
        
        # 3. Charger le fichier et extraire les éléments d'ouvrage
        import_service = DPGFImportService(
            gemini_key=gemini_key,
            use_gemini=use_gemini
        )
        
        # Extraire les données du fichier sans les importer
        extracted_data = import_service.extract_data_from_file(file_path, auto_detect=True)
        
        # 4. Rechercher les correspondances en base de données
        matches = []
        
        # Pour chaque élément extrait, chercher des correspondances
        for element in extracted_data.get("elements", []):
            libelle = element.get("libelle", "")
            if not libelle:
                continue
                
            # Rechercher des éléments similaires dans la base
            db_matches = element_crud.search_similar_elements(
                db, 
                libelle, 
                threshold=threshold/100.0  # Conversion en pourcentage
            )
            
            # Ajouter les correspondances à la liste de résultats
            for db_match in db_matches:
                # Récupérer les informations du contexte
                section = section_crud.get_section(db, db_match.id_section)
                section_path = section_crud.get_section_path(db, section.id_section) if section else "Inconnue"
                
                # Récupérer les informations du lot et du DPGF
                lot = lot_crud.get_lot(db, section.id_lot) if section else None
                lot_name = lot.nom if lot else "Inconnu"
                
                dpgf = dpgf_crud.get_dpgf(db, lot.id_dpgf) if lot else None
                dpgf_name = dpgf.nom_projet if dpgf else "Inconnu"
                
                # Calculer le score pour le tri (0-100%)
                similarity_score = db_match.similarity * 100 if hasattr(db_match, 'similarity') else 0
                
                matches.append(MatchResult(
                    element_id=db_match.id_element,
                    libelle=db_match.libelle,
                    prix_unitaire=db_match.prix_unitaire or 0.0,
                    quantite=db_match.quantite or 0.0,
                    unite=db_match.unite,
                    score=similarity_score,
                    dpgf_source=dpgf_name,
                    lot=lot_name,
                    section=section_path
                ))
        
        # Trier les correspondances par score décroissant
        matches.sort(key=lambda x: x.score, reverse=True)
        
        # 5. Nettoyage des fichiers temporaires
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        # 6. Retourner les résultats
        return AnalysisResult(
            success=True,
            elements_count=len(extracted_data.get("elements", [])),
            matches=matches
        )
        
    except Exception as e:
        # Nettoyer en cas d'erreur
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
        print(f"Erreur lors de l'analyse du DPGF: {str(e)}")
        traceback.print_exc()
        
        return AnalysisResult(
            success=False,
            elements_count=0,
            matches=[],
            error=str(e)
        )

@router.get('/search-elements', response_model=List[MatchResult])
def search_elements(
    query: str,
    threshold: float = Query(70.0, description="Seuil de correspondance (pourcentage 0-100)"),
    db: Session = Depends(get_db)
):
    """
    Recherche des éléments d'ouvrage similaires au texte fourni
    
    - La recherche est effectuée sur les libellés des éléments
    - Les résultats sont retournés triés par score de correspondance
    """
    try:
        # Rechercher des éléments similaires dans la base
        db_matches = element_crud.search_similar_elements(
            db, 
            query, 
            threshold=threshold/100.0
        )
        
        # Traiter les résultats
        results = []
        for db_match in db_matches:
            # Récupérer les informations du contexte
            section = section_crud.get_section(db, db_match.id_section)
            section_path = section_crud.get_section_path(db, section.id_section) if section else "Inconnue"
            
            # Récupérer les informations du lot et du DPGF
            lot = lot_crud.get_lot(db, section.id_lot) if section else None
            lot_name = lot.nom if lot else "Inconnu"
            
            dpgf = dpgf_crud.get_dpgf(db, lot.id_dpgf) if lot else None
            dpgf_name = dpgf.nom_projet if dpgf else "Inconnu"
            
            # Calculer le score pour le tri (0-100%)
            similarity_score = db_match.similarity * 100 if hasattr(db_match, 'similarity') else 0
            
            results.append(MatchResult(
                element_id=db_match.id_element,
                libelle=db_match.libelle,
                prix_unitaire=db_match.prix_unitaire or 0.0,
                quantite=db_match.quantite or 0.0,
                unite=db_match.unite,
                score=similarity_score,
                dpgf_source=dpgf_name,
                lot=lot_name,
                section=section_path
            ))
        
        # Trier par score
        results.sort(key=lambda x: x.score, reverse=True)
        return results
        
    except Exception as e:
        print(f"Erreur lors de la recherche: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur de recherche: {str(e)}")
