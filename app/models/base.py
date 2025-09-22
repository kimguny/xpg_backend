from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class TimestampMixin:
    """생성/수정 시각 자동 관리 믹스인"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    """UUID 기본키 믹스인"""
    
    @declared_attr
    def id(cls):
        return Column(
            UUID(as_uuid=True), 
            primary_key=True, 
            default=uuid.uuid4,
            server_default=func.uuid_generate_v4()
        )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    모든 모델의 기본 클래스
    - UUID 기본키 자동 생성
    - created_at, updated_at 자동 관리
    """
    __abstract__ = True
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


class BaseModelWithoutTimestamp(Base, UUIDMixin):
    """
    타임스탬프가 필요없는 모델을 위한 베이스 클래스
    (예: 연결 테이블, 로그 테이블 등)
    """
    __abstract__ = True
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"