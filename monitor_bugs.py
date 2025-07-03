import json
import time
import sys
from crawler import crawl_arca_sites, crawl_global_sites
from classifier import is_bug_post
from notifier import send_bug_alert

WEBHOOK_URL = "https://discord.com/api/webhooks/xxx/yyy"
STATE_FILE = "crawled_links.json"

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_state(links):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "arca"
    print(f"--- 실시간 버그 감시 시작 ({mode}) ---")

    crawled_links = load_state()

    # 모드별로 함수 분기
    if mode == "arca":
        posts = crawl_arca_sites()
    elif mode == "global":
        posts = crawl_global_sites()
    else:
        print(f"알 수 없는 모드: {mode}")
        return

    new_bugs_detected = 0

    for post in posts:
        title = post["title"]
        url = post["url"]
        source = post.get("source", "Unknown")

        if url in crawled_links:
            continue

        # force_bug 지원
        if post.get("force_bug") or is_bug_post(title):
            send_bug_alert(WEBHOOK_URL, f"[{source}] {title}", url, source)
            new_bugs_detected += 1

        crawled_links.append(url)

    save_state(crawled_links)
    print(f"이번 탐색에서 새로 감지된 버그 게시글 수: {new_bugs_detected}")

if __name__ == "__main__":
    main()
