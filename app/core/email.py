# app/core/email.py

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.core.config import settings
from typing import Optional

# 1. config.py의 설정을 기반으로 ConnectionConfig 생성
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_TLS=settings.MAIL_TLS,
    MAIL_SSL=settings.MAIL_SSL,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

# 2. 임시 비밀번호 발송 함수
async def send_temp_password_email(
    email_to: str, 
    nickname: Optional[str], 
    temp_password: str
):
    """임시 비밀번호를 이메일로 발송합니다."""
    
    # 이메일 제목
    subject = "[XPG] 임시 비밀번호가 발급되었습니다."
    
    # 이메일 본문 (HTML)
    body = f"""
    <html>
    <body>
        <p>안녕하세요, {nickname or 'XPG 회원'}님.</p>
        <p>요청하신 임시 비밀번호가 발급되었습니다.</p>
        <p>아래 비밀번호로 로그인하신 후, 즉시 '내 정보 수정'에서 새 비밀번호로 변경해 주세요.</p>
        <br>
        <p style="font-size: 24px; font-weight: bold; color: #333;">
            {temp_password}
        </p>
        <br>
        <p>감사합니다.</p>
    </body>
    </html>
    """

    # 메시지 객체 생성
    message = MessageSchema(
        subject=subject,
        recipients=[email_to],  # 받는 사람
        body=body,
        subtype="html"  # HTML 형식으로 발송
    )

    # 메일 발송
    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        # (실제 프로덕션에서는 print 대신 logging 사용)
        print(f"Failed to send email to {email_to}: {e}")
        # 이메일 발송 실패 시에도, API 자체는 오류를 반환하지 않아야
        # (이메일 열거 공격 방지)
        pass