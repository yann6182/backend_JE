from sqlalchemy.orm import Session
from app.db.models import DPGF
from app.schemas.dpgf import DPGFCreate


def get_dpgf(db: Session, dpgf_id: int) -> DPGF | None:
    return db.query(DPGF).filter(DPGF.id_dpgf == dpgf_id).first()


def get_dpgfs(db: Session, skip: int = 0, limit: int = 100) -> list[DPGF]:
    return db.query(DPGF).offset(skip).limit(limit).all()


def create_dpgf(db: Session, dpgf: DPGFCreate) -> DPGF:
    db_dpgf = DPGF(**dpgf.dict())
    db.add(db_dpgf)
    db.commit()
    db.refresh(db_dpgf)
    return db_dpgf


def delete_dpgf(db: Session, dpgf_id: int) -> None:
    db.query(DPGF).filter(DPGF.id_dpgf == dpgf_id).delete()
    db.commit()


def get_dpgf_structure(db: Session, dpgf_id: int) -> dict:
    """
    Récupère la structure complète d'un DPGF avec ses lots, sections et éléments d'ouvrage.
    Retourne une représentation hiérarchique qui facilite l'affichage comme dans Excel.
    """
    from sqlalchemy.orm import joinedload
    from app.db.models import Lot, Section, ElementOuvrage
    
    # Récupérer le DPGF avec ses lots préchargés
    dpgf = db.query(DPGF).filter(DPGF.id_dpgf == dpgf_id).options(
        joinedload(DPGF.lots)
    ).first()
    
    if not dpgf:
        return None
    
    # Construire la structure de base
    structure = {
        "id_dpgf": dpgf.id_dpgf,
        "nom_projet": dpgf.nom_projet,
        "date_dpgf": dpgf.date_dpgf,
        "statut_offre": dpgf.statut_offre,
        "lots": []
    }
    
    # Parcourir les lots
    for lot in dpgf.lots:
        lot_dict = {
            "id_lot": lot.id_lot,
            "numero_lot": lot.numero_lot,
            "nom_lot": lot.nom_lot,
            "sections": []
        }
        
        # Récupérer toutes les sections de ce lot
        sections = db.query(Section).filter(Section.id_lot == lot.id_lot).order_by(
            Section.numero_section
        ).all()
        
        for section in sections:
            section_dict = {
                "id_section": section.id_section,
                "numero_section": section.numero_section,
                "titre_section": section.titre_section,
                "niveau_hierarchique": section.niveau_hierarchique,
                "elements": []
            }
            
            # Récupérer tous les éléments de cette section
            elements = db.query(ElementOuvrage).filter(
                ElementOuvrage.id_section == section.id_section
            ).all()
            
            for element in elements:
                element_dict = {
                    "id_element": element.id_element,
                    "designation_exacte": element.designation_exacte,
                    "unite": element.unite,
                    "quantite": element.quantite,
                    "prix_unitaire_ht": element.prix_unitaire_ht,
                    "prix_total_ht": element.prix_total_ht,
                    "offre_acceptee": element.offre_acceptee
                }
                section_dict["elements"].append(element_dict)
            
            lot_dict["sections"].append(section_dict)
        
        structure["lots"].append(lot_dict)
    
    return structure
