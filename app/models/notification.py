from sqlalchemy import Column, String, Boolean, Integer, DateTime, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base
import uuid


class Notification(Base):
    """공지사항 모델 (notifications 테이블)"""
    
    __tablename__ = "notifications"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 기본 정보
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    notification_type = Column(String(20), nullable=False)
    
    # 게시 기간
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    
    # 상태 관리
    status = Column(String(20), nullable=False, default='draft', server_default='draft')
    
    # 추가 옵션
    show_popup_on_app_start = Column(Boolean, nullable=False, default=False, server_default='false')
    
    # 조회수
    view_count = Column(Integer, nullable=False, default=0, server_default='0')
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 제약조건
    __table_args__ = (
        CheckConstraint(
            "end_at > start_at",
            name="check_date_range"
        ),
        CheckConstraint(
            "notification_type IN ('system', 'event', 'promotion')",
            name="check_notification_type"
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'expired')",
            name="check_status"
        ),
        CheckConstraint(
            "char_length(content) <= 500",
            name="check_content_length"
        ),
    )
    
    def __repr__(self):
        return f"<Notification(id={self.id}, title='{self.title}', type='{self.notification_type}', status='{self.status}')>"
    
    @property
    def is_system(self) -> bool:
        return self.notification_type == 'system'
    
    @property
    def is_event(self) -> bool:
        return self.notification_type == 'event'
    
    @property
    def is_promotion(self) -> bool:
        return self.notification_type == 'promotion'
    
    @property
    def is_draft(self) -> bool:
        return self.status == 'draft'
    
    @property
    def is_published(self) -> bool:
        return self.status == 'published'