import time
import threading
import os
import asyncio

from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

# ===== TOKEN =====
TOKEN = "8758019971:AAGHm1VrHtGVnFT5l1OjFn01FW_KBJEupbA"

# ===== FLASK =====
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

# ===== LOGIC =====
def run_job(email):
    try:
        print(f"Running: {email}")

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(
            service=Service("/usr/local/bin/chromedriver"),
            options=options
        )

        wait = WebDriverWait(driver, 15)
        driver.get("https://www.facebook.com/login/identify/")

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

        try:
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            driver.execute_script("arguments[0].click();", btn)
        except:
            pass

        time.sleep(4)

        content = driver.page_source.lower()

        driver.quit()

        if "recovery_code_entry" in content or "confirm" in driver.current_url:
            return "✅ ĐÃ GỬI MÃ"
        elif "checkpoint" in driver.current_url or "captcha" in content:
            return "DONE"
        else:
            return "❓ CHỜ"

    except Exception as e:
        print(f"Error: {email} -> {e}")
        return "❌ LỖI"


# ===== GỬI KẾT QUẢ =====
async def send_result(context, chat_id, email, result):
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{email} => {result}"
    )


# ===== XỬ LÝ 1 EMAIL =====
def process_email(email, context, chat_id):
    result = run_job(email)

    asyncio.run(send_result(context, chat_id, email, result))


# ===== TELEGRAM =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    emails = text.split("\n")

    await update.message.reply_text("🚀 Đang xử lý...")

    MAX_THREADS = 3  # 🔥 chống crash

    for email in emails:
        email = email.strip()
        if not email:
            continue

        # giới hạn luồng
        while threading.active_count() > MAX_THREADS:
            await asyncio.sleep(1)

        threading.Thread(
            target=process_email,
            args=(email, context, update.effective_chat.id)
        ).start()


# ===== BOT THREAD (FIX EVENT LOOP) =====
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ BOT RUNNING...")
    app.run_polling()


# ===== MAIN =====
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    run_web()
