from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
from app.models import Content, UserContentProgress, User
from app.schemas.content import (
    ContentListResponse,
    ContentResponse,
    ContentProgressResponse,
    ContentJoinResponse
)
from app.models import Stage, UserStageProgress

router = APIRouter()

def format_center_point(content: Content) -> Optional[dict]:
    """geography 타입의 center_point를 dict로 변환"""
    if not content.center_point:
        return None
    
    # PostGIS geography에서 좌표 추출
    try:
        return {
            "lon": float(content.center_point.longitude) if hasattr(content.center_point, 'longitude') else 0.0,
            "lat": float(content.center_point.latitude) if hasattr(content.center_point, 'latitude') else 0.0
        }
    except:
        return None

@router.get("", response_model=List[ContentListResponse])
async def get_contents(
    only_available: bool = Query(True, description="입장 가능한 콘텐츠만 조회"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """
    입장 가능한 콘텐츠 목록 조회
    
    - **only_available**: 현재 입장 가능한 콘텐츠만 조회
    - **page**: 페이지 번호 (1부터 시작)
    - **size**: 페이지 크기 (최대 100)
    """
    
    # 기본 쿼리
    query = select(Content)
    
    if only_available:
        now = datetime.utcnow()
        query = query.where(
            and_(
                Content.is_open == True,  # 오픈된 콘텐츠만
                (Content.is_always_on == True) |  # 항상 활성화되거나
                (
                    (Content.start_at.is_(None) | (Content.start_at <= now)) &  # 시작 시간 조건
                    (Content.end_at.is_(None) | (Content.end_at >= now))        # 종료 시간 조건
                )
            )
        )
    
    # 페이지네이션
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Content.created_at.desc())
    
    result = await db.execute(query)
    contents = result.scalars().all()
    
    return [
        ContentListResponse(
            id=str(content.id),
            title=content.title,
            content_type=content.content_type,
            is_always_on=content.is_always_on,
            reward_coin=content.reward_coin,
            center_point=format_center_point(content),
            has_next_content=content.has_next_content
        )
        for content in contents
    ]

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_detail(
    content_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    콘텐츠 상세 정보 조회
    """
    
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    return ContentResponse(
        id=str(content.id),
        title=content.title,
        description=content.description,
        content_type=content.content_type,
        is_always_on=content.is_always_on,
        reward_coin=content.reward_coin,
        center_point=format_center_point(content),
        has_next_content=content.has_next_content,
        next_content_id=str(content.next_content_id) if content.next_content_id else None,
        created_at=content.created_at,
        start_at=content.start_at,
        end_at=content.end_at,
        stage_count=content.stage_count,
        is_sequential=content.is_sequential,
        is_open=content.is_open
    )

@router.get("/{content_id}/progress", response_model=ContentProgressResponse)
async def get_content_progress(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    내 콘텐츠 진행상황 조회
    """
    
    # 콘텐츠 존재 확인
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 진행상황 조회
    progress_result = await db.execute(
        select(UserContentProgress).where(
            and_(
                UserContentProgress.user_id == current_user.id,
                UserContentProgress.content_id == content_id
            )
        )
    )
    progress = progress_result.scalar_one_or_none()
    
    if not progress:
        return ContentProgressResponse(
            status="not_started",
            total_play_minutes=0
        )
    
    return ContentProgressResponse(
        status=progress.status,
        joined_at=progress.joined_at,
        cleared_at=progress.cleared_at,
        last_stage_no=progress.last_stage_no,
        total_play_minutes=progress.total_play_minutes or 0
    )

@router.post("/{content_id}/join", response_model=ContentJoinResponse)
async def join_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    콘텐츠 참여 시작
    """
    
    # 콘텐츠 존재 확인
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 콘텐츠가 오픈되어 있는지 확인
    if not content.is_open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content is not open"
        )
    
    # 콘텐츠 입장 가능 여부 확인
    now = datetime.utcnow()
    if not content.is_always_on:
        if content.start_at and content.start_at > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content has not started yet"
            )
        if content.end_at and content.end_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content has ended"
            )
    
    # 이미 참여했는지 확인
    existing_progress = await db.execute(
        select(UserContentProgress).where(
            and_(
                UserContentProgress.user_id == current_user.id,
                UserContentProgress.content_id == content_id
            )
        )
    )
    progress = existing_progress.scalar_one_or_none()
    
    if progress:
        return ContentJoinResponse(
            joined=True,
            status=progress.status
        )
    
    # 새로운 진행상황 생성
    new_progress = UserContentProgress(
        user_id=current_user.id,
        content_id=content_id,
        status="in_progress",
        joined_at=now
    )
    
    db.add(new_progress)
    await db.commit()
    
    return ContentJoinResponse(
        joined=True,
        status="in_progress"
    )

class StageListResponse(BaseModel):
    """스테이지 목록 응답 (lockState 포함)"""
    model_config = {"from_attributes": True}
    
    id: str
    stage_no: str
    title: str
    description: Optional[str] = None
    is_hidden: bool = False
    lock_state: str  # "locked" | "unlocked" | "in_progress" | "cleared"
    uses_nfc: bool = False

@router.get("/{content_id}/stages", response_model=List[StageListResponse])
async def get_content_stages(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    콘텐츠의 스테이지 목록 조회 (사용자의 잠금 상태 포함)
    
    - **content_id**: 콘텐츠 ID
    
    각 스테이지의 잠금 상태를 함께 반환합니다.
    """
    
    # 콘텐츠 존재 확인
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 사용자가 콘텐츠에 참여했는지 확인
    progress_result = await db.execute(
        select(UserContentProgress).where(
            and_(
                UserContentProgress.user_id == current_user.id,
                UserContentProgress.content_id == content_id
            )
        )
    )
    content_progress = progress_result.scalar_one_or_none()
    
    if not content_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not joined this content"
        )
    
    # 스테이지 목록 조회 (메인 스테이지만, parent_stage_id가 NULL인 것)
    stages_result = await db.execute(
        select(Stage)
        .where(
            and_(
                Stage.content_id == content_id,
                Stage.parent_stage_id.is_(None)  # 메인 스테이지만
            )
        )
        .order_by(Stage.stage_no)
    )
    stages = stages_result.scalars().all()
    
    # 사용자의 스테이지 진행상황 조회
    stage_ids = [str(stage.id) for stage in stages]
    user_progress_result = await db.execute(
        select(UserStageProgress).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id.in_(stage_ids)
            )
        )
    )
    user_stage_progress = {
        str(progress.stage_id): progress 
        for progress in user_progress_result.scalars().all()
    }
    
    # 응답 데이터 구성
    response_stages = []
    
    for stage in stages:
        stage_id = str(stage.id)
        progress = user_stage_progress.get(stage_id)
        
        # 잠금 상태 결정
        if progress:
            lock_state = progress.status
        else:
            # 진행상황이 없으면 기본적으로 locked
            # 첫 번째 스테이지이거나 이전 스테이지가 클리어된 경우 unlocked
            if stage.stage_no == "1":  # 첫 번째 스테이지
                lock_state = "unlocked"
            else:
                # 이전 스테이지들이 모두 클리어되었는지 확인하는 로직
                # 간단히 locked로 설정 (실제로는 더 복잡한 로직 필요)
                lock_state = "locked"
        
        # 히든 스테이지는 해금되지 않았으면 숨김
        if stage.is_hidden and lock_state == "locked":
            continue
        
        response_stages.append(StageListResponse(
            id=stage_id,
            stage_no=stage.stage_no,
            title=stage.title,
            description=stage.description,
            is_hidden=stage.is_hidden,
            lock_state=lock_state,
            uses_nfc=stage.uses_nfc
        ))
    
    return response_stages