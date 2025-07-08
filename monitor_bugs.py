from crawler import crawl_all_sites
from classifier import is_positive_post, is_negative_post, is_bug_post
from notifier import send_bug_alert
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BUG")

def main():
    posts = crawl_all_sites()
    print("[DEBUG] 전체 크롤링 결과:", posts)
    bugs = []
    for post in posts:
        if post.get("force_bug") or is_bug_post(post["title"]):
            bugs.append(post)
    print(f"[DEBUG] Total bugs detected: {len(bugs)}")
    if bugs:
        send_bug_alert(WEBHOOK_URL, bugs)
    else:
        print("[INFO] No bug posts to alert.")

if __name__ == "__main__":
    main()
