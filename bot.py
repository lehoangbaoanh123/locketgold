import time
import threading
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 🔐 LẤY TOKEN TỪ ENV (AN TOÀN)
TOKEN = os.getenv("TOKEN")


# ===== LOGIC GIỮ NGUYÊN =====
def run_job(email, results):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # 🔥 QUAN TRỌNG
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)

        driver.get("https://www.facebook.com/login/identify/")

        results[email] = "Đang nhập..."

        input_box = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[name='email'], input[type='text']")
            )
        )

        input_box.clear()
        input_box.send_keys(email)
        input_box.send_keys(Keys.ENTER)

        time.sleep(3)

        try:
            radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if radios:
                driver.execute_script("arguments[0].click();", radios[0])
                time.sleep(1)
        except:
            pass

        continue_xpaths = [
            "//button[@type='submit'][contains(.,'Tiếp tục') or contains(.,'Continue')]",
            "//button[@name='reset_action']",
            "//div[@role='button'][contains(.,'Tiếp tục') or contains(.,'Continue')]",
            "//button[@type='submit']"
        ]

        for xpath in continue_xpaths:
            try:
                btn = driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    break
            except:
                continue

        time.sleep(4)

        content = driver.page_source.lower()

        if "recovery_code_entry" in content or "confirm" in driver.current_url:
            results[email] = "✅ ĐÃ GỬI MÃ"
        elif "checkpoint" in driver.current_url or "captcha" in content:
            results[email] = "✅ ĐÃ GỬI MÃ.."
        else:
            results[email] = "❓ CHỜ"

        driver.quit()

    except Exception as e:
        results[email] = "❌ LỖI"


# ===== TELEGRAM HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    emails = text.split("\n")

    results = {}

    await update.message.reply_text("🚀 Đang xử lý...")

    threads = []

    for email in emails:
        email = email.strip()
        if not email:
            continue

        results[email] = "Đang chạy..."
        t = threading.Thread(target=run_job, args=(email, results))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    msg = ""
    for k, v in results.items():
        msg += f"{k} => {v}\n"

    await update.message.reply_text(msg)


# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("✅ BOT ĐANG CHẠY...")
app.run_polling()
