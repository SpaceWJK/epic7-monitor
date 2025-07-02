# generate_report.py
import json
import time
from crawler import crawl_all_sites
from classifier import is_positive_post, is_negative_post, is_bug_post
from notifier import send_daily_report

# Discord 웹훅 URL
WEBHOOK_URL = "https://discord.com/api/webhooks/xxx/yyy"

def main():
    print("--- 일일 동향 보고서 생성 시작 ---")

    posts = crawl_all_sites()

    positive_count = 0
    negative_count = 0
    bug_count = 0

    report_table = []

    for post in posts:
        title = post["title"]
        url = post["url"]
        source = post.get("source", "Unknown")

        # 🚀 force_bug 처리: Stove 버그 게시판은 무조건 bug_count로
        if post.get("force_bug"):
            bug_count += 1
            report_table.append(f"[BUG][{source}] {title} - {url}")
            continue

        # 기존 키워드 기반 분류
        if is_bug_post(title):
            bug_count += 1
            report_table.append(f"[BUG][{source}] {title} - {url}")
        elif is_positive_post(title):
            positive_count += 1
            report_table.append(f"[POS][{source}] {title} - {url}")
        elif is_negative_post(title):
            negative_count += 1
            report_table.append(f"[NEG][{source}] {title} - {url}")

    # Discord 보고서 전송
    report_message = (
        f"**에픽세븐 커뮤니티 일일 동향 ({time.strftime('%Y-%m-%d')})**\n\n"
        f"📌 긍정 언급: {positive_count} 건\n"
        f"📌 부정 언급: {negative_count} 건\n"
        f"🚨 버그 언급: {bug_count} 건\n\n"
        f"---\n"
        + "\n".join(report_table)
    )

    send_daily_report(WEBHOOK_URL, report_message)

    print("일일 보고서 생성 완료.")

if __name__ == "__main__":
    main()
