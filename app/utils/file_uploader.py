# app/utils/file_uploader.py
import aiofiles
import os
import uuid
from fastapi import UploadFile
from typing import Optional

# 파일을 저장할 기본 디렉토리 ('static' 폴더 내부)
SAVE_DIR = "static/uploads"
# 클라이언트에 반환할 기본 URL 경로
BASE_URL_PATH = "/static/uploads"

async def upload_file_to_storage(file: UploadFile, path_prefix: str) -> Optional[str]:
    """
    파일 저장소(로컬 'static/uploads')에 파일을 비동기적으로 저장하고 URL을 반환합니다.
    path_prefix: 'users/profile' 또는 'rewards/qr' 등
    """
    
    # 1. path_prefix를 포함한 전체 저장 경로 생성
    # 예: 'static/uploads/users/profile'
    full_save_dir = os.path.join(SAVE_DIR, path_prefix)
    
    try:
        # 2. 디렉토리 생성 (없을 경우)
        os.makedirs(full_save_dir, exist_ok=True)
        
        # 3. 고유한 파일명 생성 (보안 및 중복 방지)
        # 예: 'original.jpg' -> '.jpg'
        file_extension = os.path.splitext(file.filename)[1]
        # 예: 'some-uuid-string.jpg'
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        file_path = os.path.join(full_save_dir, unique_filename)
        
        # 4. 파일 비동기 쓰기 (대용량 파일을 위해 청크 단위로)
        async with aiofiles.open(file_path, 'wb') as f:
            while content := await file.read(1024 * 1024): # 1MB 청크
                await f.write(content)
                
        # 5. 웹 접근 가능 URL 반환
        # 예: '/static/uploads/users/profile/some-uuid-string.jpg'
        url_path = f"{BASE_URL_PATH}/{path_prefix}/{unique_filename}"
        return url_path

    except Exception as e:
        # 실제 운영 환경에서는 로깅 필요
        print(f"파일 업로드 실패: {e}")
        return None