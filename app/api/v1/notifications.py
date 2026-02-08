from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from datetime import datetime, timezone

from app.api.deps import get_db
from app.models import Notification
from app.schemas.notification import NotificationAppResponse

router = APIRouter()


@router.get("", response_model=List[NotificationAppResponse])
async def get_notifications_app(
    db: AsyncSession = Depends(get_db)
):
    """
    앱 사용자용 공지사항 목록 조회
    - 게시 중인 공지사항만 반환 (status = 'published')
    - 현재 시간이 start_at ~ end_at 범위 내
    - 간소화된 필드만 반환
    """
    now = datetime.now(timezone.utc)
    
    query = select(Notification).where(
        and_(
            Notification.status == 'published',
            Notification.start_at <= now,
            Notification.end_at >= now
        )
    ).order_by(Notification.created_at.desc())
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [NotificationAppResponse.model_validate(n) for n in notifications]


@router.get("/{notification_id}", response_model=NotificationAppResponse)
async def get_notification_detail_app(
    notification_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    앱 사용자용 공지사항 상세 조회
    - 조회 시 view_count 증가
    """
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    # 조회수 증가
    notification.view_count += 1
    await db.commit()
    await db.refresh(notification)
    
    return NotificationAppResponse.model_validate(notification)