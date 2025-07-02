import json, os
from crawler import crawl_all_sites
from classifier import classify_post
from notifier import send_bug_alert

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
    webhook = os.getenv("DISCORD_WEBHOOK_BUG")

    print("--- 실시간 버그 감시 시작 ---")
    posts = crawl_all_sites()

    for post in posts:
        if post["url"] in seen_links:
            continue
        category = classify_post(post["title"])
        if category == "bug":
            send_bug_alert(webhook, f"[{post['source']}] {post['title']}", post["url"])
        seen_links.add(post["url"])

    state["seen"] = list(seen_links)
    save_state(state)

if __name__ == "__main__":
    main()
