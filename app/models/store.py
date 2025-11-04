from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

# geoalchemy2 import는 Store 모델에서 사용하므로 아래로 이동
from sqlalchemy import Float
from geoalchemy2 import Geography

class StoreReward(Base):
    """리워드 상품 모델 (store_rewards 테이블)"""
    __tablename__ = "store_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(Text, nullable=False)
    product_desc = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    qr_image_url = Column(Text, nullable=True)
    price_coin = Column(Integer, nullable=False, default=0)
    stock_qty = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    exposure_order = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    store = relationship("Store", back_populates="rewards")

    def __repr__(self):
        return f"<StoreReward(id={self.id}, name='{self.product_name}')>"

class Store(Base):
    """매장 모델 (stores 테이블)"""
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(Geography('POINT', srid=4326), nullable=True)
    display_start_at = Column(DateTime(timezone=True), nullable=True)
    display_end_at = Column(DateTime(timezone=True), nullable=True)
    is_always_on = Column(Boolean, nullable=False, default=False)
    map_image_url = Column(Text, nullable=True)
    show_products = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    rewards = relationship("StoreReward", back_populates="store", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(id={self.id}, name='{self.store_name}')>"