# notifier.py
import requests

def send_bug_alert(webhook_url, title, url, source):
    """
    버그 감지 시 실시간으로 Discord에 전송
    """
    data = {
        "embeds": [{
            "title": f"[{source}] {title}",
            "description": f"[게시글 바로가기]({url})",
            "color": 15158332  # 빨간색 계열
        }]
    }
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Discord 전송 실패: {e}")

def send_daily_report(webhook_url, report_data):
    """
    일일 동향 보고서 Discord 전송
    """
    embed = {
        "title": "📊 Epic Seven 일간 유저 동향 리포트",
        "color": 3447003,
        "fields": []
    }

    for category, posts in report_data.items():
        if not posts:
            continue
        desc = ""
        for post in posts:
            desc += f"- [{post['title']}]({post['url']}) ({post.get('source', 'Unknown')})\n"
        embed["fields"].append({
            "name": f"{category.upper()} ({len(posts)}건)",
            "value": desc[:1024],  # Discord 제한
            "inline": False
        })

    data = {"embeds": [embed]}
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Discord 전송 실패: {e}")
