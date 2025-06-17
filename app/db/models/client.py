from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Client(Base):
    __tablename__ = 'clients'

    id_client: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_client: Mapped[str] = mapped_column(String(255), nullable=False)

    dpgfs: Mapped[list['DPGF']] = relationship('DPGF', back_populates='client')
