# monitor_bugs.py
import sys
import time
from crawler import crawl_arca_sites, crawl_global_sites
from notifier import send_bug_alert
from classifier import classify_post

WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK"  # 깃허브 Secrets에 보관한 환경변수로 불러오면 좋습니다.

def main():
    print("--- 실시간 버그 감시 시작 ---")

    # CLI 인자 받기
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"[INFO] 실행 모드: {mode}")

    posts = []

    # 선택적으로 모드별 크롤링
    if mode == "arca":
        posts = crawl_arca_sites()
    elif mode == "global":
        posts = crawl_global_sites()
    else:
        posts = crawl_arca_sites() + crawl_global_sites()

    print(f"[INFO] 총 크롤링된 게시글 수: {len(posts)}")

    # 게시글 순회하며 분류 및 알림
    bug_count = 0
    for post in posts:
        category = classify_post(post["title"])
        if category == "bug":
            send_bug_alert(WEBHOOK_URL, f"[{post['source']}] {post['title']}", post["url"])
            bug_count += 1

    print(f"[INFO] 버그 키워드 탐지 알림 전송 건수: {bug_count}")
    print("--- 실시간 버그 감시 종료 ---")

if __name__ == "__main__":
    main()
