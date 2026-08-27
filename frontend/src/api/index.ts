import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

const instance: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截 — 注入 JWT
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截 — 统一错误处理
instance.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    switch (status) {
      case 401:
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        break
      case 403:
        ElMessage.error(detail || '无权执行此操作')
        break
      case 404:
        ElMessage.error(detail || '请求的资源不存在')
        break
      case 422:
        // 验证错误，提取字段信息
        const msg = typeof detail === 'string'
          ? detail
          : detail?.[0]?.msg || '输入数据验证失败'
        ElMessage.error(msg)
        break
      case 500:
        ElMessage.error('服务器内部错误，请稍后重试')
        break
      default:
        if (!error.response) {
          ElMessage.error('网络连接失败，请检查后端服务是否启动')
        } else {
          ElMessage.error(detail || '请求失败')
        }
    }

    return Promise.reject(error)
  }
)

export default instance
