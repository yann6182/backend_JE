from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.db.models import Section, Lot, DPGF, ElementOuvrage
from app.schemas.section import SectionCreate
from typing import List, Dict


def get_section(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id_section == section_id).first()


def get_section_with_hierarchy(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id_section == section_id).options(
        joinedload(Section.lot).joinedload(Lot.dpgf)
    ).first()


def get_sections(db: Session, skip: int = 0, limit: int = 100) -> list[Section]:
    return db.query(Section).offset(skip).limit(limit).all()


def get_sections_by_lot(db: Session, lot_id: int, skip: int = 0, limit: int = 100) -> list[Section]:
    return db.query(Section).filter(Section.id_lot == lot_id).order_by(Section.numero_section).offset(skip).limit(limit).all()


def get_sections_by_dpgf(db: Session, dpgf_id: int, skip: int = 0, limit: int = 100) -> list[Section]:
    return db.query(Section).join(
        Lot, Section.id_lot == Lot.id_lot
    ).filter(
        Lot.id_dpgf == dpgf_id
    ).order_by(
        Lot.numero_lot, Section.numero_section
    ).options(
        joinedload(Section.lot)
    ).offset(skip).limit(limit).all()


def get_sections_with_hierarchy(db: Session, skip: int = 0, limit: int = 100) -> list[Section]:
    return db.query(Section).options(
        joinedload(Section.lot).joinedload(Lot.dpgf)
    ).order_by(
        Section.numero_section
    ).offset(skip).limit(limit).all()


def get_sections_with_elements_count(db: Session, dpgf_id: int = None) -> list[dict]:
    query = db.query(
        Section,
        func.count(ElementOuvrage.id_element).label('elements_count')
    ).outerjoin(
        ElementOuvrage, Section.id_section == ElementOuvrage.id_section
    ).group_by(Section.id_section)
    
    if dpgf_id:
        query = query.join(Lot, Section.id_lot == Lot.id_lot).filter(Lot.id_dpgf == dpgf_id)
    
    results = query.all()
    
    sections_with_count = []
    for section, count in results:
        section_dict = {
            "id_section": section.id_section,
            "id_lot": section.id_lot,
            "section_parent_id": section.section_parent_id,
            "numero_section": section.numero_section,
            "titre_section": section.titre_section,
            "niveau_hierarchique": section.niveau_hierarchique,
            "elements_count": count
        }
        sections_with_count.append(section_dict)
    
    return sections_with_count


def get_section_tree_by_dpgf(db: Session, dpgf_id: int) -> List[Dict]:
    # Récupérer toutes les sections pour ce DPGF
    sections = get_sections_by_dpgf(db, dpgf_id)
    
    # Créer un dictionnaire pour une recherche rapide
    section_map = {section.id_section: {
        "id_section": section.id_section,
        "id_lot": section.id_lot,
        "section_parent_id": section.section_parent_id,
        "numero_section": section.numero_section,
        "titre_section": section.titre_section,
        "niveau_hierarchique": section.niveau_hierarchique,
        "children": []
    } for section in sections}
    
    # Construire l'arborescence
    tree = []
    for section in sections:
        section_dict = section_map[section.id_section]
        
        if section.section_parent_id is None:
            # Racine
            tree.append(section_dict)
        else:
            # Enfant
            if section.section_parent_id in section_map:
                section_map[section.section_parent_id]["children"].append(section_dict)
    
    return tree


def create_section(db: Session, section: SectionCreate) -> Section:
    db_section = Section(**section.dict())
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section


def delete_section(db: Session, section_id: int) -> None:
    db.query(Section).filter(Section.id_section == section_id).delete()
    db.commit()
