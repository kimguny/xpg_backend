# app/utils/qr_generator.py
import qrcode
import os
import uuid
import json
import asyncio
from typing import Dict, Any

# QR 코드를 저장할 정적 파일 디렉토리
# 이 경로는 main.py에서 StaticFiles로 마운트되어야 합니다.
SAVE_DIR = "static/qrcodes"
# 서버에서 클라이언트로 반환할 URL 경로
BASE_URL_PATH = "/static/qrcodes"

def _generate_and_save_qr(data_str: str, filename: str) -> str:
    """
    [동기 함수] QR 코드를 생성하고 파일 시스템에 저장합니다.
    I/O 작업이므로 asyncio.to_thread로 호출되어야 합니다.
    """
    try:
        # 1. 저장 디렉토리 생성 (없을 경우)
        os.makedirs(SAVE_DIR, exist_ok=True)
        
        file_path = os.path.join(SAVE_DIR, filename)
        
        # 2. QR 코드 객체 생성
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data_str)
        qr.make(fit=True)

        # 3. 이미지 파일로 저장 (Pillow 사용)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(file_path)
        
        # 4. 웹 접근 가능 URL 반환
        url_path = f"{BASE_URL_PATH}/{filename}"
        return url_path

    except Exception as e:
        print(f"QR 코드 생성 실패: {e}")
        return None

async def generate_qr_code_image(data: Dict[str, Any], filename_prefix: str) -> str:
    """
    [비동기 래퍼] QR 코드 생성 I/O 작업을 별도 스레드에서 실행합니다.
    """
    # 1. QR 코드에 담을 데이터를 JSON 문자열로 변환
    data_str = json.dumps(data, ensure_ascii=False)
    
    # 2. 고유 파일명 생성
    unique_id = uuid.uuid4()
    filename = f"{filename_prefix}_{unique_id}.png"
    
    # 3. 동기 I/O 함수를 별도 스레드에서 실행 (asyncio 이벤트 루프 차단 방지)
    try:
        url_path = await asyncio.to_thread(_generate_and_save_qr, data_str, filename)
        if url_path is None:
            raise Exception("QR code generation failed in thread.")
        return url_path
    except Exception as e:
        # 실제 운영 환경에서는 로깅 필요
        print(f"Error in generate_qr_code_image: {e}")
        raise
