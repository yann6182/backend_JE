from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.crud import section as crud
from app.schemas.section import SectionCreate, SectionRead, SectionWithLot, SectionWithHierarchy, SectionTree
from app.api.deps import get_db

router = APIRouter(prefix='/sections', tags=['sections'])

@router.post('/', response_model=SectionRead)
def create_section(section_in: SectionCreate, db: Session = Depends(get_db)):
    return crud.create_section(db, section_in)

@router.get('/', response_model=list[SectionRead])
def read_sections(
    skip: int = 0, 
    limit: int = 100, 
    lot_id: int = Query(None, description="Filtrer par ID de lot"),
    dpgf_id: int = Query(None, description="Filtrer par ID de DPGF"),
    include_hierarchy: bool = Query(False, description="Inclure les détails du lot et du DPGF"),
    db: Session = Depends(get_db)
):
    """
    Récupérer la liste des sections, avec options de filtrage par lot ou DPGF.
    """
    if dpgf_id is not None:
        if include_hierarchy:
            return crud.get_sections_by_dpgf(db, dpgf_id, skip, limit)
        else:
            return crud.get_sections_by_dpgf(db, dpgf_id, skip, limit)
    elif lot_id is not None:
        return crud.get_sections_by_lot(db, lot_id, skip, limit)
    elif include_hierarchy:
        return crud.get_sections_with_hierarchy(db, skip, limit)
    else:
        return crud.get_sections(db, skip, limit)

@router.get('/with_elements_count', response_model=List[Dict[str, Any]])
def read_sections_with_elements_count(
    dpgf_id: int = Query(None, description="Filtrer par ID de DPGF"),
    db: Session = Depends(get_db)
):
    """
    Récupérer les sections avec le nombre d'éléments d'ouvrage dans chacune.
    Option de filtrage par DPGF.
    """
    return crud.get_sections_with_elements_count(db, dpgf_id)

@router.get('/tree', response_model=List[Dict[str, Any]])
def read_section_tree(
    dpgf_id: int = Query(..., description="ID du DPGF pour récupérer l'arborescence"),
    db: Session = Depends(get_db)
):
    """
    Récupérer l'arborescence hiérarchique des sections pour un DPGF spécifique.
    """
    return crud.get_section_tree_by_dpgf(db, dpgf_id)

@router.get('/{section_id}', response_model=SectionRead)
def read_section(
    section_id: int, 
    include_hierarchy: bool = Query(False, description="Inclure les détails du lot et du DPGF"),
    db: Session = Depends(get_db)
):
    if include_hierarchy:
        obj = crud.get_section_with_hierarchy(db, section_id)
    else:
        obj = crud.get_section(db, section_id)
    
    if not obj:
        raise HTTPException(status_code=404, detail='Section not found')
    return obj

@router.delete('/{section_id}', status_code=204)
def delete_section(section_id: int, db: Session = Depends(get_db)):
    crud.delete_section(db, section_id)
    return None
