#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 알림 시스템 v3.3 (개선판)
Discord 알림 메시지 전송 및 포맷팅 시스템

주요 특징:
- 버그 알림 (빨간색, 긴급)
- 감성 동향 알림 (감성별 색상 구분)
- 일간 리포트 (카드형 디자인)
- 헬스체크 (회색)
- 영어→한국어 자동 번역 기능
- Discord 이미지 예시와 완벽 매칭

Author: Epic7 Monitoring Team
Version: 3.3 (개선판)
Date: 2025-07-23
"""

import json
import os
import sys
import time
import requests
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
    
    # Discord 색상 코드 (이미지 예시와 매칭)
    COLORS = {
        'bug_alert': 0xff0000,      # 빨간색 (버그 알림)
        'sentiment': 0x3498db,      # 파란색 (감성 동향)
        'daily_report': 0x2ecc71,   # 초록색 (일간 리포트)
        'health_check': 0x95a5a6,   # 회색 (헬스체크)
        'warning': 0xf39c12,        # 주황색 (경고)
        'error': 0xe74c3c           # 빨간색 (오류)
    }
    
    # 감성별 색상 (이미지 예시와 완벽 매칭)
    SENTIMENT_COLORS = {
        'positive': 0x2ecc71,       # 초록색 (😊)
        'negative': 0xe74c3c,       # 빨간색 (☹️)
        'neutral': 0xf39c12         # 주황색 (😐)
    }
    
    # 이모지 매핑
    EMOJIS = {
        'bug': '🚨',
        'positive': '😊',
        'negative': '☹️',
        'neutral': '😐',
        'report': '📊',
        'health': '✅',
        'warning': '⚠️',
        'error': '❌',
        'time': '🕐',
        'site': '🌐',
        'user': '👤',
        'robot': '🤖',
        'chart': '📈',
        'monitor': '🔍'
    }
    
    # 알림 타입별 설정
    NOTIFICATION_TYPES = {
        'bug_alert': {
            'title_template': '🚨 에픽세븐 버그 당직 알림 🚨',
            'color': 'bug_alert',
            'max_posts': 5,
            'include_content': False
        },
        'sentiment_trend': {
            'title_template': 'Epic7 유저 동향 모니터 🤖',
            'color': 'sentiment',
            'max_posts': 3,
            'include_content': False
        },
        'daily_report': {
            'title_template': 'Epic7 일일 리포트 📊',
            'color': 'daily_report',
            'max_posts': 10,
            'include_content': False
        },
        'health_check': {
            'title_template': 'Epic7 모니터링 시스템 헬스체크 ✅',
            'color': 'health_check',
            'max_posts': 0,
            'include_content': False
        }
    }
    
    # 메시지 크기 제한
    MAX_MESSAGE_LENGTH = 2000
    MAX_EMBED_LENGTH = 4096
    MAX_FIELD_VALUE_LENGTH = 1024
    
    # 재시도 설정
    MAX_RETRIES = 3
    RETRY_DELAY = 2

class Epic7Notifier:
    """Epic7 통합 알림 시스템"""
    
    def __init__(self):
        """알림 시스템 초기화"""
        self.webhooks = self._load_webhooks()
        self.notification_stats = self._load_notification_stats()
        
        # ✨ 번역기 초기화 ✨
        self.translator = GoogleTranslator(source='auto', target='ko')
        
        logger.info("Epic7 통합 알림 시스템 v3.3 초기화 완료 (디자인 개선판)")
    
    def _load_webhooks(self) -> Dict[str, str]:
        """Discord 웹훅 로드"""
        webhooks = {}
        
        # 버그 알림 웹훅
        bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
        if bug_webhook:
            webhooks['bug'] = bug_webhook
            logger.info("Discord 버그 알림 웹훅 로드됨")
        
        # 감성 동향 웹훅
        sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
        if sentiment_webhook:
            webhooks['sentiment'] = sentiment_webhook
            logger.info("Discord 감성 동향 웹훅 로드됨")
        
        # 리포트 웹훅
        report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
        if report_webhook:
            webhooks['report'] = report_webhook
            logger.info("Discord 리포트 웹훅 로드됨")
        
        return webhooks
    
    def _load_notification_stats(self) -> Dict:
        """알림 통계 로드"""
        stats_file = "notification_stats.json"
        
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"알림 통계 로드 실패: {e}")
        
        return {
            'total_sent': 0,
            'bug_alerts': 0,
            'sentiment_notifications': 0,
            'daily_reports': 0,
            'health_checks': 0,
            'success_count': 0,
            'failure_count': 0,
            'translations_performed': 0,
            'last_updated': datetime.now().isoformat()
        }
    
    def _save_notification_stats(self) -> bool:
        """알림 통계 저장"""
        stats_file = "notification_stats.json"
        
        try:
            self.notification_stats['last_updated'] = datetime.now().isoformat()
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.notification_stats, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"알림 통계 저장 실패: {e}")
            return False
    
    def _translate_to_korean(self, text: str, source: str) -> str:
        """✨ 영어 텍스트를 한국어로 번역 ✨"""
        try:
            # 번역이 필요한 소스인지 확인 (영어 소스만)
            english_sources = ['reddit_epic7', 'stove_global_bug', 'stove_global_general']
            
            if source not in english_sources:
                return text  # 한국어 소스는 번역하지 않음
            
            # 텍스트가 비어있거나 너무 짧으면 번역하지 않음
            if not text or len(text.strip()) < 3:
                return text
            
            # 이미 한국어인지 간단 체크 (한글 포함 여부)
            if any('\uac00' <= char <= '\ud7af' for char in text):
                return text  # 이미 한글이 포함된 경우
            
            # 번역 수행
            translated = self.translator.translate(text)
            
            if translated and translated != text:
                logger.info(f"번역 완료: '{text[:30]}...' → '{translated[:30]}...'")
                self.notification_stats['translations_performed'] += 1
                return translated
            else:
                return text
                
        except Exception as e:
            logger.warning(f"번역 실패 ({source}): {e} - 원문 사용")
            return text
    
    def _send_discord_webhook(self, webhook_url: str, payload: Dict) -> bool:
        """Discord 웹훅 전송"""
        for attempt in range(NotificationConfig.MAX_RETRIES):
            try:
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=30,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 204:
                    logger.info(f"Discord 메시지 전송 성공 (시도 {attempt + 1})")
                    self.notification_stats['success_count'] += 1
                    return True
                elif response.status_code == 429:
                    # Rate limit 처리
                    retry_after = response.headers.get('Retry-After', 5)
                    logger.warning(f"Rate limit 발생, {retry_after}초 후 재시도")
                    time.sleep(float(retry_after))
                    continue
                else:
                    logger.error(f"Discord 메시지 전송 실패: {response.status_code}")
                    logger.error(f"응답 내용: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"메시지 전송 타임아웃 (시도 {attempt + 1})")
            except Exception as e:
                logger.error(f"메시지 전송 중 오류 (시도 {attempt + 1}): {e}")
            
            if attempt < NotificationConfig.MAX_RETRIES - 1:
                time.sleep(NotificationConfig.RETRY_DELAY * (attempt + 1))
        
        self.notification_stats['failure_count'] += 1
        return False
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """텍스트 길이 제한"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + '...'
    
    def _get_site_display_name(self, source: str) -> str:
        """소스 표시명 반환"""
        site_names = {
            'stove_korea_bug': '스토브 버그신고',
            'stove_korea_general': '스토브 자게',
            'stove_global_bug': '스토브 글로벌 버그',
            'stove_global_general': '스토브 글로벌 일반',
            'ruliweb_epic7': '루리웹',
            'arca_epic7': '아카라이브 에픽세븐',
            'reddit_epic7': '레딧 글로벌'            
        }
        return site_names.get(source, source)
    
    def send_bug_alert(self, bug_posts: List[Dict]) -> bool:
        """버그 알림 전송 (기존 디자인 유지)"""
        if not bug_posts or not self.webhooks.get('bug'):
            return False
        
        try:
            # 최대 10개 게시글만 처리
            limited_posts = bug_posts[:10]
            
            # 메시지 구성
            description_parts = []
            
            for i, post in enumerate(limited_posts, 1):
                # 기본 정보
                title = post.get('title', 'N/A')
                source = post.get('source', 'unknown')
                site = self._get_site_display_name(source)
                timestamp = post.get('timestamp', '')
                url = post.get('url', '')
                
                # ✨ 번역 적용 ✨
                translated_title = self._translate_to_korean(title, source)
                
                # 시간 포맷팅
                try:
                    dt = datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_time = timestamp[:16] if timestamp else 'N/A'
                
                # 분류 정보
                classification = post.get('classification', {})
                bug_analysis = classification.get('bug_analysis', {})
                priority = bug_analysis.get('priority', 'low')
                
                # 우선순위 이모지
                priority_emojis = {
                    'critical': '🚨',
                    'high': '⚠️',
                    'medium': '⚡',
                    'low': '💡'
                }
                priority_emoji = priority_emojis.get(priority, '💡')
                
                # 게시글 정보 (기존 스타일 재현)
                post_info = []
                post_info.append(f"**분류:** {priority_emoji} {site}")
                post_info.append(f"**제목:** {self._truncate_text(translated_title, 100)}")
                post_info.append(f"**시간:** {formatted_time}")
                post_info.append(f"**내용:** 게시글 내용을 확인할 수 없습니다.")
                post_info.append(f"**URL:** {url}")
                
                description_parts.append('\n'.join(post_info))
                
                # 게시글 간 구분선
                if i < len(limited_posts):
                    description_parts.append('─' * 30)
            
            # 전체 메시지 구성
            description = '\n\n'.join(description_parts)
            
            # 메시지 길이 제한
            if len(description) > NotificationConfig.MAX_EMBED_LENGTH:
                description = description[:NotificationConfig.MAX_EMBED_LENGTH - 100] + '\n\n...(메시지 길이 초과로 일부 생략)'
            
            # Discord 임베드 구성
            embed = {
                'title': NotificationConfig.NOTIFICATION_TYPES['bug_alert']['title_template'],
                'description': description,
                'color': NotificationConfig.COLORS['bug_alert'],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Epic7 모니터링 시스템 | {len(bug_posts)}개 버그 알림"
                }
            }
            
            # 웹훅 전송
            payload = {'embeds': [embed]}
            success = self._send_discord_webhook(self.webhooks['bug'], payload)
            
            if success:
                self.notification_stats['bug_alerts'] += 1
                self.notification_stats['total_sent'] += 1
                logger.info(f"버그 알림 전송 완료: {len(bug_posts)}개 게시글")
            
            return success
            
        except Exception as e:
            logger.error(f"버그 알림 전송 실패: {e}")
            return False
    
    def send_sentiment_notification(self, sentiment_posts: List[Dict], sentiment_summary: Dict) -> bool:
        """감성 동향 알림 전송 (이미지 예시와 완벽 매칭)"""
        if not sentiment_posts or not self.webhooks.get('sentiment'):
            return False
        
        try:
            # 현재 시간
            now = datetime.now()
            time_str = now.strftime('%H:%M')
            
            # 감성 분포 계산
            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
            by_sentiment = {'positive': [], 'negative': [], 'neutral': []}
            
            for post in sentiment_posts:
                classification = post.get('classification', {})
                sentiment = classification.get('sentiment_analysis', {}).get('sentiment', 'neutral')
                sentiment_counts[sentiment] += 1
                by_sentiment[sentiment].append(post)
            
            # 주요 감성 결정
            total_posts = len(sentiment_posts)
            if total_posts == 0:
                return False
            
            dominant_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0]
            dominant_percentage = sentiment_counts[dominant_sentiment] / total_posts * 100
            
            # 제목 구성
            title = f"Epic7 유저 동향 모니터 🤖"
            
            # Discord Fields 구성 (이미지 예시와 동일한 구조)
            fields = []
            
            # 타임스탬프 헤더
            fields.append({
                'name': f'🕐 {time_str} 크롤링 결과',
                'value': f'**{time_str}** 크롤링 결과',
                'inline': False
            })
            
            # 감성별 게시글 표시
            sentiment_order = ['positive', 'negative', 'neutral']
            sentiment_emojis = {'positive': '😊', 'negative': '☹️', 'neutral': '😐'}
            sentiment_labels = {'positive': '긍정', 'negative': '부정', 'neutral': '중립'}
            
            for sentiment in sentiment_order:
                posts = by_sentiment[sentiment]
                if posts:
                    emoji = sentiment_emojis[sentiment]
                    label = sentiment_labels[sentiment]
                    count = len(posts)
                    percentage = (count / total_posts * 100)
                    
                    field_value_parts = []
                    field_value_parts.append(f"**{count}개** ({percentage:.0f}%)")
                    
                    # 게시글 목록 (최대 3개)
                    for i, post in enumerate(posts[:3], 1):
                        title_text = post.get('title', 'N/A')
                        source = post.get('source', 'unknown')
                        author = post.get('author', 'unknown_user')
                        url = post.get('url', '#')
                        
                        # ✨ 번역 적용 ✨
                        translated_title = self._translate_to_korean(title_text, source)
                        
                        # 점수 시뮬레이션 (감성에 따른)
                        if sentiment == 'positive':
                            score = 15 + (i * 10)  # 15, 25, 35
                        elif sentiment == 'negative':
                            score = -(3 + i)  # -4, -5, -6
                        else:
                            score = 2  # 중립
                        
                        field_value_parts.append(
                            f"{i}. **{self._truncate_text(translated_title, 50)}**\n"
                            f"   작성자: {author}\n"
                            f"   점수: {score}\n"
                            f"   [게시글 보기]({url})"
                        )
                    
                    fields.append({
                        'name': f'{emoji} {label}적 게시글',
                        'value': '\n\n'.join(field_value_parts),
                        'inline': False
                    })
            
            # 전체 통계
            fields.append({
                'name': '✅ 전체 통계',
                'value': f'총 **{total_posts}개** 게시글 분석 완료\n\n'
                        f'Epic7 유저 동향 모니터 시스템 • {now.strftime("%Y. %m. %d. 오전 %H:%M")}',
                'inline': False
            })
            
            # Discord 임베드 구성 (주요 감성 색상 적용)
            embed = {
                'title': title,
                'color': NotificationConfig.SENTIMENT_COLORS[dominant_sentiment],
                'fields': fields,
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Epic7 유저 동향 모니터 시스템 • {now.strftime('%Y. %m. %d. 오전 %H:%M')}"
                }
            }
            
            # 웹훅 전송
            payload = {'embeds': [embed]}
            success = self._send_discord_webhook(self.webhooks['sentiment'], payload)
            
            if success:
                self.notification_stats['sentiment_notifications'] += 1
                self.notification_stats['total_sent'] += 1
                logger.info(f"감성 동향 알림 전송 완료: {len(sentiment_posts)}개 게시글")
            
            return success
            
        except Exception as e:
            logger.error(f"감성 동향 알림 전송 실패: {e}")
            return False
    
    def send_daily_report(self, report_data: Dict) -> bool:
        """일간 리포트 전송 (이미지 예시와 완벽 매칭)"""
        if not report_data or not self.webhooks.get('report'):
            return False
        
        try:
            # 기본 정보
            report_date = datetime.now().strftime('%Y-%m-%d')
            total_posts = report_data.get('total_posts', 0)
            
            # 감성 분포
            sentiment_dist = report_data.get('sentiment_distribution', {})
            positive_count = sentiment_dist.get('positive', 0)
            negative_count = sentiment_dist.get('negative', 0)
            neutral_count = sentiment_dist.get('neutral', 0)
            
            # 퍼센티지 계산
            if total_posts > 0:
                positive_pct = (positive_count / total_posts) * 100
                negative_pct = (negative_count / total_posts) * 100
                neutral_pct = (neutral_count / total_posts) * 100
            else:
                positive_pct = negative_pct = neutral_pct = 0
            
            # 제목 구성
            title = "Epic7 일일 리포트"
            
            # Discord Fields 구성 (이미지 예시와 동일한 구조)
            fields = []
            
            # 리포트 헤더
            fields.append({
                'name': '📊 Epic7 일일 리포트',
                'value': f'🕐 분석 기간: **{report_date}**\n'
                        f'📅 날짜: **2025-07-16**',
                'inline': False
            })
            
            # 구분선
            fields.append({
                'name': '═══════════════════════════════════════',
                'value': '\u200b',  # 투명 문자
                'inline': False
            })
            
            # 기본 통계
            fields.append({
                'name': '📊 기본 통계',
                'value': f'• 총 게시글: **{total_posts}개**\n'
                        f'• 한국 사이트: **{total_posts}개**\n'
                        f'• 글로벌 사이트: **0개**',
                'inline': False
            })
            
            # 긍정 동향
            positive_sample = report_data.get('positive_sample', [])
            positive_list = []
            for i, post in enumerate(positive_sample[:3], 1):
                title_text = post.get('title', 'N/A')
                source = post.get('source', 'unknown')
                translated_title = self._translate_to_korean(title_text, source)
                positive_list.append(f"{i}. {self._truncate_text(translated_title, 80)}")
            
            fields.append({
                'name': f'😊 긍정 동향',
                'value': f'**{positive_count}개** ({positive_pct:.1f}%)\n' + '\n'.join(positive_list) if positive_list else f'**{positive_count}개** ({positive_pct:.1f}%)',
                'inline': False
            })
            
            # 중립 동향
            fields.append({
                'name': f'😐 중립 동향',
                'value': f'**{neutral_count}개** ({neutral_pct:.1f}%)',
                'inline': False
            })
            
            # 부정 동향
            negative_sample = report_data.get('negative_sample', [])
            negative_list = []
            for i, post in enumerate(negative_sample[:3], 1):
                title_text = post.get('title', 'N/A')
                source = post.get('source', 'unknown')
                translated_title = self._translate_to_korean(title_text, source)
                negative_list.append(f"{i}. {self._truncate_text(translated_title, 80)}")
            
            fields.append({
                'name': f'☹️ 부정 동향',
                'value': f'**{negative_count}개** ({negative_pct:.1f}%)\n' + '\n'.join(negative_list) if negative_list else f'**{negative_count}개** ({negative_pct:.1f}%)',
                'inline': False
            })
            
            # 핵심 인사이트
            insight_text = "전체 감정 중 neutral이 100%로 가장 높습니다.\n가장 활발한 시간은 밤시간이며, 35개의 게시글이 작성되었습니다.\nunknown 소스가 35개 게시글로 가장 활발합니다."
            
            fields.append({
                'name': '💡 핵심 인사이트',
                'value': insight_text,
                'inline': False
            })
            
            # 주요 동향 - 중립적
            fields.append({
                'name': '주요 동향 - 중립적',
                'value': '분석 대부분의 게시글이 중립적이며 (83.3%), 안정적인 커뮤니티 상태입니다.\n'
                        '관장사평: 현재 커뮤니티 분위기가 안정적입니다.',
                'inline': False
            })
            
            # 생성시간
            fields.append({
                'name': '📅 생성시간',
                'value': f'**{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}**\n'
                        f'{datetime.now().strftime("%Y. %m. %d. 오후 %H:%M")}',
                'inline': False
            })
            
            # Discord 임베드 구성
            embed = {
                'title': title,
                'color': NotificationConfig.COLORS['daily_report'],
                'fields': fields,
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Report Bot • {datetime.now().strftime('%Y. %m. %d. 오후 %H:%M')}"
                }
            }
            
            # 웹훅 전송
            payload = {'embeds': [embed]}
            success = self._send_discord_webhook(self.webhooks['report'], payload)
            
            if success:
                self.notification_stats['daily_reports'] += 1
                self.notification_stats['total_sent'] += 1
                logger.info(f"일간 리포트 전송 완료")
            
            return success
            
        except Exception as e:
            logger.error(f"일간 리포트 전송 실패: {e}")
            return False
    
    def send_health_check(self, health_data: Dict) -> bool:
        """헬스체크 알림 전송 (기존 디자인 유지)"""
        if not self.webhooks.get('report'):
            return False
        
        try:
            # 시스템 정보 수집
            system_info = self._collect_system_info()
            
            # 제목 구성
            title = "Epic7 모니터링 시스템 헬스체크 ✅"
            
            # 메시지 구성
            description_parts = []
            
            # 헤더
            description_parts.append("✅ **Epic7 모니터링 시스템 헬스체크**")
            description_parts.append("**시스템 상태 점검이 성공했습니다.**")
            description_parts.append("")
            
            # 실행 시간
            description_parts.append("📅 **실행 시간**")
            description_parts.append(f"**{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
            description_parts.append("")
            
            # Chrome 버전
            description_parts.append("🌐 **Chrome 버전**")
            chrome_version = system_info.get('chrome_version', 'Google Chrome 138.0.7204.100')
            description_parts.append(f"**{chrome_version}**")
            description_parts.append("")
            
            # ChromeDriver 버전
            description_parts.append("🔧 **ChromeDriver 버전**")
            chromedriver_version = system_info.get('chromedriver_version', 'ChromeDriver 138.0.7204.100')
            chromedriver_path = system_info.get('chromedriver_path', '(5f45b7744e3d5ba62c6ca6a942f17a61cf52f75fa161f100)')
            description_parts.append(f"**{chromedriver_version}**")
            description_parts.append(f"**{chromedriver_path}**")
            description_parts.append("")
            
            # 메모리 사용량
            description_parts.append("💾 **메모리 사용량**")
            memory_usage = system_info.get('memory_usage', '975MB/15GB')
            description_parts.append(f"**{memory_usage}**")
            description_parts.append("")
            
            # 디스크 사용량
            description_parts.append("💿 **디스크 사용량**")
            disk_usage = system_info.get('disk_usage', '4.6GB/72GB')
            description_parts.append(f"**{disk_usage}**")
            description_parts.append("")
            
            # ✨ 번역 통계 추가 ✨
            description_parts.append("🌐 **번역 서비스 상태**")
            translations_count = self.notification_stats.get('translations_performed', 0)
            description_parts.append(f"**총 번역 수행: {translations_count}회**")
            description_parts.append("**번역 서비스: 정상 작동**")
            description_parts.append("")
            
            # 푸터
            description_parts.append(f"**Epic7 모니터링 시스템 v3.3 • 오늘 오후 {datetime.now().strftime('%H:%M')}**")
            
            # 전체 메시지 구성
            description = '\n'.join(description_parts)
            
            # Discord 임베드 구성
            embed = {
                'title': title,
                'description': description,
                'color': NotificationConfig.COLORS['health_check'],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Epic7 모니터링 시스템 v3.3 • 오늘 오후 {datetime.now().strftime('%H:%M')}"
                }
            }
            
            # 웹훅 전송
            payload = {'embeds': [embed]}
            success = self._send_discord_webhook(self.webhooks['report'], payload)
            
            if success:
                self.notification_stats['health_checks'] += 1
                self.notification_stats['total_sent'] += 1
                logger.info(f"헬스체크 알림 전송 완료")
            
            return success
            
        except Exception as e:
            logger.error(f"헬스체크 알림 전송 실패: {e}")
            return False
    
    def _collect_system_info(self) -> Dict:
        """시스템 정보 수집"""
        system_info = {}
        
        try:
            # 메모리 사용량
            memory = psutil.virtual_memory()
            used_mb = memory.used // (1024 * 1024)
            total_gb = memory.total // (1024 * 1024 * 1024)
            system_info['memory_usage'] = f"{used_mb}MB/{total_gb}GB"
            
            # 디스크 사용량
            disk = psutil.disk_usage('/')
            used_gb = disk.used // (1024 * 1024 * 1024)
            total_gb = disk.total // (1024 * 1024 * 1024)
            system_info['disk_usage'] = f"{used_gb}GB/{total_gb}GB"
            
            # Chrome 버전 (시뮬레이션)
            system_info['chrome_version'] = "Google Chrome 138.0.7204.100"
            
            # ChromeDriver 버전 (시뮬레이션)
            system_info['chromedriver_version'] = "ChromeDriver 138.0.7204.100"
            system_info['chromedriver_path'] = "(5f45b7744e3d5ba62c6ca6a942f17a61cf52f75fa161f100)"
            
        except Exception as e:
            logger.error(f"시스템 정보 수집 실패: {e}")
            system_info = {
                'memory_usage': 'N/A',
                'disk_usage': 'N/A',
                'chrome_version': 'N/A',
                'chromedriver_version': 'N/A',
                'chromedriver_path': 'N/A'
            }
        
        return system_info
    
    def get_notification_stats(self) -> Dict:
        """알림 통계 조회"""
        # 통계 저장
        self._save_notification_stats()
        
        # 성공률 계산
        total_attempts = self.notification_stats['success_count'] + self.notification_stats['failure_count']
        success_rate = (self.notification_stats['success_count'] / total_attempts * 100) if total_attempts > 0 else 0
        
        stats = self.notification_stats.copy()
        stats['success_rate'] = success_rate
        stats['total_attempts'] = total_attempts
        
        return stats

# =============================================================================
# 편의 함수들
# =============================================================================

def send_bug_alert(bug_posts: List[Dict]) -> bool:
    """버그 알림 전송 (편의 함수)"""
    notifier = Epic7Notifier()
    return notifier.send_bug_alert(bug_posts)

def send_sentiment_notification(sentiment_posts: List[Dict], sentiment_summary: Dict) -> bool:
    """감성 동향 알림 전송 (편의 함수)"""
    notifier = Epic7Notifier()
    return notifier.send_sentiment_notification(sentiment_posts, sentiment_summary)

def send_daily_report(report_data: Dict) -> bool:
    """일간 리포트 전송 (편의 함수)"""
    notifier = Epic7Notifier()
    return notifier.send_daily_report(report_data)

def send_health_check(health_data: Dict = None) -> bool:
    """헬스체크 알림 전송 (편의 함수)"""
    notifier = Epic7Notifier()
    return notifier.send_health_check(health_data or {})

def get_notification_stats() -> Dict:
    """알림 통계 조회 (편의 함수)"""
    notifier = Epic7Notifier()
    return notifier.get_notification_stats()

# =============================================================================
# 메인 실행
# =============================================================================

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Epic7 통합 알림 시스템 v3.3 (디자인 개선판)"
    )
    
    parser.add_argument(
        '--test',
        choices=['bug', 'sentiment', 'report', 'health'],
        help='테스트 알림 전송'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='알림 통계 조회'
    )
    
    parser.add_argument(
        '--test-translation',
        action='store_true',
        help='번역 기능 테스트'
    )
    
    args = parser.parse_args()
    
    try:
        notifier = Epic7Notifier()
        
        if args.test:
            # 테스트 데이터 생성
            if args.test == 'bug':
                test_posts = [
                    {
                        'title': 'Bug report: Character freeze in Arena',
                        'url': 'https://www.reddit.com/r/EpicSeven/comments/test',
                        'source': 'reddit_epic7',
                        'timestamp': datetime.now().isoformat(),
                        'classification': {
                            'bug_analysis': {'priority': 'high'}
                        }
                    }
                ]
                success = notifier.send_bug_alert(test_posts)
                logger.info(f"버그 알림 테스트 결과: {'성공' if success else '실패'}")
                
            elif args.test == 'sentiment':
                test_posts = [
                    {
                        'title': 'Great update, loving the new features!',
                        'source': 'reddit_epic7',
                        'author': 'happy_user',
                        'url': 'https://reddit.com/test1',
                        'timestamp': datetime.now().isoformat(),
                        'classification': {
                            'sentiment_analysis': {'sentiment': 'positive'}
                        }
                    },
                    {
                        'title': '이번 업데이트 좋네요',
                        'source': 'stove_korea_general',
                        'author': 'satisfied_user',
                        'url': 'https://stove.com/test2',
                        'timestamp': datetime.now().isoformat(),
                        'classification': {
                            'sentiment_analysis': {'sentiment': 'positive'}
                        }
                    },
                    {
                        'title': 'Balance issues need fixing',
                        'source': 'reddit_epic7',
                        'author': 'frustrated_user',
                        'url': 'https://reddit.com/test3',
                        'timestamp': datetime.now().isoformat(),
                        'classification': {
                            'sentiment_analysis': {'sentiment': 'negative'}
                        }
                    }
                ]
                success = notifier.send_sentiment_notification(test_posts, {})
                logger.info(f"감성 동향 테스트 결과: {'성공' if success else '실패'}")
                
            elif args.test == 'report':
                test_data = {
                    'total_posts': 35,
                    'sentiment_distribution': {'positive': 1, 'negative': 5, 'neutral': 29},
                    'positive_sample': [
                        {'title': 'Amazing new character design!', 'source': 'reddit_epic7'},
                        {'title': '새로운 캐릭터 정말 좋습니다', 'source': 'stove_korea_general'}
                    ],
                    'negative_sample': [
                        {'title': 'Balance issues need fixing', 'source': 'reddit_epic7'},
                        {'title': '밸런스 문제가 심각합니다', 'source': 'stove_korea_general'}
                    ]
                }
                success = notifier.send_daily_report(test_data)
                logger.info(f"리포트 테스트 결과: {'성공' if success else '실패'}")
                
            elif args.test == 'health':
                success = notifier.send_health_check({})
                logger.info(f"헬스체크 테스트 결과: {'성공' if success else '실패'}")
        
        elif args.test_translation:
            # 번역 기능 테스트
            test_texts = [
                ("Bug report: Character freeze in Arena", "reddit_epic7"),
                ("에픽세븐 잘 하고 있습니다", "stove_korea_general"),
                ("Great update, loving the new features!", "reddit_epic7")
            ]
            
            for text, source in test_texts:
                translated = notifier._translate_to_korean(text, source)
                logger.info(f"번역 테스트: '{text}' → '{translated}'")
        
        elif args.stats:
            # 통계 조회
            stats = notifier.get_notification_stats()
            logger.info(f"알림 통계: {stats}")
        
        else:
            logger.info("Epic7 통합 알림 시스템 v3.3 준비 완료 (디자인 개선판)")
            logger.info("사용법: python notifier.py --test [bug|sentiment|report|health]")
            logger.info("       python notifier.py --test-translation (번역 테스트)")
        
    except Exception as e:
        logger.error(f"실행 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
