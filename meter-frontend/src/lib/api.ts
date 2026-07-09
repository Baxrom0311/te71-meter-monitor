import axios, { AxiosInstance } from 'axios'
import { getTokenFromStorage, removeTokenFromStorage } from './auth'
import { API_BASE_URL } from './env'
import { getApiErrorMessage } from './errors'
import { notify } from './toast'

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = getTokenFromStorage()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor: handle 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      removeTokenFromStorage()
      window.sessionStorage.setItem(
        'meter-toast',
        JSON.stringify({
          type: 'warning',
          title: 'Sessiya tugadi',
          message: 'Xavfsizlik uchun qaytadan login qiling.',
        }),
      )
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    } else if (status === 403) {
      notify({ type: 'warning', title: 'Ruxsat yetarli emas', message: getApiErrorMessage(error) })
    } else if (!status || status >= 500) {
      notify({ type: 'error', title: 'Server bilan muammo', message: getApiErrorMessage(error) })
    }
    return Promise.reject(error)
  },
)

export default apiClient
