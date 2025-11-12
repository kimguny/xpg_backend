from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text, func
from sqlalchemy.orm import selectinload
import uuid
from typing import Optional, Dict
from datetime import datetime, timezone

from app.api.deps import get_db, get_current_user
from app.models import (
    User, Stage, UserStageProgress, UserContentProgress, 
    Content, RewardLedger, StoreReward
)
from app.schemas.progress import (
    StageUnlockRequest,
    StageUnlockResponse,
    StageClearRequest,
    StageClearResponse,
    RewardInfo,
    RewardHistoryItem,
    RewardConsumeRequest,
    RewardConsumeResponse
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
            unlock_at=stage_progress.unlock_at or datetime.now(timezone.utc)
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
    
    now = datetime.now(timezone.utc)
    
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
    
    # 이미 클리어된 경우 (이 로직은 유지)
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
            content_cleared=False, # 이미 클리어된 상태이므로 false 반환
            next_content=None
        )
    
    # --- [수정] "잠김" 상태 확인 로직 제거 ---
    # 스테이지가 해금되지 않은 경우 (기존 코드)
    # if not stage_progress or stage_progress.status == "locked":
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Stage is locked"
    #     )
    
    now = datetime.now(timezone.utc)
    
    # [수정] 스테이지 진행상황 업데이트 (또는 생성)
    if not stage_progress:
        # "locked" 상태였거나 진행 기록이 아예 없으면, 새로 생성
        stage_progress = UserStageProgress(
            user_id=current_user.id,
            stage_id=stage_id,
            status="cleared", # 'locked' 여부와 상관없이 'cleared'로 강제
            unlock_at=now,     # 해금된 적이 없으므로 지금 해금
            cleared_at=now     # 지금 클리어
        )
        db.add(stage_progress)
    else:
        # 'locked', 'unlocked', 'in_progress' 등 모든 상태를 'cleared'로 덮어쓰기
        stage_progress.status = "cleared"
        stage_progress.cleared_at = now
    
    if clear_request.best_time_sec is not None:
        if stage_progress.best_time_sec is None or clear_request.best_time_sec < stage_progress.best_time_sec:
            stage_progress.best_time_sec = clear_request.best_time_sec
    
    # 보상 지급 (빈 리스트로 초기화)
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
    all_stage_ids = [s.id for s in all_stages]
    
    # [수정] 이미 클리어된 스테이지 ID 목록을 DB에서 조회 (현재 스테이지 제외)
    cleared_stages_db_result = await db.execute(
        select(UserStageProgress.stage_id).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id.in_(all_stage_ids),
                UserStageProgress.stage_id != stage.id, # 방금 클리어한 스테이지는 제외
                UserStageProgress.status == "cleared"
            )
        )
    )
    # DB에서 가져온 이미 클리어된 스테이지 ID 세트
    cleared_stage_ids = {row[0] for row in cleared_stages_db_result.all()}
    # 현재 스테이지 ID 추가 (방금 클리어했으므로)
    cleared_stage_ids.add(stage.id)


    # 모든 스테이지를 클리어한 경우
    if len(cleared_stage_ids) == len(all_stage_ids):
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
        
        # --- [수정] 콘텐츠 클리어 보상 로직 삭제 ---
        # (클라이언트에서 수동으로 지급)
        # --- [수정] 로직 삭제 끝 ---
        
        # 다음 콘텐츠 확인
        if content.has_next_content and content.next_content_id:
            next_content_id = str(content.next_content_id)
    
    await db.commit()
    
    return StageClearResponse(
        cleared=True,
        rewards=rewards, # 빈 리스트 또는 스테이지 보상만 반환
        content_cleared=content_cleared,
        next_content=next_content_id
    )

@router.post("/rewards/consume", response_model=RewardConsumeResponse, summary="[App] 리워드 상품 교환(결제)")
async def consume_reward(
    consume_request: RewardConsumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    사용자가 포인트를 사용해 리워드 상품을 교환(결제)합니다.
    재고 확인, 포인트 확인, 재고 차감, 포인트 내역 기록을 트랜잭션으로 처리합니다.
    """
    
    # [수정] with db.begin()을 사용하여 트랜잭션 보장
    async with db.begin():
        try:
            # 1. 교환할 상품(StoreReward) 조회 (FOR UPDATE로 비관적 락 설정)
            reward_item_result = await db.execute(
                select(StoreReward)
                .where(StoreReward.id == consume_request.reward_id)
                .with_for_update() # 비관적 락 (재고 동시성 문제 방지)
            )
            reward_item = reward_item_result.scalar_one_or_none()

            if not reward_item:
                raise HTTPException(status_code=404, detail="Reward item not found")
            if not reward_item.is_active:
                raise HTTPException(status_code=400, detail="Reward item is not active")

            # 2. (재고 체크)
            if reward_item.stock_qty is not None: # NULL이 아니면(무제한이 아니면)
                if reward_item.stock_qty <= 0:
                    raise HTTPException(status_code=400, detail="Item out of stock")

            # 3. (포인트 체크) 사용자의 현재 포인트 잔액 계산
            # [수정] 이 쿼리도 트랜잭션에 포함
            user_points_result = await db.execute(
                select(func.sum(RewardLedger.coin_delta)).where(RewardLedger.user_id == current_user.id)
            )
            current_points = user_points_result.scalar() or 0

            # 4. 상품 가격과 비교
            if current_points < reward_item.price_coin:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Not enough points. Required: {reward_item.price_coin}, Available: {current_points}"
                )
                
            # 5. (재고 차감) stock_qty가 NULL이 아닐 때만 1 차감
            if reward_item.stock_qty is not None:
                reward_item.stock_qty -= 1
                
            # 6. (포인트 내역 기록) RewardLedger에 차감 내역 추가
            new_ledger_entry = RewardLedger(
                user_id=current_user.id,
                store_id=reward_item.store_id,
                store_reward_id=reward_item.id, # [수정] reward_id -> store_reward_id
                coin_delta=-reward_item.price_coin, # 포인트 차감
                note=f"Consumed: {reward_item.product_name}"
            )
            db.add(new_ledger_entry)
            
            # 7. user.profile 캐시 업데이트
            user_to_update = await db.get(User, current_user.id, with_for_update=True)
            if user_to_update:
                user_profile = user_to_update.profile or {}
                user_profile['points'] = current_points - reward_item.price_coin
                user_to_update.profile = user_profile
                # SQLAlchemy 1.4+는 변경 감지
            
            # [수정] db.commit()은 with db.begin()이 대신 처리

            # 8. 성공 응답 반환 (트랜잭션이 성공적으로 커밋된 후)
            # new_ledger_entry.id는 flush 이후에 접근 가능 (commit 전에)
            await db.flush([new_ledger_entry])
            
            return RewardConsumeResponse(
                success=True,
                reward_id=reward_item.id,
                points_deducted=reward_item.price_coin,
                remaining_points=current_points - reward_item.price_coin,
                ledger_id=new_ledger_entry.id
            )

        except Exception as e:
            # [수정] db.rollback()은 with db.begin()이 대신 처리
            if isinstance(e, HTTPException):
                raise e # HTTP 예외는 그대로 다시 발생시킴
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during transaction: {e}"
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
    
    # [수정] Pydantic 스키마의 타입에 맞게 UUID를 str()로 변환
    items = [
        RewardHistoryItem.model_validate(reward)
        for reward in rewards
    ]
    
    return PaginatedResponse(
        items=items,
        page=page,
        size=size,
        total=total
    )