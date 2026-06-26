export default class TriggerManager {
    constructor(app) {
        this.app = app;
        this.refreshInterval = null;
        this.refreshIntervalTime = 100; // 0.1秒刷新一次
        this.globalRefreshInterval = null;
        this.globalRefreshIntervalTime = 500; // 0.5秒刷新一次所有房间
    }

    /**
     * 添加触发任务
     * @param {number} deviceId - 设备ID
     * @param {number} count - 触发次数
     */
    async addTrigger(deviceId, count) {
        try {
            const response = await fetch(`/api/trigger/${deviceId}/add`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ count })
            });

            const data = await response.json();
            
            if (data.success) {
                return true;
            } else {
                console.error('[TriggerManager] 添加触发任务失败:', data.error);
                return false;
            }
        } catch (error) {
            console.error('[TriggerManager] 添加触发任务异常:', error);
            return false;
        }
    }

    /**
     * 清空触发任务
     * @param {number} deviceId - 设备ID
     */
    async clearTrigger(deviceId) {
        try {
            const response = await fetch(`/api/trigger/${deviceId}/clear`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();
            
            if (data.success) {
                return true;
            } else {
                console.error('[TriggerManager] 清空触发任务失败:', data.error);
                return false;
            }
        } catch (error) {
            console.error('[TriggerManager] 清空触发任务异常:', error);
            return false;
        }
    }

    /**
     * 获取设备触发状态
     * @param {number} deviceId - 设备ID
     */
    async getDeviceStatus(deviceId) {
        try {
            const response = await fetch(`/api/trigger/${deviceId}/status`);
            const data = await response.json();
            
            if (data.success) {
                return data.status;
            } else {
                console.error('[TriggerManager] 获取设备状态失败:', data.error);
                return null;
            }
        } catch (error) {
            console.error('[TriggerManager] 获取设备状态异常:', error);
            return null;
        }
    }

    /**
     * 获取房间所有触发装置的状态
     * @param {number} roomId - 房间ID
     */
    async getRoomTriggerStatus(roomId) {
        try {
            const response = await fetch(`/api/rooms/${roomId}/trigger_status`);
            const data = await response.json();
            
            if (data.success) {
                return data.devices;
            } else {
                console.error('[TriggerManager] 获取房间触发状态失败:', data.error);
                return [];
            }
        } catch (error) {
            console.error('[TriggerManager] 获取房间触发状态异常:', error);
            return [];
        }
    }

    /**
     * 开始刷新触发状态
     * @param {number} roomId - 房间ID
     * @param {function} callback - 回调函数
     */
    startRefresh(roomId, callback) {
        this.stopRefresh();
        
        // 立即执行一次
        this._refreshRoomTriggerStatus(roomId, callback);
        
        // 设置定时刷新
        this.refreshInterval = setInterval(() => {
            this._refreshRoomTriggerStatus(roomId, callback);
        }, this.refreshIntervalTime);
    }

    /**
     * 停止刷新触发状态
     */
    stopRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * 刷新房间触发状态
     * @param {number} roomId - 房间ID
     * @param {function} callback - 回调函数
     */
    async _refreshRoomTriggerStatus(roomId, callback) {
        const devices = await this.getRoomTriggerStatus(roomId);
        
        if (callback && typeof callback === 'function') {
            callback(devices);
        }
    }

    /**
     * 更新设备触发计数到内存
     * @param {number} roomId - 房间ID
     * @param {object} devices - 设备状态数组
     */
    updateRoomTriggerCounts(roomId, devices) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        devices.forEach(device => {
            const deviceName = device.name;
            const remainingCount = device.remaining_count;
            const state = device.state;

            if (deviceName === 'trigger') {
                room.triggerCount = remainingCount;
            } else if (deviceName.startsWith('prog')) {
                if (!room.triggerCounts) {
                    room.triggerCounts = {};
                }
                room.triggerCounts[deviceName] = remainingCount;
            }

            // 更新房间设备对象中的 trigger_remaining_count 字段，以便左侧显示
            if (room.devices) {
                const roomDevice = room.devices.find(d => d.name === deviceName);
                if (roomDevice) {
                    roomDevice.trigger_remaining_count = remainingCount;
                }
            }

            // 更新进度条
            this.app.deviceController.updateTriggerProgress(roomId, deviceName);
        });
        
        // 计算总剩余次数用于日志
        let totalRemaining = 0;
        if (room.devices) {
            room.devices.forEach(device => {
                if (device.trigger_remaining_count !== undefined) {
                    totalRemaining += device.trigger_remaining_count;
                }
            });
        }
        console.log(`[TriggerManager] 更新房间${roomId}(${room.name})触发计数, 总剩余: ${totalRemaining}`);
        
        // 更新左侧房间按钮的触发数显示
        this.app.roomManager.updateRoomTriggerCount(room);
    }

    /**
     * 开始全局刷新所有房间的触发状态
     */
    startGlobalRefresh() {
        this.stopGlobalRefresh();
        
        console.log('[TriggerManager] 启动全局触发状态刷新');
        
        // 立即执行一次
        this._refreshAllRoomsTriggerStatus();
        
        // 设置定时刷新
        this.globalRefreshInterval = setInterval(() => {
            this._refreshAllRoomsTriggerStatus();
        }, this.globalRefreshIntervalTime);
    }

    /**
     * 停止全局刷新
     */
    stopGlobalRefresh() {
        if (this.globalRefreshInterval) {
            clearInterval(this.globalRefreshInterval);
            this.globalRefreshInterval = null;
        }
    }

    /**
     * 刷新所有房间的触发状态
     */
    async _refreshAllRoomsTriggerStatus() {
        const allRooms = this.app.rooms;
        
        if (allRooms.length > 0) {
            console.log(`[TriggerManager] 全局刷新 ${allRooms.length} 个房间的触发状态`);
        }
        
        const promises = allRooms.map(room =>
            this.getRoomTriggerStatus(room.id)
                .then(devices => ({ roomId: room.id, devices }))
                .catch(error => {
                    console.error(`[TriggerManager] 刷新房间${room.id}触发状态失败:`, error);
                    return null;
                })
        );
        
        const results = await Promise.all(promises);
        
        results.forEach(result => {
            if (result && result.devices && result.devices.length > 0) {
                this.updateRoomTriggerCounts(result.roomId, result.devices);
            }
        });
    }
}
