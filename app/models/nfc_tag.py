from sqlalchemy import Column, String, Boolean, Integer, DateTime, CheckConstraint, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, DOUBLE_PRECISION
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.models.base import Base
import uuid


class NFCTag(Base):
    """NFC 태그 모델 (DB 문서의 nfc_tags 테이블)"""
    
    __tablename__ = "nfc_tags"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 고유 식별자
    udid = Column(Text, nullable=False, unique=True)
    
    # 태그 정보
    tag_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    floor_location = Column(Text, nullable=True)
    
    # 미디어 링크
    media_url = Column(Text, nullable=True)
    link_url = Column(Text, nullable=True)
    
    # 위치 정보
    latitude = Column(DOUBLE_PRECISION, nullable=True)
    longitude = Column(DOUBLE_PRECISION, nullable=True)
    geom = Column(Geography('POINT', srid=4326), nullable=True)
    
    # 태깅 설정
    tap_message = Column(Text, nullable=True)
    point_reward = Column(Integer, nullable=False, default=0)
    cooldown_sec = Column(Integer, nullable=False, default=0)
    use_limit = Column(Integer, nullable=True)
    
    # 활성화 및 분류
    is_active = Column(Boolean, nullable=False, default=True)
    category = Column(Text, nullable=True)
    
    # 제약조건
    __table_args__ = (
        CheckConstraint(
            "category IS NULL OR category IN ('none', 'stage', 'hint', 'checkpoint', 'base', 'safezone', 'treasure')",
            name="nfc_tags_category_chk"
        ),
    )
    
    # 관계 설정
    hints = relationship("StageHint", back_populates="nfc")
    scan_logs = relationship("NFCScanLog", back_populates="nfc")
    
    def __repr__(self):
        return f"<NFCTag(id={self.id}, udid='{self.udid}', tag_name='{self.tag_name}')>"
    
    @property
    def has_coordinates(self) -> bool:
        """좌표 정보가 있는지 확인"""
        return self.latitude is not None and self.longitude is not None
    
    @property
    def has_cooldown(self) -> bool:
        """쿨다운이 설정되어 있는지 확인"""
        return self.cooldown_sec > 0
    
    @property
    def has_use_limit(self) -> bool:
        """사용 제한이 있는지 확인"""
        return self.use_limit is not None and self.use_limit > 0
    
    @property
    def is_hint_tag(self) -> bool:
        """힌트용 태그인지 확인"""
        return self.category == 'hint'


class NFCScanLog(Base):
    """NFC 스캔 로그 모델 (DB 문서의 nfc_scan_logs 테이블)"""
    
    __tablename__ = "nfc_scan_logs"
    
    # 기본키 (bigserial)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 사용자 (삭제 시 NULL로 설정)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # NFC 태그 (삭제 시 NULL로 설정)
    nfc_id = Column(UUID(as_uuid=True), ForeignKey("nfc_tags.id", ondelete="SET NULL"), nullable=True)
    
    # 스캔 시각
    scanned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # 허용 여부 및 사유
    allowed = Column(Boolean, nullable=False, default=True)
    reason = Column(Text, nullable=True)
    
    # 관련 힌트 (삭제 시 NULL로 설정, 트리거로 자동 보정)
    hint_id = Column(UUID(as_uuid=True), ForeignKey("stage_hints.id", ondelete="SET NULL"), nullable=True)
    
    # 관계 설정
    user = relationship("User", back_populates="nfc_scan_logs")
    nfc = relationship("NFCTag", back_populates="scan_logs")
    hint = relationship("StageHint", back_populates="scan_logs")
    
    def __repr__(self):
        return f"<NFCScanLog(id={self.id}, user_id={self.user_id}, nfc_id={self.nfc_id}, allowed={self.allowed})>"
    
    @property
    def is_successful_scan(self) -> bool:
        """성공적인 스캔인지 확인"""
        return self.allowed
    
    @property
    def has_hint(self) -> bool:
        """힌트와 연결된 스캔인지 확인"""
        return self.hint_id is not None
    
    @property
    def denial_reason(self) -> str:
        """거부 사유 (허용되지 않은 경우)"""
        return self.reason if not self.allowed else None