export default class AudioManager {
    constructor(app) {
        this.app = app;
        this.audioContext = null;
        this.analyser = null;
        this.microphoneStream = null;
        this.dataArray = null;
        this.animationId = null;
        this.currentRoomId = null;
        this.isMicActive = false;
    }

    async initAudioContext() {
        if (!this.audioContext) {
            try {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                this.analyser = this.audioContext.createAnalyser();
                this.analyser.fftSize = 256;
                const bufferLength = this.analyser.frequencyBinCount;
                this.dataArray = new Uint8Array(bufferLength);
            } catch (error) {
                console.error('[AudioManager] Failed to initialize AudioContext:', error);
                throw error;
            }
        }
    }

    async startMicrophone(roomId) {
        try {
            await this.initAudioContext();

            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            this.microphoneStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            const source = this.audioContext.createMediaStreamSource(this.microphoneStream);
            source.connect(this.analyser);

            this.currentRoomId = roomId;
            this.isMicActive = true;
            this.startAudioAnalysis(roomId);

            return true;
        } catch (error) {
            console.error('[AudioManager] Failed to access microphone:', error);
            this.app.uiManager.showToast('无法访问麦克风，请检查权限设置', 'error');
            return false;
        }
    }

    stopMicrophone() {
        if (this.microphoneStream) {
            this.microphoneStream.getTracks().forEach(track => track.stop());
            this.microphoneStream = null;
        }

        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        this.isMicActive = false;
        this.currentRoomId = null;

        this.resetAudioLevelUI();
    }

    startAudioAnalysis(roomId) {
        const analyze = () => {
            if (!this.isMicActive || this.currentRoomId !== roomId) {
                return;
            }

            this.analyser.getByteFrequencyData(this.dataArray);

            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;
            const volumeLevel = Math.round((average / 255) * 100);

            this.updateAudioLevelUI(roomId, volumeLevel);

            this.animationId = requestAnimationFrame(analyze);
        };

        analyze();
    }

    updateAudioLevelUI(roomId, level) {
        const levelFill = document.getElementById(`audio-level-${roomId}`);
        const levelText = document.getElementById(`audio-level-text-${roomId}`);

        if (levelFill) {
            levelFill.style.width = `${level}%`;
            if (level > 70) {
                levelFill.style.backgroundColor = '#f44336';
            } else if (level > 40) {
                levelFill.style.backgroundColor = '#ff9800';
            } else {
                levelFill.style.backgroundColor = '#4caf50';
            }
        }

        if (levelText) {
            levelText.textContent = level;
        }
    }

    resetAudioLevelUI() {
        document.querySelectorAll('[id^="audio-level-"]').forEach(el => {
            if (el.id.includes('text')) {
                el.textContent = '0';
            } else {
                el.style.width = '0%';
            }
        });
    }

    updateAudioStatus(data) {
        if (data.active) {
            this.app.currentAudioRoom = data.room_id;
            this.app.broadcastMode = false;
        } else {
            this.app.currentAudioRoom = null;
        }
        this.updateAudioUI();
    }

    updateAudioUI() {
        const broadcastBtn = document.getElementById('broadcast-btn');
        const audioStatus = document.getElementById('audio-status');
        
        if (this.app.broadcastMode) {
            broadcastBtn.textContent = '广播模式 (开启)';
            broadcastBtn.className = 'btn btn-success';
            audioStatus.textContent = '音频: 广播模式';
        } else if (this.app.currentAudioRoom) {
            const room = this.app.rooms.find(r => r.id === this.app.currentAudioRoom);
            broadcastBtn.textContent = '广播模式';
            broadcastBtn.className = 'btn btn-warning';
            audioStatus.textContent = `音频: ${room ? room.name : '未知'}`;
        } else {
            broadcastBtn.textContent = '广播模式';
            broadcastBtn.className = 'btn btn-warning';
            audioStatus.textContent = '音频: 未连接';
        }
    }

    toggleMicrophone(roomId, enabled) {
        console.log('[前端] toggleMicrophone 被调用', { roomId, enabled });
        const room = this.app.rooms.find(r => r.id === roomId);
        if (room) {
            room.mic_enabled = enabled;
            
            const micBtn = document.querySelector(`.device-btn[onclick*="toggleMicrophone(${roomId}"]`);
            if (micBtn) {
                micBtn.className = `device-btn ${enabled ? 'active' : ''}`;
            }
            
            console.log('[前端] 发送 socket 事件: toggle_microphone');
            this.app.socket.emit('toggle_microphone', {
                room_id: roomId,
                enabled: enabled
            });
            
            // 更新所有房间的对讲状态显示
            this.app.rooms.forEach(r => {
                this.app.roomManager.updateRoomIntercomStatus(r);
            });
        } else {
            console.error('[前端] 房间未找到:', roomId);
        }
    }

    toggleRoomMusic(roomId, enabled) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (room) {
            room.music = enabled;
            
            // 音乐控制直接通过play/stop_background_music事件，不需要control_device
            // 因为"music"不是一个真实的硬件设备
            
            if (enabled && room.background_music_url) {
                const volume = room.intercom_volume ?? 50;
                this.app.socket.emit('play_background_music', {
                    room_id: roomId,
                    url: room.background_music_url,
                    loop: true,
                    volume: volume / 100
                });
            } else if (!enabled) {
                this.app.socket.emit('stop_background_music', {
                    room_id: roomId
                });
            }
        }
    }

    async toggleRoomDialog(roomId, enabled) {
        console.log('[前端] toggleRoomDialog 被调用', { roomId, enabled });
        if (enabled) {
            console.log('[前端] 正在启动麦克风...');
            const success = await this.startMicrophone(roomId);
            console.log('[前端] 麦克风启动结果:', success);
            if (success) {
                console.log('[前端] 调用 toggleMicrophone(true)');
                this.toggleMicrophone(roomId, true);
            } else {
                console.error('[前端] 麦克风启动失败');
                const switchEl = document.getElementById('device-dialog-switch');
                if (switchEl) {
                    switchEl.checked = false;
                }
            }
        } else {
            console.log('[前端] 正在停止麦克风...');
            this.stopMicrophone();
            console.log('[前端] 调用 toggleMicrophone(false)');
            this.toggleMicrophone(roomId, false);
        }
    }

    openVolumeDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const currentVolume = room.intercom_volume ?? 50;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>音量设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field inline">
                        <label for="volume-input">音量</label>
                        <div class="volume-slider-container">
                            <input type="range" id="volume-input" min="0" max="100" value="${currentVolume}" class="volume-slider">
                            <span id="volume-value" style="min-width: 50px; text-align: center;">${currentVolume}%</span>
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

        const volumeInput = document.getElementById('volume-input');
        const volumeValue = document.getElementById('volume-value');

        volumeInput.addEventListener('input', (e) => {
            volumeValue.textContent = `${e.target.value}%`;
        });

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', () => {
            const newVolume = parseInt(volumeInput.value);
            
            this.app.socket.emit('update_room_intercom_volume', {
                room_id: roomId,
                volume: newVolume
            });
            
            const speakerBtn = document.querySelector(`.device-btn[onclick*="openVolumeDialog(${roomId})"]`);
            if (speakerBtn) {
                speakerBtn.textContent = `音量 ${newVolume}%`;
            }
            
            dialog.remove();
        });
    }

    openIntercomVolumeDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const currentVolume = room.intercom_volume ?? 50;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>对讲音量设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field inline">
                        <label for="intercom-volume-input">对讲音量</label>
                        <div class="volume-slider-container">
                            <input type="range" id="intercom-volume-input" min="0" max="100" value="${currentVolume}" class="volume-slider">
                            <span id="intercom-volume-value" style="min-width: 50px; text-align: center;">${currentVolume}%</span>
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

        const volumeInput = document.getElementById('intercom-volume-input');
        const volumeValue = document.getElementById('intercom-volume-value');

        volumeInput.addEventListener('input', (e) => {
            volumeValue.textContent = `${e.target.value}%`;
        });

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', () => {
            const newVolume = parseInt(volumeInput.value);
            
            this.app.socket.emit('update_room_intercom_volume', {
                room_id: roomId,
                volume: newVolume
            });
            
            const intercomBtn = document.querySelector(`.device-btn[onclick*="openIntercomVolumeDialog(${roomId})"]`);
            if (intercomBtn) {
                intercomBtn.textContent = `对讲音量 ${newVolume}%`;
            }
            
            dialog.remove();
        });
    }

    openBackgroundMusicDialog(roomId) {
        const room = this.app.rooms.find(r => r.id === roomId);
        if (!room) return;

        const currentUrl = room.background_music_url || '';
        const currentDisplay = this.formatBackgroundMusicDisplay(currentUrl);
        const currentMusicName = room.background_music_name || '';
        const currentSize = room.background_music_size || 0;

        const dialog = document.createElement('div');
        dialog.className = 'settings-dialog-overlay';
        dialog.innerHTML = `
            <div class="settings-dialog">
                <div class="settings-dialog-header">
                    <h3>背景音乐设置</h3>
                    <button class="dialog-close-btn" id="dialog-close-btn">&times;</button>
                </div>
                <div class="settings-dialog-body">
                    <div class="settings-field">
                        <label>当前选择</label>
                        <div class="audio-files-list" id="current-selection-display">
                            <div class="audio-file-item">
                                <div class="audio-file-info">
                                    <span class="audio-file-index">-</span>
                                    <div class="audio-file-details">
                                        <span class="audio-file-name">${currentMusicName || '未选择'}</span>
                                        <span class="audio-file-path">${currentDisplay || ''}</span>
                                    </div>
                                    <span class="audio-file-size">${currentSize ? this.formatFileSize(currentSize) : ''}</span>
                                </div>
                                <button class="audio-file-select-btn audio-file-clear-btn" id="clear-selection-btn" style="display: ${currentUrl ? 'inline-block' : 'none'};">清除</button>
                            </div>
                        </div>
                        <input type="hidden" id="current-url-input" value="${currentUrl}">
                        <input type="hidden" id="current-music-name-input" value="${currentMusicName}">
                        <input type="hidden" id="current-size-input" value="${currentSize}">
                    </div>
                    <div class="settings-field">
                        <label>上传音乐</label>
                        <div class="upload-music-row">
                            <input type="text" id="music-name-input" placeholder="音乐名称">
                            <input type="file" id="bg-audio-file-input" accept=".wav">
                            <button class="upload-btn" id="upload-music-btn">上传</button>
                        </div>
                    </div>
                    <div class="settings-field">
                        <label>音乐列表</label>
                        <div class="audio-files-list" id="bg-audio-files-list">
                            <p class="no-files">加载中...</p>
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

        const audioFileInput = document.getElementById('bg-audio-file-input');
        const musicNameInput = document.getElementById('music-name-input');
        const uploadBtn = document.getElementById('upload-music-btn');

        uploadBtn.addEventListener('click', () => {
            const file = audioFileInput.files[0];
            const musicName = musicNameInput.value.trim();
            
            if (!file) {
                this.showToast('请选择音频文件', 'error');
                return;
            }
            
            if (!musicName) {
                this.showToast('请输入音乐名称', 'error');
                return;
            }
            
            this.uploadBackgroundMusicFile(file, roomId, musicName, musicNameInput, audioFileInput);
        });

        this.loadBackgroundMusicFiles(roomId);

        document.getElementById('dialog-close-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-cancel-btn').addEventListener('click', () => {
            dialog.remove();
        });

        document.getElementById('dialog-save-btn').addEventListener('click', () => {
            const newUrl = document.getElementById('current-url-input').value.trim();
            const newMusicName = document.getElementById('current-music-name-input').value.trim();
            const newSize = parseInt(document.getElementById('current-size-input').value) || 0;
            const room = this.app.rooms.find(r => r.id === roomId);
            
            console.log('[DEBUG] 保存背景音乐URL:', {
                roomId,
                newUrl,
                newMusicName,
                newSize,
                room: room ? { id: room.id, name: room.name, music: room.music } : null
            });
            
            this.app.socket.emit('update_room_background_music_url', {
                room_id: roomId,
                url: newUrl,
                music_name: newMusicName,
                size: newSize
            });
            
            console.log('[DEBUG] 发送 update_room_background_music_url 事件');
            
            if (room && room.music && newUrl) {
                console.log('[DEBUG] 房间音乐开启，发送 play_background_music 事件');
                this.app.socket.emit('play_background_music', {
                    room_id: roomId,
                    url: newUrl
                });
            } else {
                console.log('[DEBUG] 不发送 play_background_music 事件:', {
                    roomExists: !!room,
                    musicEnabled: room ? room.music : false,
                    hasUrl: !!newUrl
                });
            }
            
            dialog.remove();
        });
    }

    async uploadBackgroundMusicFile(file, roomId, musicName, musicNameInput, audioFileInput) {
        if (!file.name.toLowerCase().endsWith('.wav')) {
            this.showToast('只支持WAV格式文件', 'error');
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            this.showToast('文件大小不能超过5MB', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('music_name', musicName);

        try {
            const response = await fetch('/api/audio/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                musicNameInput.value = '';
                audioFileInput.value = '';
                this.loadBackgroundMusicFiles(roomId);
            } else {
                this.showToast(`上传失败: ${result.error}`, 'error');
            }
        } catch (error) {
            this.showToast('上传失败: 网络错误', 'error');
        }
    }

    async loadBackgroundMusicFiles(roomId) {
        try {
            const response = await fetch('/api/audio/files');
            const result = await response.json();

            if (result.success) {
                this.displayBackgroundMusicFiles(result.files, roomId);
            } else {
                this.showToast('获取音频文件列表失败', 'error');
            }
        } catch (error) {
            this.showToast('获取音频文件列表失败: 网络错误', 'error');
        }
    }

    displayBackgroundMusicFiles(files, roomId) {
        const filesList = document.getElementById('bg-audio-files-list');

        if (files.length === 0) {
            filesList.innerHTML = '<p class="no-files">暂无音频文件</p>';
            return;
        }

        filesList.innerHTML = files.map((file, index) => `
            <div class="audio-file-item">
                <div class="audio-file-info">
                    <span class="audio-file-index">${index + 1}</span>
                    <div class="audio-file-details">
                        <span class="audio-file-name">${file.music_name || file.filename}</span>
                        <span class="audio-file-path">${this.formatBackgroundMusicDisplay(file.url)}</span>
                    </div>
                    <span class="audio-file-size">${this.formatFileSize(file.size)}</span>
                </div>
                <div class="audio-file-buttons">
                    <button class="audio-file-select-btn" onclick="app.audioManager.selectBackgroundMusic('${file.filename}', ${roomId}, '${file.music_name || file.filename}', ${file.size})">选择</button>
                    <button class="audio-file-delete-btn" onclick="app.audioManager.deleteBackgroundMusic('${file.filename}', ${roomId})">删除</button>
                </div>
            </div>
        `).join('');
    }

    async deleteBackgroundMusic(filename, roomId) {
        if (!confirm('确定要删除这个音频文件吗？')) {
            return;
        }

        try {
            const response = await fetch(`/api/audio/delete/${filename}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.success) {
                this.loadBackgroundMusicFiles(roomId);
            } else {
                this.showToast('删除音频文件失败', 'error');
            }
        } catch (error) {
            this.showToast('删除音频文件失败: 网络错误', 'error');
        }
    }

    selectBackgroundMusic(filename, roomId, musicName, size) {
        const dialog = document.querySelector('.settings-dialog-overlay');
        const currentSelectionDisplay = document.getElementById('current-selection-display');
        const currentUrlInput = document.getElementById('current-url-input');
        const currentMusicNameInput = document.getElementById('current-music-name-input');
        const currentSizeInput = document.getElementById('current-size-input');
        
        if (currentSelectionDisplay && currentUrlInput) {
            const url = `/static/audio/${filename}`;
            currentUrlInput.value = url;
            currentMusicNameInput.value = musicName;
            currentSizeInput.value = size;
            
            const displayHtml = `
                <div class="audio-file-item">
                    <div class="audio-file-info">
                        <span class="audio-file-index">-</span>
                        <div class="audio-file-details">
                            <span class="audio-file-name">${musicName}</span>
                            <span class="audio-file-path">${this.formatBackgroundMusicDisplay(url)}</span>
                        </div>
                        <span class="audio-file-size">${this.formatFileSize(size)}</span>
                    </div>
                    <button class="audio-file-select-btn audio-file-clear-btn" id="clear-selection-btn" style="display: inline-block;">清除</button>
                </div>
            `;
            currentSelectionDisplay.innerHTML = displayHtml;
            
            const clearBtn = document.getElementById('clear-selection-btn');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => {
                    const currentSelectionDisplay = document.getElementById('current-selection-display');
                    const currentUrlInput = document.getElementById('current-url-input');
                    const currentMusicNameInput = document.getElementById('current-music-name-input');
                    const currentSizeInput = document.getElementById('current-size-input');
                    const clearBtn = document.getElementById('clear-selection-btn');
                    
                    currentUrlInput.value = '';
                    currentMusicNameInput.value = '';
                    currentSizeInput.value = 0;
                    
                    const displayHtml = `
                        <div class="audio-file-item">
                            <div class="audio-file-info">
                                <span class="audio-file-index">-</span>
                                <div class="audio-file-details">
                                    <span class="audio-file-name">未选择</span>
                                    <span class="audio-file-path"></span>
                                </div>
                                <span class="audio-file-size"></span>
                            </div>
                        </div>
                    `;
                    currentSelectionDisplay.innerHTML = displayHtml;
                });
            }
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatBackgroundMusicDisplay(url) {
        if (!url) return '';
        
        const urlObj = new URL(url, window.location.origin);
        const pathname = urlObj.pathname;
        const filename = pathname.split('/').pop();
        const ext = filename.includes('.') ? '.' + filename.split('.').pop() : '';
        const nameWithoutExt = filename.replace(ext, '');
        
        let shortPath = pathname;
        if (pathname.length > 10) {
            const first3 = pathname.substring(0, 3);
            const last3 = nameWithoutExt.substring(nameWithoutExt.length - 3);
            shortPath = `${first3}...${last3}${ext}`;
        }
        
        return shortPath;
    }

    switchAudio(roomId) {
        this.app.socket.emit('switch_audio', { room_id: roomId });
    }

    toggleBroadcast() {
        this.app.socket.emit('toggle_broadcast', { enable: !this.app.broadcastMode });
    }
}