from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid


class Admin(Base):
    """관리자 계정 모델 (DB 문서의 admins 테이블)"""
    
    __tablename__ = "admins"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 연결된 사용자 (users 중 권한 부여)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True)
    
    # 관리자 역할
    role = Column(Text, nullable=False, default='admin')
    
    # 권한 부여 시각
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="admin")
    created_contents = relationship("Content", back_populates="created_by_admin")
    
    def __repr__(self):
        return f"<Admin(id={self.id}, user_id={self.user_id}, role='{self.role}')>"
    
    @property
    def is_super_admin(self) -> bool:
        """슈퍼 관리자 권한 확인"""
        return self.role == 'super_admin'
    
    @property
    def can_manage_users(self) -> bool:
        """사용자 관리 권한 확인"""
        return self.role in ['admin', 'super_admin']
    
    @property
    def can_manage_contents(self) -> bool:
        """콘텐츠 관리 권한 확인"""
        return self.role in ['admin', 'super_admin']