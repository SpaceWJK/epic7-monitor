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
TRANSLATION_ENABLED = True
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
                print("[INFO] 번역기 초기화 완료 (영어→한국어)")
            except Exception as e:
                print(f"[ERROR] 번역기 초기화 실패: {e}")
                self.translator = None
    
    def load_translation_cache(self) -> Dict[str, Dict]:
        """번역 캐시 로드"""
        if os.path.exists(TRANSLATION_CACHE_FILE):
            try:
                with open(TRANSLATION_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] 번역 캐시 로드 실패: {e}")
        return {}
    
    def save_translation_cache(self):
        """번역 캐시 저장"""
        try:
            # 캐시 크기 제한 (최대 500개)
            if len(self.cache) > 500:
                # 오래된 캐시 삭제
                sorted_items = sorted(
                    self.cache.items(), 
                    key=lambda x: x[1].get('timestamp', ''), 
                    reverse=True
                )
                self.cache = dict(sorted_items[:500])
            
            with open(TRANSLATION_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 번역 캐시 저장 실패: {e}")
    
    def get_cache_key(self, text: str) -> str:
        """캐시 키 생성"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def detect_language(self, text: str) -> str:
        """간단한 언어 감지 (한국어/영어 구분)"""
        if not text:
            return 'unknown'
        
        # 한국어 문자 비율 확인
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if korean_chars > english_chars:
            return 'ko'
        elif english_chars > 0:
            return 'en'
        else:
            return 'unknown'
    
    def needs_translation(self, text: str) -> bool:
        """번역 필요성 검사"""
        if not text or not TRANSLATION_ENABLED or not self.translator:
            return False
        
        # 언어 감지
        detected_lang = self.detect_language(text)
        
        # 한국어면 번역 불필요
        if detected_lang == 'ko':
            return False
        
        # 영어 또는 기타 언어면 번역 필요
        return detected_lang in ['en', 'unknown']
    
    def translate_text(self, text: str, force_translate: bool = False) -> str:
        """텍스트 번역 (영어→한국어만)"""
        if not text:
            return text
        
        # 번역 필요성 검사
        if not force_translate and not self.needs_translation(text):
            return text
        
        # 통계 업데이트
        self.translation_stats['total_requests'] += 1
        
        # 캐시 확인
        cache_key = self.get_cache_key(text)
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            # 캐시 유효성 확인 (24시간)
            cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
            if datetime.now() - cache_time < timedelta(hours=24):
                self.translation_stats['cache_hits'] += 1
                return cached_item['translated_text']
        
        # 번역 시도
        try:
            if not self.translator:
                raise Exception("번역기가 초기화되지 않음")
            
            print(f"[TRANSLATE] 번역 시도: {text[:50]}...")
            translated = self.translator.translate(text)
            
            if translated and translated != text:
                # 캐시에 저장
                self.cache[cache_key] = {
                    'original_text': text,
                    'translated_text': translated,
                    'timestamp': datetime.now().isoformat()
                }
                self.save_translation_cache()
                self.translation_stats['translation_success'] += 1
                print(f"[SUCCESS] 번역 완료: {translated[:50]}...")
                return translated
            else:
                raise Exception("번역 결과가 비어있거나 원문과 동일함")
                
        except Exception as e:
            print(f"[ERROR] 번역 실패: {e}")
            self.translation_stats['translation_failed'] += 1
            return text  # 번역 실패 시 원문 반환
    
    def translate_batch(self, texts: List[str]) -> List[str]:
        """배치 번역"""
        if not texts:
            return texts
        
        translated_texts = []
        for text in texts:
            translated = self.translate_text(text)
            translated_texts.append(translated)
            # 과도한 API 호출 방지
            time.sleep(0.1)
        
        return translated_texts
    
    def get_translation_stats(self) -> Dict:
        """번역 통계 반환"""
        return self.translation_stats.copy()

class NotificationManager:
    """Epic7 모니터링 시스템 알림 관리자"""
    
    def __init__(self, mode: str = "korean"):
        self.mode = mode
        self.webhooks = self.load_webhooks()
        self.notification_stats = self.load_notification_stats()
        self.translation_manager = TranslationManager()
        
        # 알림 제한 설정
        self.max_message_length = 1900
        self.max_embed_fields = 25
        self.retry_attempts = 3
        self.retry_delay = 2
        
        print(f"[INFO] NotificationManager 초기화 완료 - 모드: {mode}")
    
    def load_webhooks(self) -> Dict[str, str]:
        """Discord 웹훅 환경변수 로드"""
        webhooks = {}
        
        # 버그 알림 웹훅
        bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
        if bug_webhook:
            webhooks['bug'] = bug_webhook
            print("[INFO] 버그 알림 웹훅 설정 완료")
        
        # 감성 동향 웹훅
        sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
        if sentiment_webhook:
            webhooks['sentiment'] = sentiment_webhook
            print("[INFO] 감성 동향 웹훅 설정 완료")
        
        # 일간 보고서 웹훅 (번역 제외)
        report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
        if report_webhook:
            webhooks['report'] = report_webhook
            print("[INFO] 일간 보고서 웹훅 설정 완료")
        
        return webhooks
    
    def load_notification_stats(self) -> Dict:
        """알림 통계 로드"""
        stats_file = f"notification_stats_{self.mode}.json"
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'total_sent': 0,
            'total_failed': 0,
            'success_rate': 0.0,
            'last_reset': datetime.now().isoformat(),
            'daily_stats': {}
        }
    
    def save_notification_stats(self):
        """알림 통계 저장"""
        stats_file = f"notification_stats_{self.mode}.json"
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.notification_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 알림 통계 저장 실패: {e}")
    
    def get_source_display_name(self, source: str) -> str:
        """소스 표시명 반환"""
        source_names = {
            'stove_bug': '🏪 스토브 버그게시판',
            'stove_general': '🏪 스토브 자유게시판',
            'stove_global_bug': '🌍 스토브 글로벌 버그',
            'stove_global_general': '🌍 스토브 글로벌 자유',
            'ruliweb_epic7': '🎮 루리웹 에픽세븐',
            'arca_epic7': '🔥 아카라이브 에픽세븐',
            'reddit_epic7': '🌐 Reddit EpicSeven',
            'global_forum': '🌍 글로벌 포럼'
        }
        return source_names.get(source, source)
    
    def get_category_emoji(self, category: str) -> str:
        """카테고리별 이모지 반환"""
        emoji_map = {
            '버그': '🐛',
            'bug': '🐛',
            '긍정': '😊',
            'positive': '😊',
            '부정': '😞',
            'negative': '😞',
            '기타': '📝',
            'other': '📝',
            '일반': '💬',
            'general': '💬'
        }
        return emoji_map.get(category.lower(), '📝')
    
    def truncate_text(self, text: str, max_length: int = 100) -> str:
        """텍스트 길이 제한"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + '...'
    
    def format_post_for_notification(self, post: Dict) -> Dict[str, str]:
        """게시글 알림 포맷팅 (번역 포함)"""
        title = post.get('title', '')
        content = post.get('content', '')
        source = post.get('source', '')
        
        # 번역 적용
        translated_title = self.translation_manager.translate_text(title)
        translated_content = self.translation_manager.translate_text(content)
        
        # 번역 여부 확인
        title_translated = (translated_title != title)
        content_translated = (translated_content != content)
        
        # 포맷팅
        formatted_title = translated_title
        formatted_content = translated_content
        
        # 번역된 경우 원문 표시
        if title_translated:
            formatted_title = f"{translated_title}\n📝 원문: {self.truncate_text(title, 80)}"
        
        if content_translated and content:
            formatted_content = f"{translated_content}\n📝 원문: {self.truncate_text(content, 100)}"
        
        return {
            'title': formatted_title,
            'content': formatted_content,
            'source_name': self.get_source_display_name(source),
            'url': post.get('url', ''),
            'timestamp': post.get('timestamp', ''),
            'translated': title_translated or content_translated
        }
    
    def split_long_message(self, content: str, max_length: int = 1900) -> List[str]:
        """긴 메시지 분할"""
        if len(content) <= max_length:
            return [content]
        
        messages = []
        current_message = ""
        lines = content.split('\n')
        
        for line in lines:
            if len(current_message + line + '\n') <= max_length:
                current_message += line + '\n'
            else:
                if current_message:
                    messages.append(current_message.strip())
                    current_message = line + '\n'
                else:
                    # 한 줄이 너무 긴 경우 강제 분할
                    while len(line) > max_length:
                        messages.append(line[:max_length])
                        line = line[max_length:]
                    current_message = line + '\n'
        
        if current_message:
            messages.append(current_message.strip())
        
        return messages
    
    def send_webhook_message(self, webhook_url: str, data: Dict, max_retries: int = 3) -> bool:
        """Discord 웹훅 메시지 전송"""
        if not webhook_url:
            print("[WARNING] 웹훅 URL이 없어 메시지 전송을 건너뜁니다.")
            return False
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    webhook_url,
                    json=data,
                    timeout=15,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 204:
                    print(f"[INFO] Discord 메시지 전송 성공 (시도 {attempt + 1}/{max_retries})")
                    self.notification_stats['total_sent'] += 1
                    return True
                elif response.status_code == 429:
                    # Rate limit 처리
                    retry_after = response.headers.get('Retry-After', 5)
                    print(f"[WARNING] Rate limit 발생, {retry_after}초 후 재시도")
                    time.sleep(float(retry_after))
                    continue
                else:
                    print(f"[ERROR] Discord 메시지 전송 실패: {response.status_code}")
                    print(f"[ERROR] 응답 내용: {response.text}")
                    
            except requests.exceptions.Timeout:
                print(f"[ERROR] 메시지 전송 타임아웃 (시도 {attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"[ERROR] 메시지 전송 중 오류 (시도 {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        self.notification_stats['total_failed'] += 1
        return False
    
    def send_bug_alert(self, posts: List[Dict]) -> bool:
        """버그 알림 전송 (번역 포함)"""
        if not posts:
            return True
        
        webhook_url = self.webhooks.get('bug')
        if not webhook_url:
            print("[WARNING] 버그 알림 웹훅이 설정되지 않았습니다.")
            return False
        
        # 메시지 구성
        title = "🚨 Epic7 버그 알림"
        description = f"**{len(posts)}개의 새로운 버그 관련 게시글이 발견되었습니다.**\n\n"
        
        embed_fields = []
        for i, post in enumerate(posts[:10]):  # 최대 10개만 표시
            formatted_post = self.format_post_for_notification(post)
            
            field_value = f"**출처:** {formatted_post['source_name']}\n"
            if formatted_post['content']:
                field_value += f"**내용:** {self.truncate_text(formatted_post['content'], 200)}\n"
            field_value += f"**시간:** {formatted_post['timestamp'][:19]}\n"
            field_value += f"[전체 내용 보기]({formatted_post['url']})"
            
            # 번역 표시
            translation_emoji = "🌐" if formatted_post['translated'] else ""
            
            embed_fields.append({
                "name": f"🐛 {translation_emoji} {self.truncate_text(formatted_post['title'], 80)}",
                "value": field_value,
                "inline": False
            })
        
        # 임베드 데이터 구성
        embed_data = {
            "title": title,
            "description": description,
            "color": 0xff0000,  # 빨간색
            "fields": embed_fields,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Epic7 모니터링 시스템 | 번역: {self.translation_manager.get_translation_stats()['translation_success']}건"
            }
        }
        
        # 메시지 전송
        data = {"embeds": [embed_data]}
        
        # 메시지 길이 확인 및 분할
        message_json = json.dumps(data, ensure_ascii=False)
        if len(message_json) > 5000:  # Discord 메시지 크기 제한
            embed_data["fields"] = embed_fields[:5]
            remaining_count = len(posts) - 5
            if remaining_count > 0:
                embed_data["description"] += f"\n*({remaining_count}개 추가 버그 게시글이 더 있습니다.)*"
            data = {"embeds": [embed_data]}
        
        success = self.send_webhook_message(webhook_url, data)
        if success:
            print(f"[INFO] 버그 알림 전송 완료: {len(posts)}개 게시글 (번역 포함)")
        
        return success
    
    def send_sentiment_notification(self, posts: List[Dict], sentiment_summary: Dict) -> bool:
        """감성 동향 알림 전송 (번역 포함)"""
        if not posts:
            return True
        
        webhook_url = self.webhooks.get('sentiment')
        if not webhook_url:
            print("[WARNING] 감성 동향 웹훅이 설정되지 않았습니다.")
            return False
        
        # 감성 분석 결과 요약
        total_posts = len(posts)
        positive_count = sentiment_summary.get('positive', 0)
        negative_count = sentiment_summary.get('negative', 0)
        neutral_count = sentiment_summary.get('neutral', 0)
        
        # 메시지 구성
        title = "📊 Epic7 유저 동향"
        description = f"**{total_posts}개의 새로운 게시글 감성 분석 결과**\n\n"
        description += f"😊 긍정: {positive_count}개\n"
        description += f"😞 부정: {negative_count}개\n"
        description += f"😐 중립: {neutral_count}개\n\n"
        
        # 감성별 대표 게시글 (번역 포함)
        embed_fields = []
        
        # 긍정 게시글
        positive_posts = [p for p in posts if p.get('sentiment') == 'positive'][:3]
        if positive_posts:
            for post in positive_posts:
                formatted_post = self.format_post_for_notification(post)
                translation_emoji = "🌐" if formatted_post['translated'] else ""
                embed_fields.append({
                    "name": f"😊 {translation_emoji} {self.truncate_text(formatted_post['title'], 80)}",
                    "value": f"출처: {formatted_post['source_name']}\n[내용 보기]({formatted_post['url']})",
                    "inline": True
                })
        
        # 부정 게시글
        negative_posts = [p for p in posts if p.get('sentiment') == 'negative'][:3]
        if negative_posts:
            for post in negative_posts:
                formatted_post = self.format_post_for_notification(post)
                translation_emoji = "🌐" if formatted_post['translated'] else ""
                embed_fields.append({
                    "name": f"😞 {translation_emoji} {self.truncate_text(formatted_post['title'], 80)}",
                    "value": f"출처: {formatted_post['source_name']}\n[내용 보기]({formatted_post['url']})",
                    "inline": True
                })
        
        # 임베드 데이터 구성
        embed_data = {
            "title": title,
            "description": description,
            "color": 0x00ff00 if positive_count > negative_count else 0xff9900,
            "fields": embed_fields,
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Epic7 모니터링 시스템 | 번역: {self.translation_manager.get_translation_stats()['translation_success']}건"
            }
        }
        
        # 메시지 전송
        data = {"embeds": [embed_data]}
        success = self.send_webhook_message(webhook_url, data)
        if success:
            print(f"[INFO] 감성 동향 알림 전송 완료: {total_posts}개 게시글 (번역 포함)")
        
        return success
    
    def send_daily_report(self, report_data: Dict) -> bool:
        """일간 리포트 전송 (번역 제외 - 데이터 취합 결과)"""
        webhook_url = self.webhooks.get('report')
        if not webhook_url:
            print("[WARNING] 일간 리포트 웹훅이 설정되지 않았습니다.")
            return False
        
        # 리포트 데이터 추출
        total_posts = report_data.get('total_posts', 0)
        bug_posts = report_data.get('bug_posts', 0)
        positive_posts = report_data.get('positive_posts', 0)
        negative_posts = report_data.get('negative_posts', 0)
        top_sources = report_data.get('top_sources', [])
        
        # 메시지 구성 (번역 없음 - 데이터 취합 결과)
        title = "📈 Epic7 일간 리포트"
        description = f"**지난 24시간 Epic7 커뮤니티 동향**\n\n"
        description += f"📊 **전체 통계**\n"
        description += f"• 총 게시글: {total_posts}개\n"
        description += f"• 버그 관련: {bug_posts}개\n"
        description += f"• 긍정적: {positive_posts}개\n"
        description += f"• 부정적: {negative_posts}개\n\n"
        
        # 주요 소스별 활동
        if top_sources:
            description += f"🔥 **활발한 커뮤니티**\n"
            for source_info in top_sources[:5]:
                source_name = self.get_source_display_name(source_info['source'])
                description += f"• {source_name}: {source_info['count']}개\n"
            description += "\n"
        
        # 감성 분석 트렌드
        sentiment_score = positive_posts - negative_posts
        if sentiment_score > 0:
            trend_emoji = "📈"
            trend_text = "긍정적 트렌드"
        elif sentiment_score < 0:
            trend_emoji = "📉"
            trend_text = "부정적 트렌드"
        else:
            trend_emoji = "➡️"
            trend_text = "중립적 트렌드"
        
        description += f"{trend_emoji} **감성 트렌드:** {trend_text}\n"
        
        # 번역 통계 추가
        translation_stats = self.translation_manager.get_translation_stats()
        description += f"🌐 **번역 통계:** {translation_stats['translation_success']}건 성공\n"
        
        # 임베드 데이터 구성
        embed_data = {
            "title": title,
            "description": description,
            "color": 0x0099ff,  # 파란색
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Epic7 모니터링 시스템 | 모드: {self.mode}"
            }
        }
        
        # 메시지 전송
        data = {"embeds": [embed_data]}
        success = self.send_webhook_message(webhook_url, data)
        if success:
            print(f"[INFO] 일간 리포트 전송 완료: {total_posts}개 게시글 분석 (번역 제외)")
        
        return success
    
    def send_system_alert(self, alert_type: str, message: str, level: str = "info") -> bool:
        """시스템 알림 전송"""
        webhook_url = self.webhooks.get('bug')  # 기본적으로 버그 채널 사용
        if not webhook_url:
            print("[WARNING] 시스템 알림 웹훅이 설정되지 않았습니다.")
            return False
        
        # 알림 레벨에 따른 색상 설정
        colors = {
            'info': 0x0099ff,
            'warning': 0xff9900,
            'error': 0xff0000,
            'success': 0x00ff00
        }
        
        # 알림 타입에 따른 이모지
        emojis = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅'
        }
        
        embed_data = {
            "title": f"{emojis.get(level, 'ℹ️')} {alert_type}",
            "description": message,
            "color": colors.get(level, 0x0099ff),
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Epic7 모니터링 시스템 | 모드: {self.mode}"
            }
        }
        
        data = {"embeds": [embed_data]}
        success = self.send_webhook_message(webhook_url, data)
        if success:
            print(f"[INFO] 시스템 알림 전송 완료: {alert_type}")
        
        return success
    
    def update_notification_stats(self):
        """알림 통계 업데이트"""
        total = self.notification_stats['total_sent'] + self.notification_stats['total_failed']
        if total > 0:
            self.notification_stats['success_rate'] = (
                self.notification_stats['total_sent'] / total * 100
            )
        
        # 일일 통계 업데이트
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.notification_stats['daily_stats']:
            self.notification_stats['daily_stats'][today] = {
                'sent': 0,
                'failed': 0
            }
        
        self.save_notification_stats()
    
    def get_notification_stats(self) -> Dict:
        """알림 통계 조회"""
        self.update_notification_stats()
        stats = self.notification_stats.copy()
        stats['translation_stats'] = self.translation_manager.get_translation_stats()
        return stats
    
    def cleanup_old_stats(self, days: int = 30):
        """오래된 통계 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        daily_stats = self.notification_stats.get('daily_stats', {})
        self.notification_stats['daily_stats'] = {
            date: stats for date, stats in daily_stats.items()
            if date >= cutoff_str
        }
        
        self.save_notification_stats()
        print(f"[INFO] {days}일 이전 통계 정리 완료")

# 편의 함수들
def create_notification_manager(mode: str = "korean") -> NotificationManager:
    """알림 관리자 생성"""
    return NotificationManager(mode)

def send_bug_alert(posts: List[Dict], mode: str = "korean") -> bool:
    """버그 알림 전송 (편의 함수)"""
    manager = create_notification_manager(mode)
    return manager.send_bug_alert(posts)

def send_sentiment_notification(posts: List[Dict], sentiment_summary: Dict, mode: str = "korean") -> bool:
    """감성 알림 전송 (편의 함수)"""
    manager = create_notification_manager(mode)
    return manager.send_sentiment_notification(posts, sentiment_summary)

def send_daily_report(report_data: Dict, mode: str = "korean") -> bool:
    """일간 리포트 전송 (편의 함수)"""
    manager = create_notification_manager(mode)
    return manager.send_daily_report(report_data)

def send_system_alert(alert_type: str, message: str, level: str = "info", mode: str = "korean") -> bool:
    """시스템 알림 전송 (편의 함수)"""
    manager = create_notification_manager(mode)
    return manager.send_system_alert(alert_type, message, level)

# 메인 실행부
if __name__ == "__main__":
    # 테스트용 코드
    print("=== Epic7 모니터링 시스템 - 한국어 전용 번역 알림 테스트 ===")
    
    # 테스트 데이터
    test_posts = [
        {
            "title": "Character skill animation bug in arena",
            "url": "https://example.com/post1",
            "content": "The character skill animation is stuck in arena battles.",
            "timestamp": datetime.now().isoformat(),
            "source": "reddit_epic7",
            "sentiment": "negative"
        },
        {
            "title": "새로운 캐릭터 너무 좋아요!",
            "url": "https://example.com/post2",
            "content": "새 캐릭터가 정말 멋있습니다.",
            "timestamp": datetime.now().isoformat(),
            "source": "stove_general",
            "sentiment": "positive"
        }
    ]
    
    # 알림 관리자 생성
    manager = create_notification_manager("korean")
    
    # 버그 알림 테스트
    bug_posts = [p for p in test_posts if p.get('source') == 'reddit_epic7']
    if bug_posts:
        print("버그 알림 테스트 중...")
        manager.send_bug_alert(bug_posts)
    
    # 감성 알림 테스트
    sentiment_summary = {
        'positive': 1,
        'negative': 1,
        'neutral': 0
    }
    print("감성 알림 테스트 중...")
    manager.send_sentiment_notification(test_posts, sentiment_summary)
    
    # 통계 출력
    stats = manager.get_notification_stats()
    print(f"알림 통계: {stats}")
    
    # 번역 통계 출력
    translation_stats = manager.translation_manager.get_translation_stats()
    print(f"번역 통계: {translation_stats}")
    
    print("=== 알림 테스트 완료 ===")