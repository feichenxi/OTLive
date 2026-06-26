export default class MessageManager {
    constructor(app) {
        this.app = app;
        this.maxMessageElements = 50;
        this._initialized = false;
        this.manualCloseTime = new Map();
    }

    async initAllMessageContainers() {
        if (this._initialized) return;
        this._initialized = true;

        const area = document.getElementById('room-messages-area');
        if (!area) {
            console.error('[MessageManager] room-messages-area not found!');
            return;
        }
        console.log('[MessageManager] Initializing message containers, rooms:', this.app.rooms.length);

        let html = '';

        html += `<div class="msg-panel active" id="msg-panel-home">
            <div class="room-interaction-card">
                <h3>全部互动</h3>
                <div class="interaction-messages" id="msg_home"></div>
            </div>
            <div class="room-gift-card">
                <h3>全部礼物</h3>
                <div class="gift-messages" id="gift_home"></div>
            </div>
        </div>`;

        for (const room of this.app.rooms) {
            html += `<div class="msg-panel" id="msg-panel-${room.id}">
                <div class="room-interaction-card">
                    <h3>房间消息</h3>
                    <div class="interaction-messages" id="msg_${room.id}"></div>
                </div>
                <div class="room-gift-card">
                    <h3>房间礼物</h3>
                    <div class="gift-messages" id="gift_${room.id}"></div>
                </div>
            </div>`;
        }

        area.innerHTML = html;
        console.log('[MessageManager] Panels created, loading history...');

        for (const room of this.app.rooms) {
            await this.loadRoomHistory(room.id);
        }
        await this.loadHomeHistory();

        this.showPanel(this.app.selectedRoom ? this.app.selectedRoom.id : 'home');
        console.log('[MessageManager] Initialization complete');
    }

    async loadRoomHistory(roomId, limit = 20) {
        try {
            const response = await fetch(`/api/messages/${roomId}?limit=${limit}`);
            const data = await response.json();
            if (data.success) {
                console.log(`[MessageManager] Room ${roomId}: loaded ${data.messages.length} messages`);
                this.renderMessagesToContainer(data.messages, roomId);
            } else {
                console.error(`[MessageManager] Room ${roomId} API error:`, data.error);
            }
        } catch (error) {
            console.error(`Error loading room ${roomId} history:`, error);
        }
    }

    async loadHomeHistory(limit = 100) {
        try {
            const response = await fetch(`/api/messages/all?limit=${limit}`);
            const data = await response.json();
            if (data.success) {
                this.renderMessagesToContainer(data.messages, 'home');
            }
        } catch (error) {
            console.error('Error loading home history:', error);
        }
    }

    renderMessagesToContainer(messages, targetId) {
        let msgContainer, giftContainer;

        if (targetId === 'home') {
            msgContainer = document.getElementById('msg_home');
            giftContainer = document.getElementById('gift_home');
        } else {
            msgContainer = document.getElementById(`msg_${targetId}`);
            giftContainer = document.getElementById(`gift_${targetId}`);
        }

        if (!msgContainer || !giftContainer) {
            console.error(`[MessageManager] Containers not found for target: ${targetId}`, { msgContainer, giftContainer });
            return;
        }

        msgContainer.innerHTML = '';
        giftContainer.innerHTML = '';

        const interactionMsgs = messages.filter(m => m.type !== 'gif');
        const giftMsgs = messages.filter(m => m.type === 'gif');

        if (interactionMsgs.length === 0) {
            msgContainer.innerHTML = '<div class="no-messages">暂无消息</div>';
        } else {
            interactionMsgs.forEach(msg => {
                msgContainer.insertAdjacentHTML('beforeend', this.createMessageHTML(msg, targetId === 'home'));
            });
        }

        if (giftMsgs.length === 0) {
            giftContainer.innerHTML = '<div class="no-messages">暂无礼物</div>';
        } else {
            giftMsgs.forEach(msg => {
                giftContainer.insertAdjacentHTML('beforeend', this.createGiftHTML(msg, targetId === 'home'));
            });
        }
    }

    showPanel(targetId) {
        document.querySelectorAll('.msg-panel').forEach(el => {
            el.classList.remove('active');
        });

        const panel = document.getElementById(`msg-panel-${targetId}`);
        if (panel) {
            panel.classList.add('active');
        }
    }

    updateAllInteractionList(data) {
    }

    updateAllGiftList(data) {
    }

    appendMessage(msg) {
        const roomId = msg.room_id;
        if (!roomId) return;

        this.appendToRoomContainer(msg, roomId);
        this.appendToHomeContainer(msg);
    }

    appendToRoomContainer(msg, roomId) {
        if (msg.type === 'gif') {
            const container = document.getElementById(`gift_${roomId}`);
            if (container) {
                this.clearNoMessageIfNeeded(container);
                this.trimContainer(container);
                container.insertAdjacentHTML('afterbegin', this.createGiftHTML(msg, false));
            }
        } else {
            const container = document.getElementById(`msg_${roomId}`);
            if (container) {
                this.clearNoMessageIfNeeded(container);
                this.trimContainer(container);
                container.insertAdjacentHTML('afterbegin', this.createMessageHTML(msg, false));
            }
        }
    }

    appendToHomeContainer(msg) {
        if (msg.type === 'gif') {
            const container = document.getElementById('gift_home');
            if (container) {
                this.clearNoMessageIfNeeded(container);
                this.trimContainer(container);
                container.insertAdjacentHTML('afterbegin', this.createGiftHTML(msg, true));
            }
        } else {
            const container = document.getElementById('msg_home');
            if (container) {
                this.clearNoMessageIfNeeded(container);
                this.trimContainer(container);
                container.insertAdjacentHTML('afterbegin', this.createMessageHTML(msg, true));
            }
        }
    }

    clearNoMessageIfNeeded(container) {
        const noMsgElement = container.querySelector('.no-messages');
        if (noMsgElement) {
            noMsgElement.remove();
        }
    }

    trimContainer(container) {
        const children = container.children;
        if (children.length > this.maxMessageElements) {
            while (children.length > this.maxMessageElements) {
                container.removeChild(children[children.length - 1]);
            }
        }
    }

    createMessageHTML(msg, isHome) {
        const userName = msg.name || '匿名';
        const content = msg.content || '';
        const time = msg.created_at || '';

        let roomBadge = '';
        if (isHome && msg.room) {
            const room = this.app.rooms.find(r => r.ip === msg.room);
            if (room) {
                let label = room.name || '';
                if (label.length === 0) {
                    label = `房间${room.id}`;
                }
                let shortName;
                const m = label.match(/^(房间\d+)/);
                if (m) {
                    shortName = m[1];
                } else if (label.length > 4) {
                    shortName = label.substring(0, 4);
                } else {
                    shortName = label;
                }
                roomBadge = `<span class="message-room-badge clickable" onclick="event.stopPropagation(); app.roomManager.selectRoom(${room.id})">${shortName}</span>`;
            }
        }

        return `
            <div class="interaction-message">
                <span class="interaction-user">${userName}</span>
                <span class="interaction-content clickable" onclick="app.showMessageDetail('${userName}', '${content.replace(/'/g, "\\'")}', '${time}')">${roomBadge}${content}</span>
                <span class="interaction-time">${time}</span>
            </div>
        `;
    }

    createGiftHTML(msg, isHome) {
        const userName = msg.name || '匿名';
        const content = msg.content || '';
        const time = msg.created_at || '';
        const status = msg.status !== undefined && msg.status !== null ? msg.status : 0;
        const giftId = msg.id || '';
        const roomId = msg.room_id || '';

        let roomBadge = '';
        if (isHome && msg.room) {
            const room = this.app.rooms.find(r => r.ip === msg.room);
            if (room) {
                let label = room.name || '';
                if (label.length === 0) {
                    label = `房间${room.id}`;
                }
                let shortName;
                const m = label.match(/^(房间\d+)/);
                if (m) {
                    shortName = m[1];
                } else if (label.length > 4) {
                    shortName = label.substring(0, 4);
                } else {
                    shortName = label;
                }
                roomBadge = `<span class="message-room-badge clickable" onclick="event.stopPropagation(); app.roomManager.selectRoom(${room.id})">${shortName}</span>`;
            }
        }

        const statusLabels = {
            '-5': '不谢',
            '-1': '低值',
            '-2': '超限',
            '-3': '合并',
            '-4': '冷却',
            '0': '待谢',
            '1': '生文',
            '2': '生音',
            '3': '正谢',
            '4': '播放',
            '9': '已谢'
        };
        const statusLabel = statusLabels[status.toString()] || '?';
        const statusClass = status >= 0 ? `gift-status-${status}` : `gift-status-${status}`;
        const statusBadge = `<span class="gift-status-badge ${statusClass}">${statusLabel}</span>`;

        return `
            <div class="gift-message" data-room-id="${roomId}" data-gift-id="${giftId}">
                <span class="gift-user">${userName}</span>
                <span class="gift-name clickable" onclick="app.showMessageDetail('${userName}', '${content.replace(/'/g, "\\'")}', '${time}')">${roomBadge}${statusBadge}${content}</span>
                <span class="gift-time">${time}</span>
            </div>
        `;
    }

    updateGiftStatus(roomId, giftId, newStatus) {
        const statusLabels = {
            '-5': '不谢',
            '-1': '低值',
            '-2': '超限',
            '-3': '合并',
            '-4': '冷却',
            '0': '待谢',
            '1': '生文',
            '2': '生音',
            '3': '正谢',
            '4': '播放',
            '9': '已谢'
        };
        const statusLabel = statusLabels[newStatus.toString()] || '?';
        const statusClass = newStatus >= 0 ? `gift-status-${newStatus}` : `gift-status-${newStatus}`;

        const elements = document.querySelectorAll(`.gift-message[data-room-id="${roomId}"][data-gift-id="${giftId}"]`);
        elements.forEach(el => {
            const badge = el.querySelector('.gift-status-badge');
            if (badge) {
                badge.className = `gift-status-badge ${statusClass}`;
                badge.textContent = statusLabel;
            }
        });
    }

    openGiftConfigDialog() {
        document.getElementById('gift-config-modal').style.display = 'flex';
        this.loadGifts();
        this.initGiftSearch();
    }

    initGiftSearch() {
        const searchInput = document.getElementById('gift-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                this.filterGifts(query);
            });
        }
    }

    filterGifts(query) {
        const tbody = document.getElementById('gift-list-body');
        if (!tbody) return;
        
        const rows = tbody.querySelectorAll('tr');
        rows.forEach(row => {
            const nameCell = row.querySelector('td:nth-child(2)');
            if (nameCell) {
                const name = nameCell.textContent.toLowerCase();
                row.style.display = name.includes(query) ? '' : 'none';
            }
        });
    }

    loadGifts() {
        fetch('/api/gifts')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.allGifts = data.gifts;
                    this.renderGiftList(data.gifts);
                }
            })
            .catch(error => {
                console.error('Error loading gifts:', error);
            });
    }

    renderGiftList(gifts) {
        const tbody = document.getElementById('gift-list-body');
        if (!tbody) return;
        
        tbody.innerHTML = gifts.map(gift => `
            <tr data-gift-id="${gift.id}">
                <td><input type="checkbox" class="gift-enable" data-gift-id="${gift.id}" ${gift.enabled ? 'checked' : ''}></td>
                <td><input type="text" class="gift-name" data-gift-id="${gift.id}" value="${gift.name || ''}"></td>
                <td><input type="number" class="gift-value" data-gift-id="${gift.id}" value="${gift.value || 0}" min="0"></td>
                <td>
                    <select class="gift-level" data-gift-id="${gift.id}">
                        <option value="1" ${gift.level === 1 ? 'selected' : ''}>一级</option>
                        <option value="2" ${gift.level === 2 ? 'selected' : ''}>二级</option>
                        <option value="3" ${gift.level === 3 ? 'selected' : ''}>三级</option>
                    </select>
                </td>
                <td><input type="number" class="gift-delay" data-gift-id="${gift.id}" value="${gift.delay || 0}" min="0" step="0.5"></td>
                <td><button class="dialog-btn dialog-btn-save" onclick="app.saveGift(${gift.id})">保存</button></td>
                <td><button class="dialog-btn dialog-btn-danger" onclick="app.deleteGift(${gift.id})">删除</button></td>
            </tr>
        `).join('');
    }

    addGift() {
        const tbody = document.getElementById('gift-list-body');
        if (!tbody) return;
        
        const newRow = document.createElement('tr');
        newRow.dataset.giftId = 'new';
        newRow.innerHTML = `
            <td><input type="checkbox" class="gift-enable" data-gift-id="new" checked></td>
            <td><input type="text" class="gift-name" data-gift-id="new" value="" placeholder="礼物名称"></td>
            <td><input type="number" class="gift-value" data-gift-id="new" value="0" min="0"></td>
            <td>
                <select class="gift-level" data-gift-id="new">
                    <option value="1">一级</option>
                    <option value="2">二级</option>
                    <option value="3">三级</option>
                </select>
            </td>
            <td><input type="number" class="gift-delay" data-gift-id="new" value="0" min="0" step="0.5"></td>
            <td><button class="dialog-btn dialog-btn-save" onclick="app.addGift()">保存</button></td>
            <td><button class="dialog-btn dialog-btn-danger" onclick="this.closest('tr').remove()">删除</button></td>
        `;
        tbody.insertBefore(newRow, tbody.firstChild);
    }

    editGift(giftId) {
    }

    saveGiftEdit() {
    }

    saveGift(giftId) {
        const row = document.querySelector(`tr[data-gift-id="${giftId}"]`);
        if (!row) return;

        const name = row.querySelector('.gift-name').value;
        const value = parseInt(row.querySelector('.gift-value').value) || 0;
        const level = parseInt(row.querySelector('.gift-level').value) || 1;
        const delay = parseFloat(row.querySelector('.gift-delay').value) || 0;
        const enabled = row.querySelector('.gift-enable').checked;

        const giftData = { name, value, level, delay, enabled };

        const url = giftId === 'new' ? '/api/gifts' : `/api/gifts/${giftId}`;
        const method = giftId === 'new' ? 'POST' : 'PUT';

        fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(giftData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.loadGifts();
                } else {
                    alert('保存失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                console.error('Error saving gift:', error);
                alert('保存失败');
            });
    }

    deleteGift(giftId) {
        if (!confirm('确定要删除这个礼物吗？')) return;
        
        fetch(`/api/gifts/${giftId}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.loadGifts();
                } else {
                    alert('删除失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                console.error('Error deleting gift:', error);
                alert('删除失败');
            });
    }

    stopMessageRefresh() {
    }

    cancelGiftEdit() {
        const giftConfigModal = document.getElementById('gift-config-modal');
        if (giftConfigModal) {
            giftConfigModal.style.display = 'none';
        }
    }

    _parseViewerCount(text) {
        if (!text || typeof text !== 'string') {
            return null;
        }
        const cleanText = text.trim();
        
        let match = cleanText.match(/(\d+(?:\.\d+)?)\s*万\+/);
        if (match) {
            const num = parseFloat(match[1]);
            return Math.round(num * 10000);
        }
        
        match = cleanText.match(/(\d+(?:\.\d+)?)\s*万人?/);
        if (match) {
            const num = parseFloat(match[1]);
            return Math.round(num * 10000);
        }
        
        match = cleanText.match(/(\d+(?:\.\d+)?)/);
        if (match) {
            return parseInt(match[1], 10);
        }
        
        return null;
    }
}
