#web-scraping
import socket
import time
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

log = logging.getLogger(__name__)


def get_dynamic_data(url: str):
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
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        log.info(f"Scraping: {url}")
        driver.get(url)

        # Step 1: Body aane ka wait
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass

        # Step 2: JavaScript content load hone do
        time.sleep(4)

        # Step 3: Page scroll karo — lazy load content ke liye
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Step 4: Actual text content aane ka wait
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