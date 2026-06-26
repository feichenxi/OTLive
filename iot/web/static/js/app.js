import SocketManager from './modules/SocketManager.js';
import RoomManager from './modules/RoomManager.js';
import DeviceController from './modules/DeviceController.js';
import AudioManager from './modules/AudioManager.js';
import MessageManager from './modules/MessageManager.js';
import UIManager from './modules/UIManager.js';
import SystemManager from './modules/SystemManager.js';
import TriggerManager from './modules/TriggerManager.js';

class IoTControlApp {
    constructor() {
        this.socket = null;
        this.rooms = [];
        this.currentAudioRoom = null;
        this.broadcastMode = false;
        this.heartbeatInterval = 5;
        this.heartbeatCountdown = null;
        this.selectedRoom = null;
        this.loadedMessageIds = new Set();
        this.loadedGiftIds = new Set();
        this.patrolDialogEnabled = false;
        this.messageRefreshInterval = null;
        this.startTime = Date.now();
        this.collectorStatusCheckers = new Map();
        this.licenseId = window.LICENSE_ID || 0;
        
        const savedPatrolEnabled = localStorage.getItem('patrolDialogEnabled');
        if (savedPatrolEnabled !== null) {
            this.patrolDialogEnabled = savedPatrolEnabled === 'true';
        }
        
        // 初始化模块
        this.socketManager = new SocketManager(this);
        this.roomManager = new RoomManager(this);
        this.deviceController = new DeviceController(this);
        this.audioManager = new AudioManager(this);
        this.messageManager = new MessageManager(this);
        this.uiManager = new UIManager(this);
        this.systemManager = new SystemManager(this);
        this.triggerManager = new TriggerManager(this);
        
        this.init();
    }

    init() {
        this.socketManager.connectSocket();
        this.bindEvents();
        this.loadRooms();
        this.roomManager.showHomeView();
        this.startRuntimeCounter();
        this.triggerManager.startGlobalRefresh();
        this.systemManager.loadSystemStatus();
    }

    bindEvents() {
        // Room selection buttons event listeners
        document.addEventListener('click', async (e) => {
            if (e.target.classList.contains('room-btn')) {
                const roomId = parseInt(e.target.dataset.room);
                await this.roomManager.selectRoom(roomId);
            }
        });

        // Home button
        document.getElementById('home-btn')?.addEventListener('click', () => {
            this.roomManager.showHomeView();
        });

        // Settings button
        document.getElementById('settings-btn')?.addEventListener('click', () => {
            this.uiManager.openSystemSettingsDialog();
        });

        // Barrage button
        document.getElementById('barrage-btn')?.addEventListener('click', () => {
            this.launchBarrage();
        });

        // Detect modal close button
        document.getElementById('detect-modal-close')?.addEventListener('click', () => {
            document.getElementById('detect-modal').style.display = 'none';
        });

        // Message detail modal close button
        document.getElementById('message-detail-modal-close')?.addEventListener('click', () => {
            document.getElementById('message-detail-modal').style.display = 'none';
        });

        // Message detail modal ok button
        document.getElementById('message-detail-modal-ok')?.addEventListener('click', () => {
            document.getElementById('message-detail-modal').style.display = 'none';
        });

        document.getElementById('broadcast-btn')?.addEventListener('click', () => {
            this.audioManager.toggleBroadcast();
        });

        document.getElementById('connect-audio-btn')?.addEventListener('click', () => {
            const roomSelect = document.getElementById('room-select');
            const roomId = parseInt(roomSelect.value);
            
            if (roomId) {
                this.audioManager.switchAudio(roomId);
            } else {
                this.uiManager.showToast('请选择房间', 'warning');
            }
        });

        // Audio modal close button
        document.getElementById('audio-modal-close')?.addEventListener('click', () => {
            document.getElementById('audio-modal').style.display = 'none';
        });

        // Audio file upload area
        const uploadArea = document.getElementById('upload-area');
        const audioFileInput = document.getElementById('audio-file-input');

        uploadArea?.addEventListener('click', () => {
            audioFileInput.click();
        });

        uploadArea?.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea?.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea?.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.uploadAudioFile(files[0]);
            }
        });

        audioFileInput?.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadAudioFile(e.target.files[0]);
            }
        });

        // Refresh button
        document.getElementById('refresh-btn')?.addEventListener('click', () => {
            location.reload();
        });

        // Fullscreen button
        document.getElementById('fullscreen-btn')?.addEventListener('click', () => {
            this.uiManager.toggleFullscreen();
        });

        // Shutdown button
        document.getElementById('shutdown-btn')?.addEventListener('click', () => {
            if (confirm('确定要关机吗？这将关闭整个系统。')) {
                this.systemManager.shutdownSystem();
            }
        });

        // Gift config button
        document.getElementById('gift-btn')?.addEventListener('click', () => {
            this.messageManager.openGiftConfigDialog();
        });

        // Gift config modal close button
        document.getElementById('gift-config-modal-close')?.addEventListener('click', () => {
            document.getElementById('gift-config-modal').style.display = 'none';
            this.messageManager.cancelGiftEdit();
        });

        // Add gift button
        document.getElementById('add-gift-btn')?.addEventListener('click', () => {
            this.addGift();
        });

        // Sync gifts button
        document.getElementById('sync-gifts-btn')?.addEventListener('click', () => {
            this.syncGiftsFromMySQL();
        });
    }

    // 代理方法：将原方法代理到对应的模块
    loadRooms() {
        this.roomManager.loadRooms();
    }

    async launchBarrage() {
        try {
            const response = await fetch('/api/launch_barrage', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                this.uiManager.showToast('弹幕程序已启动', 'success');
            } else {
                this.uiManager.showToast(data.error || '启动弹幕程序失败', 'error');
            }
        } catch (e) {
            this.uiManager.showToast('启动弹幕程序失败: ' + e.message, 'error');
        }
    }

    toggleMicrophone(roomId, enabled) {
        this.audioManager.toggleMicrophone(roomId, enabled);
    }

    toggleRoomMusic(roomId, enabled) {
        this.audioManager.toggleRoomMusic(roomId, enabled);
    }

    async toggleRoomDialog(roomId, enabled) {
        await this.audioManager.toggleRoomDialog(roomId, enabled);
    }

    openVolumeDialog(roomId) {
        this.audioManager.openVolumeDialog(roomId);
    }

    openIntercomVolumeDialog(roomId) {
        this.audioManager.openIntercomVolumeDialog(roomId);
    }

    openBackgroundMusicDialog(roomId) {
        this.audioManager.openBackgroundMusicDialog(roomId);
    }

    playSpeakerBeep(roomId) {
        this.deviceController.playSpeakerBeep(roomId);
    }

    // 其他代理方法
    stopMessageRefresh() {
        this.messageManager.stopMessageRefresh && this.messageManager.stopMessageRefresh();
    }

    // 礼物配置代理方法
    openGiftDialog() {
        this.messageManager.openGiftConfigDialog();
    }

    loadGifts() {
        this.messageManager.loadGifts();
    }

    addGift() {
        this.messageManager.addGift();
    }

    async syncGiftsFromMySQL() {
        try {
            const btn = document.getElementById('sync-gifts-btn');
            const originalText = btn.textContent;
            btn.textContent = '拉取中...';
            btn.disabled = true;

            const response = await fetch('/api/gifts/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            if (data.success) {
                this.uiManager.showToast(`成功同步礼物！新增: ${data.synced}, 更新: ${data.updated}, 总计: ${data.total}`, 'success');
                // 刷新礼物列表
                this.loadGifts();
            } else {
                this.uiManager.showToast('同步失败: ' + (data.error || '未知错误'), 'error');
            }
        } catch (error) {
            this.uiManager.showToast('同步失败: ' + error.message, 'error');
        } finally {
            const btn = document.getElementById('sync-gifts-btn');
            if (btn) {
                btn.textContent = '一键拉取';
                btn.disabled = false;
            }
        }
    }

    editGift(giftId) {
        this.messageManager.editGift(giftId);
    }

    saveGiftEdit() {
        this.messageManager.saveGiftEdit();
    }

    saveGift(giftId) {
        this.messageManager.saveGift(giftId);
    }

    deleteGift(giftId) {
        this.messageManager.deleteGift(giftId);
    }

    showMessageDetail(nickname, content, time) {
        this.uiManager.showMessageDetail(nickname, content, time);
    }

    controlDevice(roomId, deviceName, action) {
        this.deviceController.controlDevice(roomId, deviceName, action);
    }

    openTriggerOnDurationDialog(roomId) {
        this.deviceController.openTriggerOnDurationDialog(roomId);
    }

    openTriggerOffDurationDialog(roomId) {
        this.deviceController.openTriggerOffDurationDialog(roomId);
    }

    openTriggerProgramDialog(roomId) {
        this.deviceController.openTriggerProgramDialog(roomId);
    }

    triggerDevice(roomId, deviceName) {
        this.deviceController.triggerDevice(roomId, deviceName);
    }

    triggerDeviceWithDuration(roomId, deviceName, duration) {
        this.deviceController.triggerDeviceWithDuration(roomId, deviceName, duration);
    }

    clearTriggerCount(roomId, deviceName = 'trigger') {
        this.deviceController.clearTriggerCount(roomId, deviceName);
    }

    // 切换房间互动监控
    async toggleInteractionMonitor(roomId, enabled) {
        const room = this.rooms.find(r => r.id === roomId);
        if (!room) {
            this.uiManager.showToast('房间不存在', 'error');
            return;
        }

        // 检查直播地址是否已填写
        if (!room.live_url || room.live_url.trim() === '') {
            this.uiManager.showToast('对不起，请先填写直播地址', 'warning');
            // 重置开关状态
            const switchEl = document.getElementById(`interaction-monitor-switch-${roomId}`);
            if (switchEl) {
                switchEl.checked = false;
            }
            return;
        }

        // 显示等待状态
        this._updateCollectorStatusBadge(roomId, 'waiting', enabled ? '启动中' : '关闭中');

        try {
            const response = await fetch(`/api/rooms/${roomId}/interaction_monitor`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    enabled: enabled,
                    live_url: room.live_url
                })
            });

            const data = await response.json();

            if (data.success) {
                this.uiManager.showToast(enabled ? '互动监控指令已发送' : '互动监控已停止', 'success');

                // 如果是关闭，记录手动关闭时间（用于自动开启的60秒冷却期）
                if (!enabled && room.ip) {
                    this.messageManager.manualCloseTime.set(room.ip, Date.now());
                    console.log(`[手动关闭] 房间 ${room.name || roomId} 互动开关已手动关闭，60秒内不会自动开启`);
                }

                // 如果是开启，开始轮询检查状态
                if (enabled) {
                    this._startCollectorStatusCheck(roomId);
                } else {
                    // 停止正在进行的轮询
                    this._stopCollectorStatusCheck(roomId);
                    // 关闭直接显示已关闭
                    this._updateCollectorStatusBadge(roomId, 'offline', '已关闭');
                }
            } else {
                // 处理 409 冲突错误
                if (response.status === 409) {
                    this.uiManager.showToast(data.error || '该房间已存在未执行的监控指令', 'warning');
                } else {
                    this.uiManager.showToast('操作失败: ' + (data.error || '未知错误'), 'error');
                }
                // 重置开关状态
                const switchEl = document.getElementById(`interaction-monitor-switch-${roomId}`);
                if (switchEl) {
                    switchEl.checked = !enabled;
                }
                // 隐藏状态徽章
                this._updateCollectorStatusBadge(roomId, 'hidden', '');
            }
        } catch (error) {
            this.uiManager.showToast('操作失败: ' + error.message, 'error');
            // 重置开关状态
            const switchEl = document.getElementById(`interaction-monitor-switch-${roomId}`);
            if (switchEl) {
                switchEl.checked = !enabled;
            }
            // 隐藏状态徽章
            this._updateCollectorStatusBadge(roomId, 'hidden', '');
        }
    }

    // 更新采集器状态显示
    _updateCollectorStatusBadge(roomId, status, text) {
        const statusDot = document.getElementById(`collector-status-dot-${roomId}`);
        const statusText = document.getElementById(`collector-status-text-${roomId}`);
        if (!statusDot || !statusText) return;

        // 更新状态文本
        statusText.textContent = text;

        // 移除所有状态类
        statusDot.classList.remove('on', 'off', 'waiting');

        // 添加对应状态类
        if (status === 'online') {
            statusDot.classList.add('on');
        } else if (status === 'offline') {
            statusDot.classList.add('off');
        } else if (status === 'waiting') {
            // 等待状态使用渐变动画效果，通过CSS实现
            statusDot.classList.add('waiting');
        }
    }

    // 开始采集器状态检查（轮询）
    _startCollectorStatusCheck(roomId) {
        // 先停止之前的轮询（如果有）
        this._stopCollectorStatusCheck(roomId);

        const maxAttempts = 33; // 最多检查33次（66秒）
        const interval = 2000; // 每2秒检查一次
        let attempts = 0;
        let isRunning = true;

        // 存储控制器以便可以停止
        this.collectorStatusCheckers.set(roomId, {
            stop: () => { isRunning = false; }
        });

        const checkStatus = async () => {
            if (!isRunning) return; // 如果已停止，不再执行

            attempts++;

            // 更新倒计时显示
            const remainingSeconds = Math.ceil((maxAttempts - attempts + 1) * interval / 1000);
            this._updateCollectorStatusBadge(roomId, 'waiting', `启动中 ${remainingSeconds}s`);

            try {
                const response = await fetch(`/api/rooms/${roomId}/collector_status`);
                const data = await response.json();

                if (data.success) {
                    // 检查是否有新消息
                    if (data.has_messages) {
                        // 有消息，开启成功
                        this._updateCollectorStatusBadge(roomId, 'online', '已开启');
                        this.collectorStatusCheckers.delete(roomId); // 清理
                        return; // 停止轮询
                    }
                }

                // 继续轮询
                if (attempts < maxAttempts && isRunning) {
                    setTimeout(checkStatus, interval);
                } else if (isRunning) {
                    // 超时，显示已失败，重置开关状态
                    this._updateCollectorStatusBadge(roomId, 'offline', '已失败');
                    this.uiManager.showToast('采集器启动超时，请检查采集端和直播地址是否正确', 'error');
                    // 重置滑块开关为关闭状态
                    const switchEl = document.getElementById(`interaction-monitor-switch-${roomId}`);
                    if (switchEl) {
                        switchEl.checked = false;
                    }
                    this.collectorStatusCheckers.delete(roomId); // 清理
                }
            } catch (error) {
                console.error('检查采集器状态失败:', error);
                if (attempts < maxAttempts && isRunning) {
                    setTimeout(checkStatus, interval);
                } else if (isRunning) {
                    this._updateCollectorStatusBadge(roomId, 'offline', '已失败');
                    // 重置滑块开关为关闭状态
                    const switchEl = document.getElementById(`interaction-monitor-switch-${roomId}`);
                    if (switchEl) {
                        switchEl.checked = false;
                    }
                    this.collectorStatusCheckers.delete(roomId); // 清理
                }
            }
        };

        // 开始第一次检查
        setTimeout(checkStatus, interval);
    }

    // 停止采集器状态检查
    _stopCollectorStatusCheck(roomId) {
        const checker = this.collectorStatusCheckers.get(roomId);
        if (checker) {
            checker.stop();
            this.collectorStatusCheckers.delete(roomId);
        }
    }

    // 切换AI语音回复状态
    async toggleVoiceStatus(roomId, enabled) {
        const room = this.rooms.find(r => r.id === roomId);
        if (!room) {
            this.uiManager.showToast('房间不存在', 'error');
            return;
        }

        if (enabled) {
            try {
                const checkResponse = await fetch(`https://live.hzjt.com/api/upload_voice.php?action=get&room=${room.ip}&license_id=${this.licenseId || 0}`);
                const checkData = await checkResponse.json();
                
                if (checkData.code !== 0 || !checkData.data) {
                    this.uiManager.showToast('请先配置AI音频实时复刻，才能启用AI答谢', 'warning');
                    const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
                    if (switchEl) switchEl.checked = false;
                    return;
                }
                
                const voiceData = checkData.data;
                const isVoiceCloned = (voiceData.voice_id && voiceData.voice_id !== 'None') || voiceData.voice_status === 2;
                if (!isVoiceCloned) {
                    this.uiManager.showToast('请先完成音频复刻，才能启用AI答谢', 'warning');
                    const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
                    if (switchEl) switchEl.checked = false;
                    return;
                }
                
                if (!voiceData.ai_prompt || !voiceData.ai_prompt.trim()) {
                    this.uiManager.showToast('请先填写主播介绍（AI提示词），才能启用AI答谢', 'warning');
                    const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
                    if (switchEl) switchEl.checked = false;
                    return;
                }
            } catch (error) {
                this.uiManager.showToast('检查复刻状态失败，请检查网络', 'error');
                const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
                if (switchEl) switchEl.checked = false;
                return;
            }
        }

        try {
            const response = await fetch('https://live.hzjt.com/api/upload_voice.php?action=update_ai_thank', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    room: room.ip,
                    license_id: this.licenseId || 0,
                    ai_thank_enabled: enabled ? 1 : 0
                })
            });

            const data = await response.json();

            if (data.code === 0) {
                room.ai_thank_enabled = enabled;
                this.uiManager.showToast(enabled ? 'AI答谢已启用' : 'AI答谢已关闭', 'success');

                fetch(`/api/rooms/${roomId}/voice_status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voice_status: enabled })
                }).catch(err => console.error('通知后端voice_status失败:', err));
            } else {
                this.uiManager.showToast('操作失败: ' + (data.msg || '未知错误'), 'error');
                const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
                if (switchEl) switchEl.checked = !enabled;
            }
        } catch (error) {
            this.uiManager.showToast('操作失败: ' + error.message, 'error');
            const switchEl = document.getElementById(`voice-status-switch-${roomId}`);
            if (switchEl) switchEl.checked = !enabled;
        }
    }

    // 上传音频文件方法 (需要保留在主类中)
    async uploadAudioFile(file) {
        if (!file.name.toLowerCase().endsWith('.mp3')) {
            this.uiManager.showToast('只支持MP3格式文件', 'error');
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            this.uiManager.showToast('文件大小不能超过5MB', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        const modal = document.getElementById('audio-modal');
        const uploadStatus = document.getElementById('upload-status');
        const progressBar = document.getElementById('upload-progress');

        if (uploadStatus) uploadStatus.textContent = '上传中...';
        if (progressBar) progressBar.style.width = '0%';

        try {
            const response = await fetch('/api/audio/upload', {
                method: 'POST',
                body: formData
            });

            if (uploadStatus) uploadStatus.textContent = '上传完成，处理中...';

            const result = await response.json();

            if (result.success) {
                this.uiManager.showToast('音频文件上传成功', 'success');
                modal.style.display = 'none';
            } else {
                this.uiManager.showToast('上传失败: ' + result.error, 'error');
            }
        } catch (error) {
            this.uiManager.showToast('上传失败: 网络错误', 'error');
        } finally {
            if (uploadStatus) uploadStatus.textContent = '';
            if (progressBar) progressBar.style.width = '0%';
        }
    }

    startRuntimeCounter() {
        const updateRuntime = () => {
            const now = Date.now();
            const elapsed = now - this.startTime;
            const hoursFloat = elapsed / (1000 * 60 * 60);
            const hoursInt = Math.floor(hoursFloat);
            const hasDecimal = hoursFloat - hoursInt > 0.01;
            const hours = hasDecimal ? hoursFloat.toFixed(1) : hoursInt;
            const runtimeBtn = document.getElementById('runtime-btn');
            if (runtimeBtn) {
                runtimeBtn.textContent = `已运行${hours}小时`;
            }
        };

        updateRuntime();
        setInterval(updateRuntime, 60000);
    }
}

// 初始化应用
const app = new IoTControlApp();
window.app = app;
