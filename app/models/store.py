from sqlalchemy import Column, String, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from app.models.base import Base
import uuid

class Store(Base):
    """매장 모델 (stores 테이블)"""
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    location = Column(Geography('POINT', srid=4326), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # 관계 설정
    rewards = relationship("Reward", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(id={self.id}, name='{self.name}')>"