from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# [추가] 위치 거리 계산을 위한 라이브러리
from geoalchemy2.functions import ST_Distance, ST_GeogFromText
from geoalchemy2.elements import WKTElement

from app.api.deps import get_db, get_current_user
from app.models import (
    User, NFCTag, StageHint, UserStageProgress, 
    NFCScanLog, RewardLedger
)
from app.schemas.progress import NFCScanRequest, NFCScanResponse

# [추가] 위치 인증 요청 스키마
class LocationVerifyRequest(BaseModel):
    hint_id: str = Field(..., description="인증하려는 힌트 ID")
    latitude: float = Field(..., description="현재 위도")
    longitude: float = Field(..., description="현재 경도")

# [추가] 위치 인증 응답 스키마
class LocationVerifyResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    point_reward: int = 0
    next: Optional[dict] = None # 다음 단계 정보

class NFCTagLookupResponse(BaseModel):
    """
    앱에서 UDID로 태그 조회 시 반환하는 정보
    (포인트, 쿨다운 등 민감한 정보 제외)
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    udid: str
    tag_name: str
    description: Optional[str] = None
    media_url: Optional[str] = None
    link_url: Optional[str] = None
    tap_message: Optional[str] = None
    point_reward: int
    floor_location: Optional[str] = None
    category: Optional[str] = None
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        data = super().model_validate(obj, **kwargs).model_dump()
        data['point_reward'] = obj.point_reward
        return cls(**data)

class NFCRegisterRequest(BaseModel):
    """NFC 사전 등록 요청 스키마"""
    udid: str = Field(..., description="등록할 NFC 태그의 UDID")
    tag_name: str = Field(..., min_length=1, max_length=100, description="NFC 태그 이름")

class NFCRegisterResponse(BaseModel):
    """NFC 사전 등록 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    udid: str
    tag_name: str
    is_active: bool

router = APIRouter()

@router.post(
    "/register", 
    response_model=NFCRegisterResponse,
    summary="[App] NFC 태그 사전 등록",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "UDID already exists"}
    }
)
async def register_nfc(
    register_request: NFCRegisterRequest,
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    일반 사용자가 NFC 태그를 스캔하여 UDID와 태그명만으로 시스템에 사전 등록합니다.
    """
    
    existing_tag_result = await db.execute(
        select(NFCTag).where(NFCTag.udid == register_request.udid)
    )
    existing_tag = existing_tag_result.scalar_one_or_none()
    
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tag with this UDID already exists."
        )
        
    new_tag = NFCTag(
        udid=register_request.udid,
        tag_name=register_request.tag_name,
        is_active=True 
    )
    
    try:
        db.add(new_tag)
        await db.commit()
        await db.refresh(new_tag)
    except Exception as e:
        await db.rollback()
        if "uq_nfc_tags_udid" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A tag with this UDID already exists (concurrent registration)."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register NFC tag: {e}"
        )
        
    return NFCRegisterResponse.model_validate(new_tag)


@router.post("/scan", response_model=NFCScanResponse)
async def scan_nfc(
    scan_request: NFCScanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    NFC 태깅 처리 + 쿨다운/인증 판단 + 로그 적재
    """
    
    async with db.begin():
        # 1. NFC 태그 조회
        nfc_result = await db.execute(select(NFCTag).where(NFCTag.udid == scan_request.udid))
        nfc_tag = nfc_result.scalar_one_or_none()
        
        if not nfc_tag:
            scan_log = NFCScanLog(
                user_id=current_user.id, nfc_id=None, allowed=False, reason="NFC tag not found"
            )
            db.add(scan_log)
            return NFCScanResponse(allowed=False, reason="NFC tag not found")
        
        # 2. 태그 활성화 상태 확인
        if not nfc_tag.is_active:
            scan_log = NFCScanLog(
                user_id=current_user.id, nfc_id=nfc_tag.id, allowed=False, reason="NFC tag is not active"
            )
            db.add(scan_log)
            return NFCScanResponse(allowed=False, reason="NFC tag is not active")
        
        # 3. 쿨다운 확인
        if nfc_tag.cooldown_sec > 0:
            cooldown_threshold = datetime.utcnow() - timedelta(seconds=nfc_tag.cooldown_sec)
            recent_scan_result = await db.execute(
                select(NFCScanLog)
                .where(
                    and_(
                        NFCScanLog.user_id == current_user.id,
                        NFCScanLog.nfc_id == nfc_tag.id,
                        NFCScanLog.allowed == True,
                        NFCScanLog.scanned_at > cooldown_threshold
                    )
                )
                .order_by(NFCScanLog.scanned_at.desc())
                .limit(1)
            )
            recent_scan = recent_scan_result.scalar_one_or_none()
            
            if recent_scan:
                time_diff = (datetime.utcnow() - recent_scan.scanned_at).total_seconds()
                remaining_cooldown = int(nfc_tag.cooldown_sec - time_diff)
                scan_log = NFCScanLog(
                    user_id=current_user.id, nfc_id=nfc_tag.id, allowed=False,
                    reason=f"Cooldown active ({remaining_cooldown}s remaining)"
                )
                db.add(scan_log)
                
                return NFCScanResponse(
                    allowed=False,
                    reason=f"Cooldown active. Please wait {remaining_cooldown} seconds.",
                    cooldown_sec=remaining_cooldown
                )
        
        # 4. 사용 제한 확인
        if nfc_tag.use_limit is not None:
            usage_count_result = await db.execute(
                select(func.count(NFCScanLog.id))
                .where(
                    and_(
                        NFCScanLog.user_id == current_user.id,
                        NFCScanLog.nfc_id == nfc_tag.id,
                        NFCScanLog.allowed == True
                    )
                )
            )
            usage_count = usage_count_result.scalar() or 0
            
            if usage_count >= nfc_tag.use_limit:
                scan_log = NFCScanLog(
                    user_id=current_user.id, nfc_id=nfc_tag.id, allowed=False, reason="Usage limit reached"
                )
                db.add(scan_log)
                
                return NFCScanResponse(allowed=False, reason="Usage limit reached for this NFC tag")
        
        # 5. 힌트 ID 자동 보정
        hint_id = scan_request.hint_id
        hint = None
        if not hint_id:
            hint_result = await db.execute(select(StageHint).where(StageHint.nfc_id == nfc_tag.id))
            hint = hint_result.scalar_one_or_none()
            if hint: hint_id = str(hint.id)
        else:
            hint_result = await db.execute(select(StageHint).where(StageHint.id == hint_id))
            hint = hint_result.scalar_one_or_none()
        
        # 6. 스캔 로그 생성 (성공)
        scan_log = NFCScanLog(
            user_id=current_user.id, nfc_id=nfc_tag.id, hint_id=hint_id, allowed=True, reason=None
        )
        db.add(scan_log)
        
        new_points = 0 
        
        # 7. 포인트 보상 지급 (및 캐시 업데이트)
        if nfc_tag.point_reward > 0:
            reward = RewardLedger(
                user_id=current_user.id,
                coin_delta=nfc_tag.point_reward,
                note=f"NFC scan: {nfc_tag.tag_name}"
            )
            db.add(reward)
            
            user_to_update = await db.get(User, current_user.id, with_for_update=True)
            if not user_to_update:
                raise HTTPException(status_code=404, detail="User not found during point update")

            current_points = user_to_update.profile.get("points", 0) if user_to_update.profile else 0
            new_points = current_points + nfc_tag.point_reward 
            
            if user_to_update.profile is None:
                updated_profile = {}
            else:
                updated_profile = user_to_update.profile.copy()
            
            updated_profile["points"] = new_points
            
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(profile=updated_profile)
            )
        
        # 8. 힌트와 연결된 경우 스테이지 진행상황 업데이트
        if hint:
            stage_progress_result = await db.execute(
                select(UserStageProgress).where(
                    UserStageProgress.user_id == current_user.id,
                    UserStageProgress.stage_id == hint.stage_id
                )
            )
            stage_progress = stage_progress_result.scalar_one_or_none()
            
            if not stage_progress:
                stage_progress = UserStageProgress(
                    user_id=current_user.id, stage_id=hint.stage_id, status="in_progress", nfc_count=1
                )
                db.add(stage_progress)
            else:
                stage_progress.nfc_count = (stage_progress.nfc_count or 0) + 1
        
    # 10. 응답 구성 (트랜잭션 밖에서)
    hint_info = None
    if hint:
        hint_info = {"id": str(hint.id)}
    
    next_info = None
    if hint:
        next_hint_result = await db.execute(
            select(StageHint)
            .where(
                StageHint.stage_id == hint.stage_id,
                StageHint.order_no > hint.order_no
            )
            .order_by(StageHint.order_no)
            .limit(1)
        )
        next_hint = next_hint_result.scalar_one_or_none()
        
        if next_hint:
            next_info = {"type": "hint", "id": str(next_hint.id)}
        else:
            next_info = {"type": "stage", "id": str(hint.stage_id)}
    
    return NFCScanResponse(
        allowed=True,
        reason=None,
        point_reward=nfc_tag.point_reward,
        cooldown_sec=nfc_tag.cooldown_sec,
        hint=hint_info,
        next=next_info
    )

# [6. 추가] 앱용 UDID 조회 API
@router.get(
    "/by-udid", 
    response_model=NFCTagLookupResponse,
    summary="[App] UDID로 NFC 태그 정보 조회",
    responses={
        404: {"description": "Tag not found or not active"}
    }
)
async def get_nfc_tag_by_udid_for_app(
    udid: str = Query(..., description="조회할 NFC 태그의 UDID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    앱에서 UDID를 기준으로 활성화된 NFC 태그의 공개 정보를 조회합니다.
    """
    
    query = select(NFCTag).where(
        NFCTag.udid == udid,
        NFCTag.is_active == True 
    )
    result = await db.execute(query)
    tag = result.scalars().first()
    
    if not tag:
        raise HTTPException(
            status_code=404, 
            detail="NFC tag not found or is not active."
        )
        
    return tag

# ==========================================================
# [신규] 위치 인증 API (GPS 정답 처리)
# ==========================================================
@router.post(
    "/verify-location",
    response_model=LocationVerifyResponse,
    summary="[App] GPS 위치 인증 (힌트 정답 확인)"
)
async def verify_location(
    req: LocationVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자의 현재 GPS 좌표가 힌트에 설정된 목표 지점의 반경 내에 있는지 확인합니다.
    - 정답이면: allowed=True, 포인트 지급(있는 경우), 스테이지 진행 갱신
    - 오답이면: allowed=False
    """
    
    async with db.begin():
        # 1. 힌트 조회
        hint_result = await db.execute(select(StageHint).where(StageHint.id == req.hint_id))
        hint = hint_result.scalar_one_or_none()
        
        if not hint:
            return LocationVerifyResponse(allowed=False, reason="Hint not found")
        
        # 2. 위치 설정 여부 확인
        if not hint.location or not hint.radius_m:
            return LocationVerifyResponse(allowed=False, reason="This hint does not have location verification configured.")
        
        # 3. 거리 계산 (PostGIS ST_Distance: 미터 단위 반환)
        # 사용자 위치 Point 생성
        user_point = f"POINT({req.longitude} {req.latitude})"
        
        # DB에서 거리 계산
        # ST_Distance(geography, geography) -> meters
        # hint.location은 이미 Geography 타입
        distance_query = select(
            func.ST_Distance(
                hint.location,
                func.ST_GeogFromText(user_point)
            )
        )
        distance_result = await db.execute(distance_query)
        distance_meters = distance_result.scalar() or 0.0
        
        # 4. 반경 확인
        if distance_meters > hint.radius_m:
            return LocationVerifyResponse(
                allowed=False, 
                reason=f"Not within target area. Distance: {int(distance_meters)}m, Required: {hint.radius_m}m"
            )
            
        # --- [정답 처리 로직] ---
        
        # 5. 포인트 보상 지급 (힌트 자체 보상)
        if hint.reward_coin > 0:
            # 이미 보상을 받았는지 체크할 수도 있음 (기획에 따라 다름)
            # 여기서는 중복 지급 방지 로직은 생략 (필요 시 추가)
            
            reward = RewardLedger(
                user_id=current_user.id,
                coin_delta=hint.reward_coin,
                note=f"Location verified: Hint {hint.id}"
            )
            db.add(reward)
            
            # 유저 프로필 업데이트
            user_to_update = await db.get(User, current_user.id, with_for_update=True)
            current_points = user_to_update.profile.get("points", 0) if user_to_update.profile else 0
            new_points = current_points + hint.reward_coin
            
            if user_to_update.profile is None:
                updated_profile = {}
            else:
                updated_profile = user_to_update.profile.copy()
            updated_profile["points"] = new_points
            
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(profile=updated_profile)
            )

        # 6. 스테이지 진행상황 업데이트
        stage_progress_result = await db.execute(
            select(UserStageProgress).where(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id == hint.stage_id
            )
        )
        stage_progress = stage_progress_result.scalar_one_or_none()
        
        if not stage_progress:
            stage_progress = UserStageProgress(
                user_id=current_user.id, 
                stage_id=hint.stage_id, 
                status="in_progress", 
                nfc_count=1 # 위치 인증도 카운트로 칠 경우
            )
            db.add(stage_progress)
        else:
            # 단순히 카운트만 늘릴지, 특정 상태를 바꿀지는 기획에 따름
            stage_progress.nfc_count = (stage_progress.nfc_count or 0) + 1
            
    # 7. 다음 단계 정보 조회 (트랜잭션 밖)
    next_info = None
    next_hint_result = await db.execute(
        select(StageHint)
        .where(
            StageHint.stage_id == hint.stage_id,
            StageHint.order_no > hint.order_no
        )
        .order_by(StageHint.order_no)
        .limit(1)
    )
    next_hint = next_hint_result.scalar_one_or_none()
    
    if next_hint:
        next_info = {"type": "hint", "id": str(next_hint.id)}
    else:
        next_info = {"type": "stage", "id": str(hint.stage_id)}

    return LocationVerifyResponse(
        allowed=True,
        point_reward=hint.reward_coin,
        next=next_info
    )