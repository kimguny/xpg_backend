from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
from datetime import datetime, timezone

from app.api.deps import get_db, get_current_admin
from app.models import Notification
from app.schemas.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


def calculate_status(start_at: datetime, end_at: datetime, is_draft: bool = False) -> str:
    """공지사항 상태 계산"""
    if is_draft:
        return 'draft'
    
    now = datetime.now(timezone.utc)
    if now < start_at:
        return 'scheduled'
    elif start_at <= now <= end_at:
        return 'published'
    else:
        return 'expired'


@router.post("", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """공지사항 생성"""
    # 상태 자동 계산
    status_value = calculate_status(
        notification_data.start_at, 
        notification_data.end_at, 
        notification_data.is_draft
    )
    
    notification = Notification(
        title=notification_data.title,
        content=notification_data.content,
        notification_type=notification_data.notification_type,
        start_at=notification_data.start_at,
        end_at=notification_data.end_at,
        status=status_value,
        show_popup_on_app_start=notification_data.show_popup_on_app_start
    )
    
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    
    return NotificationResponse.model_validate(notification)


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: str,
    notification_data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """공지사항 수정"""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    update_data = notification_data.model_dump(exclude_unset=True)
    
    # is_draft 제거 (상태 계산에만 사용)
    is_draft = update_data.pop("is_draft", None)
    
    # 필드 업데이트
    for field, value in update_data.items():
        setattr(notification, field, value)
    
    # 상태 재계산 (날짜나 is_draft가 변경된 경우)
    if any(key in update_data for key in ['start_at', 'end_at']) or is_draft is not None:
        notification.status = calculate_status(
            notification.start_at,
            notification.end_at,
            is_draft if is_draft is not None else notification.status == 'draft'
        )
    
    await db.commit()
    await db.refresh(notification)
    
    return NotificationResponse.model_validate(notification)


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def get_notifications_admin(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="draft|scheduled|published|expired|all"),
    notification_type: Optional[str] = Query(None, description="system|event|promotion"),
    search: Optional[str] = Query(None, description="제목 검색"),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """공지사항 목록 조회 (관리자)"""
    query = select(Notification)
    count_query = select(func.count(Notification.id))
    conditions = []
    
    # 상태 필터
    if status and status != "all":
        conditions.append(Notification.status == status)
    
    # 유형 필터
    if notification_type:
        conditions.append(Notification.notification_type == notification_type)
    
    # 제목 검색
    if search:
        conditions.append(Notification.title.ilike(f"%{search}%"))
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # 전체 개수 조회
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # 페이지네이션
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Notification.created_at.desc())
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return PaginatedResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        page=page,
        size=size,
        total=total
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification_admin(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """공지사항 상세 조회 (관리자)"""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    return NotificationResponse.model_validate(notification)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """공지사항 삭제 (하드 삭제)"""
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    await db.delete(notification)
    await db.commit()
    
    return {"deleted": True, "notification_id": notification_id}