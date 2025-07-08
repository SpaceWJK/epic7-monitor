import requests
import json

WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK"

def send_bug_alert(posts):
    try:
        if not posts:
            print("[DEBUG] No posts to send.")
            return
        message = "**🚨 Bug Detected:**\n"
        for post in posts:
            message += f"- [{post.get('title')}]({post.get('url')}) ({post.get('source')})\n"
        response = requests.post(WEBHOOK_URL, json={"content": message})
        if response.status_code == 204:
            print("[INFO] Bug alert sent successfully.")
        else:
            print(f"[ERROR] Discord webhook failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] send_bug_alert failed: {e}")
