# Login isn't time-critical, so this clears Cloudflare + authenticates via a real browser,
# then hands the resulting cookie jar off to a TLS-impersonating client for the fast path.

from playwright.sync_api import sync_playwright

from .config import LOGIN_URL, MEMBER_NUMBER, PASSWORD

LOGIN_FIELD = 'input[name="_com_liferay_login_web_portlet_LoginPortlet_login"]'
PASSWORD_FIELD = 'input[name="_com_liferay_login_web_portlet_LoginPortlet_password"]'


def login(headless: bool = True) -> dict[str, str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, channel="chrome")
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, wait_until="networkidle")
        page.fill(LOGIN_FIELD, MEMBER_NUMBER)
        page.fill(PASSWORD_FIELD, PASSWORD)
        page.press(PASSWORD_FIELD, "Enter")
        page.wait_for_url(lambda url: "/web/pages/login" not in url, timeout=30_000)

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        browser.close()
        return cookies
