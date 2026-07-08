import { RootLayout } from '@/components/layout/RootLayout'
import { Book, Cpu, Wifi, Info } from 'lucide-react'

export default function InstallGuidePage() {
  return (
    <RootLayout>
      <div className="space-y-8 max-w-4xl">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Book className="w-8 h-8 text-blue-500" />
          <h1 className="text-3xl font-bold text-gray-950 dark:text-gray-100">Qurilmalarni O'rnatish Qo'llanmasi</h1>
        </div>

        {/* Section 1: Hardware Connections */}
        <div className="glass-card rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center gap-3 text-blue-650 dark:text-blue-400 font-bold text-lg border-b border-gray-300 dark:border-gray-850 pb-3">
            <Cpu className="w-5 h-5" />
            <h2>1. Sxema va Hardware Ulanishlar (ESP32)</h2>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            Datchiklar va hisoblagichlardan ma'lumotlarni o'qish uchun ESP32 mikrokontrolleri va MAX485 (RS-485 to TTL) moduli ishlatiladi. Quyidagi pin ulanishlarini to'g'ri bajaring:
          </p>
          <div className="overflow-x-auto rounded-xl border border-gray-350 dark:border-gray-800 shadow-sm">
            <table className="w-full text-sm border-collapse bg-gray-100/20 dark:bg-gray-950/40">
              <thead>
                <tr className="border-b border-gray-355 dark:border-gray-800 bg-gray-200/50 dark:bg-gray-950/80">
                  <th className="p-3 text-left font-bold text-gray-800 dark:text-gray-200">MAX485 Pin</th>
                  <th className="p-3 text-left font-bold text-gray-800 dark:text-gray-200">ESP32 Pin</th>
                  <th className="p-3 text-left font-bold text-gray-800 dark:text-gray-200">Tavsif</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-300 dark:divide-gray-800 text-gray-750 dark:text-gray-300">
                <tr className="hover:bg-gray-200/20 dark:hover:bg-gray-850/20 transition">
                  <td className="p-3 font-bold text-blue-650 dark:text-blue-400">RO (Receiver Out)</td>
                  <td className="p-3 font-medium">GPIO 16 (RX2)</td>
                  <td className="p-3">Ma'lumot qabul qilish liniyasi</td>
                </tr>
                <tr className="hover:bg-gray-200/20 dark:hover:bg-gray-850/20 transition">
                  <td className="p-3 font-bold text-blue-650 dark:text-blue-400">DI (Driver In)</td>
                  <td className="p-3 font-medium">GPIO 17 (TX2)</td>
                  <td className="p-3">Ma'lumot uzatish liniyasi</td>
                </tr>
                <tr className="hover:bg-gray-200/20 dark:hover:bg-gray-850/20 transition">
                  <td className="p-3 font-bold text-blue-650 dark:text-blue-400">DE & RE (Jumperlangan)</td>
                  <td className="p-3 font-medium">GPIO 4</td>
                  <td className="p-3">MAX485 uzatish/qabul qilish rejimini yoqish</td>
                </tr>
                <tr className="hover:bg-gray-200/20 dark:hover:bg-gray-850/20 transition">
                  <td className="p-3 font-bold text-blue-650 dark:text-blue-400">VCC</td>
                  <td className="p-3 font-medium">5V / 3.3V</td>
                  <td className="p-3">Modul ta'minoti</td>
                </tr>
                <tr className="hover:bg-gray-200/20 dark:hover:bg-gray-850/20 transition">
                  <td className="p-3 font-bold text-blue-650 dark:text-blue-400">GND</td>
                  <td className="p-3 font-medium">GND</td>
                  <td className="p-3">Yer (Ground) ulanishi</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-lg flex gap-3 text-sm text-blue-650 dark:text-blue-400">
            <Info className="w-5 h-5 shrink-0" />
            <div>
              <span className="font-bold">Maslahat:</span> A va B liniyalarini hisoblagichning mos ravishda RS-485 A va B chiqishlariga ulang. Agar aloqa o'rnatilmasa, A va B simlarini o'zaro almashtirib ko'ring.
            </div>
          </div>
        </div>

        {/* Section 2: WiFi and Portal Configuration */}
        <div className="glass-card rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center gap-3 text-blue-650 dark:text-blue-400 font-bold text-lg border-b border-gray-300 dark:border-gray-850 pb-3">
            <Wifi className="w-5 h-5" />
            <h2>2. WiFi Manager va Serverga Ulash</h2>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            ESP32 birinchi marta yoqilganda avtomatik ravishda o'zining WiFi nuqtasini ochadi:
          </p>
          <ul className="list-disc pl-5 text-sm text-gray-700 dark:text-gray-300 space-y-2">
            <li><strong>AP Nomi (SSID):</strong> <code className="bg-gray-150 dark:bg-gray-950 px-1.5 py-0.5 rounded text-blue-650 dark:text-blue-400 font-mono border border-gray-250 dark:border-gray-900">MeterSetup</code></li>
            <li><strong>Parol:</strong> <code className="bg-gray-150 dark:bg-gray-950 px-1.5 py-0.5 rounded text-blue-650 dark:text-blue-400 font-mono border border-gray-250 dark:border-gray-900">meter1234</code></li>
          </ul>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            WiFi nuqtasiga ulaning va brauzeringizda avtomatik ochiladigan sozlash sahifasiga o'ting. Quyidagi ma'lumotlarni kiriting:
          </p>
          <ol className="list-decimal pl-5 text-sm text-gray-700 dark:text-gray-300 space-y-2">
            <li>Uyingiz yoki ofisingizning faol WiFi nuqtasini tanlang va parolini yozing.</li>
            <li><strong>Server URL:</strong> Monitoring serverining HTTP IP manzilini kiriting (masalan: <code className="bg-gray-150 dark:bg-gray-950 px-1.5 py-0.5 rounded text-blue-650 dark:text-blue-400 font-mono border border-gray-250 dark:border-gray-900">http://67.205.171.93</code>).</li>
            <li>Sozlamalarni saqlang. ESP32 qayta yuklanib, serverga bog'lanadi.</li>
          </ol>
        </div>

        {/* Section 3: Floating Pins and Universal Code */}
        <div className="glass-card rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center gap-3 text-yellow-600 dark:text-yellow-450 font-bold text-lg border-b border-gray-300 dark:border-gray-850 pb-3">
            <Info className="w-5 h-5" />
            <h2>3. Universal Firmware & Shovqinlarni Oldini Olish</h2>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            Datchik turini pinlar holatiga qarab avtomatik aniqlash floating (suzuvchi) pinlardagi shovqin sababli noto'g'ri ishlashi mumkin. Buning oldini olish uchun quyidagi gibrid tizim o'rnatilgan:
          </p>
          <div className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
            <div className="p-3 bg-gray-150/40 dark:bg-gray-950/40 border border-gray-250 dark:border-gray-800 rounded-lg shadow-sm">
              <span className="font-bold text-gray-900 dark:text-gray-200">1. Startup Auto-detection:</span> Qurilma birinchi marta yoqilganda pinlar holatini o'qib, o'zining utility_type (elektr, suv, gaz) turini taxminiy aniqlaydi.
            </div>
            <div className="p-3 bg-gray-150/40 dark:bg-gray-950/40 border border-gray-250 dark:border-gray-800 rounded-lg shadow-sm">
              <span className="font-bold text-gray-900 dark:text-gray-200">2. NVS Config Sync (Asosiy himoya):</span> Qurilma serverga muvaffaqiyatli bog'langandan so'ng, <code className="bg-gray-150 dark:bg-gray-950 px-1 py-0.5 rounded text-blue-650 dark:text-blue-400 border border-gray-250 dark:border-gray-900">/api/device-config/&#123;device_id&#125;</code> endpointi orqali admin tasdiqlagan haqiqiy sozlamalarni yuklab oladi va uni o'zining doimiy **NVS (Preferences)** xotirasida saqlaydi.
            </div>
            <div className="p-3 bg-gray-150/40 dark:bg-gray-950/40 border border-gray-250 dark:border-gray-800 rounded-lg shadow-sm">
              <span className="font-bold text-gray-900 dark:text-gray-200">3. Anti-Noise Logic:</span> Keyingi safar ishga tushganda, qurilma pin signallariga qaramaydi, balki NVS xotiradagi tasdiqlangan sozlamaga tayanib ishlaydi. Bu pinlardagi elektr shovqinlarni 100% chetlab o'tadi.
            </div>
          </div>
        </div>
      </div>
    </RootLayout>
  )
}
