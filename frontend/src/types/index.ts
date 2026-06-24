// 前端核心类型定义
// 这些 interface 用来约束页面表单、后端接口响应、旅行规划结果展示之间的数据结构。
// 集中维护类型可以减少字段名不一致带来的运行时错误，也方便后续页面和 API 服务复用。

// 地理坐标类型，用于景点、餐厅、酒店等实体的位置描述。
// 后续接入地图组件或路线规划服务时，可以直接复用该结构。
export interface Location {
  longitude: number
  latitude: number
}

// 景点信息类型。
// 既包含行程展示必须使用的基础信息，也预留了评分、图片、门票等可选展示字段。
export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number
}

// 餐饮信息类型。
// type 使用联合字面量限制可选值，避免页面或接口中出现 breakfast/lunch/dinner/snack 之外的非法餐饮类别。
export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

// 酒店信息类型。
// location 和 estimated_cost 设为可选，是为了兼容只返回文本推荐、暂未返回精确坐标或价格估算的场景。
export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

// 预算汇总类型。
// 将景点、住宿、餐饮、交通拆开统计，便于结果页展示费用构成，也便于后续做预算图表。
export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

// 单日行程类型。
// 一个 DayPlan 表示旅行中的某一天，内部聚合当天的景点、餐饮、住宿和交通建议。
export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

// 天气信息类型。
// 按日期记录白天和夜间天气、温度、风向风力，供行程结果页给出穿衣和出行建议。
export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

// 完整旅行规划类型。
// 这是结果页最核心的数据结构，通常由后端智能规划接口生成后返回给前端展示。
export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
}

// 用户提交旅行规划表单时的数据类型。
// 该结构对应首页表单输入，也通常会作为调用后端规划接口的请求体。
export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

// 旅行规划接口响应类型。
// data 设为可选，是为了兼容接口失败时只返回 success 和 message、没有规划结果的情况。
export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
}

// 景点图片接口响应类型。
// photo_url 允许为 null，表示接口成功返回了景点名称，但没有找到可用图片。
export interface PhotoResponse {
  success: boolean
  message: string
  data: {
    name: string
    photo_url?: string | null
  }
}
