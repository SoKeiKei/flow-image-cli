"""
本机浏览器 reCAPTCHA token 获取（personal 模式）
"""

from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False


RECAPTCHA_SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"


async def get_personal_recaptcha_token(
    project_id: str,
    action: str,
    st_token: Optional[str],
    headless: bool = False,
    timeout_seconds: int = 90,
    settle_seconds: float = 2.0,
) -> str:
    """通过本机浏览器执行 reCAPTCHA，返回 token"""
    if not HAS_PLAYWRIGHT:
        raise Exception("未安装 playwright，请先运行: pip install playwright && python -m playwright install chromium")

    profile_dir = Path.home() / ".flow-cli" / "browser-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://labs.google/fx/tools/flow/project/{project_id}"

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ],
            viewport={"width": 1440, "height": 900},
        )

        try:
            page = context.pages[0] if context.pages else await context.new_page()

            if st_token:
                await context.add_cookies(
                    [
                        {
                            "name": "__Secure-next-auth.session-token",
                            "value": st_token,
                            "domain": "labs.google",
                            "path": "/",
                            "httpOnly": True,
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    ]
                )

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            await page.wait_for_timeout(int(max(0.0, settle_seconds) * 1000))

            await page.wait_for_function(
                "typeof grecaptcha !== 'undefined' && typeof grecaptcha.enterprise !== 'undefined' && typeof grecaptcha.enterprise.execute === 'function'",
                timeout=20000,
            )

            token = await page.evaluate(
                """
                async ({siteKey, actionName}) => {
                    return await new Promise((resolve, reject) => {
                        try {
                            grecaptcha.enterprise.ready(async () => {
                                try {
                                    const t = await grecaptcha.enterprise.execute(siteKey, {action: actionName});
                                    resolve(t || "");
                                } catch (err) {
                                    reject(err?.message || String(err));
                                }
                            });
                        } catch (err) {
                            reject(err?.message || String(err));
                        }
                    });
                }
                """,
                {"siteKey": RECAPTCHA_SITE_KEY, "actionName": action},
            )

            if not token:
                raise Exception("浏览器执行成功但未返回 token")
            return token
        finally:
            await context.close()

