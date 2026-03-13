// logs.js - 日志查看页面

document.addEventListener('DOMContentLoaded', async () => {
    // 初始化 i18n
    await i18n.loadLang();
    i18n.updatePage();
    i18n.initLangSwitcher('langContainer');

    // 监听语言变化
    window.addEventListener('langchange', () => {
        loadLogs();
    });

    loadLogs();

    document.getElementById('backBtn').addEventListener('click', () => {
        window.location.href = 'popup.html';
    });

    document.getElementById('clearBtn').addEventListener('click', async () => {
        await chrome.runtime.sendMessage({ action: 'clearLogs' });
        loadLogs();
    });

    setInterval(loadLogs, 3000);
});

async function loadLogs() {
    const response = await chrome.runtime.sendMessage({ action: 'getLogs' });

    if (response && response.logs) {
        const logList = document.getElementById('logList');

        if (response.logs.length === 0) {
            logList.innerHTML = `
                <div class="empty">
                    <div class="empty-icon">📭</div>
                    <span>${i18n.t('logs.noLogs')}</span>
                </div>
            `;
            return;
        }

        logList.innerHTML = response.logs.map(log => {
            const time = new Date(log.timestamp).toLocaleString(i18n.getLang() === 'zh-CN' ? 'zh-CN' : 'en-US');
            const details = log.details
                ? `<div class="log-details">${JSON.stringify(log.details, null, 2)}</div>`
                : '';

            return `
                <div class="log-item">
                    <div class="log-time">${time}</div>
                    <span class="log-level ${log.level}">${log.level}</span>
                    <span class="log-message">${log.message}</span>
                    ${details}
                </div>
            `;
        }).join('');
    }
}