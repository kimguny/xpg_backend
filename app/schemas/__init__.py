# 공통 스키마
from app.schemas.common import (
    PaginatedResponse,
    ErrorResponse, 
    SuccessResponse,
    CoordinateSchema,
    GeographySchema,
    ImageSchema,
    RewardSchema,
    MetaSchema,
    IDempotencyResponse
)

# 사용자 스키마
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserUpdateRequest,
    UserResponse,
    UserSummary,
    AuthIdentityResponse,
    UserDetailResponse,
    PasswordChangeRequest,
    UserStatsResponse
)

# --- 새로 추가된 Store 및 Reward 스키마 import ---
from app.schemas.store import (
    StoreBase,
    StoreCreate,
    StoreUpdate,
    StoreResponse
)
from app.schemas.reward import (
    StoreRewardBase,
    StoreRewardCreate,
    StoreRewardUpdate,
    StoreRewardResponse
)


__all__ = [
    # Common schemas
    "PaginatedResponse",
    "ErrorResponse", 
    "SuccessResponse",
    "CoordinateSchema",
    "GeographySchema",
    "ImageSchema",
    "RewardSchema",
    "MetaSchema",
    "IDempotencyResponse",
    
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate", 
    "UserUpdateRequest",
    "UserResponse",
    "UserSummary",
    "AuthIdentityResponse",
    "UserDetailResponse",
    "PasswordChangeRequest",
    "UserStatsResponse",

    # --- 새로 추가된 Store 및 Reward 스키마를 __all__에 등록 ---
    "StoreBase",
    "StoreCreate",
    "StoreUpdate",
    "StoreResponse",
    "StoreRewardBase",
    "StoreRewardCreate",
    "StoreRewardUpdate",
    "StoreRewardResponse",
]