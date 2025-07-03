from crawler import crawl_arca_sites, crawl_global_sites
from classifier import is_positive_post, is_negative_post, is_bug_post
from notifier import send_daily_report
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_REPORT")

def main():
    posts = crawl_arca_sites() + crawl_global_sites()
    report = {"긍정": [], "부정": [], "버그": []}
    for post in posts:
        if is_bug_post(post["title"]):
            report["버그"].append(post)
        elif is_positive_post(post["title"]):
            report["긍정"].append(post)
        elif is_negative_post(post["title"]):
            report["부정"].append(post)
    send_daily_report(WEBHOOK_URL, report)

if __name__ == "__main__":
    main()
