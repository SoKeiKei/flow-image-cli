# Flow Token Updater

自动提取 Google Flow `__Secure-next-auth.session-token` 并同步到本地的 Chrome 插件。

## 功能特性

- 🔄 自动定时提取 Token（可配置间隔）
- 📋 保留最近 10 个提取的 Token 记录
- 📋 一键复制 Token 到剪贴板
- 🔍 查看运行日志
- 🚫 自动去重相同的 Token
- 📺 支持本地服务器同步

## 依赖

### 1. Chrome 插件

需要先安装本插件，详见下方安装步骤。

### 2. 本地服务

需要运行 `flow_token_server.py` 作为本地 Token 接收服务：

```bash
python flow_token_server.py
```

默认监听：`http://127.0.0.1:8765/token`

## 安装步骤

### Chrome 插件

1. **打开扩展程序页面**

   在 Chrome 地址栏输入：`chrome://extensions/`

2. **开启开发者模式**

   点击页面右上角的「开发者模式」开关。

3. **载入插件**

   - 方式一：直接将 `flow-token-updater` 文件夹拖拽到浏览器页面
   - 方式二：点击「加载已解压的扩展程序」，选择 `flow-token-updater` 目录

### 启动本地服务

```bash
cd D:\Code\tools\flow-image-cli
python flow_token_server.py
```

## 使用指南

### 1. 配置插件

1. 点击浏览器工具栏的插件图标
2. 在「本地服务器地址」中填写：`http://127.0.0.1:8765/token`
3. 设置刷新间隔（默认 60 分钟）
4. 点击「保存配置」

### 2. 手动获取 Token

点击「立即获取」按钮，插件会：

1. 打开 Google Flow 认证页面
2. 提取 `__Secure-next-auth.session-token`
3. 发送到本地服务器保存到 `~/.flow-cli/token.json`

### 3. 查看 Token 列表

- 每次成功提取的 Token 会自动保存
- 点击任意条目可展开查看完整 Token
- 点击「复制」按钮一键复制
- 点击「清除」删除所有历史记录

### 4. 查看运行日志

点击「查看日志」可查看插件的详细运行记录。

## 文件说明

```
flow-token-updater/
├── manifest.json       # 插件配置
├── background.js       # 后台脚本
├── popup.html          # 插件界面
├── popup.js            # 界面脚本
├── logs.html           # 日志页面
├── logs.js             # 日志脚本
└── icon*.png           # 插件图标
```

```
flow-image-cli/
├── flow_token_server.py  # 本地 Token 接收服务
└── ...
```

## 工作原理

1. **定时任务**：根据配置的间隔，插件自动触发
2. **页面访问**：在后台打开 `https://labs.google/fx/vi/tools/flow`
3. **Cookie 提取**：从页面提取 `__Secure-next-auth.session-token`
4. **本地同步**：发送到本地服务器，保存到 `~/.flow-cli/token.json`
5. **Token 列表**：保存到 Chrome 本地存储，可在插件界面查看

## 注意事项

- 确保已登录 Google 账号
- 本地服务需要在插件获取 Token 前启动
- Token 文件路径：`~/.flow-cli/token.json`
- 插件会自动去除重复的 Token

## 作者

📺 [细Kei](https://space.bilibili.com/3546772855064749)