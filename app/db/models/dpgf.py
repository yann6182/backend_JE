from datetime import date
from sqlalchemy import Integer, String, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.client import Client
from enum import Enum as PyEnum

class StatutOffre(PyEnum):
    en_cours = 'en_cours'
    acceptee = 'acceptee'
    refusee = 'refusee'

class DPGF(Base):
    __tablename__ = 'dpgf'

    id_dpgf: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_client: Mapped[int] = mapped_column(ForeignKey('clients.id_client'))
    nom_projet: Mapped[str] = mapped_column(String(255), nullable=False)
    date_dpgf: Mapped[date] = mapped_column(Date, nullable=False)
    statut_offre: Mapped[StatutOffre] = mapped_column(Enum(StatutOffre), nullable=False)
    fichier_source: Mapped[str] = mapped_column(String(255), nullable=False)

    client: Mapped[Client] = relationship('Client', back_populates='dpgfs')
    lots: Mapped[list['Lot']] = relationship('Lot', back_populates='dpgf')
