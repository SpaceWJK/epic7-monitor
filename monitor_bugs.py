import os
import time
from crawler import crawl_stove, crawl_dcinside, crawl_reddit
from classifier import classify_post
from notifier import send_bug_alert

TARGET_SITES = {
    "스토브": {"func": crawl_stove, "url": "https://page.onstove.com/epicseven/kr/list/free"},
    "디시인사이드": {"func": crawl_dcinside, "url": "https://gall.dcinside.com/mgallery/board/lists/?id=epicseven"},
    "Reddit": {"func": crawl_reddit, "url": "https://www.reddit.com/r/EpicSeven/new/"}
}

def main():
    print("실시간 버그 모니터링을 시작합니다.")
    webhook_url = os.getenv('DISCORD_WEBHOOK_BUG')

    if not webhook_url:
        print("[치명적 오류] DISCORD_WEBHOOK_BUG 환경 변수가 설정되지 않았습니다. GitHub Secrets를 확인해주세요.")
        return

    bug_count = 0
    for source, site_info in TARGET_SITES.items():
        print(f"[{source}] 커뮤니티에서 게시글을 수집합니다...")
        try:
            posts = site_info["func"](site_info["url"])
            for post in posts:
                if classify_post(post['title']) == 'bug':
                    bug_count += 1
                    print(f"  [버그 감지!] 제목: {post['title']}")
                    send_bug_alert(webhook_url=webhook_url, title=post['title'], url=post['url'], source=source)
            time.sleep(1)
        except Exception as e:
            print(f"[{source}] 처리 중 오류 발생: {e}")

    if bug_count == 0:
        print("새로운 버그 의심 게시글이 발견되지 않았습니다.")
    print("버그 모니터링 작업을 종료합니다.")

if __name__ == "__main__":
    main()