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


def search_similar_elements(db: Session, query: str, threshold: float = 0.7, limit: int = 50) -> list[ElementOuvrage]:
    """
    Recherche des éléments d'ouvrage similaires au texte fourni
    
    Args:
        db: Session de base de données
        query: Texte à rechercher
        threshold: Seuil de similarité (0.0 - 1.0)
        limit: Nombre maximum de résultats
        
    Returns:
        Liste des éléments d'ouvrage similaires, avec un attribut 'similarity' ajouté
    """
    try:
        # Si SQLAlchemy supporte les recherches de similarité de texte (PostgreSQL)
        from sqlalchemy.sql import func
        from sqlalchemy.sql.expression import cast
        from sqlalchemy import String, Float
        
        # Normaliser la requête
        query = query.strip().lower()
        
        # Utiliser la fonction de similarité de texte de PostgreSQL
        elements = db.query(
            ElementOuvrage,
            func.similarity(
                func.lower(ElementOuvrage.libelle), 
                query
            ).label('similarity')
        ).filter(
            func.similarity(
                func.lower(ElementOuvrage.libelle),
                query
            ) > threshold
        ).options(
            joinedload(ElementOuvrage.section).joinedload(Section.lot).joinedload(Lot.dpgf)
        ).order_by(
            func.similarity(
                func.lower(ElementOuvrage.libelle),
                query
            ).desc()
        ).limit(limit).all()
        
        # Ajouter le score de similarité comme attribut à chaque élément
        for element, similarity in elements:
            element.similarity = similarity
        
        # Extraire uniquement les éléments (sans le score)
        return [element for element, _ in elements]
    
    except Exception as e:
        # Fallback si la fonction de similarité n'est pas disponible
        import difflib
        
        # Récupérer tous les éléments
        all_elements = db.query(ElementOuvrage).options(
            joinedload(ElementOuvrage.section).joinedload(Section.lot).joinedload(Lot.dpgf)
        ).all()
        
        # Calculer la similarité manuellement
        results = []
        query_lower = query.lower()
        
        for element in all_elements:
            if element.libelle:
                similarity = difflib.SequenceMatcher(
                    None, 
                    query_lower, 
                    element.libelle.lower()
                ).ratio()
                
                if similarity >= threshold:
                    element.similarity = similarity
                    results.append(element)
        
        # Trier par similarité décroissante et limiter les résultats
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:limit]
