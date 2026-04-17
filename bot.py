import aiohttp
import asyncio
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = "8775175535:AAEFtDzYhDej129U1cID1_LCaoYO1RGG-5c"
ADMIN_ID = 8505592726
ALLOWED_USERS_FILE = "users.txt"
sem = asyncio.Semaphore(300)

def load_users():
    try:
        with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except:
        return set()

def save_users(users):
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
        for user in sorted(users):
            f.write(user + "\n")

def is_allowed(username):
    return bool(username and username.lower() in load_users())

async def check_fb_info(session, uid):
    url = f"https://scanfb.id.vn/getInfo.php?id={uid}"
    async with sem:
        try:
            async with session.get(url, timeout=100) as response:
                text = await response.text()

                if '"status":"error"' in text:
                    return f"{uid} | DIE"

                created = re.search(r'"created_time"\s*:\s*"([^"]+)"', text)
                locale = re.search(r'"locale"\s*:\s*"([^"]+)"', text)

                created_time = created.group(1) if created else "N/A"
                locale_text = locale.group(1) if locale else "N/A"

                return f"{uid} | {created_time} | {locale_text}"
        except:
            return f"{uid} | ERROR"

async def process_uids(uid_list):
    connector = aiohttp.TCPConnector(limit=500)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_fb_info(session, uid) for uid in uid_list]
        results = await asyncio.gather(*tasks)

    with open("result.txt", "w", encoding="utf-8") as f:
        for line in results:
            f.write(line + "\n")

    return "result.txt"

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Dung: /adduser username")
        return

    username = context.args[0].replace("@", "").lower()
    users = load_users()
    users.add(username)
    save_users(users)

    await update.message.reply_text(f"Da them @{username}")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Dung: /removeuser username")
        return

    username = context.args[0].replace("@", "").lower()
    users = load_users()
    users.discard(username)
    save_users(users)

    await update.message.reply_text(f"Da xoa @{username}")

async def list_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    users = load_users()
    await update.message.reply_text("\n".join("@" + u for u in users) or "Chua co user")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username

    if update.effective_user.id != ADMIN_ID and not is_allowed(username):
        await update.message.reply_text("Ban khong co quyen su dung bot")
        return

    file = await update.message.document.get_file()
    await file.download_to_drive("uid.txt")

    await update.message.reply_text("Dang check UID...")

    with open("uid.txt", "r", encoding="utf-8") as f:
        uids = [line.strip() for line in f if line.strip()]

    result_file = await process_uids(uids)

    with open(result_file, "rb") as doc:
        await update.message.reply_document(document=doc)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("listuser", list_user))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
