export default class SocketManager {
    constructor(app) {
        this.app = app;
        this.socket = null;
        this._messageContainersInitialized = false;
    }

    connectSocket() {
        this.socket = io({
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            transports: ['websocket', 'polling'],
            forceNew: false,
            rememberUpgrade: true
        });
        
        this.app.socket = this.socket;
        
        this.socket.on('connect', () => {
            this.app.systemManager.updateConnectionStatus(true);
            this.app.systemManager.loadSystemStatus();
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket.IO 连接错误:', error);
        });

        this.socket.on('disconnect', (reason) => {
            this.app.systemManager.updateConnectionStatus(false);
        });

        this.socket.on('reconnect', (attemptNumber) => {
            this.app.systemManager.updateConnectionStatus(true);
        });

        this.socket.on('reconnect_attempt', (attemptNumber) => {
        });

        this.socket.on('reconnect_error', (error) => {
            console.error('Socket.IO 重连失败:', error);
        });

        this.socket.on('rooms_update', (data) => {
            const previousRoomStatus = {};
            this.app.rooms.forEach(room => {
                previousRoomStatus[room.id] = {
                    online: room.online,
                    rssi: room.rssi,
                    last_seen: room.last_seen,
                    audio_active: room.audio_active
                };
            });
            
            this.app.rooms = data.rooms;
            const now = Date.now();
            this.app.rooms.forEach(room => {
                if (room.viewer_count !== undefined && room.viewer_count !== null && room.viewer_count > 0) {
                    this.app.roomManager.last_viewer_update_time[room.id] = now;
                }
            });
            
            this.app.rooms.forEach(room => {
                if (previousRoomStatus[room.id]) {
                    const prevStatus = previousRoomStatus[room.id];
                    if (prevStatus.last_seen && (!room.last_seen || prevStatus.last_seen > room.last_seen)) {
                        room.online = prevStatus.online;
                        room.rssi = prevStatus.rssi;
                        room.last_seen = prevStatus.last_seen;
                    }
                    if (prevStatus.audio_active !== undefined && room.audio_active !== prevStatus.audio_active) {
                        room.audio_active = prevStatus.audio_active;
                    }
                }
                
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
            });
            
            this.app.roomManager.updateRoomButtons();
            this.app.systemManager.updateSystemStatus();
            
            // 首次加载房间时初始化消息容器
            if (!this._messageContainersInitialized) {
                this._messageContainersInitialized = true;
                this.app.messageManager.initAllMessageContainers();
            }
            
            if (!this.app.selectedRoom) {
                this.app.roomManager.updateHomeCardStatus();
            } else {
                // 更新当前选中房间的详情显示
                const selectedRoom = this.app.rooms.find(r => r.id === this.app.selectedRoom.id);
                if (selectedRoom) {
                    this.app.selectedRoom = selectedRoom;
                    this.app.roomManager.updateRoomDetailsDisplay(selectedRoom);
                }
            }
            
            // 启动全局触发状态刷新（如果还没启动）
            this.app.triggerManager.startGlobalRefresh();
        });

        this.socket.on('room_status_update', (data) => {
            this.app.roomManager.updateRoomStatus(data);
        });

        this.socket.on('device_status_update', (data) => {
            this.app.systemManager.updateDeviceStatus(data);
        });

        this.socket.on('audio_status_update', (data) => {
            this.app.audioManager.updateAudioStatus(data);
        });

        this.socket.on('audio_switched', (data) => {
            this.app.currentAudioRoom = data.room_id;
            this.app.broadcastMode = false;
            this.app.audioManager.updateAudioUI();
        });

        this.socket.on('broadcast_toggled', (data) => {
            this.app.broadcastMode = data.enabled;
            if (data.enabled) {
                this.app.currentAudioRoom = null;
            }
            this.app.audioManager.updateAudioUI();
        });

        this.socket.on('microphone_toggled', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.mic_enabled = data.enabled;
                
                if (this.app.selectedRoom && this.app.selectedRoom.id === data.room_id) {
                    this.app.roomManager.updateRoomDetailsDisplay(room);
                }
            }
        });

        this.socket.on('device_control_result', (data) => {
            if (!data.success) {
                const room = this.app.rooms.find(r => r.id === data.room_id);
                const roomName = room ? room.name : `房间${data.room_id}`;
                const deviceName = data.device || '未知设备';
                this.app.uiManager.showToast(`房间【${roomName}】，设备【${deviceName}】控制失败`, 'error');
            }
        });

        this.socket.on('room_name_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.name = data.name;
                
                const roomBtn = document.querySelector(`.room-btn[data-room="${room.id}"]`);
                if (roomBtn) {
                    const roomName = roomBtn.querySelector('.room-name');
                    if (roomName) {
                        roomName.textContent = data.name;
                    }
                }
                const selectedBtn = document.querySelector('.room-btn.active');
                if (selectedBtn && parseInt(selectedBtn.dataset.room) === room.id) {
                    this.app.roomManager.updateRoomDetailsDisplay(room);
                    const roomInfoHeader = document.getElementById('selected-room-name');
                    if (roomInfoHeader) {
                        roomInfoHeader.textContent = data.name;
                    }
                }
            }
        });

        this.socket.on('room_sort_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.sort_order = data.sort_order;
                this.app.roomManager.updateRoomButtons();
            }
        });

        this.socket.on('room_intercom_volume_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.intercom_volume = data.volume;
                
                const speakerBtn = document.querySelector(`.device-btn[onclick*="openVolumeDialog(${room.id})"]`);
                if (speakerBtn) {
                    speakerBtn.textContent = `音量 ${data.volume}%`;
                }
                
                const intercomBtn = document.querySelector(`.device-btn[onclick*="openIntercomVolumeDialog(${room.id})"]`);
                if (intercomBtn) {
                    intercomBtn.textContent = `对讲音量 ${data.volume}%`;
                }
            }
        });

        this.socket.on('intercom_status_update', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.mic_enabled = data.enabled;
                
                // If of room is currently selected, update display
                // Skip trigger device room to avoid progress bar jumping
                const hasTriggerDevice = room && room.devices && room.devices.some(d => d.name === 'trigger');
                if (!hasTriggerDevice) {
                    const selectedBtn = document.querySelector('.room-btn.active');
                    if (selectedBtn && parseInt(selectedBtn.dataset.room) === data.room_id) {
                        this.app.roomManager.updateRoomDetailsDisplay(room);
                    }
                }
                
                // 更新房间对讲状态显示
                this.app.roomManager.updateRoomIntercomStatus(room);
            }
        });

        this.socket.on('all_intercom_status', (data) => {
            const intercomStatus = data.intercom_status || {};
            for (const [roomId, enabled] of Object.entries(intercomStatus)) {
                const room = this.app.rooms.find(r => r.id === parseInt(roomId));
                if (room) {
                    room.mic_enabled = enabled;
                }
            }
            // Update all room buttons
            this.app.roomManager.updateRoomButtons();
        });
        
        this.socket.on('current_intercom_room_update', (data) => {
            this.app.currentIntercomRoomId = data.room_id;
            // 更新所有房间的对讲状态显示
            this.app.rooms.forEach(r => {
                this.app.roomManager.updateRoomIntercomStatus(r);
            });
        });
        
        this.socket.on('ai_voice_playing', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                if (data.playing) {
                    room.ai_voice_playing = true;
                    if (this.app.patrolDialogEnabled) {
                        room.mic_enabled_before_ai = room.mic_enabled;
                        if (room.mic_enabled) {
                            room.mic_enabled = false;
                        }
                    }
                } else {
                    room.ai_voice_playing = false;
                    if (this.app.patrolDialogEnabled && room.mic_enabled_before_ai !== undefined) {
                        room.mic_enabled = room.mic_enabled_before_ai;
                        delete room.mic_enabled_before_ai;
                    }
                }
                this.app.roomManager.updateRoomIntercomStatus(room);
                if (this.app.selectedRoom && this.app.selectedRoom.id === data.room_id) {
                    this.app.roomManager.updateRoomDetailsDisplay(room);
                }
            }
        });

        this.socket.on('audio_level_update', (data) => {
            const roomId = data.room_id;
            const level = data.level;
            const levelBar = document.getElementById(`audio-level-${roomId}`);
            const levelText = document.getElementById(`audio-level-text-${roomId}`);
            if (levelBar && levelText) {
                const percentage = Math.min(100, Math.max(0, level));
                levelBar.style.width = `${percentage}%`;
                levelText.textContent = level;
            }
        });

        this.socket.on('room_background_music_url_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.background_music_url = data.url;
                room.background_music_name = data.music_name || '';
                room.background_music_size = data.size || 0;
            }
        });

        this.socket.on('room_live_url_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.live_url = data.live_url;
            }
        });

        this.socket.on('all_interaction_update', (data) => {
            this.app.messageManager.updateAllInteractionList(data);
        });

        this.socket.on('all_gift_update', (data) => {
            this.app.messageManager.updateAllGiftList(data);
        });

        this.socket.on('gift_status_update', (data) => {
            const roomId = data.room_id;
            const giftId = data.gift_id;
            const status = data.status;
            if (roomId !== undefined && giftId !== undefined && status !== undefined) {
                this.app.messageManager.updateGiftStatus(roomId, giftId, status);
            }
        });

        this.socket.on('new_gifts', (data) => {
            const roomId = data.room_id;
            const gifts = data.gifts || [];
            if (gifts.length === 0) return;
            const room = this.app.rooms.find(r => r.id === roomId);
            const roomIp = room ? room.ip : '';
            gifts.forEach(g => {
                const msg = {
                    id: g.id || Date.now() + Math.random(),
                    type: 'gif',
                    name: g.nickname || '',
                    content: g.content || '',
                    gift_name: g.gift_name || '',
                    gift_count: g.gift_count || 0,
                    gift_price: g.gift_price || 0,
                    status: g.status || 0,
                    room: roomIp,
                    room_id: roomId,
                    created_at: g.created_at || ''
                };
                this.app.messageManager.appendMessage(msg);
            });
        });

        this.socket.on('new_messages', (data) => {
            const roomId = data.room_id;
            const msgs = data.messages || [];
            if (msgs.length === 0) return;
            const room = this.app.rooms.find(r => r.id === roomId);
            const roomIp = room ? room.ip : '';
            msgs.forEach(m => {
                const msg = {
                    id: m.id || Date.now() + Math.random(),
                    type: m.type || 'msg',
                    name: m.nickname || '',
                    content: m.content || '',
                    room: roomIp,
                    room_id: roomId,
                    created_at: m.created_at || ''
                };
                this.app.messageManager.appendMessage(msg);
            });
        });

        this.socket.on('viewer_count_update', (data) => {
            if (data.room_ip && data.viewer_count !== undefined) {
                this.app.roomManager.updateRoomViewerCount(data.room_ip, data.viewer_count);
            }
        });

        this.socket.on('audio_file_played', (data) => {
            if (!data.success) {
                this.app.uiManager.showToast('音频文件播放失败', 'error');
            }
        });

        this.socket.on('background_music_played', (data) => {
            if (!data.success) {
                this.app.uiManager.showToast('背景音乐播放失败', 'error');
            }
        });

        this.socket.on('background_music_stopped', (data) => {
            if (!data.success) {
                this.app.uiManager.showToast('背景音乐停止失败', 'error');
            }
        });

        this.socket.on('room_background_music_url_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                room.background_music_url = data.url;
                room.background_music_name = data.music_name || '';
                room.background_music_size = data.size || 0;
            }
        });

        this.socket.on('trigger_device_config_updated', (data) => {
            const room = this.app.rooms.find(r => r.id === data.room_id);
            if (room) {
                if (room.devices) {
                    const triggerDevice = room.devices.find(d => d.name === 'trigger');
                    if (triggerDevice) {
                        triggerDevice.trigger_on_duration = data.trigger_on_duration;
                        triggerDevice.trigger_off_duration = data.trigger_off_duration;
                    }
                }
                room.trigger_on_duration = data.trigger_on_duration;
                room.trigger_off_duration = data.trigger_off_duration;
            }
        });

        this.socket.on('shutdown_progress', (data) => {
            this.app.uiManager.updateShutdownProgress(data);
        });

        this.socket.on('error', (data) => {
            this.app.uiManager.showToast(data.message, 'error');
        });
    }
}