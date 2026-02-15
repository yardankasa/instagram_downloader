"""
One-time Instagram downloader using Instaloader.
Uses .env for INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD (or test_username/test_password).
Optional: PROXY_URL (e.g. socks5h://127.0.0.1:10808). Session saved under DOWNLOAD_DIR.

Login: tries saved session first, then Instaloader API, then Selenium headless browser
(so checkpoints can be completed automatically on a VPS with no GUI).

Usage:
  python scripts/onetime_downloader.py profile <username>
  python scripts/onetime_downloader.py post <shortcode>
"""
import argparse
import os
import sys
import time
from pathlib import Path

import instaloader
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
except Exception:
    ChromeDriverManager = None

load_dotenv()

# Config from env
USERNAME = os.getenv("INSTAGRAM_USERNAME") or os.getenv("test_username")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD") or os.getenv("test_password")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
PROXY_URL = os.getenv("PROXY_URL", "socks5h://127.0.0.1:10808").strip() or None
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "1").strip().lower() in ("1", "true", "yes")

if not USERNAME or not PASSWORD:
    print("Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env (or test_username/test_password)")
    sys.exit(1)

SESSION_FILE = os.getenv("SESSION_FILE") or str(DOWNLOAD_DIR / f"session-{USERNAME}")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _set_proxy(loader: instaloader.Instaloader) -> None:
    """Set SOCKS proxy on the loader's session."""
    if not PROXY_URL:
        return
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    loader.context._session.proxies.update(proxies)


def _find_system_chromium() -> str | None:
    """Return path to system Chromium on Linux if found."""
    candidates = [
        os.getenv("CHROME_BIN"),
        os.getenv("CHROMIUM_BIN"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _login_with_selenium() -> dict:
    """Log in via headless Chrome, handle checkpoint if possible, return cookie dict for Instaloader."""
    # Snap Chromium and some builds need DISPLAY even in headless; xvfb-run sets :99
    if SELENIUM_HEADLESS and not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":99"
    options = Options()
    if SELENIUM_HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--window-size=1920,1080")
    if PROXY_URL:
        proxy = PROXY_URL.replace("socks5h://", "socks5://")
        options.add_argument(f"--proxy-server={proxy}")
    # Prefer system Chromium on Linux (avoids version mismatch with webdriver-manager)
    chromium_bin = _find_system_chromium()
    if chromium_bin:
        options.binary_location = chromium_bin

    # Snap Chromium must use Snap's chromedriver (version must match)
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    if not chromedriver_path and chromium_bin and "/snap/" in chromium_bin:
        snap_driver = "/snap/bin/chromium.chromedriver"
        if os.path.isfile(snap_driver):
            chromedriver_path = snap_driver
    service = None
    if chromedriver_path and os.path.isfile(chromedriver_path):
        service = Service(chromedriver_path)
    elif not chromium_bin and ChromeDriverManager is not None:
        try:
            service = Service(ChromeDriverManager().install())
        except Exception:
            pass
    try:
        driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
    except Exception as e:
        err = str(e)
        if "session not created" in err or "Chrome instance exited" in err:
            print("", file=sys.stderr)
            print("Chrome/Chromium failed to start. On a VPS try:", file=sys.stderr)
            print("  If using SNAP Chromium: use Snap's chromedriver (version must match):", file=sys.stderr)
            print("    CHROMEDRIVER_PATH=/snap/bin/chromium.chromedriver", file=sys.stderr)
            print("  And run with a virtual display: xvfb-run -a uv run python scripts/onetime_downloader.py ...", file=sys.stderr)
            print("  (install: sudo apt install -y xvfb)", file=sys.stderr)
            print("  Prefer APT (often more reliable on servers): sudo apt install -y chromium-browser chromium-chromedriver", file=sys.stderr)
            print("  Then in .env: CHROME_BIN=/usr/bin/chromium  CHROMEDRIVER_PATH=/usr/bin/chromedriver", file=sys.stderr)
        raise

    wait = WebDriverWait(driver, 25)
    cookie_dict = {}

    try:
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(2)

        # Username: try name, then placeholder
        username_sel = (By.NAME, "username")
        password_sel = (By.NAME, "password")
        try:
            wait.until(EC.presence_of_element_located(username_sel))
        except Exception:
            username_sel = (By.CSS_SELECTOR, 'input[name="username"], input[aria-label*="Phone"], input[aria-label*="Username"]')
            wait.until(EC.presence_of_element_located(username_sel))
        user_el = driver.find_element(*username_sel)
        pass_el = driver.find_element(*password_sel)
        user_el.clear()
        user_el.send_keys(USERNAME)
        pass_el.clear()
        pass_el.send_keys(PASSWORD)

        # Submit: button type submit or "Log in" text
        try:
            submit = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        except Exception:
            submit = driver.find_element(By.XPATH, '//button[.//span[text()="Log in"]] | //div[@role="button"][.//span[text()="Log in"]]')
        submit.click()

        # Wait for navigation: either feed (success) or challenge
        time.sleep(4)
        for _ in range(30):
            url = driver.current_url
            if "/accounts/login/" not in url and "challenge" not in url.lower() and "one_page" not in url:
                # Likely logged in (feed or home)
                break
            # Checkpoint: try to open challenge link if present
            try:
                link = driver.find_element(By.CSS_SELECTOR, 'a[href*="auth_platform"], a[href*="challenge"]')
                href = link.get_attribute("href")
                if href and "instagram.com" in href:
                    driver.get(href)
                    time.sleep(3)
            except Exception:
                pass
            # "Confirm" / "This was me" button
            try:
                btn = driver.find_element(By.XPATH, "//button[contains(.,'Confirm') or contains(.,'This was me') or contains(.,'Not Now')]")
                btn.click()
                time.sleep(3)
            except Exception:
                pass
            time.sleep(2)

        cookies = driver.get_cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        if "sessionid" not in cookie_dict:
            raise RuntimeError("Login or checkpoint not completed: no sessionid cookie. Try running with SELENIUM_HEADLESS=0 to see the browser.")
    finally:
        driver.quit()

    return cookie_dict


def get_loader() -> instaloader.Instaloader:
    """Create loader: use saved session, or API login, or Selenium headless login."""
    loader = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=True,
        dirname_pattern=str(DOWNLOAD_DIR / "{target}"),
    )
    _set_proxy(loader)
    if os.path.isfile(SESSION_FILE):
        try:
            loader.load_session_from_file(USERNAME, SESSION_FILE)
        except Exception:
            pass
    if not loader.context.is_logged_in:
        try:
            loader.login(USERNAME, PASSWORD)
            loader.save_session_to_file(SESSION_FILE)
        except instaloader.exceptions.LoginException:
            # Fallback: Selenium headless browser (handles checkpoint on VPS)
            print("API login failed (e.g. checkpoint). Using headless browser login...", file=sys.stderr)
            try:
                cookie_dict = _login_with_selenium()
                loader.context.load_session(USERNAME, cookie_dict)
                loader.save_session_to_file(SESSION_FILE)
            except Exception as e:
                print("Headless browser login failed:", e, file=sys.stderr)
                print("On VPS install: chromium-browser and chromium-chromedriver (or use Chrome).", file=sys.stderr)
                sys.exit(1)
    _set_proxy(loader)
    return loader


def download_profile(loader: instaloader.Instaloader, profile_name: str) -> None:
    """Download all posts (and profile pic) of a profile."""
    loader.download_profile(profile_name, profile_pic=True)


def download_post(loader: instaloader.Instaloader, shortcode: str, target: str = "post") -> None:
    """Download a single post by shortcode (e.g. B_K4CykAOtf from instagram.com/p/B_K4CykAOtf/)."""
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target=DOWNLOAD_DIR / target)


def main() -> None:
    p = argparse.ArgumentParser(description="One-time Instagram downloader")
    p.add_argument("mode", choices=["profile", "post"], help="profile = download a user's posts; post = download one post")
    p.add_argument("target", help="Username (e.g. instagram) or post shortcode (e.g. B_K4CykAOtf from .../p/SHORTCODE/)")
    args = p.parse_args()

    loader = get_loader()
    if args.mode == "profile":
        download_profile(loader, args.target)
    else:
        download_post(loader, args.target, target=args.target)
    print("Done.")


if __name__ == "__main__":
    main()
