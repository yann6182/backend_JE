from sqlalchemy import Integer, String, DECIMAL, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ElementOuvrage(Base):
    __tablename__ = 'elements_ouvrage'

    id_element: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_section: Mapped[int] = mapped_column(ForeignKey('sections.id_section'))
    designation_exacte: Mapped[str] = mapped_column(String(255), nullable=False)
    unite: Mapped[str] = mapped_column(String(10), nullable=False)
    quantite: Mapped[float] = mapped_column(DECIMAL(12,3), nullable=False)
    prix_unitaire_ht: Mapped[float] = mapped_column(DECIMAL(15,2), nullable=False)
    prix_total_ht: Mapped[float] = mapped_column(DECIMAL(18,2), nullable=False)
    offre_acceptee: Mapped[bool] = mapped_column(Boolean, default=False)

    section: Mapped['Section'] = relationship('Section', back_populates='elements')
