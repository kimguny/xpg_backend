from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class StoreReward(Base):
    """리워드 상품 모델 (store_rewards 테이블)"""
    __tablename__ = "store_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(Text, nullable=False)
    product_desc = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    
    # QR 코드 URL 저장 컬럼
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