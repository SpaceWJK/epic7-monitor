import requests
import json
from datetime import datetime
from typing import List, Dict

def send_bug_alert(webhook_url: str, title: str, url: str, source: str):
    """'버그'로 분류된 게시물을 즉시 Discord로 전송합니다."""
    if not webhook_url:
        print("[알림 에러] Discord 웹훅 URL이 전달되지 않았습니다.")
        return

    embed = {
        "title": ":bug: 신규 버그 의심 게시글 발생!",
        "description": f"**{title}**",
        "url": url,
        "color": 15158332, # Red
        "fields": [
            {"name": "출처", "value": source, "inline": True},
            {"name": "발생 시각", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "inline": True}
        ],
        "footer": {"text": "Epic Seven Community Monitoring System"}
    }
    payload = {"username": "버그 감시봇", "avatar_url": "https://i.imgur.com/RDTsJb3.png", "embeds": [embed]}

    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        print(f"성공적으로 버그 알림을 전송했습니다: {title}")
    except requests.exceptions.RequestException as e:
        print(f"Discord 버그 알림 전송 실패: {e}")

def send_daily_report(webhook_url: str, report_data: Dict[str, List[Dict[str, str]]]):
    """수집된 동향 데이터를 종합하여 일일 보고서를 Discord로 전송합니다."""
    if not webhook_url:
        print("[알림 에러] Discord 웹훅 URL이 전달되지 않았습니다.")
        return
        
    today_str = datetime.now().strftime('%Y년 %m월 %d일')
    embed = {
        "title": f"📈 에픽세븐 유저 동향 일일 보고서 ({today_str})",
        "description": "지난 24시간 동안 수집된 커뮤니티 주요 동향 요약입니다.",
        "color": 5814783, # Blue
        "fields": [],
        "footer": {"text": "Epic Seven Community Monitoring System"}
    }
    
    category_map = {
        'bug': ':beetle: 버그 의심',
        'negative': ':warning: 부정 동향',
        'positive': ':sparkles: 긍정 동향',
    }

    for category in ['bug', 'negative', 'positive']:
        if category in report_data:
            posts = report_data[category]
            field_name = category_map[category]
            value = "\n".join([f" • [{p['title']}]({p['url']})" for p in posts[:5]])
            if len(posts) > 5:
                value += f"\n... 외 {len(posts) - 5}건"
            if not value:
                value = "관련 게시글이 없습니다."
            
            embed['fields'].append({"name": f"{field_name} ({len(posts)}건)", "value": value, "inline": False})
            
    payload = {"username": "동향 리포터", "avatar_url": "https://i.imgur.com/kQZgY7E.png", "embeds": [embed]}

    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        print("성공적으로 일일 보고서를 전송했습니다.")
    except requests.exceptions.RequestException as e:
        print(f"Discord 일일 보고서 전송 실패: {e}")