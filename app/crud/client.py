from sqlalchemy.orm import Session
from app.db.models import Client
from app.schemas.client import ClientCreate


def get_client(db: Session, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id_client == client_id).first()


def get_clients(db: Session, skip: int = 0, limit: int = 100) -> list[Client]:
    return db.query(Client).offset(skip).limit(limit).all()


def create_client(db: Session, client: ClientCreate) -> Client:
    db_client = Client(nom_client=client.nom_client)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


def delete_client(db: Session, client_id: int) -> None:
    db.query(Client).filter(Client.id_client == client_id).delete()
    db.commit()
