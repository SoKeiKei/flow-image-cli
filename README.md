# Flow Image CLI — Beyond Images, Now with Video Generation

中文说明：[README-zh.md](./README-zh.md)

A local CLI for generating Google Flow images and videos directly from a terminal or an agent chat.

## Features

- Text-to-image, image-to-image, and multi-reference editing
- Nano Banana 2, Nano Banana Pro, and Imagen 4
- Text-to-video, image-to-video, first/last-frame video, and reference-to-video
- Gemini Omni Flash and Veo 3.1
- Reuse one fixed Flow project instead of creating a project for every task
- Real Chrome login, plus the original Session Token image workflow
- Chrome token extension with a prefilled local server URL and health check
- 2K / 4K image upscaling with original-image fallback

Version 1.2.0 adds the current image/video commands, fixed-project reuse, agent usage instructions, and automatic local defaults in the token extension.

> This is an unofficial tool that drives Google Flow web capabilities. Model availability, credits, and page behavior may vary by account, region, and future Flow updates. Generation consumes your Flow credits.

## Why this project

The referenced projects cover a broader set of use cases and remain a better fit for platform services or deeper control. This repository intentionally keeps a smaller surface for everyday generation:

- One `flow-cli` entry point that agents can call without coordinating multiple services
- Login, image, and video commands under the same CLI
- Fixed-project reuse for clean, continuous agent conversations
- One result by default and a 4-second video default when no duration is requested
- A local token receiver and Chrome extension for compatibility with the original image workflow

It is not intended to replace the referenced projects. Its focus is the shorter path from an agent request to a verified local media file.

## Installation

Python 3.11+ and Chrome are required.

### Quick agent install

Copy and send this line to an agent:

```text
Install https://github.com/SoKeiKei/flow-image-cli and check for missing dependencies
```

### Manual installation

```bash
git clone https://github.com/SoKeiKei/flow-image-cli.git
cd flow-image-cli
py -m pip install -e .
```

Verify the installation:

```bash
flow-cli --help
flow-cli media-models
```

## Recommended login

Run this once before using the current image or video commands:

```bash
flow-cli auth login --browser chrome
```

Complete Google sign-in in the real Chrome window. Later terminal and agent sessions can reuse the saved login.

```bash
flow-cli auth status
```

## Reuse one Flow project

Copy the project ID from a Flow project URL and save it once:

```bash
flow-cli project use <Flow project ID>
flow-cli project show
```

`image t2i`, `image i2i`, `video t2v`, `video i2v`, and `video r2v` will then reuse that project by default. An explicit `--project` option overrides the saved project for one command.

```bash
flow-cli project clear
```

Clearing the setting does not delete the project in Flow. The setting is stored in `~/.flow-cli/fixed-flow-project.json`; set `FLOW_CLI_HOME` to use another directory.

## Use from an agent chat

Paste a request like this into a new agent window:

```text
Use the local flow-cli and its saved Flow login.
First run flow-cli auth status and flow-cli project show.
Reuse the fixed Flow project and do not create a new project.
Generate exactly one result. Use 4 seconds when no video duration is requested; follow the user's requested duration when one is provided.
Verify that the saved file opens, then return its absolute path.

Request:
[prompt, reference paths, model, aspect ratio, and output path]
```

### Ask an agent to create a Skill

After installing this tool, paste the following prompt into an agent window to create and install an automatically triggered Skill:

```text
Create a Skill named flow-media for the locally installed flow-cli, and install it in a Skill directory discoverable by the current agent.
Trigger it when I ask to generate images with Gemini/Flow, videos with Veo/Flow, or image-to-video content.
Before generation, run flow-cli auth status and flow-cli project show. Reuse the fixed project and do not create a new project.
Generate one result by default. Use 4 seconds when no video duration is requested, and follow the user's requested duration when one is provided. Verify that the output file opens and return its absolute path.
Validate the Skill, and never store tokens, cookies, or login data in it.
```

## Image generation

```bash
# Nano Banana 2
flow-cli image t2i "cinematic rainy street at night" --model nano2 --aspect 16:9 -n 1 -o output\street.png

# Nano Banana Pro
flow-cli image t2i "minimal product photography" --model nano-pro --aspect 1:1 -n 1 -o output\product.png

# Imagen 4
flow-cli image t2i "mountain valley at dawn" --model image4 --aspect 16:9 -n 1 -o output\valley.png

# Multi-reference image editing
flow-cli image i2i "keep the person consistent and change the scene to winter" --ref person.jpg --ref clothes.jpg --model nano2 -n 1 -o output\winter.png
```

Image aliases:

- `nano2`: Nano Banana 2, up to 10 references
- `nano-pro`: Nano Banana Pro, up to 10 references
- `image4` / `imagen4`: Imagen 4, up to 3 references

Image aspects: `9:16`, `16:9`, `1:1`, `4:3`, and `3:4`. The default count is one; `-n` accepts 1–4.

## Video generation

These examples generate one video using the 4-second default for requests without a duration. Change `--duration` when the user requests another length:

```bash
# Text-to-video
flow-cli video t2v "slow push through a misty bamboo forest at dawn" --model omni-flash --duration 4 --count 1 --aspect 16:9 -o output\bamboo.mp4

# Animate a generated image
flow-cli video i2v output\street.png "rain falls slowly as the camera moves forward" --model veo-lite --duration 4 --count 1 --aspect 16:9 -o output\street.mp4

# First/last-frame transition
flow-cli video i2v --initial-frame first.png --end-frame last.png "smooth cinematic transition" --model veo-fast --duration 4 --count 1 -o output\transition.mp4

# Reference-to-video
flow-cli video r2v "the two characters meet in the rain" --ref person-a.png --ref person-b.png --model omni-flash --duration 4 --count 1 -o output\meeting.mp4
```

Video aliases:

- `omni-flash`: up to 7 references; 4 / 6 / 8 / 10 seconds
- `veo-lite`: cost-oriented; up to 3 references
- `veo-fast`: speed-oriented; up to 3 references
- `veo-quality`: quality-oriented; no reference-to-video support
- `veo-lite-lp`: lower-priority alias; availability depends on the current Flow UI and account

Veo 3.1 models accept 4 / 6 / 8 seconds. Only `omni-flash` accepts 10 seconds. A `--count` greater than one increases credit usage.

## Original Session Token image workflow

The original `flow-cli gen` command remains available:

```bash
flow-cli login --st "your-session-token"
flow-cli models
flow-cli credits
flow-cli gen "a cinematic cat in neon city" -o output\cat.png
flow-cli gen "convert to watercolor" -r input.jpg -u 2k -o output\watercolor.png
```

`-u` accepts `none`, `2k`, and `4k`. If upscale fails, the original image is saved instead.

## Token extension

The bundled `flow-token-updater` extension syncs the Chrome Flow Session Token to the original image workflow.

Start the local receiver:

```bash
python flow_token_server.py
```

The default endpoint is `http://127.0.0.1:8765/token`; health checks use `http://127.0.0.1:8765/health`.

To install the extension:

1. Open `chrome://extensions/`.
2. Enable Developer mode.
3. Click **Load unpacked**.
4. Select the repository's `flow-token-updater` directory.

On first install, the extension saves the default endpoint and checks whether the service is online. Edit it only when using a custom address. Tokens are written to `~/.flow-cli/token.json`.

## Configuration

The original image workflow reads `~/.flow-cli/config.toml`:

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

The `personal` captcha mode additionally requires:

```bash
py -m pip install playwright
py -m playwright install chromium
```

The root `config.toml` is a template. Set `FLOW_CONFIG` to read another path.

## Troubleshooting

- Run `flow-cli auth status` and confirm that generation also works in the Google Flow website.
- Run `flow-cli project show` if tasks still create new projects.
- Check account credits, output directory permissions, and free disk space.
- A Flow UI update may require upgrading this project's pinned integration dependency.

## Security

- Never commit or publish ST, AT, cookies, login profiles, or generation history.
- Do not expose complete tokens in chat or screenshots.
- Keep `~/.flow-cli/token.json` and browser login data on the local machine.
- The extension keeps token history in Chrome local storage; clear it from the popup when no longer needed.

## Credits

- Current image, video, and real-Chrome login support is provided through [gflow-cli](https://pypi.org/project/gflow-cli/).
- The original image workflow was inspired by [Flow2API](https://github.com/TheSmallHanCat/flow2api).
- The token extension was inspired by [Flow2API-Token-Updater](https://github.com/TheSmallHanCat/Flow2API-Token-Updater).

## License

MIT. See [LICENSE](./LICENSE).
