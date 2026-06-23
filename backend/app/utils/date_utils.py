"""日期处理工具函数。

这个模块专门处理旅行日期相关的公共逻辑，避免在路由、服务或图流程中重复编写日期计算代码。
当前主要提供两个能力：
1. 根据开始日期和结束日期计算旅行天数；
2. 校验用户填写的旅行天数是否与日期范围一致。
"""

from datetime import datetime


# 项目中统一使用 YYYY-MM-DD 格式的日期字符串，例如 2026-07-01。
DATE_FORMAT = "%Y-%m-%d"


def calculate_days(start_date: str, end_date: str) -> int:
    """计算旅行总天数。

    参数 start_date 和 end_date 都是字符串格式日期，例如：
    start_date = "2026-07-01"
    end_date = "2026-07-03"

    这里返回 3，而不是 2，因为旅行日期通常包含开始当天和结束当天。
    """
    # 将字符串日期转换成 datetime 对象，方便做日期差计算。
    start = datetime.strptime(start_date, DATE_FORMAT)
    end = datetime.strptime(end_date, DATE_FORMAT)

    # (end - start).days 只计算两个日期之间相隔多少天；
    # 旅行场景需要包含开始日和结束日，所以最后要 +1。
    return (end - start).days + 1


def validate_trip_dates(start_date: str, end_date: str, travel_days: int) -> None:
    """校验旅行日期和旅行天数是否匹配。

    这个函数通常用于处理前端提交的旅行规划请求：
    - 如果结束日期早于开始日期，直接抛出错误；
    - 如果用户填写的 travel_days 与日期范围计算出的天数不一致，也抛出错误。

    函数没有返回值，校验通过时什么都不做；校验失败时抛出 ValueError。
    """
    # 先根据开始日期和结束日期计算实际旅行天数。
    actual_days = calculate_days(start_date, end_date)

    # actual_days <= 0 表示结束日期在开始日期之前，属于非法日期范围。
    if actual_days <= 0:
        raise ValueError("结束日期不能早于开始日期")

    # 用户填写的 travel_days 必须和日期范围推导出的天数一致。
    # 这样可以避免前端传入 "7月1日到7月3日，但旅行天数填 5 天" 这种矛盾数据。
    if actual_days != travel_days:
        raise ValueError(f"旅行天数应为 {actual_days}, 当前为 {travel_days}")
