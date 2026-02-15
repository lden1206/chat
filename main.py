from flask import Flask, request
import asyncio
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters
import json
import os

app = Flask(__name__)

TOKEN = "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL"
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "chat", "medictdata.json")

def norm_text(s: str) -> str:
    """
    Chuẩn hoá để tra từ ổn định:
    - lower
    - strip đầu/cuối
    - gộp nhiều khoảng trắng thành 1
    """
    if not s:
        return ""
    return " ".join(s.lower().strip().split())

def load_mechanical_dict(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Không tìm thấy file từ điển: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("File medictdata.json của bạn phải là dạng object/dict { 'word': {...} }")

    # Chuẩn hoá key (xử lý cả trường hợp key có khoảng trắng cuối như 'be on tv ')
    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_mechanical_dict(DICT_PATH)

async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    raw = update.message.text
    query = norm_text(raw)

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

@app.route("/")
def index():
    return "<h1>Bot Từ Điển đang hoạt động!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True) or {}
    update = Update.de_json(payload.get("result", payload), bot)

    # chạy async trong Flask sync route
    try:
        asyncio.run(dispatcher.process_update(update))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(dispatcher.process_update(update))
        loop.close()

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8443)
