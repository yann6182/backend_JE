from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.crud import lot as crud
from app.schemas.lot import LotCreate, LotRead
from app.api.deps import get_db

router = APIRouter(prefix='/lots', tags=['lots'])

@router.post('/', response_model=LotRead)
def create_lot(lot_in: LotCreate, db: Session = Depends(get_db)):
    return crud.create_lot(db, lot_in)

@router.get('/', response_model=list[LotRead])
def read_lots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_lots(db, skip, limit)

@router.get('/{lot_id}', response_model=LotRead)
def read_lot(lot_id: int, db: Session = Depends(get_db)):
    obj = crud.get_lot(db, lot_id)
    if not obj:
        raise HTTPException(status_code=404, detail='Lot not found')
    return obj

@router.delete('/{lot_id}', status_code=204)
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    crud.delete_lot(db, lot_id)
    return None
