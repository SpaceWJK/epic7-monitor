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
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        print(f"[DEBUG] 제목 추출 성공: {title[:30]}...")
                        return f"제목: {title}"
        
        # JavaScript 동적 로딩으로 인한 내용 추출 불가 안내
        print(f"[INFO] 스토브 게시글은 동적 로딩으로 내용 추출 불가")
        return "스토브 게시글은 JavaScript로 동적 로딩되어 내용을 직접 추출할 수 없습니다. 링크를 클릭하여 확인하세요."
        
    except requests.exceptions.Timeout:
        print(f"[WARN] 게시글 요청 시간 초과: {post_url}")
        return "게시글 로딩 시간 초과 - 링크를 클릭하여 확인하세요."
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 게시글 접근 실패: {e}")
        return "게시글 접근 불가 - 링크를 클릭하여 확인하세요."
    except Exception as e:
        print(f"[ERROR] 게시글 처리 중 오류: {e}")
        return "게시글 내용 확인을 위해 링크를 클릭하세요."

def get_post_content_summary(post_url, source):
    """게시글 내용 요약 (소스별 처리)"""
    try:
        if source in ['stove_bug', 'stove_general']:
            return get_stove_post_content(post_url)
        else:
            # 기타 사이트는 기본 처리
            return "게시글 내용을 확인하세요."
    except Exception as e:
        print(f"[ERROR] 게시글 내용 요약 실패: {e}")
        return "내용 확인 불가"

def send_bug_alert(webhook_url, bugs):
    """버그 알림 전송 (개선된 내용 표시 포함)"""
    if not webhook_url or not bugs:
        return
    
    try:
        MAX_MESSAGE_LENGTH = 1900
        current_message = "🚨 **에픽세븐 버그 탐지 알림** 🚨\n\n"
        message_count = 1
        
        for bug in bugs:
            try:
                source_type = get_source_type_korean(bug.get('source', 'unknown'))
                formatted_time = format_timestamp(bug.get('timestamp', ''))
                
                # 게시글 내용 추출 (개선된 방식)
                content_summary = get_post_content_summary(bug.get('url', ''), bug.get('source', ''))
                
                bug_info = f"""**분류**: {source_type}
**제목**: {bug['title'][:80]}{'...' if len(bug['title']) > 80 else ''}
**시간**: {formatted_time}
**내용**: {content_summary}
**URL**: {bug['url']}

"""
                
                if len(current_message + bug_info) > MAX_MESSAGE_LENGTH:
                    send_discord_message(webhook_url, current_message, message_count)
                    message_count += 1
                    current_message = f"🚨 **버그 알림 계속 ({message_count})** 🚨\n\n" + bug_info
                else:
                    current_message += bug_info
                    
            except Exception as e:
                print(f"[ERROR] 개별 버그 메시지 처리 중 오류: {e}")
                continue
        
        if current_message.strip():
            send_discord_message(webhook_url, current_message, message_count)
                
    except Exception as e:
        print(f"[ERROR] Discord 버그 알림 전송 중 오류: {e}")

def send_sentiment_alert(webhook_url, sentiment_posts):
    """유저 동향 실시간 알림 전송"""
    if not webhook_url or not sentiment_posts:
        return
    
    try:
        print(f"[INFO] 유저 동향 알림 전송 시작")
        
        # 카테고리별 분류
        categorized = {"긍정": [], "중립": [], "부정": []}
        total_posts = 0
        
        for category, posts in sentiment_posts.items():
            if category in categorized:
                categorized[category] = posts
                total_posts += len(posts)
        
        if total_posts == 0:
            print("[INFO] 전송할 감성 게시글이 없습니다.")
            return
        
        # 메시지 구성
        current_time = datetime.now().strftime('%H:%M')
        
        embed = {
            "title": "📊 에픽세븐 유저 동향 알림",
            "description": f"🕒 **{current_time}** 크롤링 결과",
            "color": get_sentiment_color(categorized),
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 유저 동향 모니터링 시스템"
            }
        }
        
        # 카테고리별 필드 추가
        for category, posts in categorized.items():
            if posts:
                emoji = get_category_emoji(category)
                percentage = (len(posts) / total_posts * 100) if total_posts > 0 else 0
                
                # 상위 3개 게시글
                top_posts = []
                for i, post in enumerate(posts[:3], 1):
                    title = post['title'][:40] + "..." if len(post['title']) > 40 else post['title']
                    source = get_source_type_korean(post.get('source', ''))
                    top_posts.append(f"{i}. {title} ({source})")
                
                if len(posts) > 3:
                    top_posts.append(f"... 외 {len(posts) - 3}개")
                
                field_value = f"**{len(posts)}개** ({percentage:.1f}%)\n" + "\n".join(top_posts)
                
                embed["fields"].append({
                    "name": f"{emoji} {category}",
                    "value": field_value,
                    "inline": True
                })
        
        # 전체 통계 추가
        if total_posts > 0:
            embed["fields"].append({
                "name": "📈 전체 통계",
                "value": f"총 {total_posts}개 게시글 분석 완료",
                "inline": False
            })
        
        # Discord 전송
        data = {
            "embeds": [embed],
            "username": "Epic7 유저 동향 모니터",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print(f"[SUCCESS] 유저 동향 알림 전송 성공: {total_posts}개 게시글")
        else:
            print(f"[WARN] 유저 동향 알림 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 유저 동향 알림 전송 중 오류: {e}")

def get_sentiment_color(categorized):
    """감성 비율에 따른 색상 결정"""
    total = sum(len(posts) for posts in categorized.values())
    if total == 0:
        return 0x808080  # 회색
    
    positive_ratio = len(categorized['긍정']) / total
    negative_ratio = len(categorized['부정']) / total
    
    if positive_ratio > 0.5:
        return 0x00ff00  # 녹색 (긍정 우세)
    elif negative_ratio > 0.4:
        return 0xff4444  # 빨간색 (부정 우세)
    else:
        return 0x4488ff  # 파란색 (중립/혼재)

def send_daily_report(webhook_url, report_data):
    """일간 감성 동향 보고서 전송"""
    if not webhook_url:
        return
        
    try:
        print("[INFO] 일간 감성 동향 보고서 전송 시작")
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        
        # 리포트 데이터 처리
        if isinstance(report_data, dict) and 'sentiment_report' in report_data:
            # 새로운 형식 (감성 분석 데이터)
            sentiment_report = report_data['sentiment_report']
            analysis = report_data.get('analysis', {})
            bug_count = report_data.get('bug_count', 0)
        else:
            # 기존 형식 호환
            sentiment_report = report_data
            analysis = {}
            bug_count = 0
        
        total_posts = sum(len(posts) for posts in sentiment_report.values())
        
        # Embed 구성
        embed = {
            "title": "📊 에픽세븐 일간 감성 동향 보고서",
            "description": f"📅 **{current_time}**\n📈 **분석 게시글: {total_posts}개**",
            "color": 0x4488ff,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 일간 동향 분석 시스템"
            }
        }
        
        # 감성 카테고리별 통계
        for category, posts in sentiment_report.items():
            if category in ['긍정', '중립', '부정']:
                emoji = get_category_emoji(category)
                percentage = (len(posts) / total_posts * 100) if total_posts > 0 else 0
                
                # 대표 게시글 (상위 3개)
                top_posts = []
                for i, post in enumerate(posts[:3], 1):
                    title = post['title'][:35] + "..." if len(post['title']) > 35 else post['title']
                    top_posts.append(f"{i}. {title}")
                
                if len(posts) > 3:
                    top_posts.append(f"... 외 {len(posts) - 3}개")
                
                field_value = f"**{len(posts)}개** ({percentage:.1f}%)"
                if top_posts:
                    field_value += "\n" + "\n".join(top_posts)
                
                embed["fields"].append({
                    "name": f"{emoji} {category} 동향",
                    "value": field_value,
                    "inline": True
                })
        
        # 인사이트 분석 추가
        if analysis:
            insight_text = f"**주요 동향**: {analysis.get('trend', '중립적')}\n"
            insight_text += f"**분석**: {analysis.get('insight', '특별한 변화 없음')}\n"
            insight_text += f"**권장사항**: {analysis.get('recommendation', '지속적인 모니터링 필요')}"
            
            embed["fields"].append({
                "name": "🔍 동향 인사이트",
                "value": insight_text,
                "inline": False
            })
        
        # 버그 현황 참고 정보
        if bug_count > 0:
            embed["fields"].append({
                "name": "🐛 버그 현황 (참고)",
                "value": f"{bug_count}개 (실시간 알림으로 처리됨)",
                "inline": True
            })
        
        # Discord 전송
        data = {
            "embeds": [embed],
            "username": "Epic7 일간 리포터",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print("[SUCCESS] 일간 감성 동향 보고서 전송 완료")
        else:
            print(f"[WARN] 일간 보고서 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 일간 보고서 전송 중 오류: {e}")

def send_discord_message(webhook_url, message, count):
    """Discord 메시지 전송"""
    try:
        data = {
            "content": message,
            "username": "Epic7 Bug Monitor",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print(f"[SUCCESS] Discord 알림 {count} 전송 성공")
        else:
            print(f"[WARN] Discord 알림 {count} 전송 실패: {response.status_code}")
            
        time.sleep(1.5)  # Rate Limit 방지
        
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")

def get_source_type_korean(source):
    """소스 타입을 한국어로 변환"""
    source_map = {
        "stove_bug": "🏪 스토브 버그",
        "stove_general": "🏪 스토브 자유",
        "ruliweb_epic7": "🎮 루리웹",
        "reddit_epic7": "🌐 Reddit",
        "unknown": "❓ 기타"
    }
    return source_map.get(source, f"🔸 {source}")

def get_category_emoji(category):
    """카테고리별 이모지 반환"""
    emoji_map = {
        "긍정": "😊",
        "중립": "😐", 
        "부정": "😞",
        "버그": "🐛"
    }
    return emoji_map.get(category, "📌")

def format_timestamp(timestamp_str):
    """타임스탬프를 yyyy-mm-dd hh:mm 형태로 포맷"""
    try:
        if timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        else:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"[WARN] 시간 포맷 변환 실패: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M')