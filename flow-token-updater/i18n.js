// i18n.js - 国际化模块
const i18n = {
    currentLang: 'zh-CN',

    translations: {
        'zh-CN': {
            // 通用
            lang: '语言',
            save: '保存',
            cancel: '取消',
            clear: '清除',
            back: '返回',
            close: '关闭',
            copy: '复制',
            copied: '已复制',
            copyFailed: '复制失败',

            // popup.html
            serverStatus: {
                checking: '检测中...',
                online: '服务器在线',
                offline: '服务器离线',
                error: '服务器异常',
                notConfigured: '未配置服务器'
            },
            form: {
                serverUrl: '本地服务器',
                serverUrlPlaceholder: 'http://127.0.0.1:8765/token',
                serverUrlHint: '运行 flow-token-server 后填入',
                refreshInterval: '刷新间隔',
                refreshIntervalHint: '单位：分钟',
                saveConfig: '保存配置',
                fetchNow: '立即获取'
            },
            status: {
                configSaved: '✅ 配置已保存',
                pleaseFillServer: '请填写本地服务器地址',
                invalidInterval: '刷新间隔必须在 1-1440 分钟之间',
                pleaseSaveConfig: '请先填写并保存配置',
                fetching: '⏳ 正在获取 Token...',
                fetchSuccess: '✅ Token 获取成功',
                fetchFailed: '❌ 获取失败',
                unknownError: '未知错误'
            },
            token: {
                history: 'Token 历史',
                noRecords: '暂无提取记录',
                chars: '字符',
                clearHistory: '清除历史',
                viewLogs: '查看日志'
            },

            // logs.html
            logs: {
                title: '运行日志',
                noLogs: '暂无日志记录'
            },

            // popup.html
            popup: {
                title: 'Flow Token Updater'
            }
        },
        'en-US': {
            // Common
            lang: 'Language',
            save: 'Save',
            cancel: 'Cancel',
            clear: 'Clear',
            back: 'Back',
            close: 'Close',
            copy: 'Copy',
            copied: 'Copied',
            copyFailed: 'Copy Failed',

            // popup.html
            serverStatus: {
                checking: 'Checking...',
                online: 'Server Online',
                offline: 'Server Offline',
                error: 'Server Error',
                notConfigured: 'Server Not Configured'
            },
            form: {
                serverUrl: 'Local Server',
                serverUrlPlaceholder: 'http://127.0.0.1:8765/token',
                serverUrlHint: 'Fill after running flow-token-server',
                refreshInterval: 'Refresh Interval',
                refreshIntervalHint: 'Unit: minutes',
                saveConfig: 'Save Config',
                fetchNow: 'Fetch Now'
            },
            status: {
                configSaved: '✅ Config Saved',
                pleaseFillServer: 'Please fill in server URL',
                invalidInterval: 'Interval must be between 1-1440 minutes',
                pleaseSaveConfig: 'Please save config first',
                fetching: '⏳ Fetching Token...',
                fetchSuccess: '✅ Token Fetched',
                fetchFailed: '❌ Fetch Failed',
                unknownError: 'Unknown Error'
            },
            token: {
                history: 'Token History',
                noRecords: 'No records yet',
                chars: 'chars',
                clearHistory: 'Clear History',
                viewLogs: 'View Logs'
            },

            // logs.html
            logs: {
                title: 'Logs',
                noLogs: 'No logs yet'
            },

            // popup.html
            popup: {
                title: 'Flow Token Updater'
            }
        }
    },

    // 获取翻译文本
    t(key) {
        const keys = key.split('.');
        let value = this.translations[this.currentLang];

        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                return key;
            }
        }

        return value;
    },

    // 设置语言
    setLang(lang) {
        if (this.translations[lang]) {
            this.currentLang = lang;
            this.updatePage();
            this.saveLang(lang);
        }
    },

    // 获取当前语言
    getLang() {
        return this.currentLang;
    },

    // 保存语言设置
    async saveLang(lang) {
        try {
            await chrome.storage.sync.set({ language: lang });
        } catch (e) {
            console.error('Failed to save language:', e);
        }
    },

    // 加载语言设置
    async loadLang() {
        try {
            const result = await chrome.storage.sync.get(['language']);
            if (result.language && this.translations[result.language]) {
                this.currentLang = result.language;
            } else {
                // 尝试检测浏览器语言
                const browserLang = navigator.language;
                if (browserLang.startsWith('zh')) {
                    this.currentLang = 'zh-CN';
                } else {
                    this.currentLang = 'en-US';
                }
            }
        } catch (e) {
            console.error('Failed to load language:', e);
        }
        return this.currentLang;
    },

    // 更新页面文本
    updatePage() {
        // 更新所有带 data-i18n 属性的元素
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = this.t(key);

            if (translation) {
                if (el.tagName === 'INPUT') {
                    el.placeholder = translation;
                } else {
                    el.textContent = translation;
                }
            }
        });

        // 更新 document.title
        const titleKey = document.body.getAttribute('data-i18n-title');
        if (titleKey) {
            document.title = this.t(titleKey);
        }
    },

    // 初始化语言切换器
    initLangSwitcher(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const langBtn = document.createElement('button');
        langBtn.className = 'lang-switch';
        langBtn.innerHTML = this.currentLang === 'zh-CN' ? '中' : 'EN';
        langBtn.title = this.t('lang');

        langBtn.addEventListener('click', () => {
            const newLang = this.currentLang === 'zh-CN' ? 'en-US' : 'zh-CN';
            this.setLang(newLang);
            langBtn.innerHTML = newLang === 'zh-CN' ? '中' : 'EN';
            // 触发自定义事件让其他组件更新
            window.dispatchEvent(new CustomEvent('langchange', { detail: { lang: newLang } }));
        });

        container.appendChild(langBtn);
    }
};

// 导出给其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = i18n;
}