// popup.js - Flow Token Updater

// 检测服务器状态
async function checkServerStatus() {
    const statusEl = document.getElementById('serverStatus');
    const config = await chrome.storage.sync.get(['localServerUrl']);

    if (!config.localServerUrl) {
        statusEl.innerHTML = `<span class="status-dot offline"></span><span class="status-text">${i18n.t('serverStatus.notConfigured')}</span>`;
        return;
    }

    const serverUrl = config.localServerUrl.replace('/token', '/health');

    try {
        const response = await fetch(serverUrl, { method: 'GET' });
        if (response.ok) {
            statusEl.innerHTML = `<span class="status-dot online"></span><span class="status-text">${i18n.t('serverStatus.online')}</span>`;
        } else {
            statusEl.innerHTML = `<span class="status-dot offline"></span><span class="status-text">${i18n.t('serverStatus.error')}</span>`;
        }
    } catch (e) {
        statusEl.innerHTML = `<span class="status-dot offline"></span><span class="status-text">${i18n.t('serverStatus.offline')}</span>`;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // 初始化 i18n
    await i18n.loadLang();
    i18n.updatePage();
    i18n.initLangSwitcher('langContainer');

    // 监听语言变化
    window.addEventListener('langchange', () => {
        checkServerStatus();
        loadTokenList();
    });

    // 检测服务器状态
    checkServerStatus();

    // 加载已保存的配置
    const config = await chrome.storage.sync.get(['localServerUrl', 'refreshInterval']);

    if (config.localServerUrl) {
        document.getElementById('localServerUrl').value = config.localServerUrl;
    }
    if (config.refreshInterval) {
        document.getElementById('refreshInterval').value = config.refreshInterval;
    }

    // 延迟加载 Token 列表
    requestAnimationFrame(() => {
        setTimeout(loadTokenList, 50);
    });

    // 保存配置
    document.getElementById('saveBtn').addEventListener('click', async () => {
        const localServerUrl = document.getElementById('localServerUrl').value.trim();
        const refreshInterval = parseInt(document.getElementById('refreshInterval').value);

        if (!localServerUrl) {
            showStatus(i18n.t('status.pleaseFillServer'), 'error');
            return;
        }

        if (refreshInterval < 1 || refreshInterval > 1440) {
            showStatus(i18n.t('status.invalidInterval'), 'error');
            return;
        }

        await chrome.storage.sync.set({ localServerUrl, refreshInterval });

        chrome.runtime.sendMessage({
            action: 'updateConfig',
            config: { localServerUrl, refreshInterval }
        });

        showStatus(i18n.t('status.configSaved'), 'success');

        // 保存后检测服务器状态
        setTimeout(checkServerStatus, 500);
    });

    // 立即获取
    document.getElementById('testBtn').addEventListener('click', async () => {
        const localServerUrl = document.getElementById('localServerUrl').value.trim();

        if (!localServerUrl) {
            showStatus(i18n.t('status.pleaseSaveConfig'), 'error');
            return;
        }

        showStatus(i18n.t('status.fetching'), 'info');

        chrome.runtime.sendMessage({
            action: 'testNow'
        }, (response) => {
            if (response && response.success) {
                loadTokenList();
                showStatus(`${i18n.t('status.fetchSuccess')}\n${response.message}`, 'success');
            } else {
                showStatus(`${i18n.t('status.fetchFailed')}: ${response ? response.error : i18n.t('status.unknownError')}`, 'error');
            }
        });
    });

    // 查看日志
    document.getElementById('logsBtn').addEventListener('click', () => {
        window.location.href = 'logs.html';
    });

    // 清除 Token
    document.getElementById('clearTokensBtn').addEventListener('click', async () => {
        await chrome.storage.local.set({ tokenHistory: [] });
        loadTokenList();
    });
});

function showStatus(message, type) {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;

    setTimeout(() => {
        statusEl.style.display = 'none';
    }, 4000);
}

// 加载 Token 列表
async function loadTokenList() {
    const { tokenHistory = [] } = await chrome.storage.local.get(['tokenHistory']);
    const tokenListEl = document.getElementById('tokenList');

    if (tokenHistory.length === 0) {
        tokenListEl.innerHTML = `
            <div class="empty">
                <div class="empty-icon">📭</div>
                <span data-i18n="token.noRecords">${i18n.t('token.noRecords')}</span>
            </div>
        `;
        return;
    }

    tokenListEl.innerHTML = tokenHistory.map((item) => {
        const date = new Date(item.time);
        const timeStr = date.toLocaleString(i18n.getLang() === 'zh-CN' ? 'zh-CN' : 'en-US', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const escapedToken = item.token.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const copyText = i18n.t('copy');

        return `
            <div class="token-item">
                <div class="token-header">
                    <span class="token-time">${timeStr}</span>
                    <span class="token-length">${item.token.length} ${i18n.t('token.chars')}</span>
                </div>
                <div class="token-preview">${item.token.substring(0, 28)}...</div>
                <div class="token-full">${escapedToken}</div>
                <button class="copy-btn" data-token="${encodeURIComponent(item.token)}">${copyText}</button>
            </div>
        `;
    }).join('');

    // 事件委托：展开/收起
    tokenListEl.addEventListener('click', (e) => {
        const item = e.target.closest('.token-item');
        if (item && !e.target.classList.contains('copy-btn')) {
            item.classList.toggle('expanded');
        }
    });

    // 事件委托：复制
    tokenListEl.addEventListener('click', (e) => {
        if (e.target.classList.contains('copy-btn')) {
            const token = decodeURIComponent(e.target.dataset.token);
            copyToken(e.target, token);
        }
    });
}

// 复制 Token
function copyToken(btn, token) {
    navigator.clipboard.writeText(token).then(() => {
        const copiedText = i18n.t('copied');
        btn.textContent = copiedText;
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = i18n.t('copy');
            btn.classList.remove('copied');
        }, 2000);
    }).catch(() => {
        btn.textContent = i18n.t('copyFailed');
    });
}