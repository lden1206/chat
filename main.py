from flask import Flask, request
import asyncio
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters
import json
import os

app = Flask(__name__)

TOKEN = os.environ.get("ZALO_BOT_TOKEN", "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL")
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")  # ✅ root

def norm_text(s: str) -> str:
    if not s:
        return ""
    return " ".join(s.lower().strip().split())

def load_mechanical_dict(path: str) -> dict:
    # Không crash app nếu thiếu file, để service vẫn lên và bạn debug webhook
    if not os.path.exists(path):
        print(f"[WARN] Missing dict file: {path}", flush=True)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("[WARN] medictdata.json must be a dict/object", flush=True)
        return {}

    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_mechanical_dict(DICT_PATH)

async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    query = norm_text(update.message.text)

    if query in MECHANICAL_DICT:
        item = MECHANICAL_DICT[query]
        response = (
            f"🔤 {query}\n"
            f"{item.get('ipa', '')}\n\n"
            f"🇻🇳 {item.get('meaning_vi', '')}\n\n"
            f"📘 {item.get('example_en', '')}\n"
            f"📙 {item.get('example_vi', '')}\n"
            f"📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')}"
        )
    else:
        response = f"Xin lỗi, mình chưa có từ {query}"

    await update.message.reply_text(response)

dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/", methods=["GET"])
def index():
    return "<h1>Bot Từ Điển đang hoạt động!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True) or {}
    update = Update.de_json(payload.get("result", payload), bot)
    asyncio.run(dispatcher.process_update(update))
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8443"))  # ✅ Render dùng PORT
    app.run(host="0.0.0.0", port=port)
