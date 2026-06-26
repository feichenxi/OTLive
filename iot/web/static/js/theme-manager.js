class ThemeManager {
    constructor() {
        this.currentTheme = 'smart-home';
        this.init();
    }

    init() {
        this.loadTheme(this.currentTheme);
        this.bindEvents();
    }

    bindEvents() {
        // 场景按钮点击事件
        const sceneButtons = document.querySelectorAll('.scene-button');
        sceneButtons.forEach(button => {
            button.addEventListener('click', () => {
                const scene = button.getAttribute('data-scene');
                this.activateScene(scene);
            });
        });

        // 安全按钮点击事件
        const securityBtns = document.querySelectorAll('.security-btn');
        securityBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.toggleSecurity(btn);
            });
        });
    }

    loadTheme(themeName) {
        const stylesheet = document.getElementById('theme-stylesheet');
        if (stylesheet) {
            stylesheet.href = '';
        }
        
        document.body.setAttribute('data-theme', themeName);
    }

    activateScene(scene) {
        // 场景激活，不显示提示
    }

    toggleSecurity(button) {
        const isActive = button.classList.contains('active');
        const isDanger = button.classList.contains('danger');

        // 移除所有安全按钮的active状态
        document.querySelectorAll('.security-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // 激活当前按钮
        button.classList.add('active');
    }

    getSceneName(scene) {
        const names = {
            'welcome': '温馨回家',
            'away': '安全离家',
            'temperature': '全屋恒温',
            'dehumidify': '全屋除湿',
            'ventilation': '全屋通风',
            'more': '更多场景'
        };
        return names[scene] || scene;
    }

    showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'theme-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 12px 20px;
            background: rgba(64, 158, 255, 0.9);
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 10001;
            animation: slideIn 0.3s ease-out;
            font-weight: 600;
            backdrop-filter: blur(5px);
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }
}

const themeManager = new ThemeManager();