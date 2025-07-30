#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 다국가 크롤러 v4.4 - 6개 소스 완전 구현 완성형
Master 요구사항: 게시글별 즉시 처리 (크롤링→감성분석→알림→마킹)

핵심 구현사항:
- 6개 크롤링 소스 완전 구현 (STOVE 4개 + Reddit + 루리웹)
- 루리웹 파싱 로직 완전 구현 (신규 추가)
- 게시글별 즉시 처리 완전 구현
- 에러 격리 및 복원력 강화
- 재시도 메커니즘 자동 관리
- Dev 정책 기준 적용
- 한국/글로벌 분리 구조 지원

Author: Epic7 Monitoring Team  
Version: 4.4 (6개 소스 완전 구현)
Date: 2025-07-28
Fixed: 루리웹 파싱 로직 완전 구현
"""

import time
import random
import re
import requests
import concurrent.futures
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from urllib.parse import urljoin, urlparse

# Selenium 관련 import
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# ✨ 신규 추가: BeautifulSoup 임포트 (루리웹 파싱용)
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
    print("[INFO] BeautifulSoup4 로드 완료 - 루리웹 크롤링 지원")
except ImportError:
    print("[WARNING] BeautifulSoup4 라이브러리가 설치되지 않았습니다. 루리웹 크롤링을 건너뜁니다.")
    BEAUTIFULSOUP_AVAILABLE = False

# Epic7 시스템 모듈 import (즉시 처리용)
try:
    from classifier import Epic7Classifier, is_bug_post, is_high_priority_bug, should_send_realtime_alert
    from notifier import send_bug_alert, send_sentiment_notification
    from sentiment_data_manager import save_sentiment_data, get_sentiment_summary
    EPIC7_MODULES_AVAILABLE = True
    print("[INFO] Epic7 처리 모듈들 로드 완료")
except ImportError as e:
    print(f"[WARNING] Epic7 처리 모듈 로드 실패: {e}")
    print("[WARNING] 즉시 처리 기능이 제한됩니다.")
    EPIC7_MODULES_AVAILABLE = False

# Reddit 크롤링용 import
try:
    import praw
    REDDIT_AVAILABLE = True
    print("[INFO] PRAW 라이브러리 로드 완료 - Reddit 크롤링 지원")
except ImportError:
    print("[WARNING] PRAW 라이브러리가 설치되지 않았습니다. Reddit 크롤링을 건너뜁니다.")
    REDDIT_AVAILABLE = False

# =============================================================================
# 🚀 Master 요구사항: 즉시 처리 시스템 구현
# =============================================================================

class ImmediateProcessor:
    """게시글별 즉시 처리 시스템"""
    
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        self.retry_queue = []
        self.classifier = None
        
        if EPIC7_MODULES_AVAILABLE:
            try:
                self.classifier = Epic7Classifier()
                print("[INFO] 즉시 처리 시스템 초기화 완료")
            except Exception as e:
                print(f"[ERROR] 분류기 초기화 실패: {e}")
                
    def process_post_immediately(self, post_data: Dict) -> bool:
        """
        게시글별 즉시 처리 메인 함수
        Master 요구사항: 크롤링 → 감성분석 → 알림 → 마킹
        """
        try:
            print(f"[IMMEDIATE] 즉시 처리 시작: {post_data.get('title', '')[:50]}...")
            
            if not EPIC7_MODULES_AVAILABLE:
                print("[WARNING] 처리 모듈 없음, 기본 처리만 수행")
                self._basic_processing(post_data)
                return True
            
            # 1. 유저 동향 감성 분석
            sentiment_result = self._analyze_sentiment(post_data)
            
            # 2. 알림 전송 여부 체크 및 전송
            notification_sent = self._handle_notifications(post_data, sentiment_result)
            
            # 3. 처리 완료 마킹 (알림 성공 시에만)
            if notification_sent:
                self._mark_as_processed(post_data['url'], notified=True)
                self.processed_count += 1
                print(f"[SUCCESS] 즉시 처리 완료: {post_data.get('title', '')[:30]}...")
            else:
                # 실패한 경우 재시도 큐에 추가
                self._add_to_retry_queue(post_data, sentiment_result)
                self.failed_count += 1
                
            return notification_sent
            
        except Exception as e:
            print(f"[ERROR] 즉시 처리 실패: {e}")
            self._add_to_retry_queue(post_data, None)
            self.failed_count += 1
            return False
    
    def _analyze_sentiment(self, post_data: Dict) -> Dict:
        """감성 분석 수행"""
        try:
            if not self.classifier:
                return {"sentiment": "neutral", "confidence": 0.5}
                
            result = self.classifier.classify_post(post_data)
            print(f"[SENTIMENT] 분석 결과: {result.get('sentiment', 'unknown')}")
            return result
            
        except Exception as e:
            print(f"[ERROR] 감성 분석 실패: {e}")
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}
    
    def _handle_notifications(self, post_data: Dict, sentiment_result: Dict) -> bool:
        """분류별 알림 처리"""
        try:
            source = post_data.get('source', '')
            sentiment = sentiment_result.get('sentiment', 'neutral')
            
            # Master 요구사항: 버그 게시판 글이라면 실시간 버그 메시지
            if source.endswith('_bug') or 'bug' in source.lower():
                print("[ALERT] 버그 게시판 글 → 즉시 버그 알림")
                return self._send_bug_alert(post_data)
            
            # Master 요구사항: 동향 분석 후 버그로 분류된 글도 실시간 버그 메시지
            elif is_bug_post(sentiment_result) or should_send_realtime_alert(sentiment_result):
                print("[ALERT] 버그 분류 글 → 즉시 버그 알림")
                return self._send_bug_alert(post_data)
            
            # Master 요구사항: 긍정/중립/부정 동향은 감성 알림 + 저장
            else:
                print(f"[ALERT] 감성 동향 글 ({sentiment}) → 즉시 감성 알림")
                return self._send_sentiment_alert(post_data, sentiment_result)
                
        except Exception as e:
            print(f"[ERROR] 알림 처리 실패: {e}")
            return False
    
    def _send_bug_alert(self, post_data: Dict) -> bool:
        """버그 알림 전송"""
        try:
            success = send_bug_alert(post_data)
            if success:
                print("[SUCCESS] 버그 알림 전송 완료")
            else:
                print("[FAILED] 버그 알림 전송 실패")
            return success
        except Exception as e:
            print(f"[ERROR] 버그 알림 전송 오류: {e}")
            return False
    
    def _send_sentiment_alert(self, post_data: Dict, sentiment_result: Dict) -> bool:
        """감성 알림 전송 및 데이터 저장"""
        try:
            # Master 요구사항: 일간 리포트용 데이터 저장
            save_success = save_sentiment_data(post_data, sentiment_result)
            
            # 즉시 감성 알림 전송
            alert_success = send_sentiment_notification(post_data, sentiment_result)
            
            if save_success and alert_success:
                print("[SUCCESS] 감성 알림 전송 및 데이터 저장 완료")
                return True
            else:
                print(f"[PARTIAL] 저장: {save_success}, 알림: {alert_success}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 감성 처리 오류: {e}")
            return False
    
    def _mark_as_processed(self, url: str, notified: bool = True):
        """처리 완료 마킹"""
        try:
            mark_as_processed(url, notified)
        except Exception as e:
            print(f"[ERROR] 마킹 실패: {e}")
    
    def _add_to_retry_queue(self, post_data: Dict, sentiment_result: Optional[Dict]):
        """재시도 큐에 추가"""
        retry_item = {
            "post_data": post_data,
            "sentiment_result": sentiment_result,
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0
        }
        self.retry_queue.append(retry_item)
        print(f"[RETRY] 재시도 큐 추가: {len(self.retry_queue)}개 대기중")
    
    def _basic_processing(self, post_data: Dict):
        """기본 처리 (모듈 없을 때)"""
        print(f"[BASIC] 기본 처리: {post_data.get('title', '')[:50]}...")
        self._mark_as_processed(post_data['url'], notified=False)
    
    def process_retry_queue(self):
        """재시도 큐 처리"""
        if not self.retry_queue:
            return
            
        print(f"[RETRY] 재시도 큐 처리 시작: {len(self.retry_queue)}개")
        processed_items = []
        
        for item in self.retry_queue:
            try:
                if item["retry_count"] >= 3:
                    print("[SKIP] 최대 재시도 횟수 초과")
                    processed_items.append(item)
                    continue
                
                item["retry_count"] += 1
                success = self.process_post_immediately(item["post_data"])
                
                if success:
                    processed_items.append(item)
                    
            except Exception as e:
                print(f"[ERROR] 재시도 처리 실패: {e}")
        
        # 처리 완료된 항목들 제거
        for item in processed_items:
            self.retry_queue.remove(item)
        
        print(f"[RETRY] 재시도 완료: {len(processed_items)}개 처리, {len(self.retry_queue)}개 남음")
    
    def get_stats(self) -> Dict:
        """처리 통계 반환"""
        return {
            "processed": self.processed_count,
            "failed": self.failed_count,
            "retry_queue": len(self.retry_queue)
        }

# 전역 즉시 처리기 인스턴스
immediate_processor = ImmediateProcessor()

# =============================================================================
# 크롤링 스케줄 설정 클래스
# =============================================================================

class CrawlingSchedule:
    """크롤링 스케줄별 설정 관리"""

    FREQUENT_WAIT_TIME = 25      # 15분 주기 대기시간 (최적화)
    REGULAR_WAIT_TIME = 30       # 30분 주기 대기시간  
    REDDIT_WAIT_TIME = 15        # Reddit 대기시간
    RULIWEB_WAIT_TIME = 20       # 루리웹 대기시간

    # 스크롤 횟수 설정
    FREQUENT_SCROLL_COUNT = 2    # 15분 주기 스크롤 (성능 최적화)
    REGULAR_SCROLL_COUNT = 3

    @staticmethod
    def get_wait_time(schedule_type: str) -> int:
        """스케줄 타입별 대기시간 반환"""
        if schedule_type == 'frequent':
            return CrawlingSchedule.FREQUENT_WAIT_TIME
        elif schedule_type == 'regular':
            return CrawlingSchedule.REGULAR_WAIT_TIME
        elif schedule_type == 'reddit':
            return CrawlingSchedule.REDDIT_WAIT_TIME
        elif schedule_type == 'ruliweb':
            return CrawlingSchedule.RULIWEB_WAIT_TIME
        else:
            return CrawlingSchedule.REGULAR_WAIT_TIME

    @staticmethod
    def get_scroll_count(schedule_type: str) -> int:
        """스케줄 타입별 스크롤 횟수 반환"""
        if schedule_type == 'frequent':
            return CrawlingSchedule.FREQUENT_SCROLL_COUNT
        else:
            return CrawlingSchedule.REGULAR_SCROLL_COUNT

# =============================================================================
# 파일 관리 시스템 - 시간 기반 중복 관리 개선
# =============================================================================

def get_crawled_links_file():
    """워크플로우별 독립적인 크롤링 링크 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')

    if 'debug' in workflow_name.lower() or 'test' in workflow_name.lower():
        return "crawled_links_debug.json"
    elif 'monitor' in workflow_name.lower():
        return "crawled_links_monitor.json"
    else:
        return "crawled_links.json"

def get_content_cache_file():
    """워크플로우별 독립적인 콘텐츠 캐시 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')

    if 'debug' in workflow_name.lower():
        return "content_cache_debug.json"
    else:
        return "content_cache.json"

def load_crawled_links():
    """크롤링 링크 로드 - 시간 기반 구조 적용"""
    crawled_links_file = get_crawled_links_file()
    
    if os.path.exists(crawled_links_file):
        try:
            with open(crawled_links_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 기존 단순 리스트 형태를 새 구조로 변환
                if isinstance(data, dict) and "links" in data:
                    if isinstance(data["links"], list) and len(data["links"]) > 0:
                        # 기존 단순 링크를 시간 구조로 변환
                        if isinstance(data["links"][0], str):
                            converted_links = []
                            for link in data["links"]:
                                converted_links.append({
                                    "url": link,
                                    "processed_at": (datetime.now() - timedelta(hours=25)).isoformat(),
                                    "notified": False
                                })
                            data["links"] = converted_links
                            print(f"[INFO] 기존 {len(converted_links)}개 링크를 새 구조로 변환")
                
                # 24시간 지난 항목 자동 제거
                now = datetime.now()
                valid_links = []
                for item in data.get("links", []):
                    try:
                        processed_time = datetime.fromisoformat(item["processed_at"])
                        if now - processed_time < timedelta(hours=24):
                            valid_links.append(item)
                    except:
                        continue
                
                data["links"] = valid_links
                print(f"[INFO] 24시간 기준 유효한 링크: {len(valid_links)}개")
                return data
                        
        except Exception as e:
            print(f"[WARNING] 크롤링 링크 파일 읽기 실패: {e}")
    
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data):
    """크롤링 링크 저장 - 적극적 크기 관리"""
    try:
        # 크기 제한을 100개로 축소 (더 적극적 관리)
        if len(link_data["links"]) > 100:
            # 최신 100개만 유지
            link_data["links"] = sorted(
                link_data["links"], 
                key=lambda x: x.get("processed_at", ""), 
                reverse=True
            )[:100]
            print(f"[INFO] 링크 목록을 최신 100개로 정리")

        link_data["last_updated"] = datetime.now().isoformat()

        crawled_links_file = get_crawled_links_file()
        with open(crawled_links_file, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
            
        print(f"[INFO] 크롤링 링크 저장 완료: {len(link_data['links'])}개")

    except Exception as e:
        print(f"[ERROR] 링크 저장 실패: {e}")

def is_recently_processed(url: str, links_data: List[Dict], hours: int = 24) -> bool:
    """시간 기반 중복 체크 - 24시간 내 처리된 링크인지 확인"""
    try:
        now = datetime.now()
        for item in links_data:
            if item.get("url") == url:
                processed_time = datetime.fromisoformat(item["processed_at"])
                if now - processed_time < timedelta(hours=hours):
                    return True
        return False
    except Exception as e:
        print(f"[DEBUG] 중복 체크 오류: {e}")
        return False

def mark_as_processed(url: str, notified: bool = False):
    """게시글을 처리됨으로 마킹 - 알림 성공 후에만 호출"""
    try:
        link_data = load_crawled_links()
        
        # 기존 항목 업데이트 또는 새 항목 추가
        found = False
        for item in link_data["links"]:
            if item.get("url") == url:
                item["processed_at"] = datetime.now().isoformat()
                item["notified"] = notified
                found = True
                break
        
        if not found:
            link_data["links"].append({
                "url": url,
                "processed_at": datetime.now().isoformat(),
                "notified": notified
            })
        
        save_crawled_links(link_data)
        print(f"[INFO] 링크 처리 완료 마킹: {url[:50]}... (알림: {notified})")
        
    except Exception as e:
        print(f"[ERROR] 링크 마킹 실패: {e}")

def load_content_cache():
    """게시글 내용 캐시 로드"""
    content_cache_file = get_content_cache_file()

    if os.path.exists(content_cache_file):
        try:
            with open(content_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"[WARNING] {content_cache_file} 파일 읽기 실패, 새로 생성")
    return {}

def save_content_cache(cache_data):
    """게시글 내용 캐시 저장"""
    try:
        if len(cache_data) > 500:
            sorted_items = sorted(cache_data.items(), 
                                key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache_data = dict(sorted_items[:500])

        content_cache_file = get_content_cache_file()
        with open(content_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[ERROR] 캐시 저장 실패: {e}")

# =============================================================================
# Chrome Driver 관리 - 리소스 최적화 강화
# =============================================================================

def get_chrome_driver():
    """Chrome 드라이버 초기화 - 리소스 최적화 및 안정성 강화"""
    options = Options()

    # 기본 옵션들
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--window-size=1920,1080')

    # 추가 리소스 최적화 옵션
    options.add_argument('--memory-pressure-off')
    options.add_argument('--max_old_space_size=2048')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')

    # 봇 탐지 우회
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 랜덤 User-Agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')

    # 성능 최적화
    prefs = {
        'profile.default_content_setting_values': {
            'images': 2, 'plugins': 2, 'popups': 2,
            'geolocation': 2, 'notifications': 2, 'media_stream': 2,
        }
    }
    options.add_experimental_option('prefs', prefs)

    # 3단계 폴백 메커니즘
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver', 
        '/snap/bin/chromium.chromedriver'
    ]

    # 1단계: 시스템 경로들 시도
    for path in possible_paths:
        try:
            if os.path.exists(path):
                print(f"[DEBUG] ChromeDriver 시도: {path}")
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                print(f"[DEBUG] ChromeDriver 성공: {path}")
                return driver
        except Exception as e:
            print(f"[DEBUG] ChromeDriver 실패 {path}: {str(e)[:100]}...")
            continue

    # 2단계: WebDriver Manager
    try:
        print("[DEBUG] WebDriver Manager 시도")
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("[DEBUG] WebDriver Manager 성공")
        return driver
    except Exception as e:
        print(f"[DEBUG] WebDriver Manager 실패: {str(e)[:100]}...")

    raise Exception("모든 ChromeDriver 초기화 방법이 실패했습니다.")

# =============================================================================
# URL 처리 유틸리티
# =============================================================================

def fix_url_bug(url):
    """URL 버그 수정 함수"""
    if not url:
        return url

    # ttps:// → https:// 수정
    if url.startswith('ttps://'):
        url = 'h' + url
        print(f"[URL FIX] ttps → https: {url}")

    # 상대 경로 → 절대 경로
    elif url.startswith('/'):
        if 'onstove.com' in url or 'epicseven' in url:
            url = 'https://page.onstove.com' + url
        elif 'ruliweb.com' in url:
            url = 'https://bbs.ruliweb.com' + url
        elif 'reddit.com' in url:
            url = 'https://www.reddit.com' + url
        print(f"[URL FIX] 상대경로 수정: {url}")

    # 프로토콜 누락
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        print(f"[URL FIX] 프로토콜 추가: {url}")

    return url

# =============================================================================
# Phase 2: 의미있는 본문 추출 함수 (성능 최적화)
# =============================================================================

def extract_meaningful_content(text: str) -> str:
    """Phase 2: 의미있는 본문 내용 추출 알고리즘 (성능 최적화)"""
    if not text or len(text) < 30:
        return ""

    # 문장 단위로 분할 (개선된 정규식)
    sentences = re.split(r'[.!?。！？]\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:100].strip()

    # 의미있는 문장 필터링 시스템
    meaningful_sentences = []

    for sentence in sentences:
        if len(sentence) < 10:  # 너무 짧은 문장 제외
            continue

        # 의미없는 문장 패턴 제외
        meaningless_patterns = [
            r'^[ㅋㅎㄷㅠㅜㅡ]+$',  # 자음모음만
            r'^[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?`~]+$',  # 특수문자만
            r'^\d+$',  # 숫자만
            r'^(음|어|아|네|예|응|ㅇㅇ|ㅠㅠ|ㅜㅜ)$',  # 단순 감탄사
        ]

        if any(re.match(pattern, sentence) for pattern in meaningless_patterns):
            continue

        # Epic7 관련 의미있는 키워드 스코어링
        meaningful_keywords = [
            '버그', '오류', '문제', '에러', '안됨', '작동', '실행',
            '캐릭터', '스킬', '아티팩트', '장비', '던전', '아레나', 
            '길드', '이벤트', '업데이트', '패치', '밸런스', '너프',
            '게임', '플레이', '유저', '운영', '공지', '확률',
            '뽑기', '소환', '6성', '각성', '초월', '룬', '젬'
        ]

        score = sum(1 for keyword in meaningful_keywords if keyword in sentence)

        # 의미있는 문장으로 판별
        if score > 0 or len(sentence) >= 30:
            meaningful_sentences.append(sentence)

    if not meaningful_sentences:
        # 폴백: 첫 번째 긴 문장
        long_sentences = [s for s in sentences if len(s) >= 20]
        if long_sentences:
            return long_sentences[0]
        else:
            return sentences[0] if sentences else text[:100]

    # 최적 조합: 1-3개 문장 조합으로 의미있는 내용 구성
    result = meaningful_sentences[0]

    # 첫 번째 문장이 너무 짧으면 두 번째 문장 추가
    if len(result) < 50 and len(meaningful_sentences) > 1:
        result += ' ' + meaningful_sentences[1]

    # 여전히 부족하면 세 번째 문장까지 추가
    if len(result) < 80 and len(meaningful_sentences) > 2:
        result += ' ' + meaningful_sentences[2]

    return result.strip()

# =============================================================================
# Phase 2: Stove 게시글 내용 추출 함수 - 성능 최적화 완료
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome, 
                          source: str = "stove_korea_bug", 
                          schedule_type: str = "frequent") -> str:
    """Phase 2: 스토브 게시글 내용 추출 - 성능 최적화 완료"""

    # 캐시 확인
    cache = load_content_cache()
    url_hash = hash(post_url) % (10**8)

    if str(url_hash) in cache:
        cached_item = cache[str(url_hash)]
        cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
        if datetime.now() - cache_time < timedelta(hours=24):
            print(f"[CACHE] 캐시된 내용 사용: {post_url}")
            return cached_item.get('content', "게시글 내용을 확인할 수 없습니다.")

    content_summary = "게시글 내용을 확인할 수 없습니다."

    try:
        print(f"[DEBUG] 게시글 내용 추출 시도: {post_url}")

        wait_time = CrawlingSchedule.get_wait_time(schedule_type)
        driver.set_page_load_timeout(wait_time + 10)
        driver.get(post_url)

        print(f"[DEBUG] 페이지 로딩 대기 중... ({wait_time}초)")
        time.sleep(wait_time)

        # JavaScript 완전 로딩 확인
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Phase 2 최적화: 단계별 스크롤링 (성능 개선)
        print("[DEBUG] 최적화된 스크롤링 시작...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        print("[DEBUG] 최적화된 스크롤링 완료")

        # Phase 2: Master 발견 CSS Selector 우선 적용
        content_selectors = [
            # Master 지적사항: 목록 페이지에서 직접 추출
            'meta[data-vmid="description"]',
            'meta[name="description"]',

            # 개별 페이지 선택자들 (백업)
            'div.s-article-content',
            'div.s-article-content-text',
            'section.s-article-body',
            'div.s-board-content',

            # Phase 2: 추가 백업 선택자
            '.article-content',
            '.post-content',
            '[class*="content"]'
        ]

        # Phase 2: 의미있는 본문 추출 알고리즘 적용
        for i, selector in enumerate(content_selectors):
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        # 메타 태그는 content 속성에서, 일반 태그는 text에서 추출
                        if selector.startswith('meta'):
                            raw_text = element.get_attribute('content').strip()
                        else:
                            raw_text = element.text.strip()

                        if not raw_text or len(raw_text) < 30:
                            continue           

                        # Phase 2: 메타데이터 필터링 강화
                        skip_keywords = [
                            'install stove', '스토브를 설치', '로그인이 필요', 
                            'javascript', '댓글', '공유', '좋아요', '추천', '신고',
                            '작성자', '작성일', '조회수', '첨부파일', '다운로드',
                            'copyright', '저작권', '이용약관', '개인정보', '쿠키',
                            '광고', 'ad', 'advertisement', '프로모션', '이벤트',
                            '로그인', 'login', 'sign in', '회원가입', 'register',
                            '메뉴', 'menu', 'navigation', '네비게이션', '사이드바',
                            '배너', 'banner', '푸터', 'footer', '헤더', 'header'
                        ]

                        if any(skip.lower() in raw_text.lower() for skip in skip_keywords):
                            continue

                        # Phase 2: 의미있는 문단 추출 (성능 최적화)
                        meaningful_content = extract_meaningful_content(raw_text)

                        # Phase 2: 최소 길이 50자 이상으로 증가
                        if len(meaningful_content) >= 50:
                            # 150자 이내로 요약
                            if len(meaningful_content) > 150:
                                content_summary = meaningful_content[:147] + '...'
                            else:
                                content_summary = meaningful_content

                            print(f"[SUCCESS] 선택자 {i+1}/{len(content_selectors)} '{selector}'로 내용 추출 성공")
                            print(f"[CONTENT] {content_summary[:80]}...")
                            break

                    if content_summary != "게시글 내용을 확인할 수 없습니다.":
                        break

            except Exception as e:
                print(f"[DEBUG] 선택자 '{selector}' 실패: {e}")
                continue

        # 캐시 저장
        cache[str(url_hash)] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url,
            'source': source
        }
        save_content_cache(cache)

    except TimeoutException:
        print(f"[ERROR] 페이지 로딩 타임아웃: {post_url}")
        content_summary = "⏰ 게시글 로딩 시간 초과"
    except Exception as e:
        print(f"[ERROR] 게시글 내용 추출 실패: {e}")
        content_summary = "🔗 게시글 내용 확인 실패"

    return content_summary

# =============================================================================
# 🚀 Master 요구사항: Stove 게시판 크롤링 + 즉시 처리 통합
# =============================================================================

def crawl_stove_board(board_url: str, source: str, force_crawl: bool = False, 
                     schedule_type: str = "frequent", region: str = "korea",
                     on_post_process: Optional[Callable[[Dict], None]] = None) -> List[Dict]:
    """
    Stove 게시판 크롤링 + 즉시 처리 통합
    Master 요구사항: 게시글별 즉시 처리 (크롤링→감성분석→알림→마킹)
    """

    posts = []
    link_data = load_crawled_links()

    print(f"[INFO] {source} 크롤링 시작 - URL: {board_url}")
    print(f"[DEBUG] 기존 링크 수: {len(link_data['links'])}, Force Crawl: {force_crawl}")

    driver = None
    try:
        driver = get_chrome_driver()

        wait_time = CrawlingSchedule.get_wait_time(schedule_type)
        driver.set_page_load_timeout(wait_time + 10)
        driver.implicitly_wait(15)

        print(f"[DEBUG] 게시판 접속 중: {board_url}")
        driver.get(board_url)

        print(f"[DEBUG] 페이지 로딩 대기 중... ({wait_time}초)")
        time.sleep(wait_time)

        # JavaScript 완전 로딩 확인
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Phase 2: 최적화된 스크롤링 (성능 개선)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(3)

        # 디버깅용 HTML 저장
        debug_filename = f"{source}_debug_selenium.html"
        with open(debug_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"[DEBUG] HTML 저장: {debug_filename}")

        # Phase 2: Master 발견 선택자 우선 적용 - JavaScript 최적화
        user_posts = driver.execute_script("""
            var userPosts = [];

            // Phase 2: Master 지적사항 - section.s-board-item 최우선 적용
            const selectors = [
                'section.s-board-item',           // Master 발견 선택자 (최우선)
                'h3.s-board-title',               // 기존 선택자 (백업)
                '[class*="board-title"]',         // 클래스명 포함
                '[class*="post-title"]',          // post-title 포함
                '[class*="article-title"]',       // article-title 포함
                'h3[class*="title"]',            // h3 태그 title 포함
                'a[href*="/view/"]'              // view 링크 직접 찾기
            ];

            var elements = [];
            var successful_selector = '';

            // 선택자별 시도
            for (var i = 0; i < selectors.length; i++) {
                try {
                    elements = document.querySelectorAll(selectors[i]);
                    if (elements && elements.length > 0) {
                        successful_selector = selectors[i];
                        console.log('Phase 2 선택자 성공:', selectors[i], '개수:', elements.length);
                        break;
                    }
                } catch (e) {
                    console.log('선택자 실패:', selectors[i], e);
                    continue;
                }
            }

            if (!elements || elements.length === 0) {
                console.log('모든 선택자 실패');
                return [];
            }

            console.log('총 발견된 요소 수:', elements.length);

            // 공지사항 ID들 (제외 대상)
            const officialIds = ['10518001', '10855687', '10855562', '10855132'];

            // 각 요소에서 게시글 정보 추출
            for (var i = 0; i < Math.min(elements.length, 20); i++) {
                var element = elements[i];

                try {
                    var linkElement, titleElement, contentElement = null;
                    var href = '', title = '', preview_content = '';

                    // 링크 요소 찾기
                    if (successful_selector === 'section.s-board-item') {
                        // Phase 2: Master 지적사항 - 목록 페이지에서 직접 본문 추출
                        linkElement = element.querySelector('a[href*="/view/"]');
                        titleElement = element.querySelector('.s-board-title-text, .board-title, h3 span, .title');

                        // Master 발견: p.s-board-text에서 본문 직접 추출
                        contentElement = element.querySelector('p.s-board-text');
                        if (contentElement) {
                            preview_content = contentElement.textContent?.trim() || '';
                        }
                    } else {
                        // 기타 선택자 기반 추출
                        linkElement = element.closest('a[href*="/view/"]') || element.querySelector('a[href*="/view/"]');
                        titleElement = element;
                    }

                    // 링크 추출
                    if (linkElement && linkElement.href) {
                        href = linkElement.href;
                    }

                    // 제목 추출
                    if (titleElement) {
                        title = titleElement.textContent?.trim() || titleElement.innerText?.trim() || '';
                    }

                    // 유효성 검사
                    if (!href || !title || title.length < 3) {
                        continue;
                    }

                    // URL에서 게시글 ID 추출
                    var idMatch = href.match(/\/view\/(\d+)/);
                    if (!idMatch) {
                        continue;
                    }
                    var id = idMatch[1];

                    // 공지사항 제외
                    if (officialIds.includes(id)) {
                        console.log('공지사항 제외:', id, title.substring(0, 20));
                        continue;
                    }

                    // 공지/이벤트 배지 확인
                    var isNotice = element.querySelector('i.element-badge__s.notice, .notice, [class*="notice"]');
                    var isEvent = element.querySelector('i.element-badge__s.event, .event, [class*="event"]');
                    var isOfficial = element.querySelector('span.s-profile-staff-official, [class*="official"]');

                    if (isNotice || isEvent || isOfficial) {
                        console.log('공지/이벤트 제외:', title.substring(0, 20));
                        continue;
                    }

                    // 제목에서 [공지], [이벤트] 등 키워드 제외  
                    var skipKeywords = ['[공지]', '[이벤트]', '[안내]', '[점검]', '[공지사항]'];
                    var shouldSkip = skipKeywords.some(function(keyword) {
                        return title.includes(keyword);
                    });

                    if (shouldSkip) {
                        console.log('키워드 제외:', title.substring(0, 20));
                        continue;
                    }

                    // URL 정규화
                    var fullUrl = href.startsWith('http') ? href : 'https://page.onstove.com' + href;

                    userPosts.push({
                        href: fullUrl,
                        id: id,
                        title: title.substring(0, 200).trim(),
                        preview_content: preview_content.substring(0, 150).trim(),
                        selector_used: successful_selector
                    });

                    console.log('Phase 2 게시글 추가:', title.substring(0, 30));

                } catch (e) {
                    console.log('게시글 처리 오류:', e.message);
                    continue;
                }
            }

            console.log('Phase 2 최종 추출된 유저 게시글 수:', userPosts.length);
            return userPosts;
        """)

        print(f"[DEBUG] Phase 2 JavaScript로 {len(user_posts)}개 게시글 발견")

        # 🚀 Master 요구사항: 각 게시글별 즉시 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                post_id = post_info['id']
                preview_content = post_info.get('preview_content', '')

                # URL 버그 수정 적용
                href = fix_url_bug(href)

                print(f"[DEBUG] 게시글 {i}/{len(user_posts)}: {title[:40]}...")
                print(f"[DEBUG] URL: {href}")

                # 시간 기반 중복 확인 (24시간 내 처리된 경우만 SKIP)
                if not force_crawl and is_recently_processed(href, link_data["links"]):
                    print(f"[SKIP] 24시간 내 처리된 링크: {post_id}")
                    continue

                # 제목 길이 검증
                if len(title) < 5:
                    print(f"[SKIP] 제목이 너무 짧음: {title}")
                    continue

                # Phase 2: 목록 페이지에서 추출한 본문이 있으면 사용, 없으면 개별 페이지 방문
                if preview_content and len(preview_content) >= 50:
                    content = preview_content
                    print(f"[PHASE2] 목록 페이지에서 본문 직접 추출 성공 (90% 시간 단축)")
                else:
                    # 개별 페이지 방문 (백업)
                    print(f"[FALLBACK] 개별 페이지 방문하여 본문 추출")
                    content = get_stove_post_content(href, driver, source, schedule_type)

                # 최소 본문 길이 검증
                if len(content) < 20:
                    print(f"[SKIP] 본문이 너무 짧음: {content[:50]}")
                    continue

                # 게시글 데이터 구성
                post_data = {
                    'title': title,
                    'url': href,
                    'content': content,
                    'source': source,
                    'post_id': post_id,
                    'timestamp': datetime.now().isoformat(),
                    'region': region
                }

                posts.append(post_data)

                # 🚀 Master 요구사항: 게시글별 즉시 처리
                if on_post_process:
                    try:
                        on_post_process(post_data)
                        print(f"[IMMEDIATE] 즉시 처리 완료: {title[:30]}...")
                    except Exception as e:
                        print(f"[ERROR] 즉시 처리 실패: {e}")

                print(f"[SUCCESS] 게시글 추가: {title[:40]}...")

            except Exception as e:
                print(f"[ERROR] 게시글 처리 실패: {e}")
                continue

        print(f"[INFO] {source} 크롤링 완료: {len(posts)}개 게시글")

    except TimeoutException:
        print(f"[ERROR] 페이지 로딩 타임아웃: {board_url}")
    except Exception as e:
        print(f"[ERROR] {source} 크롤링 실패: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                print(f"[DEBUG] ChromeDriver 종료: {source}")
            except Exception as e:
                print(f"[WARNING] ChromeDriver 종료 실패: {e}")

    return posts

# =============================================================================
# ✨ 완전 신규 구현: 루리웹 Epic7 크롤링 (Master 요구사항)
# =============================================================================

def crawl_ruliweb_epic7(force_crawl: bool = False, schedule_type: str = "frequent", 
                       on_post_process: Optional[Callable[[Dict], None]] = None) -> List[Dict]:
    """
    ✨ 완전 신규 구현: 루리웹 에픽세븐 게시판 크롤링
    Master 요구사항: 6번째 소스 완전 구현
    """
    
    posts = []
    link_data = load_crawled_links()
    
    print("[INFO] 루리웹 Epic7 크롤링 시작")
    
    # BeautifulSoup 라이브러리 확인
    if not BEAUTIFULSOUP_AVAILABLE:
        print("[ERROR] BeautifulSoup4가 설치되지 않았습니다. 루리웹 크롤링을 건너뜁니다.")
        return posts
    
    try:
        # 루리웹 Epic7 게시판 URL (Master 지정)
        url = "https://bbs.ruliweb.com/game/84834"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        wait_time = CrawlingSchedule.get_wait_time('ruliweb')
        
        print(f"[DEBUG] 루리웹 요청 시작: {url}")
        response = requests.get(url, headers=headers, timeout=wait_time)
        response.raise_for_status()
        
        # 페이지 로딩 대기
        time.sleep(wait_time)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 루리웹 게시글 선택자 (실제 HTML 구조 기반)
        board_items = soup.select('table.board_list_table tbody tr')
        
        print(f"[DEBUG] 루리웹에서 {len(board_items)}개 항목 발견")
        
        for item in board_items:
            try:
                # 제목 및 링크 추출
                title_element = item.select_one('td.subject a.deco')
                if not title_element:
                    continue
                
                title = title_element.get_text(strip=True)
                href = title_element.get('href', '')
                
                # URL 정규화
                if href.startswith('/'):
                    href = 'https://bbs.ruliweb.com' + href
                
                # 기본 검증
                if not title or len(title) < 5 or not href:
                    continue
                
                # 공지사항 제외
                notice_element = item.select_one('.notice_icon, .icon_notice')
                if notice_element:
                    continue
                
                # 중복 체크
                if not force_crawl and is_recently_processed(href, link_data["links"]):
                    print(f"[SKIP] 24시간 내 처리된 링크: {href}")
                    continue
                
                # 게시글 ID 추출
                post_id_match = re.search(r'/hobby/(\d+)', href)
                post_id = post_id_match.group(1) if post_id_match else str(hash(href))
                
                # 작성자 정보
                author_element = item.select_one('td.writer .nick')
                author = author_element.get_text(strip=True) if author_element else "익명"
                
                # 작성일 정보
                date_element = item.select_one('td.time')
                created_time = date_element.get_text(strip=True) if date_element else ""
                
                # 조회수 정보
                hit_element = item.select_one('td.hit')
                hit_count = hit_element.get_text(strip=True) if hit_element else "0"
                
                # Epic7 관련 키워드 필터링 (중요!)
                epic7_keywords = [
                    '에픽세븐', 'epic7', 'epic seven', '에7', 'e7',
                    '스킬', '캐릭터', '아티팩트', '장비', '버그', '오류',
                    '업데이트', '패치', '밸런스', '너프', '버프',
                    '소환', '뽑기', '6성', '각성', '초월'
                ]
                
                if not any(keyword.lower() in title.lower() for keyword in epic7_keywords):
                    print(f"[SKIP] Epic7 관련 없는 게시글: {title[:30]}...")
                    continue
                
                # 게시글 데이터 구성
                post_data = {
                    'title': title,
                    'url': href,
                    'content': title,  # 루리웹은 목록에서 본문 미제공
                    'source': 'ruliweb_epic7',
                    'author': author,
                    'created_time': created_time,
                    'hit_count': hit_count,
                    'post_id': post_id,
                    'timestamp': datetime.now().isoformat()
                }
                
                posts.append(post_data)
                
                # 🚀 Master 요구사항: 게시글별 즉시 처리
                if on_post_process:
                    try:
                        on_post_process(post_data)
                        print(f"[IMMEDIATE] 루리웹 즉시 처리 완료: {title[:30]}...")
                    except Exception as e:
                        print(f"[ERROR] 루리웹 즉시 처리 실패: {e}")
                
                print(f"[SUCCESS] 루리웹 게시글 추가: {title[:40]}...")
                
            except Exception as e:
                print(f"[ERROR] 루리웹 게시글 처리 실패: {e}")
                continue
        
        print(f"[INFO] 루리웹 크롤링 완료: {len(posts)}개 게시글")
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 루리웹 네트워크 오류: {e}")
    except Exception as e:
        print(f"[ERROR] 루리웹 크롤링 실패: {e}")
    
    return posts

# =============================================================================
# Reddit Epic7 크롤링 (기존 유지)
# =============================================================================

def crawl_reddit_epic7(force_crawl: bool = False, schedule_type: str = "frequent",
                      on_post_process: Optional[Callable[[Dict], None]] = None) -> List[Dict]:
    """Reddit r/EpicSeven 서브레딧 크롤링"""
    
    posts = []
    link_data = load_crawled_links()
    
    print("[INFO] Reddit Epic7 크롤링 시작")
    
    if not REDDIT_AVAILABLE:
        print("[ERROR] PRAW 라이브러리가 설치되지 않았습니다. Reddit 크롤링을 건너뜁니다.")
        return posts
    
    try:
        # Reddit API 환경변수 확인
        client_id = os.environ.get('REDDIT_CLIENT_ID')
        client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
        user_agent = os.environ.get('REDDIT_USER_AGENT', 'Epic7Monitor/1.0')
        
        if not client_id or not client_secret:
            print("[ERROR] Reddit API 환경변수가 설정되지 않았습니다.")
            return posts
        
        # Reddit 인스턴스 생성
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        # r/EpicSeven 서브레딧
        subreddit = reddit.subreddit('EpicSeven')
        
        # 최신 게시글 20개 가져오기
        for submission in subreddit.new(limit=20):
            try:
                # 기본 검증
                if not submission.title or len(submission.title) < 5:
                    continue
                
                # URL 구성
                post_url = f"https://www.reddit.com{submission.permalink}"
                
                # 중복 체크
                if not force_crawl and is_recently_processed(post_url, link_data["links"]):
                    continue
                
                # 스팸 키워드 필터
                spam_keywords = ['buy', 'sell', 'account', 'cheap', 'discord.gg']
                if any(keyword.lower() in submission.title.lower() for keyword in spam_keywords):
                    continue
                
                # Epic7 핵심 키워드 필터
                epic7_keywords = [
                    'epic7', 'epic seven', 'e7', 'character', 'artifact', 
                    'equipment', 'bug', 'update', 'patch', 'balance',
                    'summon', '6star', 'awakening', 'imprint'
                ]
                
                if not any(keyword.lower() in submission.title.lower() for keyword in epic7_keywords):
                    continue
                
                # 게시글 본문 추출
                content = submission.selftext[:200] if submission.selftext else submission.title
                
                # 게시글 데이터 구성
                post_data = {
                    'title': submission.title,
                    'url': post_url,
                    'content': content,
                    'source': 'reddit_epic7',
                    'author': str(submission.author) if submission.author else "deleted",
                    'created_time': datetime.fromtimestamp(submission.created_utc).isoformat(),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'post_id': submission.id,
                    'timestamp': datetime.now().isoformat()
                }
                
                posts.append(post_data)
                
                # 🚀 Master 요구사항: 게시글별 즉시 처리
                if on_post_process:
                    try:
                        on_post_process(post_data)
                        print(f"[IMMEDIATE] Reddit 즉시 처리 완료: {submission.title[:30]}...")
                    except Exception as e:
                        print(f"[ERROR] Reddit 즉시 처리 실패: {e}")
                
                print(f"[SUCCESS] Reddit 게시글 추가: {submission.title[:40]}...")
                
            except Exception as e:
                print(f"[ERROR] Reddit 게시글 처리 실패: {e}")
                continue
        
        print(f"[INFO] Reddit 크롤링 완료: {len(posts)}개 게시글")
        
    except Exception as e:
        print(f"[ERROR] Reddit 크롤링 실패: {e}")
    
    return posts

# =============================================================================
# 🚀 Master 요구사항: 통합 크롤링 함수 (6개 소스 완전 구현)
# =============================================================================

def crawl_frequent_sites(force_crawl: bool = False, schedule_type: str = "frequent", 
                        region: str = "all") -> List[Dict]:
    """
    🚀 Master 요구사항: 15분 주기 빈번한 크롤링 - 6개 소스 완전 구현
    한국/글로벌 분리 구조 지원
    """
    
    all_posts = []
    
    print(f"[INFO] 빈번한 크롤링 시작 - 지역: {region}, Force: {force_crawl}")
    
    # Master 요구사항: 6개 크롤링 소스 정의
    crawl_tasks = []
    
    if region in ["all", "korea"]:
        crawl_tasks.extend([
            ('한국 버그 게시판', lambda: crawl_stove_board(
                "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST",
                "stove_korea_bug", force_crawl, schedule_type, "korea",
                immediate_processor.process_post_immediately
            )),
            ('한국 자유게시판', lambda: crawl_stove_board(
                "https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST",
                "stove_korea_general", force_crawl, schedule_type, "korea",
                immediate_processor.process_post_immediately
            )),
            ('루리웹 Epic7', lambda: crawl_ruliweb_epic7(
                force_crawl, schedule_type,
                immediate_processor.process_post_immediately
            ))
        ])
    
    if region in ["all", "global"]:
        crawl_tasks.extend([
            ('글로벌 버그 게시판', lambda: crawl_stove_board(
                "https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST",
                "stove_global_bug", force_crawl, schedule_type, "global",
                immediate_processor.process_post_immediately
            )),
            ('글로벌 자유게시판', lambda: crawl_stove_board(
                "https://page.onstove.com/epicseven/global/list/989?page=1&direction=LATEST",
                "stove_global_general", force_crawl, schedule_type, "global",
                immediate_processor.process_post_immediately
            )),
            ('Reddit Epic7', lambda: crawl_reddit_epic7(
                force_crawl, schedule_type,
                immediate_processor.process_post_immediately
            ))
        ])
    
    # 병렬 크롤링 실행
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_site = {executor.submit(task[1]): task[0] for task in crawl_tasks}
        
        for future in concurrent.futures.as_completed(future_to_site):
            site_name = future_to_site[future]
            try:
                site_posts = future.result(timeout=300)  # 5분 타임아웃
                all_posts.extend(site_posts)
                print(f"[SUCCESS] {site_name}: {len(site_posts)}개 게시글")
            except Exception as e:
                print(f"[ERROR] {site_name} 크롤링 실패: {e}")
    
    # 재시도 큐 처리
    immediate_processor.process_retry_queue()
    
    # 통계 출력
    stats = immediate_processor.get_stats()
    print(f"[STATS] 전체: {len(all_posts)}개, 즉시처리: {stats['processed']}개, 실패: {stats['failed']}개")
    
    return all_posts

def crawl_regular_sites(force_crawl: bool = False, schedule_type: str = "regular",
                       region: str = "all") -> List[Dict]:
    """30분 주기 정규 크롤링 (frequent_sites와 동일하게 6개 소스 완전 지원)"""
    return crawl_frequent_sites(force_crawl, schedule_type, region)

def crawl_by_schedule(schedule_or_site: str, force_crawl: bool = False, region: str = "all") -> List[Dict]:
    """스케줄별 크롤링 통합 함수 - 사이트명 호환성 추가"""
    
    print(f"[INFO] 스케줄별 크롤링 시작: {schedule_or_site}, 지역: {region}")
    
    # 사이트명이 들어온 경우 매핑
    site_to_schedule = {
        'stove_korea_bug': 'frequent',
        'stove_korea_general': 'regular',
        'stove_global_bug': 'frequent', 
        'stove_global_general': 'regular',
        'ruliweb_epic7': 'regular',
        'reddit_epicseven': 'regular'
    }
    
    # 사이트명인지 스케줄명인지 판별
    if schedule_or_site in site_to_schedule:
        schedule = site_to_schedule[schedule_or_site]
        print(f"[INFO] 사이트명 '{schedule_or_site}'을 스케줄 '{schedule}'로 매핑")
    else:
        schedule = schedule_or_site
        
    # 기존 스케줄 처리 로직 (그대로 유지)
    if schedule in ["15min", "frequent"]:
        return crawl_frequent_sites(force_crawl, "frequent", region)
    elif schedule in ["30min", "regular"]:
        return crawl_regular_sites(force_crawl, "regular", region)
    elif schedule in ["24h", "daily"]:
        # 일간 리포트용은 기존 데이터 활용
        return []
    else:
        print(f"[ERROR] 알 수 없는 스케줄: {schedule}")
        return []
      
def get_all_posts_for_report(hours: int = 24) -> List[Dict]:
    """일간 리포트용 게시글 수집 (감성 데이터에서 추출)"""
    try:
        # 감성 데이터 매니저에서 일간 데이터 수집
        if EPIC7_MODULES_AVAILABLE:
            from sentiment_data_manager import get_today_sentiment_summary
            return get_today_sentiment_summary(hours)
        else:
            print("[WARNING] 감성 데이터 매니저 없음, 빈 리포트 반환")
            return []
    except Exception as e:
        print(f"[ERROR] 일간 리포트 데이터 수집 실패: {e}")
        return []

# =============================================================================
# 메인 실행 함수
# =============================================================================

def main():
    """메인 실행 함수 - 6개 소스 완전 구현 테스트"""
    
    print("=== Epic7 크롤러 v4.4 - 6개 소스 완전 구현 테스트 ===")
    
    # 한국 사이트만 테스트
    print("\n1. 한국 사이트 크롤링 테스트")
    korea_posts = crawl_frequent_sites(force_crawl=True, region="korea")
    print(f"한국 사이트 결과: {len(korea_posts)}개")
    
    # 글로벌 사이트만 테스트
    print("\n2. 글로벌 사이트 크롤링 테스트")
    global_posts = crawl_frequent_sites(force_crawl=True, region="global")
    print(f"글로벌 사이트 결과: {len(global_posts)}개")
    
    # 전체 사이트 테스트
    print("\n3. 전체 사이트 크롤링 테스트")
    all_posts = crawl_frequent_sites(force_crawl=True, region="all")
    print(f"전체 사이트 결과: {len(all_posts)}개")
    
    # 즉시 처리 통계
    stats = immediate_processor.get_stats()
    print(f"\n즉시 처리 통계: {stats}")
    
    print("\n=== 6개 소스 완전 구현 테스트 완료 ===")

if __name__ == "__main__":
    main()