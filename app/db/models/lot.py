from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Lot(Base):
    __tablename__ = 'lots'

    id_lot: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_dpgf: Mapped[int] = mapped_column(ForeignKey('dpgf.id_dpgf'))
    numero_lot: Mapped[str] = mapped_column(String(50), nullable=False)
    nom_lot: Mapped[str] = mapped_column(String(255), nullable=False)

    dpgf: Mapped['DPGF'] = relationship('DPGF', back_populates='lots')
    sections: Mapped[list['Section']] = relationship('Section', back_populates='lot')
