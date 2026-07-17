import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

api.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        console.warn('[API] Unauthorized')
      }
      let message: string
      if (data?.detail && Array.isArray(data.detail)) {
        message = data.detail.map((d: any) => d.msg).join('; ')
      } else {
        message = data?.detail || data?.message || `Request failed with status ${status}`
      }
      return Promise.reject(new Error(message))
    }
    if (error.request) {
      return Promise.reject(new Error('Network error: Unable to reach the server'))
    }
    return Promise.reject(error)
  }
)

export default api
