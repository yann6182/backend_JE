from pydantic import BaseModel

class ClientBase(BaseModel):
    nom_client: str

class ClientCreate(ClientBase):
    pass

class ClientRead(ClientBase):
    id_client: int

    class Config:
        orm_mode = True
