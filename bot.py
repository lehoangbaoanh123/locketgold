import logging
import requests
import threading
import datetime
import os
import json
from flask import Flask
from tinydb import TinyDB, Query
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# --- CONFIG ---
TOKEN_BOT = "8330278397:AAGaoqGXXL_BDca2Kztev2X_O4AOEKW_hGg"
ADMIN_ID = 8505592726  
FIELDS = "id,name,first_name,last_name,username,is_verified,birthday,gender,relationship_status,significant_other,hometown,location,work,education,about,quotes,website,subscribers.limit(0),created_time,updated_time,languages,timezone,locale"

# Database
db = TinyDB('db.json')
tokens_table = db.table('tokens')
users_table = db.table('users')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- WEB SERVER (Cho Render) ---
app_web = Flask(__name__)
@app_web.route('/')
def home(): return "Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

# --- QUẢN LÝ TOKEN ---
current_token_index = 0
token_lock = threading.Lock()

def get_tokens():
    return [t['value'] for t in tokens_table.all()]

def rotate_token():
    global current_token_index
    all_t = get_tokens()
    if all_t:
        current_token_index = (current_token_index + 1) % len(all_t)

# --- HÀM LẤY UID TỪ URL/USERNAME ---
def get_fb_uid(input_data):
    """Chuyển đổi URL/Username sang UID thông qua ffb.vn"""
    input_data = input_data.strip()
    
    # Nếu đã là UID (toàn số) thì trả về luôn
    if input_data.isdigit():
        return input_data

    # Xử lý URL
    if not input_data.startswith("http"):
        url_to_check = f"https://www.facebook.com/{input_data}"
    else:
        url_to_check = input_data

    api_url = "https://ffb.vn/api/tool/get-id-fb"
    try:
        response = requests.get(api_url, params={'idfb': url_to_check}, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            return res_json.get('id') # Trả về UID hoặc None
    except:
        pass
    return None

# --- KIỂM TRA QUYỀN ---
def check_permission(user_id):
    if user_id == ADMIN_ID: return True
    U = Query()
    user = users_table.get(U.id == user_id)
    if user:
        expiry = datetime.datetime.fromisoformat(user['expiry'])
        if expiry > datetime.datetime.now(): return True
    return False

# --- LOGIC FACEBOOK GRAPH API ---
def request_fb_api(uid):
    all_t = get_tokens()
    if not all_t: return {"error_internal": "Hệ thống chưa có Token."}
    
    max_retry = len(all_t)
    for _ in range(max_retry):
        with token_lock:
            token = all_t[current_token_index % len(all_t)]
        
        url = f"https://graph.facebook.com/{uid}?fields={FIELDS}&access_token={token}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if "error" in data:
                msg = data["error"].get("message", "").lower()
                if any(k in msg for k in ["access token", "expired", "session", "checkpoint"]):
                    rotate_token()
                    continue
            return data
        except:
            rotate_token()
    return {"error_internal": "Tất cả Token đều lỗi hoặc hết hạn."}

# --- COMMANDS ADMIN ---
async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    new_tokens = context.args
    if not new_tokens:
        await update.message.reply_text("❌ HD: `/add token1 token2...`")
        return
    for t in new_tokens:
        tokens_table.insert({'value': t})
    await update.message.reply_text(f"✅ Đã thêm {len(new_tokens)} token mới.")

async def grant_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        users_table.upsert({'id': target_id, 'expiry': expiry}, Query().id == target_id)
        await update.message.reply_text(f"✅ Đã cấp quyền cho <code>{target_id}</code> trong {days} ngày.", parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ HD: `/grant [ID] [Số ngày]`")

# --- XỬ LÝ TIN NHẮN CHÍNH ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_permission(user_id):
        await update.message.reply_text("🚫 <b>Bạn không có quyền hoặc hết hạn sử dụng.</b>", parse_mode=ParseMode.HTML)
        return

    raw_text = update.message.text.strip()
    sent_msg = await update.message.reply_text("⌛ <b>Đang nhận diện và lấy UID...</b>", parse_mode=ParseMode.HTML)

    # Bước 1: Lấy UID từ input (Link/User/UID)
    uid = get_fb_uid(raw_text)
    
    if not uid:
        await sent_msg.edit_text("❌ <b>Không tìm thấy UID từ dữ liệu bạn gửi.</b>\nVui lòng kiểm tra lại Link hoặc Username.", parse_mode=ParseMode.HTML)
        return

    # Bước 2: Truy xuất thông tin từ Facebook API bằng UID
    await sent_msg.edit_text(f"⌛ <b>Đang quét dữ liệu UID:</b> <code>{uid}</code>...", parse_mode=ParseMode.HTML)
    data = request_fb_api(uid)

    if "error_internal" in data or "error" in data:
        err = data.get("error_internal") or data["error"].get("message")
        await sent_msg.edit_text(f"❌ <b>Lỗi API FB:</b> <code>{err}</code>", parse_mode=ParseMode.HTML)
        return

    # --- XỬ LÝ DỮ LIỆU HIỂN THỊ ---
    def g(field, default="🔒 Ẩn"):
        return data.get(field, default)

    name = g('name')
    is_verified = "💎" if data.get("is_verified") else ""
    gender = {"male": "Nam 👨", "female": "Nữ 👩"}.get(data.get("gender"), "Ẩn 🔒")
    sub = data.get("subscribers", {}).get("summary", {}).get("total_count", 0)
    
    hometown = data.get("hometown", {}).get("name", "N/A")
    location = data.get("location", {}).get("name", "N/A")
    work = data.get("work", [{}])[0].get("employer", {}).get("name", "N/A")
    edu = data.get("education", [{}])[-1].get("school", {}).get("name", "N/A")
    
    c_time = g('created_time', 'N/A').split("T")[0]
    u_time = g('updated_time', 'N/A').split("T")[0]

    msg = f"👤 <b>{name.upper()}</b> {is_verified}\n"
    msg += f"<code>ID: {uid}</code>\n"
    msg += f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
    msg += f"📅 <b>Ngày tạo:</b> <code>{c_time}</code>\n"
    msg += f"🎂 <b>Sinh nhật:</b> <code>{g('birthday')}</code>\n"
    msg += f"⚧ <b>Giới tính:</b> {gender}\n"
    msg += f"👥 <b>Follower:</b> <code>{sub:,}</code>\n"
    msg += f"💍 <b>Hôn nhân:</b> {g('relationship_status')}\n"
    
    if hometown != "N/A" or location != "N/A":
        msg += f"<code>────────────────────</code>\n"
        msg += f"🏠 <b>Quê quán:</b> {hometown}\n"
        msg += f"📍 <b>Sống tại:</b> {location}\n"
    
    if work != "N/A" or edu != "N/A":
        msg += f"💼 <b>Công việc:</b> {work}\n"
        msg += f"🎓 <b>Học vấn:</b> {edu}\n"

    msg += f"<code>────────────────────</code>\n"
    msg += f"📝 <b>Tiểu sử:</b> <i>{g('about', 'Trống')}</i>\n"
    msg += f"🔗 <a href='https://fb.com/{uid}'><b>MỞ TRANG CÁ NHÂN</b></a>\n"
    msg += f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
    msg += f"✨ <i>Cập nhật: {u_time}</i>"

    await sent_msg.edit_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 <b>Gửi UID, Link hoặc Username FB để check!</b>", parse_mode=ParseMode.HTML)

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_token))
    app.add_handler(CommandHandler("grant", grant_user))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()
