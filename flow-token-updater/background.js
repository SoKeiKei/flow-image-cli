// background.js - Flow Token Updater 后台脚本

// 定时器名称
const ALARM_NAME = 'flowTokenRefresh';

// 日志系统
const Logger = {
    async log(level, message, details = null) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            details
        };

        console.log(`[${level}] ${message}`, details || '');

        const { logs = [] } = await chrome.storage.local.get(['logs']);
        logs.unshift(logEntry);

        if (logs.length > 50) {
            logs.splice(50);
        }

        await chrome.storage.local.set({ logs });
    },

    info(message, details) {
        return this.log('INFO', message, details);
    },

    error(message, details) {
        return this.log('ERROR', message, details);
    },

    success(message, details) {
        return this.log('SUCCESS', message, details);
    },

    async getLogs() {
        const { logs = [] } = await chrome.storage.local.get(['logs']);
        return logs;
    },

    async clearLogs() {
        await chrome.storage.local.set({ logs: [] });
    }
};

// Token 历史记录管理
const MAX_TOKEN_HISTORY = 10;

async function saveTokenToHistory(token) {
    const { tokenHistory = [] } = await chrome.storage.local.get(['tokenHistory']);

    // 检查是否已存在相同的 token（去重）
    const exists = tokenHistory.some(item => item.token === token);
    if (exists) {
        await Logger.info('Token 已存在，跳过保存');
        return;
    }

    tokenHistory.unshift({
        token: token,
        time: new Date().toISOString()
    });

    // 只保留最新 10 个
    if (tokenHistory.length > MAX_TOKEN_HISTORY) {
        tokenHistory.length = MAX_TOKEN_HISTORY;
    }

    await chrome.storage.local.set({ tokenHistory });
}

// 初始化：设置定时器
chrome.runtime.onInstalled.addListener(async () => {
    await Logger.info('Flow Token Updater installed');
    await setupAlarm();
});

// 监听来自popup的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'updateConfig') {
        setupAlarm().then(async () => {
            await Logger.info('Config updated, alarm reset');
        });
    } else if (request.action === 'testNow') {
        extractToken().then((result) => {
            sendResponse(result);
        }).catch((error) => {
            sendResponse({ success: false, error: error.message });
        });
        return true;
    } else if (request.action === 'getLogs') {
        Logger.getLogs().then((logs) => {
            sendResponse({ success: true, logs });
        });
        return true;
    } else if (request.action === 'clearLogs') {
        Logger.clearLogs().then(() => {
            sendResponse({ success: true });
        });
        return true;
    } else if (request.action === 'getToken') {
        extractToken().then((result) => {
            sendResponse(result);
        }).catch((error) => {
            sendResponse({ success: false, error: error.message });
        });
        return true;
    }
});

// 监听定时器触发
chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === ALARM_NAME) {
        await Logger.info('Alarm triggered, extracting token...');
        const result = await extractToken();

        // 可以选择启用/禁用通知
        // 如果需要通知，可以取消注释下面这段代码
        /*
        if (result.success) {
            const title = '✅ Token已更新';
            const message = result.message || 'Token已成功同步到本地';

            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon48.png',
                title: title,
                message: message
            });
        } else {
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon48.png',
                title: '❌ Token同步失败',
                message: result.error || '未知错误'
            });
        }
        */
    }
});

// 设置定时器
async function setupAlarm() {
    await chrome.alarms.clear(ALARM_NAME);

    const config = await chrome.storage.sync.get(['refreshInterval']);
    const intervalMinutes = config.refreshInterval || 60;

    chrome.alarms.create(ALARM_NAME, {
        periodInMinutes: intervalMinutes
    });

    await Logger.info(`Alarm set to ${intervalMinutes} minutes`);
}

// 提取token并发送到本地服务器
async function extractToken() {
    let tab = null;

    try {
        await Logger.info('开始提取 Token...');

        const config = await chrome.storage.sync.get(['localServerUrl']);

        if (!config.localServerUrl) {
            await Logger.error('本地服务器地址未设置');
            return { success: false, error: '请先配置本地服务器地址' };
        }

        await Logger.info('配置已加载', { serverUrl: config.localServerUrl });

        // 1. 打开 Google Flow 页面（后台）
        // 注意：需要访问 labs.google 的特定认证页面才能获取 __Secure-next-auth.session-token
        await Logger.info('正在打开 Google Flow 认证页面...');
        tab = await chrome.tabs.create({
            url: 'https://labs.google/fx/vi/tools/flow',
            active: false
        });

        await Logger.info('页面已创建，等待加载...', { tabId: tab.id });

        // 等待页面完全加载
        await new Promise((resolve) => {
            const listener = (tabId, changeInfo) => {
                if (tabId === tab.id && changeInfo.status === 'complete') {
                    chrome.tabs.onUpdated.removeListener(listener);
                    resolve();
                }
            };
            chrome.tabs.onUpdated.addListener(listener);
        });

        await Logger.info('页面加载完成，等待 JavaScript 执行...');

        // 等待 5 秒确保 JavaScript 完全执行
        await new Promise(resolve => setTimeout(resolve, 5000));

        await Logger.info('开始提取 Cookies...');

        // 2. 获取 session-token
        let sessionToken = null;
        let allCookiesFound = [];

        try {
            // 方法1: 从当前标签页 URL 获取 cookies
            const tabCookies = await chrome.cookies.getAll({ url: 'https://labs.google/fx/vi/tools/flow' });
            allCookiesFound.push(...tabCookies);
            await Logger.info(`从 labs.google/fx/vi/tools/flow 找到 ${tabCookies.length} 个 cookies`);

            // 方法2: 获取 labs.google 域名下的所有 cookies
            const labsCookies = await chrome.cookies.getAll({ domain: 'labs.google' });
            allCookiesFound.push(...labsCookies);
            await Logger.info(`从 labs.google 域名找到 ${labsCookies.length} 个 cookies`);

            // 方法3: 获取 google.com 域名下的 cookies
            const googleCookies = await chrome.cookies.getAll({ domain: '.google.com' });
            allCookiesFound.push(...googleCookies);
            await Logger.info(`从 .google.com 域名找到 ${googleCookies.length} 个 cookies`);

        } catch (err) {
            await Logger.error('获取 cookies 失败', { error: err.message });
        }

        // 去重
        const uniqueCookies = Array.from(
            new Map(allCookiesFound.map(c => [c.name + c.domain, c])).values()
        );

        await Logger.info(`总共找到 ${uniqueCookies.length} 个唯一 cookies`);

        // 查找 __Secure-next-auth.session-token
        for (const cookie of uniqueCookies) {
            if (cookie.name === '__Secure-next-auth.session-token' && !sessionToken) {
                sessionToken = cookie.value;
                await Logger.success('找到 session-token', {
                    domain: cookie.domain,
                    path: cookie.path,
                    length: sessionToken.length
                });
                break;
            }
        }

        // 关闭标签页
        if (tab) {
            await chrome.tabs.remove(tab.id);
            await Logger.info('标签页已关闭');
        }

        if (!sessionToken) {
            await Logger.error('未找到 session-token', {
                foundCookies: uniqueCookies.map(c => ({
                    name: c.name,
                    domain: c.domain
                }))
            });

            return {
                success: false,
                error: '未找到 session-token。请确保已登录 Google Flow。'
            };
        }

        await Logger.info('Session-token 提取成功', { tokenLength: sessionToken.length });

        // 3. 发送到本地服务器
        await Logger.info('正在发送到本地服务器...', { url: config.localServerUrl });

        try {
            const response = await fetch(config.localServerUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_token: sessionToken
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                await Logger.error('服务器错误', {
                    status: response.status,
                    error: errorText
                });
                return { success: false, error: `服务器错误: ${response.status}` };
            }

            const result = await response.json();

            if (result.success) {
                await Logger.success('✅ Token 已保存到本地', result);
                // 保存到历史记录
                await saveTokenToHistory(sessionToken);
            }

            return {
                success: true,
                message: result.message || 'Token 更新成功',
                token: sessionToken.substring(0, 20) + '...',
                tokenData: sessionToken
            };

        } catch (fetchError) {
            await Logger.error('发送失败', {
                error: fetchError.message,
                hint: '请确保本地服务器正在运行，且地址正确'
            });
            return {
                success: false,
                error: `发送失败: ${fetchError.message}. 请确保服务器正在运行.`
            };
        }

    } catch (error) {
        await Logger.error('提取过程出错', {
            error: error.message,
            stack: error.stack
        });

        if (tab) {
            try {
                await chrome.tabs.remove(tab.id);
            } catch (e) {
                // 忽略关闭标签页的错误
            }
        }

        return { success: false, error: error.message };
    }
}