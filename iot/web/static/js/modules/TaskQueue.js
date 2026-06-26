export default class TaskQueue {
    constructor(app) {
        this.app = app;
        this.taskQueue = [];
    }

    /**
     * 添加任务到队列
     * @param {string} type - 任务类型（如'trigger'）
     * @param {number} roomId - 房间ID
     * @param {object} data - 任务数据
     */
    addTaskToQueue(type, roomId, data) {
        const task = {
            id: `${type}_${roomId}_${data.deviceName || 'trigger'}_${Date.now()}`,
            type: type,
            roomId: roomId,
            data: data,
            status: 'active',
            createdAt: Date.now()
        };
        
        // 检查是否已存在相同类型的任务（根据deviceName区分）
        const deviceName = data.deviceName || 'trigger';
        const existingIndex = this.taskQueue.findIndex(t => t.type === type && t.roomId === roomId && t.data.deviceName === deviceName);
        if (existingIndex >= 0) {
            // 更新现有任务
            this.taskQueue[existingIndex] = task;
        } else {
            // 添加新任务
            this.taskQueue.push(task);
        }
        
        this.saveTaskQueue();
        console.log('[TaskQueue] 任务已添加:', task);
    }
    
    /**
     * 从队列中移除任务
     * @param {string} type - 任务类型
     * @param {number} roomId - 房间ID
     * @param {string} deviceName - 设备名称（可选）
     */
    removeTaskFromQueue(type, roomId, deviceName = 'trigger') {
        const index = this.taskQueue.findIndex(t => t.type === type && t.roomId === roomId && t.data.deviceName === deviceName);
        if (index >= 0) {
            const removedTask = this.taskQueue.splice(index, 1)[0];
            this.saveTaskQueue();
            console.log('[TaskQueue] 任务已移除:', removedTask);
        }
    }
    
    /**
     * 更新任务数据
     * @param {string} type - 任务类型
     * @param {number} roomId - 房间ID
     * @param {object} data - 新的任务数据
     */
    updateTaskData(type, roomId, data) {
        const task = this.taskQueue.find(t => t.type === type && t.roomId === roomId);
        if (task) {
            task.data = { ...task.data, ...data };
            this.saveTaskQueue();
        }
    }
    
    /**
     * 获取任务
     * @param {string} type - 任务类型
     * @param {number} roomId - 房间ID
     * @returns {object|null} 任务对象或null
     */
    getTask(type, roomId) {
        return this.taskQueue.find(t => t.type === type && t.roomId === roomId) || null;
    }
    
    /**
     * 保存任务队列到localStorage
     */
    saveTaskQueue() {
        try {
            localStorage.setItem('taskQueue', JSON.stringify(this.taskQueue));
        } catch (e) {
            console.error('[TaskQueue] 保存任务队列失败:', e);
        }
    }
    
    /**
     * 从localStorage加载任务队列
     */
    loadTaskQueue() {
        try {
            const queue = localStorage.getItem('taskQueue');
            if (queue) {
                this.taskQueue = JSON.parse(queue);
                console.log('[TaskQueue] 任务队列已加载:', this.taskQueue.length, '个任务');
            }
        } catch (e) {
            console.error('[TaskQueue] 加载任务队列失败:', e);
            this.taskQueue = [];
        }
    }
    
    /**
     * 恢复所有未完成的任务
     */
    restoreAllTasks() {
        console.log('[TaskQueue] 开始恢复任务队列...');
        
        // 第一步：先强制关闭所有房间的触发装置，确保从关闭状态开始
        console.log('[TaskQueue] 第一步：关闭所有触发装置');
        this.app.rooms.forEach(room => {
            // 关闭主触发装置
            const triggerDevice = room.devices.find(d => d.name === 'trigger');
            if (triggerDevice) {
                console.log('[TaskQueue] 关闭房间', room.id, '的主触发装置');
                this.app.controlDevice(room.id, 'trigger', 'off');
                this.app.deviceController.updateTriggerDeviceStatus(room.id, false);
            }
            
            // 关闭所有副触发装置
            room.devices.forEach(device => {
                if (device.name.startsWith('prog')) {
                    const triggerOffDuration = device.trigger_off_duration !== undefined ? device.trigger_off_duration : 0;
                    if (triggerOffDuration > 0) {
                        console.log('[TaskQueue] 关闭房间', room.id, '的副触发装置:', device.name);
                        this.app.controlDevice(room.id, device.name, 'off');
                        this.app.deviceController.updateTriggerDeviceStatus(room.id, false, device.name);
                    }
                }
            });
        });
        
        // 第二步：延迟200ms后恢复任务，确保所有设备都已关闭
        setTimeout(() => {
            console.log('[TaskQueue] 第二步：开始恢复任务');
            
            this.taskQueue.forEach(task => {
                if (task.status === 'active') {
                    console.log('[TaskQueue] 恢复任务:', task);
                    
                    // 根据任务类型执行不同的恢复逻辑
                    switch (task.type) {
                        case 'trigger':
                            this.restoreTriggerTask(task);
                            break;
                        // 未来可以在这里添加其他任务类型的恢复逻辑
                        default:
                            console.warn('[TaskQueue] 未知任务类型:', task.type);
                    }
                }
            });
        }, 200);
    }
    
    /**
     * 恢复触发装置任务 - 全局独立运行，不受页面状态影响
     * @param {object} task - 任务对象
     */
    restoreTriggerTask(task) {
        const room = this.app.rooms.find(r => r.id === task.roomId);
        if (!room) {
            console.warn('[TaskQueue] 房间不存在，无法恢复任务:', task);
            return;
        }
        
        const deviceName = task.data.deviceName || 'trigger';
        const triggerDevice = room.devices.find(d => d.name === deviceName);
        if (!triggerDevice) {
            console.warn('[TaskQueue] 触发装置不存在，无法恢复任务:', task);
            return;
        }
        
        const isMainTrigger = deviceName === 'trigger';
        
        // 恢复触发计数
        if (isMainTrigger) {
            room.triggerCount = task.data.count || 0;
        } else {
            // 副触发装置的计数管理可以在这里添加
        }
        
        // 恢复触发状态
        if (task.data.isActive) {
            console.log('[TaskQueue] 恢复触发装置状态:', task.roomId, deviceName);
            this.app.controlDevice(task.roomId, deviceName, 'on');
            this.app.deviceController.updateTriggerDeviceStatus(task.roomId, true, deviceName);
        }
    }
}