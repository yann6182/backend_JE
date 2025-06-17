from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import and_
from app.db.models import ElementOuvrage, Section, Lot, DPGF
from app.schemas.element_ouvrage import ElementOuvrageCreate


def get_element(db: Session, element_id: int) -> ElementOuvrage | None:
    return db.query(ElementOuvrage).filter(ElementOuvrage.id_element == element_id).first()


def get_element_with_section(db: Session, element_id: int) -> ElementOuvrage | None:
    return db.query(ElementOuvrage).filter(ElementOuvrage.id_element == element_id).options(
        joinedload(ElementOuvrage.section)
    ).first()


def get_element_with_hierarchy(db: Session, element_id: int) -> ElementOuvrage | None:
    return db.query(ElementOuvrage).filter(ElementOuvrage.id_element == element_id).options(
        joinedload(ElementOuvrage.section).joinedload(Section.lot).joinedload(Lot.dpgf)
    ).first()


def get_elements(db: Session, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).offset(skip).limit(limit).all()
    

def get_elements_with_section(db: Session, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).options(
        joinedload(ElementOuvrage.section)
    ).join(
        Section, ElementOuvrage.id_section == Section.id_section
    ).order_by(Section.numero_section).offset(skip).limit(limit).all()


def get_elements_with_hierarchy(db: Session, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).options(
        joinedload(ElementOuvrage.section).joinedload(Section.lot).joinedload(Lot.dpgf)
    ).join(
        Section, ElementOuvrage.id_section == Section.id_section
    ).join(
        Lot, Section.id_lot == Lot.id_lot
    ).join(
        DPGF, Lot.id_dpgf == DPGF.id_dpgf
    ).order_by(
        DPGF.nom_projet, Lot.numero_lot, Section.numero_section
    ).offset(skip).limit(limit).all()


def get_elements_by_section(db: Session, section_id: int, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).options(
        joinedload(ElementOuvrage.section)
    ).filter(ElementOuvrage.id_section == section_id).offset(skip).limit(limit).all()


def get_elements_by_lot(db: Session, lot_id: int, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).options(
        joinedload(ElementOuvrage.section)
    ).join(
        Section, ElementOuvrage.id_section == Section.id_section
    ).filter(
        Section.id_lot == lot_id
    ).order_by(Section.numero_section).offset(skip).limit(limit).all()


def get_elements_by_dpgf(db: Session, dpgf_id: int, skip: int = 0, limit: int = 100) -> list[ElementOuvrage]:
    return db.query(ElementOuvrage).options(
        joinedload(ElementOuvrage.section).joinedload(Section.lot)
    ).join(
        Section, ElementOuvrage.id_section == Section.id_section
    ).join(
        Lot, Section.id_lot == Lot.id_lot
    ).filter(
        Lot.id_dpgf == dpgf_id
    ).order_by(
        Lot.numero_lot, Section.numero_section
    ).offset(skip).limit(limit).all()


def create_element(db: Session, element: ElementOuvrageCreate) -> ElementOuvrage:
    db_element = ElementOuvrage(**element.dict())
    db.add(db_element)
    db.commit()
    db.refresh(db_element)
    return db_element


def delete_element(db: Session, element_id: int) -> None:
    db.query(ElementOuvrage).filter(ElementOuvrage.id_element == element_id).delete()
    db.commit()
