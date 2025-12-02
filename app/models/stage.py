from sqlalchemy import Column, String, Boolean, Integer, DateTime, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.models.base import Base
import uuid


class Stage(Base):
    """스테이지 모델 (DB 문서의 stages 테이블)"""
    
    __tablename__ = "stages"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 소속 콘텐츠
    content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    
    # 부모 스테이지 (서브 스테이지용)
    parent_stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=True)
    
    # 스테이지 번호 (문자열, 콘텐츠 내에서 유니크)
    stage_no = Column(Text, nullable=False)
    
    # 기본 정보
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    start_button_text = Column(Text, nullable=True)
    
    # 기능 설정
    uses_nfc = Column(Boolean, nullable=False, default=False)  # 자동 동기화됨
    is_hidden = Column(Boolean, nullable=False, default=False)
    is_open = Column(Boolean, nullable=False, default=True)
    
    # 제한 시간
    time_limit_min = Column(Integer, nullable=True)
    
    # 클리어 조건
    clear_need_nfc_count = Column(Integer, nullable=True)
    clear_time_attack_sec = Column(Integer, nullable=True)
    
    # 위치 정보
    location = Column(Geography('POINT', srid=4326), nullable=True)
    radius_m = Column(Integer, nullable=True)
    unlock_on_enter_radius = Column(Boolean, nullable=False, default=False)
    
    # 히든 스테이지 해금 조건
    unlock_stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="RESTRICT"), nullable=True)
    
    # 이미지
    background_image_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    
    # 메타데이터
    meta = Column(JSONB, nullable=True)
    
    # 생성 시각
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # 제약조건
    __table_args__ = (
        # 콘텐츠 내 스테이지 번호 유니크
        UniqueConstraint("content_id", "stage_no", name="stages_content_id_stage_no_key"),
        # 히든 스테이지는 unlock_stage_id 필수
        CheckConstraint(
            "(is_hidden = TRUE AND unlock_stage_id IS NOT NULL) OR (is_hidden = FALSE AND unlock_stage_id IS NULL)",
            name="stages_hidden_unlock_consistency_chk"
        ),
        # 자기 참조 방지
        CheckConstraint(
            "unlock_stage_id IS NULL OR unlock_stage_id != id",
            name="stages_unlock_not_self_chk"
        ),
    )
    
    # 관계 설정
    content = relationship("Content", back_populates="stages")
    parent_stage = relationship("Stage", remote_side=[id], back_populates="sub_stages", foreign_keys=[parent_stage_id])
    sub_stages = relationship("Stage", back_populates="parent_stage", foreign_keys=[parent_stage_id])
    unlock_stage = relationship("Stage", remote_side=[id], foreign_keys=[unlock_stage_id])
    hints = relationship("StageHint", back_populates="stage", cascade="all, delete-orphan")
    puzzles = relationship("StagePuzzle", back_populates="stage", cascade="all, delete-orphan")
    unlocks = relationship("StageUnlock", back_populates="stage", cascade="all, delete-orphan")
    user_progress = relationship("UserStageProgress", back_populates="stage", cascade="all, delete-orphan")
    rewards = relationship("RewardLedger", back_populates="stage")
    
    def __repr__(self):
        return f"<Stage(id={self.id}, stage_no='{self.stage_no}', title='{self.title}')>"
    
    @property
    def is_main_stage(self) -> bool:
        """메인 스테이지인지 확인"""
        return self.parent_stage_id is None
    
    @property
    def is_sub_stage(self) -> bool:
        """서브 스테이지인지 확인"""
        return self.parent_stage_id is not None


class StageHint(Base):
    """스테이지 힌트 모델 (DB 문서의 stage_hints 테이블)"""
    
    __tablename__ = "stage_hints"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 소속 스테이지
    stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=False)
    
    # 표시 설정
    preset = Column(Text, nullable=False)
    order_no = Column(Integer, nullable=False)
    
    # 텍스트 블록들
    text_block_1 = Column(Text, nullable=True)
    text_block_2 = Column(Text, nullable=True)
    text_block_3 = Column(Text, nullable=True)
    
    # 쿨다운 및 보상
    cooldown_sec = Column(Integer, default=0)
    failure_cooldown_sec = Column(Integer, default=0, nullable=True, comment="미션 실패 시 재시도 쿨타임(초)")
    reward_coin = Column(Integer, default=0)
    
    # 연계 NFC 태그
    nfc_id = Column(UUID(as_uuid=True), ForeignKey("nfc_tags.id", ondelete="RESTRICT"), nullable=True)
    
    # 관계 설정
    stage = relationship("Stage", back_populates="hints")
    nfc = relationship("NFCTag", back_populates="hints")
    images = relationship("HintImage", back_populates="hint", cascade="all, delete-orphan")
    scan_logs = relationship("NFCScanLog", back_populates="hint")
    
    def __repr__(self):
        return f"<StageHint(id={self.id}, stage_id={self.stage_id}, order_no={self.order_no})>"


class HintImage(Base):
    """힌트 이미지 모델 (DB 문서의 hint_images 테이블)"""
    
    __tablename__ = "hint_images"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 소속 힌트
    hint_id = Column(UUID(as_uuid=True), ForeignKey("stage_hints.id", ondelete="CASCADE"), nullable=False)
    
    # 표시 순서
    order_no = Column(Integer, nullable=False)
    
    # 이미지 정보
    url = Column(Text, nullable=False)
    alt_text = Column(Text, nullable=True)
    
    # 관계 설정
    hint = relationship("StageHint", back_populates="images")
    
    def __repr__(self):
        return f"<HintImage(id={self.id}, hint_id={self.hint_id}, order_no={self.order_no})>"


class StagePuzzle(Base):
    """스테이지 퍼즐 모델 (DB 문서의 stage_puzzles 테이블)"""
    
    __tablename__ = "stage_puzzles"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 소속 스테이지
    stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=False)
    
    # 퍼즐 설정
    puzzle_style = Column(Text, nullable=False)
    show_when = Column(Text, nullable=False)  # always|after_clear
    config = Column(JSONB, nullable=True)
    
    # 제약조건
    __table_args__ = (
        CheckConstraint(
            "show_when IN ('always', 'after_clear')",
            name="stage_puzzles_show_when_chk"
        ),
    )
    
    # 관계 설정
    stage = relationship("Stage", back_populates="puzzles")
    
    def __repr__(self):
        return f"<StagePuzzle(id={self.id}, stage_id={self.stage_id}, style='{self.puzzle_style}')>"


class StageUnlock(Base):
    """스테이지 클리어 연출 모델 (DB 문서의 stage_unlocks 테이블)"""
    
    __tablename__ = "stage_unlocks"
    
    # 기본키
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    
    # 소속 스테이지
    stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=False)
    
    # 연출 설정
    unlock_preset = Column(Text, nullable=False)  # fullscreen|popup
    next_action = Column(Text, nullable=False)    # next_step|next_stage
    
    # 표시 내용
    title = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    bottom_text = Column(Text, nullable=True)
    
    # 제약조건
    __table_args__ = (
        CheckConstraint(
            "unlock_preset IN ('fullscreen', 'popup')",
            name="stage_unlocks_preset_chk"
        ),
        CheckConstraint(
            "next_action IN ('next_step', 'next_stage')",
            name="stage_unlocks_next_action_chk"
        ),
    )
    
    # 관계 설정
    stage = relationship("Stage", back_populates="unlocks")
    
    def __repr__(self):
        return f"<StageUnlock(id={self.id}, stage_id={self.stage_id}, preset='{self.unlock_preset}')>"