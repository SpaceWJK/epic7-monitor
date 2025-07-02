# generate_report.py
from crawler import crawl_all_sites
from notifier import send_daily_report
from classifier import classify_post
from datetime import datetime

print("--- 일일 보고서 생성 시작 ---")

def main():
    webhook = "<YOUR_DISCORD_WEBHOOK_URL>"
    posts = crawl_all_sites()

    report_data = {"bugs": [], "positive": [], "negative": []}

    for post in posts:
        title = post.get("title", "제목 없음")
        url = post.get("url", "")
        source = post.get("source", "Unknown")

        category = classify_post(title)
        if category:
            report_data[category].append({"title": title, "url": url, "source": source})

    # 디스코드로 전송
    try:
        send_daily_report(webhook, report_data)
        print(f"[+] 보고서 발송 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"[!] Discord 전송 실패: {e}")

if __name__ == "__main__":
    main()
