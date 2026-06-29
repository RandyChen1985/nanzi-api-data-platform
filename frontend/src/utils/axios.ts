/**
 * Axios 全局配置
 * 统一处理请求/响应拦截、错误处理
 */
import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

// 创建 axios 实例
const instance = axios.create({
  // 不需要 baseURL，Vite 代理会自动转发 /api 请求到后端
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 自动添加 API Key
    const apiKey = localStorage.getItem('api_key')
    if (apiKey && config.headers) {
      config.headers['X-API-Key'] = apiKey
    }
    
    return config
  },
  (error: AxiosError) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
instance.interceptors.response.use(
  (response) => {
    return response
  },
  (error: AxiosError) => {
    // 统一错误处理
    if (error.response) {
      const status = error.response.status
      const data: any = error.response.data
      
      switch (status) {
        case 401:
          localStorage.removeItem('api_key')
          localStorage.removeItem('user_info')
          if (window.location.pathname !== '/login') {
            window.location.href = '/login'
          }
          break
          
        case 403:
          console.error('权限不足:', data.detail || '您没有权限执行此操作')
          break
          
        case 404:
          console.error('资源未找到:', data.detail || '请求的资源不存在')
          break
          
        case 422:
          // 验证错误
          console.error('验证错误:', data.detail || '请求参数不正确')
          break
          
        case 500:
          console.error('服务器错误:', data.detail || '服务器内部错误，请稍后重试')
          break
          
        default:
          console.error('请求失败:', data.detail || `请求失败 (${status})`)
      }
    } else if (error.request) {
      // 请求已发出但没有收到响应
      console.error('网络错误:', '网络连接失败，请检查网络设置')
    } else {
      // 其他错误
      console.error('请求错误:', error.message)
    }
    
    return Promise.reject(error)
  }
)

export default instance
