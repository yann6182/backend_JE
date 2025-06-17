from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.crud import client as crud
from app.schemas.client import ClientCreate, ClientRead
from app.api.deps import get_db

router = APIRouter(prefix='/clients', tags=['clients'])

@router.post('/', response_model=ClientRead)
def create_client(client_in: ClientCreate, db: Session = Depends(get_db)):
    return crud.create_client(db, client_in)

@router.get('/', response_model=list[ClientRead])
def read_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_clients(db, skip, limit)

@router.get('/{client_id}', response_model=ClientRead)
def read_client(client_id: int, db: Session = Depends(get_db)):
    db_client = crud.get_client(db, client_id)
    if not db_client:
        raise HTTPException(status_code=404, detail='Client not found')
    return db_client

@router.delete('/{client_id}', status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    crud.delete_client(db, client_id)
    return None
