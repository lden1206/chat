from flask import Flask, request
import os
import json
import difflib
import re
import random

from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters

app = Flask(__name__)

# ================= CONFIG =================
TOKEN = os.getenv("ZALO_TOKEN", "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL")
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

VALID_BOOKS = ["tack1", "tack2", "tackcb3", "tackcb4"]
VALID_LESSONS = [str(i) for i in range(1, 11)]

# ================= LOAD DATA =================
def norm_text(s):
    if not s:
        return ""
    return " ".join(s.lower().strip().split())

def load_dict(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {norm_text(k): v for k, v in data.items()}

MECHANICAL_DICT = load_dict(DICT_PATH)
DICT_KEYS = list(MECHANICAL_DICT.keys())

USER_STATES = {}

# ================= FORMAT WORD =================
def format_word_response(word, item):
    clean = "".join(word.split())
    audio = item.get("audio_url")

    if not audio or not str(audio).endswith(".mp3"):
        audio = f"https://translate.google.com/translate_tts?ie=UTF-8&q={clean}&tl=en&client=tw-ob"

    return (
        f"🔤 {word.upper()} ({item.get('pos','')}): {item.get('meaning_vi','')}\n"
        f"🔊 {item.get('ipa','')} - {audio}\n"
        f"Ví dụ:\n"
        f"🇬🇧 {item.get('example_en','')}\n"
        f"🇻🇳 {item.get('example_vi','')}\n"
        f"(📚 Bài {item.get('lesson')} - Sách {item.get('book')})"
    )

# ================= BOOK LESSON =================
def extract_book_lesson(text):
    text = text.lower()

    book = None
    for b in VALID_BOOKS:
        if b in text:
            book = b
            break

    lesson_match = re.search(r"(lesson|bài)\s*(\d+)", text)
    lesson = lesson_match.group(2) if lesson_match else None

    return book, lesson

def get_words(book, lesson):
    result = {}
    for k, v in MECHANICAL_DICT.items():
        if str(v.get("book")).lower() == book and str(v.get("lesson")) == lesson:
            result[k] = v
    return result

# ================= QUIZ =================
def generate_quiz(words_dict):
    word = random.choice(list(words_dict.keys()))
    correct = words_dict[word]["meaning_vi"]

    all_meanings = [
        v["meaning_vi"]
        for v in MECHANICAL_DICT.values()
        if v.get("meaning_vi")
    ]

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

# ================= HANDLE MESSAGE =================
async def handle_message(update: Update, context):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat.id
    raw = update.message.text
    text = norm_text(raw)
    state = USER_STATES.get(chat_id, {})

    # ========= QUIZ ANSWER =========
    if state.get("mode") == "quiz_answer":

        if text.lower() == state["correct"]:
            await update.message.reply_text("✅ Chính xác! 🎉")
        else:
            await update.message.reply_text(
                f"❌ Sai rồi!\nĐáp án đúng: {state['correct'].upper()}"
            )

        await update.message.reply_text("Bạn có muốn chơi tiếp không? (có / không)")
        state["mode"] = "quiz_continue"
        USER_STATES[chat_id] = state
        return

    # ========= QUIZ CONTINUE =========
    if state.get("mode") == "quiz_continue":

        if "có" in text:
            question, correct = generate_quiz(state["words"])
            USER_STATES[chat_id] = {
                "mode": "quiz_answer",
                "correct": correct,
                "words": state["words"]
            }
            await update.message.reply_text(question)
        else:
            USER_STATES.pop(chat_id, None)
            await bot.send_sticker(
                chat_id,
                "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.webp"
            )
        return

    # ========= LIST DETAIL =========
    if state.get("mode") == "list_detail":

        if text in MECHANICAL_DICT:
            item = MECHANICAL_DICT[text]
            await update.message.reply_text(format_word_response(text, item))
        else:
            suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.6)
            if suggestions:
                await update.message.reply_text(
                    "Bạn có muốn tra:\n" + "\n".join([f"• {s}" for s in suggestions])
                )
            else:
                await update.message.reply_text("Từ không tồn tại.")

        USER_STATES.pop(chat_id, None)
        return

    # ========= MENU =========
    if state.get("mode") == "menu":

        if text == "1":
            words = state["words"]
            response = "📚 Danh sách từ:\n\n"
            for w, item in words.items():
                response += f"• {w} : {item.get('meaning_vi')}\n"

            await update.message.reply_text(response)
            await update.message.reply_text("Bạn muốn xem chi tiết từ nào?")
            USER_STATES[chat_id] = {"mode": "list_detail"}
            return

        if text == "2":
            question, correct = generate_quiz(state["words"])
            USER_STATES[chat_id] = {
                "mode": "quiz_answer",
                "correct": correct,
                "words": state["words"]
            }
            await update.message.reply_text(question)
            return

    # ========= 1. TRA TỪ =========
    if text in MECHANICAL_DICT:
        item = MECHANICAL_DICT[text]
        await update.message.reply_action('typing')
        await update.message.reply_text(response)
        if img and img.startswith("http"):
            await update.message.reply_action('sending photo')
            await bot.send_photo(update.message.chat.id, "", img)        
        return

    # ========= 2. SUGGESTION =========
    suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.6)
    if suggestions:
        await update.message.reply_text(
            f"❌ Không tìm thấy '{raw}'.\n\n"
            "💡 Có thể bạn muốn tìm:\n" +
            "\n".join([f"• {s}" for s in suggestions])
        )
        return

    # ========= 3. BOOK LESSON =========
    book, lesson = extract_book_lesson(text)

    if book and book not in VALID_BOOKS:
        await update.message.reply_text(
            "❌ Sách không hợp lệ.\nChỉ có: tack1, tack2, tackcb3, tackcb4"
        )
        return

    if lesson and lesson not in VALID_LESSONS:
        await update.message.reply_text("❌ Lesson phải từ 1 đến 10.")
        return

    if book and lesson:
        words = get_words(book, lesson)
        if words:
            USER_STATES[chat_id] = {
                "mode": "menu",
                "words": words
            }
            await update.message.reply_text(
                f"📚 {book.upper()} - Lesson {lesson}\n\n"
                "1️⃣ Liệt kê từ\n"
                "2️⃣ Quiz trắc nghiệm"
            )
        else:
            await update.message.reply_text("Không tìm thấy dữ liệu bài này.")
        return

    if book and not lesson:
        await update.message.reply_text(
            f"Bạn muốn tra {book.upper()} lesson mấy? (1-10)"
        )
        return

    if lesson and not book:
        await update.message.reply_text(
            "Bạn muốn tra lesson này ở sách nào?\n"
            "tack1, tack2, tackcb3, tackcb4"
        )
        return

    # ========= 4. KHÔNG TÌM THẤY =========
    await update.message.reply_text(
        f"Xin lỗi, mình chưa có từ '{raw}'.\n"
        "Vui lòng nhập từ khác hoặc tra theo cú pháp: tack1 lesson 2"
    )

# ================= DISPATCHER =================
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/")
def index():
    return "Bot Dictionary Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    data = payload.get("result") or payload
    update = Update.de_json(data, bot)

    if hasattr(dispatcher, "process_update_sync"):
        dispatcher.process_update_sync(update)
    else:
        import asyncio
        asyncio.run(dispatcher.process_update(update))

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
