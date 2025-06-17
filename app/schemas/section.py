from pydantic import BaseModel
from typing import Optional, List

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

class SectionBase(BaseModel):
    id_lot: int
    section_parent_id: int | None = None
    numero_section: str
    titre_section: str
    niveau_hierarchique: int

class SectionCreate(SectionBase):
    pass

class SectionRead(SectionBase):
    id_section: int

    class Config:
        orm_mode = True

class SectionWithLot(SectionRead):
    lot: Optional[LotInfo] = None
    
    class Config:
        orm_mode = True

class SectionWithHierarchy(SectionWithLot):
    dpgf: Optional[DPGFInfo] = None
    elements_count: int = 0
    
    class Config:
        orm_mode = True

class SectionTree(SectionRead):
    children: List["SectionTree"] = []
    
    class Config:
        orm_mode = True
