from pydantic import BaseModel

class DashboardStatsResponse(BaseModel):
    """
    관리자 대시보드 상단 카드 4개 통계 응답 스키마
    """
    today_consumed_count: int  # 오늘 교환 건수
    total_consumed_count: int  # 누적 교환 건수
    total_points_spent: int    # 총 포인트 차감 (양수로 반환)
    low_stock_count: int       # 재고 임박 (10개 이하)
