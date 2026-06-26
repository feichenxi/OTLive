# ESP32-S3离线原因排查系统

## 📋 系统概述

本系统用于自动诊断ESP32-S3设备离线原因，通过完善的日志记录体系，能够准确定位离线发生的根本原因。

**实施日期**: 2025-05-30  
**固件版本**: 3.1.1  
**适用设备**: ESP32-S3

---

## 🎯 核心功能

### 1. ESP32端日志增强

#### 新增事件类型（LogEventType枚举）

| 事件代码 | 事件名称 | 说明 |
|---------|---------|------|
| 1 | EVENT_HEARTBEAT_ATTEMPT | 心跳尝试 |
| 2 | EVENT_HEARTBEAT_SUCCESS | 心跳成功 |
| 3 | EVENT_HEARTBEAT_FAILED | 心跳失败 |
| 4 | EVENT_WIFI_DISCONNECTED | WiFi断开 |
| 5 | EVENT_WIFI_CONNECTING | WiFi连接中 |
| 6 | EVENT_WIFI_CONNECTED | WiFi已连接 |
| 7 | EVENT_WIFI_RECONNECT_START | WiFi重连开始 |
| 8 | EVENT_WIFI_RECONNECT_SUCCESS | WiFi重连成功 |
| 9 | EVENT_WIFI_RECONNECT_FAILED | WiFi重连失败 |
| 10 | EVENT_LOOP_BLOCKED | Loop阻塞 |
| 11 | EVENT_AUDIO_START | 音频开始 |
| 12 | EVENT_AUDIO_STOP | 音频停止 |
| 13 | EVENT_RESET_DETECTED | 系统重启 |
| 14 | EVENT_MEMORY_LOW | 内存不足 |
| 15 | EVENT_LOGS_UPLOAD_START | 日志上传开始 |
| 16 | EVENT_LOGS_UPLOAD_SUCCESS | 日志上传成功 |
| 17 | EVENT_LOGS_UPLOAD_FAILED | 日志上传失败 |
| 18 | EVENT_SPIFFS_FULL | SPIFFS空间不足 |
| 19 | EVENT_TASK_STACK_OVERFLOW | 任务栈溢出 |
| 20 | EVENT_UDP_SEND_FAILED | UDP发送失败 |
| 21 | EVENT_UDP_RECV_FAILED | UDP接收失败 |
| 22 | EVENT_TCP_CLIENT_TIMEOUT | TCP客户端超时 |
| 23 | EVENT_WEB_REQUEST_TIMEOUT | Web请求超时 |
| 24 | EVENT_OTA_START | OTA开始 |
| 25 | EVENT_OTA_PROGRESS | OTA进度 |
| 26 | EVENT_OTA_SUCCESS | OTA成功 |
| 27 | EVENT_OTA_FAILED | OTA失败 |
| 28 | EVENT_POWER_LOW | 电源电压低 |
| 29 | EVENT_TEMPERATURE_HIGH | 温度过高 |
| 30 | EVENT_WIFI_SIGNAL_WEAK | WiFi信号弱 |
| 31 | EVENT_WIFI_SIGNAL_SCAN | WiFi信号扫描 |
| 32 | EVENT_WIFI_SIGNAL_SWITCH | WiFi信号切换 |
| 33 | EVENT_HEAP_FRAGMENTATION | 内存碎片化严重 |
| 34 | EVENT_WATCHDOG_TRIGGERED | 看门狗触发 |
| 35 | EVENT_EXCEPTION_CAUGHT | 异常捕获 |
| 36 | EVENT_DHCP_TIMEOUT | DHCP超时 |
| 37 | EVENT_NETWORK_CONGESTION | 网络拥塞 |

#### 增强日志结构（EnhancedLogEntry）

新增监控字段：
- `wifiBSSID` - WiFi基站MAC地址
- `uptime` - 设备运行时间（秒）
- `temperature` - 芯片温度
- `spiffsUsed` - SPIFFS已使用空间
- `spiffsTotal` - SPIFFS总空间
- `heapFragmentation` - 内存碎片化程度
- `lastHeartbeatSeq` - 最后心跳序列号
- `lastHeartbeatTime` - 最后心跳时间
- `tcpClientCount` - TCP客户端连接数
- `webRequestCount` - Web请求计数

#### 定时监控机制

1. **内存监控**（每30秒）
   - 检查freeHeap是否低于阈值
   - 检查内存碎片化程度
   - 自动记录EVENT_MEMORY_LOW和EVENT_HEAP_FRAGMENTATION

2. **SPIFFS监控**（每60秒）
   - 检查剩余空间是否不足
   - 自动记录EVENT_SPIFFS_FULL

3. **WiFi信号监控**（实时）
   - 检测信号强度是否低于-75dBm
   - 自动扫描更强信号
   - 自动切换到信号更好的AP
   - 记录EVENT_WIFI_SIGNAL_WEAK、EVENT_WIFI_SIGNAL_SCAN、EVENT_WIFI_SIGNAL_SWITCH

---

### 2. Python端日志增强

#### 新增日志记录器

| 日志文件 | 记录器名称 | 用途 |
|---------|-----------|------|
| `network_error.log` | OTLive.NetworkError | 网络异常（丢包、延迟过高） |
| `heartbeat_detail.log` | OTLive.HeartbeatDetail | 心跳详细信息（序列号、延迟、RSSI） |
| `room_state_change.log` | OTLive.RoomStateChange | 房间状态变更（上线/离线/RSSI变化） |
| `esp32_logs_recv.log` | OTLive.ESP32LogsRecv | ESP32日志接收记录 |

#### 心跳接收增强

1. **序列号追踪**
   - 记录每次心跳的序列号
   - 检测丢包（序列号不连续）
   - 记录丢包数量和原因

2. **延迟分析**
   - 计算心跳延迟时间
   - 延迟超过1秒自动警告
   - 记录到network_error.log

3. **RSSI监控**
   - 记录每次心跳的RSSI值
   - 检测RSSI持续弱信号（连续10次 < -70dBm）
   - 自动诊断WiFi信号问题

#### ESP32日志接收和存储

1. **接收机制**
   - 通过UDP接收ESP32上传的日志
   - JSON格式保存到`log/esp32/`目录
   - 文件名格式：`room_<id>_<timestamp>.json`

2. **存储结构**
```json
{
  "room_id": 1,
  "recv_time": 1717344000.123,
  "recv_time_str": "2025-05-30 12:00:00.123",
  "logs_count": 50,
  "logs": [
    {
      "timestamp": 1717344000000,
      "event_type": 4,
      "error_code": 1,
      "error_msg": "WiFi连接失败",
      "rssi": -85,
      "free_heap": 45000,
      "max_alloc_heap": 40000,
      "loop_duration": 120,
      "audio_active": false,
      "uptime": 3600,
      "wifiBSSID": "AA:BB:CC:DD:EE:FF"
    }
  ]
}
```

3. **自动清理**
   - 每个房间最多保留50个日志文件
   - 自动删除最旧的日志文件

---

### 3. 离线原因自动诊断

#### 诊断算法流程

1. 检测心跳超时（默认15秒）
2. 获取离线前的ESP32日志文件
3. 分析最后事件类型和系统状态
4. 根据事件类型匹配诊断规则
5. 生成诊断报告并写入日志

#### 支持的诊断类型

| 诊断类型 | 触发条件 | 详细说明 |
|---------|---------|---------|
| **WIFI_DISCONNECT** | EVENT_WIFI_DISCONNECTED (4) | WiFi断开连接，包含断开原因和RSSI值 |
| **WIFI_RECONNECT_FAILED** | EVENT_WIFI_RECONNECT_FAILED (9) | WiFi重连失败，包含尝试次数 |
| **WIFI_SIGNAL_WEAK** | RSSI持续 < -70dBm 或 EVENT_WIFI_SIGNAL_WEAK (30) | WiFi信号持续弱，包含平均RSSI值 |
| **MEMORY_LOW** | freeHeap < 20000 或 EVENT_MEMORY_LOW (14) | 内存不足，包含剩余内存大小 |
| **SYSTEM_RESET** | EVENT_RESET_DETECTED (13) | 系统重启，包含重启原因和运行时间 |
| **LOOP_BLOCKED** | loopDuration > 500ms 或 EVENT_LOOP_BLOCKED (10) | Loop阻塞，包含阻塞时长 |
| **SPIFFS_FULL** | EVENT_SPIFFS_FULL (18) | SPIFFS空间不足，包含剩余空间大小 |
| **HEARTBEAT_FAILED** | EVENT_HEARTBEAT_FAILED (3) | 心跳发送失败，包含失败原因 |
| **HEARTBEAT_DELAY** | latency > 1000ms | 心跳延迟过高，包含延迟时间 |
| **HEARTBEAT_TIMEOUT** | 无明确异常事件 | 心跳超时，无法确定具体原因 |

#### 诊断报告示例

```
[OFFLINE] 房间ID=1 | 名称=测试房间 | IP=192.168.1.101
  原因: heartbeat_timeout
  超时详情: 最后心跳距今18.5秒, 超时阈值15秒
  离线前状态: RSSI=-85dBm, audio_active=false, 在线持续=2时30分15秒
  离线前RSSI趋势: [-80, -82, -84, -85]
  离线前设备状态: trigger=OFF, light=ON
  疑似原因: WiFi信号弱导致连接不稳定
  诊断结果: [WIFI_DISCONNECT] WiFi断开: WiFi连接失败, RSSI=-85dBm
  相关日志:
    {event_type: 4, error_msg: "WiFi连接失败", rssi: -85, free_heap: 45000}
```

---

### 4. Web端日志查看

#### 访问方式

- **日志概览**: `http://192.168.1.101/log/`
- **房间详情**: `http://192.168.1.101/log/<room_id>`

#### 功能模块

1. **概览页面** (`log_index.html`)
   - 日志统计（总数、大小、ESP32日志数、离线事件数）
   - 最近日志文件列表
   - 日志类型筛选
   - 内容搜索

2. **房间详情页面** (`log_room.html`)
   - ESP32日志文件列表
   - 离线诊断记录
   - 事件时间线
   - 日志详情查看（JSON格式化显示）

#### API接口

| 接口路径 | 功能 |
|---------|------|
| `/api/log/types` | 获取日志类型列表 |
| `/api/log/list` | 获取所有日志文件列表 |
| `/api/log/content/<filename>` | 获取日志内容（支持行数限制） |
| `/api/log/room/<room_id>` | 获取房间ESP32日志列表 |
| `/api/log/diagnosis/<room_id>` | 获取房间离线诊断记录 |
| `/api/log/diagnose/<room_id>/<offline_time>` | 实时诊断离线原因 |

---

## 📁 文件位置

### ESP32端

- **固件文件**: `d:\item\OTLive\esp32-s3\src\main.cpp`
- **日志上传**: 通过UDP发送到Python端

### Python端

- **核心逻辑**: `d:\item\OTLive\iot\core\device.py`
- **日志存储目录**: `d:\item\OTLive\iot\log\`
- **ESP32日志**: `d:\item\OTLive\iot\log\esp32\room_<id>_<timestamp>.json`
- **网络异常日志**: `d:\item\OTLive\iot\log\network_error.log`
- **心跳详细日志**: `d:\item\OTLive\iot\log\heartbeat_detail.log`
- **房间状态变更**: `d:\item\OTLive\iot\log\room_state_change.log`
- **ESP32日志接收**: `d:\item\OTLive\iot\log\esp32_logs_recv.log`
- **离线事件日志**: `d:\item\OTLive\iot\log\offline.log`

### Web端

- **路由文件**: `d:\item\OTLive\iot\web\app.py`
- **概览页面**: `d:\item\OTLive\iot\web\templates\log_index.html`
- **房间详情**: `d:\item\OTLive\iot\web\templates\log_room.html`

---

## 🔧 使用方法

### 1. 查看实时日志

1. 打开浏览器访问：`http://<服务器IP>/log/`
2. 在概览页面查看：
   - 日志统计信息
   - 最近更新的日志文件
   - 点击日志卡片查看详细内容

### 2. 查看房间日志

1. 在概览页面点击"房间日志"标签
2. 选择要查看的房间
3. 查看该房间的ESP32日志文件列表
4. 点击日志文件查看详细内容（JSON格式化）

### 3. 查看离线诊断

1. 在概览页面点击"离线诊断"标签
2. 选择要查看的房间
3. 查看该房间的离线诊断记录
4. 每条记录包含：
   - 离线时间
   - 离线原因
   - 诊断结果（原因类型、详细描述）
   - 相关日志片段

### 4. 手动诊断离线原因

如果需要手动诊断特定时间的离线事件：

```bash
# API调用示例
curl http://192.168.1.101/api/log/diagnose/1/1717344000
```

返回结果：
```json
{
  "success": true,
  "diagnosis_type": "WIFI_DISCONNECT",
  "diagnosis_desc": "WiFi断开: WiFi连接失败, RSSI=-85dBm",
  "diagnosis_logs": [
    {"event_type": 4, "error_msg": "WiFi连接失败", "rssi": -85}
  ]
}
```

---

## 📊 常见离线原因分析

### 1. WiFi相关问题

#### WiFi断开（WIFI_DISCONNECT）
**症状**: 设备突然离线，最后日志显示EVENT_WIFI_DISCONNECTED  
**原因**:
- WiFi信号强度不足（RSSI < -75dBm）
- WiFi路由器重启或故障
- WiFi信道切换
- WiFi密码错误

**解决方案**:
- 检查WiFi信号强度，确保RSSI > -70dBm
- 检查WiFi路由器状态
- 考虑使用WiFi信号增强器
- 启用WiFi自动切换功能（已实现）

#### WiFi重连失败（WIFI_RECONNECT_FAILED）
**症状**: 设备尝试重连WiFi多次失败后离线  
**原因**:
- WiFi密码错误
- WiFi路由器不可达
- WiFi频段不支持
- DHCP服务器故障

**解决方案**:
- 检查WiFi配置是否正确
- 检查WiFi路由器是否正常工作
- 检查DHCP服务器状态

#### WiFi信号弱（WIFI_SIGNAL_WEAK）
**症状**: RSSI持续低于-70dBm，设备频繁掉线  
**原因**:
- 设备距离WiFi路由器过远
- WiFi信号被障碍物阻挡
- WiFi信道拥塞

**解决方案**:
- 将设备移近WiFi路由器
- 使用WiFi信号增强器
- 切换到信号更好的WiFi AP（已实现自动切换）

---

### 2. 内存相关问题

#### 内存不足（MEMORY_LOW）
**症状**: freeHeap低于20000字节，设备运行不稳定  
**原因**:
- 内存泄漏
- 大量音频缓冲区占用
- 任务栈溢出
- 内存碎片化严重

**解决方案**:
- 检查代码是否存在内存泄漏
- 减少音频缓冲区大小
- 增加任务栈大小
- 定期重启设备释放内存

#### 内存碎片化（HEAP_FRAGMENTATION）
**症状**: 内存碎片化程度超过50%，maxAllocHeap远小于freeHeap  
**原因**:
- 频繁的内存分配和释放
- 不合理的内存分配策略

**解决方案**:
- 使用内存池管理
- 避免频繁分配大块内存
- 定期重启设备整理内存

---

### 3. 系统运行问题

#### Loop阻塞（LOOP_BLOCKED）
**症状**: loop()函数执行时间超过500ms  
**原因**:
- 阻塞式操作（delay、等待网络响应）
- 大量数据处理
- 任务优先级冲突

**解决方案**:
- 使用非阻塞式操作
- 将耗时操作放到独立任务
- 优化数据处理流程

#### 系统重启（SYSTEM_RESET）
**症状**: 设备突然重启，uptime重置为0  
**原因**:
- 电源不稳定
- 看门狗触发
- 异常/错误导致崩溃
- 温度过高

**解决方案**:
- 检查电源稳定性
- 检查看门狗配置
- 检查异常日志定位崩溃原因
- 检查设备温度

---

### 4. 存储相关问题

#### SPIFFS空间不足（SPIFFS_FULL）
**症状**: SPIFFS剩余空间不足，无法写入新日志  
**原因**:
- 日志文件过多
- 音频文件占用大量空间
- 未清理旧文件

**解决方案**:
- 定期清理旧日志文件
- 减少日志记录频率
- 扩大SPIFFS分区大小

---

### 5. 网络通信问题

#### 心跳延迟过高（HEARTBEAT_DELAY）
**症状**: 心跳延迟超过1秒  
**原因**:
- 网络拥塞
- 服务器处理能力不足
- WiFi信号不稳定

**解决方案**:
- 检查网络带宽使用情况
- 检查服务器负载
- 优化WiFi信号

#### 心跳丢包
**症状**: 心跳序列号不连续，出现丢包  
**原因**:
- 网络不稳定
- UDP包丢失
- 网络拥塞

**解决方案**:
- 检查网络稳定性
- 考虑使用TCP代替UDP
- 增加心跳重发机制

---

## 🧪 测试验证

### 测试步骤

1. **编译ESP32固件**
   ```bash
   # 使用根目录下的BAT批处理文件
   # 根据项目实际情况选择编译脚本
   ```

2. **刷新固件到ESP32-S3**
   ```bash
   # 使用根目录下的BAT批处理文件
   # 根据项目实际情况选择刷固件脚本
   ```

3. **验证日志上传**
   - 观察ESP32串口输出，确认日志记录正常
   - 检查Python端是否接收到ESP32日志
   - 检查`log/esp32/`目录是否有JSON文件生成

4. **验证Web界面**
   - 访问`http://<服务器IP>/log/`
   - 检查日志列表是否显示
   - 点击日志文件查看内容
   - 检查JSON格式化显示是否正常

5. **验证离线诊断**
   - 手动关闭ESP32设备模拟离线
   - 等待15秒让系统检测离线
   - 检查`offline.log`是否生成诊断报告
   - 在Web界面查看离线诊断记录

### 验证要点

- ✅ ESP32是否正常记录事件日志
- ✅ ESP32是否正常上传日志到Python端
- ✅ Python端是否正确保存ESP32日志到JSON文件
- ✅ Web界面是否能正常查看日志
- ✅ 离线诊断是否准确定位原因
- ✅ 日志文件是否自动清理（超过50个文件）
- ✅ 内存监控是否正常工作
- ✅ SPIFFS监控是否正常工作
- ✅ WiFi信号监控是否正常工作

---

## 📝 维护建议

### 日常维护

1. **定期检查日志文件大小**
   - 日志文件会自动轮转（最大10MB）
   - 定期检查`log/`目录大小
   - 必要时手动清理旧日志

2. **监控离线频率**
   - 定期查看`offline.log`
   - 分析离线原因分布
   - 针对高频原因进行优化

3. **检查ESP32日志上传频率**
   - ESP32每30秒上传一次日志
   - 如果上传频率异常，检查网络状态

### 性能优化

1. **调整日志记录频率**
   - 内存监控：30秒（可调整`memoryCheckInterval`）
   - SPIFFS监控：60秒（可调整`spiffsCheckInterval`）
   - 心跳上传：30秒（可调整`heartbeatInterval`）

2. **调整监控阈值**
   - 内存不足阈值：20000字节（`CRITICAL_HEAP_THRESHOLD`）
   - 内存偏低阈值：40000字节（`LOW_HEAP_THRESHOLD`）
   - WiFi弱信号阈值：-75dBm（`WIFI_WEAK_SIGNAL_THRESHOLD`）
   - Loop阻塞阈值：500ms（`MAX_LOOP_DURATION`）

3. **调整日志保留数量**
   - ESP32日志：每个房间最多50个文件
   - Python日志：每个日志文件最大10MB，保留5个备份

---

## 🔍 故障排查流程

### 设备离线排查步骤

1. **查看离线日志**
   ```
   打开: d:\item\OTLive\iot\log\offline.log
   查找: 房间ID=<离线房间ID>
   ```

2. **分析诊断结果**
   - 查看"诊断结果"字段
   - 确定离线原因类型
   - 查看相关日志片段

3. **查看ESP32日志**
   ```
   打开: d:\item\OTLive\iot\log\esp32\
   查找: room_<id>_<离线前时间>.json
   ```

4. **分析最后事件**
   - 查看最后几个事件类型
   - 检查系统状态（RSSI、内存、Loop耗时）
   - 确定根本原因

5. **实施解决方案**
   - 根据诊断类型选择对应解决方案
   - 实施修复措施
   - 观察设备是否恢复正常

### Web界面排查步骤

1. **访问日志概览**
   ```
   URL: http://<服务器IP>/log/
   ```

2. **选择离线房间**
   - 点击"离线诊断"标签
   - 选择离线的房间
   - 查看诊断记录

3. **查看ESP32日志**
   - 点击"房间日志"标签
   - 选择房间
   - 查看离线前的日志文件
   - 分析事件时间线

---

## 📚 相关文档

- **ESP32固件**: `d:\item\OTLive\esp32-s3\src\main.cpp`
- **Python核心**: `d:\item\OTLive\iot\core\device.py`
- **Web应用**: `d:\item\OTLive\iot\web\app.py`
- **日志概览页面**: `d:\item\OTLive\iot\web\templates\log_index.html`
- **房间详情页面**: `d:\item\OTLive\iot\web\templates\log_room.html`

---

## 📞 技术支持

如遇到问题，请按以下顺序排查：

1. 查看本文档的"常见离线原因分析"章节
2. 查看日志文件确定具体原因
3. 实施对应的解决方案
4. 如问题持续，检查硬件和网络环境
5. 必要时联系技术支持团队

---

**文档版本**: 1.0  
**最后更新**: 2025-05-30  
**维护者**: ESP32-S3开发团队