from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import secrets

from app.core.config import settings

# 비밀번호 해싱 컨텍스트 (bcrypt 사용 - 문서에 명시됨)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """JWT 리프레시 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """JWT 토큰 검증 및 페이로드 반환"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_password_hash(password: str) -> str:
    """비밀번호 해싱 (bcrypt 사용)"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_password_reset_token() -> str:
    """비밀번호 재설정 토큰 생성 (URL 안전한 랜덤 문자열)"""
    return secrets.token_urlsafe(32)


def generate_email_verification_token() -> str:
    """이메일 인증 토큰 생성"""
    return secrets.token_urlsafe(32)


def create_email_verification_token(email: str, expires_hours: int = 24) -> str:
    """이메일 인증용 JWT 토큰 생성"""
    data = {
        "email": email,
        "type": "email_verification"
    }
    expires_delta = timedelta(hours=expires_hours)
    return create_access_token(data, expires_delta)


def verify_email_verification_token(token: str) -> Optional[str]:
    """이메일 인증 토큰 검증 후 이메일 반환"""
    payload = verify_token(token)
    if payload and payload.get("type") == "email_verification":
        return payload.get("email")
    return None


def create_password_reset_token(user_id: str, expires_hours: int = 1) -> str:
    """비밀번호 재설정용 JWT 토큰 생성"""
    data = {
        "user_id": user_id,
        "type": "password_reset"
    }
    expires_delta = timedelta(hours=expires_hours)
    return create_access_token(data, expires_delta)


def verify_password_reset_token(token: str) -> Optional[str]:
    """비밀번호 재설정 토큰 검증 후 user_id 반환"""
    payload = verify_token(token)
    if payload and payload.get("type") == "password_reset":
        return payload.get("user_id")
    return None


def validate_login_id(login_id: str) -> bool:
    """로그인 ID 형식 검증 (3~30자, [A-Za-z0-9._-])"""
    import re
    if not (3 <= len(login_id) <= 30):
        return False
    pattern = r'^[A-Za-z0-9._-]+$'
    return bool(re.match(pattern, login_id))


def validate_password_strength(password: str) -> dict:
    """비밀번호 강도 검증"""
    errors = []
    
    if len(password) < 8:
        errors.append("비밀번호는 최소 8자 이상이어야 합니다.")
    
    if len(password) > 128:
        errors.append("비밀번호는 128자를 초과할 수 없습니다.")
    
    if not any(c.islower() for c in password):
        errors.append("소문자를 포함해야 합니다.")
    
    if not any(c.isupper() for c in password):
        errors.append("대문자를 포함해야 합니다.")
    
    if not any(c.isdigit() for c in password):
        errors.append("숫자를 포함해야 합니다.")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


# OAuth 관련 헬퍼 함수들
def generate_oauth_state() -> str:
    """OAuth state 파라미터 생성 (CSRF 방지)"""
    return secrets.token_urlsafe(32)


def create_oauth_access_token(provider: str, provider_user_id: str, user_id: str) -> str:
    """OAuth 로그인 성공 후 액세스 토큰 생성"""
    data = {
        "user_id": user_id,
        "provider": provider,
        "provider_user_id": provider_user_id,
        "type": "access"
    }
    return create_access_token(data)


# 토큰에서 사용자 정보 추출
def get_user_id_from_token(token: str) -> Optional[str]:
    """토큰에서 user_id 추출"""
    payload = verify_token(token)
    if payload:
        return payload.get("user_id")
    return None


def get_admin_role_from_token(token: str) -> Optional[str]:
    """토큰에서 관리자 role 추출"""
    payload = verify_token(token)
    if payload:
        return payload.get("role")
    return None