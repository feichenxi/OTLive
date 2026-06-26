#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include <HTTPClient.h>
#include <Update.h>
#include "FS.h"
#include "SPIFFS.h"
#include "esp_heap_caps.h"

#define FIRMWARE_VERSION "3.1.1"
#define FIRMWARE_BUILD_DATE __DATE__ " " __TIME__

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

const int tcpPort = 8080;
const int webPort = 80;

const int triggerPin = 19;
const int fanPin = 20;
const int prog1Pin = 21;
const int prog2Pin = 47;
const int prog3Pin = 48;
const int prog4Pin = 45;
const int prog5Pin = 35;
const int prog6Pin = 36;
const int prog7Pin = 37;
const int prog8Pin = 38;
const int prog9Pin = 39;
const int prog10Pin = 40;

#define I2S_NUM         I2S_NUM_0
#define I2S_BCLK_IO     4
#define I2S_LRCLK_IO    6
#define I2S_DIN_IO      5

#define SAMPLE_RATE     48000
#define BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT
#define BUFFER_LEN      512
#define WAV_BUFFER_SIZE 4096
#define AUDIO_BUFFER_SIZE 4096

const int heartbeatPort = 9999;
const unsigned long heartbeatSendInterval = 5000;
const unsigned long wifiCheckInterval = 1000;
const unsigned long wifiReconnectDelay = 3000;
const int wifiMaxReconnectAttempts = 5;
const int8_t WIFI_WEAK_SIGNAL_THRESHOLD = -60;
const unsigned long WIFI_WEAK_SCAN_INTERVAL = 30000;
const int WIFI_SWITCH_CONFIRM_COUNT = 2;

bool triggerState = false;
bool fanState = false;

unsigned long triggerStartTime = 0;
float triggerDuration = 0.3;
bool triggerTimerActive = false;
bool prog1State = false;
bool prog2State = false;
bool prog3State = false;
bool prog4State = false;
bool prog5State = false;
bool prog6State = false;
bool prog7State = false;
bool prog8State = false;
bool prog9State = false;
bool prog10State = false;

bool audioEnabled_trigger = false;
bool audioEnabled_fan = false;
bool audioEnabled_prog1 = false;
bool audioEnabled_prog2 = false;
bool audioEnabled_prog3 = false;
bool audioEnabled_prog4 = false;
bool audioEnabled_prog5 = false;
bool audioEnabled_prog6 = false;
bool audioEnabled_prog7 = false;
bool audioEnabled_prog8 = false;
bool audioEnabled_prog9 = false;
bool audioEnabled_prog10 = false;

unsigned long lastHeartbeatSend = 0;
unsigned long heartbeatSeq = 0;
unsigned long lastWiFiCheck = 0;
int wifiReconnectAttempts = 0;
bool wifiWasConnected = false;
unsigned long lastWeakSignalScanTime = 0;
int consecutiveStrongSignalCount = 0;
int8_t lastDetectedStrongRssi = -100;
String lastDetectedStrongBssid = "";
bool wifiScanInProgress = false;
unsigned long wifiScanStartTime = 0;

WebServer webServer(webPort);
WiFiServer tcpServer(tcpPort);
WiFiUDP udpAudioServer;
WiFiUDP udpHeartbeat;

bool intercomEnabled = false;
unsigned long lastIntercomTime = 0;
const unsigned long intercomTimeout = 30000;

enum OTAState {
  OTA_IDLE,
  OTA_UPDATING,
  OTA_SUCCESS,
  OTA_FAILED
};
OTAState otaState = OTA_IDLE;
float otaProgress = 0.0;
String otaError = "";

unsigned long loopStartTime = 0;
unsigned long maxLoopDuration = 0;
unsigned long audioPlaybackStartTime = 0;
unsigned long lastMemoryCheck = 0;
unsigned long lastSpiffsCheck = 0;
const unsigned long memoryCheckInterval = 10000;
const unsigned long spiffsCheckInterval = 30000;
const unsigned int LOW_HEAP_THRESHOLD = 20000;
const unsigned int CRITICAL_HEAP_THRESHOLD = 10000;
const size_t SPIFFS_FULL_THRESHOLD = 100000;

enum LogEventType {
  EVENT_HEARTBEAT_ATTEMPT = 1,
  EVENT_HEARTBEAT_SUCCESS = 2,
  EVENT_HEARTBEAT_FAILED = 3,
  EVENT_WIFI_DISCONNECTED = 4,
  EVENT_WIFI_CONNECTING = 5,
  EVENT_WIFI_CONNECTED = 6,
  EVENT_WIFI_RECONNECT_START = 7,
  EVENT_WIFI_RECONNECT_SUCCESS = 8,
  EVENT_WIFI_RECONNECT_FAILED = 9,
  EVENT_LOOP_BLOCKED = 10,
  EVENT_AUDIO_START = 11,
  EVENT_AUDIO_STOP = 12,
  EVENT_RESET_DETECTED = 13,
  EVENT_MEMORY_LOW = 14,
  EVENT_LOGS_UPLOAD_START = 15,
  EVENT_LOGS_UPLOAD_SUCCESS = 16,
  EVENT_LOGS_UPLOAD_FAILED = 17,
  EVENT_SPIFFS_FULL = 18,
  EVENT_TASK_STACK_OVERFLOW = 19,
  EVENT_UDP_SEND_FAILED = 20,
  EVENT_UDP_RECV_FAILED = 21,
  EVENT_TCP_CLIENT_TIMEOUT = 22,
  EVENT_WEB_REQUEST_TIMEOUT = 23,
  EVENT_OTA_START = 24,
  EVENT_OTA_PROGRESS = 25,
  EVENT_OTA_SUCCESS = 26,
  EVENT_OTA_FAILED = 27,
  EVENT_POWER_LOW = 28,
  EVENT_TEMPERATURE_HIGH = 29,
  EVENT_WIFI_SIGNAL_WEAK = 30,
  EVENT_WIFI_SIGNAL_SCAN = 31,
  EVENT_WIFI_SIGNAL_SWITCH = 32,
  EVENT_HEAP_FRAGMENTATION = 33,
  EVENT_WATCHDOG_TRIGGERED = 34,
  EVENT_EXCEPTION_CAUGHT = 35,
  EVENT_DHCP_TIMEOUT = 36,
  EVENT_NETWORK_CONGESTION = 37
};

struct EnhancedLogEntry {
  unsigned long timestamp;
  LogEventType eventType;
  int errorCode;
  char errorMsg[96];
  int rssi;
  unsigned int freeHeap;
  size_t maxAllocHeap;
  unsigned long loopDuration;
  unsigned long maxLoopDurationVal;
  bool audioActive;
  unsigned long audioPlaybackTime;
  char resetReason[32];
  int wifiStatus;
  char wifiSSID[32];
  unsigned long ipAddr;
  char wifiBSSID[18];
  int tcpClientCount;
  int webRequestCount;
  unsigned long uptime;
  int temperature;
  size_t spiffsUsed;
  size_t spiffsTotal;
  int heapFragmentation;
  unsigned long lastHeartbeatSeq;
  unsigned long lastHeartbeatTime;
};

class HeartbeatLogger {
private:
  static const int BUFFER_SIZE = 30;
  EnhancedLogEntry* buffer;
  int writeIndex;
  int readIndex;
  int count;
  bool wasConnected;
  bool logsPendingUpload;

  String getResetReasonString();
  void copyString(char* dest, const char* src, size_t maxLen);

public:
  HeartbeatLogger();
  void init();
  void log(LogEventType eventType, int errorCode = 0, const char* errorMsg = "");
  bool hasPendingLogs();
  void markLogsForUpload();
  bool shouldUploadLogs();
  void clearPendingUpload();
  String getLogsJSON();
  void clearLogs();
  void checkConnectionState(bool currentConnected);
};

HeartbeatLogger heartbeatLogger;

typedef struct {
  bool active;
  int16_t* samples;
  size_t write_pos;
  size_t read_pos;
  float volume;
  SemaphoreHandle_t mutex;
} AudioBuffer;

AudioBuffer intercomBuffer;
AudioBuffer triggerBuffer;
TaskHandle_t mixerTaskHandle = NULL;
bool triggerAudioActive = false;
File uploadFile;
TaskHandle_t localSoundTaskHandle = NULL;

#define SOUND_QUEUE_SIZE 20
struct SoundRequest {
  char device[16];
  float soundDelay;
};
QueueHandle_t soundQueue = NULL;

void initAudioBuffers();
void mixerTask(void* parameter);
void writeToAudioBuffer(AudioBuffer* buffer, int16_t* samples, size_t count);
void handleAudioControlCommand(String jsonStr);
void connectWiFi();
void setupWebServer();
void startupBeep();
void handleTCPClient();
void handleUDPAudio();
void sendHeartbeat();
void checkWiFiStatus();
void checkTriggerTimeout();
void sendStatusResponse(WebServer& server);
void handleControlRequest(WebServer& server, String device);
void processTCPCommand(String command, WiFiClient& client);
void setupI2S();
void generateSineWave(int16_t* buffer, size_t len, int frequency, float volume);
void playTone(int frequency, int duration, float volume);
bool connectToStrongestWiFi(bool isInitial = false);
void monitorWeakSignalWiFi();
void setupOTARoutes();
void handleOTAInfo();
void handleOTAUpload();
void handleOTAUploadFinish();
void handleOTAUpdate();
void handleOTAStatus();
void handleOTAReboot();
int getRoomNumber();
String getDeviceAudioFilename(String device);
bool isAudioEnabled(String device);
void playLocalTriggerSound(String device, float soundDelay = 0);
void localSoundPlaybackTask(void* parameter);

void initAudioBuffers() {
  intercomBuffer.samples = (int16_t*)malloc(AUDIO_BUFFER_SIZE * sizeof(int16_t));
  intercomBuffer.mutex = xSemaphoreCreateMutex();
  intercomBuffer.active = false;
  intercomBuffer.write_pos = 0;
  intercomBuffer.read_pos = 0;
  intercomBuffer.volume = 1.0f;

  triggerBuffer.samples = (int16_t*)malloc(AUDIO_BUFFER_SIZE * sizeof(int16_t));
  triggerBuffer.mutex = xSemaphoreCreateMutex();
  triggerBuffer.active = false;
  triggerBuffer.write_pos = 0;
  triggerBuffer.read_pos = 0;
  triggerBuffer.volume = 0.8f;

  if (intercomBuffer.samples && triggerBuffer.samples) {
    Serial.println("[Audio] 音频缓冲区初始化成功");
  } else {
    Serial.println("[Audio] 音频缓冲区初始化失败");
  }
}

void mixerTask(void* parameter) {
  Serial.println("[Audio] 混音器任务已启动");
  int16_t mixBuffer[BUFFER_LEN];

  while (true) {
    if (triggerAudioActive) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    for (int i = 0; i < BUFFER_LEN; i++) {
      int32_t sample = 0;

      xSemaphoreTake(intercomBuffer.mutex, portMAX_DELAY);
      if (intercomBuffer.active && intercomBuffer.write_pos != intercomBuffer.read_pos) {
        sample += (int32_t)(intercomBuffer.samples[intercomBuffer.read_pos] * intercomBuffer.volume);
        intercomBuffer.read_pos = (intercomBuffer.read_pos + 1) % AUDIO_BUFFER_SIZE;
      }
      xSemaphoreGive(intercomBuffer.mutex);

      if (sample > 32767) sample = 32767;
      if (sample < -32768) sample = -32768;
      mixBuffer[i] = (int16_t)sample;
    }

    size_t bytes_written;
    i2s_write(I2S_NUM, mixBuffer, BUFFER_LEN * sizeof(int16_t), &bytes_written, portMAX_DELAY);
  }

  vTaskDelete(NULL);
}

void writeToAudioBuffer(AudioBuffer* buffer, int16_t* samples, size_t count) {
  if (!buffer || !samples || count == 0) return;

  xSemaphoreTake(buffer->mutex, portMAX_DELAY);

  for (size_t i = 0; i < count; i++) {
    buffer->samples[buffer->write_pos] = samples[i];
    buffer->write_pos = (buffer->write_pos + 1) % AUDIO_BUFFER_SIZE;
  }

  xSemaphoreGive(buffer->mutex);
}

void handleAudioControlCommand(String jsonStr) {
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, jsonStr);

  if (error) {
    Serial.printf("[Audio] JSON解析错误: %s\n", error.c_str());
    return;
  }

  const char* type = doc["type"];

  if (strcmp(type, "trigger_audio_start") == 0) {
    intercomBuffer.active = false;
    intercomBuffer.write_pos = 0;
    intercomBuffer.read_pos = 0;

    triggerAudioActive = true;
    heartbeatLogger.log(EVENT_AUDIO_START, 0, "触发音效开始");
    Serial.println("[Audio] 触发音效开始");
  } else if (strcmp(type, "trigger_audio_end") == 0) {
    triggerAudioActive = false;
    heartbeatLogger.log(EVENT_AUDIO_STOP, 0, "触发音效结束");
    Serial.println("[Audio] 触发音效结束");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n========================================");
  Serial.println("ESP32-S3 直播间控制系统启动中...");
  Serial.println("========================================\n");

  pinMode(triggerPin, OUTPUT);
  pinMode(fanPin, OUTPUT);
  pinMode(prog1Pin, OUTPUT);
  pinMode(prog2Pin, OUTPUT);
  pinMode(prog3Pin, OUTPUT);
  pinMode(prog4Pin, OUTPUT);
  pinMode(prog5Pin, OUTPUT);
  pinMode(prog6Pin, OUTPUT);
  pinMode(prog7Pin, OUTPUT);
  pinMode(prog8Pin, OUTPUT);
  pinMode(prog9Pin, OUTPUT);
  pinMode(prog10Pin, OUTPUT);
  digitalWrite(triggerPin, LOW);
  digitalWrite(fanPin, LOW);
  digitalWrite(prog1Pin, LOW);
  digitalWrite(prog2Pin, LOW);
  digitalWrite(prog3Pin, LOW);
  digitalWrite(prog4Pin, LOW);
  digitalWrite(prog5Pin, LOW);
  digitalWrite(prog6Pin, LOW);
  digitalWrite(prog7Pin, LOW);
  digitalWrite(prog8Pin, LOW);
  digitalWrite(prog9Pin, LOW);
  digitalWrite(prog10Pin, LOW);

  Serial.println("GPIO引脚初始化完成");

  if (!SPIFFS.begin(true)) {
    Serial.println("[SPIFFS] 挂载失败，已格式化");
  } else {
    Serial.println("[SPIFFS] 挂载成功");
    Serial.printf("[SPIFFS] 总空间: %u 字节\n", SPIFFS.totalBytes());
    Serial.printf("[SPIFFS] 已用空间: %u 字节\n", SPIFFS.usedBytes());
  }

  setupI2S();

  initAudioBuffers();
  xTaskCreatePinnedToCore(mixerTask, "MixerTask", 8192, NULL, 1, &mixerTaskHandle, 0);
  Serial.println("[Audio] 混音器任务已创建");

  soundQueue = xQueueCreate(SOUND_QUEUE_SIZE, sizeof(SoundRequest));
  xTaskCreate(localSoundPlaybackTask, "SoundPlayer", 8192, NULL, 2, &localSoundTaskHandle);
  Serial.println("[Audio] 音效播放常驻任务已创建");

  connectWiFi();

  delay(1000);

  tcpServer.begin();
  Serial.printf("TCP服务器已启动，端口: %d\n", tcpPort);

  udpAudioServer.begin(1234);
  Serial.println("UDP音频服务器已启动，端口: 1234");

  udpHeartbeat.begin(heartbeatPort);
  Serial.printf("UDP心跳服务已启动，端口: %d\n", heartbeatPort);

  setupWebServer();
  setupOTARoutes();

  webServer.begin();
  Serial.printf("Web服务器已启动，端口: %d\n", webPort);

  lastWeakSignalScanTime = millis();
  lastHeartbeatSend = millis();
  lastWiFiCheck = millis();
  wifiWasConnected = (WiFi.status() == WL_CONNECTED);
  heartbeatLogger.init();

  Serial.println("\n========================================\n");
  Serial.println("系统启动完成");
  Serial.println("========================================\n");

  startupBeep();
}

void loop() {
  loopStartTime = millis();

  checkTriggerTimeout();

  webServer.handleClient();
  handleTCPClient();
  handleUDPAudio();
  sendHeartbeat();
  checkWiFiStatus();

  monitorWeakSignalWiFi();

  if (millis() - lastMemoryCheck >= memoryCheckInterval) {
    lastMemoryCheck = millis();
    unsigned int freeHeap = ESP.getFreeHeap();
    size_t maxAllocHeap = ESP.getMaxAllocHeap();
    
    if (freeHeap < CRITICAL_HEAP_THRESHOLD) {
      Serial.printf("[警告] 内存严重不足: freeHeap=%u, maxAllocHeap=%u\n", freeHeap, maxAllocHeap);
      heartbeatLogger.log(EVENT_MEMORY_LOW, freeHeap, "内存严重不足");
    } else if (freeHeap < LOW_HEAP_THRESHOLD) {
      Serial.printf("[警告] 内存偏低: freeHeap=%u, maxAllocHeap=%u\n", freeHeap, maxAllocHeap);
      heartbeatLogger.log(EVENT_MEMORY_LOW, freeHeap, "内存偏低警告");
    }
    
    int fragmentation = 100 - (maxAllocHeap * 100 / freeHeap);
    if (fragmentation > 50) {
      Serial.printf("[警告] 内存碎片化严重: fragmentation=%d%%\n", fragmentation);
      heartbeatLogger.log(EVENT_HEAP_FRAGMENTATION, fragmentation, "内存碎片化严重");
    }
  }

  if (millis() - lastSpiffsCheck >= spiffsCheckInterval) {
    lastSpiffsCheck = millis();
    size_t spiffsUsed = SPIFFS.usedBytes();
    size_t spiffsTotal = SPIFFS.totalBytes();
    size_t spiffsFree = spiffsTotal - spiffsUsed;
    
    if (spiffsFree < SPIFFS_FULL_THRESHOLD) {
      Serial.printf("[警告] SPIFFS空间不足: free=%u bytes, used=%u/%u\n", spiffsFree, spiffsUsed, spiffsTotal);
      heartbeatLogger.log(EVENT_SPIFFS_FULL, spiffsFree, "SPIFFS空间不足");
    }
  }

  unsigned long loopDuration = millis() - loopStartTime;
  if (loopDuration > maxLoopDuration) {
    maxLoopDuration = loopDuration;
  }

  if (loopDuration > 1000) {
    Serial.printf("[警告] loop执行超时: %lu ms\n", loopDuration);
    heartbeatLogger.log(EVENT_LOOP_BLOCKED, loopDuration, "loop执行超时");
  }

  if (heartbeatLogger.shouldUploadLogs()) {
    Serial.println("[Logger] 开始上传心跳日志...");
    heartbeatLogger.log(EVENT_LOGS_UPLOAD_START, 0, "开始上传日志");

    String logsJSON = heartbeatLogger.getLogsJSON();

    if (logsJSON.length() > 0) {
      bool uploadSuccess = false;

      if (WiFi.status() == WL_CONNECTED) {
        udpHeartbeat.beginPacket(IPAddress(255, 255, 255, 255), heartbeatPort);
        size_t written = udpHeartbeat.write((const uint8_t*)logsJSON.c_str(), logsJSON.length());
        uploadSuccess = udpHeartbeat.endPacket();

        if (uploadSuccess && written == logsJSON.length()) {
          Serial.println("[Logger] 心跳日志上传成功");
          heartbeatLogger.log(EVENT_LOGS_UPLOAD_SUCCESS, 0, "日志上传成功");
          heartbeatLogger.clearLogs();
          heartbeatLogger.clearPendingUpload();
        } else {
          Serial.println("[Logger] 心跳日志上传失败");
          heartbeatLogger.log(EVENT_LOGS_UPLOAD_FAILED, 1, "UDP发送失败");
        }
      }
    }
  }
}

bool connectToStrongestWiFi(bool isInitial) {
  Serial.println("开始扫描WiFi网络...");
  int n = WiFi.scanNetworks();

  if (n == 0) {
    Serial.println("未发现任何WiFi网络");
    return false;
  }

  Serial.printf("发现 %d 个WiFi网络\n", n);

  int bestIndex = -1;
  int8_t bestRssi = -100;

  for (int i = 0; i < n; i++) {
    String foundSsid = WiFi.SSID(i);
    int8_t foundRssi = WiFi.RSSI(i);

    if (foundSsid == ssid) {
      Serial.printf("  - 发现同名网络: RSSI=%d dBm, BSSID=%s\n", foundRssi, WiFi.BSSIDstr(i).c_str());

      if (foundRssi > bestRssi) {
        bestRssi = foundRssi;
        bestIndex = i;
      }
    }
  }

  if (bestIndex < 0) {
    Serial.printf("未发现同名网络(%s)\n", ssid);
    return false;
  }

  Serial.printf("选择最强信号: RSSI=%d dBm, 正在连接...\n", bestRssi);

  if (WiFi.status() == WL_CONNECTED) {
    WiFi.disconnect(true);
    delay(500);
  }

  uint8_t* bssid = WiFi.BSSID(bestIndex);
  WiFi.begin(ssid, password, WiFi.channel(bestIndex), bssid);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi连接成功!");
    Serial.print("IP地址: ");
    Serial.println(WiFi.localIP());
    Serial.print("MAC地址: ");
    Serial.println(WiFi.macAddress());
    Serial.print("信号强度: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    wifiReconnectAttempts = 0;
    wifiWasConnected = true;
    heartbeatLogger.log(EVENT_WIFI_CONNECTED, WiFi.RSSI(), isInitial ? "初始连接成功" : "切换连接成功");
    return true;
  } else {
    Serial.println("\nWiFi连接失败!");

    if (isInitial) {
      Serial.println("尝试不指定BSSID连接...");

      WiFi.disconnect(true);
      delay(500);
      WiFi.begin(ssid, password);

      attempts = 0;
      while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
      }

      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi连接成功!");
        Serial.print("IP地址: ");
        Serial.println(WiFi.localIP());
        Serial.print("MAC地址: ");
        Serial.println(WiFi.macAddress());
        Serial.print("信号强度: ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
        wifiReconnectAttempts = 0;
        wifiWasConnected = true;
        heartbeatLogger.log(EVENT_WIFI_CONNECTED, WiFi.RSSI(), "备用连接成功");
        return true;
      }
    }

    Serial.println("WiFi连接失败!");
    wifiWasConnected = false;
    heartbeatLogger.log(EVENT_WIFI_DISCONNECTED, 1, "WiFi连接失败");
    return false;
  }
}

void checkTriggerTimeout() {
  if (triggerTimerActive && triggerState) {
    unsigned long elapsed = millis() - triggerStartTime;
    float elapsedSeconds = elapsed / 1000.0f;

    if (elapsedSeconds >= triggerDuration + 0.3f) {
      Serial.printf("[触发超时] 自动关闭触发装置，已持续: %.2f 秒\n", elapsedSeconds);
      triggerState = false;
      digitalWrite(triggerPin, LOW);
      triggerTimerActive = false;
    }
  }
}

void monitorWeakSignalWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  int8_t currentRssi = WiFi.RSSI();
  if (currentRssi >= WIFI_WEAK_SIGNAL_THRESHOLD) {
    if (consecutiveStrongSignalCount > 0) {
      Serial.printf("信号改善 (%d dBm >= %d dBm)，重置监控状态\n", currentRssi, WIFI_WEAK_SIGNAL_THRESHOLD);
      consecutiveStrongSignalCount = 0;
      lastDetectedStrongBssid = "";
      lastDetectedStrongRssi = -100;
    }
    return;
  }

  heartbeatLogger.log(EVENT_WIFI_SIGNAL_WEAK, currentRssi, "WiFi信号弱");

  unsigned long elapsed = millis() - lastWeakSignalScanTime;
  if (elapsed < WIFI_WEAK_SCAN_INTERVAL) {
    return;
  }

  lastWeakSignalScanTime = millis();

  Serial.printf("\n===== 弱信号监控扫描 (%d dBm < %d dBm) =====\n", currentRssi, WIFI_WEAK_SIGNAL_THRESHOLD);
  heartbeatLogger.log(EVENT_WIFI_SIGNAL_SCAN, currentRssi, "WiFi信号扫描开始");

  int n = WiFi.scanNetworks();
  if (n == 0) {
    Serial.println("未发现任何WiFi网络");
    heartbeatLogger.log(EVENT_WIFI_SIGNAL_SCAN, 0, "未发现WiFi网络");
    return;
  }

  int bestIndex = -1;
  int8_t bestRssi = -100;
  String bestBssid = "";

  for (int i = 0; i < n; i++) {
    String foundSsid = WiFi.SSID(i);
    int8_t foundRssi = WiFi.RSSI(i);

    if (foundSsid == ssid) {
      Serial.printf("  - 发现同名网络: RSSI=%d dBm, BSSID=%s\n", foundRssi, WiFi.BSSIDstr(i).c_str());

      if (foundRssi > bestRssi) { bestRssi = foundRssi; bestIndex = i; bestBssid = WiFi.BSSIDstr(i); }
    }
  }

  if (bestIndex < 0) {
    Serial.println("未发现同名网络");
    consecutiveStrongSignalCount = 0;
    lastDetectedStrongBssid = "";
    lastDetectedStrongRssi = -100;
    return;
  }

  String currentBssid = WiFi.BSSIDstr();

  if (bestBssid == currentBssid || bestRssi <= currentRssi) {
    if (consecutiveStrongSignalCount > 0) {
      Serial.printf("未发现更强信号，重置计数\n");
    }
    consecutiveStrongSignalCount = 0;
    lastDetectedStrongBssid = "";
    lastDetectedStrongRssi = -100;
    Serial.printf("===== 弱信号监控扫描完成 =====\n\n");
    return;
  }

  Serial.printf("发现更强信号: 当前=%d dBm, 新=%d dBm, BSSID=%s\n", currentRssi, bestRssi, bestBssid.c_str());

  if (bestBssid == lastDetectedStrongBssid && bestRssi == lastDetectedStrongRssi) {
    consecutiveStrongSignalCount++;
    Serial.printf("连续检测到同一强信号: %d/%d\n", consecutiveStrongSignalCount, WIFI_SWITCH_CONFIRM_COUNT);
  } else {
    consecutiveStrongSignalCount = 1;
    lastDetectedStrongBssid = bestBssid;
    lastDetectedStrongRssi = bestRssi;
    Serial.printf("发现新的强信号，开始计数: 1/%d\n", WIFI_SWITCH_CONFIRM_COUNT);
  }

  if (consecutiveStrongSignalCount >= WIFI_SWITCH_CONFIRM_COUNT) {
    Serial.println("连续检测到足够次数，执行切换...");
    heartbeatLogger.log(EVENT_WIFI_SIGNAL_SWITCH, bestRssi, "执行WiFi信号切换");

    WiFi.disconnect(true);
    delay(500);

    uint8_t* bssid = WiFi.BSSID(bestIndex);
    WiFi.begin(ssid, password, WiFi.channel(bestIndex), bssid);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi切换成功!");
      Serial.print("IP地址: ");
      Serial.println(WiFi.localIP());
      Serial.print("MAC地址: ");
      Serial.println(WiFi.macAddress());
      Serial.print("信号强度: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      wifiReconnectAttempts = 0;
      wifiWasConnected = true;
      heartbeatLogger.log(EVENT_WIFI_CONNECTED, WiFi.RSSI(), "信号切换成功");
    } else {
      Serial.println("\nWiFi切换失败，尝试重新连接原网络...");
      WiFi.disconnect(true);
      delay(500);
      WiFi.begin(ssid, password);
      heartbeatLogger.log(EVENT_WIFI_DISCONNECTED, 1, "信号切换失败");
    }

    consecutiveStrongSignalCount = 0;
    lastDetectedStrongBssid = "";
    lastDetectedStrongRssi = -100;
  }

  Serial.printf("===== 弱信号监控扫描完成 =====\n\n");
}

void connectWiFi() {
  Serial.println("WiFi初始化完成，立即扫描并连接最强信号...");
  heartbeatLogger.log(EVENT_WIFI_CONNECTING, 0, "立即扫描连接");

  if (!connectToStrongestWiFi(true)) {
    Serial.println("初始连接失败，请检查WiFi配置");
  }
}

void checkWiFiStatus() {
  if (millis() - lastWiFiCheck < wifiCheckInterval) {
    return;
  }
  lastWiFiCheck = millis();

  wl_status_t status = WiFi.status();
  heartbeatLogger.checkConnectionState(status == WL_CONNECTED);

  if (status == WL_CONNECTED) {
    if (!wifiWasConnected) {
      Serial.println("WiFi恢复连接!");
      Serial.print("IP地址: ");
      Serial.println(WiFi.localIP());
      wifiReconnectAttempts = 0;
      wifiWasConnected = true;
      heartbeatLogger.log(EVENT_WIFI_RECONNECT_SUCCESS, 0, "WiFi重连成功");

      lastHeartbeatSend = 0;
    }
    return;
  }

  if (wifiWasConnected) {
    Serial.printf("WiFi断开! 状态: %d，尝试重连...\n", status);
    wifiWasConnected = false;
    heartbeatLogger.log(EVENT_WIFI_DISCONNECTED, status, "WiFi连接断开");
  }

  wifiReconnectAttempts++;

  if (wifiReconnectAttempts <= 3) {
    Serial.printf("WiFi重连尝试 %d: WiFi.reconnect()\n", wifiReconnectAttempts);
    heartbeatLogger.log(EVENT_WIFI_RECONNECT_START, wifiReconnectAttempts, "使用reconnect()重连");
    WiFi.reconnect();
  } else if (wifiReconnectAttempts <= wifiMaxReconnectAttempts) {
    Serial.printf("WiFi重连尝试 %d: 完全重连\n", wifiReconnectAttempts);
    heartbeatLogger.log(EVENT_WIFI_RECONNECT_START, wifiReconnectAttempts, "完全重连(断开+begin)");
    WiFi.disconnect(true);
    delay(100);
    WiFi.begin(ssid, password);
  } else {
    Serial.println("WiFi重连失败次数过多，5秒后重试...");
    heartbeatLogger.log(EVENT_WIFI_RECONNECT_FAILED, wifiReconnectAttempts, "重连失败次数过多");
    wifiReconnectAttempts = 0;
  }
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (millis() - lastHeartbeatSend < heartbeatSendInterval) {
    return;
  }
  lastHeartbeatSend = millis();
  heartbeatSeq++;

  heartbeatLogger.log(EVENT_HEARTBEAT_ATTEMPT, 0, "准备发送心跳");

  StaticJsonDocument<512> doc;
  doc["type"] = "heartbeat";
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["audio_active"] = triggerAudioActive;
  doc["intercom_enabled"] = intercomEnabled;
  doc["uptime"] = millis() / 1000;
  doc["free_heap"] = ESP.getFreeHeap();
  doc["version"] = FIRMWARE_VERSION;
  doc["seq"] = heartbeatSeq;
  doc["ts"] = millis();

  JsonObject devices = doc.createNestedObject("devices");
  devices["trigger"] = triggerState;
  devices["always"] = fanState;
  devices["prog1"] = prog1State;
  devices["prog2"] = prog2State;
  devices["prog3"] = prog3State;
  devices["prog4"] = prog4State;
  devices["prog5"] = prog5State;
  devices["prog6"] = prog6State;
  devices["prog7"] = prog7State;
  devices["prog8"] = prog8State;
  devices["prog9"] = prog9State;
  devices["prog10"] = prog10State;

  char buffer[512];
  size_t len = serializeJson(doc, buffer, sizeof(buffer));

  bool udpSuccess = true;
  int errorCode = 0;

  if (!udpHeartbeat.beginPacket(IPAddress(255, 255, 255, 255), heartbeatPort)) {
    udpSuccess = false;
    errorCode = 2;
    heartbeatLogger.log(EVENT_HEARTBEAT_FAILED, errorCode, "UDP beginPacket失败");
  } else if (udpHeartbeat.write((const uint8_t*)buffer, len) != len) {
    udpSuccess = false;
    errorCode = 3;
    heartbeatLogger.log(EVENT_HEARTBEAT_FAILED, errorCode, "UDP write失败");
  } else if (!udpHeartbeat.endPacket()) {
    udpSuccess = false;
    errorCode = 4;
    heartbeatLogger.log(EVENT_HEARTBEAT_FAILED, errorCode, "UDP endPacket失败");
  }

  if (udpSuccess) {
    heartbeatLogger.log(EVENT_HEARTBEAT_SUCCESS, 0, "心跳发送成功");
    Serial.printf("[心跳] 已发送: RSSI=%d, audio=%d, heap=%u\n",
                  WiFi.RSSI(), triggerAudioActive ? 1 : 0, ESP.getFreeHeap());
  }
}

void setupWebServer() {
  const char* headerKeys[] = {"Content-Length", "Content-Type"};
  webServer.collectHeaders(headerKeys, 2);
  webServer.on("/", HTTP_GET, []() { sendStatusResponse(webServer); });
  webServer.on("/status", HTTP_GET, []() { sendStatusResponse(webServer); });
  webServer.on("/trigger", HTTP_POST, []() { handleControlRequest(webServer, "trigger"); });
  webServer.on("/always", HTTP_POST, []() { handleControlRequest(webServer, "always"); });
  webServer.on("/prog1", HTTP_POST, []() { handleControlRequest(webServer, "prog1"); });
  webServer.on("/prog2", HTTP_POST, []() { handleControlRequest(webServer, "prog2"); });
  webServer.on("/prog3", HTTP_POST, []() { handleControlRequest(webServer, "prog3"); });
  webServer.on("/prog4", HTTP_POST, []() { handleControlRequest(webServer, "prog4"); });
  webServer.on("/prog5", HTTP_POST, []() { handleControlRequest(webServer, "prog5"); });
  webServer.on("/prog6", HTTP_POST, []() { handleControlRequest(webServer, "prog6"); });
  webServer.on("/prog7", HTTP_POST, []() { handleControlRequest(webServer, "prog7"); });
  webServer.on("/prog8", HTTP_POST, []() { handleControlRequest(webServer, "prog8"); });
  webServer.on("/prog9", HTTP_POST, []() { handleControlRequest(webServer, "prog9"); });
  webServer.on("/prog10", HTTP_POST, []() { handleControlRequest(webServer, "prog10"); });
  webServer.on("/beep", HTTP_POST, []() {
    String body = webServer.arg("plain");
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, body);
    if (error) { webServer.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}"); return; }
    int duration = doc["duration"] | 200;
    int frequency = doc["frequency"] | 1000;
    float volume = doc["volume"] | 0.5;
    playTone(frequency, duration, volume);
    webServer.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Beep played\"}");
  });
  webServer.on("/set_audio_enabled", HTTP_POST, []() {
    String body = webServer.arg("plain");
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, body);
    if (error) { webServer.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}"); return; }
    String device = doc["device"] | "trigger";
    bool enabled = doc["enabled"] | false;
    Serial.printf("设置音效开关: 设备=%s, 状态=%s\n", device.c_str(), enabled ? "开启" : "关闭");
    if (device == "trigger") audioEnabled_trigger = enabled;
    else if (device == "fan") audioEnabled_fan = enabled;
    else if (device == "prog1") audioEnabled_prog1 = enabled;
    else if (device == "prog2") audioEnabled_prog2 = enabled;
    else if (device == "prog3") audioEnabled_prog3 = enabled;
    else if (device == "prog4") audioEnabled_prog4 = enabled;
    else if (device == "prog5") audioEnabled_prog5 = enabled;
    else if (device == "prog6") audioEnabled_prog6 = enabled;
    else if (device == "prog7") audioEnabled_prog7 = enabled;
    else if (device == "prog8") audioEnabled_prog8 = enabled;
    else if (device == "prog9") audioEnabled_prog9 = enabled;
    else if (device == "prog10") audioEnabled_prog10 = enabled;
    webServer.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Audio enabled updated\"}");
  });
  webServer.on("/heartbeat", HTTP_GET, []() { webServer.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"heartbeat\"}"); });
  webServer.on("/sound/upload", HTTP_POST, []() {
    webServer.send(200, "application/json", "{\"status\":\"success\"}");
  }, []() {
    HTTPUpload& upload = webServer.upload();
    if (upload.status == UPLOAD_FILE_START) {
      String filename = upload.filename;
      if (!filename.startsWith("/")) filename = "/" + filename;
      String path = filename.startsWith("/sound/") ? filename : "/sound/" + filename;
      Serial.printf("[Sound] 开始接收音效文件: %s\n", path.c_str());
      uploadFile = SPIFFS.open(path, "w");
      if (!uploadFile) {
        Serial.printf("[Sound] 无法创建文件: %s\n", path.c_str());
      }
    } else if (upload.status == UPLOAD_FILE_WRITE) {
      if (uploadFile) {
        uploadFile.write(upload.buf, upload.currentSize);
      }
    } else if (upload.status == UPLOAD_FILE_END) {
      if (uploadFile) {
        uploadFile.close();
        Serial.printf("[Sound] 音效文件接收完成: %u 字节\n", upload.totalSize);
        Serial.printf("[SPIFFS] 已用: %u / %u 字节\n", SPIFFS.usedBytes(), SPIFFS.totalBytes());
      }
    }
  });
  webServer.on("/sound/delete", HTTP_POST, []() {
    String body = webServer.arg("plain");
    StaticJsonDocument<256> doc;
    deserializeJson(doc, body);
    String device = doc["device"] | "";
    if (device.length() > 0) {
      String path = "/sound/" + device + ".wav";
      if (SPIFFS.remove(path)) {
        Serial.printf("[Sound] 音效文件已删除: %s\n", path.c_str());
        webServer.send(200, "application/json", "{\"status\":\"success\"}");
      } else {
        webServer.send(404, "application/json", "{\"status\":\"error\",\"message\":\"File not found\"}");
      }
    } else {
      webServer.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid device\"}");
    }
  });
  webServer.on("/sound/list", HTTP_GET, []() {
    StaticJsonDocument<1024> doc;
    doc["total"] = SPIFFS.totalBytes();
    doc["used"] = SPIFFS.usedBytes();
    JsonArray files = doc.createNestedArray("files");
    File root = SPIFFS.open("/sound");
    if (root && root.isDirectory()) {
      File file = root.openNextFile();
      while (file) {
        JsonObject f = files.createNestedObject();
        f["name"] = String(file.name());
        f["size"] = file.size();
        file = root.openNextFile();
      }
    }
    String response;
    serializeJson(doc, response);
    webServer.send(200, "application/json", response);
  });
  webServer.on("/restart", HTTP_POST, []() {
    webServer.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"rebooting\"}");
    delay(1000);
    ESP.restart();
  });
  webServer.onNotFound([]() { webServer.send(404, "application/json", "{\"status\":\"error\",\"message\":\"not found\"}"); });
}

void handleTCPClient() {
  WiFiClient client = tcpServer.available();

  if (!client) return;

  client.setTimeout(200);

  unsigned long startTime = millis();
  String currentLine = "";

  while (client.connected() && (millis() - startTime) < 500) {
    if (client.available()) {
      char c = client.read();
      currentLine += c;

      if (c == '\n') {
        if (currentLine.length() > 1) {
          processTCPCommand(currentLine, client);
          client.stop();
          return;
        }
        currentLine = "";
        startTime = millis();
      }
    }
  }

  client.stop();
}

void handleUDPAudio() {
  int packetSize = udpAudioServer.parsePacket();

  if (packetSize > 0) {
    uint8_t tempBuf[1024];
    int bytesRead = udpAudioServer.read(tempBuf, packetSize);

    if (packetSize <= 64) {
      String jsonStr = String((char*)tempBuf);
      if (jsonStr.startsWith("{")) {
        handleAudioControlCommand(jsonStr);
        return;
      }
    }

    if (triggerAudioActive) {
      size_t bytes_written;
      i2s_write(I2S_NUM, tempBuf, packetSize, &bytes_written, portMAX_DELAY);
      lastIntercomTime = millis();
      return;
    }

    if (!intercomEnabled) {
      intercomEnabled = true;
      Serial.println("[Audio] 房间对讲已启用");
    }

    lastIntercomTime = millis();

    writeToAudioBuffer(&intercomBuffer, (int16_t*)tempBuf, packetSize / 2);

    if (!intercomBuffer.active) {
      intercomBuffer.active = true;
    }
  } else {
    if (intercomEnabled && millis() - lastIntercomTime > intercomTimeout) {
      intercomEnabled = false;
      intercomBuffer.active = false;
      Serial.println("[Audio] 房间对讲已超时关闭");
    }
  }
}

void processTCPCommand(String command, WiFiClient& client) {
  command.trim();

  if (command.length() == 0) {
    return;
  }

  Serial.printf("收到TCP命令: %s\n", command.c_str());

  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, command);

  if (error) {
    Serial.printf("JSON解析错误: %s\n", error.c_str());
    client.println("{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
    return;
  }

  String type = doc["type"];

  if (type == "control") {
    String device = doc["device"];
    String action = doc["action"];
    bool playSound = doc["play_sound"] | false;
    float soundDelay = doc["sound_delay"] | 0.0f;

    bool newState = false;
    bool shouldUpdate = false;

    if (device == "trigger") {
      if (action == "on") {
        newState = true;
        shouldUpdate = true;
        triggerStartTime = millis();
        triggerDuration = doc["duration"] | 0.3f;
        triggerTimerActive = true;
        Serial.printf("[触发] 启动定时器，时长: %.2f 秒\n", triggerDuration);
      } else if (action == "off") {
        newState = false;
        shouldUpdate = true;
        triggerTimerActive = false;
      } else if (action == "toggle") {
        newState = !triggerState;
        shouldUpdate = true;
        if (newState) {
          triggerStartTime = millis();
          triggerDuration = doc["duration"] | 0.3f;
          triggerTimerActive = true;
          Serial.printf("[触发] 启动定时器，时长: %.2f 秒\n", triggerDuration);
        } else {
          triggerTimerActive = false;
        }
      }
      if (shouldUpdate) { triggerState = newState; digitalWrite(triggerPin, triggerState ? HIGH : LOW); }
    } else if (device == "always") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !fanState; shouldUpdate = true; }
      if (shouldUpdate) { fanState = newState; digitalWrite(fanPin, fanState ? HIGH : LOW); }
    } else if (device == "prog1") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog1State; shouldUpdate = true; }
      if (shouldUpdate) { prog1State = newState; digitalWrite(prog1Pin, prog1State ? HIGH : LOW); }
    } else if (device == "prog2") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog2State; shouldUpdate = true; }
      if (shouldUpdate) { prog2State = newState; digitalWrite(prog2Pin, prog2State ? HIGH : LOW); }
    } else if (device == "prog3") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog3State; shouldUpdate = true; }
      if (shouldUpdate) { prog3State = newState; digitalWrite(prog3Pin, prog3State ? HIGH : LOW); }
    } else if (device == "prog4") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog4State; shouldUpdate = true; }
      if (shouldUpdate) { prog4State = newState; digitalWrite(prog4Pin, prog4State ? HIGH : LOW); }
    } else if (device == "prog5") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog5State; shouldUpdate = true; }
      if (shouldUpdate) { prog5State = newState; digitalWrite(prog5Pin, prog5State ? HIGH : LOW); }
    } else if (device == "prog6") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog6State; shouldUpdate = true; }
      if (shouldUpdate) { prog6State = newState; digitalWrite(prog6Pin, prog6State ? HIGH : LOW); }
    } else if (device == "prog7") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog7State; shouldUpdate = true; }
      if (shouldUpdate) { prog7State = newState; digitalWrite(prog7Pin, prog7State ? HIGH : LOW); }
    } else if (device == "prog8") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog8State; shouldUpdate = true; }
      if (shouldUpdate) { prog8State = newState; digitalWrite(prog8Pin, prog8State ? HIGH : LOW); }
    } else if (device == "prog9") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog9State; shouldUpdate = true; }
      if (shouldUpdate) { prog9State = newState; digitalWrite(prog9Pin, prog9State ? HIGH : LOW); }
    } else if (device == "prog10") {
      if (action == "on") { newState = true; shouldUpdate = true; }
      else if (action == "off") { newState = false; shouldUpdate = true; }
      else if (action == "toggle") { newState = !prog10State; shouldUpdate = true; }
      if (shouldUpdate) { prog10State = newState; digitalWrite(prog10Pin, prog10State ? HIGH : LOW); }
    }

    if (shouldUpdate) {
      if (playSound && newState) {
        playLocalTriggerSound(device, soundDelay);
      }
      client.println("{\"status\":\"success\",\"message\":\"Device updated\"}");
    } else {
      client.println("{\"status\":\"error\",\"message\":\"Invalid device or action\"}");
    }
  } else if (type == "beep") {
    int duration = doc["duration"] | 200;
    int frequency = doc["frequency"] | 1000;
    float volume = doc["volume"] | 0.5;
    playTone(frequency, duration, volume);
    client.println("{\"status\":\"success\",\"message\":\"Beep played\"}");
  } else if (type == "status") {
    String response = "{\"status\":\"success\",";
    response += "\"audio_active\":" + String(triggerAudioActive ? "true" : "false") + ",";
    response += "\"devices\":{";
    response += "\"trigger\":" + String(triggerState ? "true" : "false") + ",";
    response += "\"always\":" + String(fanState ? "true" : "false") + ",";
    response += "\"prog1\":" + String(prog1State ? "true" : "false") + ",";
    response += "\"prog2\":" + String(prog2State ? "true" : "false") + ",";
    response += "\"prog3\":" + String(prog3State ? "true" : "false") + ",";
    response += "\"prog4\":" + String(prog4State ? "true" : "false") + ",";
    response += "\"prog5\":" + String(prog5State ? "true" : "false") + ",";
    response += "\"prog6\":" + String(prog6State ? "true" : "false") + ",";
    response += "\"prog7\":" + String(prog7State ? "true" : "false") + ",";
    response += "\"prog8\":" + String(prog8State ? "true" : "false") + ",";
    response += "\"prog9\":" + String(prog9State ? "true" : "false") + ",";
    response += "\"prog10\":" + String(prog10State ? "true" : "false");
    response += "},";
    response += "\"rssi\":" + String(WiFi.RSSI()) + "}";
    client.println(response);
  } else if (type == "set_audio_enabled") {
    String device = doc["device"] | "trigger";
    bool enabled = doc["enabled"] | false;
    Serial.printf("设置音效开关: 设备=%s, 状态=%s\n", device.c_str(), enabled ? "开启" : "关闭");
    if (device == "trigger") audioEnabled_trigger = enabled;
    else if (device == "fan") audioEnabled_fan = enabled;
    else if (device == "prog1") audioEnabled_prog1 = enabled;
    else if (device == "prog2") audioEnabled_prog2 = enabled;
    else if (device == "prog3") audioEnabled_prog3 = enabled;
    else if (device == "prog4") audioEnabled_prog4 = enabled;
    else if (device == "prog5") audioEnabled_prog5 = enabled;
    else if (device == "prog6") audioEnabled_prog6 = enabled;
    else if (device == "prog7") audioEnabled_prog7 = enabled;
    else if (device == "prog8") audioEnabled_prog8 = enabled;
    else if (device == "prog9") audioEnabled_prog9 = enabled;
    else if (device == "prog10") audioEnabled_prog10 = enabled;
    client.println("{\"status\":\"success\",\"message\":\"Audio enabled updated\"}");
  } else if (type == "heartbeat") {
    client.println("{\"status\":\"ok\",\"message\":\"heartbeat\"}");
  } else {
    client.println("{\"status\":\"error\",\"message\":\"Unknown command\"}");
  }
}

void handleControlRequest(WebServer& server, String device) {
  String body = server.arg("plain");

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, body);

  if (error) {
    server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
    return;
  }

  String action = doc["action"];
  bool newState = false;
  bool shouldUpdate = false;

  if (device == "trigger") {
    if (action == "on") {
      newState = true;
      shouldUpdate = true;
      triggerStartTime = millis();
      triggerDuration = doc["duration"] | 0.3f;
      triggerTimerActive = true;
      Serial.printf("[触发] 启动定时器，时长: %.2f 秒\n", triggerDuration);
    } else if (action == "off") {
      newState = false;
      shouldUpdate = true;
      triggerTimerActive = false;
    } else if (action == "toggle") {
      newState = !triggerState;
      shouldUpdate = true;
      if (newState) {
        triggerStartTime = millis();
        triggerDuration = doc["duration"] | 0.3f;
        triggerTimerActive = true;
        Serial.printf("[触发] 启动定时器，时长: %.2f 秒\n", triggerDuration);
      } else {
        triggerTimerActive = false;
      }
    }
    if (shouldUpdate) { triggerState = newState; digitalWrite(triggerPin, triggerState ? HIGH : LOW); }
  } else if (device == "always") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !fanState; shouldUpdate = true; }
    if (shouldUpdate) { fanState = newState; digitalWrite(fanPin, fanState ? HIGH : LOW); }
  } else if (device == "prog1") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog1State; shouldUpdate = true; }
    if (shouldUpdate) { prog1State = newState; digitalWrite(prog1Pin, prog1State ? HIGH : LOW); }
  } else if (device == "prog2") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog2State; shouldUpdate = true; }
    if (shouldUpdate) { prog2State = newState; digitalWrite(prog2Pin, prog2State ? HIGH : LOW); }
  } else if (device == "prog3") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog3State; shouldUpdate = true; }
    if (shouldUpdate) { prog3State = newState; digitalWrite(prog3Pin, prog3State ? HIGH : LOW); }
  } else if (device == "prog4") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog4State; shouldUpdate = true; }
    if (shouldUpdate) { prog4State = newState; digitalWrite(prog4Pin, prog4State ? HIGH : LOW); }
  } else if (device == "prog5") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog5State; shouldUpdate = true; }
    if (shouldUpdate) { prog5State = newState; digitalWrite(prog5Pin, prog5State ? HIGH : LOW); }
  } else if (device == "prog6") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog6State; shouldUpdate = true; }
    if (shouldUpdate) { prog6State = newState; digitalWrite(prog6Pin, prog6State ? HIGH : LOW); }
  } else if (device == "prog7") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog7State; shouldUpdate = true; }
    if (shouldUpdate) { prog7State = newState; digitalWrite(prog7Pin, prog7State ? HIGH : LOW); }
  } else if (device == "prog8") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog8State; shouldUpdate = true; }
    if (shouldUpdate) { prog8State = newState; digitalWrite(prog8Pin, prog8State ? HIGH : LOW); }
  } else if (device == "prog9") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog9State; shouldUpdate = true; }
    if (shouldUpdate) { prog9State = newState; digitalWrite(prog9Pin, prog9State ? HIGH : LOW); }
  } else if (device == "prog10") {
    if (action == "on") { newState = true; shouldUpdate = true; }
    else if (action == "off") { newState = false; shouldUpdate = true; }
    else if (action == "toggle") { newState = !prog10State; shouldUpdate = true; }
    if (shouldUpdate) { prog10State = newState; digitalWrite(prog10Pin, prog10State ? HIGH : LOW); }
  }

  server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Device updated\"}");
}

void sendStatusResponse(WebServer& server) {
  String response = "{\"status\":\"success\",";
  response += "\"audio_active\":" + String(triggerAudioActive ? "true" : "false") + ",";
  response += "\"devices\":{";
  response += "\"trigger\":" + String(triggerState ? "true" : "false") + ",";
  response += "\"always\":" + String(fanState ? "true" : "false") + ",";
  response += "\"prog1\":" + String(prog1State ? "true" : "false") + ",";
  response += "\"prog2\":" + String(prog2State ? "true" : "false") + ",";
  response += "\"prog3\":" + String(prog3State ? "true" : "false") + ",";
  response += "\"prog4\":" + String(prog4State ? "true" : "false") + ",";
  response += "\"prog5\":" + String(prog5State ? "true" : "false") + ",";
  response += "\"prog6\":" + String(prog6State ? "true" : "false") + ",";
  response += "\"prog7\":" + String(prog7State ? "true" : "false") + ",";
  response += "\"prog8\":" + String(prog8State ? "true" : "false") + ",";
  response += "\"prog9\":" + String(prog9State ? "true" : "false") + ",";
  response += "\"prog10\":" + String(prog10State ? "true" : "false");
  response += "},";
  response += "\"rssi\":" + String(WiFi.RSSI()) + "}";

  server.send(200, "application/json", response);
}

void startupBeep() {
  Serial.println("启动提示音...");
  playTone(1000, 100, 0.5);
  delay(100);
  playTone(1200, 100, 0.5);
  delay(100);
  playTone(1500, 100, 0.5);
  Serial.println("启动提示音完成");
}

void setupI2S() {
  Serial.println("初始化I2S接口（PCM5102A）- ESP32-S3...");

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCLK_IO,
    .ws_io_num = I2S_LRCLK_IO,
    .data_out_num = I2S_DIN_IO,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM);

  Serial.printf("I2S初始化完成: BCLK=%d, LRCLK=%d, DIN=%d, 采样率=%d Hz\n",
                I2S_BCLK_IO, I2S_LRCLK_IO, I2S_DIN_IO, SAMPLE_RATE);
}

void generateSineWave(int16_t* buffer, size_t len, int frequency, float volume) {
  for (size_t i = 0; i < len; i++) {
    float t = (float)i / SAMPLE_RATE;
    buffer[i] = (int16_t)(32767.0f * volume * sin(2.0f * PI * frequency * t));
  }
}

void playTone(int frequency, int duration, float volume) {
  Serial.printf("播放音调: 频率=%dHz, 时长=%dms, 音量=%.2f\n", frequency, duration, volume);

  intercomBuffer.active = false;
  intercomBuffer.write_pos = 0;
  intercomBuffer.read_pos = 0;

  triggerAudioActive = true;

  int16_t audioBuffer[BUFFER_LEN];
  size_t total_samples = (SAMPLE_RATE * duration) / 1000;
  size_t samples_played = 0;

  while (samples_played < total_samples) {
    size_t samples_to_generate = min((size_t)BUFFER_LEN, total_samples - samples_played);
    generateSineWave(audioBuffer, samples_to_generate, frequency, volume);
    size_t bytes_written;
    i2s_write(I2S_NUM, audioBuffer, samples_to_generate * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    samples_played += samples_to_generate;
  }

  triggerAudioActive = false;
  Serial.println("[Audio] 音调播放结束");
}

HeartbeatLogger::HeartbeatLogger() {
  writeIndex = 0;
  readIndex = 0;
  count = 0;
  wasConnected = false;
  logsPendingUpload = false;
  buffer = nullptr;
}

void HeartbeatLogger::init() {
  if (buffer == nullptr) {
    buffer = (EnhancedLogEntry*)heap_caps_malloc(BUFFER_SIZE * sizeof(EnhancedLogEntry), MALLOC_CAP_8BIT);
    if (buffer) {
      memset(buffer, 0, BUFFER_SIZE * sizeof(EnhancedLogEntry));
      Serial.printf("[Logger] 缓冲区已分配: %d条, %d字节\n", BUFFER_SIZE, BUFFER_SIZE * (int)sizeof(EnhancedLogEntry));
    } else {
      Serial.println("[Logger] 缓冲区分配失败!");
    }
  }
  wasConnected = (WiFi.status() == WL_CONNECTED);
  String resetReason = getResetReasonString();
  if (resetReason.length() > 0) {
    log(EVENT_RESET_DETECTED, 0, resetReason.c_str());
  }
}

String HeartbeatLogger::getResetReasonString() {
  esp_reset_reason_t reason = esp_reset_reason();
  switch (reason) {
    case ESP_RST_POWERON: return "POWERON_RESET";
    case ESP_RST_SW: return "SW_RESET";
    case ESP_RST_INT_WDT: return "INT_WDT_RESET";
    case ESP_RST_TASK_WDT: return "TASK_WDT_RESET";
    case ESP_RST_WDT: return "WDT_RESET";
    case ESP_RST_DEEPSLEEP: return "DEEPSLEEP_RESET";
    case ESP_RST_BROWNOUT: return "BROWNOUT_RESET";
    case ESP_RST_SDIO: return "SDIO_RESET";
    default: return String("UNKNOWN_") + String(reason);
  }
}

void HeartbeatLogger::copyString(char* dest, const char* src, size_t maxLen) {
  if (dest == NULL || src == NULL || maxLen == 0) return;
  size_t i;
  for (i = 0; i < maxLen - 1 && src[i] != '\0'; i++) {
    dest[i] = src[i];
  }
  dest[i] = '\0';
}

void HeartbeatLogger::log(LogEventType eventType, int errorCode, const char* errorMsg) {
  if (buffer == nullptr) return;
  EnhancedLogEntry entry;
  memset(&entry, 0, sizeof(entry));

  entry.timestamp = millis();
  entry.eventType = eventType;
  entry.errorCode = errorCode;
  copyString(entry.errorMsg, errorMsg, sizeof(entry.errorMsg));

  if (WiFi.status() == WL_CONNECTED) {
    entry.rssi = WiFi.RSSI();
    IPAddress ip = WiFi.localIP();
    entry.ipAddr = ip;
    copyString(entry.wifiBSSID, WiFi.BSSIDstr().c_str(), sizeof(entry.wifiBSSID));
  } else {
    entry.rssi = -100;
    entry.ipAddr = 0;
    copyString(entry.wifiBSSID, "", sizeof(entry.wifiBSSID));
  }

  entry.freeHeap = ESP.getFreeHeap();
  entry.maxAllocHeap = ESP.getMaxAllocHeap();
  entry.loopDuration = 0;
  entry.maxLoopDurationVal = maxLoopDuration;
  entry.audioActive = triggerAudioActive;

  if (triggerAudioActive && audioPlaybackStartTime > 0) {
    entry.audioPlaybackTime = millis() - audioPlaybackStartTime;
  } else {
    entry.audioPlaybackTime = 0;
  }

  entry.wifiStatus = WiFi.status();
  copyString(entry.wifiSSID, ssid, sizeof(entry.wifiSSID));
  
  entry.uptime = millis() / 1000;
  entry.temperature = temperatureRead();
  entry.spiffsUsed = SPIFFS.usedBytes();
  entry.spiffsTotal = SPIFFS.totalBytes();
  entry.heapFragmentation = 100 - (entry.maxAllocHeap * 100 / entry.freeHeap);
  entry.lastHeartbeatSeq = heartbeatSeq;
  entry.lastHeartbeatTime = lastHeartbeatSend;
  entry.tcpClientCount = 0;
  entry.webRequestCount = 0;
  copyString(entry.resetReason, "", sizeof(entry.resetReason));

  buffer[writeIndex] = entry;
  writeIndex = (writeIndex + 1) % BUFFER_SIZE;

  if (count < BUFFER_SIZE) {
    count++;
  } else {
    readIndex = (readIndex + 1) % BUFFER_SIZE;
  }
}

bool HeartbeatLogger::hasPendingLogs() {
  return count > 0;
}

void HeartbeatLogger::markLogsForUpload() {
  logsPendingUpload = true;
}

bool HeartbeatLogger::shouldUploadLogs() {
  return logsPendingUpload && count > 0 && WiFi.status() == WL_CONNECTED;
}

void HeartbeatLogger::clearPendingUpload() {
  logsPendingUpload = false;
}

String HeartbeatLogger::getLogsJSON() {
  if (buffer == nullptr) return "";
  StaticJsonDocument<8192> doc;
  doc["type"] = "heartbeat_logs";
  doc["room_id"] = getRoomNumber();

  JsonArray logsArray = doc.createNestedArray("logs");

  int idx = readIndex;
  for (int i = 0; i < count; i++) {
    EnhancedLogEntry entry = buffer[idx];

    JsonObject logObj = logsArray.createNestedObject();
    logObj["timestamp"] = entry.timestamp;
    logObj["event_type"] = entry.eventType;
    logObj["error_code"] = entry.errorCode;
    logObj["error_msg"] = entry.errorMsg;
    logObj["rssi"] = entry.rssi;
    logObj["free_heap"] = entry.freeHeap;
    logObj["max_alloc_heap"] = entry.maxAllocHeap;
    logObj["loop_duration"] = entry.loopDuration;
    logObj["max_loop_duration"] = entry.maxLoopDurationVal;
    logObj["audio_active"] = entry.audioActive;
    logObj["audio_playback_time"] = entry.audioPlaybackTime;
    logObj["wifi_status"] = entry.wifiStatus;
    logObj["wifi_ssid"] = entry.wifiSSID;
    logObj["wifi_bssid"] = entry.wifiBSSID;
    logObj["uptime"] = entry.uptime;
    logObj["temperature"] = entry.temperature;
    logObj["spiffs_used"] = entry.spiffsUsed;
    logObj["spiffs_total"] = entry.spiffsTotal;
    logObj["heap_fragmentation"] = entry.heapFragmentation;
    logObj["last_heartbeat_seq"] = entry.lastHeartbeatSeq;
    logObj["last_heartbeat_time"] = entry.lastHeartbeatTime;
    logObj["reset_reason"] = entry.resetReason;
    
    idx = (idx + 1) % BUFFER_SIZE;
  }
  
  String jsonStr;
  serializeJson(doc, jsonStr);
  return jsonStr;
}

void HeartbeatLogger::clearLogs() {
  writeIndex = 0;
  readIndex = 0;
  count = 0;
  if (buffer) memset(buffer, 0, BUFFER_SIZE * sizeof(EnhancedLogEntry));
}

void HeartbeatLogger::checkConnectionState(bool currentConnected) {
  if (currentConnected && !wasConnected) {
    Serial.println("[Logger] WiFi恢复连接，标记日志待上传");
    markLogsForUpload();
  }
  wasConnected = currentConnected;
}

void setupOTARoutes() {
  webServer.on("/ota/info", HTTP_GET, handleOTAInfo);
  webServer.on("/ota/upload", HTTP_POST, handleOTAUploadFinish, handleOTAUpload);
  webServer.on("/ota/update", HTTP_PUT, handleOTAUpdate);
  webServer.on("/ota/status", HTTP_GET, handleOTAStatus);
  webServer.on("/ota/reboot", HTTP_POST, handleOTAReboot);
  Serial.println("[OTA] OTA路由已设置");
}

void handleOTAInfo() {
  StaticJsonDocument<512> doc;
  doc["status"] = "success";
  doc["version"] = FIRMWARE_VERSION;
  doc["build_date"] = FIRMWARE_BUILD_DATE;
  doc["mac"] = WiFi.macAddress();
  doc["ip"] = WiFi.localIP().toString();
  doc["board"] = "esp32-s3-n16r8";
  doc["free_heap"] = ESP.getFreeHeap();
  doc["uptime"] = millis() / 1000;
  
  String response;
  serializeJson(doc, response);
  webServer.send(200, "application/json", response);
  
  Serial.printf("[OTA] 固件信息查询: version=%s, mac=%s\n", FIRMWARE_VERSION, WiFi.macAddress().c_str());
}

void handleOTAUpload() {
  HTTPUpload& upload = webServer.upload();
  
  if (upload.status == UPLOAD_FILE_START) {
    Serial.println("[OTA] 开始接收固件...");
    otaState = OTA_UPDATING;
    otaProgress = 0.0;
    otaError = "";
    
    size_t freeSpace = ESP.getFreeSketchSpace();
    Serial.printf("[OTA] 可用OTA空间: %u 字节\n", freeSpace);
    Serial.printf("[OTA] 自由堆: %u 字节\n", ESP.getFreeHeap());
    Serial.printf("[OTA] 上传文件名: %s, 总大小: %u\n", upload.filename.c_str(), upload.totalSize);
    
    if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
      otaState = OTA_FAILED;
      otaError = "Update.begin err=" + String(Update.getError());
      Serial.printf("[OTA] 错误: %s\n", otaError.c_str());
    } else {
      Serial.printf("[OTA] Update.begin成功, 目标大小: %u\n", Update.size());
    }
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    if (otaState == OTA_UPDATING) {
      size_t written = Update.write(upload.buf, upload.currentSize);
      if (written != upload.currentSize) {
        otaState = OTA_FAILED;
        otaError = "Update.write err=" + String(Update.getError()) + " written=" + String(written) + " expected=" + String(upload.currentSize);
        Serial.printf("[OTA] 错误: %s\n", otaError.c_str());
      } else {
        if (Update.progress() % 102400 < upload.currentSize) {
          Serial.printf("[OTA] 进度: %u/%u 字节 (%.1f%%), 堆: %u\n", 
            Update.progress(), Update.size(), 
            Update.size() > 0 ? (float)Update.progress() / Update.size() * 100 : 0,
            ESP.getFreeHeap());
        }
      }
    }
  } else if (upload.status == UPLOAD_FILE_END) {
    if (otaState == OTA_UPDATING) {
      Serial.printf("[OTA] 上传完成, progress=%u, size=%u, totalSize=%u\n", 
        Update.progress(), Update.size(), upload.totalSize);
      if (Update.end(true)) {
        otaState = OTA_SUCCESS;
        otaProgress = 100.0;
        Serial.println("[OTA] 固件接收完成，等待重启");
      } else {
        otaState = OTA_FAILED;
        otaError = "Update.end err=" + String(Update.getError());
        Serial.printf("[OTA] 错误: %s\n", otaError.c_str());
      }
    }
  }
}

void handleOTAUploadFinish() {
  StaticJsonDocument<512> doc;
  
  if (otaState == OTA_SUCCESS) {
    doc["status"] = "success";
    doc["message"] = "Firmware uploaded successfully, rebooting...";
    webServer.send(200, "application/json", doc.as<String>());
    Serial.println("[OTA] 固件上传成功，3秒后自动重启...");
    webServer.stop();
    delay(3000);
    ESP.restart();
  } else {
    doc["status"] = "error";
    doc["message"] = otaError.length() > 0 ? otaError : "Unknown error";
    doc["free_heap"] = ESP.getFreeHeap();
    webServer.send(500, "application/json", doc.as<String>());
    Serial.printf("[OTA] 固件上传失败: %s\n", otaError.c_str());
  }
}

void handleOTAStatus() {
  StaticJsonDocument<256> doc;
  doc["status"] = "success";
  
  String stateStr;
  switch (otaState) {
    case OTA_IDLE: stateStr = "idle"; break;
    case OTA_UPDATING: stateStr = "updating"; break;
    case OTA_SUCCESS: stateStr = "success"; break;
    case OTA_FAILED: stateStr = "failed"; break;
    default: stateStr = "unknown"; break;
  }
  
  doc["ota_state"] = stateStr;
  doc["progress"] = otaProgress;
  if (otaError.length() > 0) {
    doc["error"] = otaError;
  }
  
  String response;
  serializeJson(doc, response);
  webServer.send(200, "application/json", response);
}

void handleOTAReboot() {
  StaticJsonDocument<256> doc;
  doc["status"] = "success";
  doc["message"] = "Rebooting...";
  
  String response;
  serializeJson(doc, response);
  webServer.send(200, "application/json", response);
  
  Serial.println("[OTA] 收到重启命令，2秒后重启...");
  webServer.stop();
  delay(2000);
  ESP.restart();
}

void handleOTAUpdate() {
  WiFiClient client = webServer.client();
  
  String contentLengthStr = webServer.header("Content-Length");
  size_t contentLength = contentLengthStr.toInt();
  
  Serial.printf("[OTA2] PUT固件更新开始, Content-Length: %u\n", contentLength);
  Serial.printf("[OTA2] 自由堆: %u 字节\n", ESP.getFreeHeap());
  
  if (contentLength == 0) {
    webServer.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Content-Length required\"}");
    return;
  }
  
  otaState = OTA_UPDATING;
  otaProgress = 0.0;
  otaError = "";
  
  if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
    otaState = OTA_FAILED;
    otaError = "Update.begin err=" + String(Update.getError());
    webServer.send(500, "application/json", "{\"status\":\"error\",\"message\":\"" + otaError + "\"}");
    Serial.printf("[OTA2] 错误: %s\n", otaError.c_str());
    return;
  }
  
  size_t totalWritten = 0;
  uint8_t buf[4096];
  size_t lastProgress = 0;
  unsigned long lastDataTime = millis();
  
  while (totalWritten < contentLength && client.connected()) {
    size_t available = client.available();
    if (available > 0) {
      size_t toRead = min(available, sizeof(buf));
      size_t bytesRead = client.read(buf, toRead);
      
      if (bytesRead > 0) {
        size_t written = Update.write(buf, bytesRead);
        if (written != bytesRead) {
          otaState = OTA_FAILED;
          otaError = "Update.write err=" + String(Update.getError());
          Serial.printf("[OTA2] 写入错误: written=%u expected=%u\n", written, bytesRead);
          break;
        }
        totalWritten += written;
        lastDataTime = millis();
        
        if (totalWritten - lastProgress >= 102400) {
          Serial.printf("[OTA2] 进度: %u/%u (%.1f%%), 堆: %u\n", 
            totalWritten, contentLength, (float)totalWritten / contentLength * 100, ESP.getFreeHeap());
          lastProgress = totalWritten;
        }
      }
    } else {
      delay(1);
      if (millis() - lastDataTime > 30000) {
        otaState = OTA_FAILED;
        otaError = "Timeout: no data for 30s";
        Serial.printf("[OTA2] 超时: %u/%u 字节\n", totalWritten, contentLength);
        break;
      }
    }
  }
  
  if (otaState == OTA_UPDATING) {
    Serial.printf("[OTA2] 上传完成: %u/%u 字节\n", totalWritten, contentLength);
    if (Update.end(true)) {
      otaState = OTA_SUCCESS;
      otaProgress = 100.0;
      Serial.println("[OTA2] 固件验证通过，等待重启");
      
      StaticJsonDocument<256> doc;
      doc["status"] = "success";
      doc["message"] = "Firmware uploaded successfully, rebooting...";
      String response;
      serializeJson(doc, response);
      webServer.send(200, "application/json", response);
      
      delay(100);
      webServer.stop();
      delay(3000);
      ESP.restart();
    } else {
      otaState = OTA_FAILED;
      otaError = "Update.end err=" + String(Update.getError());
      Serial.printf("[OTA2] 验证失败: %s\n", otaError.c_str());
      
      StaticJsonDocument<512> doc;
      doc["status"] = "error";
      doc["message"] = otaError;
      doc["written"] = totalWritten;
      doc["expected"] = contentLength;
      String response;
      serializeJson(doc, response);
      webServer.send(500, "application/json", response);
    }
  } else {
    StaticJsonDocument<512> doc;
    doc["status"] = "error";
    doc["message"] = otaError;
    doc["written"] = totalWritten;
    doc["expected"] = contentLength;
    String response;
    serializeJson(doc, response);
    webServer.send(500, "application/json", response);
  }
}

void handleOTAUpdateFinish() {
  StaticJsonDocument<512> doc;
  
  if (otaState == OTA_SUCCESS) {
    doc["status"] = "success";
    doc["message"] = "Firmware uploaded successfully, rebooting...";
    webServer.send(200, "application/json", doc.as<String>());
    Serial.println("[OTA2] 固件上传成功，3秒后自动重启...");
    webServer.stop();
    delay(3000);
    ESP.restart();
  } else {
    doc["status"] = "error";
    doc["message"] = otaError.length() > 0 ? otaError : "Unknown error";
    doc["free_heap"] = ESP.getFreeHeap();
    webServer.send(500, "application/json", doc.as<String>());
    Serial.printf("[OTA2] 固件上传失败: %s\n", otaError.c_str());
  }
}

int getRoomNumber() {
  if (WiFi.status() != WL_CONNECTED) {
    return 1; // 默认1号房
  }
  IPAddress ip = WiFi.localIP();
  int lastOctet = ip[3]; // 获取最后一位
  int roomNumber = lastOctet - 100; // 101→1, 102→2, ...
  if (roomNumber < 1) roomNumber = 1;
  if (roomNumber > 12) roomNumber = 12; // 最多12房
  return roomNumber;
}

String getDeviceAudioFilename(String device) {
  if (device == "trigger") return "触发装置.wav";
  if (device == "fan") return "常动装置.wav";
  if (device == "prog1") return "编程21.wav";
  if (device == "prog2") return "编程47.wav";
  if (device == "prog3") return "编程48.wav";
  if (device == "prog4") return "编程45.wav";
  if (device == "prog5") return "编程35.wav";
  if (device == "prog6") return "编程36.wav";
  if (device == "prog7") return "编程37.wav";
  if (device == "prog8") return "编程38.wav";
  if (device == "prog9") return "编程39.wav";
  if (device == "prog10") return "编程40.wav";
  return device + ".wav"; // 默认
}

bool isAudioEnabled(String device) {
  if (device == "trigger") return audioEnabled_trigger;
  if (device == "fan") return audioEnabled_fan;
  if (device == "prog1") return audioEnabled_prog1;
  if (device == "prog2") return audioEnabled_prog2;
  if (device == "prog3") return audioEnabled_prog3;
  if (device == "prog4") return audioEnabled_prog4;
  if (device == "prog5") return audioEnabled_prog5;
  if (device == "prog6") return audioEnabled_prog6;
  if (device == "prog7") return audioEnabled_prog7;
  if (device == "prog8") return audioEnabled_prog8;
  if (device == "prog9") return audioEnabled_prog9;
  if (device == "prog10") return audioEnabled_prog10;
  return false;
}

void localSoundPlaybackTask(void* parameter) {
  Serial.println("[Audio] 音效播放常驻任务已启动");
  SoundRequest req;

  while (true) {
    if (xQueueReceive(soundQueue, &req, portMAX_DELAY)) {
      if (req.soundDelay > 0) {
        triggerAudioActive = true;
        Serial.printf("[Audio] 音效延时 %.1f 秒后播放\n", req.soundDelay);
        vTaskDelay(pdMS_TO_TICKS((int)(req.soundDelay * 1000)));
      }

      String filename = "/sound/" + String(req.device) + ".wav";

      if (!SPIFFS.exists(filename)) {
        Serial.printf("[Audio] 音效文件不存在: %s\n", filename.c_str());
        if (uxQueueMessagesWaiting(soundQueue) == 0) {
          triggerAudioActive = false;
        }
        continue;
      }

      File wavFile = SPIFFS.open(filename, "r");
      if (!wavFile) {
        Serial.printf("[Audio] 无法打开音效文件: %s\n", filename.c_str());
        if (uxQueueMessagesWaiting(soundQueue) == 0) {
          triggerAudioActive = false;
        }
        continue;
      }

      wavFile.seek(44);

      intercomBuffer.active = false;
      intercomBuffer.write_pos = 0;
      intercomBuffer.read_pos = 0;

      triggerAudioActive = true;

      int16_t readBuffer[BUFFER_LEN];

      while (wavFile.available() >= sizeof(int16_t)) {
        size_t bytesRead = wavFile.read((uint8_t*)readBuffer, sizeof(readBuffer));
        size_t samplesRead = bytesRead / sizeof(int16_t);

        if (samplesRead == 0) break;

        for (size_t i = 0; i < samplesRead; i++) {
          readBuffer[i] = (int16_t)(readBuffer[i] * 0.8f);
        }

        size_t bytes_written;
        i2s_write(I2S_NUM, readBuffer, samplesRead * sizeof(int16_t), &bytes_written, portMAX_DELAY);
      }

      wavFile.close();

      heartbeatLogger.log(EVENT_AUDIO_STOP, 0, "本地音效播放结束");
      Serial.printf("[Audio] 本地音效播放结束: %s\n", req.device);

      if (uxQueueMessagesWaiting(soundQueue) == 0) {
        triggerAudioActive = false;
      }
    }
  }
}

void playLocalTriggerSound(String device, float soundDelay) {
  SoundRequest req;
  strncpy(req.device, device.c_str(), sizeof(req.device) - 1);
  req.device[sizeof(req.device) - 1] = '\0';
  req.soundDelay = soundDelay;

  if (xQueueSend(soundQueue, &req, 0) != pdPASS) {
    Serial.println("[Audio] 音效队列已满，丢弃本次请求");
  } else {
    triggerAudioActive = true;
    heartbeatLogger.log(EVENT_AUDIO_START, 0, "本地音效加入队列");
    Serial.printf("[Audio] 音效加入队列: %s, 延时: %.1f秒, 队列剩余: %d\n", device.c_str(), soundDelay, uxQueueMessagesWaiting(soundQueue));
  }
}