from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from typing import Optional
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models import (
    User, Stage, UserStageProgress, UserContentProgress, 
    Content, RewardLedger
)
from app.schemas.progress import (
    StageUnlockRequest,
    StageUnlockResponse,
    StageClearRequest,
    StageClearResponse,
    RewardInfo,
    RewardHistoryItem
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

@router.post("/stages/{stage_id}/unlock", response_model=StageUnlockResponse)
async def unlock_stage(
    stage_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    스테이지 해금
    """
    
    # 스테이지 조회
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 콘텐츠 참여 확인
    content_progress_result = await db.execute(
        select(UserContentProgress).where(
            and_(
                UserContentProgress.user_id == current_user.id,
                UserContentProgress.content_id == stage.content_id
            )
        )
    )
    content_progress = content_progress_result.scalar_one_or_none()
    
    if not content_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not joined this content"
        )
    
    # 스테이지 진행상황 조회
    stage_progress_result = await db.execute(
        select(UserStageProgress).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id == stage_id
            )
        )
    )
    stage_progress = stage_progress_result.scalar_one_or_none()
    
    # 이미 해금된 경우
    if stage_progress and stage_progress.status != "locked":
        return StageUnlockResponse(
            unlocked=True,
            unlock_at=stage_progress.unlock_at or datetime.utcnow()
        )
    
    # 해금 조건 확인 (unlock_stage_id가 있는 경우)
    if stage.unlock_stage_id:
        unlock_stage_progress_result = await db.execute(
            select(UserStageProgress).where(
                and_(
                    UserStageProgress.user_id == current_user.id,
                    UserStageProgress.stage_id == stage.unlock_stage_id
                )
            )
        )
        unlock_stage_progress = unlock_stage_progress_result.scalar_one_or_none()
        
        if not unlock_stage_progress or unlock_stage_progress.status != "cleared":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required stage not cleared"
            )
    
    now = datetime.utcnow()
    
    # 진행상황 생성 또는 업데이트
    if not stage_progress:
        stage_progress = UserStageProgress(
            user_id=current_user.id,
            stage_id=stage_id,
            status="unlocked",
            unlock_at=now
        )
        db.add(stage_progress)
    else:
        stage_progress.status = "unlocked"
        stage_progress.unlock_at = now
    
    await db.commit()
    
    return StageUnlockResponse(
        unlocked=True,
        unlock_at=now
    )

@router.post("/stages/{stage_id}/clear", response_model=StageClearResponse)
async def clear_stage(
    stage_id: str,
    clear_request: StageClearRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    스테이지 클리어
    """
    
    # 스테이지 조회
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 콘텐츠 조회
    content_result = await db.execute(select(Content).where(Content.id == stage.content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 스테이지 진행상황 조회
    stage_progress_result = await db.execute(
        select(UserStageProgress).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id == stage_id
            )
        )
    )
    stage_progress = stage_progress_result.scalar_one_or_none()
    
    # 이미 클리어된 경우
    if stage_progress and stage_progress.status == "cleared":
        # 기존 보상 조회
        existing_rewards_result = await db.execute(
            select(RewardLedger).where(
                and_(
                    RewardLedger.user_id == current_user.id,
                    RewardLedger.stage_id == stage_id
                )
            )
        )
        existing_rewards = existing_rewards_result.scalars().all()
        
        return StageClearResponse(
            cleared=True,
            rewards=[
                RewardInfo(coin_delta=reward.coin_delta, note=reward.note)
                for reward in existing_rewards
            ],
            content_cleared=False,
            next_content=None
        )
    
    # 스테이지가 해금되지 않은 경우
    if not stage_progress or stage_progress.status == "locked":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stage is locked"
        )
    
    now = datetime.utcnow()
    
    # 스테이지 진행상황 업데이트
    stage_progress.status = "cleared"
    stage_progress.cleared_at = now
    
    if clear_request.best_time_sec is not None:
        if stage_progress.best_time_sec is None or clear_request.best_time_sec < stage_progress.best_time_sec:
            stage_progress.best_time_sec = clear_request.best_time_sec
    
    # 보상 지급
    rewards = []
    
    # 스테이지 기본 보상 (있는 경우)
    # TODO: 스테이지별 보상 설정이 있다면 추가
    
    # 콘텐츠 클리어 확인
    content_cleared = False
    next_content_id = None
    
    # 해당 콘텐츠의 모든 메인 스테이지 조회
    all_stages_result = await db.execute(
        select(Stage).where(
            and_(
                Stage.content_id == stage.content_id,
                Stage.parent_stage_id.is_(None)
            )
        )
    )
    all_stages = all_stages_result.scalars().all()
    
    # 모든 스테이지 클리어 상태 확인
    all_stage_ids = [str(s.id) for s in all_stages]
    cleared_stages_result = await db.execute(
        select(UserStageProgress).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id.in_(all_stage_ids),
                UserStageProgress.status == "cleared"
            )
        )
    )
    cleared_stages = cleared_stages_result.scalars().all()
    
    # 모든 스테이지를 클리어한 경우
    if len(cleared_stages) == len(all_stages):
        content_cleared = True
        
        # 콘텐츠 진행상황 업데이트
        content_progress_result = await db.execute(
            select(UserContentProgress).where(
                and_(
                    UserContentProgress.user_id == current_user.id,
                    UserContentProgress.content_id == stage.content_id
                )
            )
        )
        content_progress = content_progress_result.scalar_one_or_none()
        
        if content_progress:
            content_progress.status = "cleared"
            content_progress.cleared_at = now
        
        # 콘텐츠 클리어 보상
        if content.reward_coin > 0:
            content_reward = RewardLedger(
                user_id=current_user.id,
                content_id=content.id,
                coin_delta=content.reward_coin,
                note="Content clear"
            )
            db.add(content_reward)
            rewards.append(RewardInfo(
                coin_delta=content.reward_coin,
                note="Content clear"
            ))
        
        # 다음 콘텐츠 확인
        if content.has_next_content and content.next_content_id:
            next_content_id = str(content.next_content_id)
    
    await db.commit()
    
    return StageClearResponse(
        cleared=True,
        rewards=rewards,
        content_cleared=content_cleared,
        next_content=next_content_id
    )

@router.get("/rewards", response_model=PaginatedResponse[RewardHistoryItem])
async def get_rewards_history(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    내 보상 히스토리 조회
    """
    
    from sqlalchemy import func
    
    # 전체 개수 조회
    count_result = await db.execute(
        select(func.count(RewardLedger.id)).where(RewardLedger.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    # 보상 히스토리 조회
    offset = (page - 1) * size
    rewards_result = await db.execute(
        select(RewardLedger)
        .where(RewardLedger.user_id == current_user.id)
        .order_by(RewardLedger.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    rewards = rewards_result.scalars().all()
    
    items = [
        RewardHistoryItem(
            id=reward.id,
            coin_delta=reward.coin_delta,
            created_at=reward.created_at,
            note=reward.note,
            stage_id=str(reward.stage_id) if reward.stage_id else None,
            content_id=str(reward.content_id) if reward.content_id else None
        )
        for reward in rewards
    ]
    
    return PaginatedResponse(
        items=items,
        page=page,
        size=size,
        total=total
    )