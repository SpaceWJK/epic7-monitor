from crawler import crawl_arca_sites
from classifier import is_bug_post
from notifier import send_bug_alert
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BUG")

def main():
    posts = crawl_arca_sites()
    bugs = [post for post in posts if is_bug_post(post["title"])]
    print(f"[DEBUG] Total bugs detected: {len(bugs)}")
    if bugs:
        print("[INFO] Sending bug alert to Discord")
        send_bug_alert(WEBHOOK_URL, bugs)
    else:
        print("[INFO] No bug posts to alert.")

if __name__ == "__main__":
    main()
