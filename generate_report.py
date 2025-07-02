import os
import time
from collections import defaultdict
from crawler import crawl_stove, crawl_dcinside, crawl_reddit
from classifier import classify_post
from notifier import send_daily_report

TARGET_SITES = {
    "스토브": {"func": crawl_stove, "url": "https://page.onstove.com/epicseven/kr/list/free"},
    "디시인사이드": {"func": crawl_dcinside, "url": "https://gall.dcinside.com/mgallery/board/lists/?id=epicseven"},
    "Reddit": {"func": crawl_reddit, "url": "https://www.reddit.com/r/EpicSeven/new/"}
}

def main():
    print("일일 동향 보고서 생성을 시작합니다.")
    webhook_url = os.getenv('DISCORD_WEBHOOK_REPORT')

    if not webhook_url:
        print("[치명적 오류] DISCORD_WEBHOOK_REPORT 환경 변수가 설정되지 않았습니다. GitHub Secrets를 확인해주세요.")
        return

    categorized_posts = defaultdict(list)
    for source, site_info in TARGET_SITES.items():
        print(f"[{source}] 커뮤니티에서 게시글을 수집합니다...")
        try:
            posts = site_info["func"](site_info["url"])
            for post in posts:
                category = classify_post(post['title'])
                if category != 'neutral':
                    categorized_posts[category].append(post)
            time.sleep(1)
        except Exception as e:
            print(f"[{source}] 처리 중 오류 발생: {e}")
    
    print("분류 결과:")
    for category, posts in categorized_posts.items():
        print(f"  - {category}: {len(posts)}건")

    if not any(categorized_posts.values()):
        print("보고할 주요 동향 게시글이 없습니다.")
    else:
        print("Discord로 일일 보고서를 전송합니다.")
        send_daily_report(webhook_url=webhook_url, report_data=categorized_posts)

    print("일일 동향 보고서 생성을 종료합니다.")

if __name__ == "__main__":
    main()