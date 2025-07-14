import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import time
import re
import random

def get_stove_post_content(post_url):
    """스토브 게시글 내용 추출 - 현실적 접근 방식"""
    try:
        print(f"[DEBUG] 스토브 게시글 내용 확인 시도: {post_url}")
        
        # 간단한 요청으로 제목 재확인 시도
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        
        response = requests.get(post_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 제목 추출 시도
            title_selectors = [
                'title', 'h1', 'h2', 'h3',
                '[data-title]', '[title]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem and title_elem.get_text(strip=True):
                    title_text = title_elem.get_text(strip=True)
                    if len(title_text) > 10:  # 의미있는 제목인지 확인
                        return title_text[:100]  # 100자로 제한
            
            return "스토브 게시글"
        else:
            return f"접근 불가 ({response.status_code})"
            
    except Exception as e:
        print(f"[ERROR] 스토브 내용 추출 실패: {e}")
        return "내용 확인 불가"

def send_discord_message(webhook_url, content):
    """Discord 웹훅으로 메시지 전송"""
    if not webhook_url:
        print("[WARNING] Discord 웹훅 URL이 설정되지 않음")
        return False
        
    try:
        payload = {"content": content}
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            print("[SUCCESS] Discord 메시지 전송 성공")
            return True
        else:
            print(f"[ERROR] Discord 메시지 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")
        return False

def send_bug_alert(title, url, site, severity="보통"):
    """버그 알림 전송 (즉시 전송)"""
    import os
    webhook_url = os.environ.get("DISCORD_WEBHOOK_BUG")
    
    if not webhook_url:
        print("[WARNING] 버그 알림 웹훅이 설정되지 않음")
        return False
    
    # 심각도에 따른 이모지
    severity_emoji = {
        "높음": "🚨",
        "보통": "⚠️", 
        "낮음": "ℹ️"
    }
    
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
    """단건별 동향 알림 전송 (새로운 함수)"""
    import os
    webhook_url = os.environ.get("DISCORD_WEBHOOK_SENTIMENT")
    
    if not webhook_url:
        print("[WARNING] 감성 동향 웹훅이 설정되지 않음")
        return False
    
    if not posts:
        # 빈 크롤링 상태 메시지
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"""
🔍 **Epic7 동향 모니터링 상태**

새로운 게시글이 없습니다.
**확인 시간:** {timestamp}

시스템이 정상적으로 동작 중입니다.
"""
        return send_discord_message(webhook_url, message.strip())
    
    # 단건별 동향 알림 전송
    success_count = 0
    for post in posts:
        title = post.get('title', '제목 없음')
        url = post.get('url', '')
        site = post.get('site', '알 수 없음')
        sentiment = post.get('sentiment', '중립')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 감성에 따른 이모지
        sentiment_emoji = {
            "긍정": "😊",
            "부정": "😞",
            "중립": "😐"
        }
        
        emoji = sentiment_emoji.get(sentiment, "😐")
        
        message = f"""
{emoji} **Epic7 유저 동향**

**제목:** {title}
**사이트:** {site}
**감성:** {sentiment}
**링크:** {url}
**수집 시간:** {timestamp}
"""
        
        if send_discord_message(webhook_url, message.strip()):
            success_count += 1
            time.sleep(1)  # Discord API 제한 고려
    
    print(f"[INFO] 동향 알림 전송 완료: {success_count}/{len(posts)}")
    return success_count > 0

def send_daily_report(report_content):
    """일일 리포트 전송 (24시간 누적 데이터)"""
    import os
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

---
Epic7 모니터링 시스템
"""
    
    return send_discord_message(webhook_url, message.strip())

def send_monitoring_status(status_message):
    """모니터링 시스템 상태 메시지 전송"""
    import os
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

# 기존 함수들도 유지 (하위 호환성)
def send_alert(title, url, site, alert_type="버그"):
    """기존 호환성을 위한 함수"""
    if alert_type == "버그":
        return send_bug_alert(title, url, site)
    else:
        # 동향 알림은 새로운 방식 사용
        posts = [{'title': title, 'url': url, 'site': site, 'sentiment': '중립'}]
        return send_sentiment_alert(posts)

if __name__ == "__main__":
    # 테스트 코드
    print("notifier.py 테스트 실행")
    
    # 빈 크롤링 테스트
    send_sentiment_alert([])
    
    # 단건 동향 알림 테스트
    test_posts = [
        {
            'title': '테스트 게시글',
            'url': 'https://example.com',
            'site': '루리웹',
            'sentiment': '긍정'
        }
    ]
    send_sentiment_alert(test_posts)