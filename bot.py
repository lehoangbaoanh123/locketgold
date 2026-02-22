import time
import chromedriver_autoinstaller

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8459006504:AAGXFtwPP30LudboEH3oE4HTxUr_xXwGUbU"
ADMIN_ID = 8505592726

waiting_user = {}
users_using = set()
history = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_user[update.effective_chat.id] = True
    await update.message.reply_text("🔒 Nhập username cần unlock:")

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return

    if not users_using:
        await update.message.reply_text("Không ai đang sử dụng.")
    else:
        msg = "\n".join([str(u) for u in users_using])
        await update.message.reply_text("👥 Đang dùng:\n" + msg)

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return

    if not history:
        await update.message.reply_text("Chưa có dữ liệu.")
    else:
        msg = "\n".join(history)
        await update.message.reply_text("📜 Lịch sử:\n" + msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in waiting_user:
        return

    username = update.message.text
    del waiting_user[chat_id]

    users_using.add(chat_id)

    await update.message.reply_text("⚙️ Running...")

    try:
        # ===== FIX SELENIUM =====
        chromedriver_autoinstaller.install()

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

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

        history.append(f"{chat_id} → {username}")
        users_using.remove(chat_id)

        await update.message.reply_text("✅ Done!")

    except Exception as e:
        users_using.remove(chat_id)
        await update.message.reply_text(f"❌ Error: {str(e)}")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("users", users))
app.add_handler(CommandHandler("history", history_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
