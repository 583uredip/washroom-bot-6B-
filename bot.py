import json
import os
import re
from datetime import datetime, date, timedelta, timezone

import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

TZ = timezone(timedelta(hours=6))   # ঢাকা সময়
STATE_FILE = "state.json"
REMIND_AFTER_DAYS = 7              # clean এর কত দিন পর প্রথম রিমাইন্ডার
REPEAT_EVERY_DAYS = 5              # এরপর কত দিন পরপর রিমাইন্ডার
REMIND_HOUR = 9                    # সকাল ৯টার পর রিমাইন্ডার যাবে

# clean / Clean / /clean / ক্লিন
CLEAN_PATTERN = re.compile(r"^\s*/?(clean|ক্লিন)(@\w+)?\s*$", re.IGNORECASE)


def load_state():
    state = {
        "offset": 0,
        "last_cleaner": None,
        "last_date": None,
        "chat_id": None,
        "last_reminded": None,      # শেষ যেদিন রিমাইন্ডার গেছে
    }
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state.update(json.load(f))
    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_message(chat_id, text):
    requests.post(API + "/sendMessage", data={"chat_id": chat_id, "text": text})


def get_updates(offset):
    response = requests.post(API + "/getUpdates", data={"offset": offset, "timeout": 0})
    return response.json()["result"]


def format_date(iso_text):
    return date.fromisoformat(iso_text).strftime("%d/%m/%Y")


def handle_clean(state, message):
    user = message["from"]
    cleaner = (user.get("first_name", "") + " " + user.get("last_name", "")).strip()
    clean_date = datetime.fromtimestamp(message["date"], TZ).date()
    chat_id = message["chat"]["id"]

    state["last_cleaner"] = cleaner
    state["last_date"] = clean_date.isoformat()
    state["chat_id"] = chat_id
    state["last_reminded"] = None   # রিমাইন্ডার রিসেট

    text = (
        f"✅ {cleaner} আজ {clean_date.strftime('%d/%m/%Y')} তারিখে ওয়াশরুম পরিষ্কার করেছেন।\n"
        "আপনাকে অনেক ধন্যবাদ! 🙏\n\n"
        "🚽 পরের পালা যার, সে প্রস্তুত থাকুন।\n\n"
        "নিজে পরিষ্কার-পরিচ্ছন্ন থাকুন, নিজে সুস্থ থাকুন, অন্যকে সুস্থ রাখুন। ধন্যবাদ।"
    )
    send_message(chat_id, text)


def process_updates(state):
    updates = get_updates(state["offset"])

    for update in updates:
        state["offset"] = update["update_id"] + 1

        message = update.get("message")
        if message is None:
            continue

        text = message.get("text")
        if text is None:
            continue

        if CLEAN_PATTERN.match(text):
            handle_clean(state, message)


def check_reminder(state):
    if state["last_date"] is None:
        return
    if state["chat_id"] is None:
        return

    now = datetime.now(TZ)
    if now.hour < REMIND_HOUR:
        return

    today = now.date()
    last_clean = date.fromisoformat(state["last_date"])
    days_passed = (today - last_clean).days

    # ৭ দিন পার না হলে রিমাইন্ডার নয়
    if days_passed < REMIND_AFTER_DAYS:
        return

    # আগে রিমাইন্ডার গিয়ে থাকলে, ৫ দিন না পেরোলে আবার নয়
    if state["last_reminded"] is not None:
        last_reminded = date.fromisoformat(state["last_reminded"])
        if (today - last_reminded).days < REPEAT_EVERY_DAYS:
            return

    late_days = days_passed - REMIND_AFTER_DAYS

    text = (
        "⏰ রিমাইন্ডার!\n\n"
        f"{state['last_cleaner']} গত {format_date(state['last_date'])} তারিখে ওয়াশরুম পরিষ্কার করেছিলেন "
        f"({days_passed} দিন আগে)।\n"
    )
    if late_days > 0:
        text += f"⚠️ পালা পার হয়ে {late_days} দিন দেরি হয়ে গেছে!\n"
    text += (
        "\nএবার যার পালা, সে দয়া করে ওয়াশরুম পরিষ্কার করুন। ধন্যবাদ। 🙏\n\n"
        "পরিষ্কার করে গ্রুপে clean লিখুন।"
    )

    send_message(state["chat_id"], text)
    state["last_reminded"] = today.isoformat()


def main():
    state = load_state()
    process_updates(state)
    check_reminder(state)
    save_state(state)


main()
