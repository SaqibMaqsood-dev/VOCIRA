#web-scraping
import socket
import time
import logging

import httpx
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

log = logging.getLogger(__name__)
    
# after resolving , ChromeDriver path will be cached
_driver_path_cache = None


def _get_driver_path():
    global _driver_path_cache
    if _driver_path_cache is None:
        _driver_path_cache = ChromeDriverManager().install()
    return _driver_path_cache


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Less visible text than this and the page is probably built by
# JavaScript - only then is a real browser worth starting.
_MIN_STATIC_TEXT = 500


def _fetch_static(url: str) -> str | None:
    """The page as the server sends it, or None if that is not enough."""
    try:
        response = httpx.get(
            url,
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
    except httpx.HTTPError as error:
        log.warning("Plain fetch failed for %s: %s", url, error)
        return None

    if response.status_code != 200:
        log.warning("Plain fetch of %s returned %s", url, response.status_code)
        return None

    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    return response.text if len(text) >= _MIN_STATIC_TEXT else None


def get_dynamic_data(url: str):
    """
    Fetch a page for the knowledge base.

    A plain HTTP request first. The school site is served as ready
    HTML: that takes ~1.5s and gives the same text a headless Chrome
    gave in 20-60s (starting the browser, fixed sleeps, scrolling),
    which is what made every sync take over a minute. Selenium is kept
    for a page that really is rendered by JavaScript.
    """
    html = _fetch_static(url)
    if html:
        log.info("Fetched %s without a browser", url)
        return html

    return _get_rendered(url)


def _get_rendered(url: str):
    """Scrape a single URL using Selenium with safety checks."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except OSError:
        log.error(f"Network Error: Cannot reach {url}")
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(_get_driver_path()),
            options=options
        )
        log.info(f"Scraping: {url}")
        driver.get(url)

        # Step 1: wait for body
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass

        # Step 2: loading JavaScript content
        time.sleep(4)

        # Step 3: scroll page — for lazy load content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Step 4: wait for actual text content
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "p"))
            )
        except Exception:
            pass

        return driver.page_source

    except Exception as e:
        log.error(f"Scraping Error for {url}: {e}")
        return None

    finally:
        if driver:
            driver.quit()