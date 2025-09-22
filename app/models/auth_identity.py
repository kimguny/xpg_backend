from sqlalchemy import Column, String, DateTime, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid


class AuthIdentity(Base):
    """인증 아이덴티티 모델 (DB 문서의 auth_identities 테이블)"""
    
    __tablename__ = "auth_identities"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 사용자 연결
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 인증 제공자 (local|google|apple|kakao|naver|facebook|github|line)
    provider = Column(Text, nullable=False)
    
    # 제공자별 사용자 식별자 (local: login_id, SNS: subject/uid)
    provider_user_id = Column(Text, nullable=False)
    
    # 로컬 인증용 비밀번호 (provider='local'에서만 사용)
    password_hash = Column(Text, nullable=True)
    
    # 비밀번호 알고리즘 (bcrypt|argon2id)
    password_algo = Column(Text, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # SNS 프로필 스냅샷 등 메타데이터
    meta = Column(JSONB, nullable=True)
    
    # 제약조건
    __table_args__ = (
        # 제공자 검증
        CheckConstraint(
            "provider IN ('local', 'google', 'apple', 'kakao', 'naver', 'facebook', 'github', 'line')",
            name="auth_identities_provider_chk"
        ),
    )
    
    # 관계 설정
    user = relationship("User", back_populates="auth_identities")
    
    def __repr__(self):
        return f"<AuthIdentity(id={self.id}, provider='{self.provider}', user_id={self.user_id})>"
    
    @property
    def is_local(self) -> bool:
        """로컬 인증인지 확인"""
        return self.provider == 'local'
    
    @property
    def is_social(self) -> bool:
        """소셜 로그인인지 확인"""
        return self.provider != 'local'
    
    def update_last_login(self):
        """최근 로그인 시각 업데이트"""
        self.last_login_at = func.now()