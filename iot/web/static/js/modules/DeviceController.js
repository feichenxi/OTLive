export default class DeviceController {
    constructor(app) {
        this.app = app;
    }

    controlDevice(roomId, deviceName, action) {
        this.app.socket.emit('control_device', {
            room_id: roomId,
            device: deviceName,
            action: action
        });
    }

    openTriggerOnDurationDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const currentDuration = room.trigger_on_duration !== undefined ? room.trigger_on_duration : 3;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>开时间设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field">
                        <label for="duration-input">开时间 (1-60秒)</label>
                        <div class="volume-slider-container">
                            <input type="range" id="duration-input" min="1" max="60" value="${currentDuration}" class="volume-slider">
                            <span id="duration-value">${currentDuration}秒</span>
                        </div>
                    </div>
                </div>
                <div class="settings-dialog-footer">
                    <button class="dialog-btn dialog-btn-cancel" id="dialog-cancel-btn">取消</button>
                    <button class="dialog-btn dialog-btn-save" id="dialog-save-btn">保存</button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        const durationInput = document.getElementById('duration-input');
        const durationValue = document.getElementById('duration-value');

        durationInput.addEventListener('input', (e) => {
            durationValue.textContent = `${e.target.value}秒`;
        });

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', () => {
            const newDuration = parseInt(durationInput.value);
            
            this.app.socket.emit('update_trigger_device_config', {
                room_id: roomId,
                trigger_on_duration: newDuration,
                trigger_off_duration: room.trigger_off_duration !== undefined ? room.trigger_off_duration : 1
            });
            
            room.trigger_on_duration = newDuration;
            
            dialog.remove();
            this.app.roomManager.updateRoomDetailsDisplay(room);
        });
    }

    openTriggerOffDurationDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const currentDuration = room.trigger_off_duration !== undefined ? room.trigger_off_duration : 1;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>关时间设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field">
                        <label for="duration-input">关时间 (0-60秒，0表示不关闭)</label>
                        <div class="volume-slider-container">
                            <input type="range" id="duration-input" min="0" max="60" value="${currentDuration}" class="volume-slider">
                            <span id="duration-value">${currentDuration}秒</span>
                        </div>
                    </div>
                </div>
                <div class="settings-dialog-footer">
                    <button class="dialog-btn dialog-btn-cancel" id="dialog-cancel-btn">取消</button>
                    <button class="dialog-btn dialog-btn-save" id="dialog-save-btn">保存</button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        const durationInput = document.getElementById('duration-input');
        const durationValue = document.getElementById('duration-value');

        durationInput.addEventListener('input', (e) => {
            durationValue.textContent = `${e.target.value}秒`;
        });

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', () => {
            const newDuration = parseInt(durationInput.value);

            this.app.socket.emit('update_trigger_device_config', {
                room_id: roomId,
                trigger_on_duration: room.trigger_on_duration !== undefined ? room.trigger_on_duration : 3,
                trigger_off_duration: newDuration
            });

            room.trigger_off_duration = newDuration;

            dialog.remove();
            this.app.roomManager.updateRoomDetailsDisplay(room);
        });
    }

    async openTriggerProgramDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        this.currentEditingRoomId = roomId;

        const currentOnDuration = room.trigger_on_duration !== undefined ? room.trigger_on_duration : 3;
        const currentOffDuration = room.trigger_off_duration !== undefined ? room.trigger_off_duration : 1;

        // 获取未知礼物配置
        let unknownGiftEnabled = false;
        let unknownGiftThreshold = 10;
        try {
            const response = await fetch(`/api/rooms/${roomId}/unknown_gift_config`);
            const data = await response.json();
            if (data.success) {
                unknownGiftEnabled = data.enabled || false;
                unknownGiftThreshold = data.threshold || 10;
            }
        } catch (e) {
            console.error('获取未知礼物配置失败:', e);
        }

        // 获取空闲超时配置
        let idleTimeoutEnabled = false;
        let idleTimeoutSeconds = 60;
        let idleTimeoutCount = 1;
        try {
            const response = await fetch(`/api/rooms/${roomId}/idle_timeout_config`);
            const data = await response.json();
            if (data.success) {
                idleTimeoutEnabled = data.enabled || false;
                idleTimeoutSeconds = data.timeout_seconds || 60;
                idleTimeoutCount = data.trigger_count || 1;
            }
        } catch (e) {
            console.error('获取空闲超时配置失败:', e);
        }

        // 生成触发次数选项
        let triggerCountOptions = '';
        for (let i = 1; i <= 100; i++) {
            triggerCountOptions += `<option value="${i}">${i}次</option>`;
        }

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <style>
                #gift-trigger-list::-webkit-scrollbar {
                    width: 8px;
                }
                #gift-trigger-list::-webkit-scrollbar-track {
                    background: rgba(255,255,255,0.05);
                    border-radius: 4px;
                }
                #gift-trigger-list::-webkit-scrollbar-thumb {
                    background: rgba(255,255,255,0.3);
                    border-radius: 4px;
                }
                #gift-trigger-list::-webkit-scrollbar-thumb:hover {
                    background: rgba(255,255,255,0.5);
                }
                .duration-row {
                    display: flex;
                    gap: 20px;
                    margin-bottom: 15px;
                }
                .duration-input-group {
                    flex: 1;
                }
                .duration-input-group label {
                    display: block;
                    margin-bottom: 8px;
                    font-size: 14px;
                    color: rgba(255,255,255,0.9);
                }
                .duration-input-group input {
                    width: 100%;
                    padding: 10px;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                }
                .unknown-gift-section {
                    margin-top: 20px;
                    padding: 15px;
                    background: rgba(255,255,255,0.03);
                    border-radius: 4px;
                    border: 1px solid rgba(255,255,255,0.1);
                }
                .unknown-gift-row {
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    margin-bottom: 10px;
                }
                .checkbox-label {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    font-size: 14px;
                    color: rgba(255,255,255,0.9);
                }
                .checkbox-label input[type="checkbox"] {
                    width: 18px;
                    height: 18px;
                    cursor: pointer;
                }
                .threshold-row {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding-left: 26px;
                }
                .threshold-row label {
                    font-size: 14px;
                    color: rgba(255,255,255,0.7);
                }
                .threshold-row input {
                    width: 80px;
                    padding: 8px;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                }
                .threshold-row span {
                    font-size: 14px;
                    color: rgba(255,255,255,0.7);
                }
            </style>
            <div class="settings-dialog" style="max-width: 600px;">
                <div class="settings-dialog-header">
                    <h3>主触发装置编程设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <!-- 单次开/关时间 - 标题和输入框同行 -->
                    <div class="duration-row" style="display: flex; gap: 20px; margin-bottom: 15px; align-items: center;">
                        <div class="duration-input-group" style="flex: 1; display: flex; align-items: center; gap: 8px;">
                            <label for="on-duration-input" style="margin: 0; white-space: nowrap;">单次开(秒)</label>
                            <input type="number" id="on-duration-input" min="0.1" max="60" step="0.1" value="${currentOnDuration}" style="flex: 1; padding: 6px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff;">
                        </div>
                        <div class="duration-input-group" style="flex: 1; display: flex; align-items: center; gap: 8px;">
                            <label for="off-duration-input" style="margin: 0; white-space: nowrap;">单次关(秒)</label>
                            <input type="number" id="off-duration-input" min="0" max="60" step="0.1" value="${currentOffDuration}" style="flex: 1; padding: 6px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff;">
                        </div>
                    </div>
                    
                    <!-- 未知礼物配置 - 始终显示价值输入框 -->
                    <div class="unknown-gift-row" style="display: flex; gap: 15px; margin-bottom: 15px; align-items: center; background: rgba(255,255,255,0.03); padding: 10px 12px; border-radius: 4px;">
                        <label class="wechat-checkbox-label" style="display: flex; align-items: center; gap: 8px; margin: 0; white-space: nowrap; cursor: pointer;">
                            <input type="checkbox" id="unknown-gift-enabled" class="wechat-checkbox" ${unknownGiftEnabled ? 'checked' : ''}>
                            <span class="wechat-checkbox-icon"></span>
                            <span class="wechat-checkbox-text">未知礼物触发</span>
                        </label>
                        <div class="threshold-inline" style="display: flex; align-items: center; gap: 8px;">
                            <span style="color: rgba(255,255,255,0.7);">价值</span>
                            <input type="number" id="unknown-gift-threshold" min="1" value="${unknownGiftThreshold}" style="width: 60px; padding: 4px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff;">
                            <span style="color: rgba(255,255,255,0.7);">触发1次</span>
                        </div>
                    </div>
                    
                    <!-- 空闲超时触发配置 -->
                    <div class="idle-timeout-row" style="display: flex; gap: 15px; margin-bottom: 15px; align-items: center; background: rgba(255,255,255,0.03); padding: 10px 12px; border-radius: 4px;">
                        <label class="wechat-checkbox-label" style="display: flex; align-items: center; gap: 8px; margin: 0; white-space: nowrap; cursor: pointer;">
                            <input type="checkbox" id="idle-timeout-enabled" class="wechat-checkbox" ${idleTimeoutEnabled ? 'checked' : ''}>
                            <span class="wechat-checkbox-icon"></span>
                            <span class="wechat-checkbox-text">空闲超时触发</span>
                        </label>
                        <div class="timeout-inline" style="display: flex; align-items: center; gap: 8px;">
                            <span style="color: rgba(255,255,255,0.7);">超时</span>
                            <input type="number" id="idle-timeout-seconds" min="1" max="3600" value="${idleTimeoutSeconds}" style="width: 70px; padding: 4px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff;">
                            <span style="color: rgba(255,255,255,0.7);">秒后触发</span>
                            <input type="number" id="idle-timeout-count" min="1" max="100" value="${idleTimeoutCount}" style="width: 60px; padding: 4px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff;">
                            <span style="color: rgba(255,255,255,0.7);">次</span>
                        </div>
                    </div>
                    
                    <div class="trigger-settings-footer" style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: flex-end; gap: 10px;">
                        <button class="dialog-btn dialog-btn-cancel" id="dialog-cancel-btn">取消</button>
                        <button class="dialog-btn dialog-btn-save" id="dialog-save-btn">保存</button>
                    </div>
                    <div class="gift-trigger-section" style="margin-top: 25px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <h4 style="margin-bottom: 15px; color: rgba(255,255,255,0.9);">礼物触发设置</h4>
                        <div id="gift-trigger-list" style="height: 150px; overflow-y: auto; margin-bottom: 15px; padding-right: 5px; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.3) rgba(255,255,255,0.05);">
                            <!-- 礼物触发配置列表将动态生成 -->
                        </div>
                        <div class="gift-trigger-add-row" style="display: flex; gap: 10px; align-items: center;">
                            <select id="gift-select" class="prog-device-event-select" style="flex: 2;">
                                <option value="">选择礼物...</option>
                            </select>
                            <input type="number" id="gift-trigger-count" class="prog-device-event-select" style="flex: 1;" min="1" max="100" value="1">
                            <button class="device-btn" id="add-gift-trigger-btn" style="flex: 0 0 35px; padding: 8px;">+</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        const onDurationInput = document.getElementById('on-duration-input');
        const offDurationInput = document.getElementById('off-duration-input');
        const unknownGiftEnabledCheckbox = document.getElementById('unknown-gift-enabled');
        const unknownGiftThresholdInput = document.getElementById('unknown-gift-threshold');
        const idleTimeoutEnabledCheckbox = document.getElementById('idle-timeout-enabled');
        const idleTimeoutSecondsInput = document.getElementById('idle-timeout-seconds');
        const idleTimeoutCountInput = document.getElementById('idle-timeout-count');

        // 先加载礼物列表和礼物触发配置
        (async () => {
            await this.loadGiftOptions(roomId);
            await this.loadGiftTriggerConfigs(roomId);
        })();

        // 添加礼物触发配置
        document.getElementById('add-gift-trigger-btn').addEventListener('click', () => {
            this.addGiftTriggerConfig(roomId);
        });

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', async () => {
            const newOnDuration = parseFloat(onDurationInput.value);
            const newOffDuration = parseFloat(offDurationInput.value);
            const newUnknownGiftEnabled = unknownGiftEnabledCheckbox.checked;
            const newUnknownGiftThreshold = parseInt(unknownGiftThresholdInput.value) || 10;
            const newIdleTimeoutEnabled = idleTimeoutEnabledCheckbox.checked;
            const newIdleTimeoutSeconds = parseInt(idleTimeoutSecondsInput.value) || 60;
            const newIdleTimeoutCount = parseInt(idleTimeoutCountInput.value) || 1;

            // 保存主触发装置配置
            this.app.socket.emit('update_trigger_device_config', {
                room_id: roomId,
                trigger_on_duration: newOnDuration,
                trigger_off_duration: newOffDuration
            });

            // 保存未知礼物配置
            try {
                await fetch(`/api/rooms/${roomId}/unknown_gift_config`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        enabled: newUnknownGiftEnabled,
                        threshold: newUnknownGiftThreshold
                    })
                });
            } catch (e) {
                console.error('保存未知礼物配置失败:', e);
            }

            // 保存空闲超时配置
            try {
                await fetch(`/api/rooms/${roomId}/idle_timeout_config`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        enabled: newIdleTimeoutEnabled,
                        timeout_seconds: newIdleTimeoutSeconds,
                        trigger_count: newIdleTimeoutCount
                    })
                });
            } catch (e) {
                console.error('保存空闲超时配置失败:', e);
            }

            room.trigger_on_duration = newOnDuration;
            room.trigger_off_duration = newOffDuration;

            dialog.remove();
            this.app.roomManager.updateRoomDetailsDisplay(room);
        });
    }

    async loadGiftOptions(roomId) {
        try {
            // 加载所有已配置的礼物（包括主触发装置和可编程设备的）
            const configResponse = await fetch(`/api/rooms/${roomId}/gift_triggers`);
            const configData = await configResponse.json();
            const configuredGifts = configData.success ? configData.configs.map(c => c.gift_name) : [];
            
            // 加载所有礼物列表，不过滤任何礼物
            const response = await fetch('/api/gifts');
            const data = await response.json();
            if (data.success) {
                const giftSelect = document.getElementById('gift-select');
                // 按ID从小到大排序
                const sortedGifts = data.gifts.sort((a, b) => a.id - b.id);
                sortedGifts.forEach(gift => {
                    // 如果礼物已配置（在任何设备中），则不显示在下拉菜单中
                    if (!configuredGifts.includes(gift.name)) {
                        const option = document.createElement('option');
                        option.value = gift.name;
                        option.textContent = `${gift.id} ~ ${gift.name}【${gift.level} ~ ${gift.value}】`;
                        giftSelect.appendChild(option);
                    }
                });
            }
        } catch (error) {
            console.error('加载礼物列表失败:', error);
        }
    }

    async refreshGiftSelectOptions(roomId) {
        try {
            // 加载所有已配置的礼物（包括主触发装置和可编程设备的）
            const configResponse = await fetch(`/api/rooms/${roomId}/gift_triggers`);
            const configData = await configResponse.json();
            const configuredGifts = configData.success ? configData.configs.map(c => c.gift_name) : [];
            
            // 加载所有礼物列表
            const response = await fetch('/api/gifts');
            const data = await response.json();
            if (data.success) {
                const giftSelect = document.getElementById('gift-select');
                const currentValue = giftSelect.value;
                
                // 清空现有选项，保留第一个默认选项
                while (giftSelect.options.length > 1) {
                    giftSelect.remove(1);
                }
                
                // 按ID从小到大排序
                const sortedGifts = data.gifts.sort((a, b) => a.id - b.id);
                sortedGifts.forEach(gift => {
                    // 如果礼物已配置（在任何设备中），则不显示在下拉菜单中
                    if (!configuredGifts.includes(gift.name)) {
                        const option = document.createElement('option');
                        option.value = gift.name;
                        option.textContent = `${gift.id} ~ ${gift.name}【${gift.level} ~ ${gift.value}】`;
                        giftSelect.appendChild(option);
                    }
                });
                
                // 恢复之前选中的值（如果还在列表中）
                if (currentValue && Array.from(giftSelect.options).some(opt => opt.value === currentValue)) {
                    giftSelect.value = currentValue;
                }
            }
        } catch (error) {
            console.error('刷新礼物列表失败:', error);
        }
    }

    async loadGiftTriggerConfigs(roomId) {
        try {
            console.log('加载礼物触发配置，roomId:', roomId);
            const response = await fetch(`/api/rooms/${roomId}/gift_triggers?device_type=main`);
            const data = await response.json();
            console.log('API返回数据:', data);
            if (data.success) {
                const listContainer = document.getElementById('gift-trigger-list');
                listContainer.innerHTML = '';
                console.log('配置数量:', data.configs.length);
                data.configs.forEach(config => {
                    this.addGiftTriggerRow(config.gift_name, config.trigger_count, config.id, roomId);
                });
            }
        } catch (error) {
            console.error('加载礼物触发配置失败:', error);
        }
    }

    addGiftTriggerRow(giftName, triggerCount, configId = null, roomId = null) {
        const listContainer = document.getElementById('gift-trigger-list');
        const row = document.createElement('div');
        row.className = 'gift-trigger-row';
        row.style.cssText = 'display: flex; gap: 8px; margin-bottom: 10px; align-items: center; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 4px;';
        row.dataset.configId = configId || '';
        row.dataset.giftName = giftName;
        row.dataset.roomId = roomId || '';
        
        // 未知礼物和闲置触发不显示编辑和删除按钮
        const isSpecialGift = giftName === '未知礼物' || giftName === '闲置触发';
        
        row.innerHTML = `
            <span style="flex: 1; color: rgba(255,255,255,0.9); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${giftName}</span>
            <span style="flex: 0.8; color: rgba(255,255,255,0.7); white-space: nowrap;">触发${triggerCount}次</span>
            ${isSpecialGift ? `
                <span style="flex: 0 0 40px;"></span>
                <span style="flex: 0 0 40px;"></span>
            ` : `
                <button class="device-btn edit-gift-trigger" style="flex: 0 0 40px; padding: 4px 6px; background: rgba(100,218,87,0.3); white-space: nowrap; font-size: 0.85em;">编辑</button>
                <button class="device-btn delete-gift-trigger" style="flex: 0 0 40px; padding: 4px 6px; background: rgba(255,100,100,0.3); white-space: nowrap; font-size: 0.85em;">删除</button>
            `}
        `;
        
        // 只有非特殊礼物才绑定编辑和删除事件
        if (!isSpecialGift) {
            row.querySelector('.edit-gift-trigger').addEventListener('click', () => {
                this.editGiftTriggerConfig(configId, giftName, triggerCount);
            });
            
            row.querySelector('.delete-gift-trigger').addEventListener('click', () => {
                this.deleteGiftTriggerConfig(row, configId, roomId);
            });
        }
        
        listContainer.appendChild(row);
    }

    async addGiftTriggerConfig(roomId) {
        const giftSelect = document.getElementById('gift-select');
        const countSelect = document.getElementById('gift-trigger-count');
        
        const giftName = giftSelect.value;
        const triggerCount = parseInt(countSelect.value);
        
        // 检查是否在编辑模式
        const addForm = document.querySelector('.gift-trigger-add-row');
        if (addForm.dataset.editMode === 'true') {
            // 编辑模式下，调用保存编辑方法
            this.saveGiftTriggerEdit(roomId);
            return;
        }
        
        if (!giftName) {
            this.app.uiManager.showToast('请选择礼物', 'warning');
            return;
        }

        try {
            const response = await fetch(`/api/rooms/${roomId}/gift_triggers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    gift_name: giftName,
                    trigger_count: triggerCount,
                    device_type: 'main'
                })
            });
            
            const data = await response.json();
            if (data.success) {
                this.addGiftTriggerRow(giftName, triggerCount, data.config_id, roomId);
                giftSelect.value = '';
                // 刷新礼物下拉菜单，过滤掉刚添加的礼物
                await this.refreshGiftSelectOptions(roomId);
                this.app.uiManager.showToast('添加成功', 'success');
            } else {
                this.app.uiManager.showToast(data.error || '添加失败', 'error');
            }
        } catch (error) {
            console.error('添加礼物触发配置失败:', error);
            this.app.uiManager.showToast('添加失败', 'error');
        }
    }

    editGiftTriggerConfig(configId, giftName, triggerCount) {
        const giftSelect = document.getElementById('gift-select');
        const countSelect = document.getElementById('gift-trigger-count');
        const addBtn = document.getElementById('add-gift-trigger-btn');
        
        // 检查是否已经在编辑模式
        if (document.getElementById('cancel-gift-trigger-edit')) {
            return;
        }
        
        // 保存原始礼物名称到添加表单的data属性中
        const addForm = document.querySelector('.gift-trigger-add-row');
        addForm.dataset.originalGiftName = giftName;
        addForm.dataset.editMode = 'true';
        
        // 填充表单
        countSelect.value = triggerCount;
        
        // 禁用礼物选择下拉框，显示为文本
        giftSelect.style.display = 'none';
        const giftNameDisplay = document.createElement('span');
        giftNameDisplay.id = 'gift-name-display';
        giftNameDisplay.textContent = giftName;
        giftNameDisplay.style.cssText = 'flex: 2; padding: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 4px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';
        giftSelect.parentNode.insertBefore(giftNameDisplay, giftSelect);
        
        // 修改添加按钮为保存按钮
        addBtn.textContent = '保存';
        addBtn.style.cssText = 'flex: 0 0 40px; padding: 4px 6px; background: rgba(100,218,87,0.3); white-space: nowrap; font-size: 0.85em;';
        addBtn.onclick = () => this.saveGiftTriggerEdit(roomId);
        
        // 添加取消编辑按钮
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '取消';
        cancelBtn.className = 'device-btn';
        cancelBtn.style.cssText = 'flex: 0 0 40px; padding: 4px 6px; background: rgba(255,255,255,0.15); white-space: nowrap; font-size: 0.85em;';
        cancelBtn.onclick = () => this.cancelGiftTriggerEdit();
        cancelBtn.id = 'cancel-gift-trigger-edit';
        
        // 在添加按钮后插入取消按钮
        addBtn.parentNode.insertBefore(cancelBtn, addBtn.nextSibling);
        
        // 高亮正在编辑的礼物触发行
        this.highlightEditingGiftTrigger(giftName);
    }

    async saveGiftTriggerEdit(roomId) {
        const addForm = document.querySelector('.gift-trigger-add-row');
        const countSelect = document.getElementById('gift-trigger-count');
        
        const originalGiftName = addForm.dataset.originalGiftName;
        const triggerCount = parseInt(countSelect.value);
        
        try {
            const response = await fetch(`/api/rooms/${roomId}/gift_triggers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    gift_name: originalGiftName,
                    trigger_count: triggerCount
                })
            });
            
            const data = await response.json();
            if (data.success) {
                // 直接更新旧行的显示
                const oldRow = document.querySelector(`.gift-trigger-row[data-gift-name="${originalGiftName}"]`);
                if (oldRow) {
                    oldRow.dataset.configId = data.config_id;
                    const countSpan = oldRow.querySelector('span:nth-child(2)');
                    if (countSpan) countSpan.textContent = `触发${triggerCount}次`;
                    // 更新编辑按钮的点击事件
                    const editBtn = oldRow.querySelector('.edit-gift-trigger');
                    if (editBtn) {
                        editBtn.onclick = () => this.editGiftTriggerConfig(data.config_id, originalGiftName, triggerCount);
                    }
                }
                // 取消编辑模式，但保持窗口打开
                this.cancelGiftTriggerEdit();
                // 刷新礼物下拉菜单（过滤已配置的礼物）
                await this.refreshGiftSelectOptions(roomId);
                this.app.uiManager.showToast('修改成功', 'success');
            } else {
                this.app.uiManager.showToast(data.error || '修改失败', 'error');
            }
        } catch (error) {
            console.error('修改礼物触发配置失败:', error);
            this.app.uiManager.showToast('修改失败', 'error');
        }
    }

    cancelGiftTriggerEdit() {
        const addForm = document.querySelector('.gift-trigger-add-row');
        const giftSelect = document.getElementById('gift-select');
        const countSelect = document.getElementById('gift-trigger-count');
        const addBtn = document.getElementById('add-gift-trigger-btn');
        const cancelBtn = document.getElementById('cancel-gift-trigger-edit');
        
        // 清除编辑模式
        if (addForm) {
            delete addForm.dataset.originalGiftName;
            delete addForm.dataset.editMode;
        }
        
        // 重置表单
        countSelect.value = '1';
        
        // 恢复礼物选择下拉框
        const giftNameDisplay = document.getElementById('gift-name-display');
        if (giftNameDisplay) {
            giftNameDisplay.remove();
        }
        giftSelect.style.display = '';
        giftSelect.value = '';
        
        // 恢复添加按钮
        addBtn.textContent = '+';
        addBtn.style.cssText = 'flex: 0 0 35px; padding: 8px;';
        addBtn.onclick = () => this.addGiftTriggerConfig(this.currentEditingRoomId);
        
        // 移除取消按钮
        if (cancelBtn) {
            cancelBtn.remove();
        }
        
        // 清除高亮
        document.querySelectorAll('.gift-trigger-row').forEach(row => {
            row.classList.remove('editing');
        });
    }

    highlightEditingGiftTrigger(giftName) {
        const listContainer = document.getElementById('gift-trigger-list');
        listContainer.querySelectorAll('.gift-trigger-row').forEach(row => {
            row.classList.remove('editing');
            if (row.dataset.giftName === giftName) {
                row.classList.add('editing');
                row.style.background = 'rgba(100, 218, 87, 0.15)';
            } else {
                row.style.background = 'rgba(255,255,255,0.03)';
            }
        });
    }

    async deleteGiftTriggerConfig(rowElement, configId, roomId) {
        if (!configId) {
            rowElement.remove();
            return;
        }

        try {
            let url = `/api/gift_triggers/${configId}`;
            if (roomId) {
                url += `?room_id=${roomId}`;
            }
            const response = await fetch(url, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            if (data.success) {
                rowElement.remove();
                this.app.uiManager.showToast('删除成功', 'success');
            } else {
                this.app.uiManager.showToast(data.error || '删除失败', 'error');
            }
        } catch (error) {
            console.error('删除礼物触发配置失败:', error);
            this.app.uiManager.showToast('删除失败', 'error');
        }
    }

    /**
     * 触发设备（添加触发任务）
     * @param {number} roomId - 房间ID
     * @param {string} deviceName - 设备名称
     * @param {number} duration - 触发次数
     */
    async triggerDeviceWithDuration(roomId, deviceName, duration) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const isMainTrigger = deviceName === 'trigger';

        if (isMainTrigger) {
            if (!room.triggerCount) {
                room.triggerCount = 0;
            }
            room.triggerCount += duration;
        } else {
            if (!room.triggerCounts) {
                room.triggerCounts = {};
            }
            if (!room.triggerCounts[deviceName]) {
                room.triggerCounts[deviceName] = 0;
            }
            room.triggerCounts[deviceName] += duration;
        }

        // 获取设备ID
        const device = room.devices.find(d => d.name === deviceName);
        if (!device) {
            console.error('[DeviceController] 设备不存在:', deviceName);
            return;
        }

        // 调用后端API添加触发任务
        const success = await this.app.triggerManager.addTrigger(device.id, duration);
        
        if (success) {
            // 更新进度条显示
            this.updateTriggerProgress(roomId, deviceName);
        } else {
            console.error('[DeviceController] 添加触发任务失败，回滚计数');
            // 回滚计数
            if (isMainTrigger) {
                room.triggerCount -= duration;
            } else {
                room.triggerCounts[deviceName] -= duration;
            }
        }
    }

    /**
     * 清空触发计数
     * @param {number} roomId - 房间ID
     * @param {string} deviceName - 设备名称
     */
    async clearTriggerCount(roomId, deviceName = 'trigger') {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const isMainTrigger = deviceName === 'trigger';

        // 获取设备ID
        const device = room.devices.find(d => d.name === deviceName);
        if (!device) {
            console.error('[DeviceController] 设备不存在:', deviceName);
            return;
        }

        // 调用后端API清空触发任务
        const success = await this.app.triggerManager.clearTrigger(device.id);
        
        if (success) {
            // 清空本地计数
            if (isMainTrigger) {
                room.triggerCount = 0;
            } else {
                if (!room.triggerCounts) {
                    room.triggerCounts = {};
                }
                room.triggerCounts[deviceName] = 0;
            }

            // 关闭设备
            this.controlDevice(roomId, deviceName, 'off');
            this.updateTriggerDeviceStatus(roomId, false, deviceName);

            // 更新进度条显示
            this.updateTriggerProgress(roomId, deviceName);
        }
    }

    /**
     * 更新触发设备状态显示
     * @param {number} roomId - 房间ID
     * @param {boolean} state - 设备状态
     * @param {string} deviceName - 设备名称
     */
    updateTriggerDeviceStatus(roomId, state, deviceName = 'trigger') {
        const statusSpan = document.getElementById(`trigger-status-${roomId}${deviceName === 'trigger' ? '' : '-' + deviceName}`);
        if (statusSpan) {
            statusSpan.textContent = state ? '已打开' : '已关闭';
            const containerDiv = statusSpan.parentElement.parentElement;
            const statusDiv = containerDiv.querySelector('.device-state');
            if (statusDiv) {
                statusDiv.className = `device-state ${state ? 'on' : 'off'}`;
            }
        }
    }

    /**
     * 更新触发进度条
     * @param {number} roomId - 房间ID
     * @param {string} deviceName - 设备名称
     */
    updateTriggerProgress(roomId, deviceName = 'trigger') {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const levelFill = document.getElementById(`trigger-level-${roomId}${deviceName === 'trigger' ? '' : '-' + deviceName}`);
        const levelText = document.getElementById(`trigger-level-text-${roomId}${deviceName === 'trigger' ? '' : '-' + deviceName}`);

        if (levelFill && levelText) {
            const maxCount = 20;
            const count = deviceName === 'trigger' ? room.triggerCount : (room.triggerCounts?.[deviceName] || 0);
            const percentage = (count / maxCount) * 100;
            levelFill.style.width = `${Math.min(percentage, 100)}%`;
            levelText.textContent = count;
        }
    }

    /**
     * 播放蜂鸣测试音
     * @param {number} roomId - 房间ID
     */
    playSpeakerBeep(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (room) {
            const volume = room.intercom_volume ?? 50;
            const frequency = room.speaker_frequency ?? 1000;
            const duration = room.speaker_duration ?? 200;
            
            for (let i = 0; i < 3; i++) {
                setTimeout(() => {
                    this.app.socket.emit('play_speaker_beep', {
                        room_id: roomId,
                        volume: volume / 100,
                        frequency: frequency,
                        duration: duration
                    });
                }, i * 400);
            }
        }
    }
}
