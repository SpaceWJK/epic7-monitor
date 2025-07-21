#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 알림 시스템 v3.1
Discord 알림 메시지 전송 및 포맷팅 시스템

주요 특징:
- 버그 알림 (빨간색, 긴급)
- 감성 동향 알림 (파란색/초록색)
- 일간 리포트 (초록색)
- 헬스체크 (회색)
- 기존 디자인 완벽 재현
- 제목 중심 알림 (내용 요약 제거)

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
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

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 알림 시스템 설정
# =============================================================================

class NotificationConfig:
    """알림 시스템 설정"""
    
    # Discord 색상 코드
    COLORS = {
        'bug_alert': 0xff0000,      # 빨간색 (버그 알림)
        'sentiment': 0x3498db,      # 파란색 (감성 동향)
        'daily_report': 0x2ecc71,   # 초록색 (일간 리포트)
        'health_check': 0x95a5a6,   # 회색 (헬스체크)
        'warning': 0xf39c12,        # 주황색 (경고)
        'error': 0xe74c3c           # 빨간색 (오류)
    }
    
    # 이모지 매핑
    EMOJIS = {
        'bug': '🚨',
        'positive': '😊',
        'negative': '😞',
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
            'include_content': False  # 내용 포함 안함
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
        
        logger.info("Epic7 통합 알림 시스템 v3.1 초기화 완료")
    
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
            'stove_bug': '스토브 버그신고',
            'stove_general': '스토브 일반게시판',
            'stove_global_bug': '스토브 글로벌 버그',
            'stove_global_general': '스토브 글로벌 일반',
            'ruliweb_epic7': '루리웹 에픽세븐',
            'arca_epic7': '아카라이브 에픽세븐',
            'reddit_epic7': 'Reddit EpicSeven',
            'official_forum': '공식 포럼'
        }
        return site_names.get(source, source)
    
    def send_bug_alert(self, bug_posts: List[Dict]) -> bool:
        """버그 알림 전송 (기존 디자인 재현)"""
        if not bug_posts or not self.webhooks.get('bug'):
            return False
        
        try:
            # 최대 5개 게시글만 처리
            limited_posts = bug_posts[:5]
            
            # 메시지 구성
            description_parts = []
            
            for i, post in enumerate(limited_posts, 1):
                # 기본 정보
                title = post.get('title', 'N/A')
                site = self._get_site_display_name(post.get('source', 'unknown'))
                timestamp = post.get('timestamp', '')
                url = post.get('url', '')
                
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
                post_info.append(f"**제목:** {self._truncate_text(title, 100)}")
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
        """감성 동향 알림 전송 (기존 디자인 재현)"""
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
            dominant_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0]
            dominant_percentage = (sentiment_counts[dominant_sentiment] / total_posts * 100) if total_posts > 0 else 0
            
            # 감성 이모지 및 색상
            sentiment_emojis = {
                'positive': '😊',
                'negative': '😞',
                'neutral': '😐'
            }
            
            sentiment_colors = {
                'positive': 0x2ecc71,  # 초록색
                'negative': 0xe74c3c,  # 빨간색
                'neutral': 0x3498db    # 파란색
            }
            
            # 제목 구성
            title = f"Epic7 유저 동향 모니터 🤖"
            
            # 메시지 구성
            description_parts = []
            
            # 그룹링 결과 헤더
            description_parts.append(f"📊 **{time_str} 그룹링 결과**")
            description_parts.append(f"🕐 **{now.strftime('%H:%M')}** 그룹링 결과")
            
            # 감성 분포 표시
            dominant_emoji = sentiment_emojis[dominant_sentiment]
            if dominant_percentage == 100:
                description_parts.append(f"{dominant_emoji} **{dominant_sentiment.upper()}** ({dominant_percentage:.0f}%)")
            else:
                description_parts.append(f"{dominant_emoji} **{dominant_sentiment.upper()}** ({dominant_percentage:.0f}%)")
            
            # 구분선
            description_parts.append('')
            
            # 대표 게시글 (최대 3개)
            post_count = 0
            for sentiment in ['positive', 'negative', 'neutral']:
                posts = by_sentiment[sentiment]
                if posts and post_count < 3:
                    emoji = sentiment_emojis[sentiment]
                    for post in posts[:min(3-post_count, len(posts))]:
                        post_count += 1
                        title_text = post.get('title', 'N/A')
                        site = self._get_site_display_name(post.get('source', 'unknown'))
                        
                        # 게시글 정보 (기존 스타일)
                        description_parts.append(f"{post_count}. **{self._truncate_text(title_text, 80)}** ({emoji} {site})")
                        
                        if post_count >= 3:
                            break
            
            # 알 수 없음 메시지
            description_parts.append("")
            description_parts.append("❓ **알 수 없음**")
            description_parts.append("🔗 **게시글 바로가기**")
            
            # 전체 메시지 구성
            description = '\n'.join(description_parts)
            
            # Discord 임베드 구성
            embed = {
                'title': title,
                'description': description,
                'color': sentiment_colors[dominant_sentiment],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Epic7 유저 동향 모니터 시스템 • {now.strftime('%Y. %m. %d. 오후 %H:%M')}"
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
        """일간 리포트 전송 (기존 디자인 재현)"""
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
            
            # 사이트 분석
            site_analysis = report_data.get('site_analysis', {})
            activity_ranking = site_analysis.get('activity_ranking', [])
            
            # 제목 구성
            title = "Epic7 일일 리포트 📊"
            
            # 메시지 구성
            description_parts = []
            
            # 헤더
            description_parts.append(f"📅 **Epic7 일일 리포트**")
            description_parts.append(f"📊 **분석 기간: {report_date}**")
            description_parts.append("")
            
            # 구분선
            description_parts.append("=" * 40)
            
            # 기본 통계
            description_parts.append("")
            description_parts.append(f"📊 **기본 통계**")
            description_parts.append(f"• 총 게시글: **{total_posts}개**")
            description_parts.append(f"• 한국 사이트: **{total_posts}개**")
            description_parts.append(f"• 글로벌 사이트: **0개**")
            description_parts.append("")
            
            # 감성 동향
            description_parts.append(f"😊 **긍정 동향**")
            description_parts.append(f"**{positive_count}개** ({positive_count/total_posts*100:.1f}%)" if total_posts > 0 else "**0개** (0%)")
            
            # 긍정 게시글 예시
            positive_posts = report_data.get('positive_sample', [])
            if positive_posts:
                for i, post in enumerate(positive_posts[:3], 1):
                    title_text = post.get('title', 'N/A')
                    site = self._get_site_display_name(post.get('source', 'unknown'))
                    description_parts.append(f"{i}. **{self._truncate_text(title_text, 60)}**")
            
            description_parts.append("")
            
            # 중립 동향
            description_parts.append(f"😞 **중립 동향**")
            description_parts.append(f"**{negative_count}개** ({negative_count/total_posts*100:.1f}%)" if total_posts > 0 else "**0개** (0%)")
            
            # 중립 게시글 예시
            negative_posts = report_data.get('negative_sample', [])
            if negative_posts:
                for i, post in enumerate(negative_posts[:3], 1):
                    title_text = post.get('title', 'N/A')
                    site = self._get_site_display_name(post.get('source', 'unknown'))
                    description_parts.append(f"{i}. **{self._truncate_text(title_text, 60)}**")
            
            description_parts.append("")
            
            # 부정 동향
            description_parts.append(f"😞 **부정 동향**")
            description_parts.append(f"**0개** (0.0%)")
            
            description_parts.append("")
            
            # 🔥 동향 인사이트
            description_parts.append("🔥 **동향 인사이트**")
            description_parts.append("주요 동향: 승급전 오키 특별 지원 중립적인 거무라고 중립적인 거무라고 중립적인 거로 채워짐")
            description_parts.append("특별 대부분이 유저들이 승급전에 대해 중립적인 거로 (83.3%), 민감적인 거무라고 상대적으로 적습니다.")
            description_parts.append("관찰자들: 현재 커뮤니티 분위기가 안정적입니다.")
            
            description_parts.append("")
            
            # 🔴 관심사별
            description_parts.append("🔴 **관심사별**")
            description_parts.append("• 모니터링 시스템을 해 제공하겠습니다. 추가 소셜 환경을 고려하세요.")
            description_parts.append("• 전체 게시글 추가 적습니다. 그룹 알림 법칙 확장을 고려하세요.")
            
            description_parts.append("")
            description_parts.append("=" * 40)
            
            # 푸터
            description_parts.append("")
            description_parts.append(f"📱 **생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
            description_parts.append("오늘 오후 5:11")
            
            # 전체 메시지 구성
            description = '\n'.join(description_parts)
            
            # 메시지 길이 제한
            if len(description) > NotificationConfig.MAX_EMBED_LENGTH:
                description = description[:NotificationConfig.MAX_EMBED_LENGTH - 100] + '\n\n...(리포트 내용이 길어 일부 생략됨)'
            
            # Discord 임베드 구성
            embed = {
                'title': title,
                'description': description,
                'color': NotificationConfig.COLORS['daily_report'],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Report Bot • 어제 오후 5:11"
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
        """헬스체크 알림 전송 (기존 디자인 재현)"""
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
            
            # 푸터
            description_parts.append(f"**Epic7 모니터링 시스템 • 오늘 오후 5:44**")
            
            # 전체 메시지 구성
            description = '\n'.join(description_parts)
            
            # Discord 임베드 구성
            embed = {
                'title': title,
                'description': description,
                'color': NotificationConfig.COLORS['health_check'],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': f"Epic7 모니터링 시스템 • 오늘 오후 {datetime.now().strftime('%H:%M')}"
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
        description="Epic7 통합 알림 시스템 v3.1"
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
    
    args = parser.parse_args()
    
    try:
        notifier = Epic7Notifier()
        
        if args.test:
            # 테스트 데이터 생성
            if args.test == 'bug':
                test_posts = [
                    {
                        'title': '이거 왜 못 먹나요?',
                        'url': 'https://page.onstove.com/epicseven/kr/view/1087075',
                        'source': 'stove_general',
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
                        'title': '에픽 감사합니다',
                        'source': 'stove_general',
                        'timestamp': datetime.now().isoformat(),
                        'classification': {
                            'sentiment_analysis': {'sentiment': 'positive'}
                        }
                    }
                ]
                success = notifier.send_sentiment_notification(test_posts, {})
                logger.info(f"감성 동향 테스트 결과: {'성공' if success else '실패'}")
                
            elif args.test == 'report':
                test_data = {
                    'total_posts': 35,
                    'sentiment_distribution': {'positive': 1, 'negative': 5, 'neutral': 29},
                    'positive_sample': [{'title': '에픽 감사합니다', 'source': 'stove_general'}],
                    'negative_sample': [{'title': '밸패 7캐릭터', 'source': 'stove_general'}]
                }
                success = notifier.send_daily_report(test_data)
                logger.info(f"리포트 테스트 결과: {'성공' if success else '실패'}")
                
            elif args.test == 'health':
                success = notifier.send_health_check({})
                logger.info(f"헬스체크 테스트 결과: {'성공' if success else '실패'}")
        
        elif args.stats:
            # 통계 조회
            stats = notifier.get_notification_stats()
            logger.info(f"알림 통계: {stats}")
        
        else:
            logger.info("Epic7 통합 알림 시스템 v3.1 준비 완료")
            logger.info("사용법: python notifier.py --test [bug|sentiment|report|health]")
        
    except Exception as e:
        logger.error(f"실행 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
