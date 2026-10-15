from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# Esta clase es solo el mapeo ORM para consultar/insertar; manten ambos en sintonía.
EMBEDDING_DIM = 512

class KnownFace(Base):
    """Rostro conocido: nombre, foto y su embedding para buscar coincidencias."""

    __tablename__ = "known_face"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    image_filename: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
