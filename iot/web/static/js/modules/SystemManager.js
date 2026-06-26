export default class SystemManager {
    constructor(app) {
        this.app = app;
    }

    async loadSystemStatus() {
        try {
            const response = await fetch('/api/system/status');
            const data = await response.json();
            if (data.patrol_dialog_enabled !== undefined) {
                this.app.patrolDialogEnabled = data.patrol_dialog_enabled;
                localStorage.setItem('patrolDialogEnabled', this.app.patrolDialogEnabled);
            }
            if (data.current_intercom_room_id !== undefined) {
                this.app.currentIntercomRoomId = data.current_intercom_room_id;
                // 更新所有房间的对讲状态显示
                this.app.rooms.forEach(r => {
                    this.app.roomManager.updateRoomIntercomStatus(r);
                });
            }
            if (data.license_id !== undefined) {
                this.app.licenseId = data.license_id;
            }
            
            // 如果有当前选中的房间，更新房间详情显示
            if (this.app.selectedRoom) {
                this.app.roomManager.updateRoomDetailsDisplay(this.app.selectedRoom);
            }
        } catch (error) {
            console.error('加载系统状态失败:', error);
        }
    }

    updateSystemStatus() {
        const onlineCount = this.app.rooms.filter(r => r.online).length;
        const totalCount = this.app.rooms.length;
        
        const homeStatusBadge = document.getElementById('home-status-badge');
        if (homeStatusBadge) {
            const offlineCount = totalCount - onlineCount;
            homeStatusBadge.textContent = `共${totalCount}个房间，其中${onlineCount}个在线，${offlineCount}个离线`;
        }
    }

    updateConnectionStatus(connected) {
        const status = document.getElementById('connection-status');
        if (status) {
            status.textContent = connected ? '已连接' : '未连接';
            status.className = connected ? 'status-badge online' : 'status-badge offline';
        }
    }

    updateDeviceStatus(data) {
        const roomId = data.room_id;
        const deviceName = data.device;
        const state = data.state;
        
        const room = this.app.rooms.find(r => r.id === roomId);
        if (room) {
            const device = room.devices.find(d => d.name === deviceName);
            if (device) {
                device.state = state;
                
                // If trigger device, just update the status text without re-rendering
                if (deviceName === 'trigger') {
                    this.app.deviceController.updateTriggerDeviceStatus(roomId, state);
                } else {
                    // If the room is currently selected, update the display
                    const selectedBtn = document.querySelector('.room-btn.active');
                    if (selectedBtn && parseInt(selectedBtn.dataset.room) === roomId) {
                        this.app.roomManager.updateRoomDetailsDisplay(room);
                    }
                }
            }
        }
    }

    async shutdownSystem() {
        try {
            // 立即显示关机遮罩层，不等待服务器响应
            this.app.uiManager.showShutdownOverlay();

            const response = await fetch('/api/system/shutdown', {
                method: 'POST'
            });

            const result = await response.json();

            if (!result.success) {
                // 如果关机失败，移除遮罩层并显示错误
                const overlay = document.getElementById('shutdown-overlay');
                if (overlay) {
                    overlay.remove();
                }
                this.app.uiManager.showToast(`关机失败: ${result.error}`, 'error');
            }
        } catch (error) {
            // 如果网络错误，移除遮罩层并显示错误
            const overlay = document.getElementById('shutdown-overlay');
            if (overlay) {
                overlay.remove();
            }
            this.app.uiManager.showToast('关机失败: 网络错误', 'error');
        }
    }

    toggleBroadcastTrigger(enabled) {
        this.app.socket.emit('broadcast_trigger', { enabled: enabled });
    }

    toggleBroadcastAudio(enabled) {
        this.app.socket.emit('broadcast_audio', { enabled: enabled });
    }
}