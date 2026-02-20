import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8552047398:AAHaeVCRxRO41Ze0GrYHmaeBP9-W9_l4JBo"

waiting_user = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_user[update.effective_chat.id] = True
    await update.message.reply_text("🔒 Nhập username cần unlock:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in waiting_user:
        return

    username = update.message.text
    del waiting_user[chat_id]

    await update.message.reply_text("Running...")

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://hieutrungnguyen.com/hieuoi/")
        time.sleep(3)

        try:
            user_box = driver.find_element(By.NAME, "username")
        except:
            try:
                user_box = driver.find_element(By.ID, "username")
            except:
                user_box = driver.find_element(By.XPATH, "//input")

        user_box.send_keys(username)
        time.sleep(1)

        try:
            unlock_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Unlock')]")
        except:
            unlock_btn = driver.find_element(By.XPATH, "//button")

        unlock_btn.click()
        time.sleep(3)

        driver.quit()

        await update.message.reply_text("Done!")

    except:
        await update.message.reply_text("Error!")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
