from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.api.deps import get_db, get_current_admin
from app.models import Content, Stage, StageHint, HintImage, StagePuzzle, StageUnlock, NFCTag
from app.schemas.stage import (
    StageCreate,
    StageUpdate,
    StageResponse,
    StageDetailResponse,
    HintCreate,
    HintResponse,
    HintImageUpdate,
    PuzzleConfig,
    UnlockConfig
)

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

def format_stage_response(stage: Stage) -> StageResponse:
    """Stage 모델을 StageResponse로 변환"""
    return StageResponse(
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
        created_at=stage.created_at
    )

@router.get("/by-content/{content_id}", response_model=List[StageDetailResponse]) # [1. 수정] StageResponse -> StageDetailResponse
async def get_stages_by_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    특정 콘텐츠에 속한 모든 스테이지 목록을 조회합니다.
    (힌트, 퍼즐, 해금 설정 포함)
    """
    
    # [2. 수정] 쿼리에 selectinload 옵션 추가 (Eager Loading)
    stmt = (
        select(Stage)
        .where(Stage.content_id == content_id)
        .options(
            # 힌트 로드 > 힌트의 NFC 로드, 힌트의 이미지 로드
            selectinload(Stage.hints).options(
                selectinload(StageHint.nfc),
                selectinload(StageHint.images)
            ),
            # 퍼즐 로드
            selectinload(Stage.puzzles),
            # 해금 설정 로드
            selectinload(Stage.unlocks)
        )
        .order_by(Stage.stage_no)
    )
    result = await db.execute(stmt)
    # .unique()를 추가하여 중복 방지
    stages = result.scalars().unique().all()

    # [3. 수정] 반환 로직을 StageDetailResponse에 맞게 수정
    response_list = []
    for stage in stages:
        # --- 힌트 포맷팅 (get_stage 함수 로직 재사용) ---
        hints_response = []
        if stage.hints:
            sorted_hints = sorted(stage.hints, key=lambda h: h.order_no)
            for hint in sorted_hints:
                nfc_info = None
                if hint.nfc:
                    nfc_info = {"id": str(hint.nfc.id), "udid": hint.nfc.udid, "tag_name": hint.nfc.tag_name}
                
                image_list = []
                if hint.images:
                    sorted_images = sorted(hint.images, key=lambda img: img.order_no)
                    image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in sorted_images]

                hints_response.append(HintResponse(
                    id=str(hint.id), stage_id=str(hint.stage_id), preset=hint.preset, order_no=hint.order_no,
                    text_block_1=hint.text_block_1, text_block_2=hint.text_block_2, text_block_3=hint.text_block_3,
                    cooldown_sec=hint.cooldown_sec, reward_coin=hint.reward_coin, nfc=nfc_info, images=image_list
                ))

        # --- 퍼즐 포맷팅 ---
        puzzles_response = []
        if stage.puzzles:
            puzzles_response = [
                {"id": str(p.id), "style": p.puzzle_style, "showWhen": p.show_when, "config": p.config} 
                for p in stage.puzzles
            ]

        # --- 해금 설정 포맷팅 ---
        unlock_config_response = None
        if stage.unlocks:
            unlock = stage.unlocks[0]
            unlock_config_response = {
                "preset": unlock.unlock_preset, "next_action": unlock.next_action,
                "image_url": unlock.image_url, "bottom_text": unlock.bottom_text
            }

        # --- 최종 StageDetailResponse 생성 ---
        response_list.append(StageDetailResponse(
            id=str(stage.id), content_id=str(stage.content_id), parent_stage_id=str(stage.parent_stage_id) if stage.parent_stage_id else None,
            stage_no=stage.stage_no, title=stage.title, description=stage.description, start_button_text=stage.start_button_text,
            uses_nfc=stage.uses_nfc, is_hidden=stage.is_hidden, time_limit_min=stage.time_limit_min,
            clear_need_nfc_count=stage.clear_need_nfc_count, clear_time_attack_sec=stage.clear_time_attack_sec,
            location=format_location(stage), unlock_on_enter_radius=stage.unlock_on_enter_radius,
            is_open=stage.is_open, unlock_stage_id=str(stage.unlock_stage_id) if stage.unlock_stage_id else None,
            background_image_url=stage.background_image_url, thumbnail_url=stage.thumbnail_url,
            meta=stage.meta, created_at=stage.created_at,
            
            # 연관 데이터 포함
            hints=hints_response,
            puzzles=puzzles_response,
            unlock_config=unlock_config_response
        ))
        
    return response_list

@router.post("", response_model=StageResponse)
async def create_stage(
    content_id: str,
    stage_data: StageCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    스테이지 생성
    """
    
    # 콘텐츠 존재 확인
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 동일한 stage_no 중복 확인
    existing_stage = await db.execute(
        select(Stage).where(
            and_(
                Stage.content_id == content_id,
                Stage.stage_no == stage_data.stage_no
            )
        )
    )
    if existing_stage.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stage with stage_no '{stage_data.stage_no}' already exists"
        )
    
    # unlock_stage_id 검증 (같은 콘텐츠 내 스테이지여야 함)
    if stage_data.unlock_stage_id:
        unlock_stage_result = await db.execute(
            select(Stage).where(
                and_(
                    Stage.id == stage_data.unlock_stage_id,
                    Stage.content_id == content_id
                )
            )
        )
        if not unlock_stage_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unlock_stage_id must belong to the same content"
            )
    
    # PostGIS POINT 생성 (위치가 있는 경우)
    location_sql = None
    if stage_data.location:
        location_sql = text(f"ST_GeogFromText('POINT({stage_data.location.lon} {stage_data.location.lat})')")
    
    # 스테이지 생성
    stage = Stage(
        content_id=content_id,
        stage_no=stage_data.stage_no,
        title=stage_data.title,
        description=stage_data.description,
        start_button_text=stage_data.start_button_text,
        is_hidden=stage_data.is_hidden,
        time_limit_min=stage_data.time_limit_min,
        clear_need_nfc_count=stage_data.clear_need_nfc_count,
        clear_time_attack_sec=stage_data.clear_time_attack_sec,
        location=location_sql,
        radius_m=stage_data.location.radius_m if stage_data.location else None,
        unlock_on_enter_radius=stage_data.unlock_on_enter_radius,
        unlock_stage_id=stage_data.unlock_stage_id,
        background_image_url=stage_data.background_image_url,
        thumbnail_url=stage_data.thumbnail_url,
        meta=stage_data.meta
    )
    
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    
    return format_stage_response(stage)

@router.patch("/{stage_id}", response_model=StageResponse)
async def update_stage(
    stage_id: str,
    stage_data: StageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    스테이지 수정
    """
    
    result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # unlock_stage_id 검증
    if stage_data.unlock_stage_id:
        unlock_stage_result = await db.execute(
            select(Stage).where(
                and_(
                    Stage.id == stage_data.unlock_stage_id,
                    Stage.content_id == stage.content_id
                )
            )
        )
        if not unlock_stage_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unlock_stage_id must belong to the same content"
            )
    
    # 수정할 필드들 업데이트
    update_data = stage_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(stage, field, value)
    
    await db.commit()
    await db.refresh(stage)
    
    return format_stage_response(stage)

@router.get("/{stage_id}", response_model=StageDetailResponse)  # ◀◀◀ [수정] StageResponse -> StageDetailResponse
async def get_stage(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    ID로 특정 스테이지의 상세 정보를 조회합니다.
    (힌트, 퍼즐, 해금 설정 포함)
    """
    
    # ◀◀◀ [수정] 쿼리에 selectinload 옵션 추가
    stmt = (
        select(Stage)
        .where(Stage.id == stage_id)
        .options(
            # 힌트 로드 > 힌트의 NFC 로드, 힌트의 이미지 로드
            selectinload(Stage.hints).options(
                selectinload(StageHint.nfc),
                selectinload(StageHint.images)
            ),
            # 퍼즐 로드
            selectinload(Stage.puzzles),
            # 해금 설정 로드
            selectinload(Stage.unlocks)
        )
    )
    result = await db.execute(stmt)
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # ◀◀◀ [추가] StageDetailResponse에 맞게 힌트, 퍼즐, 해금 설정 포맷팅

    # 1. 힌트 포맷팅 (get_hints_by_stage 로직 재사용)
    hints_response = []
    if stage.hints:
        # 힌트를 order_no 순서로 정렬
        sorted_hints = sorted(stage.hints, key=lambda h: h.order_no)
        for hint in sorted_hints:
            nfc_info = None
            if hint.nfc:  # Eager Loading으로 .nfc 바로 접근
                nfc_info = {
                    "id": str(hint.nfc.id),
                    "udid": hint.nfc.udid,
                    "tag_name": hint.nfc.tag_name
                }
            
            image_list = []
            if hint.images: # Eager Loading으로 .images 바로 접근
                # 이미지 order_no 순서로 정렬
                sorted_images = sorted(hint.images, key=lambda img: img.order_no)
                image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in sorted_images]

            hints_response.append(HintResponse(
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
                images=image_list
            ))

    # 2. 퍼즐 포맷팅 (puzzles가 리스트라고 가정)
    puzzles_response = []
    if stage.puzzles:
        puzzles_response = [
            {
                "id": str(puzzle.id), 
                "style": puzzle.puzzle_style,
                "showWhen": puzzle.show_when, # 스키마는 show_when이지만 모델은 show_when (확인 필요)
                "config": puzzle.config
            } for puzzle in stage.puzzles
        ]

    # 3. 해금 설정 포맷팅 (하나만 존재한다고 가정)
    unlock_config_response = None
    if stage.unlocks:
        unlock = stage.unlocks[0] # 첫 번째 해금 설정을 사용
        unlock_config_response = {
            "preset": unlock.unlock_preset,
            "next_action": unlock.next_action,
            "title": unlock.title,
            "image_url": unlock.image_url,
            "bottom_text": unlock.bottom_text
        }
    
    # 4. 최종 StageDetailResponse 반환
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
        
        # 연관 데이터 추가
        hints=hints_response,
        puzzles=puzzles_response,
        unlock_config=unlock_config_response
    )

@router.get("/{stage_id}/hints", response_model=List[HintResponse])
async def get_hints_by_stage(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    특정 스테이지에 속한 모든 힌트 목록을 조회합니다.
    """
    # 힌트 목록을 order_no 순서로 가져옵니다.
    result = await db.execute(
        select(StageHint)
        .where(StageHint.stage_id == stage_id)
        .order_by(StageHint.order_no)
    )
    hints = result.scalars().all()

    response_list = []
    for hint in hints:
        # 각 힌트에 연결된 NFC 태그 정보를 가져옵니다.
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
        
        # 각 힌트에 연결된 이미지 정보를 가져옵니다.
        images_result = await db.execute(select(HintImage).where(HintImage.hint_id == hint.id).order_by(HintImage.order_no))
        images = images_result.scalars().all()
        image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in images]

        # 최종 응답 객체를 만듭니다.
        response_list.append(HintResponse(
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
            images=image_list
        ))
        
    return response_list

@router.post("/{stage_id}/hints", response_model=HintResponse)
async def create_hint(
    stage_id: str,
    hint_data: HintCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    힌트 생성 + NFC 바인딩
    """
    
    # 스테이지 존재 확인
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # NFC 태그 존재 확인 (지정된 경우)
    nfc_tag = None
    if hint_data.nfc_id:
        nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == hint_data.nfc_id))
        nfc_tag = nfc_result.scalar_one_or_none()
        
        if not nfc_tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFC tag not found"
            )
        
        # 동일한 스테이지 내 NFC 중복 확인
        existing_hint = await db.execute(
            select(StageHint).where(
                and_(
                    StageHint.stage_id == stage_id,
                    StageHint.nfc_id == hint_data.nfc_id
                )
            )
        )
        if existing_hint.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NFC tag already bound to another hint in this stage"
            )
    
    # 힌트 생성
    hint = StageHint(
        stage_id=stage_id,
        preset=hint_data.preset,
        order_no=hint_data.order_no,
        text_block_1=hint_data.text_blocks[0] if len(hint_data.text_blocks) > 0 else None,
        text_block_2=hint_data.text_blocks[1] if len(hint_data.text_blocks) > 1 else None,
        text_block_3=hint_data.text_blocks[2] if len(hint_data.text_blocks) > 2 else None,
        cooldown_sec=hint_data.cooldown_sec,
        reward_coin=hint_data.reward_coin,
        nfc_id=hint_data.nfc_id
    )
    
    db.add(hint)
    await db.commit()
    await db.refresh(hint)
    
    # 응답 데이터 구성
    nfc_info = None
    if nfc_tag:
        nfc_info = {
            "id": str(nfc_tag.id),
            "udid": nfc_tag.udid,
            "tag_name": nfc_tag.tag_name
        }
    
    return HintResponse(
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
        images=[]  # 이미지는 별도 API로 관리
    )

@router.put("/{hint_id}/images")
async def update_hint_images(
    hint_id: str,
    image_data: HintImageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    힌트 이미지 일괄 교체
    """
    
    # 힌트 존재 확인
    hint_result = await db.execute(select(StageHint).where(StageHint.id == hint_id))
    hint = hint_result.scalar_one_or_none()
    
    if not hint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hint not found"
        )
    
    # 기존 이미지 모두 삭제
    await db.execute(delete(HintImage).where(HintImage.hint_id == hint_id))
    
    # 새 이미지들 추가
    for img_data in image_data.images:
        image = HintImage(
            hint_id=hint_id,
            order_no=img_data.get("order_no", 1),
            url=img_data.get("url", ""),
            alt_text=img_data.get("alt", "")
        )
        db.add(image)
    
    await db.commit()
    
    return {
        "hint_id": hint_id,
        "images": image_data.images
    }

@router.put("/{stage_id}/puzzles")
async def update_stage_puzzles(
    stage_id: str,
    puzzle_data: PuzzleConfig,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    퍼즐 설정 (Upsert)
    """
    
    # 스테이지 존재 확인
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 기존 퍼즐 모두 삭제
    await db.execute(delete(StagePuzzle).where(StagePuzzle.stage_id == stage_id))
    
    # 새 퍼즐들 추가
    created_puzzles = []
    for puzzle_config in puzzle_data.puzzles:
        puzzle = StagePuzzle(
            stage_id=stage_id,
            puzzle_style=puzzle_config.get("style", ""),
            show_when=puzzle_config.get("show_when", "always"),
            config=puzzle_config.get("config", {})
        )
        db.add(puzzle)
        await db.flush()
        
        created_puzzles.append({
            "id": str(puzzle.id),
            "style": puzzle.puzzle_style,
            "show_when": puzzle.show_when,
            "config": puzzle.config
        })
    
    await db.commit()
    
    return {
        "stage_id": stage_id,
        "puzzles": created_puzzles
    }

@router.put("/{stage_id}/unlock")
async def update_unlock_config(
    stage_id: str,
    unlock_data: UnlockConfig,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    클리어 연출 설정
    """
    
    # 스테이지 존재 확인
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    # 기존 해금 설정 삭제
    await db.execute(delete(StageUnlock).where(StageUnlock.stage_id == stage_id))
    
    # 새 해금 설정 생성
    unlock_config = StageUnlock(
        stage_id=stage_id,
        unlock_preset=unlock_data.preset,
        next_action=unlock_data.next_action,
        title=unlock_data.title,
        image_url=unlock_data.image_url,
        bottom_text=unlock_data.bottom_text
    )
    
    db.add(unlock_config)
    await db.commit()
    await db.refresh(unlock_config)
    
    return {
        "stage_id": stage_id,
        "unlock": {
            "preset": unlock_config.unlock_preset,
            "next_action": unlock_config.next_action,
            "image_url": unlock_config.image_url,
            "bottom_text": unlock_config.bottom_text
        }
    }