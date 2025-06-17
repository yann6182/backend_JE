from datetime import date
from typing import List
from pydantic import BaseModel
from app.db.models.dpgf import StatutOffre

class DPGFBase(BaseModel):
    id_client: int
    nom_projet: str
    date_dpgf: date
    statut_offre: StatutOffre
    fichier_source: str

class DPGFCreate(DPGFBase):
    pass

class DPGFRead(DPGFBase):
    id_dpgf: int

    class Config:
        orm_mode = True

class ElementOuvrageStructure(BaseModel):
    id_element: int
    designation_exacte: str
    unite: str
    quantite: float
    prix_unitaire_ht: float
    prix_total_ht: float
    offre_acceptee: bool

class SectionStructure(BaseModel):
    id_section: int
    numero_section: str
    titre_section: str
    niveau_hierarchique: int
    elements: List[ElementOuvrageStructure]

class LotStructure(BaseModel):
    id_lot: int
    numero_lot: str
    nom_lot: str
    sections: List[SectionStructure]

class DPGFStructure(BaseModel):
    id_dpgf: int
    nom_projet: str
    date_dpgf: date
    statut_offre: StatutOffre
    lots: List[LotStructure]
