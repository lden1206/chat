from flask import Flask, request
import os
import json
import difflib

from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters

app = Flask(__name__)

# ================= CONFIG =================
TOKEN = os.getenv("ZALO_TOKEN")  # Set trên Render
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

# ================= UTILS =================
def norm_text(s: str) -> str:
    if not s:
        return ""
    return " ".join(s.lower().strip().split())

def load_dict(path: str) -> dict:
    if not os.path.exists(path):
        print("⚠ Không tìm thấy medictdata.json")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_dict(DICT_PATH)
DICT_KEYS = list(MECHANICAL_DICT.keys())

# ================= FORMAT RESPONSE =================
def format_word_response(word, item):
    raw_pos = item.get("pos", "")
    raw_audio = item.get("audio_url", "") or ""

    pos_str = f"({raw_pos})" if raw_pos else ""

    if raw_audio and raw_audio.endswith(".mp3"):
        audio_str = raw_audio
    else:
        audio_str = (
            f"https://translate.google.com/translate_tts"
            f"?ie=UTF-8&q={word}&tl=en&client=tw-ob"
        )

    return (
        f"🔤 {word.upper()} {pos_str}: {item.get('meaning_vi', '')}\n"
        f"🗣️ {item.get('ipa', '')} {audio_str}\n"
        f"Ví dụ:\n"
        f"🇬🇧 {item.get('example_en', '')}\n"
        f"🇻🇳 {item.get('example_vi', '')}\n"
        f"(📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')})"
    )

# ================= MESSAGE HANDLER =================
def handle_message(update: Update, context):

    if not getattr(update, "message", None):
        return

    if not getattr(update.message, "text", None):
        return

    raw = update.message.text
    text_lower = norm_text(raw)

    if not DICT_KEYS:
        update.message.reply_text("⚠️ Từ điển chưa load được.")
        return

    if text_lower in MECHANICAL_DICT:
        item = MECHANICAL_DICT[text_lower]
        response = format_word_response(text_lower, item)
        img_url = item.get("img_url", "") or ""
    else:
        suggestions = difflib.get_close_matches(
            text_lower, DICT_KEYS, n=5, cutoff=0.5
        )

        if suggestions:
            list_str = "\n".join([f"• {s}" for s in suggestions])
            response = (
                f"❌ Không tìm thấy '{raw}'.\n\n"
                f"💡 Có thể bạn muốn tìm:\n{list_str}"
            )
        else:
            response = f"Xin lỗi, mình chưa có từ '{raw}'."

        img_url = ""

    # Gửi text
    update.message.reply_text(response)

    # Gửi ảnh nếu có
    if img_url:
        try:
            update.message.reply_photo(img_url)
        except Exception as e:
            print("Send image error:", e)

# ================= DISPATCHER =================
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

# ================= ROUTES =================
@app.route("/")
def home():
    return "Bot Dictionary is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    if not payload:
        return "No payload", 400

    data = payload.get("result") or payload
    update = Update.de_json(data, bot)

    dispatcher.process_update(update)

    return "ok", 200

# ================= RUN APP =================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
