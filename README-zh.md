# Flow Image CLI：不只有 Image，现已支持视频生成

English README: [README.md](./README.md)

供终端和 Agent 窗口直接调用的 Google Flow 图片与视频生成工具。

## 功能

- 新版 Flow 网址上的文生图；旧网址仍保留图生图和多参考图编辑入口
- Nano Banana 2 Lite、Nano Banana 2、Nano Banana Pro
- 新版 `flow.google.com` 的文生视频、素材参考视频、首帧视频和首尾帧视频
- Omni 1.1 Flash（命令别名 `omni-flash`）与 Veo 3.1 Lite / Fast / Quality
- 固定复用同一个 Flow 项目，避免每次生成都新建项目
- 真实 Chrome 登录，并保留原有 Session Token 生图方式
- Chrome Token 插件默认连接本机服务并自动检查在线状态
- 图片 2K / 4K 放大，失败时保底保存原图

v1.3.0 已补上新版 Flow 网址的文生图通道，并更新当前图片、视频模型清单。

> 本项目是非官方工具，会调用 Google Flow 网页能力。模型、额度和页面行为可能随账号、地区或 Flow 更新而变化。生成会消耗你的 Flow 额度。

## 为什么使用这个项目

这个项目专注于终端和 Agent 窗口里的日常生成：

- 安装后直接使用 `flow-cli`，Agent 不需要理解多套服务和接口
- 把登录、图片和视频统一到同一个命令入口
- 可以固定复用一个 Flow 项目，连续对话生成时不会把项目列表弄乱
- 默认只生成一个结果、4 秒、720p；模型必须显式指定，所有配置都会在提交前回读核对
- 保留本机 Token 服务和 Chrome 插件，兼容原有图片生成方式

目标是在 Agent 窗口里说一句，就直接生成并返回文件。

## 安装

需要 Python 3.11+ 和 Chrome。

### 让 Agent 快速安装

复制下面这句话发给 Agent：

```text
帮我安装 https://github.com/SoKeiKei/flow-image-cli 并检测是否缺少依赖
```

### 手动安装

```bash
git clone https://github.com/SoKeiKei/flow-image-cli.git
cd flow-image-cli
py -m pip install -e .
```

确认安装：

```bash
flow-cli --help
flow-cli media-models
```

## 推荐登录方式

首次使用最新图片或视频命令时运行：

```bash
flow-cli auth login --browser chrome
```

命令会打开真实 Chrome。完成 Google 登录后，可以在后续终端或 Agent 窗口中复用登录状态。

```bash
flow-cli auth status
```

## 固定复用一个 Flow 项目

从 Flow 项目网址中复制项目 ID，然后只需设置一次：

```bash
flow-cli project use <Flow 项目 ID>
flow-cli project show
```

之后 `image t2i`、`image i2i`、`video t2v`、`video i2v`、`video r2v` 和 `video extend` 会默认复用这个项目。对 `video extend` 来说，固定项目必须拥有对应的媒体 ID。命令中显式传入 `--project` 时，以该次指定为准。

取消固定项目不会删除 Flow 网页中的项目：

```bash
flow-cli project clear
```

固定设置保存在 `~/.flow-cli/fixed-flow-project.json`。也可以通过 `FLOW_CLI_HOME` 改变保存目录。

## 当前 Flow 网址的兼容边界

账号迁移到新的 `flow.google.com` 网址后，本项目可以在已有 Flow 项目中进行文生图、文生视频、素材参考视频、首帧视频和首尾帧视频。新版链路会直接复用 `flow-cli auth login --browser chrome` 保存的本机登录状态，不需要手工复制 Token。

迁移账号应先运行 `flow-cli auth status` 和 `flow-cli project show`，并使用一个已经存在的固定项目。素材参考统一使用 `video r2v`，单张、多张都进入网页“素材”模式；本地图片使用 `--ref`，项目中已有的素材使用 `--project-ref` 加素材的精确标题，两种来源可以混用。只有用户明确要求首帧或首尾帧时才使用 `video i2v` 和网页“帧”模式。`video extend` 仍取决于账号是否开放。

## 在 Agent 窗口中调用

新窗口可直接这样说：

```text
请使用本机 flow-cli 和已经保存的 Flow 登录状态生成内容。
先运行 flow-cli auth status 和 flow-cli project show。
必须复用固定 Flow 项目，不要新建项目。
素材参考使用 `video r2v`，单张或多张都走“素材”；按素材来源自行选择本地图片 `--ref` 或项目已有素材 `--project-ref`，需要时可混用。只有明确要求首帧或首尾帧时才使用 `video i2v`。
模型必须显式指定。画幅、清晰度、时长和数量按用户要求传入；未指定时长和清晰度时分别使用 4 秒和 720p。提交前必须回读全部配置，任一不符就停止，不能换模式继续。
生成后确认文件可以打开，并把绝对路径发给我。

具体要求：
【填写提示词、参考图路径、模型、画幅和保存位置】
```

如果 Agent 不熟悉命令，也可以把下面对应示例一起发给它。

### 让 Agent 制作成 Skill

安装本工具后，可以直接把下面这段话发给 Agent，让它制作并安装一个可自动调用的 Skill：

```text
请把本机已经安装的 flow-cli 制作成一个名为 flow-media 的 Skill，并安装到当前 Agent 能发现的 Skill 目录。
当我说“用 Gemini/Flow 生图”“用 Veo/Flow 生视频”或“图生视频”时自动使用它。
每次生成前先检查 flow-cli auth status 和 flow-cli project show，必须复用固定项目，不要新建项目。
素材参考统一使用 `video r2v` 和网页“素材”模式，单张、多张都适用；本地图片使用 `--ref`，固定项目已有素材使用 `--project-ref "精确标题"`，两者可重复或混用，由你按现有输入选择。只有明确要求首帧或首尾帧时才使用 `video i2v` 和网页“帧”模式。模型必须显式指定，画幅、清晰度、时长和数量按用户要求传入；未指定时长和清晰度时分别使用 4 秒和 720p。提交前回读全部配置，任一不符就停止，不得自动换模式。生成后检查文件可以正常打开，并返回绝对路径。
请完成 Skill 校验，不要把 Token、Cookie 或登录资料写入 Skill。
```

## 图片生成

```bash
# Nano Banana 2 文生图
flow-cli image t2i "电影感的雨夜街道" --model nano2 --aspect 16:9 -n 1 -o output\street.png

# Nano Banana Pro 文生图
flow-cli image t2i "极简产品摄影" --model nano-pro --aspect 1:1 -n 1 -o output\product.png

# Nano Banana 2 Lite 文生图（成本最低）
flow-cli image t2i "清晨山谷风景" --model nano2-lite --aspect 16:9 -n 1 -o output\valley.png

# 多参考图编辑
flow-cli image i2i "保持人物一致，改成冬季雪景" --ref person.jpg --ref clothes.jpg --model nano2 -n 1 -o output\winter.png
```

图片模型：

- `nano2-lite`：Nano Banana 2 Lite，当前最低成本选择
- `nano2`：Nano Banana 2
- `nano-pro`：Nano Banana Pro

新版 Flow 页面已不再提供 Imagen 4，因此 `image4` / `imagen4` 不再列为可用模型。

图片画幅：`9:16`、`16:9`、`1:1`、`4:3`、`3:4`。默认只生成 1 张，`-n` 可设为 1–4。

## 视频生成

以下示例都只生成 1 个，并显式请求 4 秒和 720p。用户指定时按用户参数设置；当前账号或模型没有对应选项时，命令会在提交前拒绝执行：

```bash
# 文生视频
flow-cli video t2v "镜头缓慢推进清晨薄雾中的竹林" --model omni-flash --resolution 720p --duration 4 --count 1 --aspect 16:9 -o output\bamboo.mp4

# 明确指定首帧
flow-cli video i2v output\street.png "雨水缓慢落下，镜头轻微前移" --model veo-lite --resolution 720p --duration 4 --count 1 --aspect 16:9 -o output\street.mp4

# 首尾帧过渡
flow-cli video i2v --initial-frame first.png --end-frame last.png "平滑的电影感转场" --model veo-fast --resolution 720p --duration 4 --count 1 -o output\transition.mp4

# 本地素材参考视频（单张、多张都使用 r2v/素材）
flow-cli video r2v "两名角色在雨中相遇" --ref person-a.png --ref person-b.png --model omni-flash --resolution 720p --duration 4 --count 1 -o output\meeting.mp4

# 复用固定项目中已有素材（按素材卡片的精确标题选择，不重新上传）
flow-cli video r2v "镜头缓慢掠过已有场景" --project-ref "首张横版场景图" --model veo-fast --resolution 360p --duration 8 --count 1 --aspect 16:9 -o output\scene.mp4

# 本地素材与项目已有素材可以混用
flow-cli video r2v "角色走入已有场景" --ref person.png --project-ref "首张横版场景图" --model omni-flash --resolution 720p --duration 6 --count 2 --aspect 9:16 -o output\mixed.mp4

# 续接已有视频（可显式提供项目，也可使用已保存的固定项目）
flow-cli video extend <media-id> "海浪退去" --project <Flow 项目 ID> --aspect 16:9 -o output\continued.mp4
```

视频模型：

- `omni-flash`：Omni 1.1 Flash，最多 7 张参考图，可选 4 / 6 / 8 / 10 秒
- `veo-lite`：Veo 3.1 Lite，成本优先，最多 3 张参考图
- `veo-fast`：Veo 3.1 Fast，速度优先，最多 3 张参考图
- `veo-quality`：Veo 3.1 Quality，质量优先，不支持参考图视频
- `veo-lite-lp`：低优先级的 Veo 3.1 Lite 别名；是否可用可能随账号、地区和当前 Flow 页面变化

Veo 3.1 模型可选 4 / 6 / 8 秒。只有 `omni-flash` 支持 10 秒。未传 `--duration` 时命令使用 4 秒，未传 `--resolution` 时使用 720p；两项仍会真实选择并回读，不依赖网页上次状态。`--count` 大于 1 会增加额度消耗。

素材图片保持原始画幅，不会因为输出视频选择了 9:16 或 16:9 而预先裁切。本地素材会原样上传；项目已有素材会直接从当前项目的“素材”选择器按精确标题选取，不会重复上传。标题找不到或同名不唯一时会在提交前停止。素材画幅与输出画幅是两套独立设置。

视频保存使用详情页“下载成片”所走的原始文件导出链路，不再使用播放器的低码率预览地址。原始文件导出失败时会停止并报错，不会静默退回低码率版本。

`video extend` 会把已有视频续接为一个 8 秒片段，并且必须使用拥有该媒体 ID 的项目。已经设置固定项目时，包装器会自动传入它；示例显式传入项目是为了让归属关系更清楚。结果会作为 Flow 场景渲染到指定的 mp4 路径。迁移到新 Flow 网址的账号仍可能无法使用它。

`--resolution` 支持 360p 和 720p。视频编辑及 1080p/4K 视频放大仍未开放。

## 原有 Session Token 生图方式

旧的 `flow-cli gen` 仍然保留：

```bash
flow-cli login --st "your-session-token"
flow-cli models
flow-cli credits
flow-cli gen "a cinematic cat in neon city" -o output\cat.png
flow-cli gen "convert to watercolor" -r input.jpg -u 2k -o output\watercolor.png
```

`-u` 支持 `none`、`2k` 和 `4k`。放大失败时会自动保存原图。

## Token 插件

仓库内的 `flow-token-updater` 可以把 Chrome 中的 Flow Session Token 同步到旧生图方式。

### 1. 启动本地服务

```bash
python flow_token_server.py
```

默认地址是 `http://127.0.0.1:8765/token`，健康检查地址是 `http://127.0.0.1:8765/health`。

### 2. 加载 Chrome 插件

1. 打开 `chrome://extensions/`
2. 启用开发者模式
3. 点击“加载已解压的扩展程序”
4. 选择仓库中的 `flow-token-updater` 目录

插件首次安装会自动填入并保存 `http://127.0.0.1:8765/token`，同时检查服务是否在线。只有使用其他地址时才需要手动修改。

Token 会保存到 `~/.flow-cli/token.json`。Session Token 变化后，旧生图链路缓存的账号状态会自动清空。

## 配置

旧生图链路的用户配置位于 `~/.flow-cli/config.toml`：

```toml
[flow]
labs_base_url = "https://labs.google/fx/api"
api_base_url = "https://aisandbox-pa.googleapis.com/v1"
timeout = 120
max_retries = 3

[output]
output_dir = "output"

[captcha]
method = "personal"
personal_headless = false
personal_timeout = 90
personal_settle_seconds = 2.0

[debug]
enabled = false
```

`personal` 模式还需要：

```bash
py -m pip install playwright
py -m playwright install chromium
```

## 常见问题

### 登录成功但生成失败

先运行 `flow-cli auth status`，再确认 Google Flow 网页本身可以正常生成，并检查账号额度。网页更新后可能需要升级依赖。

### 每次任务仍会新建项目

运行 `flow-cli project show`。如果没有固定项目，用 `flow-cli project use <项目 ID>` 设置。仅支持上述五个常用生成命令自动注入固定项目。

### 配置文件没有生效

根目录的 `config.toml` 是模板。实际读取的是 `~/.flow-cli/config.toml`，也可以通过 `FLOW_CONFIG` 指定其他路径。

### 图片生成成功但没有保存

确认输出目录可写且磁盘空间足够。旧生图链路下载失败时会自动切换下载方式；需要排查时可临时开启调试模式。

## 安全说明

- 不要提交或公开 ST、AT、Cookie、登录配置和生成历史
- 不要在聊天或截图中展示完整 Token
- `~/.flow-cli/token.json` 和浏览器登录资料只应保存在本机
- 插件的 Token 历史会保存在 Chrome 本地存储中，可随时在插件中清除

## 许可证

MIT，详见 [LICENSE](./LICENSE)。
