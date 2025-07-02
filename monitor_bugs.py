# monitor_bugs.py
from crawler import crawl_all_sites
from notifier import send_bug_alert
from classifier import is_bug_post
from datetime import datetime

import time

print("--- 실시간 버그 감시 시작 ---")

def main():
    webhook = "<YOUR_DISCORD_WEBHOOK_URL>"
    checked_urls = set()

    while True:
        posts = crawl_all_sites()
        for post in posts:
            url = post.get("url")
            title = post.get("title", "제목 없음")
            source = post.get("source", "Unknown")

            if url in checked_urls:
                continue

            checked_urls.add(url)

            # 버그 탐지
            if is_bug_post(title):
                try:
                    send_bug_alert(webhook, f"[{source}] {title}", url, source)
                    print(f"[*] 버그 감지 및 알림: {source} - {title}")
                except Exception as e:
                    print(f"[!] Discord 전송 실패: {e}")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 루프 대기 중...")
        time.sleep(60)

if __name__ == "__main__":
    main()
