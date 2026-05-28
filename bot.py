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
usage_table = db.table('usage')  # Bảng lưu số lượt dùng trong ngày

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

# --- LOGIC KIỂM TRA & CẬP NHẬT LƯỢT DÙNG TRONG NGÀY ---
def check_and_update_limit(user_id, username, bulk_count=1):
    if user_id == ADMIN_ID:
        return True, 99999, 99999 # Admin không giới hạn
        
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    U = Query()
    
    # Lấy thông tin cấu hình limit cá nhân (nếu có)
    user_config = users_table.get((U.id == user_id) | (U.username == username))
    max_limit = 5 # Mặc định ai cũng có 5 lần/ngày
    
    if user_config:
        max_limit = user_config.get('max_limit', 5)
        # Đồng bộ ID nếu trước đó cấu hình bằng username
        if not user_config.get('id') and user_id:
            users_table.update({'id': user_id}, (U.username == username))

    # Đếm số lượt đã dùng hôm nay
    usage = usage_table.get((U.user_id == user_id) & (U.date == today))
    current_count = usage['count'] if usage else 0
    
    if current_count + bulk_count > max_limit:
        return False, current_count, max_limit
        
    # Tăng lượt sử dụng lên bulk_count
    if usage:
        usage_table.update({'count': current_count + bulk_count}, (U.user_id == user_id) & (U.date == today))
    else:
        usage_table.insert({'user_id': user_id, 'date': today, 'count': bulk_count})
        
    return True, current_count + bulk_count, max_limit

# --- LOGIC XOAY VÒNG TOKEN ---
def request_fb_api(uid):
    all_t = get_tokens()
    if not all_t: 
        return {"error_internal": "Hệ thống chưa có Token. Vui lòng liên hệ Admin!"}
    
    num_tokens = len(all_t)
    for _ in range(num_tokens):
        with token_lock:
            token = all_t[current_token_index % num_tokens]
        
        url = f"https://graph.facebook.com/{uid}?fields={FIELDS}&access_token={token}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if "error" in data:
                msg = data["error"].get("message", "").lower()
                if any(k in msg for k in ["access token", "expired", "session", "checkpoint", "invalid"]):
                    rotate_token()
                    continue
            return data
        except:
            rotate_token()
            continue
            
    return {"error_internal": "Tất cả Token đã die hoặc gặp sự cố. Vui lòng liên hệ Admin!"}

# --- XỬ LÝ LỆNH /INFOFB ---
async def handle_infofb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # 1. Kiểm tra tham số truyền vào lệnh
    if not context.args:
        await update.message.reply_text("❌ <b>Vui lòng nhập UID hoặc Link!</b>\n👉 Cú pháp: <code>/infofb [uid hoặc link]</code>", parse_mode=ParseMode.HTML)
        return

    raw_input = context.args[0].strip()
    
    # 2. Kiểm tra giới hạn lượt check trong ngày
    allowed, current, maximum = check_and_update_limit(user_id, username)
    if not allowed:
        await update.message.reply_text(
            f"🚫 <b>Bạn đã hết lượt check của ngày hôm nay ({current}/{maximum}).</b>\n"
            f"💡 Muốn tăng thêm limit, vui lòng inbox cho admin @lhba5510 để nâng cấp!", 
            parse_mode=ParseMode.HTML
        )
        return

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
    msg += f"📊 <b>Lượt check hôm nay:</b> <code>{current}/{maximum if maximum < 99999 else 'Vô hạn'}</code>\n"
    msg += f"✨ <i>Cập nhật: {u_time}</i>"

    await sent_msg.edit_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# --- XỬ LÝ LỆNH /SLL (CHECK FILE SỐ LƯỢNG LỚN) ---
async def handle_sll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Kiểm tra xem người dùng có quyền check số lượng lớn không (Phải là Admin hoặc được cấu hình max_limit cao, ví dụ >= 100)
    U = Query()
    user_config = users_table.get((U.id == user_id) | (U.username == username))
    max_limit = user_config.get('max_limit', 5) if user_config else 5
    
    if user_id != ADMIN_ID and max_limit < 100:
        await update.message.reply_text("🚫 <b>Bạn không có quyền sử dụng chức năng check Số Lượng Lớn.</b>\nVui lòng liên hệ Admin để nâng cấp quyền!", parse_mode=ParseMode.HTML)
        return

    # Kiểm tra xem người dùng có reply kèm file không
    if not update.message.document:
        await update.message.reply_text("❌ <b>Vui lòng gửi đính kèm file .txt chứa danh sách UID/Link Facebook!</b>\n👉 Cú pháp: Nhấp chọn File -> Thêm caption là <code>/sll</code>", parse_mode=ParseMode.HTML)
        return

    doc = update.message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Hệ thống chỉ hỗ trợ xử lý file định dạng <code>.txt</code>", parse_mode=ParseMode.HTML)
        return

    sent_msg = await update.message.reply_text("⏳ <b>Đang tải và xử lý file... Vui lòng đợi.</b>", parse_mode=ParseMode.HTML)
    
    try:
        # Tải file từ Telegram
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        content = file_bytes.decode('utf-8')
        
        # Đọc danh sách các dòng trong file
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            await sent_msg.edit_text("❌ File trống hoặc không đọc được dữ liệu hợp lệ.")
            return

        total_lines = len(lines)
        
        # Kiểm tra trước số lượng giới hạn còn lại trong ngày (Nếu không phải admin)
        allowed, current, maximum = check_and_update_limit(user_id, username, bulk_count=total_lines)
        if not allowed:
            await sent_msg.edit_text(
                f"🚫 <b>File của bạn có {total_lines} dòng, vượt quá số lượng check còn lại trong ngày của bạn.</b>\n"
                f"📊 Hiện tại đã dùng: <code>{current}/{maximum}</code>", 
                parse_mode=ParseMode.HTML
            )
            return

        # Tiến hành quét thông tin theo danh sách
        result_text = "📊 <b>KẾT QUẢ CHECK FILE SỐ LƯỢNG LỚN</b>\n"
        result_text += f"📁 File: <code>{doc.file_name}</code> (Tổng: {total_lines})\n"
        result_text += f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
        
        success_count = 0
        for idx, item in enumerate(lines, start=1):
            # Lấy UID
            if item.isdigit():
                uid = item
            else:
                uid_data = get_fb_uid(item)
                uid = uid_data.get('id')
                if not uid:
                    result_text += f"{idx}. <code>{item}</code> ❌ Lỗi lấy UID\n"
                    continue
            
            # Gửi API Facebook
            data = request_fb_api(uid)
            if "error_internal" in data:
                result_text += f"{idx}. <code>{uid}</code> ⚠️ Lỗi hệ thống: {data['error_internal']}\n"
            elif "error" in data:
                result_text += f"{idx}. <code>{uid}</code> ❌ Lỗi API FB\n"
            else:
                name = data.get('name', 'Ẩn').upper()
                gender = {"male": "Nam 👨", "female": "Nữ 👩"}.get(data.get("gender"), "Ẩn 🔒")
                sub = data.get("subscribers", {}).get("summary", {}).get("total_count", 0)
                result_text += f"{idx}. 👤 <b>{name}</b> | ID: <code>{uid}</code> | {gender} | 👥 {sub:,} follow\n"
                success_count += 1

        result_text += f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n"
        result_text += f"✅ Đã check thành công <b>{success_count}/{total_lines}</b> tài khoản."
        
        # Gửi lại kết quả đầy đủ cho người dùng
        await sent_msg.edit_text(result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    except Exception as e:
        await sent_msg.edit_text(f"❌ <b>Đã có lỗi xảy ra trong quá trình xử lý file:</b> <code>{str(e)}</code>", parse_mode=ParseMode.HTML)

# --- COMMANDS ADMIN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 <b>Gửi lệnh theo cú pháp để tra cứu thông tin:</b>\n👉 <code>/infofb [UID hoặc Link Facebook]</code>\n\n📌 <i>Mỗi người dùng có sẵn 5 lượt check miễn phí mỗi ngày!</i>", parse_mode=ParseMode.HTML)

async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    for t in context.args: tokens_table.insert({'value': t})
    await update.message.reply_text(f"✅ Đã thêm {len(context.args)} token.")

async def clear_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    tokens_table.truncate()
    await update.message.reply_text("🗑 <b>Đã xoá sạch danh sách Token.</b>", parse_mode=ParseMode.HTML)

# Cải tiến lệnh GRANT hỗ trợ thay đổi số lượt Limit tối đa trong ngày
async def grant_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        user_input = context.args[0] # Có thể là ID hoặc @username
        max_limit = int(context.args[1]) # Số lượt tối đa mỗi ngày mới
        
        U = Query()
        if user_input.startswith("@"):
            username = user_input.replace("@", "")
            users_table.upsert({'username': username, 'max_limit': max_limit}, U.username == username)
            await update.message.reply_text(f"✅ Đã cấu hình limit cho <b>{user_input}</b> thành {max_limit} lần/ngày.", parse_mode=ParseMode.HTML)
        else:
            t_id = int(user_input)
            users_table.upsert({'id': t_id, 'max_limit': max_limit}, U.id == t_id)
            await update.message.reply_text(f"✅ Đã cấu hình limit cho ID <code>{t_id}</code> thành {max_limit} lần/ngày.", parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ HD: `/grant [ID hoặc @username] [Số lượt tối đa/ngày]`")

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_token))
    app.add_handler(CommandHandler("clear", clear_tokens))
    app.add_handler(CommandHandler("grant", grant_user))
    app.add_handler(CommandHandler("infofb", handle_infofb)) 
    
    # Đăng ký handler xử lý file đính kèm kèm caption lệnh /sll
    app.add_handler(MessageHandler(filters.Document.ALL & filters.Caption(["/sll"]), handle_sll))
    
    print("Bot is running...")
    app.run_polling()
