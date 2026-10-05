import json
import os
import re
from datetime import datetime, date, timedelta, timezone

import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

TZ = timezone(timedelta(hours=6))   # ঢাকা সময়
STATE_FILE = "state.json"
REMIND_AFTER_DAYS = 7
REMIND_HOUR = 9                     # সকাল ৯টার পর রিমাইন্ডার যাবে

# clean / Clean / /clean / ক্লিন
CLEAN_PATTERN = re.compile(r"^\s*/?(clean|ক্লিন)(@\w+)?\s*$", re.IGNORECASE)


def load_state():
    state = {
        "offset": 0,
        "last_cleaner": None,
        "last_date": None,
        "chat_id": None,
        "reminded": False,
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
    state["reminded"] = False

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
    if state["reminded"]:
        return

    now = datetime.now(TZ)
    if now.hour < REMIND_HOUR:
        return

    last = date.fromisoformat(state["last_date"])
    if (now.date() - last).days < REMIND_AFTER_DAYS:
        return

    text = (
        "⏰ রিমাইন্ডার!\n\n"
        f"{state['last_cleaner']} গত {format_date(state['last_date'])} তারিখে ওয়াশরুম পরিষ্কার করেছিলেন।\n\n"
        "এবার যার পালা, সে দয়া করে ওয়াশরুম পরিষ্কার করুন। ধন্যবাদ। 🙏\n\n"
        "পরিষ্কার করে গ্রুপে clean লিখুন।"
    )
    send_message(state["chat_id"], text)
    state["reminded"] = True


def main():
    state = load_state()
    process_updates(state)
    check_reminder(state)
    save_state(state)


main()
