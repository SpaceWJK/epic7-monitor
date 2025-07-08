import sys
import json
from crawler import crawl_arca_sites, crawl_global_sites
from classifier import is_bug_post
from notifier import send_bug_alert
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BUG")

def main():
    mode = "arca"  # 기본값
    if len(sys.argv) > 2 and sys.argv[1] == "--mode":
        mode = sys.argv[2]
    
    print(f"[INFO] 모니터링 모드: {mode}")
    
    if mode == "arca":
        posts = crawl_arca_sites()
    elif mode == "global":
        posts = crawl_global_sites()
    else:
        print(f"[ERROR] 알 수 없는 모드: {mode}")
        return
    
    # 새로 발견된 게시글만 처리
    if not posts:
        print("[INFO] 새로운 게시글이 없습니다.")
        return
    
    # 버그 게시글 필터링
    bugs = []
    for post in posts:
        # 스토브 버그 게시판은 무조건 버그로 분류
        if post.get("source") == "stove_bug":
            bugs.append(post)
        # 다른 게시판은 키워드로 필터링
        elif is_bug_post(post["title"]):
            bugs.append(post)
    
    print(f"[DEBUG] 총 {len(posts)}개 게시글 중 {len(bugs)}개 버그 게시글 탐지")
    
    if bugs:
        print("[INFO] Discord로 버그 알림 전송")
        if WEBHOOK_URL:
            send_bug_alert(WEBHOOK_URL, bugs)
        else:
            print("[ERROR] DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않음")
            for bug in bugs:
                print(f"- {bug['title']}: {bug['url']}")
    else:
        print("[INFO] 알림할 버그 게시글이 없습니다.")

if __name__ == "__main__":
    main()
