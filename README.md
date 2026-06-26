<div align="center">

# 🎙️ OTLive 规模化直播矩阵系统

### Windows + ESP32-S3 驱动的多直播间设备控制与语音对讲平台

*一台 PC 统管几十个直播间：礼物触发、设备联动、AI 语音答谢、实时对讲，一气呵成。*

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20ESP32--S3-blue.svg)](https://github.com/feichenxi/OTLive)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Flask-3.0-orange.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

</div>

---

## 📖 项目简介 / Overview

**OTLive** 是一套面向直播运营团队的**规模化直播矩阵控制系统**。它把一台 Windows PC 作为控制中心，通过 WiFi 统一管理多个（默认 12 个）基于 ESP32-S3 的直播间终端，实现：

- 🎁 **礼物联动触发** — 主播收到礼物后，自动控制对应 GPIO 装置动作（喷彩带、亮灯、震动等）
- 🔊 **实时语音对讲** — PC 端麦克风 ↔ ESP32 端音箱，UDP 低延迟音频传输
- 🤖 **AI 自动答谢** — 礼物消息驱动 LLM 生成感谢语 + TTS 合成语音播放
- 🖥️ **Web 控制面板** — Flask + WebSocket 实时房间状态、设备状态、音频控制
- 🔁 **OTA 远程升级** — 批量给在线 ESP32 设备推送新固件

> 💡 适用于娱乐直播、互动带货、线下门店互动装置等需要"礼物 → 物理动作"联动的场景。

---

## ✨ 功能特性 / Features

### 🎛️ 设备控制
- **触发装置**：礼物触发后定时开关（喷彩带、气球爆破等）
- **常动装置**：持续运行设备开关（风扇、灯光等）
- **可编程设备**：每房间支持 10 路可编程 GPIO，可绑定不同礼物规则
- **WebSocket 实时推送**：房间在线状态、设备状态毫秒级刷新

### 🎵 音频功能
- **房间对讲**：UDP 实时音频传输，可调音量、噪声门
- **WAV 播放**：支持 HTTP URL 下载并流式播放
- **AI 语音合成**：礼物答谢语自动 TTS（支持阿里云 CosyVoice / SiliconFlow）

### 🎁 礼物触发引擎
- 从 MySQL 数据库实时监听礼物消息
- 每房间独立配置礼物 → 设备触发规则
- 智能触发队列管理，避免冲突
- 大/小礼物分级处理，合并窗口去重

### 🤖 AI 答谢
- 礼物信息 → LLM 生成个性化感谢文案
- 文案 → TTS 合成语音 → 推送到对应房间播放
- 房间专属提示词，冷却时间控制

### 🔐 授权管理
- 基于机器码的授权验证
- 支持试用 / 月付 / 年付 / 永久
- 房间数限制 + 周期性后台验证

### 🔄 OTA 升级
- 批量更新所有在线 ESP32-S3 设备
- 自动生成版本号（vYYYYMMDD_序号）
- 升级失败自动重试

---

## 🗂️ 项目结构 / Project Structure

```
OTLive/
├── iot/                          # ⭐ Windows 控制中心（Python + Flask）
│   ├── main.py                   #   主程序入口
│   ├── common/                   #   通用模块（数据库/配置/授权/日志）
│   ├── core/                     #   核心（audio/device/network/ota）
│   ├── trigger/                  #   礼物触发服务与队列管理
│   ├── web/                      #   Flask Web 应用 + WebSocket
│   │   ├── app.py
│   │   ├── static/               #   CSS / JS
│   │   └── templates/            #   控制面板 / 日志页面
│   └── utils/                    #   工具函数
│
├── esp32-s3/                     # ⭐ ESP32-S3 终端固件（PlatformIO）
│   ├── src/main.cpp              #   固件主程序（WiFi/TCP/UDP/I2S/OTA）
│   ├── platformio.ini            #   PlatformIO 配置
│   └── partitions.csv            #   分区表
│
├── ai/                           # ⭐ AI 模块
│   ├── ai_manager.py             #   AI 管理器（文本+语音）
│   ├── aitxt/                    #   文本生成
│   └── aiwav/                    #   语音合成（含 voice_cloning）
│
├── web/                          # 🌐 PHP 后台管理（可选，授权/订单管理）
│   ├── basic/                    #   登录 / 密码 / 设置
│   ├── data/                     #   数据库配置 + 类库
│   ├── ex/                       #   业务页面（用户/订单/跑腿员/提现）
│   └── public/                   #   layui 前端框架资源
│
├── docs/                         # 📚 开发文档
│   ├── 01_接入指南.html
│   ├── 02_项目功能与说明.md
│   ├── 03_数据库结构.md
│   ├── 04_硬件接线指南.md
│   ├── 05_语音对讲开发规范.md
│   ├── OTA_UPDATE_TOOL_README.md
│   └── sql/                      #   SQL 脚本
│
├── sound/                        # 🔊 音效资源（trigger/always/wait）
├── wav/                          # 🎵 AI 生成的礼物答谢语音
├── static/                       # 🖼️ 静态资源（logo/参考语音/SQL）
├── 运行图/                       # 📷 运行截图
│
├── config.ini.example            # ⚙️ 配置模板（复制为 config.ini 后填写）
├── requirements.txt              # 📦 Python 依赖
├── .gitignore
├── .gitattributes
├── LICENSE
└── README.md                     # 本文件
```

---

## 🚀 快速开始 / Quick Start

### 1. 环境要求

| 组件 | 要求 |
|------|------|
| **控制中心** | Windows 10 / 11，Python 3.8+ |
| **终端设备** | ESP32-S3 N16R8 开发板 |
| **音频模块** | PCM5102MK2.0 I2S 功放 + USB 麦克风 + 有源音箱 |
| **网络** | 同一局域网 WiFi |
| **数据库** | MySQL 5.7+（远程授权/消息）、SQLite（本地配置） |

### 2. 控制中心安装

```bash
# 克隆仓库
git clone https://github.com/feichenxi/OTLive.git
cd OTLive

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制配置模板并填写真实值（API Key、数据库密码等）
copy config.ini.example config.ini
# 用编辑器打开 config.ini 填入真实配置

# 启动控制中心
cd iot
python main.py
```

启动后浏览器访问：`http://localhost:5000`（或自动弹出 pywebview 窗口）。

### 3. ESP32-S3 固件烧录

```bash
cd esp32-s3

# 修改 src/main.cpp 顶部的 WiFi 账号密码
# const char* ssid = "YOUR_WIFI_SSID";
# const char* password = "YOUR_WIFI_PASSWORD";

# 使用 PlatformIO 烧录
pio run --target upload
```

详细接线见 [docs/04_硬件接线指南.md](./docs/04_硬件接线指南.md)。

### 4. 配置说明

| 文件 | 作用 | 是否提交 |
|------|------|:--------:|
| `config.ini.example` | 配置模板（占位符） | ✅ 已提交 |
| `config.ini` | 真实配置（含 API Key） | ❌ 已忽略 |
| `iot/database/config.db` | 本地 SQLite 配置库 | ❌ 已忽略 |
| `iot/database/room_*.db` | 房间运行数据 | ❌ 已忽略 |

> ⚠️ **源码中的数据库连接信息已替换为占位符**（`YOUR_MYSQL_HOST` / `YOUR_MYSQL_USER` / `YOUR_MYSQL_PASSWORD`），部署时请在对应文件中填入真实值：
> - `iot/main.py` → `_get_mysql_config()`
> - `iot/core/audio.py` → `db_config`
> - `iot/web/app.py` → `_get_license_id()` / 数据库连接段
> - `web/data/config.php` / `web/data/class.php` → PHP 数据库配置

---

## 📷 运行截图 / Screenshots

### 控制中心主界面
![控制中心主界面](./运行图/img%20%281%29.png)

### 房间设备状态
![房间设备状态](./运行图/img%20%282%29.png)

### 礼物触发配置
![礼物触发配置](./运行图/img%20%283%29.png)

### 语音对讲与音量控制
![语音对讲与音量控制](./运行图/img%20%284%29.png)

### AI 答谢语音生成
![AI答谢语音生成](./运行图/img%20%285%29.png)

### 日志监控
![日志监控](./运行图/img%20%286%29.png)

### ESP32-S3 终端运行
![ESP32-S3终端运行](./运行图/img%20%287%29.png)

---

## ⚙️ 核心配置 / Configuration

`config.ini` 主要配置项：

```ini
[system]
name = 规模化直播矩阵系统
version = 5.02
debug = false

[audio]
sample_rate = 48000       # 采样率，需与 ESP32 一致
channels = 1
chunk_size = 1024

[performance]
heartbeat_interval = 5    # ESP32 心跳间隔（秒）
heartbeat_port = 9999     # PC 监听的心跳端口
heartbeat_timeout = 15    # 心跳超时判定离线（秒）

[ai]
big_gift_threshold = 100  # 大礼物阈值
merge_window = 30         # 礼物合并窗口（秒）

[aitxt]
api_key = YOUR_AITXT_API_KEY      # 文本生成 API Key
model = deepseek-ai/DeepSeek-V3.2

[aiwav]
api_key = YOUR_AIWAV_API_KEY      # 语音合成 API Key
model = cosyvoice-v3.5-flash
```

---

## 🛠️ 技术架构 / Architecture

```
┌──────────────────────────────────────────────────┐
│              Windows 控制中心 (Python)            │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Flask Web│  │ 礼物触发 │  │   AI 管理器   │  │
│  │ + Socket │  │  服务    │  │ (LLM + TTS)   │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │WebSocket     │ MySQL           │          │
│       │             │ 监听             │          │
│  ┌────▼─────────────▼─────────────────▼──────┐  │
│  │        网络/音频/设备/OTA 核心模块         │  │
│  └────┬─────────────┬────────────────────────┘  │
│       │ TCP 控制     │ UDP 音频 + 心跳           │
└───────┼──────────────┼──────────────────────────┘
        │              │
   ┌────▼────┐    ┌────▼────┐         ┌─────────┐
   │ ESP32-1 │    │ ESP32-2 │  ...    │ ESP32-12│
   │ 触发装置│    │ 触发装置│         │ 触发装置│
   │ PCM5102 │    │ PCM5102 │         │ PCM5102 │
   └─────────┘    └─────────┘         └─────────┘
```

**通信协议：**
- **TCP 短连接**：PC → ESP32 设备控制命令
- **UDP**：PC → ESP32 音频流；ESP32 → PC 心跳广播（5 秒间隔）
- **HTTP API**：ESP32 内置 Web 服务器（端口 80）
- **WebSocket**：浏览器 ↔ Flask 实时状态推送

---

## 📚 文档 / Documentation

| 文档 | 说明 |
|------|------|
| [接入指南](./docs/01_接入指南.html) | 部署与接入流程 |
| [项目功能与说明](./docs/02_项目功能与说明.md) | 功能清单与架构 |
| [数据库结构](./docs/03_数据库结构.md) | SQLite + MySQL 表结构 |
| [硬件接线指南](./docs/04_硬件接线指南.md) | ESP32-S3 引脚分配与接线 |
| [语音对讲开发规范](./docs/05_语音对讲开发规范.md) | 音频传输协议与缓存机制 |
| [OTA 更新工具](./docs/OTA_UPDATE_TOOL_README.md) | 一键 OTA 升级说明 |

---

## 🤝 贡献 / Contributing

欢迎提 Issue / PR。请遵守：

1. Fork → 新建分支 → 提 PR
2. Python 代码保持 4 空格缩进、UTF-8 编码
3. 不要把 `venv/` `config.ini` `*.db` `*.log` 提交进来（`.gitignore` 已排除）
4. 涉及密钥/密码请使用占位符，真实值留在本地

---

## 📄 许可证 / License

本项目基于 [MIT License](./LICENSE) 开源，版权所有 © 2026 feichenxi。

依赖库遵循各自许可证：[Flask](https://flask.palletsprojects.com/)、[Flask-SocketIO](https://flask-socketio.readthedocs.io/)、[PyAudio](https://people.csail.mit.edu/hubert/pyaudio/)、[dashscope](https://help.aliyun.com/zh/dashscope/)。

---

## 📬 联系方式

如有问题、建议或合作意向，欢迎通过以下方式联系：

- **GitHub Issues**：[提交 Issue](https://github.com/feichenxi/OTLive/issues)
- **邮箱**：[44998076@qq.com](mailto:44998076@qq.com)

---

## ⚠️ 免责声明

本项目仅供学习和研究目的。部署和使用前请确保遵守当地法律法规及直播平台规则。作者不对任何不当使用行为承担责任。

---

<div align="center">

**⭐ 如果 OTLive 帮你搞定了直播矩阵自动化，给个 Star 吧 ⭐**

*One PC, Many Rooms, Full Control — 感谢使用！*

</div>
