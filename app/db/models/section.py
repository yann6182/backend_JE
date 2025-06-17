from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Section(Base):
    __tablename__ = 'sections'

    id_section: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_lot: Mapped[int] = mapped_column(ForeignKey('lots.id_lot'))
    section_parent_id: Mapped[int | None] = mapped_column(ForeignKey('sections.id_section'), nullable=True)
    numero_section: Mapped[str] = mapped_column(String(50), nullable=False)
    titre_section: Mapped[str] = mapped_column(String(255), nullable=False)
    niveau_hierarchique: Mapped[int] = mapped_column(Integer, nullable=False)

    lot: Mapped['Lot'] = relationship('Lot', back_populates='sections')
    parent: Mapped['Section | None'] = relationship('Section', remote_side=[id_section])
    elements: Mapped[list['ElementOuvrage']] = relationship('ElementOuvrage', back_populates='section')
