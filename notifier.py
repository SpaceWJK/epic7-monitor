import requests

def send_bug_alert(webhook_url, bugs):
    for bug in bugs:
        data = {
            "content": f"[BUG DETECTED]\nTitle: {bug['title']}\nURL: {bug['url']}"
        }
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print("[INFO] Discord notification sent.")
        else:
            print(f"[WARN] Discord notification failed: {response.status_code}")

def send_daily_report(webhook_url, report):
    content = "[Daily Bug Report]\n"
    for category, posts in report.items():
        content += f"\n**{category}** ({len(posts)}):"
        for post in posts:
            content += f"\n- {post['title']} ({post['url']})"
    data = {"content": content}
    requests.post(webhook_url, json=data)
