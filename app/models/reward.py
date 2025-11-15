from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class StoreReward(Base):
    __tablename__ = "store_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(Text, nullable=False)
    product_desc = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    
    qr_image_url = Column(Text, nullable=True) 
    
    price_coin = Column(Integer, nullable=False, default=0)
    initial_quantity = Column(Integer, nullable=True, comment="초기 입고 수량 (총 수량)")
    stock_qty = Column(Integer, nullable=True, comment="현재 남은 재고 (잔여 수량)")
    is_active = Column(Boolean, nullable=False, default=True)
    exposure_order = Column(Integer, nullable=True)
    category = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    store = relationship("Store", back_populates="rewards")

    def __repr__(self):
        return f"<StoreReward(id={self.id}, name='{self.product_name}')>"