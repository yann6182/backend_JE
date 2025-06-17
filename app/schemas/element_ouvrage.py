from pydantic import BaseModel
from typing import Optional

class LotInfo(BaseModel):
    id_lot: int
    numero_lot: str
    nom_lot: str

    class Config:
        orm_mode = True

class DPGFInfo(BaseModel):
    id_dpgf: int
    nom_projet: str

    class Config:
        orm_mode = True

class SectionInfo(BaseModel):
    id_section: int
    numero_section: str
    titre_section: str
    niveau_hierarchique: int
    id_lot: int

    class Config:
        orm_mode = True

class SectionWithParents(SectionInfo):
    lot: Optional[LotInfo] = None

    class Config:
        orm_mode = True

class ElementOuvrageBase(BaseModel):
    id_section: int
    designation_exacte: str
    unite: str
    quantite: float
    prix_unitaire_ht: float
    prix_total_ht: float
    offre_acceptee: bool = False

class ElementOuvrageCreate(ElementOuvrageBase):
    pass

class ElementOuvrageRead(ElementOuvrageBase):
    id_element: int

    class Config:
        orm_mode = True
        
class ElementOuvrageWithSection(ElementOuvrageRead):
    section: Optional[SectionInfo] = None
    
    class Config:
        orm_mode = True

class ElementOuvrageComplete(ElementOuvrageRead):
    section: Optional[SectionWithParents] = None
    
    class Config:
        orm_mode = True
