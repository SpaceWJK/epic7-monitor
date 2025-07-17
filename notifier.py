# notifier.py - Epic7 모니터링 시스템 한국어 전용 번역 알림 시스템
# 영어→한국어 단방향 번역만 지원하는 최적화된 버전

import json
import os
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import re
import hashlib
from urllib.parse import urlparse

# 번역 라이브러리 임포트
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
    print("[INFO] deep-translator 라이브러리 로드 성공")
except ImportError:
    TRANSLATION_AVAILABLE = False
    print("[WARNING] deep-translator 라이브러리가 설치되지 않음. 번역 기능 비활성화")

# 번역 설정
TRANSLATION_CACHE_FILE = "translation_cache.json"
TRANSLATION_ENABLED = True # 번역 기능 활성화 여부
DEFAULT_TARGET_LANGUAGE = "ko"  # 한국어로 고정
TRANSLATION_TIMEOUT = 10  # 번역 타임아웃 (초)

class TranslationManager:
    """번역 관리자 - 영어→한국어 단방향 번역 전용"""
    
    def __init__(self):
        self.cache = self.load_translation_cache()
        self.translator = None
        self.translation_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'translation_success': 0,
            'translation_failed': 0
        }
        if TRANSLATION_AVAILABLE:
            try:
                self.translator = GoogleTranslator(source='auto', target=DEFAULT_TARGET_LANGUAGE)
                print("[INFO] GoogleTranslator 인스턴스 생성 성공")
            except Exception as e:
                print(f"[ERROR] GoogleTranslator 인스턴스 생성 실패: {e}")
                global TRANSLATION_ENABLED
                TRANSLATION_ENABLED = False
    
    def load_translation_cache(self) -> Dict[str, str]:
        """번역 캐시 로드"""
        try:
            if os.path.exists(TRANSLATION_CACHE_FILE):
                with open(TRANSLATION_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"[ERROR] 번역 캐시 로드 실패: {e}")
            return {}
    
    def save_translation_cache(self):
        """번역 캐시 저장"""
        try:
            # 캐시 파일 최대 크기 제한 (예: 5MB)
            if os.path.exists(TRANSLATION_CACHE_FILE) and os.path.getsize(TRANSLATION_CACHE_FILE) > 5 * 1024 * 1024:
                print(f"[WARNING] 번역 캐시 파일이 너무 큽니다 ({os.path.getsize(TRANSLATION_CACHE_FILE) / (1024 * 1024):.2f}MB). 오래된 항목을 정리합니다.")
                # TODO: 여기에 캐시 정리 로직 추가 (예: 가장 오래된 10% 삭제)
                # 현재는 단순히 새롭게 덮어씁니다.
                pass
                
            with open(TRANSLATION_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 번역 캐시 저장 실패: {e}")

    def translate_text(self, text: str) -> str:
        """
        영어 텍스트를 한국어로 번역 (캐시 및 폴백 적용)
        다른 언어는 번역하지 않고 그대로 반환
        """
        self.translation_stats['total_requests'] += 1
        
        if not TRANSLATION_ENABLED or not self.translator:
            # print("[INFO] 번역 기능 비활성화 또는 번역기 초기화 실패. 원본 텍스트 반환.")
            return text # 번역 비활성화 시 원본 텍스트 반환

        # 텍스트가 이미 한국어인지 확인 (간단한 한글 포함 여부로 판단)
        if re.search(r'[ㄱ-ㅎ가-힣]', text):
            # print(f"[INFO] 텍스트에 한글이 포함되어 있어 번역을 건너뜜: {text[:50]}...")
            return text
            
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        if text_hash in self.cache:
            self.translation_stats['cache_hits'] += 1
            # print(f"[INFO] 캐시 히트: {text[:20]}... -> {self.cache[text_hash][:20]}...")
            return self.cache[text_hash]
        
        try:
            # print(f"[INFO] 번역 시도: {text[:50]}...")
            translated = self.translator.translate(text)
            self.cache[text_hash] = translated
            self.translation_stats['translation_success'] += 1
            # print(f"[INFO] 번역 성공: {translated[:50]}...")
            self.save_translation_cache() # 번역 성공 시마다 캐시 저장
            return translated
        except Exception as e:
            self.translation_stats['translation_failed'] += 1
            print(f"[ERROR] 번역 실패 (deep-translator): {e} (텍스트: {text[:100]}...)")
            return text # 실패 시 원본 텍스트 반환

class DiscordNotificationManager:
    """Discord 알림 전송을 관리하는 클래스 (한국어 전용 번역 지원)"""

    def __init__(self, mode: str = "korean"):
        self.mode = mode
        self.bug_webhook = os.getenv('DISCORD_WEBHOOK_BUG')
        self.sentiment_webhook = os.getenv('DISCORD_WEBHOOK_SENTIMENT')
        self.report_webhook = os.getenv('DISCORD_WEBHOOK_REPORT')
        self.translation_manager = TranslationManager()
        print(f"[INFO] DiscordNotificationManager 초기화 완료 (모드: {mode})")

    def _send_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> bool:
        """실제 Discord 웹훅 전송"""
        if not webhook_url:
            print("[WARNING] Discord 웹훅 URL이 설정되지 않았습니다. 알림을 보낼 수 없습니다.")
            return False
        
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            response.raise_for_status()  # 200 이외의 상태 코드에 대해 예외 발생
            # print(f"[INFO] Discord 알림 전송 성공: {response.status_code}")
            return True
        except requests.exceptions.Timeout:
            print(f"[ERROR] Discord 웹훅 전송 타임아웃 (10초): {webhook_url}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Discord 웹훅 전송 실패: {e} (URL: {webhook_url})")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  응답 상태 코드: {e.response.status_code}")
                print(f"  응답 본문: {e.response.text}")
            return False

    def get_category_emoji(self, category: str) -> str:
        """카테고리별 이모지 반환"""
        emojis = {
            "버그": "🐞",
            "긍정": "✨",
            "부정": "🚨",
            "중립": "💬",
            "기타": "📝",
            "고우선순위 버그": "🔥🐞"
        }
        return emojis.get(category, "❓")

    def _format_post_for_discord(self, post: Dict[str, Any]) -> str:
        """단일 게시글을 Discord 메시지 형태로 포맷"""
        title = post.get('title', '제목 없음')
        url = post.get('url', '#')
        timestamp = post.get('timestamp', datetime.now().isoformat())
        source = post.get('source', '알 수 없음')
        category = post.get('category', '기타')
        
        # 제목을 한국어로 번역 (필요한 경우)
        translated_title = self.translation_manager.translate_text(title)

        source_display = {
            "stove_bug": "스토브 (버그)", "stove_general": "스토브 (일반)",
            "ruliweb_epic7": "루리웹", "arca_epic7": "아카라이브",
            "stove_global_bug": "스토브 글로벌 (버그)", "stove_global_general": "스토브 글로벌 (일반)",
            "reddit_epic7": "레딧", "epic7_official_forum": "공식 포럼"
        }.get(source, source) # 기본값으로 source 그대로 사용

        return (
            f"{self.get_category_emoji(category)} "
            f"**[{source_display}]** [{translated_title}]({url})\n"
            f"> <t:{int(datetime.fromisoformat(timestamp).timestamp())}:R>"
        )

    def send_bug_alert(self, bugs: List[Dict[str, Any]], is_high_priority: bool = False):
        """실시간 버그 알림 전송"""
        if not self.bug_webhook:
            print("[WARNING] 버그 알림 웹훅이 설정되지 않아 알림을 보낼 수 없습니다.")
            return

        if not bugs:
            # print("[INFO] 전송할 버그 알림이 없습니다.")
            return

        title_prefix = "🚨 실시간 버그 알림"
        color = 15548997  # 빨간색 (RGB)
        if is_high_priority:
            title_prefix = "🔥 긴급 버그 알림"
            color = 16711680 # 진한 빨간색

        embed_description_parts = []
        for bug in bugs:
            embed_description_parts.append(self._format_post_for_discord(bug))
        
        # Discord 메시지 길이 제한 (2000자) 고려하여 분할 전송
        MAX_DESCRIPTION_LENGTH = 1900 
        
        current_description_parts = []
        current_length = 0
        
        for part in embed_description_parts:
            if current_length + len(part) + 1 > MAX_DESCRIPTION_LENGTH: # +1 for newline
                # 현재까지 모은 파트 전송
                embed = {
                    "title": title_prefix,
                    "description": "\n".join(current_description_parts),
                    "color": color,
                    "timestamp": datetime.now().isoformat()
                }
                self._send_webhook(self.bug_webhook, {"embeds": [embed]})
                time.sleep(1) # 짧은 딜레이
                
                # 새 메시지 시작
                current_description_parts = [part]
                current_length = len(part)
            else:
                current_description_parts.append(part)
                current_length += len(part) + 1 # +1 for newline

        # 남은 메시지 전송
        if current_description_parts:
            embed = {
                "title": title_prefix,
                "description": "\n".join(current_description_parts),
                "color": color,
                "timestamp": datetime.now().isoformat()
            }
            self._send_webhook(self.bug_webhook, {"embeds": [embed]})
        
        print(f"[INFO] 총 {len(bugs)}개 버그 알림 전송 완료.")


    def send_sentiment_alert(self, sentiment_summary: Dict[str, int]):
        """감성 변화에 대한 알림 (옵션)"""
        if not self.sentiment_webhook:
            print("[WARNING] 감성 알림 웹훅이 설정되지 않아 알림을 보낼 수 없습니다.")
            return

        description = "최근 게시글 감성 변화:\n"
        for sentiment, count in sentiment_summary.items():
            description += f"{self.get_category_emoji(sentiment)} {sentiment}: {count}개\n"
        
        embed = {
            "title": "📈 감성 변화 알림",
            "description": description,
            "color": 3447003, # 파란색
            "timestamp": datetime.now().isoformat()
        }
        self._send_webhook(self.sentiment_webhook, {"embeds": [embed]})
        print("[INFO] 감성 알림 전송 완료.")

    def send_daily_report(self, report_data: Dict[str, Any]):
        """일일 통계 리포트 전송"""
        if not self.report_webhook:
            print("[WARNING] 일일 리포트 웹훅이 설정되지 않아 리포트를 보낼 수 없습니다.")
            return False

        # 필드 생성
        fields = [
            {"name": "📅 보고일", "value": report_data['date'], "inline": True},
            {"name": "📊 총 게시글 수", "value": f"{report_data['total_posts']}개", "inline": True},
            {"name": "🇰🇷 한국 게시글", "value": f"{report_data['korean_posts']}개", "inline": True},
            {"name": "🌐 글로벌 게시글", "value": f"{report_data['global_posts']}개", "inline": True},
            {"name": "🐞 버그", "value": f"{report_data['bug_posts']}개", "inline": True},
            {"name": "✨ 긍정", "value": f"{report_data['positive_posts']}개", "inline": True},
            {"name": "🚨 부정", "value": f"{report_data['negative_posts']}개", "inline": True},
            {"name": "💬 중립/기타", "value": f"{report_data['neutral_posts']}개", "inline": True},
        ]
        
        # 인기 소스 (상위 3개)
        if report_data['top_sources']:
            top_sources_str = "\n".join([f"- {source}: {count}개" for source, count in list(report_data['top_sources'].items())[:3]])
            fields.append({"name": "🔥 인기 게시판/소스", "value": top_sources_str, "inline": False})
        
        # 트렌드 분석
        if report_data['trend_analysis']:
            trend_str = ""
            for key, value in report_data['trend_analysis'].items():
                if isinstance(value, dict) and "trend" in value and "change" in value:
                    trend_icon = "⬆️" if value["trend"] == "up" else "⬇️" if value["trend"] == "down" else "➡️"
                    trend_str += f"- {key}: {trend_icon} {value['change']}\n"
                elif isinstance(value, str):
                    trend_str += f"- {key}: {value}\n"
            if trend_str:
                fields.append({"name": "📊 트렌드 분석", "value": trend_str, "inline": False})
        
        # 인사이트
        if report_data['insights']:
            insights_str = "\n".join([f"- {i}" for i in report_data['insights']])
            fields.append({"name": "💡 인사이트", "value": insights_str, "inline": False})
            
        # 권고사항
        if report_data['recommendations']:
            recommendations_str = "\n".join([f"- {r}" for r in report_data['recommendations']])
            fields.append({"name": "🛠️ 권고사항", "value": recommendations_str, "inline": False})

        embed = {
            "title": "✅ Epic Seven 일일 커뮤니티 동향 리포트",
            "description": "최근 24시간 동안의 커뮤니티 게시글 동향을 요약합니다.",
            "color": 3066993, # 초록색
            "fields": fields,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 모니터링 시스템"
            }
        }
        return self._send_webhook(self.report_webhook, {"embeds": [embed]})

    def send_health_check_alert(self, message: str, status: str = "success"):
        """시스템 헬스 체크 결과 알림"""
        webhook = self.report_webhook or self.bug_webhook # 리포트 웹훅 없으면 버그 웹훅 사용
        if not webhook:
            print("[WARNING] 헬스 체크 알림 웹훅이 설정되지 않아 알림을 보낼 수 없습니다.")
            return

        title = "💚 시스템 헬스 체크 성공"
        color = 3066993 # 초록색
        if status == "failure":
            title = "💔 시스템 헬스 체크 실패"
            color = 15548997 # 빨간색
        elif status == "warning":
            title = "💛 시스템 헬스 체크 경고"
            color = 16776960 # 노란색

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 모니터링 시스템 헬스 체크"
            }
        }
        self._send_webhook(webhook, {"embeds": [embed]})
        print(f"[INFO] 헬스 체크 알림 전송 완료 (상태: {status}).")

    def send_general_message(self, message: str, title: str = "알림", color: int = 3447003):
        """일반적인 메시지 전송 (디버깅, 정보 등)"""
        webhook = self.report_webhook or self.bug_webhook # 기본 웹훅 사용
        if not webhook:
            print("[WARNING] 일반 메시지 알림 웹훅이 설정되지 않아 알림을 보낼 수 없습니다.")
            return

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }
        self._send_webhook(webhook, {"embeds": [embed]})
        print(f"[INFO] 일반 메시지 전송 완료: {title}")

# 외부에서 호출될 유틸리티 함수 (하위 호환성 및 편리성)
def create_notification_manager(mode: str = "korean") -> DiscordNotificationManager:
    return DiscordNotificationManager(mode)

def send_discord_message(webhook_url: str, message: str, title: str = "알림", color: int = 3447003):
    """단순 텍스트 메시지 전송 (하위 호환성을 위한 래퍼)"""
    payload = {
        "embeds": [{
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }]
    }
    headers = {'Content-Type': 'application/json'}
    try:
        requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
        print(f"[INFO] 유틸리티 함수를 통한 Discord 메시지 전송 성공: {title}")
    except Exception as e:
        print(f"[ERROR] 유틸리티 함수를 통한 Discord 메시지 전송 실패: {e}")

if __name__ == "__main__":
    print("=== Epic7 모니터링 시스템 - 한국어 전용 번역 알림 테스트 ===")
    
    # 환경변수 설정 (테스트용. 실제 환경에서는 GitHub Secrets)
    os.environ['DISCORD_WEBHOOK_BUG'] = 'YOUR_BUG_WEBHOOK_URL' # 실제 웹훅 URL로 변경
    os.environ['DISCORD_WEBHOOK_REPORT'] = 'YOUR_REPORT_WEBHOOK_URL' # 실제 웹훅 URL로 변경
    os.environ['DISCORD_WEBHOOK_SENTIMENT'] = 'YOUR_SENTIMENT_WEBHOOK_URL' # 실제 웹훅 URL로 변경

    # 테스트 데이터
    test_posts = [
        {
            "title": "Character skill animation bug in arena",
            "url": "https://example.com/post1",
            "content": "The character skill animation is stuck in arena battles.",
            "timestamp": datetime.now().isoformat(),
            "source": "reddit_epic7",
            "sentiment": "negative",
            "category": "버그" # 분류기에서 오는 카테고리 추가
        },
        {
            "title": "새로운 캐릭터 너무 좋아요!",
            "url": "https://example.com/post2",
            "content": "새 캐릭터가 정말 멋있습니다.",
            "timestamp": datetime.now().isoformat(),
            "source": "stove_general",
            "sentiment": "positive",
            "category": "긍정" # 분류기에서 오는 카테고리 추가
        },
        {
            "title": "Patch notes are fantastic, great changes!",
            "url": "https://example.com/post3",
            "content": "This update truly improves the game experience. Thank you, Smilegate.",
            "timestamp": datetime.now().isoformat(),
            "source": "epic7_official_forum",
            "sentiment": "positive",
            "category": "긍정"
        }
    ]
    
    # 알림 관리자 생성
    manager = create_notification_manager("korean")
    
    # 버그 알림 테스트
    bug_posts = [p for p in test_posts if p.get('category') == '버그']
    if bug_posts:
        print("\n버그 알림 테스트 중...")
        manager.send_bug_alert(bug_posts, is_high_priority=True) # 긴급 버그로 테스트
    
    # 감성 알림 테스트
    sentiment_summary = {
        '긍정': 2,
        '부정': 1,
        '중립': 0
    }
    print("\n감성 알림 테스트 중...")
    manager.send_sentiment_alert(sentiment_summary)

    # 일일 리포트 테스트 (mock data)
    print("\n일일 리포트 테스트 중...")
    mock_report_data = {
        "date": datetime.now().strftime('%Y-%m-%d'),
        "total_posts": 100,
        "korean_posts": 60,
        "global_posts": 40,
        "bug_posts": 5,
        "positive_posts": 30,
        "negative_posts": 20,
        "neutral_posts": 45,
        "top_sources": {"stove_bug": 5, "ruliweb_epic7": 25, "reddit_epic7": 15},
        "trend_analysis": {
            "bug_posts": {"trend": "up", "change": "+2"},
            "positive_posts": {"trend": "down", "change": "-5"}
        },
        "insights": ["버그 관련 게시글이 증가 추세입니다.", "새로운 캐릭터에 대한 긍정적인 반응이 많습니다."],
        "recommendations": ["버그 리포트 게시판을 주기적으로 확인하고 대응하세요.", "긍정적인 피드백을 활용하여 마케팅 자료로 사용하세요."]
    }
    manager.send_daily_report(mock_report_data)

    # 헬스 체크 알림 테스트
    print("\n헬스 체크 알림 테스트 중...")
    manager.send_health_check_alert("시스템 정상 작동 중입니다.", "success")
    manager.send_health_check_alert("크롤링 모듈에 경고가 있습니다.", "warning")
    manager.send_health_check_alert("데이터베이스 연결 실패!", "failure")

    # 일반 메시지 테스트
    print("\n일반 메시지 테스트 중...")
    manager.send_general_message("이것은 일반 정보 메시지입니다.", "정보", 3447003)
    
    print("\n테스트 완료.")