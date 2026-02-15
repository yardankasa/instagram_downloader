"""
One-time Instagram downloader using Instaloader.
Uses .env for INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD (or test_username/test_password).
Optional: PROXY_URL (e.g. socks5h://127.0.0.1:10808). Session saved under DOWNLOAD_DIR.

Usage:
  python scripts/onetime_downloader.py profile <username>   # e.g. profile instagram
  python scripts/onetime_downloader.py post <shortcode>    # shortcode from .../p/SHORTCODE/
"""
import os
import sys
from pathlib import Path

import instaloader
from dotenv import load_dotenv

load_dotenv()

# Config from env
USERNAME = os.getenv("INSTAGRAM_USERNAME") or os.getenv("test_username")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD") or os.getenv("test_password")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
PROXY_URL = os.getenv("PROXY_URL", "socks5h://127.0.0.1:10808").strip() or None

if not USERNAME or not PASSWORD:
    print("Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env (or test_username/test_password)")
    sys.exit(1)

SESSION_FILE = os.getenv("SESSION_FILE") or str(DOWNLOAD_DIR / f"session-{USERNAME}")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _set_proxy(loader: instaloader.Instaloader) -> None:
    """Set SOCKS proxy on the loader's session (for login and all requests)."""
    if not PROXY_URL:
        return
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    loader.context._session.proxies.update(proxies)


def get_loader() -> instaloader.Instaloader:
    """Create loader and login (reuse session if possible)."""
    loader = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=True,
        dirname_pattern=str(DOWNLOAD_DIR / "{target}"),
    )
    _set_proxy(loader)
    try:
        loader.load_session_from_file(USERNAME, SESSION_FILE)
    except (FileNotFoundError, instaloader.exceptions.BadCredentialsException):
        loader.login(USERNAME, PASSWORD)
        loader.save_session_to_file(SESSION_FILE)
    _set_proxy(loader)  # session may have been replaced by load/login
    return loader


def download_profile(loader: instaloader.Instaloader, profile_name: str) -> None:
    """Download all posts (and profile pic) of a profile."""
    loader.download_profile(profile_name, profile_pic=True)


def download_post(loader: instaloader.Instaloader, shortcode: str, target: str = "post") -> None:
    """Download a single post by shortcode (e.g. B_K4CykAOtf from instagram.com/p/B_K4CykAOtf/)."""
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target=DOWNLOAD_DIR / target)


def main() -> None:
    import argparse
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
