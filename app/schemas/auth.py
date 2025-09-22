from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """로그인 요청"""
    idOrEmail: str = Field(..., description="로그인 ID 또는 이메일")
    password: str = Field(..., description="비밀번호")


class UserInfo(BaseModel):
    """로그인 응답용 사용자 정보"""
    id: str
    loginId: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    status: str
    isAdmin: bool = False
    adminRole: Optional[str] = None


class LoginResponse(BaseModel):
    """로그인 응답"""
    accessToken: str
    user: UserInfo


class TokenResponse(BaseModel):
    """토큰 재발급 응답"""
    accessToken: str


class RefreshTokenRequest(BaseModel):
    """토큰 재발급 요청"""
    refreshToken: str = Field(..., description="리프레시 토큰")


class RegisterRequest(BaseModel):
    """회원가입 요청 (로컬)"""
    loginId: str = Field(..., min_length=3, max_length=30, pattern=r'^[A-Za-z0-9._-]+$')
    email: str = Field(..., description="이메일 주소")
    password: str = Field(..., min_length=8, max_length=128, description="비밀번호")


class RegisterResponse(BaseModel):
    """회원가입 응답"""
    user: Dict[str, Any] = Field(..., description="생성된 사용자 정보")


class PasswordResetRequest(BaseModel):
    """비밀번호 재설정 요청"""
    idOrEmail: str = Field(..., description="로그인 ID 또는 이메일")


class PasswordResetConfirmRequest(BaseModel):
    """비밀번호 재설정 확인"""
    token: str = Field(..., description="재설정 토큰")
    newPassword: str = Field(..., min_length=8, max_length=128, description="새 비밀번호")


class EmailVerificationRequest(BaseModel):
    """이메일 인증 요청"""
    email: str = Field(..., description="인증할 이메일")


class EmailVerificationConfirmRequest(BaseModel):
    """이메일 인증 확인"""
    token: str = Field(..., description="인증 토큰")


class OAuthSigninRequest(BaseModel):
    """SNS 로그인/가입 요청"""
    provider: str = Field(..., description="제공자: google|apple|kakao|naver|...")
    token: str = Field(..., description="ID 토큰 또는 액세스 토큰")
    link: bool = Field(False, description="기존 계정에 연동 여부")


class OAuthLinkRequest(BaseModel):
    """SNS 연동 요청"""
    provider: str = Field(..., description="제공자")
    token: str = Field(..., description="토큰")


class LogoutResponse(BaseModel):
    """로그아웃 응답"""
    message: str = "Logged out successfully"


class TokenPayload(BaseModel):
    """JWT 토큰 페이로드"""
    user_id: str
    login_id: str
    role: Optional[str] = None
    admin_id: Optional[str] = None
    exp: Optional[int] = None