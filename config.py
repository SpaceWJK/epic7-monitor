#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 모니터링 시스템 통합 설정 모듈
모든 설정을 중앙 집중식으로 관리하여 의존성 문제 해결

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
"""

import os
from datetime import datetime
from typing import Dict, Any

class Epic7Config:
    """Epic7 모니터링 시스템 통합 설정"""
    
    # =============================================================================
    # 시스템 설정
    # =============================================================================
    
    VERSION = "3.1"
    SYSTEM_NAME = "Epic7 모니터링 시스템"
    
    # 실행 모드
    class Mode:
        MONITORING = "monitoring"
        DEBUG = "debug"
        REPORT = "report"
        HEALTH_CHECK = "health_check"
    
    # =============================================================================
    # 파일 경로 설정
    # =============================================================================
    
    class Files:
        # 데이터 파일
        CRAWLED_LINKS = "crawled_links.json"
        CONTENT_CACHE = "content_cache.json"
        SENTIMENT_DATA = "sentiment_data.json"
        TRANSLATION_CACHE = "translation_cache.json"
        
        # 통계 파일
        MONITORING_STATS = "monitoring_stats.json"
        NOTIFICATION_STATS = "notification_stats.json"
        REPORT_STATS = "report_stats.json"
        
        # 리포트 파일
        REPORT_CACHE = "report_cache.json"
        REPORT_HISTORY = "report_history.json"
        SENTIMENT_TRENDS = "sentiment_trends.json"
        SENTIMENT_KEYWORDS = "sentiment_keywords.json"
        
        # 로그 파일
        MAIN_LOG = "monitor_bugs.log"
        ERROR_LOG = "error.log"
        DEBUG_LOG = "debug.log"
        
        # 디버그 디렉토리
        DEBUG_DIR = "debug"
    
    # =============================================================================
    # 크롤링 설정
    # =============================================================================
    
    class Crawling:
        # 주기 설정
        FREQUENT_INTERVAL = 15  # 15분 (버그 게시판)
        REGULAR_INTERVAL = 30   # 30분 (일반 게시판)
        
        # 타임아웃 설정
        BUG_BOARD_TIMEOUT = 45
        GENERAL_BOARD_TIMEOUT = 60
        
        # 캐시 설정
        BUG_CACHE_HOURS = 6
        GENERAL_CACHE_HOURS = 24
        
        # 15분 간격 소스 (버그 게시판)
        FREQUENT_SOURCES = {
            'stove_bug': {
                'url': 'https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST',
                'limit': 20,
                'priority': 1,
                'language': 'korean',
                'site': 'STOVE 버그신고'
            },
            'stove_global_bug': {
                'url': 'https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST',
                'limit': 20,
                'priority': 1,
                'language': 'english',
                'site': 'STOVE Global Bug'
            }
        }
        
        # 30분 간격 소스 (일반 게시판)
        REGULAR_SOURCES = {
            'stove_general': {
                'url': 'https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST',
                'limit': 15,
                'priority': 2,
                'language': 'korean',
                'site': 'STOVE 자유게시판'
            },
            'stove_global_general': {
                'url': 'https://page.onstove.com/epicseven/global/list/989?page=1&direction=LATEST',
                'limit': 15,
                'priority': 2,
                'language': 'english',
                'site': 'STOVE Global General'
            },
            'ruliweb_epic7': {
                'url': 'https://bbs.ruliweb.com/game/84834',
                'limit': 10,
                'priority': 3,
                'language': 'korean',
                'site': '루리웹'
            },
            'reddit_epic7': {
                'url': 'https://www.reddit.com/r/EpicSeven/new.json?limit=15',
                'limit': 15,
                'priority': 3,
                'language': 'english',
                'site': 'Reddit'
            }
        }
        
        # 실시간 알림 소스
        REALTIME_ALERT_SOURCES = ['stove_bug', 'stove_global_bug']
    
    # =============================================================================
    # 분류 설정
    # =============================================================================
    
    class Classification:
        # 버그 우선순위
        BUG_PRIORITY_LEVELS = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4
        }
        
        # 감성 분석 임계값
        SENTIMENT_THRESHOLDS = {
            'positive': 0.3,
            'negative': 0.3,
            'neutral': 0.5
        }
        
        # 실시간 알림 임계값
        REALTIME_ALERT_THRESHOLDS = {
            'bug_critical': 1.0,
            'bug_high': 0.8,
            'bug_medium': 0.6,
            'sentiment_negative': 0.7
        }
    
    # =============================================================================
    # 알림 설정
    # =============================================================================
    
    class Notification:
        # Discord 색상 코드
        COLORS = {
            'bug_alert': 0xff0000,
            'sentiment': 0x3498db,
            'daily_report': 0x2ecc71,
            'health_check': 0x95a5a6,
            'warning': 0xf39c12,
            'error': 0xe74c3c
        }
        
        # 메시지 제한
        MAX_MESSAGE_LENGTH = 2000
        MAX_EMBED_LENGTH = 4096
        MAX_FIELD_VALUE_LENGTH = 1024
        
        # 재시도 설정
        MAX_RETRIES = 3
        RETRY_DELAY = 2
    
    # =============================================================================
    # 리포트 설정
    # =============================================================================
    
    class Report:
        # 리포트 주기
        DAILY_REPORT_HOUR = 9
        WEEKLY_REPORT_DAY = 0  # 월요일
        MONTHLY_REPORT_DAY = 1  # 1일
        
        # 분석 기간
        DAILY_HOURS = 24
        WEEKLY_DAYS = 7
        MONTHLY_DAYS = 30
        
        # 제한값
        MIN_POSTS_FOR_REPORT = 5
        MAX_POSTS_IN_REPORT = 50
    
    # =============================================================================
    # 감성 분석 설정
    # =============================================================================
    
    class Sentiment:
        # 데이터 보존 기간
        MAX_DATA_DAYS = 90
        TREND_ANALYSIS_DAYS = 30
        PATTERN_ANALYSIS_DAYS = 14
        
        # 트렌드 분석 설정
        TREND_SMOOTHING_WINDOW = 5
        VOLATILITY_THRESHOLD = 0.2
        
        # 키워드 분석 설정
        MIN_KEYWORD_FREQUENCY = 3
        MAX_KEYWORDS_PER_CATEGORY = 20
        
        # 알림 설정
        SENTIMENT_ALERT_THRESHOLD = -30
        VOLATILITY_ALERT_THRESHOLD = 0.5
    
    # =============================================================================
    # 환경변수 설정
    # =============================================================================
    
    class Environment:
        @staticmethod
        def get_discord_webhooks() -> Dict[str, str]:
            """Discord 웹훅 환경변수 조회"""
            webhooks = {}
            
            bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
            if bug_webhook:
                webhooks['bug'] = bug_webhook
            
            sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
            if sentiment_webhook:
                webhooks['sentiment'] = sentiment_webhook
            
            report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
            if report_webhook:
                webhooks['report'] = report_webhook
            
            return webhooks
        
        @staticmethod
        def get_system_info() -> Dict[str, Any]:
            """시스템 정보 조회"""
            return {
                'version': Epic7Config.VERSION,
                'system_name': Epic7Config.SYSTEM_NAME,
                'timestamp': datetime.now().isoformat(),
                'webhooks_configured': len(Epic7Config.Environment.get_discord_webhooks()) > 0
            }

# 전역 설정 인스턴스
config = Epic7Config()
