import secrets
import string
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.api.deps import get_db
from app.core.security import (
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_token,
    get_password_hash,
    validate_login_id
)
from app.models import User, AuthIdentity, Admin
from app.schemas.auth import (
    LoginRequest, 
    LoginResponse, 
    RefreshTokenRequest,
    TokenResponse,
    RegisterRequest,
    RegisterResponse,
    PasswordResetRequest
)
from app.core.email import send_temp_password_email

router = APIRouter()


async def _create_user(register_request: RegisterRequest, db: AsyncSession) -> User:
    """사용자 생성 헬퍼 함수"""
    # 로그인 ID 형식 검증
    if not validate_login_id(register_request.loginId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid loginId format. Must be 3-30 characters, [A-Za-z0-9._-] only"
        )
    
    # 로그인 ID 중복 확인
    existing_user = await db.execute(
        select(User).where(User.login_id == register_request.loginId)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Login ID already exists"
        )
    
    # 이메일 중복 확인
    if register_request.email:
        existing_email = await db.execute(
            select(User).where(User.email == register_request.email)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용중인 이메일입니다"
            )
    
    # 사용자 생성
    user = User(
        login_id=register_request.loginId,
        email=register_request.email,
        nickname=register_request.nickname,
        status='active',
        email_verified=False
    )
    db.add(user)
    await db.flush()  # user.id 생성을 위해
    
    # 로컬 인증 정보 생성
    password_hash = get_password_hash(register_request.password)
    auth_identity = AuthIdentity(
        user_id=user.id,
        provider='local',
        provider_user_id=register_request.loginId,
        password_hash=password_hash,
        password_algo='bcrypt'
    )
    db.add(auth_identity)
    
    return user


@router.post("/register", response_model=RegisterResponse)
async def register(
    register_request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    회원가입 (로컬)
    
    - **loginId**: 로그인 ID (3~30자, [A-Za-z0-9._-])
    - **email**: 이메일 주소
    - **password**: 비밀번호 (8자 이상)
    - **nickname**: 닉네임
    
    새 사용자 계정을 생성합니다.
    """
    
    user = await _create_user(register_request, db)
    
    await db.commit()
    await db.refresh(user)
    
    return RegisterResponse(
        user={
            "id": str(user.id),
            "loginId": user.login_id,
            "email": user.email,
            "nickname": user.nickname,
            "emailVerified": user.email_verified
        }
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    로그인 (아이디 또는 이메일)
    
    - **idOrEmail**: 로그인 ID 또는 이메일 주소
    - **password**: 비밀번호
    
    성공 시 JWT 토큰과 사용자 정보를 반환합니다.
    """
    
    # 사용자 조회 (loginId 또는 email로)
    user_query = select(User).where(
        (User.login_id == login_request.idOrEmail) | 
        (User.email == login_request.idOrEmail)
    )
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    
    if not user:
        print(f"User not found for: {login_request.idOrEmail}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    print(f"User found: {user.login_id}, status: {user.status}")
    
    # 계정 상태 확인
    if not user.is_active:
        print(f"User inactive: {user.status}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Account is {user.status}"
        )
    
    # 로컬 인증 정보 조회
    print(f"Looking for auth identity for user_id: {user.id}")
    auth_query = select(AuthIdentity).where(
        (AuthIdentity.user_id == user.id) & 
        (AuthIdentity.provider == 'local')
    )
    auth_result = await db.execute(auth_query)
    auth_identity = auth_result.scalar_one_or_none()
    
    print(f"Auth identity found: {auth_identity is not None}")
    if auth_identity:
        print(f"Has password hash: {auth_identity.password_hash is not None}")
    
    if not auth_identity or not auth_identity.password_hash:
        print("No auth identity or password hash")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Local authentication not available"
        )
    
    # 비밀번호 검증
    if not verify_password(login_request.password, auth_identity.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # 관리자 권한 확인
    admin_query = select(Admin).where(Admin.user_id == user.id)
    admin_result = await db.execute(admin_query)
    admin = admin_result.scalar_one_or_none()
    
    # JWT 토큰 생성 (사용자 ID와 관리자 role 포함)
    token_data = {
        "user_id": str(user.id),
        "login_id": user.login_id
    }
    
    if admin:
        token_data["role"] = admin.role
        token_data["admin_id"] = str(admin.id)
    
    access_token = create_access_token(token_data)
    
    # 최근 로그인 시각 업데이트
    auth_identity.last_login_at = text("now()")
    user.last_active_at = text("now()")
    
    await db.commit()
    
    return LoginResponse(
        accessToken=access_token,
        user={
            "id": str(user.id),
            "loginId": user.login_id,
            "email": user.email,
            "nickname": user.nickname,
            "status": user.status,
            "isAdmin": bool(admin),
            "adminRole": admin.role if admin else None
        }
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    JWT 토큰 재발급
    
    - **refreshToken**: 기존 리프레시 토큰
    
    새로운 액세스 토큰을 발급합니다.
    """
    
    # 리프레시 토큰 검증
    payload = verify_token(refresh_request.refreshToken)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # 관리자 권한 재확인
    admin_query = select(Admin).where(Admin.user_id == user.id)
    admin_result = await db.execute(admin_query)
    admin = admin_result.scalar_one_or_none()
    
    # 새 토큰 생성
    token_data = {
        "user_id": str(user.id),
        "login_id": user.login_id
    }
    
    if admin:
        token_data["role"] = admin.role
        token_data["admin_id"] = str(admin.id)
    
    new_access_token = create_access_token(token_data)
    
    return TokenResponse(accessToken=new_access_token)


@router.post("/logout")
async def logout():
    """
    로그아웃
    
    클라이언트 측에서 토큰을 삭제하면 됩니다.
    서버 측에서는 토큰 블랙리스트 처리가 필요하면 추후 구현.
    """
    return {"message": "Logged out successfully"}


# OAuth2 호환을 위한 추가 엔드포인트 (FastAPI docs용)
@router.post("/token", response_model=LoginResponse)
async def login_for_docs(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 호환 로그인 엔드포인트 (API 문서 테스트용)
    """
    login_request = LoginRequest(
        idOrEmail=form_data.username,
        password=form_data.password
    )
    return await login(login_request, db)

def _generate_random_password(length: int = 8) -> str:
    """영문 대소문자, 숫자를 포함한 랜덤 8자리 비밀번호 생성"""
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        # 최소 1개 이상의 대문자, 소문자, 숫자가 포함되도록 보장
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)):
            return password
        
@router.post("/password/forgot")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    비밀번호 초기화 요청 (임시 비밀번호 발급 및 이메일 전송)
    [수정됨] 성공/실패 여부를 명확히 반환합니다.
    """
    
    # 1. 사용자 조회 (loginId 또는 email로)
    user_query = select(User).where(
        (User.login_id == reset_request.idOrEmail) | 
        (User.email == reset_request.idOrEmail)
    )
    result = await db.execute(user_query)
    user = result.scalar_one_or_none()
    
    # 2. [수정] 사용자가 존재하지 않는 경우
    if not user:
        return {"message": "존재하지않는 아이디 또는 이메일입니다."}

    # 3. [수정] 사용자는 있으나, 이메일이 등록되지 않은 경우
    if not user.email:
        return {"message": "계정에 이메일이 등록되어 있지 않아 전송할 수 없습니다."}
        
    # 4. 사용자의 'local' 인증 정보 조회
    result = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == "local"
        )
    )
    auth_identity = result.scalar_one_or_none()
    
    # 5. [수정] 로컬 계정이 아닌 경우 (예: 소셜 로그인 전용)
    if not auth_identity:
        return {"message": "소셜 로그인 계정은 비밀번호를 초기화할 수 없습니다."}
        
    # 6. 모든 조건 통과: 임시 비밀번호 발급
    temp_password = _generate_random_password()
    
    # 7. 새 비밀번호를 해싱하여 DB에 업데이트
    auth_identity.password_hash = get_password_hash(temp_password)
    
    try:
        await db.commit()
        
        # 8. 사용자 이메일로 임시 비밀번호(원본) 발송
        await send_temp_password_email(
            email_to=user.email,
            nickname=user.nickname,
            temp_password=temp_password
        )
        
        # 9. [수정] 전송 성공
        return {"message": "임시비밀번호를 전송하였습니다"}

    except Exception as e:
        await db.rollback()
        # 10. [수정] 이메일 발송 또는 DB 커밋 실패
        print(f"Error during password reset for {user.email}: {e}") # 서버 로그에 에러 기록
        return {"message": "이메일 전송 중 오류가 발생했습니다."}