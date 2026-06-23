"""请求与响应数据模型。

这个文件集中定义后端 API 的数据结构，主要用于三类场景：
1. 接收前端请求时校验参数格式；
2. 约束后端内部生成的旅行计划结构；
3. 统一 API 返回给前端的数据格式。

所有模型都继承自 Pydantic 的 BaseModel，FastAPI 会利用这些模型自动完成：
- 请求参数校验；
- 响应数据序列化；
- Swagger / ReDoc 接口文档生成。
"""

from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    """旅行规划请求模型。

    前端点击“生成行程”时，会把用户填写的目的地、日期、交通、住宿、偏好等信息
    按照这个结构发送给后端。
    """

    city: str = Field(..., description="目的地城市", examples=["北京"])
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", examples=["2026-07-01"])
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", examples=["2026-07-03"])

    # ge=1 表示最少 1 天，le=30 表示最多 30 天，避免用户提交不合理的旅行天数。
    travel_days: int = Field(..., ge=1, le=30, description="旅行天数")

    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿偏好")

    # default_factory=list 可以避免多个请求共享同一个默认列表对象。
    preferences: List[str] = Field(default_factory=list, description="旅行偏好标签")
    free_text_input: Optional[str] = Field(default="", description="额外要求")


class POISearchRequest(BaseModel):
    """POI 搜索请求模型。

    POI 是 Point of Interest 的缩写，通常指景点、餐厅、酒店、商圈等兴趣点。
    """

    keywords: str = Field(..., description="搜索关键词")
    city: str = Field(..., description="城市")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    """路线规划请求模型。

    用于描述从起点到终点的路线规划参数，例如步行、驾车或公交路线。
    """

    origin_address: str = Field(..., description="起点地址")
    destination_address: str = Field(..., description="终点地址")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="walking/driving/transit")


class Location(BaseModel):
    """地理坐标模型。

    用经度和纬度表示地图上的一个位置。
    多个业务模型会复用这个结构，例如景点、餐厅、酒店、POI 等。
    """

    longitude: float
    latitude: float


class Attraction(BaseModel):
    """景点模型。

    表示旅行计划中的一个景点，包含名称、地址、坐标、游玩时长、图片、票价等信息。
    """

    name: str
    address: str
    location: Location
    visit_duration: int
    description: str
    category: Optional[str] = "景点"
    rating: Optional[float] = None

    # 使用 default_factory=list，确保每个景点都有独立的照片列表。
    photos: Optional[List[str]] = Field(default_factory=list)
    poi_id: Optional[str] = ""
    image_url: Optional[str] = None
    ticket_price: int = 0


class Meal(BaseModel):
    """餐饮信息模型。

    表示某一天行程中的早餐、午餐、晚餐或推荐餐厅。
    """

    type: str
    name: str
    address: Optional[str] = None
    location: Optional[Location] = None
    description: Optional[str] = None
    estimated_cost: int = 0


class Hotel(BaseModel):
    """酒店信息模型。

    表示行程中推荐的住宿地点，包括价格区间、评分、距离等展示信息。
    """

    name: str
    address: str = ""
    location: Optional[Location] = None
    price_range: str = ""
    rating: str = ""
    distance: str = ""
    type: str = ""
    estimated_cost: int = 0


class DayPlan(BaseModel):
    """单日行程模型。

    一个 DayPlan 表示旅行中的某一天安排，包含当天描述、交通、住宿、景点和餐饮。
    """

    date: str
    day_index: int
    description: str
    transportation: str
    accommodation: str
    hotel: Optional[Hotel] = None

    # 景点和餐饮都可能有多个，因此使用列表保存。
    attractions: List[Attraction] = Field(default_factory=list)
    meals: List[Meal] = Field(default_factory=list)


class WeatherInfo(BaseModel):
    """天气信息模型。

    用于保存某一天的白天天气、夜间天气、温度、风向和风力等信息。
    高德天气接口返回的温度有时可能是字符串，因此下面提供了温度清洗逻辑。
    """

    date: str
    day_weather: str = ""
    night_weather: str = ""
    day_temp: Union[int, str] = 0
    night_temp: Union[int, str] = 0
    wind_direction: str = ""
    wind_power: str = ""

    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, value):
        """将温度字段统一转换为整数。

        外部天气接口可能返回 "25°C"、"25℃"、"25°" 或数字 25。
        前端展示和预算/建议逻辑更适合使用统一的整数温度，所以这里提前清洗。
        """
        if isinstance(value, str):
            # 去掉常见温度单位，只保留数字部分。
            cleaned = value.replace("°C", "").replace("℃", "").replace("°", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                # 如果无法转换，例如返回 "未知"，则用 0 兜底，避免接口整体报错。
                return 0
        return value


class Budget(BaseModel):
    """预算汇总模型。

    用于保存景点、酒店、餐饮、交通等费用估算，并计算总预算。
    """

    total_attractions: int = 0
    total_hotels: int = 0
    total_meals: int = 0
    total_transportation: int = 0
    total: int = 0


class TripPlan(BaseModel):
    """完整旅行计划模型。

    这是 AI 生成行程后返回给前端的核心数据结构，包含城市、日期、每日行程、天气、建议和预算。
    """

    city: str
    start_date: str
    end_date: str
    days: List[DayPlan]
    weather_info: List[WeatherInfo] = Field(default_factory=list)
    overall_suggestions: str
    budget: Optional[Budget] = None


class TripPlanResponse(BaseModel):
    """旅行规划接口响应模型。

    /api/trip/plan 接口会使用该模型统一返回生成结果。
    """

    success: bool
    message: str = ""
    data: Optional[TripPlan] = None


class POIInfo(BaseModel):
    """POI 信息模型。

    表示一个地图兴趣点，通常来自高德地图搜索结果。
    """

    id: str
    name: str
    type: str = ""
    address: str = ""
    location: Location
    tel: Optional[str] = None


class POISearchResponse(BaseModel):
    """POI 搜索响应模型。"""

    success: bool
    message: str = ""
    data: List[POIInfo] = Field(default_factory=list)


class RouteInfo(BaseModel):
    """路线规划结果模型。

    保存路线距离、耗时、路线类型和文字说明。
    """

    distance: float
    duration: int
    route_type: str
    description: str


class RouteResponse(BaseModel):
    """路线规划接口响应模型。"""

    success: bool
    message: str = ""
    data: Optional[RouteInfo] = None


class WeatherResponse(BaseModel):
    """天气查询接口响应模型。"""

    success: bool
    message: str = ""
    data: List[WeatherInfo] = Field(default_factory=list)


class POIDetailResponse(BaseModel):
    """POI 详情接口响应模型。

    data 使用 dict，是因为外部地图服务返回的详情字段可能比较灵活，
    不一定能完全固定成一个严格的模型。
    """

    success: bool
    message: str = ""
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """统一错误响应模型。

    当接口调用失败时，可以用该模型返回错误信息和错误码。
    """

    success: bool = False
    message: str
    error_code: Optional[str] = None
