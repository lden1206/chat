from flask import Flask, request
from zalo_bot import Bot, Update
from zalo_bot.ext import Dispatcher, MessageHandler, filters
import os
import json
import difflib
import re
import random

app = Flask(__name__)

# ================= CONFIG =================
TOKEN = os.getenv("ZALO_TOKEN", "2195711801638941102:eZWDRFTEXPKJbpYEiCOBPDcQZwDqQNWGNOqRPeQtSgeLaBDGMmBVAVnhWoVakDbL")
bot = Bot(token=TOKEN)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

VALID_BOOKS = ["tack1", "tack2", "tackcb3", "tackcb4"]
VALID_LESSONS = [str(i) for i in range(1, 9)]

dung = ["4b62f24ece0b27557e1a", "24bc8fd5b2905bce0281", "a643836dbf2856760f39", "e918f74acb0f22517b1e", "bce9b9b485f16caf35e0", "a800d75eeb1b02455b0a", "6dcf189124d4cd8a94c5", "a4d57f9843ddaa83f3cc"]
sai = ["ba328c1db05859060049", "ae05942ba86e4130187f", "63f661a45de1b4bfedf0", "71edfabdc6f82fa676e9", "2a80dedde2980bc65289", "3ae639bb05feeca0b5ef", "eb42921cae5947071e48", "5edd329b0edee780becf", "8d73553e697b8025d96a"]
hoicham = ["deb76d9b51deb880e1cf", "193f57106b55820bdb44", "923f491075559c0bc544", "16271c752030c96e9021", "5778d328ef6d06335f7c", "5a3f5b6267278e79d736", "009cc1d1fd9414ca4d85", "df9f0bd23797dec98786"]
ok = ["76be83d6be9357cd0e82", "2cdad7b2eaf703a95ae6", "c3112c39107cf922a06d", "0ee4fdb6c1f328ad71e2", "d768db3ae77f0e21576e", "2a13574d6b088256db19", "6dcf189124d4cd8a94c5", "aa457508494da013f95c"]
hi = ["7794b5fa88bf61e138ae", "555de371df34366a6f25", "b0804fe872ad9bf3c2bc", "26aa81c3bc8655d80c97", "5cb6159929dcc08299cd", "ce2e24061843f11da852", "168918db249ecdc0948f", "5721de71e2340b6a5225", "d977dd2ae16f0831517e", "7887f5d8c99d20c3798c"]

# ================= LOAD DATA =================
def norm_text(s):
    return " ".join(s.lower().strip().split()) if s else ""

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

    if not audio or not audio.endswith(".mp3"):
        audio = f"https://translate.google.com/translate_tts?ie=UTF-8&q={clean}&tl=en&client=tw-ob"

    return (f"🔤 {word.upper()} ({item.get('pos','')}): {item.get('meaning_vi','')}\n"
            f"🔊 {item.get('ipa','')} - {audio}\n"
            f"Ví dụ:\n"
            f"🇬🇧 {item.get('example_en','')}\n"
            f"🇻🇳 {item.get('example_vi','')}\n"
            f"(📚 Bài {item.get('lesson')} - Sách {item.get('book')})")

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
    return dict(sorted(
        (k, v) for k, v in MECHANICAL_DICT.items()
        if str(v.get("book")).lower() == book and str(v.get("lesson")) == lesson
    ))

# ================= QUIZ =================
def generate_quiz(words_dict):
    word = random.choice(list(words_dict.keys()))
    correct = words_dict[word]["meaning_vi"]

    lesson_meanings = [v["meaning_vi"] for v in words_dict.values()]
    wrong = random.sample([m for m in lesson_meanings if m != correct],3)

    options = wrong + [correct]
    random.shuffle(options)

    labels = ["a", "b", "c", "d"]
    correct_label = labels[options.index(correct)]

    question = (f"❓ {word.lower()} nghĩa là: \n\n"
                f"A. {options[0].lower()}\n"
                f"B. {options[1].lower()}\n"
                f"C. {options[2].lower()}\n"
                f"D. {options[3].lower()}\n\n"
                "👉 Trả lời A/B/C/D")

    return question, correct_label, word

# ================= HANDLE MESSAGE =================
async def handle_message(update: Update, context):
    if not update.message or not update.message.text:
        return
        
    chat_id = update.message.chat.id
    raw = update.message.text
    text = norm_text(raw)
    state = USER_STATES.get(chat_id, {})

    # ===== STOP QUIZ =====
    if text in ["stop", "dừng", "quit"]:
        if state.get("mode") == "quiz_answer":
            score = state.get("score", 0)
            total = state.get("total", 0)
    
            accuracy = round((score / total) * 100, 1) if total > 0 else 0

            wrong_words = state.get("wrong_words", [])

            wrong_list = ""
            if wrong_words:
                review = []
                for w in wrong_words:
                    meaning = state["words"][w]["meaning_vi"]
                    review.append(f"• {w} — {meaning}")
    
                wrong_list = "\n\n📚 Từ cần ôn lại:\n" + "\n".join(review)
            
            USER_STATES.pop(chat_id, None)
            
            await update.message.reply_text(
                f"🛑 Đã dừng quiz.\n\n"
                f"📊 Điểm hiện tại: {score}/{total}\n"
                f"🎯 Accuracy: {accuracy}%"
                f"{wrong_list}"
            )
            return
            
        # ===== WAITING BOOK =====
    if state.get("mode") == "waiting_book":
        book = None
        for b in VALID_BOOKS:
            if b in text:
                book = b
                break
    
        if book:
            lesson = state["lesson"]
            words = get_words(book, lesson)
    
            if words:
                USER_STATES[chat_id] = {"mode": "menu", "words": words}
                await update.message.reply_text(
                    f"📚 Sách {book.upper()} - Bài {lesson}\n\n"
                    "1️⃣ Liệt kê từ\n"
                    "2️⃣ Quiz trắc nghiệm"
                )
            else:
                await update.message.reply_text("Không tìm thấy dữ liệu bài này.")
            return
        else:
            await update.message.reply_text("Vui lòng nhập đúng tên sách (TACK1/TACK2/TACKCB3/TACKCB4)")
            return

    # ===== WAITING LESSON =====
    if state.get("mode") == "waiting_lesson":
        lesson = re.search(r"\d+", text)
        lesson = lesson.group() if lesson else None
    
        if lesson and lesson in VALID_LESSONS:
            book = state["book"]
            words = get_words(book, lesson)
    
            if words:
                USER_STATES[chat_id] = {"mode": "menu", "words": words}
                await update.message.reply_text(
                    f"📚 Sách {book.upper()} - Bài {lesson}\n\n"
                    "1️⃣ Liệt kê từ\n"
                    "2️⃣ Quiz trắc nghiệm"
                )
            else:
                await update.message.reply_text("Không tìm thấy dữ liệu bài này.")
            return
        else:
            await update.message.reply_text("Vui lòng nhập số bài từ 1-8.")
            return
        
    img = None
    cor = ["Đúng rùiii", "Bạn giỏi quá!", "Chuẩn không cần chỉnh!", "Excellent!", "Well done!", "Perfect!", "Bingo"]
    
   # ===== QUIZ ANSWER =====
    if state.get("mode") == "quiz_answer":
        score = state["score"]
        total = state["total"] + 1
    
        if text == state["correct"]:
            score += 1
            await bot.send_sticker(chat_id, random.choice(dung))
            await update.message.reply_text(random.choice(cor))
        else:
            state["wrong_words"].append(state["current_word"])
            await bot.send_sticker(chat_id, random.choice(sai))
            await update.message.reply_text(f"Sai rùi ❌ Đáp án đúng là {state['correct'].upper()}")
    
        pool = state["pool"]
        if not pool:
            accuracy = round((score / total) * 100, 1)
            wrong_words = state["wrong_words"]
            wrong_list = ""
            if wrong_words:
                review = []
                for w in wrong_words:
                    meaning = state["words"][w]["meaning_vi"]
                    review.append(f"• {w} — {meaning}")
                wrong_list = "\n\n📚 Từ cần ôn lại:\n" + "\n".join(review)
    
            USER_STATES.pop(chat_id, None)
    
            await update.message.reply_text(
                f"🎉 Hoàn thành quiz!\n\n"
                f"📊 Điểm: {score}/{total}\n"
                f"🎯 Accuracy: {accuracy}%"
                f"{wrong_list}"
            )
            return
    
        current_word = pool.pop()

        correct = state["words"][current_word]["meaning_vi"]
        
        lesson_meanings = [v["meaning_vi"] for v in state["words"].values()]
        wrong = random.sample([m for m in lesson_meanings if m != correct],3)
        
        options = wrong + [correct]
        random.shuffle(options)
        
        labels = ["a","b","c","d"]
        correct_label = labels[options.index(correct)]
        
        question = (f"❓ {current_word.lower()} nghĩa là:\n\n"
                    f"A. {options[0]}\n"
                    f"B. {options[1]}\n"
                    f"C. {options[2]}\n"
                    f"D. {options[3]}\n\n"
                    "👉 Trả lời A/B/C/D")
        
        correct = correct_label
    
        USER_STATES[chat_id] = {
            "mode": "quiz_answer",
            "words": state["words"],
            "pool": pool,
            "current_word": current_word,
            "correct": correct,
            "score": score,
            "total": total,
            "wrong_words": state["wrong_words"]
        }
    
        await update.message.reply_text(
            f"📊 Điểm hiện tại: {score}/{total}\n\n{question}"
        )
    
        return

    # ===== LIST DETAIL =====
    if state.get("mode") == "list_detail":
        if text in MECHANICAL_DICT:
            await update.message.reply_text(format_word_response(text, MECHANICAL_DICT[text]))
            img = MECHANICAL_DICT[text].get('img_url', "")
            if img and img.startswith("http"):
                try:
                    await bot.send_photo(chat_id, "", img)
                except Exception as e:
                    print("Send photo error:", e)
        else:
            suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.8)
            if suggestions:
                await update.message.reply_text("Bạn có muốn tra:\n" + "\n".join([f"• {s}" for s in suggestions]))
            else:
                await update.message.reply_text("Từ không tồn tại.")
        USER_STATES.pop(chat_id, None)
        return

    # ===== MENU =====
    if state.get("mode") == "menu":
        if text == "1":
            words = state["words"]
            response = "📚 Danh sách từ:\n\n"
            for w, item in words.items():
                response += f"• {w} : {item.get('meaning_vi')}\n"
            await update.message.reply_text(f"{response}\n Bạn muốn xem chi tiết từ nào?")
            USER_STATES[chat_id] = {"mode": "list_detail"}
            return

    if text == "2":
        words_list = list(state["words"].keys())
        random.shuffle(words_list)
    
        question, correct, word = generate_quiz(state["words"])
    
        words_list.remove(word)
    
        USER_STATES[chat_id] = {
            "mode": "quiz_answer",
            "words": state["words"],
            "pool": words_list,
            "current_word": word,
            "correct": correct,
            "score": 0,
            "total": 0,
            "wrong_words": []
        }
    
        await update.message.reply_text(
            "🎯 Bắt đầu quiz!\n"
            "Trả lời A/B/C/D\n"
            "Gõ 'stop' để dừng.\n\n"
            + question
        )
        return

    # ===== CHECK GRETTING =====
    if text in ["hi", "/-strong", "alo", "alu", "aloo", "alooo", "helo", "hello", "chào bot", "chào", "bot ơi", "hii", "hiii", "hiiii", "hiiiii", "hiiiiiii", "heloo", "helooo", "helooooo", "heloooo", "helloo", "hellooo", "hellooooo", "helloooo"]:
        try:
            await bot.send_sticker(chat_id, random.choice(hi))
        except Exception as e:
            print("Sticker error:", e)
        await update.message.reply_text("Vui lòng nhập từ hoặc cú pháp [Sách...(TACKCB3/TACKCB4/TACK1/TACK2) Bài...(1-8)] để tra từ vựng và làm quiz")
        return
            
    # ===== 1. TRA TỪ =====
    elif text in MECHANICAL_DICT:
        await update.message.reply_action('typing')
        await update.message.reply_text(format_word_response(text, MECHANICAL_DICT[text]))
        img = MECHANICAL_DICT[text].get('img_url', "")
        if img and img.startswith("http"):
            try:
                await bot.send_photo(chat_id, "", img)
            except Exception as e:
                print("Send photo error:", e)
        return

            # ===== 2. SUGGESTION =====
    else:
        suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.8)
    
        # ===== 3. BOOK LESSON (CHỈ CHECK KHI KHÔNG CÓ SUGGESTION) =====
        if not suggestions:
            book, lesson = extract_book_lesson(text)
    
            # Có đủ book + lesson
            if book and lesson:
                words = get_words(book, lesson)
                if words:
                    USER_STATES[chat_id] = {"mode": "menu", "words": words}
                    await update.message.reply_text(
                        f"📚 Sách {book.upper()} - Bài {lesson}\n\n"
                        "1️⃣ Liệt kê từ\n"
                        "2️⃣ Quiz trắc nghiệm"
                    )
                else:
                    await update.message.reply_text("Không tìm thấy dữ liệu bài này.")
                return
    
            # Chỉ có book
            if book and not lesson:
                USER_STATES[chat_id] = {"mode": "waiting_lesson",
                                        "book": book}
                await update.message.reply_text(f"Bạn muốn tra từ vựng bài mấy sách {book.upper()}? (1-8)")
                return
    
            # Chỉ có lesson
            if lesson and not book:
                USER_STATES[chat_id] = {"mode": "waiting_book",
                                        "lesson": lesson}
                await update.message.reply_text("Bạn muốn tra từ vựng bài này ở sách nào? (TACK1/TACK2/TACKCB3/TACKCB4)")
                return
    
        # Nếu có suggestion thì trả suggestion
        else:
            await update.message.reply_text(
                f"❌ Không tìm thấy '{raw}'.\n\n"
                "💡 Có thể bạn muốn tìm:\n" +
                "\n".join([f"• {s}" for s in suggestions])
            )
            return
    
        # ===== NOT FOUND =====
        await update.message.reply_text(
            f"Xin lỗi, mình chưa có từ '{raw}'.\n"
            "Vui lòng nhập từ hoặc cú pháp [Sách...(TACKCB3/TACKCB4/TACK1/TACK2) Bài...(1-8)] để tra từ vựng và làm quiz")

    # --- THIẾT LẬP DISPATCHER ---
dispatcher = Dispatcher(bot, None, workers=1)
dispatcher.add_handler(MessageHandler(filters.TEXT, handle_message))

@app.route("/")
def index():
    return "<h1>Bot Dictionary V5 is running!</h1>"

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    if not payload:
        return "No payload", 400

    try:
        data = payload.get("result") or payload
        update = Update.de_json(data, bot)

        dispatcher.process_update(update)

        return "ok", 200
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "error", 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
