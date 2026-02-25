from flask import Flask, request
import os
import json
import difflib
import random
import re

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
    audio_str = f"{raw_audio}" if raw_audio.endswith(".mp3") else f"https://translate.google.com/translate_tts?ie=UTF-8&q={"".join(word.split())}&tl=en&client=tw-ob"
    return (
        f"🔤 {word.upper()} {pos_str}: {item.get('meaning_vi', '')}\n"
        f"🔊 {item.get('ipa', '')} - {audio_str} \n"
        f"Ví dụ: \n"
        f"🇬🇧 {item.get('example_en', '')}\n"
        f"🇻🇳 {item.get('example_vi', '')}\n"
        f"(📚 Bài {item.get('lesson', '')} - Sách {item.get('book', '')})"
    )

# ================== BOOK LESSON ==================

def extract_book_lesson(text):
    book_match = re.search(r"book\s*(\d+)", text)
    lesson_match = re.search(r"(lesson|bài)\s*(\d+)", text)
    book = book_match.group(1) if book_match else None
    lesson = lesson_match.group(2) if lesson_match else None
    return book, lesson

def get_words_by_book_lesson(book, lesson):
    result = {}
    for k, v in MECHANICAL_DICT.items():
        if str(v.get("book")) == str(book) and str(v.get("lesson")) == str(lesson):
            result[k] = v
    return result


# ================== QUIZ ==================

def generate_quiz(words_dict):
    word = random.choice(list(words_dict.keys()))
    correct = words_dict[word]["meaning_vi"]

    all_meanings = [v["meaning_vi"] for v in MECHANICAL_DICT.values()]
    wrong = random.sample([m for m in all_meanings if m != correct], 3)

    options = wrong + [correct]
    random.shuffle(options)

    labels = ["a", "b", "c", "d"]
    correct_label = labels[options.index(correct)]

    question = (
        f"❓ Từ: {word.upper()}\n\n"
        f"A. {options[0]}\n"
        f"B. {options[1]}\n"
        f"C. {options[2]}\n"
        f"D. {options[3]}\n\n"
        "👉 Trả lời A/B/C/D"
    )

    return question, correct_label


# ================== HANDLE MESSAGE ==================

async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    chat_id = update.message.chat.id
    raw = update.message.text
    text = norm_text(raw)

    state = USER_STATES.get(chat_id, {})

    # ===== QUIZ ANSWER =====
    if state.get("mode") == "quiz_answer":

        correct = state.get("correct")

        if text.lower() == correct:
            await update.message.reply_text("✅ Chính xác! 🎉")
        else:
            await update.message.reply_text(f"❌ Sai rồi!\nĐáp án đúng: {correct.upper()}")

        await update.message.reply_text("Bạn có muốn chơi tiếp không? (có / không)")
        state["mode"] = "quiz_continue"
        USER_STATES[chat_id] = state
        return

    # ===== QUIZ CONTINUE =====
    if state.get("mode") == "quiz_continue":

        if "có" in text:
            question, correct_label = generate_quiz(state.get("words"))
            USER_STATES[chat_id] = {
                "mode": "quiz_answer",
                "correct": correct_label,
                "words": state.get("words")
            }
            await update.message.reply_text(question)
        else:
            USER_STATES.pop(chat_id, None)
            await update.message.reply_text("Cảm ơn bạn đã chơi 🥰")
        return

    # ===== MENU BOOK LESSON =====
    if state.get("mode") == "book_menu":

        words = state.get("words")

        if text == "1":
            response = "📚 Danh sách từ:\n\n"
            for w, item in words.items():
                response += f"• {w} : {item.get('meaning_vi')}\n"
            USER_STATES.pop(chat_id, None)
            await update.message.reply_text(response)
            return

        if text == "2":
            question, correct_label = generate_quiz(words)
            USER_STATES[chat_id] = {
                "mode": "quiz_answer",
                "correct": correct_label,
                "words": words
            }
            await update.message.reply_text(question)
            return

    # ===== TRA TỪ TRƯỚC =====
    if text in MECHANICAL_DICT:
        item = MECHANICAL_DICT[text]
        img = item.get("img_url", "")
        response = format_word_response(text, item)

        await update.message.reply_action("typing")
        await update.message.reply_text(response)

        if img and img.startswith("http"):
            await bot.send_photo(chat_id, "", img)
        return

    # ===== GỢI Ý =====
    suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.5)
    if suggestions:
        list_str = "\n".join([f"• {s}" for s in suggestions])
        await update.message.reply_text(
            f"❌ Không tìm thấy '{raw}'.\n\n💡 Có thể bạn muốn tìm:\n{list_str}"
        )
        return

    # ===== CHECK BOOK LESSON =====
    book, lesson = extract_book_lesson(text)

    if book and lesson:
        words = get_words_by_book_lesson(book, lesson)
        if words:
            USER_STATES[chat_id] = {
                "mode": "book_menu",
                "words": words
            }
            await update.message.reply_text(
                f"📚 Book {book} - Lesson {lesson}\n\n"
                "1️⃣ Liệt kê từ\n"
                "2️⃣ Làm quiz"
            )
        else:
            await update.message.reply_text("Không tìm thấy dữ liệu bài này.")
        return

    if book and not lesson:
        await update.message.reply_text(f"Bạn muốn tra Book {book} Lesson mấy?")
        return

    if lesson and not book:
        await update.message.reply_text(f"Bạn muốn tra Lesson {lesson} ở Book nào?")
        return

    # ===== KHÔNG TÌM THẤY =====
    await update.message.reply_text(
        f"Xin lỗi, mình chưa có từ '{raw}'.\n"
        "Vui lòng nhập từ khác hoặc tra theo cú pháp: book 1 lesson 2"
    )
'''
# --- XỬ LÝ TIN NHẮN ---
async def handle_message(update: Update, context):
    if not getattr(update, "message", None) or not getattr(update.message, "text", None):
        return

    raw = update.message.text
    text_lower = norm_text(raw)
    img = None

    # --- TRA TỪ ĐIỂN ---
    query = text_lower
    if query in MECHANICAL_DICT:
        item = MECHANICAL_DICT[query]
        img = item.get('img_url', '')
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

    await update.message.reply_action('typing')
    await update.message.reply_text(response)
    if img and img.startswith("http"):
        await bot.send_photo(update.message.chat.id, "", img)
'''
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
