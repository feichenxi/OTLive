export default class RoomManager {
    constructor(app) {
        this.app = app;
        this.last_viewer_update_time = {};
        this.viewer_timeout_interval = null;
        this._updateDetailsTimer = null;
        this._pendingRoom = null;
        this.startViewerTimeoutCheck();
    }

    /**
     * 格式化人数显示
     * - 0-9999: 原始数字
     * - 10000-99999: 1.0万人
     * - >=100000: 10万+
     */
    formatViewerCount(count) {
        if (count === undefined || count === null || count === '') {
            return null;
        }
        const num = parseInt(count, 10);
        if (isNaN(num) || num <= 0) {
            return null;
        }
        if (num >= 100000) {
            return '10万+';
        }
        if (num >= 10000) {
            const wan = (num / 10000).toFixed(1);
            return `${wan}万人`;
        }
        return `${num}人`;
    }

    startViewerTimeoutCheck() {
        if (this.viewer_timeout_interval) {
            clearInterval(this.viewer_timeout_interval);
        }
        this.viewer_timeout_interval = setInterval(() => {
            const now = Date.now();
            const TIMEOUT = 60 * 1000; // 60秒
            let needUpdate = false;
            this.app.rooms.forEach(room => {
                const lastTime = this.last_viewer_update_time[room.id];
                if (room.viewer_count !== undefined && room.viewer_count !== null && room.viewer_count > 0) {
                    if (!lastTime || (now - lastTime > TIMEOUT)) {
                        room.viewer_count = null;
                        needUpdate = true;
                    }
                }
            });
            if (needUpdate) {
                this.updateRoomButtons();
            }
        }, 1000); // 每秒检查一次
    }

    loadRooms() {
        this.app.socket.emit('get_rooms');
    }

    updateRoomStatus(data) {
        const roomId = data.room_id;
        const online = data.online;
        const rssi = data.rssi;
        const lastSeen = data.last_seen;
        const version = data.version;
        const audioActive = data.audio_active;
        const enabled = data.enabled;
        
        const room = this.app.rooms.find(r => r.id === roomId);
        if (room) {
            room.online = online;
            room.rssi = rssi;
            room.last_seen = lastSeen;
            if (version !== undefined) {
                room.version = version;
            }
            if (audioActive !== undefined) {
                room.audio_active = audioActive;
            }
            if (enabled !== undefined) {
                room.enabled = enabled;
            }
        }
        
        const roomBtn = document.querySelector(`.room-btn[data-room="${roomId}"]`);
        
        if (roomBtn) {
            const statusBadge = roomBtn.querySelector('.room-status-badge');
            if (statusBadge) {
                const isOnline = online;
                const isEnabled = enabled !== false;
                if (isEnabled) {
                    statusBadge.className = `room-status-badge ${isOnline ? 'online' : 'offline'}`;
                    statusBadge.textContent = isOnline ? '在线' : '离线';
                } else {
                        statusBadge.className = 'room-status-badge disabled';
                        statusBadge.textContent = '关闭';
                    }
            }
            
            const viewerCountEl = roomBtn.querySelector('.room-viewer-count');
            if (viewerCountEl) {
                const formatted = this.formatViewerCount(room.viewer_count);
                if (formatted) {
                    viewerCountEl.textContent = formatted;
                    viewerCountEl.style.display = 'inline-block';
                } else {
                    viewerCountEl.style.display = 'none';
                }
            }
        }
        
        const selectedBtn = document.querySelector('.room-btn.active');
        if (selectedBtn && parseInt(selectedBtn.dataset.room) === roomId) {
            // Skip re-render if current room has trigger device to avoid progress bar jumping
            const hasTriggerDevice = room && room.devices && room.devices.some(d => d.name === 'trigger');
            if (!hasTriggerDevice) {
                this.updateRoomDetailsDisplay(room);
            }
        }
        
        this.app.systemManager.updateSystemStatus();
        
        // Update home card status if in home view
        if (!this.app.selectedRoom) {
            this.updateHomeCardStatus();
        }
        
        // 更新首页总在线人数
        this.updateHomeTotalViewers();
    }

    updateRoomButtons() {
        const roomsContainer = document.querySelector('.rooms-grid-10');
        const roomButtons = Array.from(roomsContainer.querySelectorAll('.room-btn'));
        
        // Sort rooms by sort_order (or id if not set)
        this.app.rooms.sort((a, b) => {
            const sortA = a.sort_order !== undefined ? a.sort_order : a.id;
            const sortB = b.sort_order !== undefined ? b.sort_order : b.id;
            return sortA - sortB;
        });

        // Update each room button's status and name
        this.app.rooms.forEach(room => {
            const roomBtn = document.querySelector(`.room-btn[data-room="${room.id}"]`);
            if (roomBtn) {
                const statusBadge = roomBtn.querySelector('.room-status-badge');
                if (statusBadge) {
                    const isEnabled = room.enabled !== false;
                    if (isEnabled) {
                        statusBadge.className = `room-status-badge ${room.online ? 'online' : 'offline'}`;
                        statusBadge.textContent = room.online ? '在线' : '离线';
                    } else {
                            statusBadge.className = 'room-status-badge disabled';
                            statusBadge.textContent = '关闭';
                        }
                }
                
                const roomName = roomBtn.querySelector('.room-name');
                if (roomName) {
                    roomName.textContent = room.name;
                } else {
                    console.error('[RoomManager] room-name element not found for room:', room.id);
                }
                
                const viewerCountEl = roomBtn.querySelector('.room-viewer-count');
                if (viewerCountEl) {
                    const formatted = this.formatViewerCount(room.viewer_count);
                    if (formatted) {
                        viewerCountEl.textContent = formatted;
                        viewerCountEl.style.display = 'inline-block';
                    } else {
                        viewerCountEl.style.display = 'none';
                    }
                }
                
                // 更新房间触发数显示
                this.updateRoomTriggerCount(room);
                
                // 更新房间对讲状态显示
                this.updateRoomIntercomStatus(room);
            }
        });

        // Sort buttons based on room order and re-append to container
        roomButtons.sort((btnA, btnB) => {
            const roomA = this.app.rooms.find(r => r.id === parseInt(btnA.dataset.room));
            const roomB = this.app.rooms.find(r => r.id === parseInt(btnB.dataset.room));
            if (!roomA || !roomB) return 0;
            
            const sortA = roomA.sort_order !== undefined ? roomA.sort_order : roomA.id;
            const sortB = roomB.sort_order !== undefined ? roomB.sort_order : roomB.id;
            return sortA - sortB;
        });

        // Clear container and re-append buttons in sorted order
        roomsContainer.innerHTML = '';
        roomButtons.forEach(btn => {
            roomsContainer.appendChild(btn);
        });
    }

    // 更新房间观看人数
    updateRoomViewerCount(roomIp, viewerCount) {
        const room = this.app.rooms.find(r => r.ip === roomIp);
        if (!room) return;
        
        room.viewer_count = viewerCount;
        this.last_viewer_update_time[room.id] = Date.now();
        
        // 更新左侧房间列表的人数显示
        const roomBtn = document.querySelector(`.room-btn[data-room="${room.id}"]`);
        if (roomBtn) {
            const viewerCountEl = roomBtn.querySelector('.room-viewer-count');
            if (viewerCountEl) {
                const formatted = this.formatViewerCount(viewerCount);
                if (formatted) {
                    viewerCountEl.textContent = formatted;
                    viewerCountEl.style.display = 'inline-block';
                } else {
                    viewerCountEl.style.display = 'none';
                }
            }
        }
        
        // 如果当前选中了这个房间，更新右侧详情的人数显示
        if (this.app.selectedRoom && this.app.selectedRoom.id === room.id) {
            this.updateRoomDetailsViewerCount(room);
        }
        
        // 更新首页总在线人数
        this.updateHomeTotalViewers();
    }

    // 更新房间详情中的人数显示
    updateRoomDetailsViewerCount(room) {
        const viewerCountEl = document.getElementById('room-viewer-count');
        if (!viewerCountEl) return;
        
        const formatted = this.formatViewerCount(room.viewer_count);
        if (formatted) {
            viewerCountEl.textContent = formatted;
            viewerCountEl.style.display = 'inline-block';
        } else {
            viewerCountEl.style.display = 'none';
        }
    }

    getTotalOnlineViewers() {
        return this.app.rooms
            .filter(r => r.viewer_count !== undefined && r.viewer_count !== null && r.viewer_count > 0)
            .reduce((sum, r) => sum + r.viewer_count, 0);
    }

    // 更新首页总在线人数显示
    updateHomeTotalViewers() {
        const totalViewers = this.getTotalOnlineViewers();
        const totalViewersEl = document.getElementById('total-viewers-count');
        if (totalViewersEl) {
            if (totalViewers > 0) {
                const formatted = this.formatViewerCount(totalViewers);
                totalViewersEl.textContent = `，共${formatted ? formatted : totalViewers + '人'}`;
            } else {
                totalViewersEl.textContent = '';
            }
        }
    }

    // 更新房间触发数显示
    updateRoomTriggerCount(room) {
        const roomBtn = document.querySelector(`.room-btn[data-room="${room.id}"]`);
        if (!roomBtn) return;
        
        let totalRemaining = 0;
        
        // 优先从 devices 数组获取数据
        if (room.devices) {
            room.devices.forEach(device => {
                let remainingCount = device.trigger_remaining_count;
                
                // 如果 device.trigger_remaining_count 没有数据，从内存中的 triggerCount 或 triggerCounts 获取
                if (remainingCount === undefined) {
                    if (device.name === 'trigger') {
                        remainingCount = room.triggerCount || 0;
                    } else if (device.name.startsWith('prog')) {
                        remainingCount = room.triggerCounts?.[device.name] || 0;
                    }
                }
                
                if ((device.name === 'trigger' || (device.name.startsWith('prog') && device.trigger_off_duration > 0)) 
                    && remainingCount !== undefined) {
                    totalRemaining += remainingCount;
                }
            });
        }
        
        const triggerCountEl = roomBtn.querySelector('.room-trigger-count');
        if (triggerCountEl) {
            if (totalRemaining > 0) {
                triggerCountEl.textContent = `剩${totalRemaining}次`;
                triggerCountEl.style.display = 'inline-block';
            } else {
                triggerCountEl.style.display = 'none';
            }
        }
        
        // 如果当前房间正在被查看，更新房间详情页的触发数显示
        if (this.app.selectedRoom && this.app.selectedRoom.id === room.id) {
            const roomTriggerCountEl = document.getElementById('room-trigger-count');
            if (roomTriggerCountEl) {
                if (totalRemaining > 0) {
                    roomTriggerCountEl.textContent = `剩${totalRemaining}次`;
                    roomTriggerCountEl.style.display = 'inline-block';
                } else {
                    roomTriggerCountEl.style.display = 'none';
                }
            }
        }
    }
    
    // 更新房间对讲状态显示
    updateRoomIntercomStatus(room) {
        const roomBtn = document.querySelector(`.room-btn[data-room="${room.id}"]`);
        if (!roomBtn) return;
        
        const intercomBadge = roomBtn.querySelector('.room-intercom-badge');
        if (intercomBadge) {
            // 检查是否是当前对讲房间
            const isCurrentIntercomRoom = this.app.currentIntercomRoomId === room.id;
            
            if (room.ai_voice_playing) {
                // AI语音正在播放
                intercomBadge.style.display = 'inline-block';
                intercomBadge.textContent = '🤖';
                intercomBadge.className = 'room-intercom-badge ai-playing';
            } else if (isCurrentIntercomRoom && room.mic_enabled) {
                // 当前对讲房间
                intercomBadge.style.display = 'inline-block';
                intercomBadge.textContent = '🎤';
                intercomBadge.className = 'room-intercom-badge';
            } else {
                // 无状态
                intercomBadge.style.display = 'none';
            }
        }
    }

    async selectRoom(roomId) {
        const previousRoomId = this.app.selectedRoom ? this.app.selectedRoom.id : null;

        if (this.app.patrolDialogEnabled && previousRoomId) {
            const previousRoom = this.app.rooms.find(r => r.id === previousRoomId);
            if (previousRoom && previousRoom.mic_enabled) {
                await this.app.audioManager.toggleRoomDialog(previousRoomId, false);
            }
        }

        // 注意：不再清理之前房间的触发状态，因为触发机制是全局独立的
        // 每个房间的触发任务应该独立运行，不受页面切换影响

        document.querySelectorAll('.room-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        const selectedBtn = document.querySelector(`.room-btn[data-room="${roomId}"]`);
        if (selectedBtn) {
            selectedBtn.classList.add('active');
        }

        const room = this.app.rooms.find(r => r.id === roomId);
        
        if (room) {
            if (room.devices) {
                const triggerDevice = room.devices.find(d => d.name === 'trigger');
                if (triggerDevice) {
                    room.trigger_on_duration = triggerDevice.trigger_on_duration !== undefined ? triggerDevice.trigger_on_duration : 3;
                    room.trigger_off_duration = triggerDevice.trigger_off_duration !== undefined ? triggerDevice.trigger_off_duration : 1;
                } else {
                    room.trigger_on_duration = 3;
                    room.trigger_off_duration = 1;
                }
            } else {
                room.trigger_on_duration = 3;
                room.trigger_off_duration = 1;
            }
            
            this.displayRoomDetails(room);

            if (this.app.patrolDialogEnabled) {
                this.app.rooms.forEach(r => {
                    if (r.id !== roomId && r.mic_enabled) {
                        this.app.audioManager.toggleRoomDialog(r.id, false);
                    }
                });

                if (!room.ai_voice_playing && !room.mic_enabled) {
                    await this.app.audioManager.toggleRoomDialog(roomId, true);
                }
            }
        } else {
            this.displayNoRoomSelected();
        }
    }

    // 计算房间总触发数
    calculateRoomTotalTriggerCount(room) {
        let totalRemaining = 0;
        
        if (room.devices) {
            room.devices.forEach(device => {
                let remainingCount = device.trigger_remaining_count;
                
                // 如果 device.trigger_remaining_count 没有数据，从内存中的 triggerCount 或 triggerCounts 获取
                if (remainingCount === undefined) {
                    if (device.name === 'trigger') {
                        remainingCount = room.triggerCount || 0;
                    } else if (device.name.startsWith('prog')) {
                        remainingCount = room.triggerCounts?.[device.name] || 0;
                    }
                }
                
                if ((device.name === 'trigger' || (device.name.startsWith('prog') && device.trigger_off_duration > 0)) 
                    && remainingCount !== undefined) {
                    totalRemaining += remainingCount;
                }
            });
        }
        
        return totalRemaining;
    }

    displayRoomDetails(room) {
        this.app.selectedRoom = room;
        
        if (room.ai_voice_playing && this.app.patrolDialogEnabled) {
            if (room.mic_enabled_before_ai === undefined) {
                room.mic_enabled_before_ai = room.mic_enabled;
            }
            room.mic_enabled = false;
        }
        
        document.getElementById('home-card').style.display = 'none';
        document.getElementById('room-info').style.display = 'block';

        // Update room info card
        const viewerCount = room.online && room.viewer_count !== undefined ? room.viewer_count + '人' : '';
        const totalTriggerCount = this.calculateRoomTotalTriggerCount(room);

        const roomInfo = document.getElementById('room-info');
        roomInfo.innerHTML = `
            <div class="room-info-header">
                <h2 id="selected-room-name">${room.name}</h2>
                <div class="room-action-buttons">
                    <button class="room-action-btn room-settings-btn" id="room-settings-btn" title="房间设置">⚙️</button>
                    <button class="room-action-btn room-ai-btn" id="room-ai-btn" title="AI配置">🤖</button>
                    <button class="room-action-btn room-sound-btn" id="room-sound-btn" title="音效设置">🔊</button>
                    <button class="room-action-btn room-prog-btn" id="room-prog-btn" title="可编程设备">⚡</button>
                    <button class="room-action-btn room-logs-btn" id="room-logs-btn" title="触发日志">📋</button>
                </div>
            </div>
            <div class="room-status-info">
                <span class="room-meta-item status-badge ${room.enabled !== false ? (room.online ? 'online' : 'offline') : 'disabled'}">
                    ${room.enabled !== false ? (room.online ? '在线' : '离线') : '关闭'}
                </span>
                ${room.audio_active ? '<span class="status-badge audio-active">音频</span>' : ''}
                <span class="room-meta-item">IP: ${room.ip}</span>
                <span class="room-meta-item">信号: ${room.rssi || 'N/A'} dBm</span>
                <span class="room-meta-item">固件: ${room.version || '未知'}</span>
                <span class="room-meta-item room-viewer-count-info" id="room-viewer-count" style="${room.viewer_count !== undefined && room.viewer_count > 0 ? '' : 'display: none;'}">${viewerCount}</span>
                <span class="room-meta-item room-trigger-count-info" id="room-trigger-count" style="${room.online && totalTriggerCount > 0 ? '' : 'display: none;'}">剩${totalTriggerCount}次</span>
            </div>
        `;

        // Bind action buttons
        document.getElementById('room-settings-btn').addEventListener('click', () => {
            this.app.uiManager.openRoomSettingsDialog(room);
        });

        document.getElementById('room-ai-btn').addEventListener('click', () => {
            this.app.uiManager.openRoomAIConfigDialog(room);
        });

        document.getElementById('room-sound-btn').addEventListener('click', () => {
            this.app.uiManager.openSoundSettingsDialog(room);
        });

        document.getElementById('room-prog-btn').addEventListener('click', () => {
            this.app.uiManager.openProgConfigDialog(room);
        });

        document.getElementById('room-logs-btn').addEventListener('click', () => {
            this.openTriggerLogsDialog(room);
        });

        this.updateRoomDetailsDisplay(room, true);
        this.app.triggerManager.startRefresh(room.id, (devices) => {
            this.app.triggerManager.updateRoomTriggerCounts(room.id, devices);
        });

        // 切换显示对应的消息容器
        this.app.messageManager.showPanel(room.id);
    }

    _isDialogOpen() {
        if (document.querySelector('.settings-dialog-overlay')) return true;
        const modalIds = ['prog-config-modal', 'trigger-logs-modal', 'gift-config-modal', 'message-detail-modal'];
        for (const id of modalIds) {
            const el = document.getElementById(id);
            if (el && el.style.display === 'flex') return true;
        }
        return false;
    }

    updateRoomDetailsDisplay(room, force = false) {
        this._pendingRoom = room;

        if (this._updateDetailsTimer) {
            clearTimeout(this._updateDetailsTimer);
        }

        if (force) {
            this._executeUpdateRoomDetails(room);
            return;
        }

        this._updateDetailsTimer = setTimeout(() => {
            this._updateDetailsTimer = null;
            if (this._isDialogOpen()) {
                this._updateDetailsTimer = setTimeout(() => {
                    this._updateDetailsTimer = null;
                    if (this._pendingRoom) {
                        this.updateRoomDetailsDisplay(this._pendingRoom);
                    }
                }, 500);
                return;
            }
            if (this._pendingRoom) {
                this._executeUpdateRoomDetails(this._pendingRoom);
            }
        }, 200);
    }

    _executeUpdateRoomDetails(room) {
        const roomControls = document.getElementById('room-controls');
        
        if (room.ai_thank_enabled === undefined) {
            this._loadRoomAiThankStatus(room);
        }
        
        const enabledDevices = room.devices.filter(device => {
            if (device.name.startsWith('prog')) {
                return device.enabled === true;
            }
            return true;
        });

        let devicesHtml = enabledDevices.map(device => {
            if (device.name === 'trigger') {
                const triggerOn = room.trigger_on_duration !== undefined ? room.trigger_on_duration : 3;
                const triggerOff = room.trigger_off_duration !== undefined ? room.trigger_off_duration : 1;
                const initialCount = room.triggerCount || 0;
                return `
                    <div class="room-status-card">
                        <div class="card-header-with-action">
                            <h3>主触发装置</h3>
                            <div class="audio-level-indicator">
                                <div class="audio-level-bar">
                                    <div class="audio-level-fill" id="trigger-level-${room.id}"></div>
                                    <span class="audio-level-text" id="trigger-level-text-${room.id}">${initialCount}</span>
                                </div>
                            </div>
                        </div>
                        <div class="device-status-controls">
                            <div style="display: flex; align-items: center;">
                                <div class="device-state ${device.state ? 'on' : 'off'}"></div>
                                <span>状态: <span id="trigger-status-${room.id}">${device.state ? '已打开' : '已关闭'}</span></span>
                            </div>
                            <div class="device-controls">
                                <div class="trigger-button-group">
                                    <button class="device-btn" onclick="app.openTriggerProgramDialog(${room.id})">
                                        编程
                                    </button>
                                </div>
                                <div class="trigger-button-group">
                                    <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 1)">触发</button>
                                    <span class="trigger-btn-separator">|</span>
                                    <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 3)">三</button>
                                    <span class="trigger-btn-separator">|</span>
                                    <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 10)">十</button>
                                    <span class="trigger-btn-separator">|</span>
                                    <button class="device-btn" onclick="app.clearTriggerCount(${room.id})">清</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            } else if (device.name === 'always') {
                return `
                    <div class="room-status-card">
                        <h3>主常动装置</h3>
                        <div class="device-status-controls">
                            <div style="display: flex; align-items: center;">
                                <div class="device-state ${device.state ? 'on' : 'off'}"></div>
                                <span>状态: ${device.state ? '已打开' : '已关闭'}</span>
                            </div>
                            <div class="device-controls">
                                <button class="device-btn" onclick="app.uiManager.openLoopSettingsDialog(app.selectedRoom)">定时</button>
                                <button class="device-btn on" onclick="app.controlDevice(${room.id}, '${device.name}', 'on')">打开</button>
                                <button class="device-btn off" onclick="app.controlDevice(${room.id}, '${device.name}', 'off')">关闭</button>
                            </div>
                        </div>
                    </div>
                `;
            } else if (device.name.startsWith('prog')) {
                const triggerOffDuration = device.trigger_off_duration !== undefined ? device.trigger_off_duration : 0;
                if (triggerOffDuration > 0) {
                    const initialCount = room.triggerCounts?.[device.name] || 0;
                    return `
                        <div class="room-status-card">
                            <div class="card-header-with-action">
                                <h3>${device.label} 🎯</h3>
                                <div class="audio-level-indicator">
                                    <div class="audio-level-bar">
                                        <div class="audio-level-fill" id="trigger-level-${room.id}-${device.name}"></div>
                                        <span class="audio-level-text" id="trigger-level-text-${room.id}-${device.name}">${initialCount}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="device-status-controls">
                                <div style="display: flex; align-items: center;">
                                    <div class="device-state ${device.state ? 'on' : 'off'}"></div>
                                    <span>状态: <span id="trigger-status-${room.id}-${device.name}">${device.state ? '已打开' : '已关闭'}</span></span>
                                </div>
                                <div class="device-controls">
                                    <div class="trigger-button-group">
                                        <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 1)">触发</button>
                                        <span class="trigger-btn-separator">|</span>
                                        <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 3)">三</button>
                                        <span class="trigger-btn-separator">|</span>
                                        <button class="device-btn" onclick="app.triggerDeviceWithDuration(${room.id}, '${device.name}', 10)">十</button>
                                        <span class="trigger-btn-separator">|</span>
                                        <button class="device-btn" onclick="app.clearTriggerCount(${room.id}, '${device.name}')">清</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    return `
                        <div class="room-status-card">
                            <h3>${device.label} ♾️</h3>
                            <div class="device-status-controls">
                                <div style="display: flex; align-items: center;">
                                    <div class="device-state ${device.state ? 'on' : 'off'}"></div>
                                    <span>状态: ${device.state ? '已打开' : '已关闭'}</span>
                                </div>
                                <div class="device-controls">
                                    <button class="device-btn on" onclick="app.controlDevice(${room.id}, '${device.name}', 'on')">打开</button>
                                    <button class="device-btn off" onclick="app.controlDevice(${room.id}, '${device.name}', 'off')">关闭</button>
                                </div>
                            </div>
                        </div>
                    `;
                }
            } else {
                return `
                    <div class="room-status-card">
                        <h3>${device.label}</h3>
                        <div class="device-status-controls">
                            <div style="display: flex; align-items: center;">
                                <div class="device-state ${device.state ? 'on' : 'off'}"></div>
                                <span>状态: ${device.state ? '已打开' : '已关闭'}</span>
                            </div>
                            <div class="device-controls">
                                <button class="device-btn on" onclick="app.controlDevice(${room.id}, '${device.name}', 'on')">打开</button>
                                <button class="device-btn off" onclick="app.controlDevice(${room.id}, '${device.name}', 'off')">关闭</button>
                            </div>
                        </div>
                    </div>
                `;
            }
        }).join('');

        
        let dialogHtml = `
            <div class="room-status-card">
                <div class="room-intercom-header">
                    <h3>房间语音</h3>
                    <div class="audio-level-indicator">
                        <div class="audio-level-bar">
                            <div class="audio-level-fill" id="audio-level-${room.id}"></div>
                            <span class="audio-level-text" id="audio-level-text-${room.id}">0</span>
                        </div>
                    </div>
                </div>
                <div class="dialog-control-panel">
                    <div class="dialog-control-row">
                        <div class="interaction-item" style="display: flex; align-items: center; gap: 8px; margin-right: 15px; cursor: pointer;" onclick="${room.ai_voice_playing ? "app.uiManager.showToast('AI正在播报中，禁止操作，请稍后...', 'info');" : ''}">
                            <div class="interaction-switch">
                                <label class="switch ${room.ai_voice_playing ? 'temporarily-disabled' : ''}">
                                    <input type="checkbox" id="device-dialog-switch-${room.id}" ${room.mic_enabled ? 'checked' : ''} data-room-id="${room.id}" ${room.ai_voice_playing ? 'disabled' : ''}>
                                    <span class="slider"></span>
                                </label>
                            </div>
                            <span class="interaction-label">${room.ai_voice_playing ? '临时禁用' : '房间对讲'}</span>
                        </div>
                        <div class="interaction-item" style="display: flex; align-items: center; gap: 8px; margin-right: 15px; cursor: pointer;" onclick="app.toggleVoiceStatus(${room.id}, document.getElementById('voice-status-switch-${room.id}').checked)">
                            <div class="interaction-switch">
                                <label class="switch ${room.ai_voice_playing ? 'temporarily-disabled' : ''}">
                                    <input type="checkbox" id="voice-status-switch-${room.id}" ${room.ai_voice_playing ? 'checked disabled' : (room.ai_thank_enabled ? 'checked' : '')}>
                                    <span class="slider"></span>
                                </label>
                            </div>
                            <span class="interaction-label">${room.ai_voice_playing ? '播报中' : 'AI回复'}</span>
                        </div>
                        <button class="device-btn" onclick="app.openIntercomVolumeDialog(${room.id})">
                            对讲音量 ${room.intercom_volume ?? 50}%
                        </button>
                    </div>
                </div>
            </div>
        `;

        let interactionMonitorHtml = `
            <div class="room-status-card">
                <h3>房间互动</h3>
                <div class="device-status-controls">
                    <div style="display: flex; align-items: center;">
                        <div class="device-state off" id="collector-status-dot-${room.id}"></div>
                        <span>状态: <span id="collector-status-text-${room.id}">已关闭</span></span>
                    </div>
                    <div class="interaction-control-row" style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-top: 10px;">
                        <div class="interaction-item" style="display: flex; align-items: center; gap: 8px;">
                            <div class="interaction-switch">
                                <label class="switch">
                                    <input type="checkbox" id="interaction-monitor-switch-${room.id}" onchange="app.toggleInteractionMonitor(${room.id}, this.checked)">
                                    <span class="slider"></span>
                                </label>
                            </div>
                            <span class="interaction-label">采集互动</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        let parametersHtml = `
            <div class="room-parameters-card">
                <h3>其他设备</h3>
                <div class="other-devices-grid">
                    <div class="other-device-item">
                        <span class="other-device-name">主灯照明</span>
                        <div class="other-device-switch">
                            <label class="switch">
                                <input type="checkbox" id="device-main-light" ${room.main_light ? 'checked' : ''}>
                                <span class="slider"></span>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const controlsHtml = devicesHtml + dialogHtml + interactionMonitorHtml + parametersHtml;

        roomControls.innerHTML = controlsHtml;
        
        // 重新生成HTML后，恢复触发装置进度条的背景宽度
        this.app.deviceController.updateTriggerProgress(room.id);
        
        // 更新所有副触发装置的进度条
        enabledDevices.forEach(device => {
            if (device.name.startsWith('prog')) {
                const triggerOffDuration = device.trigger_off_duration !== undefined ? device.trigger_off_duration : 0;
                if (triggerOffDuration > 0) {
                    this.app.deviceController.updateTriggerProgress(room.id, device.name);
                }
            }
        });

        // 绑定对讲开关事件监听器
        const dialogSwitch = document.getElementById(`device-dialog-switch-${room.id}`);
        if (dialogSwitch) {
            dialogSwitch.addEventListener('change', async (e) => {
                if (room.ai_voice_playing) {
                    this.app.uiManager.showToast('AI正在播报中，禁止操作，请稍后...', 'info');
                    e.preventDefault();
                    return;
                }
                e.target.disabled = true;
                try {
                    await this.app.toggleRoomDialog(room.id, e.target.checked);
                } finally {
                    e.target.disabled = false;
                }
            });
        }
    }

    displayNoRoomSelected() {
        const roomInfo = document.getElementById('room-info');
        roomInfo.innerHTML = `
            <h2>请选择一个房间</h2>
            <p>点击左侧房间按钮查看详细信息</p>
        `;

        const roomControls = document.getElementById('room-controls');
        roomControls.innerHTML = '';

        // 停止触发状态刷新
        this.app.triggerManager.stopRefresh();
    }

    updateHomeCardStatus() {
        const enabledRooms = this.app.rooms.filter(r => r.enabled !== false);
        const totalRooms = enabledRooms.length;
        const onlineRooms = enabledRooms.filter(r => r.online).length;
        const offlineRooms = totalRooms - onlineRooms;
        const disabledRooms = this.app.rooms.filter(r => r.enabled === false).length;
        const totalViewers = this.getTotalOnlineViewers();
        
        const homeStatusInfo = document.querySelector('#home-card .room-status-info');
        
        if (homeStatusInfo) {
            const htmlContent = `
                <span class="room-meta-item">共${this.app.rooms.length}个房间，其中</span>
                <span class="room-meta-item status-badge online">${onlineRooms}个在线</span>
                <span class="room-meta-item status-badge offline">${offlineRooms}个离线</span>
                ${disabledRooms > 0 ? `<span class="room-meta-item status-badge disabled">${disabledRooms}个关闭</span>` : ''}
                <span class="room-meta-item" id="total-viewers-count">${totalViewers > 0 ? `，共${totalViewers}人在线` : ''}</span>
            `;
            homeStatusInfo.innerHTML = htmlContent;
        } else {
            console.error('[RoomManager] homeStatusInfo element not found!');
        }
    }

    showHomeView() {
        // Stop microphone if active
        this.app.audioManager.stopMicrophone();
        
        // Clear selected room
        this.app.selectedRoom = null;
        
        // Remove active class from all
        document.querySelectorAll('.room-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Add active class to home button
        document.getElementById('home-btn').classList.add('active');

        // Show home card, hide room info
        document.getElementById('home-card').style.display = 'block';
        document.getElementById('room-info').style.display = 'none';

        // Reset home card title
        const homeCardTitle = document.getElementById('home-card-title');
        if (homeCardTitle) {
            homeCardTitle.textContent = '全部直播间';
        }

        // Update home card status info
        this.updateHomeCardStatus();

        // Update room details section with home-specific content
        const roomControls = document.getElementById('room-controls');
        
        let devicesHtml = `
            <div class="room-status-card">
                <h3>面向全部直播间触发</h3>
                <div class="device-status-controls">
                    <div style="display: flex; align-items: center;">
                        <div class="device-state off"></div>
                        <span>状态: 已关闭</span>
                    </div>
                    <div class="device-controls">
                        <button class="device-btn on" onclick="app.toggleBroadcastTrigger(true)">打开</button>
                        <button class="device-btn off" onclick="app.toggleBroadcastTrigger(false)">关闭</button>
                    </div>
                </div>
            </div>
            <div class="room-status-card">
                <h3>面向全部直播间广播</h3>
                <div class="device-status-controls">
                    <div style="display: flex; align-items: center;">
                        <div class="device-state off"></div>
                        <span>状态: 已关闭</span>
                    </div>
                    <div class="device-controls">
                        <button class="device-btn on" onclick="app.toggleBroadcastAudio(true)">打开</button>
                        <button class="device-btn off" onclick="app.toggleBroadcastAudio(false)">关闭</button>
                    </div>
                </div>
            </div>
        `;

        roomControls.innerHTML = devicesHtml;
        
        // 显示首页消息容器
        this.app.messageManager.showPanel('home');
    }
    
    openTriggerLogsDialog(room) {
        const modal = document.getElementById('trigger-logs-modal');
        const roomNameSpan = document.getElementById('trigger-logs-room-name');
        const logsList = document.getElementById('trigger-logs-list');
        
        roomNameSpan.textContent = room.name;
        logsList.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">加载中...</td></tr>';
        modal.style.display = 'flex';
        
        // 保存当前房间ID和设备映射
        this.currentLogsRoomId = room.id;
        this.currentLogsDeviceMap = {};
        this.currentLogsFilter = 'all';
        this.currentLogsData = [];
        
        // 加载设备信息和日志
        this.loadTriggerLogsWithDevices(room.id);
        
        // 绑定关闭按钮
        document.getElementById('trigger-logs-modal-close').onclick = () => {
            modal.style.display = 'none';
        };
        document.getElementById('trigger-logs-modal-refresh').onclick = () => {
            this.loadTriggerLogsWithDevices(room.id);
        };
        
        // 点击遮罩关闭
        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        };
    }
    
    async loadTriggerLogsWithDevices(roomId) {
        try {
            // 并行加载设备配置和日志
            const [devicesResponse, logsResponse] = await Promise.all([
                fetch(`/api/rooms/${roomId}/all_devices`),
                fetch(`/api/rooms/${roomId}/trigger_logs`)
            ]);
            
            const devicesData = await devicesResponse.json();
            const logsData = await logsResponse.json();
            
            // 构建设备名称映射表
            this.currentLogsDeviceMap = {};
            if (devicesData && devicesData.devices) {
                devicesData.devices.forEach(device => {
                    if (device.name === 'trigger') {
                        this.currentLogsDeviceMap['trigger'] = '主触发';
                    } else if (device.name.startsWith('prog')) {
                        this.currentLogsDeviceMap[device.name] = device.label || device.name;
                    }
                });
            }
            
            // 保存日志数据
            this.currentLogsData = logsData.success ? logsData.logs : [];
            
            // 生成筛选按钮
            this.renderDeviceFilterButtons(devicesData.devices);
            
            // 渲染日志列表
            this.renderTriggerLogs();
            
        } catch (error) {
            console.error('加载触发日志失败:', error);
            document.getElementById('trigger-logs-list').innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--danger-color);">加载失败</td></tr>';
        }
    }
    
    renderDeviceFilterButtons(devices) {
        const filterContainer = document.getElementById('trigger-logs-filter');
        
        // 保留"全部"和"主触发"按钮，清除动态生成的
        const existingDynamic = filterContainer.querySelectorAll('.device-filter-btn[data-device^="prog"]');
        existingDynamic.forEach(btn => btn.remove());
        
        // 添加可编程设备按钮
        if (devices) {
            devices.forEach(device => {
                if (device.name.startsWith('prog') && device.enabled) {
                    const btn = document.createElement('button');
                    btn.className = 'device-filter-btn';
                    btn.dataset.device = device.name;
                    btn.textContent = device.label || device.name;
                    btn.onclick = () => this.setLogsFilter(device.name);
                    filterContainer.appendChild(btn);
                }
            });
        }
        
        // 绑定固定按钮事件
        const allBtn = filterContainer.querySelector('[data-device="all"]');
        const triggerBtn = filterContainer.querySelector('[data-device="trigger"]');
        
        if (allBtn) {
            allBtn.onclick = () => this.setLogsFilter('all');
        }
        if (triggerBtn) {
            triggerBtn.onclick = () => this.setLogsFilter('trigger');
        }
        
        // 设置当前激活状态
        this.updateFilterButtonState();
    }
    
    setLogsFilter(device) {
        this.currentLogsFilter = device;
        this.updateFilterButtonState();
        this.renderTriggerLogs();
    }
    
    updateFilterButtonState() {
        const filterContainer = document.getElementById('trigger-logs-filter');
        const buttons = filterContainer.querySelectorAll('.device-filter-btn');
        
        buttons.forEach(btn => {
            if (btn.dataset.device === this.currentLogsFilter) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    renderTriggerLogs() {
        const logsList = document.getElementById('trigger-logs-list');
        
        // 根据筛选条件过滤日志
        let filteredLogs = this.currentLogsData;
        if (this.currentLogsFilter !== 'all') {
            filteredLogs = this.currentLogsData.filter(log => log.device_name === this.currentLogsFilter);
        }
        
        if (filteredLogs.length > 0) {
            logsList.innerHTML = filteredLogs.map(log => {
                const date = new Date(log.created_at);
                const timeStr = date.toLocaleString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
                
                // 使用中文设备名称
                const deviceName = this.currentLogsDeviceMap[log.device_name] || log.device_name;
                
                return `
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 8px; font-size: 12px;">${timeStr}</td>
                        <td style="padding: 8px; font-size: 12px;">${deviceName}</td>
                        <td style="padding: 8px; font-size: 12px;">${log.gift_name}</td>
                        <td style="padding: 8px; text-align: center; font-size: 12px;">${log.gift_count}</td>
                        <td style="padding: 8px; text-align: center; font-size: 12px; color: var(--primary-color); font-weight: bold;">+${log.trigger_count}</td>
                        <td style="padding: 8px; text-align: center; font-size: 12px;">${log.original_count}</td>
                        <td style="padding: 8px; text-align: center; font-size: 12px; color: var(--success-color);">${log.remaining_count}</td>
                    </tr>
                `;
            }).join('');
        } else {
            logsList.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">暂无触发记录</td></tr>';
        }
    }

    async _loadRoomAiThankStatus(room) {
        room.ai_thank_enabled = false;
        try {
            const response = await fetch(`https://live.hzjt.com/api/upload_voice.php?action=get&room=${room.ip}&license_id=${this.app.licenseId || 0}`);
            const data = await response.json();
            if (data.code === 0 && data.data) {
                room.ai_thank_enabled = Number(data.data.ai_thank_enabled) === 1;
            }
        } catch (e) {
            console.error('加载房间AI答谢状态失败:', e);
        }
        
        const switchEl = document.getElementById(`voice-status-switch-${room.id}`);
        if (switchEl && !room.ai_voice_playing) {
            switchEl.checked = room.ai_thank_enabled;
        }
    }
}