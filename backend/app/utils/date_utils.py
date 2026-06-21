"""Date helpers."""

from datetime import datetime


def calculate_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return (end - start).days + 1


def validate_trip_dates(start_date: str, end_date: str, travel_days: int) -> None:
    actual_days = calculate_days(start_date, end_date)
    if actual_days <= 0:
        raise ValueError("结束日期不能早于开始日期")
    if actual_days != travel_days:
        raise ValueError(f"旅行天数应为 {actual_days}, 当前为 {travel_days}")
