import requests
from datetime import datetime
import os

def send_discord_message(webhook_url, content):
    if not webhook_url:
        print("[WARNING] Discord 웹훅 URL이 설정되지 않음")
        return False
    try:
        payload = {"content": content}
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            return True
        else:
            print(f"[ERROR] Discord 메시지 전송 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")
        return False

def send_bug_alert(title, url, site, severity="보통"):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_BUG")
    if not webhook_url:
        print("[WARNING] 버그 알림 웹훅이 설정되지 않음")
        return False

    severity_emoji = {"높음": "🚨", "보통": "⚠️", "낮음": "ℹ️"}
    emoji = severity_emoji.get(severity, "⚠️")
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    message = f"""
{emoji} **Epic7 버그 발견**

**제목:** {title}
**사이트:** {site}
**링크:** {url}
**심각도:** {severity}
**발견 시간:** {timestamp}

즉시 확인이 필요합니다.
"""
    return send_discord_message(webhook_url, message.strip())

def send_sentiment_alert(posts):
    """
    각 게시글을 Discord embed 카드로 건별 전송, 사이트별 아이콘 표시
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_SENTIMENT")
    if not webhook_url:
        print("[WARNING] 감성 동향 웹훅이 설정되지 않음")
        return False

    if not posts:
        print("[INFO] 전송할 감성 게시글이 없습니다.")
        return True

    for post in posts:
        sentiment = post.get('sentiment', '중립')
        emoji = {
            "긍정": "😊",
            "부정": "😠",
            "중립": "😐"
        }.get(sentiment, "😐")

        site = post.get("site", "알 수 없음")
        site_emoji = {
            "STOVE 자유": "🚉",
            "STOVE 버그": "🐞",
            "루리웹": "🏯"
        }.get(site, "🌐")

        title = post.get("title", "제목 없음")
        url = post.get("url", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        color = {
            "긍정": 0x2ecc71,
            "부정": 0xe74c3c,
            "중립": 0xf1c40f
        }.get(sentiment, 0x95a5a6)

        payload = {
            "embeds": [
                {
                    "title": f"{emoji} Epic7 유저 동향 알림",
                    "description": f"**{title}** ({site_emoji} {site})\n> 🔗 [게시글 바로가기]({url})",
                    "color": color,
                    "footer": {
                        "text": f"{timestamp} | 감성 분석: {sentiment}"
                    }
                }
            ]
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code != 204:
                print(f"[ERROR] Discord 전송 실패: {response.status_code} - {response.text}")
            else:
                print(f"[SUCCESS] {emoji} {title[:30]}... 전송 완료")
        except Exception as e:
            print(f"[ERROR] Discord 전송 중 오류: {e}")

    return True

def send_daily_report(report_content):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_REPORT")
    if not webhook_url:
        print("[WARNING] 일간 리포트 웹훅이 설정되지 않음")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"""
📊 **Epic7 일간 동향 리포트**

{report_content}

**생성 시간:** {timestamp}
**데이터 기간:** 전날 24시간 누적
"""
    return send_discord_message(webhook_url, message.strip())

def send_monitoring_status(status_message):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_SENTIMENT")
    if not webhook_url:
        print("[WARNING] 상태 알림 웹훅이 설정되지 않음")
        return False

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"""
🔧 **Epic7 모니터링 시스템 상태**

{status_message}

**확인 시간:** {timestamp}
"""
    return send_discord_message(webhook_url, message.strip())

def send_alert(title, url, site, alert_type="버그"):
    if alert_type == "버그":
        return send_bug_alert(title, url, site)
    else:
        posts = [{'title': title, 'url': url, 'site': site, 'sentiment': '중립'}]
        return send_sentiment_alert(posts)

if __name__ == "__main__":
    print("notifier.py 테스트 실행")
    test_posts = [
        {'title': '테스트 긍정', 'url': 'https://example.com', 'site': '루리웹', 'sentiment': '긍정'},
        {'title': '테스트 부정', 'url': 'https://example.com', 'site': 'STOVE 자유', 'sentiment': '부정'},
        {'title': '테스트 중립', 'url': 'https://example.com', 'site': 'STOVE 버그', 'sentiment': '중립'}
    ]
    send_sentiment_alert(test_posts)