from flask import Flask, request
import asyncio
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters
import json
import os
import difflib

app = Flask(__name__)
TOKEN = "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL" 
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

def norm_text(s: str) -> str:
    if not s:
        return ""
    return " ".join(s.lower().strip().split())

def load_mechanical_dict(path: str) -> dict:
    if not os.path.exists(path):
        # Trả về dict rỗng để code không chết nếu thiếu file
        print(f"Cảnh báo: Không tìm thấy {path}") 
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_mechanical_dict(DICT_PATH)
DICT_KEYS = list(MECHANICAL_DICT.keys()) # <--- Tạo danh sách key để tra cứu nhanh

async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    raw = update.message.text
    query = norm_text(raw)

    if query in MECHANICAL_DICT:
        item = MECHANICAL_DICT[query]
        raw_pos = item.get("pos", "")
        raw_audio = item.get("audio_url", "")
        pos_str = f"({raw_pos})" if raw_pos else ""
        audio_str = f"({raw_audio})" if raw_audio else ""
        response = (
        f"🔤 {word.upper()} {pos_str}: {item.get('meaning_vi', '')}\n"
        f"🗣️ {item.get('ipa', '')} {audio_str} \n"
        f"Ví dụ: \n"
        f"🇬🇧 {item.get('example_en', '')}\n"
        f"🇻🇳 {item.get('example_vi', '')}\n"
        f"(📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')})"
    )
    else:
        # Logic gợi ý từ gần đúng
        suggestions = difflib.get_close_matches(query, DICT_KEYS, n=5, cutoff=0.5)
        
        if suggestions:
            suggest_text = "\n".join([f"• {s}" for s in suggestions])
            response = (
                f"❌ Không tìm thấy '{raw}'.\n\n"
                f"💡 Có thể bạn muốn tìm:\n{suggest_text}"
            )
        else:
            response = f"Xin lỗi, mình không tìm thấy từ '{raw}' trong từ điển."

    await update.message.reply_text(response)

dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/")
def index():
    return "<h1>Bot Từ Điển đang hoạt động!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    
    if not payload:
        return "No payload", 400
        
    data = payload.get("result", payload)
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
