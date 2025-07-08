import requests
import json
from datetime import datetime

def send_bug_alert(webhook_url, bugs):
    """버그 알림 전송 (Discord 메시지 길이 제한 고려)"""
    if not webhook_url or not bugs:
        return
    
    try:
        # Discord 메시지 길이 제한 (2000자)
        MAX_MESSAGE_LENGTH = 1900  # 여유분 고려
        
        # 여러 메시지로 나누어 전송
        current_message = "🚨 **에픽세븐 버그 탐지 알림** 🚨\n\n"
        message_count = 1
        
        for i, bug in enumerate(bugs, 1):
            # 각 버그 정보 포맷
            bug_info = f"**{i}.** {bug['title'][:100]}\n🔗 {bug['url']}\n📅 {bug.get('timestamp', '')[:19]}\n📍 {bug.get('source', 'unknown')}\n\n"
            
            # 메시지 길이 체크
            if len(current_message + bug_info) > MAX_MESSAGE_LENGTH:
                # 현재 메시지 전송
                data = {
                    "content": current_message,
                    "username": "Epic7 Bug Monitor",
                    "avatar_url": "https://static.wikia.nocookie.net/epic7x/images/7/77/Epic7_Logo.png"
                }
                
                response = requests.post(webhook_url, json=data, timeout=10)
                if response.status_code == 204:
                    print(f"[INFO] Discord 알림 {message_count} 전송 성공")
                else:
                    print(f"[WARN] Discord 알림 {message_count} 전송 실패: {response.status_code}")
                
                # 새 메시지 시작
                message_count += 1
                current_message = f"🚨 **버그 알림 계속 ({message_count})** 🚨\n\n" + bug_info
            else:
                current_message += bug_info
        
        # 마지막 메시지 전송
        if current_message.strip():
            data = {
                "content": current_message,
                "username": "Epic7 Bug Monitor",
                "avatar_url": "https://static.wikia.nocookie.net/epic7x/images/7/77/Epic7_Logo.png"
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            if response.status_code == 204:
                print(f"[INFO] Discord 알림 {message_count} 전송 성공")
            else:
                print(f"[WARN] Discord 알림 {message_count} 전송 실패: {response.status_code}")
                
    except Exception as e:
        print(f"[ERROR] Discord 버그 알림 전송 중 오류: {e}")

def send_daily_report(webhook_url, report):
    """일일 리포트 전송"""
    if not webhook_url:
        return
        
    try:
        # 리포트 내용 생성
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        total_posts = sum(len(posts) for posts in report.values())
        
        content = f"📊 **에픽세븐 일일 리포트** 📊\n"
        content += f"📅 {current_time}\n\n"
        content += f"**📈 총 게시글 수: {total_posts}개**\n\n"
        
        for category, posts in report.items():
            if not posts:
                content += f"**{get_category_emoji(category)} {category}**: 0개\n"
                continue
                
            content += f"**{get_category_emoji(category)} {category}**: {len(posts)}개\n"
            
            # 카테고리별 상위 3개만 표시
            for i, post in enumerate(posts[:3], 1):
                title = post['title'][:60] + "..." if len(post['title']) > 60 else post['title']
                content += f"  {i}. {title}\n"
                
            if len(posts) > 3:
                content += f"  ... 외 {len(posts) - 3}개\n"
            content += "\n"
        
        # Discord 전송
        data = {
            "content": content,
            "username": "Epic7 Daily Reporter",
            "avatar_url": "https://static.wikia.nocookie.net/epic7x/images/7/77/Epic7_Logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=10)
        if response.status_code == 204:
            print("[INFO] 일일 리포트 Discord 전송 성공")
        else:
            print(f"[WARN] 일일 리포트 Discord 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 전송 중 오류: {e}")

def get_category_emoji(category):
    """카테고리별 이모지 반환"""
    emoji_map = {
        "긍정": "😊",
        "부정": "😞", 
        "버그": "🐛",
        "기타": "📝"
    }
    return emoji_map.get(category, "📌")
