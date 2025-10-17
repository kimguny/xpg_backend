from sqlalchemy import Column, String, Boolean, Integer, DateTime, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.models.base import Base
import uuid


class Content(Base):
    """콘텐츠 모델 (DB 문서의 contents 테이블)"""
    
    __tablename__ = "contents"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 기본 정보
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # 콘텐츠 유형 (story|domination)
    content_type = Column(Text, nullable=False)

    # <<<<<<<<<<<<<<<<<<< 수정된 부분 1 >>>>>>>>>>>>>>>>>>>>
    # 노출 위치 (main|event_tab 등)
    exposure_type = Column(Text, nullable=False, default='main', server_default='main')
    # <<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>
    
    # 기간 설정
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    is_always_on = Column(Boolean, nullable=False, default=False)
    
    # 스테이지 관련
    stage_count = Column(Integer, nullable=True)  # 표시용, 1~10
    is_sequential = Column(Boolean, nullable=False, default=True)  # 순차 진행 여부
    
    # 보상
    reward_coin = Column(Integer, nullable=False, default=0)
    
    # 지도 중심 좌표
    center_point = Column(Geography('POINT', srid=4326), nullable=True)
    
    # 후속 콘텐츠 연결
    has_next_content = Column(Boolean, nullable=False, default=False)
    next_content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    
    # 오픈 여부
    is_open = Column(Boolean, nullable=False, default=True)
    
    # 관리자 정보
    created_by = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 제약조건
    __table_args__ = (
        # 콘텐츠 유형 검증
        CheckConstraint(
            "content_type IN ('story', 'domination')",
            name="contents_content_type_chk"
        ),
        CheckConstraint(
            "exposure_type IN ('main', 'event_tab')",
            name="contents_exposure_type_chk"
        ),
        # 스테이지 수 범위 검증
        CheckConstraint(
            "stage_count IS NULL OR (stage_count >= 1 AND stage_count <= 10)",
            name="contents_stage_count_range_chk"
        ),
        # 후속 콘텐츠 일관성 검증
        CheckConstraint(
            "(has_next_content = FALSE AND next_content_id IS NULL) OR (has_next_content = TRUE AND next_content_id IS NOT NULL)",
            name="contents_next_consistency_chk"
        ),
        # 자기 참조 방지
        CheckConstraint(
            "next_content_id IS NULL OR next_content_id != id",
            name="contents_next_not_self_chk"
        ),
    )
    
    # 관계 설정
    created_by_admin = relationship("Admin", back_populates="created_contents")
    next_content = relationship("Content", remote_side=[id])
    stages = relationship("Stage", back_populates="content", cascade="all, delete-orphan")
    prerequisites_as_content = relationship(
        "ContentPrerequisite", 
        foreign_keys="ContentPrerequisite.content_id",
        back_populates="content"
    )
    prerequisites_as_required = relationship(
        "ContentPrerequisite", 
        foreign_keys="ContentPrerequisite.required_content_id",
        back_populates="required_content"
    )
    user_progress = relationship("UserContentProgress", back_populates="content", cascade="all, delete-orphan")
    rewards = relationship("RewardLedger", back_populates="content")
    
    def __repr__(self):
        return f"<Content(id={self.id}, title='{self.title}', type='{self.content_type}')>"
    
    @property
    def is_story(self) -> bool:
        """스토리 콘텐츠인지 확인"""
        return self.content_type == 'story'
    
    @property
    def is_domination(self) -> bool:
        """점령전 콘텐츠인지 확인"""
        return self.content_type == 'domination'
    
    @property
    def has_stages(self) -> bool:
        """스테이지가 있는지 확인"""
        return self.stage_count is not None and self.stage_count > 0


class ContentPrerequisite(Base):
    """콘텐츠 선행조건 모델 (DB 문서의 content_prerequisites 테이블)"""
    
    __tablename__ = "content_prerequisites"
    
    # 복합 기본키
    content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    required_content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="RESTRICT"), primary_key=True)
    
    # 요구사항 (현재는 'cleared'만 지원)
    requirement = Column(Text, nullable=False, default='cleared')
    
    # 제약조건
    __table_args__ = (
        # 요구사항 유형 검증
        CheckConstraint(
            "requirement IN ('cleared')",
            name="content_prerequisites_requirement_chk"
        ),
        # 자기 참조 방지
        CheckConstraint(
            "content_id != required_content_id",
            name="content_prerequisites_not_self_chk"
        ),
    )
    
    # 관계 설정
    content = relationship("Content", foreign_keys=[content_id], back_populates="prerequisites_as_content")
    required_content = relationship("Content", foreign_keys=[required_content_id], back_populates="prerequisites_as_required")
    
    def __repr__(self):
        return f"<ContentPrerequisite(content_id={self.content_id}, required_content_id={self.required_content_id})>"