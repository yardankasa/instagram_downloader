# Instagram downloader

Uses Instaloader; login is automated with Selenium headless when the API hits a checkpoint (e.g. on a VPS with no GUI).

## Ubuntu server (headless)

Install Chromium and ChromeDriver so Selenium can run:

```bash
sudo apt update
sudo apt install -y chromium-browser chromium-chromedriver
```

If your Chromium is in a non-standard path, set:

```bash
export CHROME_BIN=/usr/bin/chromium
```

Then install deps and run:

```bash
uv sync
uv run python scripts/onetime_downloader.py profile <username>
```

First run may use the headless browser to complete login/checkpoint; the session is saved for next runs.
