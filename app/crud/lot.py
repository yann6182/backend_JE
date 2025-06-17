from sqlalchemy.orm import Session
from app.db.models import Lot
from app.schemas.lot import LotCreate


def get_lot(db: Session, lot_id: int) -> Lot | None:
    return db.query(Lot).filter(Lot.id_lot == lot_id).first()


def get_lots(db: Session, skip: int = 0, limit: int = 100) -> list[Lot]:
    return db.query(Lot).offset(skip).limit(limit).all()


def create_lot(db: Session, lot: LotCreate) -> Lot:
    db_lot = Lot(**lot.dict())
    db.add(db_lot)
    db.commit()
    db.refresh(db_lot)
    return db_lot


def delete_lot(db: Session, lot_id: int) -> None:
    db.query(Lot).filter(Lot.id_lot == lot_id).delete()
    db.commit()
