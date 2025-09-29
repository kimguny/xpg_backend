from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

from app.api.deps import get_db, get_current_user
from app.models import Stage, StageHint, HintImage, StagePuzzle, StageUnlock, User, UserStageProgress, NFCTag
from app.schemas.stage import StageDetailResponse, HintResponse

router = APIRouter()

def format_location(stage: Stage) -> Optional[dict]:
    """geography 타입의 location을 dict로 변환"""
    if not stage.location:
        return None
    
    try:
        result = {
            "lon": float(stage.location.longitude) if hasattr(stage.location, 'longitude') else 0.0,
            "lat": float(stage.location.latitude) if hasattr(stage.location, 'latitude') else 0.0
        }
        if stage.radius_m:
            result["radius_m"] = stage.radius_m
        return result
    except:
        return None

@router.get("/{stage_id}", response_model=StageDetailResponse)
async def get_stage_detail(
    stage_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    스테이지 상세 정보 조회 (힌트/이미지/퍼즐 포함)
    """
    
    # 스테이지 조회
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 사용자가 해당 콘텐츠에 참여했는지 확인
    from app.models import UserContentProgress
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
    
    # 사용자의 스테이지 진행상황 확인
    stage_progress_result = await db.execute(
        select(UserStageProgress).where(
            and_(
                UserStageProgress.user_id == current_user.id,
                UserStageProgress.stage_id == stage_id
            )
        )
    )
    stage_progress = stage_progress_result.scalar_one_or_none()
    
    # 스테이지가 잠금 상태이고 히든이면 접근 불가
    if stage.is_hidden and (not stage_progress or stage_progress.status == "locked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Stage is locked"
        )
    
    # 힌트 조회
    hints_result = await db.execute(
        select(StageHint).where(StageHint.stage_id == stage_id).order_by(StageHint.order_no)
    )
    hints = hints_result.scalars().all()
    
    # 힌트별 이미지와 NFC 정보 조회
    hint_responses = []
    for hint in hints:
        # 힌트 이미지 조회
        images_result = await db.execute(
            select(HintImage).where(HintImage.hint_id == hint.id).order_by(HintImage.order_no)
        )
        images = images_result.scalars().all()
        
        # NFC 정보 조회
        nfc_info = None
        if hint.nfc_id:
            nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == hint.nfc_id))
            nfc_tag = nfc_result.scalar_one_or_none()
            if nfc_tag:
                nfc_info = {
                    "id": str(nfc_tag.id),
                    "udid": nfc_tag.udid,
                    "tag_name": nfc_tag.tag_name
                }
        
        hint_responses.append(HintResponse(
            id=str(hint.id),
            stage_id=str(hint.stage_id),
            preset=hint.preset,
            order_no=hint.order_no,
            text_block_1=hint.text_block_1,
            text_block_2=hint.text_block_2,
            text_block_3=hint.text_block_3,
            cooldown_sec=hint.cooldown_sec,
            reward_coin=hint.reward_coin,
            nfc=nfc_info,
            images=[
                {
                    "url": img.url,
                    "alt": img.alt_text,
                    "order_no": img.order_no
                }
                for img in images
            ]
        ))
    
    # 퍼즐 조회
    puzzles_result = await db.execute(
        select(StagePuzzle).where(StagePuzzle.stage_id == stage_id)
    )
    puzzles = puzzles_result.scalars().all()
    
    puzzle_list = [
        {
            "style": puzzle.puzzle_style,
            "show_when": puzzle.show_when,
            "config": puzzle.config
        }
        for puzzle in puzzles
    ]
    
    # 해금 연출 설정 조회
    unlock_result = await db.execute(
        select(StageUnlock).where(StageUnlock.stage_id == stage_id)
    )
    unlock_config = unlock_result.scalar_one_or_none()
    
    unlock_info = None
    if unlock_config:
        unlock_info = {
            "preset": unlock_config.unlock_preset,
            "next_action": unlock_config.next_action,
            "image_url": unlock_config.image_url,
            "bottom_text": unlock_config.bottom_text
        }
    
    # 응답 데이터 구성
    return StageDetailResponse(
        id=str(stage.id),
        content_id=str(stage.content_id),
        parent_stage_id=str(stage.parent_stage_id) if stage.parent_stage_id else None,
        stage_no=stage.stage_no,
        title=stage.title,
        description=stage.description,
        start_button_text=stage.start_button_text,
        uses_nfc=stage.uses_nfc,
        is_hidden=stage.is_hidden,
        time_limit_min=stage.time_limit_min,
        clear_need_nfc_count=stage.clear_need_nfc_count,
        clear_time_attack_sec=stage.clear_time_attack_sec,
        location=format_location(stage),
        unlock_on_enter_radius=stage.unlock_on_enter_radius,
        is_open=stage.is_open,
        unlock_stage_id=str(stage.unlock_stage_id) if stage.unlock_stage_id else None,
        background_image_url=stage.background_image_url,
        thumbnail_url=stage.thumbnail_url,
        meta=stage.meta,
        created_at=stage.created_at,
        hints=hint_responses,
        puzzles=puzzle_list,
        unlock_config=unlock_info
    )

@router.get("/{stage_id}/hints", response_model=List[HintResponse])
async def get_stage_hints(
    stage_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    스테이지 힌트 목록 조회
    """
    
    # 스테이지 존재 확인
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 사용자 권한 확인 (콘텐츠 참여 여부)
    from app.models import UserContentProgress
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
    
    # 힌트 조회
    hints_result = await db.execute(
        select(StageHint).where(StageHint.stage_id == stage_id).order_by(StageHint.order_no)
    )
    hints = hints_result.scalars().all()
    
    # 힌트별 NFC 정보 조회
    hint_responses = []
    for hint in hints:
        nfc_info = None
        if hint.nfc_id:
            nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == hint.nfc_id))
            nfc_tag = nfc_result.scalar_one_or_none()
            if nfc_tag:
                nfc_info = {
                    "id": str(nfc_tag.id),
                    "udid": nfc_tag.udid,
                    "tag_name": nfc_tag.tag_name
                }
        
        hint_responses.append(HintResponse(
            id=str(hint.id),
            stage_id=str(hint.stage_id),
            preset=hint.preset,
            order_no=hint.order_no,
            text_block_1=hint.text_block_1,
            text_block_2=hint.text_block_2,
            text_block_3=hint.text_block_3,
            cooldown_sec=hint.cooldown_sec,
            reward_coin=hint.reward_coin,
            nfc=nfc_info,
            images=[]  # 이미지는 상세 조회에서만 제공
        ))
    
    return hint_responses