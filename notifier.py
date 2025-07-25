#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 알림 시스템 v3.4 - 즉시 처리 완성판 (JSON 오류 수정)
Discord 알림 메시지 전송 및 포맷팅 시스템

주요 특징:
- 버그 알림 (빨간색, 긴급)
- 감성 동향 알림 (감성별 색상 구분) - 일괄 + 즉시 처리 지원
- 일간 리포트 (카드형 디자인)
- 헬스체크 (회색)
- 영어→한국어 자동 번역 기능
- 🚀 게시글별 즉시 감성 알림 추가 (v3.4)
- 🚀 일간 리포트용 데이터 저장 기능 추가 (v3.4)
- 🔧 Discord JSON 오류 수정 (payload 안전화 처리)

Master 요구사항 완벽 구현:
- 게시글 1개당 즉시 감성 분석 → 즉시 알림
- 일간 리포트용 감성 데이터 저장
- 기존 30분 주기 일괄 알림 기능 완전 보존
- Discord 웹훅 JSON 오류 해결

Author: Epic7 Monitoring Team
Version: 3.4 (즉시 처리 완성판 + JSON 오류 수정)
Date: 2025-07-24
Fixed: Discord JSON 직렬화 오류 해결
"""

import json
import os
import sys
import time
import requests
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from config import config
import logging
import psutil
import subprocess

# ✨ 번역 기능 추가 ✨
from deep_translator import GoogleTranslator

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 알림 시스템 설정
# =============================================================================

class NotificationConfig:
    """알림 시스템 설정"""
    
    # Discord 임베드 색상 (16진수)
    COLORS = {
        'bug': 0xFF0000,           # 빨간색 (긴급)
        'positive': 0x00FF00,      # 초록색 (긍정)
        'negative': 0xFF4500,      # 주황빨간색 (부정)
        'neutral': 0x808080,       # 회색 (중립)
        'report': 0x00CED1,        # 다크터콰이즈 (리포트)
        'health': 0x696969,        # 진회색 (헬스체크)
        'system': 0x4169E1         # 로열블루 (시스템)
    }
    
    # 감성별 색상 (v3.4 추가)
    SENTIMENT_COLORS = {
        'positive': COLORS['positive'],
        'negative': COLORS['negative'], 
        'neutral': COLORS['neutral']
    }
    
    # 감성별 이모지 (v3.4 추가)
    SENTIMENT_EMOJIS = {
        'positive': '😊',
        'negative': '😞', 
        'neutral': '😐'
    }
    
    # 메시지 제한
    MAX_EMBED_TITLE = 256
    MAX_EMBED_DESCRIPTION = 4096
    MAX_EMBED_FIELD_NAME = 256
    MAX_EMBED_FIELD_VALUE = 1024
    MAX_EMBEDS_PER_MESSAGE = 10
    
    # 알림 빈도 제한
    MAX_BUG_ALERTS_PER_HOUR = 50
    MAX_SENTIMENT_ALERTS_PER_HOUR = 100  # v3.4: 즉시 알림용
    
    # 웹훅 URL
    WEBHOOKS = {
        'bug': os.environ.get('DISCORD_WEBHOOK_BUG'),
        'sentiment': os.environ.get('DISCORD_WEBHOOK_SENTIMENT'),
        'report': os.environ.get('DISCORD_WEBHOOK_REPORT'),
        'health': os.environ.get('DISCORD_WEBHOOK_HEALTH')
    }

# =============================================================================
# 🚀 v3.4 추가: 일간 리포트용 감성 데이터 관리
# =============================================================================

DAILY_SENTIMENT_DATA_FILE = "daily_sentiment_data.json"

def save_sentiment_data_for_daily_report(post_data: Dict, classification: Dict) -> bool:
    """🚀 v3.4: 일간 리포트용 감성 데이터 저장"""
    try:
        # 기존 데이터 로드
        daily_data = load_daily_sentiment_data()
        
        # 새로운 감성 데이터 추가
        sentiment_entry = {
            'timestamp': datetime.now().isoformat(),
            'title': post_data.get('title', ''),
            'url': post_data.get('url', ''),
            'source': post_data.get('source', ''),
            'sentiment': classification.get('sentiment_analysis', {}).get('sentiment', 'neutral'),
            'confidence': classification.get('sentiment_analysis', {}).get('confidence', 0.0),
            'category': classification.get('category', 'neutral'),
            'saved_at': datetime.now().isoformat()
        }
        
        daily_data.append(sentiment_entry)
        
        # 24시간 이전 데이터 정리
        cutoff_time = datetime.now() - timedelta(hours=24)
        daily_data = [
            entry for entry in daily_data
            if datetime.fromisoformat(entry['saved_at']) > cutoff_time
        ]
        
        # 파일에 저장
        with open(DAILY_SENTIMENT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 일간 리포트용 감성 데이터 저장 완료: {sentiment_entry['title'][:30]}...")
        return True
        
    except Exception as e:
        logger.error(f"일간 리포트용 데이터 저장 실패: {e}")
        return False

def load_daily_sentiment_data() -> List[Dict]:
    """일간 리포트용 감성 데이터 로드"""
    try:
        if os.path.exists(DAILY_SENTIMENT_DATA_FILE):
            with open(DAILY_SENTIMENT_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 24시간 이전 데이터 필터링
            cutoff_time = datetime.now() - timedelta(hours=24)
            filtered_data = [
                entry for entry in data
                if datetime.fromisoformat(entry['saved_at']) > cutoff_time
            ]
            
            return filtered_data
        else:
            return []
            
    except Exception as e:
        logger.error(f"일간 리포트용 데이터 로드 실패: {e}")
        return []

# =============================================================================
# 알림 통계 관리
# =============================================================================

class NotificationStats:
    """알림 통계 관리"""
    
    STATS_FILE = "notification_stats.json"
    
    @staticmethod
    def load_stats() -> Dict:
        """통계 데이터 로드"""
        try:
            if os.path.exists(NotificationStats.STATS_FILE):
                with open(NotificationStats.STATS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return NotificationStats._get_empty_stats()
        except Exception as e:
            logger.error(f"통계 로드 실패: {e}")
            return NotificationStats._get_empty_stats()
    
    @staticmethod
    def save_stats(stats: Dict):
        """통계 데이터 저장"""
        try:
            with open(NotificationStats.STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"통계 저장 실패: {e}")
    
    @staticmethod
    def _get_empty_stats() -> Dict:
        """빈 통계 구조 생성"""
        return {
            'bug_notifications': 0,
            'sentiment_notifications': 0,
            'sentiment_immediate_notifications': 0,  # v3.4 추가
            'daily_reports': 0,
            'health_checks': 0,
            'total_notifications': 0,
            'failed_notifications': 0,
            'last_reset': datetime.now().isoformat(),
            'hourly_limits': {
                'bug_count': 0,
                'sentiment_count': 0,
                'last_hour_reset': datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
            }
        }
    
    @staticmethod
    def increment_stat(stat_name: str, amount: int = 1):
        """통계 증가"""
        try:
            stats = NotificationStats.load_stats()
            
            # 시간당 제한 체크 및 리셋
            NotificationStats._check_hourly_reset(stats)
            
            # 통계 증가
            if stat_name in stats:
                stats[stat_name] += amount
            
            stats['total_notifications'] += amount
            
            # 시간당 제한 카운터 업데이트
            if stat_name == 'bug_notifications':
                stats['hourly_limits']['bug_count'] += amount
            elif stat_name == 'sentiment_notifications' or stat_name == 'sentiment_immediate_notifications':
                stats['hourly_limits']['sentiment_count'] += amount
            
            NotificationStats.save_stats(stats)
            
        except Exception as e:
            logger.error(f"통계 업데이트 실패: {e}")
    
    @staticmethod
    def _check_hourly_reset(stats: Dict):
        """시간당 제한 리셋 체크"""
        try:
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            last_reset = datetime.fromisoformat(stats['hourly_limits']['last_hour_reset'])
            
            if current_hour > last_reset:
                stats['hourly_limits']['bug_count'] = 0
                stats['hourly_limits']['sentiment_count'] = 0
                stats['hourly_limits']['last_hour_reset'] = current_hour.isoformat()
                
        except Exception as e:
            logger.error(f"시간당 리셋 체크 실패: {e}")
    
    @staticmethod
    def check_rate_limit(notification_type: str) -> bool:
        """속도 제한 체크"""
        try:
            stats = NotificationStats.load_stats()
            NotificationStats._check_hourly_reset(stats)
            
            if notification_type == 'bug':
                return stats['hourly_limits']['bug_count'] < NotificationConfig.MAX_BUG_ALERTS_PER_HOUR
            elif notification_type == 'sentiment':
                return stats['hourly_limits']['sentiment_count'] < NotificationConfig.MAX_SENTIMENT_ALERTS_PER_HOUR
            
            return True
            
        except Exception as e:
            logger.error(f"속도 제한 체크 실패: {e}")
            return True

# =============================================================================
# 번역 시스템
# =============================================================================

class TranslationSystem:
    """번역 시스템"""
    
    def __init__(self):
        self.translator = GoogleTranslator(source='auto', target='ko')
        self.translation_cache = {}
        self.debug_log = []
    
    def translate_text(self, text: str, max_length: int = 500) -> str:
        """텍스트 번역"""
        if not text or len(text.strip()) == 0:
            return text
        
        # 한국어 텍스트인지 체크
        if self._is_korean_text(text):
            return text
        
        # 캐시 확인
        cache_key = text[:100]  # 캐시 키 길이 제한
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        try:
            # 번역 실행
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            translated = self.translator.translate(text)
            
            # 캐시 저장
            self.translation_cache[cache_key] = translated
            
            self.debug_log.append({
                'original': text[:50] + "..." if len(text) > 50 else text,
                'translated': translated[:50] + "..." if len(translated) > 50 else translated,
                'timestamp': datetime.now().isoformat()
            })
            
            return translated
            
        except Exception as e:
            logger.error(f"번역 실패: {e}")
            return text  # 원본 텍스트 반환
    
    def _is_korean_text(self, text: str) -> bool:
        """한국어 텍스트 여부 확인"""
        korean_chars = sum(1 for char in text if ord(char) >= 0xAC00 and ord(char) <= 0xD7A3)
        return korean_chars / len(text) > 0.3 if text else False

# 전역 번역 시스템 인스턴스
translation_system = TranslationSystem()

# =============================================================================
# Epic7 통합 알림 시스템
# =============================================================================

class Epic7Notifier:
    """Epic7 Discord 알림 시스템 v3.4"""
    
    def __init__(self):
        """알림 시스템 초기화"""
        self.webhooks = NotificationConfig.WEBHOOKS
        self.colors = NotificationConfig.COLORS
        self.stats = NotificationStats.load_stats()
        
        # 웹훅 유효성 검사
        self._validate_webhooks()
        
        logger.info("Epic7 알림 시스템 v3.4 초기화 완료")
    
    def _validate_webhooks(self):
        """웹훅 유효성 검사"""
        valid_webhooks = {}
        for name, url in self.webhooks.items():
            if url and url.startswith('https://discord.com/api/webhooks/'):
                valid_webhooks[name] = url
            else:
                logger.warning(f"유효하지 않은 웹훅: {name}")
        
        self.webhooks = valid_webhooks
        
        if not self.webhooks:
            logger.error("유효한 Discord 웹훅이 없습니다!")
    
    def _sanitize_payload(self, payload: Dict) -> Dict:
        """
        🔧 JSON 오류 수정: payload 데이터 안전화 처리
        Discord API가 처리할 수 없는 문자나 구조를 정제
        """
        def clean_string(text):
            """문자열 안전화 처리"""
            if not isinstance(text, str):
                return text
            
            # null 문자 제거
            text = text.replace('\x00', '')
            
            # 제어 문자 제거 (탭, 개행 제외)
            text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
            
            # Discord 마크다운에 문제가 될 수 있는 문자 이스케이프
            text = text.replace('```', '\\`\\`\\`')
            
            # 과도한 연속 공백 정리
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        
        def clean_object(obj):
            """객체 재귀적 안전화 처리"""
            if isinstance(obj, dict):
                cleaned = {}
                for key, value in obj.items():
                    # null 키 처리
                    if key is None:
                        continue
                    cleaned_key = clean_string(str(key))
                    cleaned[cleaned_key] = clean_object(value)
                return cleaned
            elif isinstance(obj, list):
                return [clean_object(item) for item in obj if item is not None]
            elif isinstance(obj, str):
                return clean_string(obj)
            elif obj is None:
                return ""
            else:
                return obj
        
        try:
            # payload 전체 안전화
            sanitized = clean_object(payload)
            
            # Discord 임베드 길이 제한 확인
            if 'embeds' in sanitized:
                for embed in sanitized['embeds']:
                    if 'title' in embed and len(embed['title']) > NotificationConfig.MAX_EMBED_TITLE:
                        embed['title'] = embed['title'][:NotificationConfig.MAX_EMBED_TITLE-3] + "..."
                    
                    if 'description' in embed and len(embed['description']) > NotificationConfig.MAX_EMBED_DESCRIPTION:
                        embed['description'] = embed['description'][:NotificationConfig.MAX_EMBED_DESCRIPTION-3] + "..."
                    
                    if 'fields' in embed:
                        for field in embed['fields']:
                            if 'name' in field and len(field['name']) > NotificationConfig.MAX_EMBED_FIELD_NAME:
                                field['name'] = field['name'][:NotificationConfig.MAX_EMBED_FIELD_NAME-3] + "..."
                            
                            if 'value' in field and len(field['value']) > NotificationConfig.MAX_EMBED_FIELD_VALUE:
                                field['value'] = field['value'][:NotificationConfig.MAX_EMBED_FIELD_VALUE-3] + "..."
            
            # 전체 메시지 크기 확인 (Discord 한계: 6000자)
            payload_str = json.dumps(sanitized, ensure_ascii=False)
            if len(payload_str) > 5500:  # 여유분 둠
                logger.warning("페이로드 크기가 너무 큼, 간소화 처리")
                # embeds가 있다면 첫 번째만 유지
                if 'embeds' in sanitized and len(sanitized['embeds']) > 1:
                    sanitized['embeds'] = sanitized['embeds'][:1]
            
            return sanitized
            
        except Exception as e:
            logger.error(f"payload 안전화 처리 실패: {e}")
            # 최소한의 안전한 payload 반환
            return {
                "content": "Epic7 알림 - 메시지 처리 오류 발생",
                "embeds": []
            }
    
    def _send_discord_message(self, webhook_url: str, payload: Dict) -> bool:
        """
        Discord 메시지 전송 (JSON 오류 수정)
        🔧 수정: payload 안전화 처리 추가
        """
        try:
            headers = {'Content-Type': 'application/json'}
            
            # 🔧 핵심 수정: JSON 직렬화 전 payload 안전화
            sanitized_payload = self._sanitize_payload(payload)
            
            response = requests.post(
                webhook_url,
                data=json.dumps(sanitized_payload, ensure_ascii=False),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 204:
                return True
            elif response.status_code == 429:  # Rate limit
                retry_after = response.json().get('retry_after', 1)
                logger.warning(f"Discord Rate Limit: {retry_after}초 대기")
                time.sleep(retry_after)
                return False
            else:
                logger.error(f"Discord 전송 실패: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Discord 전송 타임아웃")
            return False
        except Exception as e:
            logger.error(f"Discord 전송 오류: {e}")
            return False
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """텍스트 길이 제한"""
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length-3] + "..."
    
    def _format_timestamp(self, timestamp_str: str = None) -> str:
        """타임스탬프 포맷팅"""
        try:
            if timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.now()
            
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # =============================================================================
    # 🚀 v3.4 핵심 추가: 게시글별 즉시 감성 알림
    # =============================================================================
    
    def send_sentiment_post_notification(self, post_data: Dict) -> bool:
        """🚀 v3.4: 개별 게시글 즉시 감성 알림 전송"""
        if not self.webhooks.get('sentiment'):
            logger.warning("감성 알림 웹훅이 설정되지 않았습니다.")
            return False
        
        # 속도 제한 체크
        if not NotificationStats.check_rate_limit('sentiment'):
            logger.warning("감성 알림 시간당 제한 도달")
            return False
        
        try:
            classification = post_data.get('classification', {})
            sentiment_analysis = classification.get('sentiment_analysis', {})
            sentiment = sentiment_analysis.get('sentiment', 'neutral')
            confidence = sentiment_analysis.get('confidence', 0.0)
            
            # 제목 및 내용 처리
            title = post_data.get('title', '제목 없음')
            content = post_data.get('content', '내용 없음')
            source = post_data.get('source', 'unknown')
            url = post_data.get('url', '')
            
            # 번역 처리 (영어 게시글인 경우)
            if not translation_system._is_korean_text(title):
                title = translation_system.translate_text(title, 100)
            
            if not translation_system._is_korean_text(content):
                content = translation_system.translate_text(content, 200)
            
            # 감성별 색상 및 이모지
            embed_color = NotificationConfig.SENTIMENT_COLORS.get(sentiment, NotificationConfig.COLORS['neutral'])
            sentiment_emoji = NotificationConfig.SENTIMENT_EMOJIS.get(sentiment, '😐')
            
            # 신뢰도 표시
            confidence_bar = "■" * int(confidence * 10) + "□" * (10 - int(confidence * 10))
            
            # 임베드 생성
            embed = {
                "title": f"{sentiment_emoji} {self._truncate_text(title, NotificationConfig.MAX_EMBED_TITLE)}",
                "description": self._truncate_text(content, 300),
                "color": embed_color,
                "url": url if url else None,
                "fields": [
                    {
                        "name": "📊 감성 분석",
                        "value": f"**{sentiment.upper()}** ({confidence*100:.1f}%)",
                        "inline": True
                    },
                    {
                        "name": "📍 출처",
                        "value": self._get_source_display_name(source),
                        "inline": True
                    },
                    {
                        "name": "🎯 신뢰도",
                        "value": f"`{confidence_bar}` {confidence*100:.1f}%",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"Epic7 실시간 감성 모니터링 v3.4 | {self._format_timestamp()}",
                    "icon_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # 페이로드 구성
            payload = {
                "username": "Epic7 감성 모니터",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "embeds": [embed]
            }
            
            # Discord 전송
            success = self._send_discord_message(self.webhooks['sentiment'], payload)
            
            if success:
                # 통계 업데이트
                NotificationStats.increment_stat('sentiment_immediate_notifications')
                
                # 일간 리포트용 데이터 저장
                save_sentiment_data_for_daily_report(post_data, classification)
                
                logger.info(f"📊 즉시 감성 알림 전송 성공: {title[:30]}... ({sentiment})")
                return True
            else:
                logger.error(f"📊 즉시 감성 알림 전송 실패: {title[:30]}...")
                NotificationStats.increment_stat('failed_notifications')
                return False
                
        except Exception as e:
            logger.error(f"즉시 감성 알림 생성 중 오류: {e}")
            NotificationStats.increment_stat('failed_notifications')
            return False
    
    def _get_source_display_name(self, source: str) -> str:
        """소스명 표시용 변환"""
        source_mapping = {
            'stove_korea_bug': '스토브 한국 버그게시판',
            'stove_global_bug': '스토브 글로벌 버그게시판', 
            'stove_korea_general': '스토브 한국 자유게시판',
            'stove_global_general': '스토브 글로벌 자유게시판',
            'reddit_epicseven': 'Reddit r/EpicSeven',
            'ruliweb_epic7': '루리웹 에픽세븐'
        }
        return source_mapping.get(source, source)
    
    # =============================================================================
    # 기존 알림 기능들 (완전 보존)
    # =============================================================================
    
    def send_bug_alert(self, bug_posts: List[Dict]) -> bool:
        """버그 알림 전송 (기존 기능 완전 보존)"""
        if not bug_posts:
            logger.info("전송할 버그 알림이 없습니다.")
            return True
        
        if not self.webhooks.get('bug'):
            logger.warning("버그 알림 웹훅이 설정되지 않았습니다.")
            return False
        
        # 속도 제한 체크
        if not NotificationStats.check_rate_limit('bug'):
            logger.warning("버그 알림 시간당 제한 도달")
            return False
        
        try:
            embeds = []
            
            for post in bug_posts[:NotificationConfig.MAX_EMBEDS_PER_MESSAGE]:
                classification = post.get('classification', {})
                bug_analysis = classification.get('bug_analysis', {})
                priority = bug_analysis.get('priority', 'low')
                
                # 제목 및 내용 처리
                title = post.get('title', '제목 없음')
                content = post.get('content', '내용 없음')
                
                # 번역 처리
                if not translation_system._is_korean_text(title):
                    title = translation_system.translate_text(title)
                
                if not translation_system._is_korean_text(content):
                    content = translation_system.translate_text(content)
                
                # 우선순위별 이모지
                priority_emoji = {
                    'critical': '🚨',
                    'high': '⚠️',
                    'medium': '🔸',
                    'low': '🔹'
                }.get(priority, '🔹')
                
                embed = {
                    "title": f"{priority_emoji} {self._truncate_text(title, NotificationConfig.MAX_EMBED_TITLE)}",
                    "description": self._truncate_text(content, 500),
                    "color": NotificationConfig.COLORS['bug'],
                    "url": post.get('url', ''),
                    "fields": [
                        {
                            "name": "🎯 우선순위",
                            "value": f"**{priority.upper()}**",
                            "inline": True
                        },
                        {
                            "name": "📍 출처",
                            "value": self._get_source_display_name(post.get('source', 'unknown')),
                            "inline": True
                        },
                        {
                            "name": "⏰ 발견 시간",
                            "value": self._format_timestamp(post.get('timestamp')),
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": f"Epic7 버그 모니터링 시스템 v3.4 | 즉시 알림",
                        "icon_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                embeds.append(embed)
            
            # 페이로드 구성
            payload = {
                "username": "Epic7 버그 알림봇",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "content": f"🚨 **긴급 버그 알림** - {len(bug_posts)}개 발견",
                "embeds": embeds
            }
            
            # Discord 전송
            success = self._send_discord_message(self.webhooks['bug'], payload)
            
            if success:
                NotificationStats.increment_stat('bug_notifications')
                logger.info(f"🚨 버그 알림 전송 성공: {len(bug_posts)}개")
                return True
            else:
                NotificationStats.increment_stat('failed_notifications')
                return False
                
        except Exception as e:
            logger.error(f"버그 알림 생성 중 오류: {e}")
            NotificationStats.increment_stat('failed_notifications')
            return False
    
    def send_sentiment_notification(self, sentiment_posts: List[Dict], sentiment_summary: Dict) -> bool:
        """감성 동향 알림 전송 (기존 일괄 처리 방식 완전 보존)"""
        if not sentiment_posts:
            logger.info("전송할 감성 동향 알림이 없습니다.")
            return True
        
        if not self.webhooks.get('sentiment'):
            logger.warning("감성 알림 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            # 감성별 게시글 분류
            sentiment_groups = {'positive': [], 'negative': [], 'neutral': []}
            
            for post in sentiment_posts:
                classification = post.get('classification', {})
                sentiment = classification.get('sentiment_analysis', {}).get('sentiment', 'neutral')
                
                if sentiment in sentiment_groups:
                    sentiment_groups[sentiment].append(post)
            
            # 메인 임베드 (요약)
            total_posts = len(sentiment_posts)
            positive_count = len(sentiment_groups['positive'])
            negative_count = len(sentiment_groups['negative'])
            neutral_count = len(sentiment_groups['neutral'])
            
            # 전체적인 감성 경향 결정
            if positive_count > negative_count and positive_count > neutral_count:
                main_color = NotificationConfig.COLORS['positive']
                trend_emoji = "📈"
                trend_text = "긍정적"
            elif negative_count > positive_count and negative_count > neutral_count:
                main_color = NotificationConfig.COLORS['negative']
                trend_emoji = "📉"
                trend_text = "부정적"
            else:
                main_color = NotificationConfig.COLORS['neutral']
                trend_emoji = "📊"
                trend_text = "중립적"
            
            main_embed = {
                "title": f"{trend_emoji} Epic7 유저 감성 동향",
                "description": f"**전체적으로 {trend_text}인 반응**을 보이고 있습니다.",
                "color": main_color,
                "fields": [
                    {
                        "name": "📊 감성 분포",
                        "value": f"😊 긍정: **{positive_count}개** ({positive_count/total_posts*100:.1f}%)\n"
                                f"😞 부정: **{negative_count}개** ({negative_count/total_posts*100:.1f}%)\n"
                                f"😐 중립: **{neutral_count}개** ({neutral_count/total_posts*100:.1f}%)",
                        "inline": True
                    },
                    {
                        "name": "📈 총 분석 게시글",
                        "value": f"**{total_posts}개**",
                        "inline": True
                    },
                    {
                        "name": "⏱️ 분석 기간",
                        "value": sentiment_summary.get('time_period', '최근 30분간'),
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"Epic7 감성 분석 시스템 v3.4 | 누적 분석",
                    "icon_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            embeds = [main_embed]
            
            # 감성별 상세 임베드 (샘플 게시글)
            for sentiment, posts in sentiment_groups.items():
                if not posts:
                    continue
                
                color = NotificationConfig.SENTIMENT_COLORS[sentiment]
                emoji = NotificationConfig.SENTIMENT_EMOJIS[sentiment]
                
                # 상위 3개 게시글만 표시
                sample_posts = posts[:3]
                
                field_value = ""
                for i, post in enumerate(sample_posts, 1):
                    title = post.get('title', '제목 없음')
                    url = post.get('url', '')
                    
                    # 번역 처리
                    if not translation_system._is_korean_text(title):
                        title = translation_system.translate_text(title, 50)
                    
                    if url:
                        field_value += f"{i}. [{title[:50]}...]({url})\n"
                    else:
                        field_value += f"{i}. {title[:50]}...\n"
                
                if len(posts) > 3:
                    field_value += f"... 외 {len(posts)-3}개 더"
                
                sentiment_embed = {
                    "title": f"{emoji} {sentiment.capitalize()} 반응 ({len(posts)}개)",
                    "color": color,
                    "fields": [
                        {
                            "name": "주요 게시글",
                            "value": field_value or "게시글이 없습니다.",
                            "inline": False
                        }
                    ]
                }
                
                embeds.append(sentiment_embed)
            
            # 페이로드 구성
            payload = {
                "username": "Epic7 감성 분석봇",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "embeds": embeds[:NotificationConfig.MAX_EMBEDS_PER_MESSAGE]
            }
            
            # Discord 전송
            success = self._send_discord_message(self.webhooks['sentiment'], payload)
            
            if success:
                NotificationStats.increment_stat('sentiment_notifications')
                logger.info(f"📊 감성 동향 알림 전송 성공: {total_posts}개 분석")
                return True
            else:
                NotificationStats.increment_stat('failed_notifications')
                return False
                
        except Exception as e:
            logger.error(f"감성 동향 알림 생성 중 오류: {e}")
            NotificationStats.increment_stat('failed_notifications')
            return False
    
    def send_daily_report(self, report_data: Dict) -> bool:
        """일간 리포트 전송 (기존 기능 완전 보존)"""
        if not self.webhooks.get('report'):
            logger.warning("리포트 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            # 리포트 데이터 추출
            date = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            total_posts = report_data.get('total_posts', 0)
            bug_posts = report_data.get('bug_posts', 0)
            sentiment_summary = report_data.get('sentiment_summary', {})
            top_keywords = report_data.get('top_keywords', [])
            
            # 메인 임베드
            main_embed = {
                "title": f"📈 Epic7 일간 동향 리포트",
                "description": f"**{date}** 24시간 종합 분석 결과",
                "color": NotificationConfig.COLORS['report'],
                "fields": [
                    {
                        "name": "📊 전체 현황",
                        "value": f"총 게시글: **{total_posts:,}개**\n"
                                f"버그 리포트: **{bug_posts}개**\n"
                                f"감성 분석: **{total_posts - bug_posts}개**",
                        "inline": True
                    },
                    {
                        "name": "😊 감성 분포",
                        "value": f"긍정: **{sentiment_summary.get('positive', 0)}개**\n"
                                f"부정: **{sentiment_summary.get('negative', 0)}개**\n"
                                f"중립: **{sentiment_summary.get('neutral', 0)}개**",
                        "inline": True
                    },
                    {
                        "name": "🔥 인기 키워드",
                        "value": "\n".join([f"• {keyword}" for keyword in top_keywords[:5]]) or "데이터 없음",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Epic7 일간 리포트 시스템 v3.4 | 매일 오전 9시 발송",
                    "icon_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # 페이로드 구성
            payload = {
                "username": "Epic7 리포트봇",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "embeds": [main_embed]
            }
            
            # Discord 전송
            success = self._send_discord_message(self.webhooks['report'], payload)
            
            if success:
                NotificationStats.increment_stat('daily_reports')
                logger.info(f"📈 일간 리포트 전송 성공: {date}")
                return True
            else:
                NotificationStats.increment_stat('failed_notifications')
                return False
                
        except Exception as e:
            logger.error(f"일간 리포트 생성 중 오류: {e}")
            NotificationStats.increment_stat('failed_notifications')
            return False
    
    def send_health_check(self, health_data: Dict) -> bool:
        """헬스체크 알림 전송 (기존 기능 완전 보존)"""
        if not self.webhooks.get('health'):
            logger.warning("헬스체크 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            # 시스템 상태 확인
            system_status = health_data.get('status', 'unknown')
            uptime = health_data.get('uptime', '알 수 없음')
            memory_usage = health_data.get('memory_usage', 0)
            cpu_usage = health_data.get('cpu_usage', 0)
            
            # 상태별 색상 및 이모지
            if system_status == 'healthy':
                color = NotificationConfig.COLORS['positive']
                status_emoji = "✅"
                status_text = "정상"
            elif system_status == 'warning':
                color = NotificationConfig.COLORS['negative']
                status_emoji = "⚠️"
                status_text = "주의"
            else:
                color = NotificationConfig.COLORS['health']
                status_emoji = "❓"
                status_text = "알 수 없음"
            
            embed = {
                "title": f"{status_emoji} Epic7 시스템 헬스체크",
                "description": f"시스템 상태: **{status_text}**",
                "color": color,
                "fields": [
                    {
                        "name": "🖥️ 시스템 리소스",
                        "value": f"메모리 사용량: **{memory_usage:.1f}%**\n"
                                f"CPU 사용량: **{cpu_usage:.1f}%**",
                        "inline": True
                    },
                    {
                        "name": "⏱️ 가동 시간",
                        "value": f"**{uptime}**",
                        "inline": True
                    },
                    {
                        "name": "📊 모니터링 통계",
                        "value": f"총 알림: **{self.stats.get('total_notifications', 0)}개**\n"
                                f"실패: **{self.stats.get('failed_notifications', 0)}개**",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"Epic7 헬스체크 시스템 v3.4 | 6시간마다 점검",
                    "icon_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            payload = {
                "username": "Epic7 헬스체크봇",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "embeds": [embed]
            }
            
            # Discord 전송
            success = self._send_discord_message(self.webhooks['health'], payload)
            
            if success:
                NotificationStats.increment_stat('health_checks')
                logger.info(f"🏥 헬스체크 알림 전송 성공")
                return True
            else:
                NotificationStats.increment_stat('failed_notifications')
                return False
                
        except Exception as e:
            logger.error(f"헬스체크 알림 생성 중 오류: {e}")
            NotificationStats.increment_stat('failed_notifications')
            return False

# =============================================================================
# 편의 함수들 (외부 모듈에서 쉽게 사용할 수 있도록)
# =============================================================================

def send_bug_alert(bug_posts: List[Dict]) -> bool:
    """버그 알림 전송 편의 함수"""
    notifier = Epic7Notifier()
    return notifier.send_bug_alert(bug_posts)

def send_sentiment_notification(sentiment_posts: List[Dict], sentiment_summary: Dict) -> bool:
    """감성 동향 알림 전송 편의 함수 (기존 일괄 방식)"""
    notifier = Epic7Notifier()
    return notifier.send_sentiment_notification(sentiment_posts, sentiment_summary)

def send_sentiment_post_notification(post_data: Dict) -> bool:
    """🚀 v3.4: 개별 게시글 즉시 감성 알림 전송 편의 함수"""
    notifier = Epic7Notifier()
    return notifier.send_sentiment_post_notification(post_data)

def send_daily_report(report_data: Dict) -> bool:
    """일간 리포트 전송 편의 함수"""
    notifier = Epic7Notifier()
    return notifier.send_daily_report(report_data)

def send_health_check(health_data: Dict) -> bool:
    """헬스체크 알림 전송 편의 함수"""
    notifier = Epic7Notifier()
    return notifier.send_health_check(health_data)

# =============================================================================
# 시스템 정보 함수들
# =============================================================================

def get_system_health() -> Dict:
    """시스템 상태 정보 수집"""
    try:
        # CPU 및 메모리 사용량
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # 가동 시간 계산
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_str = f"{uptime.days}일 {uptime.seconds//3600}시간 {(uptime.seconds//60)%60}분"
        
        # 상태 판정
        if memory_usage > 90 or cpu_usage > 90:
            status = 'warning'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'uptime': uptime_str,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"시스템 상태 수집 실패: {e}")
        return {
            'status': 'unknown',
            'cpu_usage': 0,
            'memory_usage': 0,
            'uptime': '알 수 없음',
            'timestamp': datetime.now().isoformat()
        }

def get_notification_stats() -> Dict:
    """알림 통계 조회"""
    return NotificationStats.load_stats()

def reset_notification_stats():
    """알림 통계 리셋"""
    empty_stats = NotificationStats._get_empty_stats()
    NotificationStats.save_stats(empty_stats)
    logger.info("알림 통계가 리셋되었습니다.")

# =============================================================================
# 메인 실행 부분 (테스트용)
# =============================================================================

if __name__ == "__main__":
    # 테스트 실행
    logger.info("Epic7 알림 시스템 v3.4 테스트 시작 (JSON 오류 수정)")
    
    # 테스트 데이터 (문제가 될 수 있는 문자 포함)
    test_post = {
        'title': '피시 클라이언트 접속이 안 돼요... (특수문자: ★♥♦♣)',
        'content': 'still no sexflan nerf meanwhile... 테스트\x00내용\n\n\t특수문자```포함',
        'url': 'https://example.com/test',
        'source': 'test_source',
        'classification': {
            'sentiment_analysis': {
                'sentiment': 'negative',
                'confidence': 0.85
            },
            'category': 'general'
        },
        'timestamp': datetime.now().isoformat()
    }
    
    # 즉시 감성 알림 테스트
    logger.info("🚀 즉시 감성 알림 테스트 시작 (JSON 안전화 적용)")
    success = send_sentiment_post_notification(test_post)
    logger.info(f"즉시 감성 알림 테스트 결과: {'성공' if success else '실패'}")
    
    # 시스템 상태 테스트
    logger.info("🏥 시스템 헬스체크 테스트 시작")
    health_data = get_system_health()
    success = send_health_check(health_data)
    logger.info(f"헬스체크 테스트 결과: {'성공' if success else '실패'}")
    
    # 통계 조회 테스트
    stats = get_notification_stats()
    logger.info(f"📊 현재 알림 통계: {stats}")
    
    logger.info("🔧 Epic7 알림 시스템 v3.4 테스트 완료 (JSON 오류 수정)")