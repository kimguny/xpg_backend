from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
from datetime import datetime, timedelta

from app.api.deps import get_db, get_current_user
from app.models import (
    User, NFCTag, StageHint, UserStageProgress, 
    NFCScanLog, RewardLedger
)
from app.schemas.progress import NFCScanRequest, NFCScanResponse

router = APIRouter()

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
    
    # NFC 태그 조회
    nfc_result = await db.execute(select(NFCTag).where(NFCTag.udid == scan_request.udid))
    nfc_tag = nfc_result.scalar_one_or_none()
    
    if not nfc_tag:
        # 존재하지 않는 태그
        scan_log = NFCScanLog(
            user_id=current_user.id,
            nfc_id=None,
            allowed=False,
            reason="NFC tag not found"
        )
        db.add(scan_log)
        await db.commit()
        
        return NFCScanResponse(
            allowed=False,
            reason="NFC tag not found"
        )
    
    # 태그 활성화 상태 확인
    if not nfc_tag.is_active:
        scan_log = NFCScanLog(
            user_id=current_user.id,
            nfc_id=nfc_tag.id,
            allowed=False,
            reason="NFC tag is not active"
        )
        db.add(scan_log)
        await db.commit()
        
        return NFCScanResponse(
            allowed=False,
            reason="NFC tag is not active"
        )
    
    # 쿨다운 확인
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
                user_id=current_user.id,
                nfc_id=nfc_tag.id,
                allowed=False,
                reason=f"Cooldown active ({remaining_cooldown}s remaining)"
            )
            db.add(scan_log)
            await db.commit()
            
            return NFCScanResponse(
                allowed=False,
                reason=f"Cooldown active. Please wait {remaining_cooldown} seconds.",
                cooldown_sec=remaining_cooldown
            )
    
    # 사용 제한 확인
    if nfc_tag.use_limit is not None:
        usage_count_result = await db.execute(
            select(NFCScanLog)
            .where(
                and_(
                    NFCScanLog.user_id == current_user.id,
                    NFCScanLog.nfc_id == nfc_tag.id,
                    NFCScanLog.allowed == True
                )
            )
        )
        usage_count = len(usage_count_result.scalars().all())
        
        if usage_count >= nfc_tag.use_limit:
            scan_log = NFCScanLog(
                user_id=current_user.id,
                nfc_id=nfc_tag.id,
                allowed=False,
                reason="Usage limit reached"
            )
            db.add(scan_log)
            await db.commit()
            
            return NFCScanResponse(
                allowed=False,
                reason="Usage limit reached for this NFC tag"
            )
    
    # 힌트 ID 자동 보정 (hint_id가 없고 nfc_id로 찾을 수 있으면)
    hint_id = scan_request.hint_id
    hint = None
    
    if not hint_id:
        hint_result = await db.execute(
            select(StageHint).where(StageHint.nfc_id == nfc_tag.id)
        )
        hint = hint_result.scalar_one_or_none()
        if hint:
            hint_id = str(hint.id)
    else:
        hint_result = await db.execute(select(StageHint).where(StageHint.id == hint_id))
        hint = hint_result.scalar_one_or_none()
    
    # 스캔 로그 생성 (성공)
    scan_log = NFCScanLog(
        user_id=current_user.id,
        nfc_id=nfc_tag.id,
        hint_id=hint_id if hint_id else None,
        allowed=True,
        reason=None
    )
    db.add(scan_log)
    
    # 포인트 보상 지급
    if nfc_tag.point_reward > 0:
        reward = RewardLedger(
            user_id=current_user.id,
            coin_delta=nfc_tag.point_reward,
            note=f"NFC scan: {nfc_tag.tag_name}"
        )
        db.add(reward)
    
    # 힌트와 연결된 경우 스테이지 진행상황 업데이트
    if hint:
        stage_progress_result = await db.execute(
            select(UserStageProgress).where(
                and_(
                    UserStageProgress.user_id == current_user.id,
                    UserStageProgress.stage_id == hint.stage_id
                )
            )
        )
        stage_progress = stage_progress_result.scalar_one_or_none()
        
        if not stage_progress:
            # 진행상황이 없으면 생성
            stage_progress = UserStageProgress(
                user_id=current_user.id,
                stage_id=hint.stage_id,
                status="in_progress",
                nfc_count=1
            )
            db.add(stage_progress)
        else:
            # NFC 카운트 증가
            stage_progress.nfc_count += 1
    
    await db.commit()
    
    # 응답 구성
    hint_info = None
    if hint:
        hint_info = {"id": str(hint.id)}
    
    # 다음 액션 결정 (간단한 예시)
    next_info = None
    if hint:
        # 다음 힌트가 있는지 확인
        next_hint_result = await db.execute(
            select(StageHint)
            .where(
                and_(
                    StageHint.stage_id == hint.stage_id,
                    StageHint.order_no > hint.order_no
                )
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