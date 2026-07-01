/**
 * TE71 / TE73 Meter Monitor — v2.0.0
 *
 * Oqim:
 *   1. NVS dan server_url + mqtt_host o'qiladi
 *   2. WiFiManager: birinchi bootda AP ochadi →
 *      WiFi SSID/Parol + Server URL + MQTT Host kiritiladi
 *   3. WiFi ulangach server /health tekshiriladi
 *      OK  → normal ishlash (MQTT publish, HTTP zaxira)
 *      XATO→ "MeterConfig-XXXX" AP ochiladi, foydalanuvchi
 *             faqat Server URL + MQTT Host ni o'zgartiradi
 *   4. Server yo'q bo'lganda o'qishlar offline bufferda saqlanadi,
 *      server qaytgach avtomatik yuboriladi
 *
 * Pinlar  : GPIO16=RX, GPIO17=TX, GPIO4=DE/RE
 * Config  : Birinchi boot yoki BOOT (GPIO0) 3s bosish → WiFi portal
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <WebServer.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>

// ── Versiya va sabitlar ───────────────────────────────────────────────────────
#define FIRMWARE_VERSION  "2.0.0"
#define CONFIG_RESET_PIN  0           // BOOT tugmasi
#define WIFI_AP_NAME      "MeterSetup"
#define WIFI_AP_PASS      "meter1234"
#define CFG_AP_TIMEOUT_S  300         // Config AP da kutish (5 daqiqa)
#define READ_INTERVAL_MS  30000UL
#define CMD_POLL_MS       60000UL
#define MQTT_PORT         1883
#define OFFLINE_BUF_SIZE  50          // Offline saqlanadigan o'qishlar soni

// RS-485 pinlari
#define PIN_RX  16
#define PIN_TX  17
#define PIN_DE   4

// DLMS
#define SERVER_ADDR    0x03
#define CLIENT_PUBLIC  0x21
#define CLIENT_READER  0x03
static const uint8_t LLC_REQ[] = {0xE6, 0xE6, 0x00};

// OBIS — TE71 + TE73
static const uint8_t OBIS_SERIAL[6]   = {0x00,0x00,0x60,0x01,0x00,0xFF};
static const uint8_t OBIS_VOLT_L1[6]  = {0x01,0x00,0x20,0x07,0x00,0xFF};
static const uint8_t OBIS_VOLT_L2[6]  = {0x01,0x00,0x34,0x07,0x00,0xFF};
static const uint8_t OBIS_VOLT_L3[6]  = {0x01,0x00,0x48,0x07,0x00,0xFF};
static const uint8_t OBIS_CURR_L1[6]  = {0x01,0x00,0x1F,0x07,0x00,0xFF};
static const uint8_t OBIS_CURR_L2[6]  = {0x01,0x00,0x33,0x07,0x00,0xFF};
static const uint8_t OBIS_CURR_L3[6]  = {0x01,0x00,0x47,0x07,0x00,0xFF};
static const uint8_t OBIS_POWER[6]    = {0x01,0x00,0x0F,0x07,0x00,0xFF};
static const uint8_t OBIS_POWER_VAR[6]= {0x01,0x00,0x10,0x07,0x00,0xFF};
static const uint8_t OBIS_FREQ[6]     = {0x01,0x00,0x0E,0x07,0x00,0xFF};
static const uint8_t OBIS_PF[6]       = {0x01,0x00,0x0D,0x07,0x00,0xFF};
static const uint8_t OBIS_ENERGY[6]   = {0x01,0x00,0x01,0x08,0x00,0xFF};

// ── Global holat ─────────────────────────────────────────────────────────────
static char  SERVER_URL[100] = "http://192.168.1.100:8000";
static char  MQTT_HOST[64]   = "192.168.1.100";

static char  deviceId[20]    = "";
static char  meterSerial[32] = "";
static char  meterType[8]    = "unknown";
static int   meterBaud       = 9600;
static bool  registered      = false;
static bool  serverOk        = false;

static bool    dlmsConnected = false;
static uint8_t clientSrc     = CLIENT_READER;
static uint8_t sendSeq       = 0;
static uint8_t recvSeq       = 0;
static uint8_t invokeId      = 0xC0;
static uint8_t txBuf[300]; static size_t txLen;
static uint8_t rxBuf[300]; static size_t rxLen;
static bool    relayOn       = true;

static unsigned long lastReadMs = 0;
static unsigned long lastCmdMs  = 0;

// ── Offline buffer ────────────────────────────────────────────────────────────
struct Reading {
    unsigned long ts;
    float vl1, vl2, vl3;
    float il1, il2, il3;
    float pw, freq, energy, pf;
};
static Reading offBuf[OFFLINE_BUF_SIZE];
static int     offHead  = 0;
static int     offCount = 0;

void bufferReading(const Reading& r) {
    offBuf[offHead] = r;
    offHead = (offHead + 1) % OFFLINE_BUF_SIZE;
    if (offCount < OFFLINE_BUF_SIZE) offCount++;
}

// ── WiFi + MQTT ───────────────────────────────────────────────────────────────
WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

static char topicTelemetry[64];
static char topicCmd[64];
static char topicStatus[64];

// ════════════════════════════════════════════════════════════════════════════
// FCS16
// ════════════════════════════════════════════════════════════════════════════
static uint16_t fcsTbl[256];
void initFcs() {
    for (int i = 0; i < 256; i++) {
        uint16_t v = i;
        for (int j = 0; j < 8; j++)
            v = (v & 1) ? ((v >> 1) ^ 0x8408) : (v >> 1);
        fcsTbl[i] = v;
    }
}
uint16_t fcs16(const uint8_t* d, size_t n) {
    uint16_t f = 0xFFFF;
    for (size_t i = 0; i < n; i++)
        f = (f >> 8) ^ fcsTbl[(f ^ d[i]) & 0xFF];
    return f ^ 0xFFFF;
}

// ════════════════════════════════════════════════════════════════════════════
// HDLC
// ════════════════════════════════════════════════════════════════════════════
void buildHdlc(uint8_t dest, uint8_t src, uint8_t ctrl,
               const uint8_t* info, size_t infoLen) {
    if (infoLen == 0) {
        uint16_t tot = 7;
        uint8_t fd[5] = {(uint8_t)(0xA0|(tot>>8)),(uint8_t)(tot&0xFF),dest,src,ctrl};
        uint16_t f = fcs16(fd, 5);
        txBuf[0]=0x7E; memcpy(txBuf+1,fd,5);
        txBuf[6]=f&0xFF; txBuf[7]=f>>8; txBuf[8]=0x7E; txLen=9;
    } else {
        uint16_t tot = 9+(uint16_t)infoLen;
        uint8_t fmt[2]={( uint8_t)(0xA0|(tot>>8)),(uint8_t)(tot&0xFF)};
        uint8_t hcsIn[5]={fmt[0],fmt[1],dest,src,ctrl};
        uint16_t hcs=fcs16(hcsIn,5);
        txBuf[0]=0x7E; txBuf[1]=fmt[0]; txBuf[2]=fmt[1];
        txBuf[3]=dest; txBuf[4]=src; txBuf[5]=ctrl;
        txBuf[6]=hcs&0xFF; txBuf[7]=hcs>>8;
        memcpy(txBuf+8,info,infoLen);
        uint16_t fcs=fcs16(txBuf+1,7+infoLen);
        txBuf[8+infoLen]=fcs&0xFF; txBuf[9+infoLen]=fcs>>8;
        txBuf[10+infoLen]=0x7E; txLen=11+infoLen;
    }
}

// ════════════════════════════════════════════════════════════════════════════
// RS-485
// ════════════════════════════════════════════════════════════════════════════
bool txrx(uint32_t timeoutMs = 3000) {
    while (Serial2.available()) Serial2.read();
    rxLen = 0;
    digitalWrite(PIN_DE, HIGH); delayMicroseconds(150);
    Serial2.write(txBuf, txLen); Serial2.flush();
    delayMicroseconds(150); digitalWrite(PIN_DE, LOW);
    uint32_t t = millis();
    while (millis()-t < timeoutMs) {
        while (Serial2.available() && rxLen < sizeof(rxBuf))
            rxBuf[rxLen++] = Serial2.read();
        if (rxLen > 4 && rxBuf[rxLen-1] == 0x7E) break;
        delay(5);
    }
    return rxLen > 4;
}

const uint8_t* findPdu(size_t* pduLen) {
    for (size_t i = 0; i+2 < rxLen; i++) {
        if (rxBuf[i]==0xE6 && rxBuf[i+1]==0xE7 && rxBuf[i+2]==0x00) {
            int rem=(int)rxLen-(int)i-3-3;
            *pduLen=rem>0?rem:0; return rxBuf+i+3;
        }
    }
    *pduLen=0; return nullptr;
}

float readDlmsFloat(const uint8_t* d, size_t len) {
    if (len<2) return NAN;
    switch(d[0]) {
        case 0x05: return (float)(int32_t)(((uint32_t)d[1]<<24)|((uint32_t)d[2]<<16)|((uint32_t)d[3]<<8)|d[4]);
        case 0x06: return (float)(((uint32_t)d[1]<<24)|((uint32_t)d[2]<<16)|((uint32_t)d[3]<<8)|d[4]);
        case 0x12: return (float)(((uint16_t)d[1]<<8)|d[2]);
        case 0x16: return (float)d[1];
        default:   return NAN;
    }
}

// ════════════════════════════════════════════════════════════════════════════
// DLMS ulanish
// ════════════════════════════════════════════════════════════════════════════
uint8_t nextCtrl() {
    uint8_t c=((sendSeq&7)<<5)|0x10|((recvSeq&7)<<1);
    sendSeq=(sendSeq+1)%8; recvSeq=(recvSeq+1)%8; return c;
}
bool doSnrm() { buildHdlc(SERVER_ADDR,clientSrc,0x93,nullptr,0); return txrx(2000)&&rxLen>4; }

bool sendAarq(const uint8_t* aarq, size_t alen) {
    uint8_t info[128]; memcpy(info,LLC_REQ,3); memcpy(info+3,aarq,alen);
    uint8_t ctrl=((sendSeq&7)<<5)|0x10|((recvSeq&7)<<1);
    buildHdlc(SERVER_ADDR,clientSrc,ctrl,info,3+alen);
    if (!txrx(3000)) return false;
    for (size_t i=0;i+4<rxLen;i++)
        if (rxBuf[i]==0xA2&&rxBuf[i+1]==0x03&&rxBuf[i+2]==0x02&&rxBuf[i+3]==0x01&&rxBuf[i+4]==0x00) {
            dlmsConnected=true; sendSeq=1; recvSeq=1; invokeId=0xC0; return true;
        }
    return false;
}

bool connectPublic() {
    clientSrc=CLIENT_PUBLIC; sendSeq=0; recvSeq=0;
    if (!doSnrm()) return false;
    static const uint8_t aarq[]={0x60,0x1D,0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01,
        0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0};
    return sendAarq(aarq,sizeof(aarq));
}

bool connectReader() {
    clientSrc=CLIENT_READER; sendSeq=0; recvSeq=0;
    if (!doSnrm()) return false;
    static const uint8_t ctos[16]={0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x00};
    uint8_t aarq[72]; size_t p=0;
    aarq[p++]=0x60; aarq[p++]=0x3E;
    const uint8_t ac[]={0xA1,0x09,0x06,0x07,0x60,0x85,0x74,0x05,0x08,0x01,0x01}; memcpy(aarq+p,ac,11);p+=11;
    const uint8_t as[]={0x8A,0x02,0x07,0x80}; memcpy(aarq+p,as,4);p+=4;
    const uint8_t mh[]={0x8B,0x07,0x60,0x85,0x74,0x05,0x08,0x02,0x05}; memcpy(aarq+p,mh,9);p+=9;
    aarq[p++]=0xAC;aarq[p++]=0x12;aarq[p++]=0x80;aarq[p++]=0x10; memcpy(aarq+p,ctos,16);p+=16;
    const uint8_t ui[]={0xBE,0x10,0x04,0x0E,0x01,0x00,0x00,0x00,0x06,0x5F,0x1F,0x04,0x00,0x00,0x7E,0x1F,0x04,0xB0};
    memcpy(aarq+p,ui,18);p+=18;
    return sendAarq(aarq,p);
}

void doDisconnect() {
    if (!dlmsConnected) return;
    buildHdlc(SERVER_ADDR,clientSrc,0x53,nullptr,0); txrx(1000);
    dlmsConnected=false; sendSeq=0; recvSeq=0;
}

bool getAttribute(uint16_t cls, const uint8_t obis[6], uint8_t attr, float* outVal) {
    if (!dlmsConnected) return false;
    uint8_t pdu[13];
    pdu[0]=0xC0;pdu[1]=0x01;pdu[2]=invokeId++;
    pdu[3]=cls>>8;pdu[4]=cls&0xFF;
    memcpy(pdu+5,obis,6);pdu[11]=attr;pdu[12]=0x00;
    uint8_t info[16]; memcpy(info,LLC_REQ,3); memcpy(info+3,pdu,13);
    buildHdlc(SERVER_ADDR,clientSrc,nextCtrl(),info,16);
    if (!txrx(3000)) return false;
    size_t plen; const uint8_t* resp=findPdu(&plen);
    if (!resp||plen<5||resp[0]!=0xC4||resp[3]!=0x00) return false;
    if (outVal) *outVal=readDlmsFloat(resp+4,plen-4);
    return true;
}

bool getStringAttr(uint16_t cls, const uint8_t obis[6], uint8_t attr, char* out, size_t outSz) {
    if (!dlmsConnected) return false;
    uint8_t pdu[13];
    pdu[0]=0xC0;pdu[1]=0x01;pdu[2]=invokeId++;
    pdu[3]=cls>>8;pdu[4]=cls&0xFF;
    memcpy(pdu+5,obis,6);pdu[11]=attr;pdu[12]=0x00;
    uint8_t info[16]; memcpy(info,LLC_REQ,3); memcpy(info+3,pdu,13);
    buildHdlc(SERVER_ADDR,clientSrc,nextCtrl(),info,16);
    if (!txrx(3000)) return false;
    size_t plen; const uint8_t* resp=findPdu(&plen);
    if (!resp||plen<5||resp[0]!=0xC4||resp[3]!=0x00) return false;
    const uint8_t* d=resp+4; size_t dlen=plen-4;
    if (dlen>=2&&(d[0]==0x09||d[0]==0x0A)) {
        uint8_t slen=d[1]; size_t cp=slen<outSz-1?slen:outSz-1;
        memcpy(out,d+2,cp); out[cp]=0; return true;
    }
    return false;
}

bool tryConnect(uint32_t baud) {
    Serial2.end(); delay(50);
    Serial2.begin(baud,SERIAL_8N1,PIN_RX,PIN_TX); delay(100);
    if (connectReader()) return true;
    doDisconnect();
    if (connectPublic()) return true;
    return false;
}

bool autoConnect() {
    Serial.print("  9600...");
    if (tryConnect(9600)) { meterBaud=9600; return true; }
    doDisconnect();
    Serial.print(" 4800...");
    if (tryConnect(4800)) { meterBaud=4800; return true; }
    return false;
}

void detectMeterType() {
    float vl2=NAN;
    if (getAttribute(3,OBIS_VOLT_L2,2,&vl2)&&!isnan(vl2)&&vl2>0)
        strncpy(meterType,"TE73",sizeof(meterType));
    else
        strncpy(meterType,"TE71",sizeof(meterType));
    Serial.printf("Tur: %s\n", meterType);
}

// ════════════════════════════════════════════════════════════════════════════
// NVS
// ════════════════════════════════════════════════════════════════════════════
Preferences prefs;

void loadConfig() {
    prefs.begin("meter_cfg",true);
    prefs.getString("server_url",SERVER_URL,sizeof(SERVER_URL));
    prefs.getString("mqtt_host", MQTT_HOST, sizeof(MQTT_HOST));
    prefs.end();
}

void saveConfig(const char* serverUrl, const char* mqttHost) {
    prefs.begin("meter_cfg",false);
    prefs.putString("server_url",serverUrl);
    prefs.putString("mqtt_host", mqttHost);
    prefs.end();
    Serial.printf("Config saqlandi: %s | %s\n", serverUrl, mqttHost);
}

// ════════════════════════════════════════════════════════════════════════════
// Server sog'lomligini tekshirish
// ════════════════════════════════════════════════════════════════════════════
bool checkServer() {
    if (WiFi.status() != WL_CONNECTED) return false;
    HTTPClient http;
    char url[120]; snprintf(url,sizeof(url),"%s/health",SERVER_URL);
    http.begin(url); http.setTimeout(5000);
    int code = http.GET(); http.end();
    return code == 200;
}

// ════════════════════════════════════════════════════════════════════════════
// Config AP — server o'chiq bo'lganda ochiladi
// Faqat Server URL + MQTT Host o'zgartiriladi, WiFi saqlanadi
// ════════════════════════════════════════════════════════════════════════════
static const char CFG_AP_HTML[] PROGMEM = R"HTML(
<!DOCTYPE html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meter Config</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:sans-serif;background:#0f172a;color:#f1f5f9;
     display:flex;align-items:center;justify-content:center;min-height:100vh;}
.card{background:#1e293b;border:1px solid #334155;border-radius:14px;
      padding:28px 28px;width:340px;}
h2{font-size:17px;font-weight:700;margin-bottom:6px;}
.status{display:flex;gap:10px;margin-bottom:18px;font-size:13px;}
.ok {color:#22c55e;font-weight:700;}
.err{color:#ef4444;font-weight:700;}
label{display:block;color:#94a3b8;font-size:12px;font-weight:600;
      margin-bottom:4px;margin-top:14px;}
input{width:100%;background:#0f172a;border:1px solid #334155;
      color:#f1f5f9;border-radius:6px;padding:9px 12px;font-size:13px;}
input:focus{outline:none;border-color:#3b82f6;}
button{width:100%;margin-top:20px;padding:11px;background:#3b82f6;color:#fff;
       border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;}
.msg{margin-top:12px;font-size:13px;text-align:center;min-height:18px;color:#22c55e;}
.hint{color:#94a3b8;font-size:11px;margin-top:6px;}
</style></head><body>
<div class="card">
  <h2>Meter Sozlamalari</h2>
  <div class="status">
    <span>WiFi: <span class="ok">✓ ULANDI</span></span>
    <span>Server: <span class="err">✗ XATO</span></span>
  </div>
  <label>Server URL</label>
  <input id="srv" value="%SRV%" placeholder="http://192.168.1.100:8000">
  <div class="hint">Masalan: http://10.0.0.5:8000</div>
  <label>MQTT Host (IP)</label>
  <input id="mqtt" value="%MQTT%" placeholder="192.168.1.100">
  <button onclick="save()">Saqlash va qayta urinish</button>
  <div class="msg" id="msg"></div>
</div>
<script>
async function save(){
  const msg=document.getElementById('msg');
  msg.style.color='#94a3b8'; msg.textContent='Saqlanmoqda...';
  const r=await fetch('/save',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({server:document.getElementById('srv').value,
                         mqtt:document.getElementById('mqtt').value})});
  const j=await r.json();
  if(j.ok){
    msg.style.color='#22c55e';
    msg.textContent='Saqlandi! Tekshirilmoqda...';
    setTimeout(()=>{msg.textContent='Qurilma qayta ishga tushmoqda...';},1500);
  }else{msg.style.color='#ef4444';msg.textContent='Xato!';}
}
</script></body></html>
)HTML";

void openConfigAP() {
    // AP nomi: MeterCfg-XXXX (MAC oxirgi 4 belgi)
    uint8_t mac[6]; esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char apName[24];
    snprintf(apName, sizeof(apName), "MeterCfg-%02X%02X", mac[4], mac[5]);

    Serial.printf("\n=== CONFIG AP: %s (parol: %s) ===\n", apName, WIFI_AP_PASS);
    Serial.println("Telefon yoki noutbuk bilan ulab, sozlamalarni o'zgartiring.");

    // WiFi ni AP+STA rejimiga o'tkazamiz (WiFi saqlanadi, AP ham ochiladi)
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(apName, WIFI_AP_PASS);

    WebServer cfgServer(80);

    cfgServer.on("/", HTTP_GET, [&]() {
        String html = FPSTR(CFG_AP_HTML);
        html.replace("%SRV%",  SERVER_URL);
        html.replace("%MQTT%", MQTT_HOST);
        cfgServer.send(200, "text/html; charset=utf-8", html);
    });

    cfgServer.on("/save", HTTP_POST, [&]() {
        if (cfgServer.hasArg("plain")) {
            StaticJsonDocument<256> doc;
            if (!deserializeJson(doc, cfgServer.arg("plain"))) {
                const char* srv  = doc["server"] | "";
                const char* mqtt = doc["mqtt"]   | "";
                if (strlen(srv) > 4) {
                    strncpy(SERVER_URL, srv,  sizeof(SERVER_URL)-1);
                    strncpy(MQTT_HOST,  mqtt, sizeof(MQTT_HOST)-1);
                    saveConfig(SERVER_URL, MQTT_HOST);
                    cfgServer.send(200, "application/json", "{\"ok\":true}");
                    delay(1000);
                    WiFi.softAPdisconnect(true);
                    WiFi.mode(WIFI_STA);
                    ESP.restart();
                    return;
                }
            }
        }
        cfgServer.send(400, "application/json", "{\"ok\":false}");
    });

    // Captive portal: barcha so'rovlarni / ga yo'naltirish
    cfgServer.onNotFound([&]() {
        cfgServer.sendHeader("Location", "/", true);
        cfgServer.send(302, "text/plain", "");
    });

    cfgServer.begin();

    unsigned long start = millis();
    while (millis() - start < (unsigned long)CFG_AP_TIMEOUT_S * 1000) {
        cfgServer.handleClient();
        delay(5);
    }

    // Timeout — AP ni yopib davom etamiz
    Serial.println("Config AP timeout — davom etilmoqda...");
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
}

// ════════════════════════════════════════════════════════════════════════════
// HTTP va MQTT helpers
// ════════════════════════════════════════════════════════════════════════════
bool httpPost(const char* path, const String& body) {
    if (WiFi.status()!=WL_CONNECTED) return false;
    HTTPClient http;
    char url[200]; snprintf(url,sizeof(url),"%s%s",SERVER_URL,path);
    http.begin(url); http.addHeader("Content-Type","application/json"); http.setTimeout(8000);
    int code=http.POST(body); http.end();
    return code>=200&&code<300;
}

String httpGet(const char* path) {
    if (WiFi.status()!=WL_CONNECTED) return "";
    HTTPClient http;
    char url[200]; snprintf(url,sizeof(url),"%s%s",SERVER_URL,path);
    http.begin(url); http.setTimeout(5000);
    int code=http.GET();
    String resp=(code==200)?http.getString():""; http.end();
    return resp;
}

// ════════════════════════════════════════════════════════════════════════════
// MQTT
// ════════════════════════════════════════════════════════════════════════════
void onMqttMessage(char* topic, uint8_t* payload, unsigned int length) {
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc,payload,length)) return;
    const char* action=doc["action"];
    if (!action) return;
    Serial.printf("MQTT cmd: %s\n", action);
    if (strcmp(action,"relay_on")==0)  relayOn=true;
    if (strcmp(action,"relay_off")==0) relayOn=false;
    if (strcmp(action,"reboot")==0)    ESP.restart();
}

bool mqttConnect() {
    if (mqttClient.connected()) return true;
    char clientId[30]; snprintf(clientId,sizeof(clientId),"meter-%s",deviceId);
    char lwt[128]; snprintf(lwt,sizeof(lwt),"{\"online\":false,\"device_id\":\"%s\"}",deviceId);
    if (mqttClient.connect(clientId,nullptr,nullptr,topicStatus,0,true,lwt)) {
        mqttClient.subscribe(topicCmd);
        char msg[128];
        snprintf(msg,sizeof(msg),"{\"online\":true,\"device_id\":\"%s\",\"ip\":\"%s\",\"rssi\":%d}",
                 deviceId,WiFi.localIP().toString().c_str(),WiFi.RSSI());
        mqttClient.publish(topicStatus,msg,true);
        Serial.println("MQTT ulandi");
        return true;
    }
    return false;
}

// ════════════════════════════════════════════════════════════════════════════
// OTA
// ════════════════════════════════════════════════════════════════════════════
void checkOTA() {
    if (!serverOk) return;
    HTTPClient http;
    char url[200]; snprintf(url,sizeof(url),"%s/api/ota/check/%s?current_version=%s",
                            SERVER_URL,deviceId,FIRMWARE_VERSION);
    http.begin(url); http.setTimeout(5000);
    int code=http.GET();
    if (code!=200) { http.end(); return; }
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc,http.getString())) { http.end(); return; }
    http.end();
    if (!doc["update"].as<bool>()) return;
    String fwUrl=String(SERVER_URL)+doc["url"].as<String>();
    Serial.printf("OTA: v%s topildi, yuklanmoqda...\n",doc["version"].as<const char*>());
    doDisconnect();
    HTTPClient fwHttp; fwHttp.begin(fwUrl);
    if (httpUpdate.update(fwHttp)==HTTP_UPDATE_OK) ESP.restart();
}

// ════════════════════════════════════════════════════════════════════════════
// Registration
// ════════════════════════════════════════════════════════════════════════════
void doRegister() {
    if (!serverOk) return;
    StaticJsonDocument<512> doc;
    doc["device_id"]    = deviceId;
    doc["meter_serial"] = meterSerial;
    doc["meter_type"]   = meterType;
    doc["baud_rate"]    = meterBaud;
    doc["fw_version"]   = FIRMWARE_VERSION;
    doc["chip_model"]   = "ESP32";
    doc["rssi"]         = WiFi.RSSI();
    doc["ip"]           = WiFi.localIP().toString();
    String body; serializeJson(doc,body);
    if (httpPost("/api/register",body)) {
        registered=true;
        Serial.printf("Ro'yxatdan o'tildi: %s (%s)\n", deviceId, meterType);
    }
}

// ════════════════════════════════════════════════════════════════════════════
// O'qishlarni yuborish + offline buffer
// ════════════════════════════════════════════════════════════════════════════
String buildJson(const Reading& r) {
    StaticJsonDocument<512> doc;
    doc["device_id"]  = deviceId;
    doc["fw_version"] = FIRMWARE_VERSION;
    if (!isnan(r.vl1))    doc["voltage_l1"]  = roundf(r.vl1*10)/10.0f;
    if (!isnan(r.vl2))    doc["voltage_l2"]  = roundf(r.vl2*10)/10.0f;
    if (!isnan(r.vl3))    doc["voltage_l3"]  = roundf(r.vl3*10)/10.0f;
    if (!isnan(r.il1))    doc["current_l1"]  = roundf(r.il1*1000)/1000.0f;
    if (!isnan(r.il2))    doc["current_l2"]  = roundf(r.il2*1000)/1000.0f;
    if (!isnan(r.il3))    doc["current_l3"]  = roundf(r.il3*1000)/1000.0f;
    if (!isnan(r.pw))     doc["power_w"]     = roundf(r.pw);
    if (!isnan(r.freq))   doc["frequency"]   = roundf(r.freq*100)/100.0f;
    if (!isnan(r.energy)) doc["energy_kwh"]  = roundf(r.energy*1000)/1000.0f;
    if (!isnan(r.pf))     doc["pf"]          = roundf(r.pf*100)/100.0f;
    doc["relay_on"] = relayOn;
    String out; serializeJson(doc,out); return out;
}

void flushBuffer() {
    if (offCount==0 || !serverOk) return;
    Serial.printf("Offline buffer: %d ta o'qish yuborilmoqda...\n", offCount);
    int start = (offHead - offCount + OFFLINE_BUF_SIZE) % OFFLINE_BUF_SIZE;
    for (int i=0; i<offCount; i++) {
        Reading& r = offBuf[(start+i) % OFFLINE_BUF_SIZE];
        String body = buildJson(r);
        bool sent = false;
        if (mqttClient.connected())
            sent = mqttClient.publish(topicTelemetry, body.c_str());
        if (!sent)
            sent = httpPost("/api/readings", body);
        if (!sent) break;   // server hali o'chiq
        delay(100);
    }
    offCount=0; offHead=0;
    Serial.println("Buffer yuborildi.");
}

bool sendReading(const Reading& r) {
    String body = buildJson(r);
    // MQTT primary
    if (mqttClient.connected() && mqttClient.publish(topicTelemetry, body.c_str()))
        return true;
    // HTTP fallback
    return httpPost("/api/readings", body);
}

void pollCommands() {
    char path[80]; snprintf(path,sizeof(path),"/api/commands/%s",deviceId);
    String resp = httpGet(path);
    if (resp.isEmpty()) return;
    StaticJsonDocument<512> doc;
    if (deserializeJson(doc,resp)) return;
    for (JsonObject cmd : doc["commands"].as<JsonArray>()) {
        int id=cmd["id"]; const char* action=cmd["action"];
        if (!action) continue;
        if (strcmp(action,"relay_on")==0)  relayOn=true;
        if (strcmp(action,"relay_off")==0) relayOn=false;
        if (strcmp(action,"reboot")==0)    ESP.restart();
        char ackPath[80]; snprintf(ackPath,sizeof(ackPath),"/api/commands/%d/ack",id);
        httpPost(ackPath,"{}");
    }
}

// ════════════════════════════════════════════════════════════════════════════
// Setup
// ════════════════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200); delay(200);
    Serial.println("\n=== Meter Monitor v" FIRMWARE_VERSION " ===");

    // device_id = MAC
    uint8_t mac[6]; esp_read_mac(mac,ESP_MAC_WIFI_STA);
    snprintf(deviceId,sizeof(deviceId),"%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    Serial.printf("Device: %s\n", deviceId);

    // MQTT topiclar
    snprintf(topicTelemetry,sizeof(topicTelemetry),"meters/%s/telemetry",deviceId);
    snprintf(topicCmd,      sizeof(topicCmd),      "meters/%s/cmd",      deviceId);
    snprintf(topicStatus,   sizeof(topicStatus),   "meters/%s/status",   deviceId);

    // NVS dan sozlamalar
    loadConfig();
    Serial.printf("Server: %s\n", SERVER_URL);
    Serial.printf("MQTT  : %s:%d\n", MQTT_HOST, MQTT_PORT);

    // Config reset tekshiruvi (BOOT tugmasi 3s)
    pinMode(CONFIG_RESET_PIN, INPUT_PULLUP);
    bool forcePortal = false;
    if (digitalRead(CONFIG_RESET_PIN)==LOW) {
        Serial.println("BOOT bosilgan, 3s kutilmoqda...");
        delay(3000);
        if (digitalRead(CONFIG_RESET_PIN)==LOW) { forcePortal=true; Serial.println("WiFi portal ochilmoqda!"); }
    }

    // ── WiFiManager ──────────────────────────────────────────────────────────
    WiFiManagerParameter p_server("server","Server URL",  SERVER_URL, 99);
    WiFiManagerParameter p_mqtt  ("mqtt",  "MQTT Host",   MQTT_HOST,  63);

    WiFiManager wm;
    wm.setTitle("Meter Monitor");
    wm.addParameter(&p_server);
    wm.addParameter(&p_mqtt);
    wm.setConfigPortalTimeout(120);
    wm.setSaveConfigCallback([&](){
        strncpy(SERVER_URL, p_server.getValue(), sizeof(SERVER_URL)-1);
        strncpy(MQTT_HOST,  p_mqtt.getValue(),   sizeof(MQTT_HOST)-1);
        saveConfig(SERVER_URL, MQTT_HOST);
    });

    if (forcePortal)
        wm.startConfigPortal(WIFI_AP_NAME, WIFI_AP_PASS);
    else
        wm.autoConnect(WIFI_AP_NAME, WIFI_AP_PASS);

    if (WiFi.status()==WL_CONNECTED)
        Serial.printf("WiFi OK: %s (%d dBm)\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
    else {
        Serial.println("WiFi ulanmadi — offline rejimda ishlaydi");
    }

    // ── Server tekshiruvi ─────────────────────────────────────────────────────
    if (WiFi.status()==WL_CONNECTED) {
        Serial.print("Server tekshirilmoqda...");
        serverOk = checkServer();
        if (serverOk) {
            Serial.println(" OK");
        } else {
            Serial.println(" XATO!");
            // Server o'chiq → config AP ochiladi
            openConfigAP();
            // openConfigAP restart qiladi yoki timeout dan chiqadi
            // Agar timeout dan chiqqan bo'lsa, serverOk=false da davom etamiz
            serverOk = checkServer();  // qayta tekshirish
        }
    }

    // ── MQTT ─────────────────────────────────────────────────────────────────
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setCallback(onMqttMessage);
    mqttClient.setBufferSize(1024);
    if (serverOk) mqttConnect();

    // ── OTA ──────────────────────────────────────────────────────────────────
    if (serverOk) checkOTA();

    // ── RS-485 ───────────────────────────────────────────────────────────────
    initFcs();
    pinMode(PIN_DE, OUTPUT); digitalWrite(PIN_DE, LOW);
    Serial2.begin(9600, SERIAL_8N1, PIN_RX, PIN_TX);

    Serial.println("Hisoblagichga ulanilmoqda...");
    if (autoConnect()) {
        getStringAttr(1,OBIS_SERIAL,2,meterSerial,sizeof(meterSerial));
        Serial.printf("Serial: %s\n", meterSerial);
        detectMeterType();
        doRegister();
    } else {
        Serial.println("Hisoblagich javob bermadi.");
        doRegister();
    }

    Serial.println("Tayyor!\n");
}

// ════════════════════════════════════════════════════════════════════════════
// Loop
// ════════════════════════════════════════════════════════════════════════════
void loop() {
    // WiFi ulanishi
    if (WiFi.status()!=WL_CONNECTED) {
        WiFi.reconnect(); delay(1000); return;
    }

    // MQTT keep-alive
    if (!mqttClient.connected()) mqttConnect();
    mqttClient.loop();

    unsigned long now = millis();

    // ── Har READ_INTERVAL_MS da o'qish ───────────────────────────────────────
    if (now - lastReadMs >= READ_INTERVAL_MS || lastReadMs==0) {
        lastReadMs = now;
        Serial.println("--- O'qish ---");

        if (!dlmsConnected) {
            if (!autoConnect()) { Serial.println("Hisoblagich javob bermadi!"); return; }
            if (!meterSerial[0]) getStringAttr(1,OBIS_SERIAL,2,meterSerial,sizeof(meterSerial));
            if (strcmp(meterType,"unknown")==0) detectMeterType();
            if (!registered) doRegister();
        }

        float vl1=NAN,vl2=NAN,vl3=NAN;
        float il1=NAN,il2=NAN,il3=NAN;
        float pw=NAN,freq=NAN,energy=NAN,pf=NAN;

        getAttribute(3,OBIS_VOLT_L1,2,&vl1);
        getAttribute(3,OBIS_CURR_L1,2,&il1);
        getAttribute(3,OBIS_POWER,  2,&pw);
        getAttribute(3,OBIS_FREQ,   2,&freq);
        getAttribute(3,OBIS_ENERGY, 2,&energy);
        getAttribute(3,OBIS_PF,     2,&pf);
        if (strcmp(meterType,"TE73")==0) {
            getAttribute(3,OBIS_VOLT_L2,2,&vl2);
            getAttribute(3,OBIS_VOLT_L3,2,&vl3);
            getAttribute(3,OBIS_CURR_L2,2,&il2);
            getAttribute(3,OBIS_CURR_L3,2,&il3);
        }

        // Scaler
        if (!isnan(vl1)) vl1/=10.0f; if (!isnan(vl2)) vl2/=10.0f; if (!isnan(vl3)) vl3/=10.0f;
        if (!isnan(il1)) il1/=1000.0f; if (!isnan(il2)) il2/=1000.0f; if (!isnan(il3)) il3/=1000.0f;
        if (!isnan(freq))   freq/=100.0f;
        if (!isnan(energy)) energy/=1000.0f;

        Serial.printf("V:%.1f A:%.3f P:%.0fW F:%.2fHz E:%.3fkWh\n",
                      isnan(vl1)?0:vl1, isnan(il1)?0:il1,
                      isnan(pw)?0:pw, isnan(freq)?0:freq, isnan(energy)?0:energy);

        // Server holatini tekshir
        bool prevOk = serverOk;
        serverOk = checkServer();

        if (serverOk) {
            if (!prevOk) {
                // Server qaytdi — bufferni yuborish + ro'yxat
                Serial.println("Server qaytdi!");
                if (!registered) doRegister();
                flushBuffer();
            }
            Reading r = {now,vl1,vl2,vl3,il1,il2,il3,pw,freq,energy,pf};
            if (!sendReading(r)) {
                serverOk = false;
                bufferReading(r);
                Serial.printf("Yuborilmadi — buffer: %d ta\n", offCount);
            }
        } else {
            // Server o'chiq — bufferga yozish
            Reading r = {now,vl1,vl2,vl3,il1,il2,il3,pw,freq,energy,pf};
            bufferReading(r);
            Serial.printf("Offline — buffer: %d/%d\n", offCount, OFFLINE_BUF_SIZE);

            // Har 5 daqiqada config AP ochiladi
            static unsigned long lastApMs = 0;
            if (now - lastApMs > 300000UL || lastApMs==0) {
                lastApMs = now;
                openConfigAP();
            }
        }

        if (isnan(vl1)&&isnan(pw)) { Serial.println("DLMS xato — qayta ulanish"); doDisconnect(); }
    }

    // ── HTTP relay polling (MQTT zaxirasi) ────────────────────────────────────
    if (serverOk && now-lastCmdMs >= CMD_POLL_MS) {
        lastCmdMs = now;
        pollCommands();
    }
}
