from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from threading import Thread
from flask import Flask
import asyncio
import os
import time

TOKEN = "YOUR_BOT_TOKEN_HERE"


# ====== HÀM AUTO KÍCH HOẠT ======
def auto_activate(username):

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 25)

    driver.get("https://hieutrungnguyen.com/hieuoi/")

    try:
        user_box = wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        user_box.clear()
        user_box.send_keys(username)

        check_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Kiểm tra')]")))
        check_btn.click()

        time.sleep(6)

        page = driver.page_source.lower()

        if "không tồn tại" in page:
            driver.quit()
            return "❌ User không tồn tại"

        activate = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//button[.//text()[contains(.,'Kích hoạt')]]")
        ))

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", activate)
        time.sleep(2)

        driver.execute_script("""
            let btn = arguments[0];
            btn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
            btn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true}));
        """, activate)

        driver.quit()
        return "🚀 Kích hoạt thành công!"

    except Exception as e:
        driver.quit()
        return f"⚠️ Lỗi: {e}"


# ====== TELEGRAM HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gửi USER để kích hoạt")

async def handle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.text
    await update.message.reply_text("Đang xử lý...")

    result = await asyncio.to_thread(auto_activate, user)

    await update.message.reply_text(result)


# ====== CHẠY BOT Ở THREAD RIÊNG ======
telegram_app = ApplicationBuilder().token(TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user))

def run_bot():
    telegram_app.run_polling()

Thread(target=run_bot).start()


# ====== FLASK (ĐỂ RENDER KHÔNG TIMEOUT) ======
web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)
