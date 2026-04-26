from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time


URL = "https://crex.com/cricket-live-score/mi-vs-rcb-20th-match-indian-premier-league-2026-match-updates-10YI"

options = Options()
options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
driver.get(URL)

wait = WebDriverWait(driver, 15)

seen = set()

try:
    while True:
        try:
            # 🔥 ALWAYS re-find topDiv (important)
            top_div = wait.until(
                EC.presence_of_element_located((By.ID, "topDiv"))
            )

            # 🔥 get fresh elements every loop
            comment_elements = top_div.find_elements(By.CLASS_NAME, "cm-b-comment-c2")

            for el in comment_elements:
                try:
                    text = el.text.strip()

                    if text and text not in seen:
                        seen.add(text)
                        print(text)
                        print("-" * 50)

                except StaleElementReferenceException:
                    continue  # skip broken element

        except StaleElementReferenceException:
            continue  # retry whole block

        time.sleep(3)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    driver.quit()