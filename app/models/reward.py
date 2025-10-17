from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class Reward(Base):
    """리워드 상품 모델 (rewards 테이블)"""
    __tablename__ = "rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    points_required = Column(Integer, nullable=False, default=0)
    total_quantity = Column(Integer, nullable=False, default=0)
    remaining_quantity = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    # 관계 설정
    store = relationship("Store", back_populates="rewards")

    def __repr__(self):
        return f"<Reward(id={self.id}, name='{self.name}')>"

class UserReward(Base):
    """사용자 보유 리워드 모델 (user_rewards 테이블)"""
    __tablename__ = "user_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reward_id = Column(UUID(as_uuid=True), ForeignKey("rewards.id", ondelete="CASCADE"), nullable=False)
    acquired_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

    # 관계 설정
    user = relationship("User")
    reward = relationship("Reward")