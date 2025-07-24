"""
Endpoints API pour la recherche avancée d'éléments d'ouvrage.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.element_search import ElementSearchService


router = APIRouter()


@router.get("/search/", response_model=Dict[str, Any])
def search_elements(
    q: Optional[str] = Query(None, description="Texte de recherche"),
    client_id: Optional[int] = Query(None, description="ID du client"),
    dpgf_id: Optional[int] = Query(None, description="ID du DPGF"),
    lot_id: Optional[int] = Query(None, description="ID du lot"),
    section_id: Optional[int] = Query(None, description="ID de la section"),
    lot_numero: Optional[str] = Query(None, description="Numéro du lot"),
    min_price: Optional[float] = Query(None, description="Prix unitaire minimum"),
    max_price: Optional[float] = Query(None, description="Prix unitaire maximum"),
    sort_by: str = Query("relevance", description="Critère de tri: relevance, price, date, designation, dpgf, lot, section"),
    descending: bool = Query(True, description="Ordre décroissant si true, croissant si false"),
    limit: int = Query(100, ge=1, le=500, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    db: Session = Depends(get_db)
):
    """
    Recherche des éléments d'ouvrage avec filtrage multicritères.
    """
    # Validation des paramètres
    valid_sort_fields = ["relevance", "price", "date", "designation", "dpgf", "lot", "section"]
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Critère de tri invalide. Choix possibles: {', '.join(valid_sort_fields)}"
        )
    
    # Initialiser le service de recherche
    search_service = ElementSearchService(db)
    
    # Effectuer la recherche
    results, total_count = search_service.search_elements(
        query=q,
        client_id=client_id,
        dpgf_id=dpgf_id,
        lot_id=lot_id,
        section_id=section_id,
        lot_numero=lot_numero,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        descending=descending,
        limit=limit,
        offset=offset
    )
    
    # Construire la réponse
    response = {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "results": results
    }
    
    return response


@router.get("/suggestions/", response_model=List[str])
def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Texte partiel pour suggestions de recherche"),
    limit: int = Query(10, ge=1, le=20, description="Nombre maximum de suggestions"),
    db: Session = Depends(get_db)
):
    """
    Retourne des suggestions de recherche basées sur un texte partiel.
    """
    search_service = ElementSearchService(db)
    return search_service.get_search_suggestions(q, limit)


@router.get("/statistics/", response_model=Dict[str, Any])
def get_element_statistics(
    client_id: Optional[int] = Query(None, description="Filtrer par client"),
    dpgf_id: Optional[int] = Query(None, description="Filtrer par DPGF"),
    lot_id: Optional[int] = Query(None, description="Filtrer par lot"),
    db: Session = Depends(get_db)
):
    """
    Retourne des statistiques sur les éléments d'ouvrage.
    """
    search_service = ElementSearchService(db)
    return search_service.get_statistics(client_id=client_id, dpgf_id=dpgf_id, lot_id=lot_id)
