from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.crud import element_ouvrage as crud
from app.schemas.element_ouvrage import ElementOuvrageCreate, ElementOuvrageRead, ElementOuvrageWithSection, ElementOuvrageComplete
from app.api.deps import get_db

router = APIRouter(prefix='/element_ouvrages', tags=['elements_ouvrage'])

@router.post('/', response_model=ElementOuvrageRead)
def create_element(element_in: ElementOuvrageCreate, db: Session = Depends(get_db)):
    return crud.create_element(db, element_in)

@router.get('/', response_model=list[ElementOuvrageRead])
def read_elements(
    skip: int = 0, 
    limit: int = 100, 
    include_section: bool = Query(False, description="Inclure les détails de la section avec chaque élément"),
    db: Session = Depends(get_db)
):
    if include_section:
        return crud.get_elements_with_section(db, skip, limit)
    return crud.get_elements(db, skip, limit)

@router.get('/with_sections', response_model=list[ElementOuvrageWithSection])
def read_elements_with_sections(
    skip: int = 0, 
    limit: int = 100, 
    section_id: int = Query(None, description="Filtrer par ID de section"),
    lot_id: int = Query(None, description="Filtrer par ID de lot"),
    dpgf_id: int = Query(None, description="Filtrer par ID de DPGF"),
    db: Session = Depends(get_db)
):
    """
    Récupérer tous les éléments d'ouvrage avec les détails de leur section respective,
    ordonnés par numéro de section comme dans le fichier Excel.
    Possibilité de filtrer par ID de section, ID de lot ou ID de DPGF.
    """
    if section_id is not None:
        return crud.get_elements_by_section(db, section_id, skip, limit)
    elif lot_id is not None:
        return crud.get_elements_by_lot(db, lot_id, skip, limit)
    elif dpgf_id is not None:
        return crud.get_elements_by_dpgf(db, dpgf_id, skip, limit)
    return crud.get_elements_with_section(db, skip, limit)

@router.get('/complete', response_model=list[ElementOuvrageComplete])
def read_elements_complete(
    skip: int = 0, 
    limit: int = 100, 
    dpgf_id: int = Query(None, description="Filtrer par ID de DPGF"),
    db: Session = Depends(get_db)
):
    """
    Récupérer tous les éléments d'ouvrage avec leur hiérarchie complète (DPGF > Lot > Section > Élément),
    ordonnés correctement pour une affichage structuré.
    Option de filtrage par DPGF.
    """
    if dpgf_id is not None:
        return crud.get_elements_by_dpgf(db, dpgf_id, skip, limit)
    return crud.get_elements_with_hierarchy(db, skip, limit)

@router.get('/{element_id}', response_model=ElementOuvrageRead)
def read_element(
    element_id: int, 
    include_section: bool = Query(False, description="Inclure les détails de la section avec l'élément"),
    include_hierarchy: bool = Query(False, description="Inclure toute la hiérarchie (DPGF > Lot > Section > Élément)"),
    db: Session = Depends(get_db)
):
    if include_hierarchy:
        obj = crud.get_element_with_hierarchy(db, element_id)
    elif include_section:
        obj = crud.get_element_with_section(db, element_id)
    else:
        obj = crud.get_element(db, element_id)
    
    if not obj:
        raise HTTPException(status_code=404, detail='Element not found')
    return obj

@router.get('/{element_id}/with_section', response_model=ElementOuvrageWithSection)
def read_element_with_section(element_id: int, db: Session = Depends(get_db)):
    """
    Récupérer un élément d'ouvrage spécifique avec les détails de sa section,
    comme dans le fichier Excel
    """
    obj = crud.get_element_with_section(db, element_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Element not found')
    return obj

@router.get('/{element_id}/complete', response_model=ElementOuvrageComplete)
def read_element_complete(element_id: int, db: Session = Depends(get_db)):
    """
    Récupérer un élément d'ouvrage spécifique avec toute sa hiérarchie (DPGF > Lot > Section > Élément)
    """
    obj = crud.get_element_with_hierarchy(db, element_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Element not found')
    return obj

@router.delete('/{element_id}', status_code=204)
def delete_element(element_id: int, db: Session = Depends(get_db)):
    crud.delete_element(db, element_id)
    return None
