# Flow Image CLI

Chinese README: [README-zh.md](./README-zh.md)

Flow image generation command-line tool, supporting:

- Text-to-image / Image-to-image
- 2K / 4K upscaling
- Auto downgrade to original image on upscale failure with guaranteed save
- Local browser captcha (`personal`)
- Local token receiver service (works with `flow-token-updater` extension for automatic ST sync)

> Project Notes:
> - This project is inspired by [Flow2API](https://github.com/TheSmallHanCat/flow2api).
> - `flow-token-updater` is inspired by [Flow2API-Token-Updater](https://github.com/TheSmallHanCat/Flow2API-Token-Updater).

## Project Positioning

This repository is a lightweight, image-focused implementation for local use:

- Focuses on Flow image generation workflow (ST/AT, generate, optional upscale)
- Designed as CLI + local helper tools, not a full platform service

## Prerequisites

- Must be able to sign in to Google Flow: <https://labs.google/fx>
- Account must have image generation permissions (otherwise cannot generate images)
- For `-u 4k`, account must have corresponding subscription/permissions (429/quota errors common without permissions)

## Project Structure

```text
flow-image-cli/
├── flow_cli/                # CLI main code
├── flow-token-updater/      # Browser extension
├── flow_token_server.py     # Local token receiver service
├── config.toml              # Config template
└── README.md
```

## Environment Requirements

- Python 3.9+
- Chrome (for extension and personal mode)
- Access to Google Flow: <https://labs.google/fx>

## Installation

### 1) Install Python dependencies

```bash
cd flow-image-cli
pip install -r requirements.txt
pip install -e .
```

### 2) Install Playwright (required for personal captcha mode)

```bash
pip install playwright
python -m playwright install chromium
```

### 3) Start local token receiver service (recommended)

```bash
python flow_token_server.py
```

Default address: `http://127.0.0.1:8765/token`

## Recommended Token Flow: flow-token-updater

Highly recommended to use the built-in `flow-token-updater` extension to automatically maintain ST, avoiding manual copy/paste.

### Extension Installation

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click "Load unpacked"
4. Select: `/flow-image-cli/flow-token-updater`

### Extension Configuration

1. Open extension popup
2. Set server URL to `http://127.0.0.1:8765/token`
3. Save config and click "Fetch Now"

After obtaining ST, CLI will automatically use the `st` field from `~/.flow-cli/token.json`.

## Configuration

Config path: `~/.flow-cli/config.toml`

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
personal_headless = true
personal_timeout = 90
personal_settle_seconds = 2.0

[debug]
enabled = false
```

Token path: `~/.flow-cli/token.json`

## Captcha Mode

Supported `captcha.method` values:

- `personal`: Solve captcha using local browser (requires Playwright)
- `none`: Do not actively solve captcha (may fail when captcha is required)

This simplified project does not include built-in third-party captcha providers (such as YesCaptcha/CapMonster/Capsolver) by default.
Default `personal_headless = true` (silent headless, no browser popup); set to `false` only when visual debugging is needed.

## Interactive Script

Provides an interactive Python script for terminal configuration:

```bash
python interactive_generate.py
```

Supports interactive configuration:

- Prompt
- Model (index or model name)
- Output path
- Reference image path
- Upscale option (`none/2k/4k`)
- Language mode (`中文 / English / 双语`)

Default output path uses timestamp template: `output/flow_{timestamp}.png` (auto-expands timestamp to avoid overwriting).

## CLI Usage

> Usage Notes:
> - First ensure you can log in to Flow and your account has image generation permissions before running CLI.
> - `-u 4k` is not available for all accounts; requires corresponding subscription/permissions.

### Login (manual)

```bash
flow-cli login --st "your-session-token"
```

### Basic Commands

```bash
flow-cli models
flow-cli credits
flow-cli config
```

### Text-to-image / Image-to-image

```bash
# Text-to-image
flow-cli gen "a cinematic cat in neon city"

# Specify model and output
flow-cli gen "mountain landscape" -m gemini-3.1-flash-image-landscape -o output\landscape.png

# Image-to-image
flow-cli gen "convert to watercolor style" -r input.jpg -o output\watercolor.png
```

### 2K / 4K Upscale

```bash
# Generate then upscale to 2K
flow-cli gen "a cat" -m gemini-3.1-flash-image-landscape -u 2k -o output\cat_2k.png

# Generate then upscale to 4K
flow-cli gen "a cat" -m gemini-3.1-flash-image-landscape -u 4k -o output\cat_4k.png
```

Parameters:

- `-u, --upscale`: `none` / `2k` / `4k`

Note:
- When `2k/4k` upscale fails, the program automatically downgrades to original image and saves to `-o` specified path.

## Python API Examples

### 1) Text-to-image

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

### 2) Image-to-image + 2K

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

## Local Token Server API

`flow_token_server.py` provides local HTTP interface for extension or script calls.

### 1) Health check

```bash
curl http://127.0.0.1:8765/health
```

Response:

```json
{"status":"ok"}
```

### 2) Query current token status

```bash
curl http://127.0.0.1:8765/token
```

Response:

```json
{"has_token": true, "token_length": 2147}
```

### 3) Write session_token

```bash
curl -X POST http://127.0.0.1:8765/token ^
  -H "Content-Type: application/json" ^
  -d "{\"session_token\":\"your-st-token\"}"
```

Response:

```json
{"success":true,"message":"Token saved to ...","token_length":2147}
```

## FAQ

### Q1: Can I get 2K images?

Yes. Use `-u 2k`.
`-u 4k` requires account to have corresponding subscription/permissions.
On upscale failure, it automatically downgrades to original image and saves it.

### Q2: What to do if `reCAPTCHA evaluation failed`?

1. Ensure `captcha.method = "personal"`
2. Ensure Playwright + Chromium is installed
3. Ensure browser can access and is logged into Google Flow

### Q3: What to do if 401/500 errors occur?

- 401: Usually AT expired, program will auto-refresh and retry
- 500: Upstream occasional issue, recommend retry or switch model (prefer `gemini-3.1-flash-image-*`)

### Q4: Config file location and method settings not taking effect?

The CLI reads config from `~/.flow-cli/config.toml` (user's home directory), NOT from the project root `config.toml`.

**Solutions:**
1. Copy your config to the default location:
   ```bash
   mkdir -p ~/.flow-cli
   cp <your-project-path>/config.toml ~/.flow-cli/config.toml
   ```
2. Or use environment variable:
   ```bash
   export FLOW_CONFIG=/path/to/your/config.toml
   ```

### Q5: How to update/login with new Session Token?

```bash
flow-cli login --st "your-new-session-token"
```

You can get ST from Flow Token browser extension.

### Q6: Playwright/browser issues in personal captcha mode?

1. Install Playwright: `pip install playwright && python -m playwright install chromium`
2. If browser doesn't open automatically, check if another Chrome instance is using the profile
3. For headless mode issues, try setting `personal_headless = false` in config
4. Browser profile is stored at `~/.flow-cli/browser-profile`

### Q7: Image generation succeeded but file not saved?

- Check if output directory exists and is writable
- Ensure sufficient disk space
- Check debug logs for more details (set `debug.enabled = true` in config)

## Security Tips

- Do not commit ST/AT to repository
- Do not expose full tokens in chat/screenshots
- `~/.flow-cli/token.json` recommended for local use only

## Related Links

- Google Flow: <https://labs.google/fx/tools/flow>
- Flow2API: <https://github.com/TheSmallHanCat/flow2api>
- Flow2API-Token-Updater: <https://github.com/TheSmallHanCat/Flow2API-Token-Updater>

## License

MIT. See [LICENSE](./LICENSE).