export default class UIManager {
    constructor(app) {
        this.app = app;
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: ${type === 'error' ? '#ff0000' : type === 'warning' ? '#fee140' : '#4facfe'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showMessageDetail(nickname, content, time) {
        const modal = document.getElementById('message-detail-modal');
        const nicknameEl = document.getElementById('message-detail-nickname');
        const contentEl = document.getElementById('message-detail-content');
        const timeEl = document.getElementById('message-detail-time');
        
        if (nicknameEl) nicknameEl.textContent = nickname;
        if (contentEl) contentEl.textContent = content;
        if (timeEl) timeEl.textContent = time;
        
        if (modal) modal.style.display = 'flex';
    }

    openRoomSettingsDialog(room) {
        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>【${room.name}】设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field inline">
                        <label for="room-name-input">房间名称</label>
                        <input type="text" id="room-name-input" value="${room.name}" placeholder="请输入房间名称">
                    </div>
                    <div class="settings-field inline">
                        <label for="room-sort-input">排序序号</label>
                        <input type="number" id="room-sort-input" value="${room.sort_order !== undefined ? room.sort_order : (room.id || 1)}" min="1" max="99" placeholder="1-99">
                    </div>
                    <div class="settings-field inline">
                        <label for="room-live-url-input">直播地址</label>
                        <input type="text" id="room-live-url-input" value="${room.live_url || ''}" placeholder="请输入直播地址URL">
                    </div>
                    <div class="settings-field inline">
                        <label>启用房间</label>
                        <div class="speaker-switch">
                            <label class="switch">
                                <input type="checkbox" id="room-enabled-input" ${room.enabled !== false ? 'checked' : ''}>
                                <span class="slider"></span>
                            </label>
                        </div>
                        <span class="setting-description">${room.enabled !== false ? '已启用' : '已关闭'}</span>
                    </div>
                </div>
                <div class="settings-dialog-footer">
                    <button class="dialog-btn dialog-btn-cancel" id="dialog-cancel-btn">取消</button>
                    <button class="dialog-btn dialog-btn-save" id="dialog-save-btn">保存</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        const nameInput = document.getElementById('room-name-input');
        const sortInput = document.getElementById('room-sort-input');
        const liveUrlInput = document.getElementById('room-live-url-input');
        const enabledInput = document.getElementById('room-enabled-input');
        const enabledLabel = dialog.querySelector('.setting-description');

        // 滑块切换事件
        enabledInput.addEventListener('change', () => {
            enabledLabel.textContent = enabledInput.checked ? '已启用' : '已关闭';
        });

        // 获取房间当前的直播地址
        fetch(`/api/rooms/${room.id}/live_url`)
            .then(response => response.json())
            .then(data => {
                if (data.live_url) {
                    liveUrlInput.value = data.live_url;
                }
            })
            .catch(error => {
                console.error('获取房间直播地址失败:', error);
            });
        
        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });
        
        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });
        
        document.getElementById('dialog-save-btn').addEventListener('click', async () => {
            const newName = nameInput.value.trim();
            const newSort = parseInt(sortInput.value);
            const newLiveUrl = liveUrlInput.value.trim();
            
            if (!newName) {
                this.showToast('请输入房间名称', 'error');
                return;
            }
            
            if (isNaN(newSort) || newSort < 1 || newSort > 99) {
                this.showToast('请输入1-99之间的排序序号', 'error');
                return;
            }
            
            // Update room name
            this.app.socket.emit('update_room_name', {
                room_id: room.id,
                name: newName
            });
            
            // Update room sort order and adjust all rooms
            const originalSort = room.sort_order;
            room.sort_order = newSort;
            
            // Get all rooms except the current one
            const otherRooms = this.app.rooms.filter(r => r.id !== room.id);
            
            // Adjust sort orders of other rooms to maintain continuity
            otherRooms.forEach(r => {
                if (originalSort !== undefined && newSort > originalSort) {
                    // Moving room down: decrease sort order for rooms between original and new position
                    if (r.sort_order > originalSort && r.sort_order <= newSort) {
                        r.sort_order--;
                    }
                } else if (originalSort !== undefined && newSort < originalSort) {
                    // Moving room up: increase sort order for rooms between new and original position
                    if (r.sort_order >= newSort && r.sort_order < originalSort) {
                        r.sort_order++;
                    }
                } else {
                    // This is a new room or original sort was undefined
                    if (r.sort_order >= newSort) {
                        r.sort_order++;
                    }
                }
            });
            
            // Ensure no duplicate sort orders by sorting and reassigning
            const sortedRooms = [...this.app.rooms].sort((a, b) => {
                const sortA = a.sort_order !== undefined ? a.sort_order : a.id;
                const sortB = b.sort_order !== undefined ? b.sort_order : b.id;
                return sortA - sortB;
            });
            
            // Reassign to ensure absolute continuity
            sortedRooms.forEach((r, index) => {
                r.sort_order = index + 1;
            });
            
            // Send all sort order updates to server
            this.app.rooms.forEach(r => {
                this.app.socket.emit('update_room_sort', {
                    room_id: r.id,
                    sort_order: r.sort_order
                });
            });
            
            // Update room live URL
            this.app.socket.emit('update_room_live_url', {
                room_id: room.id,
                live_url: newLiveUrl
            });
            
            // 立即更新本地房间数据
            const roomIndex = this.app.rooms.findIndex(r => r.id === room.id);
            if (roomIndex !== -1) {
                this.app.rooms[roomIndex].live_url = newLiveUrl;
            }
            
            // Update room enabled status
            const newEnabled = enabledInput.checked;
            const originalEnabled = room.enabled !== false;
            if (newEnabled !== originalEnabled) {
                try {
                    const response = await fetch(`/api/rooms/${room.id}/enabled`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enabled: newEnabled })
                    });
                    const result = await response.json();
                    if (result.success) {
                        room.enabled = newEnabled;
                        if (roomIndex !== -1) {
                            this.app.rooms[roomIndex].enabled = newEnabled;
                        }
                        this.showToast(newEnabled ? '房间已启用' : '房间已关闭', 'success');
                    }
                } catch (error) {
                    console.error('更新房间启用状态失败:', error);
                    this.showToast('更新房间启用状态失败', 'error');
                }
            }
            
            dialog.remove();
        });
        
        nameInput.focus();
    }

    openSystemSettingsDialog() {
        const patrolDialogEnabled = this.app.patrolDialogEnabled || false;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog" style="max-width: 500px; max-height: 90vh; overflow-y: auto;">
                <div class="settings-dialog-header">
                    <h3>系统设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field">
                        <div class="speaker-control-row">
                            <label>巡检对讲</label>
                            <div class="speaker-switch">
                                <label class="switch">
                                    <input type="checkbox" id="patrol-dialog-switch" ${patrolDialogEnabled ? 'checked' : ''}>
                                    <span class="slider"></span>
                                </label>
                            </div>
                            <span class="setting-description">进入房间自动开启对讲，离开自动关闭</span>
                        </div>
                    </div>
                    <div class="settings-field">
                        <div class="speaker-control-row">
                            <label>导出配置</label>
                            <button class="device-btn" id="export-config-btn">下载配置文件</button>
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

        const patrolSwitch = document.getElementById('patrol-dialog-switch');

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', async () => {
            this.app.patrolDialogEnabled = patrolSwitch.checked;
            
            try {
                const patrolResponse = await fetch('/api/system/patrol_dialog', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ enabled: this.app.patrolDialogEnabled })
                });
                
                const patrolResult = await patrolResponse.json();
                if (!patrolResult.success) {
                    this.showToast('保存巡检对讲失败: ' + (patrolResult.error || '未知错误'), 'error');
                    return;
                }

                dialog.remove();
                this.showToast('设置保存成功', 'success');
                
                if (this.app.selectedRoom) {
                    this.app.roomManager.updateRoomDetailsDisplay(this.app.selectedRoom);
                }
            } catch (error) {
                console.error('保存系统设置失败:', error);
                this.showToast('保存失败，请检查网络连接', 'error');
            }
        });

        document.getElementById('export-config-btn').addEventListener('click', () => {
            this.exportConfig();
        });
    }

    openProgConfigDialog(room) {
        const modal = document.getElementById('prog-config-modal');
        const devicesList = document.getElementById('prog-devices-list');
        const roomNameSpan = document.getElementById('prog-config-room-name');
        
        modal.style.display = 'flex';
        devicesList.innerHTML = '<p>加载中...</p>';
        roomNameSpan.textContent = room.name;
        
        Promise.all([
            fetch(`/api/rooms/${room.id}/all_devices`).then(r => r.json()),
            fetch(`/api/gifts`).then(r => r.json()),
            fetch(`/api/rooms/${room.id}/gift_triggers`).then(r => r.json())
        ])
        .then(([roomData, giftData, triggerData]) => {
            const fullRoom = roomData;
            const progDevices = fullRoom.devices.filter(d => d.name.startsWith('prog'));
            const gifts = giftData.success ? giftData.gifts : [];
            // 获取所有已配置的礼物（包括主触发装置和可编程设备的）
            const configuredGifts = triggerData.success ? triggerData.configs.map(c => c.gift_name) : [];
            
            // 按ID从小到大排序
            const sortedGifts = [...gifts].sort((a, b) => a.id - b.id);
            
            devicesList.innerHTML = progDevices.map(device => {
                const triggerOnDuration = device.trigger_on_duration !== undefined ? device.trigger_on_duration : 3;
                const triggerOffDuration = device.trigger_off_duration !== undefined ? device.trigger_off_duration : 0;
                const isEnabled = device.enabled !== undefined ? device.enabled : false;
                let giftEvent = device.gift_event || '';
                let messageTriggerText = '';
                let isMessageTrigger = false;
                
                // 解析gift_event，如果是JSON格式的文字触发
                try {
                    const parsedEvent = JSON.parse(giftEvent);
                    if (parsedEvent && parsedEvent.type === 'msg') {
                        isMessageTrigger = true;
                        messageTriggerText = parsedEvent.text || '';
                    }
                } catch (e) {
                    // 不是JSON格式，保持原样
                }
                
                // 为每个设备生成礼物选项
                // 如果礼物未被配置，或者是当前设备已配置的礼物，则显示
                const deviceGiftOptions = '<option value="">无事件</option>' + 
                    '<option value="__message_trigger__" ' + (isMessageTrigger ? 'selected' : '') + '>0~文字消息触发</option>' +
                    sortedGifts.filter(gift => {
                        return !configuredGifts.includes(gift.name) || gift.name === giftEvent;
                    }).map(gift => `<option value="${gift.name}" ${(!isMessageTrigger && gift.name === giftEvent) ? 'selected' : ''}>${gift.id} ~ ${gift.name}【${gift.level} ~ ${gift.value}】</option>`).join('');
                
                return `
                    <tr data-device="${device.name}">
                        <td>
                            <label class="wechat-checkbox-label">
                                <input type="checkbox" class="wechat-checkbox prog-device-checkbox" ${isEnabled ? 'checked' : ''} data-device="${device.name}">
                                <span class="wechat-checkbox-icon"></span>
                            </label>
                        </td>
                        <td>
                            ${device.pin}
                        </td>
                        <td>
                            <input type="text" class="prog-device-name-input" value="${device.label}" data-device="${device.name}" placeholder="设备名称">
                        </td>
                        <td>
                            <input type="number" class="prog-device-time-input" value="${triggerOnDuration}" min="0" max="999" step="0.1" data-device="${device.name}" data-type="on">
                        </td>
                        <td>
                            <input type="number" class="prog-device-time-input" value="${triggerOffDuration}" min="0" max="999" step="0.1" data-device="${device.name}" data-type="off">
                        </td>
                        <td>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <select class="prog-device-event-select" data-device="${device.name}" style="width: ${isMessageTrigger ? 'calc(100% - 65px)' : '100%'}; min-width: 120px;">
                                    ${deviceGiftOptions}
                                </select>
                                <input type="text" class="prog-device-message-text prog-device-name-input" data-device="${device.name}" 
                                       placeholder="输入触发文字" value="${messageTriggerText}"
                                       style="width: 60px; flex-shrink: 0; display: ${isMessageTrigger ? 'block' : 'none'}; box-sizing: border-box;">
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
            
            progDevices.forEach(device => {
                const eventSelect = document.querySelector(`select[data-device="${device.name}"]`);
                const messageTextInput = document.querySelector(`input.prog-device-message-text[data-device="${device.name}"]`);
                
                // 绑定事件：选择变化时显示/隐藏文字输入框并调整下拉框宽度
                if (eventSelect && messageTextInput) {
                    eventSelect.addEventListener('change', (e) => {
                        if (e.target.value === '__message_trigger__') {
                            messageTextInput.style.display = 'block';
                            eventSelect.style.width = 'calc(100% - 65px)';
                        } else {
                            messageTextInput.style.display = 'none';
                            eventSelect.style.width = '100%';
                        }
                    });
                }
            });
            
            const saveBtn = document.getElementById('prog-config-modal-save');
            const closeBtn = document.getElementById('prog-config-modal-close');
            
            // 移除旧的事件监听器，避免重复绑定
            saveBtn.replaceWith(saveBtn.cloneNode(true));
            closeBtn.replaceWith(closeBtn.cloneNode(true));
            
            // 重新获取按钮引用
            const newSaveBtn = document.getElementById('prog-config-modal-save');
            const newCloseBtn = document.getElementById('prog-config-modal-close');
            
            newSaveBtn.onclick = () => {
                this.saveProgConfig(room, progDevices);
            };
            
            newCloseBtn.onclick = () => {
                modal.style.display = 'none';
            };
        })
        .catch(error => {
            console.error('Error loading prog devices:', error);
            devicesList.innerHTML = '<p>加载失败</p>';
        });
    }

    saveProgConfig(room, progDevices) {
        const config = {};
        const usedGifts = new Map(); // 用于检查重复礼物: gift_name -> device_name
        let hasDuplicate = false; // 标记是否有重复
        
        // 【修复】使用 for...of 循环代替 forEach，以便能正确跳出函数
        for (const device of progDevices) {
            const checkbox = document.querySelector(`input[type="checkbox"][data-device="${device.name}"]`);
            const nameInput = document.querySelector(`input[type="text"][data-device="${device.name}"]`);
            const onInput = document.querySelector(`input[type="number"][data-device="${device.name}"][data-type="on"]`);
            const offInput = document.querySelector(`input[type="number"][data-device="${device.name}"][data-type="off"]`);
            const eventSelect = document.querySelector(`select[data-device="${device.name}"]`);
            const messageTextInput = document.querySelector(`input.prog-device-message-text[data-device="${device.name}"]`);
            
            if (checkbox && nameInput && onInput && offInput && eventSelect) {
                let giftEvent = eventSelect.value;
                const deviceLabel = nameInput.value || device.name;
                
                // 处理文字触发
                if (giftEvent === '__message_trigger__') {
                    const messageText = messageTextInput ? messageTextInput.value.trim() : '';
                    if (!messageText) {
                        this.showToast('请输入文字触发内容', 'error');
                        hasDuplicate = true;
                        break;
                    }
                    // 保存为JSON格式
                    giftEvent = JSON.stringify({ type: 'msg', text: messageText });
                }
                
                // 【新增】检查所有设备（包括未启用的）是否有重复的礼物选择
                if (giftEvent && giftEvent !== '') {
                    // 检查是否是JSON格式的文字触发
                    let isMsgTrigger = false;
                    try {
                        const parsed = JSON.parse(giftEvent);
                        isMsgTrigger = parsed && parsed.type === 'msg';
                    } catch (e) {
                        // 不是JSON格式
                    }
                    
                    // 只有非文字触发的礼物才需要检查重复
                    if (!isMsgTrigger) {
                        if (usedGifts.has(giftEvent)) {
                            const otherDevice = usedGifts.get(giftEvent);
                            console.log('发现重复礼物:', giftEvent, '设备:', otherDevice, '和', deviceLabel);
                            this.showToast(`保存失败：礼物"${giftEvent}"已被"${otherDevice}"和"${deviceLabel}"同时选择，一个礼物只能触发一个设备`, 'error');
                            hasDuplicate = true;
                            break; // 跳出循环
                        }
                        usedGifts.set(giftEvent, deviceLabel);
                    }
                }
                
                config[device.name] = {
                    enabled: checkbox.checked,
                    label: nameInput.value,
                    trigger_on_duration: parseFloat(onInput.value) || 3,
                    trigger_off_duration: parseFloat(offInput.value) || 0,
                    gift_event: giftEvent
                };
            }
        }
        
        // 如果发现重复，直接返回，不执行保存
        if (hasDuplicate) {
            console.log('检测到重复礼物或缺少文字触发内容，取消保存');
            return;
        }
        
        console.log('保存配置:', config);
        
        fetch(`/api/rooms/${room.id}/prog_devices`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        })
        .then(response => response.json())
        .then(data => {
            console.log('响应数据:', data);
            if (data.success) {
                // 先关闭弹窗
                const modal = document.getElementById('prog-config-modal');
                if (modal) {
                    modal.style.display = 'none';
                    console.log('弹窗已关闭，display:', modal.style.display);
                } else {
                    console.log('弹窗元素不存在');
                }
                this.showToast('可编程设备配置已保存', 'success');
                // 延迟刷新房间列表，避免阻塞UI
                setTimeout(() => {
                    this.app.loadRooms();
                }, 100);
            } else {
                this.showToast('保存失败: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.log('保存错误:', error);
            this.showToast('保存失败: ' + error.message, 'error');
        });
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(err => {
                console.error(`Error attempting to enable fullscreen: ${err.message}`);
            });
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
        }
    }

    exportConfig() {
        window.location.href = '/api/system/config/zip';
    }

    objectToYaml(obj, indent = 0, isListItem = false) {
        let yaml = '';
        const spaces = ' '.repeat(indent);

        if (Array.isArray(obj)) {
            obj.forEach((item, index) => {
                yaml += `${spaces}- `;
                if (typeof item === 'object' && item !== null) {
                    yaml += this.objectToYaml(item, indent + 2, true);
                } else {
                    yaml += `${this.formatValue(item)}\n`;
                }
            });
        } else if (typeof obj === 'object' && obj !== null) {
            const keys = Object.keys(obj);
            keys.forEach((key, index) => {
                const value = obj[key];
                if (value === null || value === undefined) return;

                if (isListItem && index === 0) {
                    yaml += `${key}: `;
                } else {
                    yaml += `${spaces}${key}: `;
                }

                if (typeof value === 'object' && !Array.isArray(value)) {
                    yaml += '\n' + this.objectToYaml(value, indent + 2, false);
                } else if (Array.isArray(value)) {
                    yaml += '\n' + this.objectToYaml(value, indent + 2, false);
                } else {
                    yaml += `${this.formatValue(value)}\n`;
                }
            });
        } else {
            yaml += `${this.formatValue(obj)}\n`;
        }

        return yaml;
    }

    formatValue(value) {
        if (typeof value === 'string') {
            return `"${value}"`;
        }
        return value;
    }

    async requestFullscreenWithDelay(element, delay = 0) {
        try {
            if (element.requestFullscreen) {
                await element.requestFullscreen();
            } else if (element.webkitRequestFullscreen) {
                await element.webkitRequestFullscreen();
            } else if (element.msRequestFullscreen) {
                await element.msRequestFullscreen();
            }
        } catch (err) {
            console.error('全屏失败:', err);
        }
    }

    validateIP(ip) {
        const ipPattern = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
        if (!ipPattern.test(ip)) {
            return false;
        }
        
        const parts = ip.split('.');
        for (let i = 0; i < 4; i++) {
            const num = parseInt(parts[i]);
            if (num < 0 || num > 255) {
                return false;
            }
        }
        
        return true;
    }

    showShutdownOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'shutdown-overlay';
        overlay.className = 'shutdown-overlay';
        overlay.innerHTML = `
            <div class="shutdown-content">
                <div class="shutdown-message" id="shutdown-message">正在关机...</div>
                <div class="shutdown-progress" id="shutdown-progress"></div>
            </div>
        `;
        document.body.appendChild(overlay);

        let countdown = 30;
        const message = document.getElementById('shutdown-message');
        
        setTimeout(() => {
            if (message) {
                message.innerHTML = `在${countdown}秒后，可安全的拔掉电源...`;
                
                const countdownInterval = setInterval(() => {
                    countdown--;
                    if (countdown > 0) {
                        message.innerHTML = `在${countdown}秒后，可安全的拔掉电源...`;
                    } else {
                        clearInterval(countdownInterval);
                        message.innerHTML = '已关机，可以安全的拔掉电源了<br>如需重新使用请重插电源...';
                    }
                }, 1000);
            }
        }, 5000);
    }

    updateShutdownProgress(data) {
        const progressDiv = document.getElementById('shutdown-progress');
        if (progressDiv) {
            progressDiv.innerHTML = `<div class="progress-step">${data.message}</div>`;
        }
    }

    openRoomAIConfigDialog(room) {
        const modal = document.getElementById('room-ai-config-modal');
        const roomNameSpan = document.getElementById('room-ai-config-room-name');
        const aiPromptInput = document.getElementById('room-ai-prompt-input');
        const voiceTextInput = document.getElementById('room-voice-text-input');
        const thankValueInput = document.getElementById('room-thank-value');
        const voiceSampleStatus = document.getElementById('room-voice-sample-status');
        const voiceCloneStatus = document.getElementById('room-voice-clone-status');
        const uploadBtn = document.getElementById('room-upload-voice-btn');
        const cloneBtn = document.getElementById('room-clone-voice-btn');
        const fileInput = document.getElementById('room-voice-sample-input');
        const aiThankSwitch = document.getElementById('room-ai-thank-switch');
        const aiThankHint = document.getElementById('room-ai-thank-hint');
        
        modal.style.display = 'flex';
        roomNameSpan.textContent = room.name;
        
        aiPromptInput.value = '';
        voiceTextInput.value = '';
        thankValueInput.value = '';
        voiceSampleStatus.textContent = '加载中...';
        voiceCloneStatus.textContent = '加载中...';
        cloneBtn.disabled = true;
        aiThankSwitch.checked = false;
        aiThankSwitch.disabled = true;
        aiThankHint.style.display = 'inline';
        
        let isVoiceCloned = false;
        let hasAiPrompt = false;
        
        const updateThankSwitchState = (cloned, hasPrompt) => {
            isVoiceCloned = cloned;
            if (hasPrompt !== undefined) hasAiPrompt = hasPrompt;
            
            if (isVoiceCloned && hasAiPrompt) {
                aiThankSwitch.disabled = false;
                aiThankHint.style.display = 'none';
            } else {
                aiThankSwitch.disabled = true;
                aiThankHint.style.display = 'inline';
                if (!isVoiceCloned && !hasAiPrompt) {
                    aiThankHint.textContent = '请先完成音频复刻并填写主播介绍，才能启用AI答谢';
                } else if (!isVoiceCloned) {
                    aiThankHint.textContent = '请先完成音频复刻，才能启用AI答谢';
                } else {
                    aiThankHint.textContent = '请先填写主播介绍（AI提示词），才能启用AI答谢';
                }
            }
        };
        
        fetch(`https://live.hzjt.com/api/upload_voice.php?action=get&room=${room.ip}&license_id=${this.app.licenseId || 0}`)
            .then(response => response.json())
            .then(data => {
                if (data.code === 0 && data.data) {
                    const voiceData = data.data;
                    aiPromptInput.value = voiceData.ai_prompt || '';
                    voiceTextInput.value = voiceData.voice_text || '';
                    thankValueInput.value = voiceData.thank_value !== undefined ? voiceData.thank_value : 0;
                    
                    hasAiPrompt = !!(voiceData.ai_prompt && voiceData.ai_prompt.trim());
                    
                    if (voiceData.voice_sample_url) {
                        voiceSampleStatus.innerHTML = `<a href="${voiceData.voice_sample_url}" target="_blank" style="color: #4caf50;">${voiceData.voice_sample_url}</a>`;
                        cloneBtn.disabled = false;
                    } else if (voiceData.voice_sample) {
                        voiceSampleStatus.textContent = voiceData.voice_sample;
                        cloneBtn.disabled = false;
                    } else {
                        voiceSampleStatus.textContent = '未上传';
                        cloneBtn.disabled = true;
                    }
                    
                    let isCloned = false;
                    if (voiceData.voice_id && voiceData.voice_id !== 'None') {
                        voiceCloneStatus.textContent = '已复刻';
                        voiceCloneStatus.style.color = '#4caf50';
                        cloneBtn.textContent = '重新复刻';
                        isCloned = true;
                    } else if (voiceData.voice_status === 2) {
                        voiceCloneStatus.textContent = '已复刻';
                        voiceCloneStatus.style.color = '#4caf50';
                        cloneBtn.textContent = '重新复刻';
                        isCloned = true;
                    } else if (voiceData.voice_status === 1) {
                        voiceCloneStatus.textContent = '复刻中...';
                        voiceCloneStatus.style.color = '#ff9800';
                        cloneBtn.disabled = true;
                        isCloned = false;
                    } else if (voiceData.voice_status === 3) {
                        voiceCloneStatus.textContent = `复刻失败: ${voiceData.voice_error || '未知错误'}`;
                        voiceCloneStatus.style.color = '#f44336';
                        cloneBtn.disabled = false;
                        isCloned = false;
                    } else {
                        voiceCloneStatus.textContent = '未复刻';
                        voiceCloneStatus.style.color = '';
                        cloneBtn.textContent = '开始复刻';
                        isCloned = false;
                    }
                    
                    updateThankSwitchState(isCloned);
                    aiThankSwitch.checked = Number(voiceData.ai_thank_enabled) === 1;
                } else {
                    voiceSampleStatus.textContent = '未上传';
                    voiceCloneStatus.textContent = '未复刻';
                    cloneBtn.disabled = true;
                    updateThankSwitchState(false);
                }
            })
            .catch(error => {
                console.error('获取AI配置失败:', error);
                voiceSampleStatus.textContent = '获取失败';
                voiceCloneStatus.textContent = '获取失败';
                updateThankSwitchState(false);
                this.showToast('获取AI配置失败', 'error');
            });
        
        aiThankSwitch.onchange = async () => {
            if (aiThankSwitch.checked && !isVoiceCloned) {
                aiThankSwitch.checked = false;
                this.showToast('请先完成音频复刻，才能启用AI答谢', 'warning');
                return;
            }
            
            if (aiThankSwitch.checked && !hasAiPrompt) {
                aiThankSwitch.checked = false;
                this.showToast('请先填写主播介绍（AI提示词），才能启用AI答谢', 'warning');
                return;
            }
            
            try {
                const response = await fetch('https://live.hzjt.com/api/upload_voice.php?action=update_ai_thank', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        room: room.ip,
                        license_id: this.app.licenseId || 0,
                        ai_thank_enabled: aiThankSwitch.checked ? 1 : 0
                    })
                });
                
                const result = await response.json();
                if (result.code === 0) {
                    this.showToast(aiThankSwitch.checked ? 'AI答谢已启用' : 'AI答谢已关闭', 'success');
                    room.ai_thank_enabled = aiThankSwitch.checked;

                    fetch(`/api/rooms/${room.id}/voice_status`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ voice_status: aiThankSwitch.checked })
                    }).catch(err => console.error('通知后端voice_status失败:', err));
                } else {
                    aiThankSwitch.checked = !aiThankSwitch.checked;
                    this.showToast('保存失败: ' + result.msg, 'error');
                }
            } catch (error) {
                aiThankSwitch.checked = !aiThankSwitch.checked;
                console.error('保存AI答谢开关失败:', error);
                this.showToast('保存失败，请检查网络', 'error');
            }
        };
        
        uploadBtn.onclick = () => {
            fileInput.click();
        };
        
        fileInput.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('room', room.ip);
            formData.append('license_id', this.app.licenseId || '');
            formData.append('voice_text', voiceTextInput.value);
            formData.append('ai_prompt', aiPromptInput.value);
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = '上传中...';
            
            try {
                const response = await fetch('https://live.hzjt.com/api/upload_voice.php?action=upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.code === 0) {
                    if (result.data.voice_sample_url) {
                        voiceSampleStatus.innerHTML = `<a href="${result.data.voice_sample_url}" target="_blank" style="color: #4caf50;">${result.data.voice_sample_url}</a>`;
                    } else {
                        voiceSampleStatus.textContent = result.data.voice_sample || '已上传';
                    }
                    cloneBtn.disabled = false;
                    this.showToast('音频上传成功', 'success');
                } else {
                    this.showToast('上传失败: ' + result.msg, 'error');
                }
            } catch (error) {
                console.error('上传音频失败:', error);
                this.showToast('上传失败，请检查网络', 'error');
            } finally {
                uploadBtn.disabled = false;
                uploadBtn.textContent = '上传';
                fileInput.value = '';
            }
        };
        
        cloneBtn.onclick = async () => {
            cloneBtn.disabled = true;
            cloneBtn.textContent = '复刻中...';
            voiceCloneStatus.textContent = '复刻中...';
            voiceCloneStatus.style.color = '#ff9800';
            
            try {
                const response = await fetch('/api/rooms/' + room.id + '/voice_clone', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        room: room.ip
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    voiceCloneStatus.textContent = '已复刻';
                    voiceCloneStatus.style.color = '#4caf50';
                    cloneBtn.textContent = '重新复刻';
                    cloneBtn.disabled = false;
                    updateThankSwitchState(true);
                    aiThankSwitch.checked = true;
                    this.showToast('语音复刻成功，AI答谢已自动启用', 'success');
                    this._saveAiThankEnabled(room, true);
                } else {
                    voiceCloneStatus.textContent = '复刻失败: ' + (result.error || '未知错误');
                    voiceCloneStatus.style.color = '#f44336';
                    cloneBtn.textContent = '开始复刻';
                    cloneBtn.disabled = false;
                    updateThankSwitchState(false);
                    this.showToast('复刻失败: ' + (result.error || '未知错误'), 'error');
                }
            } catch (error) {
                console.error('语音复刻失败:', error);
                voiceCloneStatus.textContent = '复刻失败';
                voiceCloneStatus.style.color = '#f44336';
                cloneBtn.textContent = '开始复刻';
                cloneBtn.disabled = false;
                updateThankSwitchState(false);
                this.showToast('复刻失败，请检查网络', 'error');
            }
        };
        
        const closeBtn = document.getElementById('room-ai-config-modal-close');
        const cancelBtn = document.getElementById('room-ai-config-modal-cancel');
        const saveBtn = document.getElementById('room-ai-config-modal-save');
        
        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };
        
        cancelBtn.onclick = () => {
            modal.style.display = 'none';
        };
        
        saveBtn.onclick = async () => {
            const aiPrompt = aiPromptInput.value.trim();
            const voiceText = voiceTextInput.value.trim();
            const thankValue = parseFloat(thankValueInput.value) || 0;

            if (!room.ip) {
                this.showToast('房间IP未配置，无法保存', 'error');
                return;
            }

            try {
                const response = await fetch('https://live.hzjt.com/api/upload_voice.php?action=update_ai_prompt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        room: room.ip,
                        license_id: this.app.licenseId || 0,
                        ai_prompt: aiPrompt,
                        voice_text: voiceText,
                        thank_value: thankValue
                    })
                });
                
                const responseText = await response.text();
                let result;
                try {
                    result = JSON.parse(responseText);
                } catch (parseError) {
                    console.error('JSON解析失败，服务器返回:', responseText);
                    this.showToast('服务器响应格式错误', 'error');
                    return;
                }
                
                if (result.code === 0) {
                    this.showToast('AI配置保存成功', 'success');
                    modal.style.display = 'none';
                } else {
                    this.showToast('保存失败: ' + result.msg, 'error');
                }
            } catch (error) {
                console.error('保存AI配置失败:', error);
                this.showToast('保存失败: ' + error.message, 'error');
            }
        };
    }
    
    async _saveAiThankEnabled(room, enabled) {
        try {
            await fetch('https://live.hzjt.com/api/upload_voice.php?action=update_ai_thank', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    room: room.ip,
                    ai_thank_enabled: enabled ? 1 : 0
                })
            });

            fetch(`/api/rooms/${room.id}/voice_status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ voice_status: enabled })
            }).catch(err => console.error('通知后端voice_status失败:', err));
        } catch (error) {
            console.error('保存AI答谢开关失败:', error);
        }
    }
    
    openSoundSettingsDialog(room) {
            const modal = document.getElementById('sound-settings-modal');
            const devicesList = document.getElementById('sound-settings-list');
            const roomNameSpan = document.getElementById('sound-settings-room-name');
            
            modal.style.display = 'flex';
            devicesList.innerHTML = '<tr><td colspan="3">加载中...</td></tr>';
            roomNameSpan.textContent = room.name;
            
            fetch(`/api/rooms/${room.id}/devices/sound_status`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const roomOnline = data.room_online;
                        devicesList.innerHTML = data.devices.map(device => {
                            const deviceLabel = device.label || device.name;
                            const isEnabled = device.trigger_sound;
                            const hasFile = device.has_sound_file;
                            const soundDelay = device.trigger_sound_delay || 0;
                            
                            return `
                                <tr data-device-id="${device.id}" data-device-name="${device.name}">
                                    <td style="width: 120px;">
                                        <label class="switch" style="display: inline-block;">
                                            <input type="checkbox" class="sound-enable-switch" 
                                                   data-device-id="${device.id}" 
                                                   ${isEnabled ? 'checked' : ''} 
                                                   ${!hasFile && !isEnabled ? 'disabled' : ''}>
                                            <span class="slider"></span>
                                        </label>
                                    </td>
                                    <td style="width: 120px;">${deviceLabel}</td>
                                    <td style="width: 150px;">
                                        <input type="number" class="sound-delay-input" 
                                               data-device-id="${device.id}"
                                               value="${soundDelay}" min="0" max="10" step="0.5"
                                               style="width: 60px; padding: 2px 5px; border: 1px solid #444; border-radius: 4px; background: #1a1a2e; color: #fff; text-align: center;"
                                               ${!isEnabled ? 'disabled' : ''}>
                                        <span style="color: #888; font-size: 12px;">秒</span>
                                    </td>
                                    <td>
                                        ${!roomOnline 
                                            ? '<span class="sound-status-text missing">✗ 设备离线</span>' 
                                            : hasFile 
                                                ? '<span class="sound-status-text ready">✓ 音效文件已就绪</span>' 
                                                : '<span class="sound-status-text missing">✗ 音效文件不存在</span>'}
                                    </td>
                                </tr>
                            `;
                        }).join('');
                        
                        // 绑定开关事件
                        data.devices.forEach(device => {
                            const switchEl = document.querySelector(`.sound-enable-switch[data-device-id="${device.id}"]`);
                            if (switchEl) {
                                switchEl.addEventListener('change', (e) => {
                                    const delayInput = document.querySelector(`.sound-delay-input[data-device-id="${device.id}"]`);
                                    if (!e.target.checked && delayInput) {
                                        delayInput.disabled = true;
                                    }
                                    this.updateDeviceSoundConfig(room.id, device.id, e.target.checked);
                                });
                            }
                            
                            const delayInput = document.querySelector(`.sound-delay-input[data-device-id="${device.id}"]`);
                            if (delayInput) {
                                delayInput.addEventListener('change', (e) => {
                                    let val = parseFloat(e.target.value) || 0;
                                    if (val < 0) val = 0;
                                    if (val > 10) val = 10;
                                    e.target.value = val;
                                    this.updateDeviceSoundDelay(room.id, device.id, val);
                                });
                            }
                        });
                    } else {
                        devicesList.innerHTML = '<tr><td colspan="3">加载失败</td></tr>';
                        this.showToast('加载音效设置失败: ' + (data.error || '未知错误'), 'error');
                    }
                })
                .catch(error => {
                    console.error('加载音效设置失败:', error);
                    devicesList.innerHTML = '<tr><td colspan="3">加载失败</td></tr>';
                    this.showToast('加载音效设置失败', 'error');
                });
            
            const closeBtn = document.getElementById('sound-settings-modal-close');
            closeBtn.onclick = () => {
                modal.style.display = 'none';
            };
        }
    
    async updateDeviceSoundConfig(roomId, deviceId, enabled) {
        try {
            const response = await fetch(`/api/rooms/${roomId}/devices/${deviceId}/sound_config`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ trigger_sound: enabled })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const delayInput = document.querySelector(`.sound-delay-input[data-device-id="${deviceId}"]`);
                if (delayInput) {
                    delayInput.disabled = !enabled;
                }
                if (data.esp32_sync === true) {
                    this.showToast(enabled ? '音效已启用，文件已同步到设备' : '音效已停用，设备文件已删除', 'success');
                } else if (data.esp32_sync === false) {
                    this.showToast(enabled ? '音效已启用，但设备文件同步失败' : '音效已停用，但设备文件删除失败', 'warning');
                } else {
                    this.showToast('音效设置已保存（设备离线，未同步）', 'warning');
                }
            } else {
                this.showToast('保存失败: ' + (data.error || '未知错误'), 'error');
                // 恢复开关状态
                const switchEl = document.querySelector(`.sound-enable-switch[data-device-id="${deviceId}"]`);
                if (switchEl) {
                    switchEl.checked = !enabled;
                }
            }
        } catch (error) {
            console.error('保存音效设置失败:', error);
            this.showToast('保存失败', 'error');
            // 恢复开关状态
            const switchEl = document.querySelector(`.sound-enable-switch[data-device-id="${deviceId}"]`);
            if (switchEl) {
                switchEl.checked = !enabled;
            }
        }
    }

    async updateDeviceSoundDelay(roomId, deviceId, delay) {
        try {
            const response = await fetch(`/api/rooms/${roomId}/devices/${deviceId}/sound_config`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ trigger_sound_delay: delay })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast(`延时已设置为 ${delay} 秒`, 'success');
            } else {
                this.showToast('保存延时失败: ' + (data.error || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('保存延时设置失败:', error);
            this.showToast('保存延时失败', 'error');
        }
    }

    openLoopSettingsDialog(room) {
        const modal = document.getElementById('loop-settings-modal');
        const devicesList = document.getElementById('loop-settings-list');
        const roomNameSpan = document.getElementById('loop-settings-room-name');
        
        modal.style.display = 'flex';
        devicesList.innerHTML = '<tr><td colspan="4">加载中...</td></tr>';
        roomNameSpan.textContent = room.name;
        
        fetch(`/api/rooms/${room.id}/always/loop_status`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const device = data.device;
                    const loopAction = device.loop_action || 'manual';
                    const loopMinute = device.loop_minute || '';
                    const loopDuration = device.loop_duration || 0;
                    const isRunning = device.is_running || false;
                    
                    devicesList.innerHTML = `
                        <tr data-device-id="${device.id}">
                            <td>
                                <select class="prog-device-event-select" id="loop-action-select">
                                    <option value="manual" ${loopAction === 'manual' ? 'selected' : ''}>手动</option>
                                    <option value="open" ${loopAction === 'open' ? 'selected' : ''}>定开</option>
                                    <option value="close" ${loopAction === 'close' ? 'selected' : ''}>定关</option>
                                </select>
                            </td>
                            <td>
                                <input type="text" class="prog-device-time-input" id="loop-minute-input" 
                                       value="${loopMinute}" placeholder="如: 8 或 3|6 或 8|19">
                            </td>
                            <td>
                                <input type="number" class="prog-device-time-input" id="loop-duration-input" 
                                       value="${loopDuration}" min="0" max="60" step="0.1">
                            </td>
                            <td>
                                ${isRunning 
                                    ? '<span class="loop-status-text running">运行中</span>' 
                                    : '<span class="loop-status-text stopped">已停止</span>'}
                            </td>
                        </tr>
                    `;
                } else {
                    devicesList.innerHTML = '<tr><td colspan="4">加载失败</td></tr>';
                    this.showToast('加载循环设置失败: ' + (data.error || '未知错误'), 'error');
                }
            })
            .catch(error => {
                console.error('加载循环设置失败:', error);
                devicesList.innerHTML = '<tr><td colspan="4">加载失败</td></tr>';
                this.showToast('加载循环设置失败', 'error');
            });
        
        const closeBtn = document.getElementById('loop-settings-modal-close');
        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };
        
        const saveBtn = document.getElementById('loop-settings-modal-save');
        saveBtn.onclick = () => {
            this.saveLoopSettings(room.id);
        };
    }

    async saveLoopSettings(roomId) {
        try {
            const loopActionSelect = document.getElementById('loop-action-select');
            const loopMinuteInput = document.getElementById('loop-minute-input');
            const loopDurationInput = document.getElementById('loop-duration-input');
            
            const loopAction = loopActionSelect.value;
            const loopMinute = loopMinuteInput.value.trim();
            const loopDuration = parseFloat(loopDurationInput.value) || 0;
            
            if (loopMinute) {
                const parts = loopMinute.split('|');
                for (const part of parts) {
                    const trimmed = part.trim();
                    if (!/^\d+$/.test(trimmed)) {
                        this.showToast(`无效的分钟值: ${trimmed}`, 'error');
                        return;
                    }
                    const num = parseInt(trimmed);
                    if (num < 0 || num > 59) {
                        this.showToast(`分钟值必须在0-59之间: ${trimmed}`, 'error');
                        return;
                    }
                }
            }
            
            const response = await fetch(`/api/rooms/${roomId}/always/loop_config`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    loop_action: loopAction,
                    loop_minute: loopMinute,
                    loop_duration: loopDuration
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showToast('循环设置已保存', 'success');
                document.getElementById('loop-settings-modal').style.display = 'none';
            } else {
                this.showToast('保存失败: ' + (data.error || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('保存循环设置失败:', error);
            this.showToast('保存失败', 'error');
        }
    }
}
