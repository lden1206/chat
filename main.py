from flask import Flask, request
import asyncio
# Cần cài đặt: pip install nest_asyncio
import nest_asyncio 
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters
import json
import os
import difflib
import random

# --- FIX LỖI EVENT LOOP ---
nest_asyncio.apply()

app = Flask(__name__)

# --- CẤU HÌNH ---
# Lưu ý: Nên dùng biến môi trường để bảo mật Token
TOKEN = "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL"
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

# --- HÀM XỬ LÝ DỮ LIỆU ---
def norm_text(s: str) -> str:
    if not s: return ""
    return " ".join(s.lower().strip().split())

def load_mechanical_dict(path: str) -> dict:
    if not os.path.exists(path):
        print("Warning: Không tìm thấy file medictdata.json")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_mechanical_dict(DICT_PATH)
DICT_KEYS = list(MECHANICAL_DICT.keys())

# Biến lưu trạng thái người dùng
USER_STATES = {} 

def format_word_response(word, item):
    # Xử lý POS
    raw_pos = item.get('pos', '')
    pos_str = f"({raw_pos})" if raw_pos else ""

    return (
        f"🔤 {word.upper()} {pos_str}\n"
        f"🗣️ {item.get('ipa', '')}\n"
        f"🇻🇳 Nghĩa: {item.get('meaning_vi', '')}\n\n"
        f"Ví dụ: \n"
        f"🏴󠁧󠁢󠁥󠁮󠁧󠁿 {item.get('example_en', '')}\n"
        f"🇻🇳 {item.get('example_vi', '')}\n"
        f"(📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')})"
    )

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    user_id = update.message.from_id
    raw = update.message.text
    text_lower = norm_text(raw)

    # 1. BẮT ĐẦU QUIZ
    if text_lower == "quiz":
        USER_STATES[user_id] = "WAITING_QUIZ_TYPE"
        await update.message.reply_text(
            "🧠 BẠN MUỐN LÀM QUIZ GÌ?\n\n"
            "1️⃣. Ngẫu nhiên (tất cả các từ)\n"
            "2️⃣. Theo bài học (Lesson)\n\n"
            "👉 Hãy chat số '1' hoặc '2' để chọn."
        )
        return

    # 2. XỬ LÝ KHI ĐANG TRONG TRẠNG THÁI QUIZ
    if user_id in USER_STATES:
        state = USER_STATES[user_id]

        # Giai đoạn chọn loại Quiz
        if state == "WAITING_QUIZ_TYPE":
            if "1" in text_lower or "ngẫu nhiên" in text_lower:
                random_word = random.choice(DICT_KEYS)
                item = MECHANICAL_DICT[random_word]
                response = "🎲 TỪ NGẪU NHIÊN CHO BẠN:\n\n" + format_word_response(random_word, item)
                del USER_STATES[user_id] # Xóa trạng thái

            elif "2" in text_lower or "lesson" in text_lower:
                USER_STATES[user_id] = "WAITING_LESSON_NUM"
                response = "📚 Bạn muốn ôn tập Lesson số mấy? (Nhập số)"
                # Chưa xóa trạng thái, chờ nhập số
                await update.message.reply_text(response)
                return 

            else:
                response = "⚠️ Vui lòng chọn '1' hoặc '2'. Hoặc gõ 'huy' để thoát."
                if text_lower == "huy":
                    del USER_STATES[user_id]
                    response = "Đã hủy chế độ Quiz."
            
            await update.message.reply_text(response)
            return

        # Giai đoạn nhập số Lesson
        elif state == "WAITING_LESSON_NUM":
            try:
                target_lesson = str(int(text_lower))
                filtered_words = [
                    k for k, v in MECHANICAL_DICT.items() 
                    if str(v.get('lesson', '')) == target_lesson
                ]

                if filtered_words:
                    random_word = random.choice(filtered_words)
                    item = MECHANICAL_DICT[random_word]
                    response = f"📚 TỪ NGẪU NHIÊN (LESSON {target_lesson}):\n\n" + format_word_response(random_word, item)
                else:
                    response = f"❌ Không tìm thấy từ vựng nào trong Lesson {target_lesson}."
                
                del USER_STATES[user_id] # Xong quiz, xóa trạng thái
            
            except ValueError:
                response = "⚠️ Vui lòng nhập đúng con số. Gõ 'huy' để thoát."
                if text_lower == "huy":
                    del USER_STATES[user_id]
                    response = "Đã hủy."

            await update.message.reply_text(response)
            return

    # 3. TRA TỪ ĐIỂN (Nếu không làm Quiz)
    query = text_lower
    if query in MECHANICAL_DICT:
        item = MECHANICAL_DICT[query]
        response = format_word_response(query, item)
    else:
        suggestions = difflib.get_close_matches(query, DICT_KEYS, n=5, cutoff=0.5)
        if suggestions:
            list_str = "\n".join([f"• {s}" for s in suggestions])
            response = (
                f"❌ Không tìm thấy '{raw}'.\n\n"
                f"💡 Có thể bạn muốn tìm:\n{list_str}"
            )
        else:
            response = f"Xin lỗi, mình chưa có từ '{raw}'."

    await update.message.reply_text(response)

# --- THIẾT LẬP FLASK & DISPATCHER ---
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/")
def index():
    return "<h1>Bot Dictionary V3 is running!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    if not payload: return "No payload", 400
    
    data = payload.get("result", payload)
    update = Update.de_json(data, bot)

    # Logic async an toàn nhờ nest_asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(dispatcher.process_update(update))
    finally:
        loop.close()

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8443)
