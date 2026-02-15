# Instagram downloader

Download Instagram profiles and single posts using [Instaloader](https://instaloader.github.io/). Login is automated: the script tries a saved session first, then API login, then a **Selenium headless browser** when Instagram asks for a checkpoint (e.g. on a VPS with no GUI).

## Quick start

1. Copy env sample and set your credentials:

   ```bash
   cp .env-sample .env
   # Edit .env: set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD
   ```

2. Install and run:

   ```bash
   uv sync
   uv run python scripts/onetime_downloader.py profile <username>
   uv run python scripts/onetime_downloader.py post <shortcode>
   ```

- **Profile**: downloads all posts and profile picture for a user (e.g. `profile instagram`).
- **Post**: downloads one post by shortcode from `https://www.instagram.com/p/<shortcode>/`.

First run may trigger the headless browser to complete login/checkpoint; the session is saved so later runs skip login.

---

## Configuration (.env)

All options are read from `.env`. Copy `.env-sample` to `.env` and edit.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INSTAGRAM_USERNAME` or `test_username` | Yes | — | Instagram login username. |
| `INSTAGRAM_PASSWORD` or `test_password` | Yes | — | Instagram login password. |
| `PROXY_URL` | No | `socks5h://127.0.0.1:10808` | SOCKS5 proxy for Instaloader and Selenium. Use `socks5h://` for DNS via proxy. Leave empty to disable. |
| `DOWNLOAD_DIR` | No | `downloads` | Directory where profiles and media are saved. |
| `SESSION_FILE` | No | `DOWNLOAD_DIR/session-<USERNAME>` | Path to the saved session file (reused to avoid login). |
| `SELENIUM_HEADLESS` | No | `1` | `1` = headless browser; `0` = show browser (for debugging). |
| `CHROME_BIN` or `CHROMIUM_BIN` | No | — | Path to Chromium/Chrome binary (e.g. `/usr/bin/chromium`) when not in PATH. |
| `CHROMEDRIVER_PATH` | No | — | Path to `chromedriver` when using system driver instead of webdriver-manager. |

---

## Deploy on Ubuntu server (VPS, no GUI)

### 1. System dependencies

Install Chromium and ChromeDriver so the headless login can run:

```bash
sudo apt update
sudo apt install -y chromium-browser chromium-chromedriver
# or on some systems:
sudo apt install -y chromium chromium-chromedriver
```

If you get **“Chrome instance exited”**, run the script under a virtual display:

```bash
sudo apt install -y xvfb
xvfb-run uv run python scripts/onetime_downloader.py profile <username>
```

Optional: if the Chromium binary is not in a standard path, set in `.env`:

```bash
CHROME_BIN=/usr/bin/chromium
CHROMEDRIVER_PATH=/usr/bin/chromedriver
```

**If you use Snap Chromium** (`snap install chromium`): Snap’s Chromium needs a display and a matching driver. In `.env` set:

```bash
CHROME_BIN=/snap/bin/chromium
CHROMEDRIVER_PATH=/snap/bin/chromium.chromedriver
```

Then **always** run under a virtual display (Snap Chromium will exit with “Missing X server or $DISPLAY” otherwise):

```bash
sudo apt install -y xvfb
xvfb-run -a uv run python scripts/onetime_downloader.py profile <username>
```

On servers, APT Chromium is usually simpler: `sudo apt install -y chromium-browser chromium-chromedriver` and the paths above (no Snap, no xvfb required for headless).

### 2. Project setup

```bash
cd /path/to/instagram_downloader
cp .env-sample .env
# Edit .env: INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, PROXY_URL (if you use a proxy)
uv sync
```

### 3. Run

```bash
uv run python scripts/onetime_downloader.py profile <username>
```

- First run: if the API hits a checkpoint, the script starts the headless browser, completes the login/checkpoint flow, saves the session, then continues the download.
- Next runs: session is loaded from `DOWNLOAD_DIR/session-<USERNAME>`, so no browser and no login prompt.

### 4. Optional: run from a different directory

If you run from another directory, set `DOWNLOAD_DIR` and `SESSION_FILE` in `.env` to absolute paths so the session file is found:

```bash
DOWNLOAD_DIR=/home/user/instagram_downloader/downloads
SESSION_FILE=/home/user/instagram_downloader/downloads/session-your_username
```

---

## How login works

1. **Saved session**: if `SESSION_FILE` exists, load it and skip login.
2. **API login**: try Instaloader’s normal login (username/password).
3. **Checkpoint / failure**: if Instagram returns a checkpoint or error, the script starts a **Selenium headless Chrome/Chromium** session, opens the login page, submits credentials, and tries to complete any “Confirm” / “This was me” step. Cookies are then extracted and saved as the session for Instaloader.
4. The saved session is reused on the next run.

---

## Troubleshooting

- **“Chrome instance exited” / “session not created”**  
  Chrome/Chromium is crashing on start. Try in order:
  1. Install system Chromium and matching ChromeDriver:
     ```bash
     sudo apt update
     sudo apt install -y chromium-browser chromium-chromedriver
     # or on some systems:
     sudo apt install -y chromium chromium-chromedriver
     ```
  2. Point the script at them (in `.env` or `export`):
     ```bash
     CHROME_BIN=/usr/bin/chromium
     CHROMEDRIVER_PATH=/usr/bin/chromedriver
     ```
     Use `which chromium` or `which chromium-browser` to get the real path.
  3. Run under a virtual display (often fixes “exited” on minimal VPS):
     ```bash
     sudo apt install -y xvfb
     xvfb-run uv run python scripts/onetime_downloader.py profile <username>
     ```

- **“No sessionid cookie” / headless login fails**  
  Install Chromium and ChromeDriver (see “Deploy on Ubuntu server”). If the binary is not in PATH, set `CHROME_BIN` or `CHROMIUM_BIN` and optionally `CHROMEDRIVER_PATH`.

- **Proxy**  
  Set `PROXY_URL` in `.env` (e.g. `socks5h://127.0.0.1:10808`). Both Instaloader and the Selenium browser use this. Leave empty to disable.

- **Session from another machine**  
  Create a session on a PC with a browser (e.g. run the script or `instaloader -l USERNAME`, complete checkpoint), then copy the session file to the server at the path given by `SESSION_FILE` in `.env`.

- **Debug headless browser**  
  Set `SELENIUM_HEADLESS=0` and run the script; the browser window will open so you can see the login/checkpoint flow.
