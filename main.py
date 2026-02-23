from flask import Flask, request, jsonify
import requests
import os
import json
import difflib

app = Flask(__name__)

ACCESS_TOKEN = os.getenv("ZALO_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(BASE_DIR, "medictdata.json")

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

# ================= FORMAT =================
def format_word_response(word, item):
    raw_pos = item.get("pos", "")
    raw_audio = item.get("audio_url", "") or ""

    pos_str = f"({raw_pos})" if raw_pos else ""

    if raw_audio and raw_audio.endswith(".mp3"):
        audio_str = raw_audio
    else:
        audio_str = f"https://translate.google.com/translate_tts?ie=UTF-8&q={word}&tl=en&client=tw-ob"

    return (
        f"🔤 {word.upper()} {pos_str}: {item.get('meaning_vi','')}\n"
        f"🗣️ {item.get('ipa','')} {audio_str}\n"
        f"Ví dụ:\n"
        f"🇬🇧 {item.get('example_en','')}\n"
        f"🇻🇳 {item.get('example_vi','')}\n"
        f"(📚 Bài {item.get('lesson','')} - Sách {item.get('book','')})"
    )

# ================= SEND TEXT =================
def send_text(user_id, message):
    url = "https://openapi.zalo.me/v2.0/oa/message"
    headers = {
        "Content-Type": "application/json",
        "access_token": ACCESS_TOKEN,
    }
    data = {
        "recipient": {"user_id": user_id},
        "message": {"text": message}
    }
    requests.post(url, headers=headers, json=data)

# ================= SEND IMAGE =================
def send_image(user_id, image_url):
    url = "https://openapi.zalo.me/v2.0/oa/message"
    headers = {
        "Content-Type": "application/json",
        "access_token": ACCESS_TOKEN,
    }
    data = {
        "recipient": {"user_id": user_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url
                }
            }
        }
    }
    requests.post(url, headers=headers, json=data)

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json
    print("ZALO PAYLOAD:", payload)

    if "event_name" not in payload:
        return jsonify({"status": "ignored"}), 200

    if payload["event_name"] == "user_send_text":
        user_id = payload["sender"]["id"]
        text = norm_text(payload["message"]["text"])

        if text in MECHANICAL_DICT:
            item = MECHANICAL_DICT[text]
            response = format_word_response(text, item)
            send_text(user_id, response)

            img_url = item.get("img_url", "")
            if img_url:
                send_image(user_id, img_url)
        else:
            suggestions = difflib.get_close_matches(text, DICT_KEYS, n=5, cutoff=0.5)
            if suggestions:
                msg = "❌ Không tìm thấy.\n\n💡 Có thể bạn muốn tìm:\n"
                msg += "\n".join([f"• {s}" for s in suggestions])
            else:
                msg = f"Xin lỗi, mình chưa có từ '{text}'."
            send_text(user_id, msg)

    return jsonify({"status": "ok"}), 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
