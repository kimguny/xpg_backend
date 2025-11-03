from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import MetaSchema


class UserBase(BaseModel):
    """사용자 기본 스키마"""
    login_id: str = Field(..., min_length=3, max_length=30, pattern=r'^[A-Za-z0-9._-]+$')
    email: Optional[str] = Field(None, description="연락 이메일")
    nickname: Optional[str] = Field(None, description="표시명")


class UserCreate(UserBase):
    """사용자 생성 스키마"""
    password: str = Field(..., min_length=8, max_length=128, description="비밀번호")


class UserUpdate(BaseModel):
    """사용자 수정 스키마 (일반 사용자용)"""
    nickname: Optional[str] = Field(None, description="닉네임")
    email: Optional[str] = Field(None, description="이메일")
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")
    profile: Optional[Dict[str, Any]] = Field(None, description="프로필 정보")


class UserUpdateRequest(BaseModel):
    """사용자 수정 요청 스키마 (관리자용)"""
    status: Optional[str] = Field(None, description="계정 상태: active|blocked|deleted")
    profile: Optional[Dict[str, Any]] = Field(None, description="프로필 정보")


class UserResponse(BaseModel):
    """사용자 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    login_id: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    status: str
    profile: Optional[Dict[str, Any]] = None
    points: int = 0
    created_at: datetime
    last_active_at: Optional[datetime] = None

    # [추가] SQLAlchemy 모델에서 Pydantic 모델로 변환 시 points 값을 추출하는 로직
    @classmethod
    def model_validate(cls, obj, **kwargs):
        # SQLAlchemy 모델 객체(obj)에서 데이터를 가져옴
        data = super().model_validate(obj, **kwargs).model_dump()
        
        # obj.profile (JSONB 필드)에서 'points' 값을 추출
        if hasattr(obj, 'profile') and isinstance(obj.profile, dict):
            # profile.points가 있다면 사용하고, 없다면 기본값 0 사용
            data['points'] = obj.profile.get('points', 0)
        
        # Pydantic 객체로 재구성하여 반환
        return cls(**data)
    
    @property
    def display_name(self) -> str:
        """표시할 이름"""
        return self.nickname or self.login_id


class UserSummary(BaseModel):
    """사용자 요약 정보"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    login_id: str
    nickname: Optional[str] = None
    status: str
    
    @property
    def display_name(self) -> str:
        return self.nickname or self.login_id


class AuthIdentityResponse(BaseModel):
    """인증 아이덴티티 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    provider: str
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserDetailResponse(UserResponse):
    """사용자 상세 응답 (관리자용)"""
    auth_identities: List[AuthIdentityResponse] = []
    is_admin: bool = False
    
    @classmethod
    def from_user(cls, user, include_admin: bool = False):
        """User 모델에서 변환"""
        data = user.__dict__.copy()
        
        # 인증 아이덴티티 정보
        data['auth_identities'] = [
            AuthIdentityResponse.model_validate(identity) 
            for identity in user.auth_identities
        ]
        
        # 관리자 여부
        data['is_admin'] = bool(user.admin) if include_admin else False
        
        return cls.model_validate(data)


class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str = Field(..., description="현재 비밀번호")
    new_password: str = Field(..., min_length=8, max_length=128, description="새 비밀번호")


class UserStatsResponse(BaseModel):
    """사용자 통계 응답"""
    total_users: int
    active_users: int
    blocked_users: int
    deleted_users: int
    new_users_today: int
    new_users_this_week: int
    new_users_this_month: int

class PointAdjustRequest(BaseModel):
    """관리자용 포인트 조정 요청"""
    coin_delta: int = Field(..., description="조정할 포인트 값 (양수=지급, 음수=회수)")
    note: str = Field(..., min_length=1, max_length=100, description="조정 사유 (예: '관리자 지급')")