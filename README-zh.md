# Flow Image CLI

English README: [README.md](./README.md)

Flow 图片生成命令行工具，支持：

- 文生图 / 图生图
- 2K / 4K 放大（`-u 2k` / `-u 4k`）
- 放大失败自动降级为原图并保底保存
- 本机浏览器验证码模式（`personal`）
- 本地 Token 接收服务（配合 `flow-token-updater`）

> 项目说明：
> - 本项目受 [Flow2API](https://github.com/TheSmallHanCat/flow2api) 启发制作。
> - `flow-token-updater` 受 [Flow2API-Token-Updater](https://github.com/TheSmallHanCat/Flow2API-Token-Updater) 启发。

## 项目定位

本仓库是本地使用的轻量级生图实现：

- 聚焦 Flow 生图主链路（ST/AT、生成、放大）
- 提供 CLI + 本地辅助工具，不是完整平台服务

## 使用前提（必须）

- 能正常登录 Flow：<https://labs.google/fx>
- 账号具备生图权限
- 使用 `-u 4k` 时需有对应订阅/权限

## 目录结构

```text
flow-image-cli/
├── flow_cli/                # CLI 主代码
├── flow-token-updater/      # 浏览器插件（推荐）
├── flow_token_server.py     # 本地 Token 接收服务
├── config.toml              # 配置模板
└── README.md
```

## 安装

```bash
cd flow-image-cli
pip install -r requirements.txt
pip install -e .
```

### 安装 Playwright（`personal` 模式必需）

```bash
pip install playwright
python -m playwright install chromium
```

## 推荐 Token 流程：flow-token-updater

推荐使用仓库内插件自动同步 ST，避免手工复制。

### 1) 启动本地 Token 服务

```bash
python flow_token_server.py
```

默认地址：`http://127.0.0.1:8765/token`

### 2) Chrome 加载插件

1. 打开 `chrome://extensions/`
2. 启用开发者模式
3. 点击“加载已解压的扩展程序”
4. 选择 `/flow-image-cli/flow-token-updater`

### 3) 配置插件

1. 打开插件 popup
2. 服务器地址填写 `http://127.0.0.1:8765/token`
3. 保存并点击“立即获取”

ST 会写入 `~/.flow-cli/token.json`。

## 配置

配置文件：`~/.flow-cli/config.toml`

```toml
[flow]
labs_base_url = "https://labs.google/fx/api"
api_base_url = "https://aisandbox-pa.googleapis.com/v1"
timeout = 120
max_retries = 3

[output]
output_dir = "output"

[captcha]
method = "personal" # personal / none
personal_headless = false
personal_timeout = 90
personal_settle_seconds = 2.0

[debug]
enabled = false
```

Token 文件：`~/.flow-cli/token.json`

## 打码模式说明

支持的 `captcha.method`：

- `personal`：使用本机浏览器执行验证码（需要 Playwright）
- `none`：不主动处理验证码（遇到验证码场景可能失败）

默认 `personal_headless = false`（可视化浏览器模式），对部分账号更稳定。若要静默运行可改为 `true`。

## 交互式脚本

```bash
python interactive_generate.py
```

支持配置：

- 模型族 / 画幅
- 分辨率（`none/2k/4k`）
- 提示词
- 参考图路径
- 默认输出路径
- 语言模式（`中文 / English / 双语`）

默认输出使用时间戳模板：`output/flow_{timestamp}.png`

## CLI 使用示例

### 登录

```bash
flow-cli login --st "your-session-token"
```

### 基础命令

```bash
flow-cli models
flow-cli credits
flow-cli config
```

### 生图

```bash
# 文生图
flow-cli gen "a cinematic cat in neon city"

# 指定模型 + 输出
flow-cli gen "mountain landscape" -m gemini-3.1-flash-image-landscape -o output\landscape.png

# 图生图
flow-cli gen "convert to watercolor style" -r input.jpg -o output\watercolor.png
```

### 2K / 4K 放大

```bash
# 放大到 2K
flow-cli gen "a cat" -m gemini-3.1-flash-image-landscape -u 2k -o output\cat_2k.png

# 放大到 4K（需订阅/权限）
flow-cli gen "a cat" -m gemini-3.1-flash-image-landscape -u 4k -o output\cat_4k.png
```

放大失败时会自动降级保存原图到目标路径。

## Python API 示例

### 文生图

```python
import asyncio
from flow_cli.client import ImageGenerator

async def main():
    g = ImageGenerator()
    path = await g.generate(
        prompt="a cinematic cat",
        model="gemini-3.1-flash-image-landscape",
        output_path="output/api_basic.png",
    )
    print(path)

asyncio.run(main())
```

### 图生图 + 2K

```python
import asyncio
from pathlib import Path
from flow_cli.client import ImageGenerator

async def main():
    g = ImageGenerator()
    path = await g.generate(
        prompt="convert to watercolor",
        model="gemini-3.1-flash-image-landscape",
        reference_image=Path("input.jpg").read_bytes(),
        output_path="output/api_img2img_2k.png",
        upscale="2k",
    )
    print(path)

asyncio.run(main())
```

## 常见问题 (FAQ)

### Q1: 如何获取 2K 图片？

使用 `-u 2k` 参数。
`-u 4k` 需要账户有对应的订阅/权限。
放大失败时，会自动降级为原图并保存。

### Q2: 遇到 `reCAPTCHA evaluation failed` 错误怎么办？

1. 确保 `captcha.method = "personal"`
2. 确保已安装 Playwright 和 Chromium
3. 确保浏览器能访问 Google Flow 并已登录

### Q3: 遇到 401/500 错误怎么办？

- 401：通常是 AT 过期，程序会自动刷新并重试
- 500：上游服务偶发问题，建议重试或更换模型（推荐使用 `gemini-3.1-flash-image-*`）

### Q4: 配置文件不生效？配置方法设置了但没效果？

CLI 默认从 `~/.flow-cli/config.toml`（用户主目录）读取配置，而非项目根目录的 `config.toml`。

**解决方案：**
1. 将配置文件复制到默认位置：
   ```bash
   mkdir -p ~/.flow-cli
   cp <你的项目路径>/config.toml ~/.flow-cli/config.toml
   ```
2. 或使用环境变量：
   ```bash
   export FLOW_CONFIG=/path/to/your/config.toml
   ```

### Q5: 如何更新/登录新的 Session Token？

```bash
flow-cli login --st "你的新session-token"
```

你可以从 Flow Token 浏览器插件获取 ST。

### Q6: personal 验证码模式下 Playwright/浏览器问题？

1. 安装 Playwright：`pip install playwright && python -m playwright install chromium`
2. 如果浏览器没有自动打开，检查是否有其他 Chrome 实例正在使用该 profile
3. 如果 headless 模式有问题，尝试在配置中设置 `personal_headless = false`
4. 浏览器 profile 存储在 `~/.flow-cli/browser-profile`

### Q7: 图片生成成功但文件没保存？

- 检查输出目录是否存在且可写
- 确保磁盘空间充足
- 开启 debug 模式查看更多详情（在配置中设置 `debug.enabled = true`）

## 许可证

MIT，详见 [LICENSE](./LICENSE)。

