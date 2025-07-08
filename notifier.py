import requests
import json
import os

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_BUG", "YOUR_DISCORD_WEBHOOK")

def send_bug_alert(posts):
    try:
        if not posts:
            print("[DEBUG] No posts to send.")
            return
        message = "**🚨 Bug Detected:**\n"
        for post in posts:
            message += f"- [{post.get('title')}]({post.get('url')}) ({post.get('source')})\n"
        response = requests.post(WEBHOOK_URL, json={"content": message})
        if response.status_code in (200, 204):
            print("[INFO] Bug alert sent successfully.")
        else:
            print(f"[ERROR] Discord webhook failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] send_bug_alert failed: {e}")

def send_daily_report(webhook_url, report):
    try:
        message = "**📊 Daily Epic Seven Report**\n"
        message += f"- 긍정: {len(report['긍정'])} 개\n"
        message += f"- 부정: {len(report['부정'])} 개\n"
        message += f"- 버그: {len(report['버그'])} 개\n"
        message += "\n상세 링크:\n"
        for category, posts in report.items():
            if posts:
                message += f"\n**{category}**\n"
                for post in posts[:5]:
                    message += f"- [{post.get('title')}]({post.get('url')}) ({post.get('source')})\n"
        response = requests.post(webhook_url, json={"content": message})
        if response.status_code in (200, 204):
            print("[INFO] Daily report sent successfully.")
        else:
            print(f"[ERROR] Discord webhook failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] send_daily_report failed: {e}")
