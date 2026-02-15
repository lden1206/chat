from flask import Flask, request, jsonify
import asyncio
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, CommandHandler, MessageHandler, filters
import json
import os

app = Flask(__name__)

# --- CẤU HÌNH ---
TOKEN = 'ZALO_BOT_TOKEN_CUA_BAN'
bot = Bot(token=TOKEN)

# --- LOGIC TRA TỪ ĐIỂN ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
fpath = os.path.join(BASE_DIR, "medictdata_o.json")

with open(fpath, "r", encoding="utf-8") as f:
    MECHANICAL_DICT = json.load(f)

async def handle_message(update: Update, context):
    query = update.message.text.lower().strip()
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

# --- THIẾT LẬP DISPATCHER ---
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

# 1. Trang chủ (Frontend cực đơn giản để kiểm tra server)
@app.route('/')
def index():
    return "<h1>Bot Từ Điển Cơ Khí đang hoạt động!</h1>"

# 2. Webhook (Đầu nối API giữa Zalo và Python)
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json(force=True)
    update = Update.de_json(payload.get('result', payload), bot)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dispatcher.process_update(update))
    loop.close()
    
    return 'ok', 200

if __name__ == '__main__':
    app.run(port=8443)