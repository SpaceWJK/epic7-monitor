import json, os
from crawler import crawl_all_sites
from classifier import classify_post
from notifier import send_daily_report

STATE_FILE = "crawled_links.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def main():
    state = load_state()
    seen_links = set(state["seen"])
    webhook = os.getenv("DISCORD_WEBHOOK_REPORT")

    print("--- 일일 보고서 생성 시작 ---")
    posts = crawl_all_sites()

    report_data = {"bug": [], "negative": [], "positive": []}
    for post in posts:
        category = classify_post(post["title"])
        if category in report_data:
            report_data[category].append(post)
        seen_links.add(post["url"])

    send_daily_report(webhook, report_data)

    state["seen"] = list(seen_links)
    save_state(state)

if __name__ == "__main__":
    main()
