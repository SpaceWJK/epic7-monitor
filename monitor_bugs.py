from crawler import crawl_all_sites
from classifier import classify_post
from notifier import send_bug_alert

def monitor():
    posts = crawl_all_sites()
    print(f"[DEBUG] Total fetched posts: {len(posts)}")
    if not posts:
        print("[WARN] No posts fetched. Possibly selector issue.")
    bug_posts = []
    for post in posts:
        category = classify_post(post)
        if category == "bug":
            bug_posts.append(post)
    print(f"[DEBUG] Total bugs detected: {len(bug_posts)}")
    if bug_posts:
        send_bug_alert(bug_posts)
    else:
        print("[INFO] No bug posts to alert.")
        
if __name__ == "__main__":
    monitor()
