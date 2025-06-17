from pydantic import BaseModel

class LotBase(BaseModel):
    id_dpgf: int
    numero_lot: str
    nom_lot: str

class LotCreate(LotBase):
    pass

class LotRead(LotBase):
    id_lot: int

    class Config:
        orm_mode = True
