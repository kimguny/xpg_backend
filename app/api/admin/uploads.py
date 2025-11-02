import aiofiles
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.api.deps import get_current_admin
from app.models import Admin
from pydantic import BaseModel

# 업로드 설정
# TODO: 이 경로는 실제 서버의 Nginx/CDN과 연결된 정적 파일 제공 경로여야 합니다.
UPLOAD_DIR = Path("/var/www/xpg/uploads/images") 
# UPLOAD_DIR에 저장된 파일에 접근하기 위한 웹 경로 (예: /media/images/)
MEDIA_URL_PREFIX = "/media/images" 

router = APIRouter()

class UploadResponse(BaseModel):
    """이미지 업로드 응답"""
    file_path: str # 웹에서 접근 가능한 상대 경로 (예: /media/images/filename.png)
    file_name: str
    content_type: str
    size: int

@router.post(
    "/uploads/image", 
    response_model=UploadResponse,
    summary="[신규] 관리자용 범용 이미지 업로드 (상품, 프로필 등)"
)
async def upload_admin_image(
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 패널에서 사용되는 이미지를 업로드합니다.
    (상품, 프로필, 맵 이미지 등)
    """
    
    # 디렉토리 존재 확인 및 생성
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # 파일 MIME 타입 검증
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only JPG, PNG, GIF are allowed."
        )
        
    # 파일 확장자 추출
    file_extension = Path(file.filename).suffix.lower()
    if not file_extension:
        file_extension = ".jpg" if file.content_type == "image/jpeg" else ".png"

    # 고유 파일명 생성
    file_name = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / file_name
    
    # 파일 비동기 저장
    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
            file_size = len(content)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {e}"
        )
    
    # 웹 접근 경로 반환
    web_file_path = f"{MEDIA_URL_PREFIX}/{file_name}"
    
    return UploadResponse(
        file_path=web_file_path,
        file_name=file.filename,
        content_type=file.content_type,
        size=file_size
    )
