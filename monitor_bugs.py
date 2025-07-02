# monitor_bugs.py
import json
import time
from crawler import crawl_all_sites
from classifier import is_bug_post
from notifier import send_bug_alert

# Discord 웹훅 URL (GitHub Secrets 또는 환경변수에서 로드 권장)
WEBHOOK_URL = "https://discord.com/api/webhooks/xxx/yyy"

# 중복 방지를 위한 상태 파일
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
    print("--- 실시간 버그 감시 시작 ---")

    # 이전에 처리한 링크 로딩
    crawled_links = load_state()
    print(f"이미 처리된 게시글 수: {len(crawled_links)}")

    # 모든 커뮤니티 크롤링
    posts = crawl_all_sites()

    new_bugs_detected = 0

    for post in posts:
        title = post["title"]
        url = post["url"]
        source = post.get("source", "Unknown")

        # 이미 처리된 링크인지 확인
        if url in crawled_links:
            continue

        # 🚀 Stove 버그 게시판 force_bug or 키워드 필터링
        if post.get("force_bug") or is_bug_post(title):
            send_bug_alert(WEBHOOK_URL, f"[{source}] {title}", url)
            new_bugs_detected += 1

        # 상태 업데이트
        crawled_links.append(url)

    # 상태 파일 저장
    save_state(crawled_links)

    print(f"이번 탐색에서 새로 감지된 버그 게시글 수: {new_bugs_detected}")

if __name__ == "__main__":
    main()
