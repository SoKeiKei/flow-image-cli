# Flow Image CLI — Beyond Images, Now with Video Generation

中文说明：[README-zh.md](./README-zh.md)

A local CLI for generating Google Flow images and videos directly from a terminal or an agent chat.

## Features

- Text-to-image on `flow.google.com`, plus image-to-video from a local image
- Nano Banana 2 Lite, Nano Banana 2.1, and Nano Banana Pro
- Text-to-video, image-to-video, first/last-frame video, and reference-to-video where the current Flow host supports them
- Omni 1.1 Flash (`omni-flash`) and Veo 3.1 Lite / Fast / Quality
- Reuse one fixed Flow project instead of creating a project for every task
- Real Chrome login, plus the original Session Token image workflow
- Chrome token extension with a prefilled local server URL and health check
- 2K / 4K image upscaling with original-image fallback

Version 1.4.0 depends on gflow-cli 0.85. Image-to-video from a local image works on the migrated `flow.google.com` host starting with this release.

> This is an unofficial tool that drives Google Flow web capabilities. Model availability, credits, and page behavior may vary by account, region, and future Flow updates. Generation consumes your Flow credits.

## Why this project

This project focuses on everyday generation from a terminal or agent chat:

- One `flow-cli` entry point that agents can call without coordinating multiple services
- Login, image, and video commands under the same CLI
- Fixed-project reuse for clean, continuous agent conversations
- One result by default. On `flow.google.com`, `--duration` applies only to `omni-flash`; omit it for Veo and Flow uses the 8-second default
- A local token receiver and Chrome extension for compatibility with the original image workflow

Its focus is the shortest path from an agent request to a verified local media file.

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
pip install -e .
```

On Windows, `py -m pip install -e .` works as well.

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

The command opens real Chrome. Finish sign-in and reach the Flow editor. Stopping at the Google account page is not enough. Then confirm the session:

```bash
flow-cli auth status
```

## Reuse one Flow project

Copy the project ID from a Flow project URL and save it once:

```bash
flow-cli project use <id>
flow-cli project show
```

`image t2i`, `image i2i`, `video t2v`, `video i2v`, `video r2v`, and `video extend` will then reuse that project by default. For `video extend`, the fixed project must own the media ID. An explicit `--project` option overrides the saved project for one command.

```bash
flow-cli project clear
```

Clearing the setting does not delete the project in Flow. The setting is stored in `~/.flow-cli/fixed-flow-project.json`; set `FLOW_CLI_HOME` to use another directory.

## Site migration

Google is moving Flow from `https://labs.google/fx/tools/flow` to `https://flow.google.com`.

gflow-cli 0.67 could only run text-to-video on the new site. Image-to-video failed before submit with `FlowHostMigratedError` (exit 36). That path is fixed in gflow-cli 0.85+. This release requires `gflow-cli>=0.85.0,<0.86.0`, so local image-to-video runs on `flow.google.com`.

For a migrated account, start with `flow-cli auth status`, `flow-cli project show`, and an existing project. The migrated image path reuses the local browser login saved by `flow-cli auth login --browser chrome`; no manual token copy is needed.

## Use from an agent chat

Paste a request like this into a new agent window:

```text
Use the local flow-cli and its saved Flow login.
First run flow-cli auth status and flow-cli project show.
Reuse the fixed Flow project and do not create a new project.
Generate exactly one result. On flow.google.com, pass --duration only with omni-flash. Omit --duration for Veo; the default is 8 seconds. Passing --duration to Veo exits 11 with ConfigurationError before submit.
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
Generate one result by default. On flow.google.com, pass --duration only with omni-flash. Omit --duration for Veo; the default is 8 seconds. Passing --duration to Veo exits 11 with ConfigurationError before submit. Verify that the output file opens and return its absolute path.
Validate the Skill, and never store tokens, cookies, or login data in it.
```

## Image generation

```bash
# Nano Banana 2.1, 9:16
flow-cli image t2i "<prompt>" --model nano2 --aspect 9:16 --project <id> -o out.png

# Nano Banana Pro
flow-cli image t2i "minimal product photography" --model nano-pro --aspect 1:1 -n 1 -o output\product.png

# Nano Banana 2 Lite (lowest cost)
flow-cli image t2i "mountain valley at dawn" --model nano2-lite --aspect 16:9 -n 1 -o output\valley.png

# Multi-reference image editing
flow-cli image i2i "keep the person consistent and change the scene to winter" --ref person.jpg --ref clothes.jpg --model nano2 -n 1 -o output\winter.png
```

Image aliases:

- `nano2-lite`: Nano Banana 2 Lite, currently the lowest-cost option
- `nano2`: Nano Banana 2.1. Flow replaced Nano Banana 2 with it on `flow.google.com`; the command alias remains `nano2`
- `nano-pro`: Nano Banana Pro

The migrated Flow page no longer offers Imagen 4, so `image4` / `imagen4` are no longer listed as available models.

Image aspects: `9:16`, `16:9`, `1:1`, `4:3`, and `3:4`. The default count is one; `-n` accepts 1–4.

## Video generation

On `flow.google.com`, `--duration` works only with `omni-flash`. Omit it for Veo (`veo-lite`, `veo-fast`, `veo-quality`). Flow then uses the 8-second default. Passing `--duration` to Veo fails before submit with `ConfigurationError` (exit 11).

```bash
# Image-to-video on flow.google.com (no duration for Veo)
flow-cli video i2v -i selfie.png --aspect 9:16 --model veo-fast --project <id> -o out.mp4 "<prompt>"

# Text-to-video (only omni-flash accepts a duration)
flow-cli video t2v "slow push through a misty bamboo forest at dawn" --model omni-flash --duration 4 --count 1 --aspect 16:9 -o output\bamboo.mp4

# First/last-frame transition (omit --duration for Veo)
flow-cli video i2v --initial-frame first.png --end-frame last.png "smooth cinematic transition" --model veo-fast --count 1 -o output\transition.mp4

# Reference-to-video (omni-flash accepts a duration)
flow-cli video r2v "the two characters meet in the rain" --ref person-a.png --ref person-b.png --model omni-flash --duration 4 --count 1 -o output\meeting.mp4

# Continue an existing clip (pass the project explicitly, or use the saved fixed project)
flow-cli video extend <media-id> "the wave recedes" --project <id> --aspect 16:9 -o output\continued.mp4
```

Video aliases:

- `omni-flash`: Omni 1.1 Flash; up to 7 references; accepts `--duration` on `flow.google.com`
- `veo-lite`: Veo 3.1 Lite; cost-oriented; up to 3 references
- `veo-fast`: Veo 3.1 Fast; speed-oriented; up to 3 references
- `veo-quality`: Veo 3.1 Quality; quality-oriented; no reference-to-video support
- `veo-lite-lp`: lower-priority Veo 3.1 Lite alias; availability may vary by account, region, and the current Flow UI

On `flow.google.com`, omit `--duration` for Veo and keep the 8-second default. Only `omni-flash` accepts a duration: 4 / 6 / 8 / 10 seconds. A `--count` greater than one increases credit usage.

`video extend` continues an existing clip as an 8-second segment and requires the project that owns the media ID. The wrapper adds the saved fixed project when one is configured. Its output is a Flow Scene rendered to the requested mp4 path. It may still be unavailable on an account migrated to the new Flow host.

The Flow website may expose video resolution, editing, or upscale options that this CLI does not yet expose. The current CLI does not provide video 360p selection, video editing, or 1080p/4K video upscaling controls.

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

### Login succeeded but generation fails

Run `flow-cli auth status`. The status should show that Flow itself is signed in, not only the Google account. Confirm that generation also works in the Google Flow website, and check account credits. A Flow UI update may require updating this project.

### auth status logs SecurityError without a system keyring

Without a system keyring, cookie reads fall back to Playwright. Playwright needs the marker file `<profile>/.gflow_browser_strategy` containing `chrome`. If that file is missing, `flow-cli auth status` logs `auth_flow_session_probe_error` with `SecurityError`.

Fix: run `flow-cli auth login --browser chrome` again, or recreate the marker file in that profile with the contents `chrome`.

### Google is signed in, but the Flow app is not

If the profile only visited `flow.google.com`, it may lack the labs.google Flow sign-in. `flow-cli auth status` then says Google is signed in but the Flow app is not. Open `https://labs.google/fx/tools/flow` in that same profile, complete Sign in with Google, and run `flow-cli auth status` again.

### Tasks still create a new project

Run `flow-cli project show`. If no project is fixed, set one with `flow-cli project use <id>`. The image and video generation commands above inject that project. `video chain` has no `--project` option and is left unchanged.

### Veo exits as soon as a duration is passed

On `flow.google.com`, passing `--duration` to Veo fails before submit with `ConfigurationError` (exit 11). Omit `--duration` and keep the 8-second default. Only `omni-flash` accepts the flag.

Also check the output directory permissions and free disk space.

## Security

- Never commit or publish ST, AT, cookies, login profiles, or generation history.
- Do not expose complete tokens in chat or screenshots.
- Keep `~/.flow-cli/token.json` and browser login data on the local machine.
- The extension keeps token history in Chrome local storage; clear it from the popup when no longer needed.

## License

MIT. See [LICENSE](./LICENSE).
