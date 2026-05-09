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

# --- WEB SERVER ---
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

# --- LOGIC GET UID (GIỮ NGUYÊN 100% + FIX 403) ---
def get_fb_uid(link_fb):
    if not link_fb.startswith("http"):
        url_to_check = f"https://www.facebook.com/{link_fb}"
    else:
        url_to_check = link_fb

    api_url = "https://ffb.vn/api/tool/get-id-fb?idfb=" + requests.utils.quote(url_to_check)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://ffb.vn/'
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": f"Lỗi kết nối API: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- KIỂM TRA QUYỀN ---
def check_permission(user_id):
    if user_id == ADMIN_ID: return True
    U = Query()
    user = users_table.get(U.id == user_id)
    if user:
        expiry = datetime.datetime.fromisoformat(user['expiry'])
        if expiry > datetime.datetime.now(): return True
    return False

# --- LOGIC XOAY VÒNG TOKEN (ĐÃ TỐI ƯU THEO Ý BẠN) ---
def request_fb_api(uid):
    all_t = get_tokens()
    if not all_t: 
        return {"error_internal": "Hệ thống chưa có Token. Vui lòng liên hệ Admin!"}
    
    # Vòng lặp quét qua toàn bộ danh sách token
    num_tokens = len(all_t)
    for _ in range(num_tokens):
        with token_lock:
            # Lấy token hiện tại
            token = all_t[current_token_index % num_tokens]
        
        url = f"https://graph.facebook.com/{uid}?fields={FIELDS}&access_token={token}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            
            # Nếu token die hoặc hết hạn
            if "error" in data:
                msg = data["error"].get("message", "").lower()
                # Các dấu hiệu token die/checkpoint/hết hạn
                if any(k in msg for k in ["access token", "expired", "session", "checkpoint", "invalid"]):
                    rotate_token() # Chuyển sang token tiếp theo
                    continue # Thử lại với token mới
            
            # Nếu thành công hoặc lỗi không phải do token (ví dụ UID sai), trả về luôn
            return data
        except:
            rotate_token()
            continue
            
    # Nếu đã chạy hết vòng lặp mà không token nào dùng được
    return {"error_internal": "Tất cả Token đã die hoặc gặp sự cố. Vui lòng liên hệ Admin!"}

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_permission(user_id):
        await update.message.reply_text("🚫 <b>Bạn không có quyền hoặc hết hạn sử dụng.</b>", parse_mode=ParseMode.HTML)
        return

    raw_input = update.message.text.strip()
    sent_msg = await update.message.reply_text("⌛ <b>Đang trích xuất dữ liệu...</b>", parse_mode=ParseMode.HTML)

    if raw_input.isdigit():
        uid = raw_input
    else:
        uid_data = get_fb_uid(raw_input)
        uid = uid_data.get('id')
        if not uid:
            err = uid_data.get('message', 'Không tìm thấy UID')
            await sent_msg.edit_text(f"❌ <b>Lỗi lấy UID:</b> <code>{err}</code>", parse_mode=ParseMode.HTML)
            return

    data = request_fb_api(uid)
    if "error_internal" in data:
        await sent_msg.edit_text(f"⚠️ <b>Thông báo:</b> <code>{data['error_internal']}</code>", parse_mode=ParseMode.HTML)
        return
    elif "error" in data:
        err = data["error"].get("message")
        await sent_msg.edit_text(f"❌ <b>Lỗi API FB:</b> <code>{err}</code>", parse_mode=ParseMode.HTML)
        return

    # --- HIỂN THỊ THÔNG TIN ---
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
    msg += f"🌐 <b>Ngôn ngữ:</b> {g('locale')} (GMT+{g('timezone')})\n"
    msg += f"📝 <b>Tiểu sử:</b> <i>{g('about', 'Trống')}</i>\n"
    msg += f"🔗 <a href='https://fb.com/{uid}'><b>MỞ TRANG CÁ NHÂN</b></a>\n"
    msg += f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
    msg += f"✨ <i>Cập nhật: {u_time}</i>"

    await sent_msg.edit_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# --- COMMANDS ADMIN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 <b>Gửi UID/Link Facebook để check!</b>", parse_mode=ParseMode.HTML)

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    for t in context.args: tokens_table.insert({'value': t})
    await update.message.reply_text(f"✅ Đã thêm {len(context.args)} token.")

async def clear_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    tokens_table.truncate()
    await update.message.reply_text("🗑 <b>Đã xoá sạch danh sách Token.</b>", parse_mode=ParseMode.HTML)

async def grant_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        t_id, days = int(context.args[0]), int(context.args[1])
        expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        users_table.upsert({'id': t_id, 'expiry': expiry}, Query().id == t_id)
        await update.message.reply_text(f"✅ Đã cấp quyền cho {t_id} trong {days} ngày.")
    except: await update.message.reply_text("❌ HD: `/grant [ID] [Ngày]`")

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_token))
    app.add_handler(CommandHandler("clear", clear_tokens))
    app.add_handler(CommandHandler("grant", grant_user))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()
