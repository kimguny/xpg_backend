from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from typing import List, Optional
from datetime import datetime

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models import Content, UserContentProgress, User
from app.schemas.content import (
    ContentListResponse,
    ContentResponse,
    ContentProgressResponse,
    ContentJoinResponse
)

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