export const translations = {
  // Navigation
  nav: {
    dashboard: 'Bosh sahifa',
    buildings: 'Binolar',
    devices: 'Qurilmalar',
    alerts: 'Ogohlantirishlar',
    firmware: 'Firmware',
    users: 'Foydalanuvchilar',
    audit: 'Audit jurnali',
    settings: 'Sozlamalar',
    chat: 'AI Yordamchi',
    analytics: 'Tahlil (Analytics)',
  },

  // Login
  login: {
    title: 'SmartBino',
    subtitle: 'Kommunal monitoring tizimi',
    username: 'Foydalanuvchi nomi',
    password: 'Parol',
    signIn: 'Kirish',
    error: "Login yoki parol noto\'g\'ri",
    loading: 'Kirilmoqda...',
  },

  // Dashboard
  dashboard: {
    title: 'Bosh sahifa',
    devices: 'Qurilmalar',
    buildings: 'Binolar',
    alerts: 'Ogohlantirishlar',
    readings: "O\'lchovlar (bugun)",
    online: 'onlayn',
    offline: 'offlayn',
    energy: "So\'nggi 24 soat — Energiya sarfi",
    activeAlerts: 'Faol ogohlantirishlar',
  },

  // KPI
  kpi: {
    totalDevices: 'Jami qurilmalar',
    onlineDevices: 'Onlayn qurilmalar',
    totalBuildings: 'Jami binolar',
    activeAlerts: 'Faol ogohlantirishlar',
    criticalAlerts: 'Kritik ogohlantirishlar',
    warningAlerts: 'Ogohlantirish ogohlantirishlar',
    readingsToday: "Bugungi o\'lchovlar",
  },

  // Buildings
  buildings: {
    title: 'Binolar',
    name: 'Bino nomi',
    address: 'Manzil',
    mapsUrl: 'Google Maps link',
    coordinates: 'Koordinatalar',
    deviceCount: 'Qurilmalar soni',
    devices: 'Qurilmalar',
    addBuilding: "Yangi bino qo\'shish",
    editBuilding: 'Binoni tahrirlash',
    deleteBuilding: "Binoni o\'chirish",
  },

  // Devices
  devices: {
    title: 'Qurilmalar',
    id: 'ID',
    type: 'Tur',
    building: 'Bino',
    ip: 'IP manzili',
    firmware: 'Firmware',
    lastSeen: 'Oxirgi aloqa',
    status: 'Holat',
    online: 'Onlayn',
    offline: 'Offlayn',
    minutes: 'daqiqa oldin',
    hours: 'soat oldin',
    days: 'kun oldin',
    addDevice: "Yangi qurilma qo\'shish",
    editDevice: 'Qurilmani tahrirlash',
    deleteDevice: "Qurilmani o\'chirish",
  },

  // Device Types
  deviceTypes: {
    electricity: 'Elektr',
    water: 'Suv',
    gas: 'Gaz',
    soil: "Yerto'la namligi",
  },

  // Alerts
  alerts: {
    title: 'Ogohlantirishlar',
    severity: "Og\'irligi",
    kind: 'Turi',
    message: 'Xabar',
    timestamp: 'Vaqti',
    status: 'Holat',
    cleared: 'Bekor qilingan',
    open: 'Ochiq',
    critical: 'Kritik',
    warning: 'Ogohlantirish',
    info: 'Axborot',
    markAsCleared: 'Bekor qilingan deb belgilash',
    dismiss: "O\'tkazib yuborish",
  },

  // Firmware
  firmware: {
    title: 'Firmware boshqaruvi',
    version: 'Versiya',
    releaseDate: 'Chiqarilgan sana',
    changelog: "O\'zgarishlar jurnali",
    deploy: 'Joylashtirish',
    schedule: 'Rejalashtirilgan',
    updateStatus: 'Yangilash holati',
    deployed: 'Joylashtirilyapti',
  },

  // Users (Admin)
  users: {
    title: 'Foydalanuvchilar',
    username: 'Foydalanuvchi nomi',
    role: 'Rol',
    status: 'Holat',
    admin: 'Admin',
    user: 'Foydalanuvchi',
    active: 'Faol',
    inactive: 'Faol emas',
    createUser: 'Yangi foydalanuvchi yaratish',
    editUser: 'Foydalanuvchini tahrirlash',
    deleteUser: "Foydalanuvchini o\'chirish",
  },

  // Audit (Admin)
  audit: {
    title: 'Audit jurnali',
    timestamp: 'Vaqti',
    user: 'Foydalanuvchi',
    action: 'Harakat',
    resource: 'Resurs',
    details: 'Tafsilotlar',
  },

  // Settings (Admin)
  settings: {
    title: 'Sozlamalar',
    systemSettings: 'Tizim sozlamalari',
    alertThresholds: 'Ogohlantirish chegaralari',
    notifications: 'Bildirishlar',
    save: 'Saqlash',
  },

  // Common
  common: {
    loading: 'Yuklanmoqda...',
    error: 'Xato yuz berdi',
    success: 'Muvaffaqiyatli',
    delete: "O\'chirish",
    cancel: 'Bekor qilish',
    save: 'Saqlash',
    edit: 'Tahrirlash',
    add: "Qo\'shish",
    back: 'Orqaga',
    logout: 'Chiqish',
    profile: 'Profil',
    noData: "Ma\'lumot topilmadi",
    confirm: 'Tasdiqlash',
    confirmDelete: "Haqiqatdan ham o\'chirmoqchisiz?",
  },
}

export type TranslationKey = keyof typeof translations
