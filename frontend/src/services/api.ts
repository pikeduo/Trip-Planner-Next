import axios from 'axios'
import type { PhotoResponse, TripFormData, TripPlanResponse } from '@/types'

// 后端服务基础地址。
// 优先读取 Vite 环境变量，便于开发、测试、生产环境使用不同后端地址；如果没有配置，则默认连接本地后端。
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 创建统一的 axios 客户端。
// 所有前端接口请求都复用这个实例，便于集中维护 baseURL、超时时间、请求头和拦截器。
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // 旅行规划通常需要调用大模型、地图、天气等外部服务，耗时可能较长，因此这里设置为 2 分钟超时。
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器。
// 在请求发出前统一记录方法和路径，方便开发阶段排查接口是否被正确调用。
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器。
// 在响应返回后统一记录状态码和接口路径，错误场景则继续抛出给具体业务函数处理。
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

/**
 * 生成旅行计划。
 *
 * 前端把首页表单收集到的 TripFormData 发送给后端规划接口，
 * 后端通常会整合智能体、天气、地图或 POI 服务后返回结构化的 TripPlanResponse。
 */
export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '生成旅行计划失败')
  }
}

/**
 * 健康检查。
 *
 * 用于确认前端是否可以正常连接后端服务，适合在调试、部署验证或页面初始化时调用。
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

/**
 * 获取景点图片。
 *
 * 根据景点名称向后端查询图片信息，前端结果页可以用返回的 photo_url 丰富景点卡片展示。
 */
export async function getAttractionPhoto(name: string): Promise<PhotoResponse> {
  try {
    const response = await apiClient.get<PhotoResponse>('/api/poi/photo', {
      params: { name }
    })
    return response.data
  } catch (error: any) {
    console.error('获取景点图片失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '获取景点图片失败')
  }
}

// 默认导出统一 API 客户端，方便其他模块在需要自定义请求时直接复用相同配置。
export default apiClient
