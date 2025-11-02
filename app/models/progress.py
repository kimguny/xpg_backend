from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class UserContentProgress(Base):
    """사용자 콘텐츠 진행 상황 모델 (DB 문서의 user_content_progress 테이블)"""
    
    __tablename__ = "user_content_progress"
    
    # 복합 기본키
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True)
    
    # 진행 상태 (joined|in_progress|cleared|left)
    status = Column(Text, nullable=False)
    
    # 시간 정보
    joined_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    total_play_minutes = Column(Integer, nullable=True)
    
    # 마지막 진행 스테이지
    last_stage_no = Column(Text, nullable=True)
    
    # 관계 설정
    user = relationship("User", back_populates="content_progress")
    content = relationship("Content", back_populates="user_progress")
    
    def __repr__(self):
        return f"<UserContentProgress(user_id={self.user_id}, content_id={self.content_id}, status='{self.status}')>"
    
    @property
    def is_joined(self) -> bool:
        """참여한 상태인지 확인"""
        return self.status == 'joined'
    
    @property
    def is_in_progress(self) -> bool:
        """진행 중인지 확인"""
        return self.status == 'in_progress'
    
    @property
    def is_cleared(self) -> bool:
        """클리어했는지 확인"""
        return self.status == 'cleared'
    
    @property
    def is_left(self) -> bool:
        """중도 포기했는지 확인"""
        return self.status == 'left'
    
    @property
    def play_time_hours(self) -> float:
        """플레이 시간을 시간 단위로 반환"""
        if self.total_play_minutes:
            return self.total_play_minutes / 60.0
        return 0.0


class UserStageProgress(Base):
    """사용자 스테이지 진행 상황 모델 (DB 문서의 user_stage_progress 테이블)"""
    
    __tablename__ = "user_stage_progress"
    
    # 복합 기본키
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), primary_key=True)
    
    # 진행 상태 (locked|unlocked|in_progress|cleared)
    status = Column(Text, nullable=False)
    
    # 시간 정보
    unlock_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    
    # 진행 통계
    nfc_count = Column(Integer, nullable=False, default=0)  # 태그한 NFC 수
    best_time_sec = Column(Integer, nullable=True)         # 최단 클리어 시간
    
    # 관계 설정
    user = relationship("User", back_populates="stage_progress")
    stage = relationship("Stage", back_populates="user_progress")
    
    def __repr__(self):
        return f"<UserStageProgress(user_id={self.user_id}, stage_id={self.stage_id}, status='{self.status}')>"
    
    @property
    def is_locked(self) -> bool:
        """잠겨있는지 확인"""
        return self.status == 'locked'
    
    @property
    def is_unlocked(self) -> bool:
        """해금되었는지 확인"""
        return self.status == 'unlocked'
    
    @property
    def is_in_progress(self) -> bool:
        """진행 중인지 확인"""
        return self.status == 'in_progress'
    
    @property
    def is_cleared(self) -> bool:
        """클리어했는지 확인"""
        return self.status == 'cleared'
    
    @property
    def best_time_minutes(self) -> float:
        """최단 시간을 분 단위로 반환"""
        if self.best_time_sec:
            return self.best_time_sec / 60.0
        return 0.0
    
    @property
    def completion_percentage(self) -> float:
        """NFC 태깅 완료율 계산 (스테이지의 필요 NFC 수 기준)"""
        # 실제로는 stage.clear_need_nfc_count와 비교해야 함
        # 여기서는 기본 로직만 제공
        if self.nfc_count > 0:
            return min(100.0, (self.nfc_count / max(1, self.nfc_count)) * 100)
        return 0.0


class RewardLedger(Base):
    """보상 원장 모델 (DB 문서의 rewards_ledger 테이블)"""
    
    __tablename__ = "rewards_ledger"
    
    # 기본키 (bigserial)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 사용자
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 관련 콘텐츠/스테이지 (삭제 시 NULL로 설정)
    content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="SET NULL"), nullable=True)
    
    # 보상 정보
    coin_delta = Column(Integer, nullable=False)  # 증감량 (음수 가능)
    note = Column(Text, nullable=True)           # 보상 사유 메모
    
    # 기록 시각
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="rewards")
    content = relationship("Content", back_populates="rewards")
    stage = relationship("Stage", back_populates="rewards")

    store = relationship("Store")
    reward = relationship("StoreReward")
    
    def __repr__(self):
        return f"<RewardLedger(id={self.id}, user_id={self.user_id}, coin_delta={self.coin_delta})>"
    
    @property
    def is_earning(self) -> bool:
        """코인 획득인지 확인"""
        return self.coin_delta > 0
    
    @property
    def is_spending(self) -> bool:
        """코인 사용인지 확인"""
        return self.coin_delta < 0
    
    @property
    def reward_type(self) -> str:
        """보상 유형 반환"""
        if self.stage_id:
            return "stage_reward"
        elif self.content_id:
            return "content_reward"
        else:
            return "system_reward"
    
    @property
    def abs_amount(self) -> int:
        """절댓값 반환"""
        return abs(self.coin_delta)