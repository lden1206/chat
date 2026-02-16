from flask import Flask, request
import os
import json
import difflib
import random

from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters

app = Flask(__name__)

# --- CẤU HÌNH (khuyến nghị dùng ENV trên Render) ---
TOKEN = os.getenv("ZALO_TOKEN", "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL")
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

# --- HÀM XỬ LÝ DỮ LIỆU ---
def norm_text(s: str) -> str:
    if not s:
        return ""
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

# Lưu trạng thái theo chat_id (ổn định nhất khi làm bot 1-1)
USER_STATES = {}

def format_word_response(word, item):
    raw_pos = item.get("pos", "")
    raw_audio = item.get("audio_url", "")
    pos_str = f"({raw_pos})" if raw_pos else ""
    audio_str = f"({raw_audio})" if raw_audio else ""
    return (
        f"🔤 {word.upper()} {pos_str}: {item.get('meaning_vi', '')}\n"
        f"🗣️ {item.get('ipa', '')} \n"
        f"Ví dụ: \n"
        f"🇬🇧 {item.get('example_en', '')}\n"
        f"🇻🇳 {item.get('example_vi', '')}\n"
        f"(📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')})"
    ), audio_str

# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    raw = update.message.text
    text_lower = norm_text(raw)

    # chat_id dùng để reply + lưu trạng thái
    chat_id = getattr(getattr(update.message, "chat", None), "id", None)
    if chat_id is None:
        # Nếu không có chat.id thì không xử lý (tránh crash)
        return
    user_key = str(chat_id)

    # Hủy mọi chế độ nếu gõ "huy"
    if text_lower == "huy":
        USER_STATES.pop(user_key, None)
        await update.message.reply_text("Đã hủy.")
        return

    # --- LOGIC QUIZ ---
    if text_lower == "quiz":
        if not DICT_KEYS:
            await update.message.reply_text("⚠️ Từ điển đang rỗng hoặc chưa load được medictdata.json.")
            return
        USER_STATES[user_key] = "WAITING_QUIZ_TYPE"
        await update.message.reply_text(
            "🧠 BẠN MUỐN LÀM QUIZ GÌ?\n\n"
            "1️⃣. Ngẫu nhiên (tất cả các từ)\n"
            "2️⃣. Theo bài học (Lesson)\n\n"
            "👉 Hãy chat số '1' hoặc '2' để chọn. (Gõ 'huy' để thoát)"
        )
        return

    # --- XỬ LÝ KHI ĐANG TRONG TRẠNG THÁI QUIZ ---
    if user_key in USER_STATES:
        state = USER_STATES[user_key]

        if state == "WAITING_QUIZ_TYPE":
            if "1" in text_lower or "ngẫu nhiên" in text_lower:
                if not DICT_KEYS:
                    response = "⚠️ Từ điển đang rỗng."
                else:
                    random_word = random.choice(DICT_KEYS)
                    item = MECHANICAL_DICT[random_word]
                    response = "🎲 TỪ NGẪU NHIÊN CHO BẠN:\n\n" + format_word_response(random_word, item)
                USER_STATES.pop(user_key, None)
                await update.message.reply_text(response)
                return

            if "2" in text_lower or "lesson" in text_lower:
                USER_STATES[user_key] = "WAITING_LESSON_NUM"
                await update.message.reply_text("📚 Bạn muốn ôn tập Lesson số mấy? (Nhập số)")
                return

            await update.message.reply_text("⚠️ Vui lòng chọn '1' hoặc '2'. (Gõ 'huy' để thoát)")
            return

        if state == "WAITING_LESSON_NUM":
            try:
                target_lesson = str(int(text_lower))
                filtered_words = [
                    k for k, v in MECHANICAL_DICT.items()
                    if str(v.get("lesson", "")) == target_lesson
                ]

                if filtered_words:
                    random_word = random.choice(filtered_words)
                    item = MECHANICAL_DICT[random_word]
                    response = f"📚 TỪ NGẪU NHIÊN (LESSON {target_lesson}):\n\n" + format_word_response(random_word, item)
                else:
                    response = f"❌ Không tìm thấy từ vựng nào trong Lesson {target_lesson}."

                USER_STATES.pop(user_key, None)
                await update.message.reply_text(response)
                return

            except ValueError:
                await update.message.reply_text("⚠️ Vui lòng nhập đúng con số. (Gõ 'huy' để thoát)")
                return

    # --- TRA TỪ ĐIỂN ---
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

    await update.message.reply_text(response[0])
    await update.message.reply_audio(response[1])

# --- THIẾT LẬP DISPATCHER ---
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/")
def index():
    return "<h1>Bot Dictionary V5 is running!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    if not payload:
        return "No payload", 400

    data = payload.get("result") or payload
    update = Update.de_json(data, bot)

    # ✅ CHẠY SYNC, KHÔNG TẠO EVENT LOOP, KHÔNG NEST_ASYNCIO
    # Tùy version thư viện, 1 trong các cách dưới sẽ tồn tại:
    if hasattr(dispatcher, "process_update_sync"):
        dispatcher.process_update_sync(update)
    elif hasattr(dispatcher, "application") and hasattr(dispatcher.application, "process_update_sync"):
        dispatcher.application.process_update_sync(update)
    else:
        # fallback cuối cùng nếu thư viện chỉ có async
        import asyncio
        asyncio.run(dispatcher.process_update(update))

    return "ok", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
