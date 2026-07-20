import axios from 'axios'

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || item?.message || String(item)).join(', ')
    }
    if (typeof detail === 'string' && detail.trim()) return detail
    if (typeof error.response?.data?.message === 'string') return error.response.data.message

    if (error.response?.status === 401) return 'Sessiya muddati tugadi. Qaytadan login qiling.'
    if (error.response?.status === 403) return 'Bu amal uchun ruxsat yetarli emas.'
    if (error.response?.status === 404) return 'Maʼlumot topilmadi.'
    if (error.response?.status === 409) return 'Bu maʼlumot allaqachon mavjud yoki konflikt bor.'
    if (error.response?.status && error.response.status >= 500) return "Serverda xatolik yuz berdi. Keyinroq urinib ko'ring."
    if (error.code === 'ERR_NETWORK') return "Server bilan aloqa yo'q. Internet yoki backend holatini tekshiring."
    return error.message || "So'rov bajarilmadi."
  }

  if (error instanceof Error) return error.message
  return 'Nomaʼlum xatolik yuz berdi.'
}

export function getApiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined
}
