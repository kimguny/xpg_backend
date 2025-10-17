# SQLAlchemy 모델들을 한 곳에서 임포트
from app.models.base import Base, BaseModel, BaseModelWithoutTimestamp

# 사용자 관련 모델
from app.models.user import User
from app.models.auth_identity import AuthIdentity
from app.models.admin import Admin

# 콘텐츠 관련 모델
from app.models.content import Content, ContentPrerequisite

# 스테이지 관련 모델
from app.models.stage import (
    Stage,
    StageHint,
    HintImage,
    StagePuzzle,
    StageUnlock
)

# NFC 관련 모델
from app.models.nfc_tag import NFCTag, NFCScanLog

# 진행 상황 및 보상 모델
from app.models.progress import (
    UserContentProgress,
    UserStageProgress,
    RewardLedger
)

# 매장 및 리워드 모델
from app.models.store import Store
from app.models.reward import StoreReward

# 모든 모델을 리스트로 정리 (Alembic 등에서 사용)
__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "BaseModelWithoutTimestamp",

    # User models
    "User",
    "AuthIdentity",
    "Admin",

    # Content models
    "Content",
    "ContentPrerequisite",

    # Stage models
    "Stage",
    "StageHint",
    "HintImage",
    "StagePuzzle",
    "StageUnlock",

    # NFC models
    "NFCTag",
    "NFCScanLog",

    # Progress models
    "UserContentProgress",
    "UserStageProgress",
    "RewardLedger",

    # Store and Reward models
    "Store",
    "StoreReward",
]