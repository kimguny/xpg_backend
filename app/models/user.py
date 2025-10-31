from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid


class User(Base):
    """사용자 계정 모델 (DB 문서의 users 테이블)"""
    
    __tablename__ = "users"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 로그인 ID (citext, 대소문자 무시, 3~30자, [A-Za-z0-9._-])
    login_id = Column(String, nullable=False, unique=True)
    
    # 이메일 (NULL 허용, 부분 유니크)
    email = Column(String, nullable=True)
    
    # 표시명
    nickname = Column(Text, nullable=True)
    
    # 이메일 인증 관련
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # 계정 상태
    status = Column(String, nullable=False, default='active')
    
    # 프로필 (자유 확장)
    profile = Column(JSONB, nullable=True)

    # 프로필 이미지 URL
    profile_image_url = Column(Text, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # 제약조건
    __table_args__ = (
        CheckConstraint(
            "length(login_id) >= 3 AND length(login_id) <= 30 AND login_id ~ '^[A-Za-z0-9._-]+$'",
            name="users_login_id_format_chk"
        ),
        CheckConstraint(
            "status IN ('active', 'blocked', 'deleted')",
            name="users_status_chk"
        ),
    )
    
    # 관계 설정
    auth_identities = relationship("AuthIdentity", back_populates="user", cascade="all, delete-orphan")
    admin = relationship("Admin", back_populates="user", uselist=False)
    content_progress = relationship("UserContentProgress", back_populates="user", cascade="all, delete-orphan")
    stage_progress = relationship("UserStageProgress", back_populates="user", cascade="all, delete-orphan")
    rewards = relationship("RewardLedger", back_populates="user", cascade="all, delete-orphan")
    nfc_scan_logs = relationship("NFCScanLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, login_id='{self.login_id}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """계정이 활성 상태인지 확인"""
        return self.status == 'active'
    
    @property
    def is_blocked(self) -> bool:
        """계정이 차단 상태인지 확인"""
        return self.status == 'blocked'
    
    @property
    def is_deleted(self) -> bool:
        """계정이 삭제 상태인지 확인"""
        return self.status == 'deleted'
    
    @property
    def display_name(self) -> str:
        """표시할 이름 (닉네임이 있으면 닉네임, 없으면 로그인 ID)"""
        return self.nickname or self.login_id