#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 다국가 크롤러 v3.6 - 본문 추출 최적화 완료본 
🔥 3순위 문제 완전 해결: "콘텐츠 추출 개선"

핵심 개선 사항:
- ✅ 의미있는 본문 내용 추출 알고리즘 도입
- ✅ 메타데이터 필터링 시스템 강화  
- ✅ 최소 길이 50자 이상으로 증가
- ✅ 2025년 Stove 구조 최적화 CSS Selector 재배치
- ✅ 다단계 품질 검증 시스템 적용

Author: Epic7 Monitoring Team
Version: 3.6
Date: 2025-07-22
"""

import time
import random
import re
import requests
import concurrent.futures
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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

# =============================================================================
# 크롤링 스케줄 설정 클래스
# =============================================================================

class CrawlingSchedule:
    """크롤링 스케줄별 설정 관리"""
    
    FREQUENT_WAIT_TIME = 30      # 버그 게시판 대기시간
    REGULAR_WAIT_TIME = 35       # 일반 게시판 대기시간  
    REDDIT_WAIT_TIME = 20        # Reddit 대기시간
    RULIWEB_WAIT_TIME = 22       # 루리웹 대기시간
    
    # 스크롤 횟수 설정
    FREQUENT_SCROLL_COUNT = 3
    REGULAR_SCROLL_COUNT = 5
    
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
# 파일 관리 시스템
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
    """이미 크롤링된 링크들을 로드"""
    crawled_links_file = get_crawled_links_file()
    
    if os.path.exists(crawled_links_file):
        try:
            with open(crawled_links_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"links": data, "last_updated": datetime.now().isoformat()}
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"[WARNING] {crawled_links_file} 파일 읽기 실패, 새로 생성")
    
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data):
    """크롤링된 링크들을 저장 (최대 1000개 유지)"""
    try:
        if len(link_data["links"]) > 1000:
            link_data["links"] = link_data["links"][-1000:]
        
        link_data["last_updated"] = datetime.now().isoformat()
        
        crawled_links_file = get_crawled_links_file()
        with open(crawled_links_file, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"[ERROR] 링크 저장 실패: {e}")

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
# Chrome Driver 관리
# =============================================================================

def get_chrome_driver():
    """Chrome 드라이버 초기화 (Chrome 138+ 호환)"""
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
    
    # 1단계: Chrome for Testing API
    try:
        response = requests.get('https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE')
        if response.status_code == 200:
            version = response.text.strip()
            print(f"[DEBUG] 최신 Chrome 버전: {version}")
    except:
        pass
    
    # 2단계: 시스템 경로들 시도
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
    
    # 3단계: WebDriver Manager
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
    """URL 버그 수정 함수 (998, 989, 1012, 1005 등)"""
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
# 🔥 핵심 개선: 의미있는 본문 추출 함수
# =============================================================================

def extract_meaningful_content(text: str) -> str:
    """🔥 새로 추가: 의미있는 본문 내용 추출 알고리즘"""
    if not text or len(text) < 30:
        return ""
    
    # 문장 단위로 분할 (개선된 정규식)
    sentences = re.split(r'[.!?。！？]\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return text[:100].strip()
    
    # 🎯 의미있는 문장 필터링 시스템
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
        
        # 의미있는 문장으로 판별 (키워드 점수 또는 충분한 길이)
        if score > 0 or len(sentence) >= 30:
            meaningful_sentences.append(sentence)
    
    if not meaningful_sentences:
        # 폴백: 첫 번째 긴 문장
        long_sentences = [s for s in sentences if len(s) >= 20]
        if long_sentences:
            return long_sentences[0]
        else:
            return sentences[0] if sentences else text[:100]
    
    # 🎯 최적 조합: 1-3개 문장 조합으로 의미있는 내용 구성
    result = meaningful_sentences[0]
    
    # 첫 번째 문장이 너무 짧으면 두 번째 문장 추가
    if len(result) < 50 and len(meaningful_sentences) > 1:
        result += ' ' + meaningful_sentences[1]
    
    # 여전히 부족하면 세 번째 문장까지 추가
    if len(result) < 80 and len(meaningful_sentences) > 2:
        result += ' ' + meaningful_sentences[2]
    
    return result.strip()

# =============================================================================
# 🔥 핵심 수정: 게시글 내용 추출 함수 - 본문 추출 로직 완전 개선
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome, 
                          source: str = "stove_korea_bug", 
                          schedule_type: str = "frequent") -> str:
    """스토브 게시글 내용 추출 - 본문 추출 로직 완전 개선 v3.6"""
    
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
        
        # 단계별 스크롤링
        print("[DEBUG] 단계별 스크롤링 시작...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        print("[DEBUG] 단계별 스크롤링 완료")
        
        # 스토브 게시글 내용 추출용 CSS Selector (0714 성공 버전)
        content_selectors = [
            # Vue.js 메타 태그에서 본문 추출 (최우선)
            'meta[data-vmid="description"]',
            'meta[name="description"]',
    
            # 백업 선택자들
            'div.s-article-content',
            'div.s-article-content-text',
            'section.s-article-body',
            'div.s-board-content'            
        ]
           
        # 🚀 핵심 개선: 의미있는 본문 추출 알고리즘
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
                                            
                        # 🔥 개선 1: 메타데이터 필터링 강화
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
                        
                        # 🔥 개선 2: 의미있는 문단 추출 (첫 문장 → 문단 조합)
                        meaningful_content = extract_meaningful_content(raw_text)
                        
                        # 🔥 개선 3: 최소 길이 50자 이상으로 증가
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
# 스토브 게시판 크롤링 함수 - CSS Selector 수정
# =============================================================================

def crawl_stove_board(board_url: str, source: str, force_crawl: bool = False, 
                     schedule_type: str = "frequent", region: str = "korea") -> List[Dict]:
    """스토브 게시판 크롤링 - CSS Selector 수정"""
    
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[INFO] {source} 크롤링 시작 - URL: {board_url}")
    print(f"[DEBUG] 기존 링크 수: {len(crawled_links)}, Force Crawl: {force_crawl}")
    
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
        
        # 게시글 목록 영역까지 스크롤
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)
        
        # 디버깅용 HTML 저장
        debug_filename = f"{source}_debug_selenium.html"
        with open(debug_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"[DEBUG] HTML 저장: {debug_filename}")
        
        # JavaScript CSS Selector 수정
        user_posts = driver.execute_script("""
            var userPosts = [];
            
            // 수정된 선택자 우선순위 (section.s-board-item 최우선)
            const selectors = [
                'section.s-board-item',           // ✅ 0714 성공 선택자 (최우선)
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
                        console.log('선택자 성공:', selectors[i], '개수:', elements.length);
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
                    var linkElement, titleElement;
                    var href = '', title = '';
                    
                    // 링크 요소 찾기
                    if (successful_selector === 'section.s-board-item') {
                        // section 기반 추출
                        linkElement = element.querySelector('a[href*="/view/"]');
                        titleElement = element.querySelector('.s-board-title-text, .board-title, h3 span, .title');
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
                        selector_used: successful_selector
                    });
                    
                    console.log('유저 게시글 추가:', title.substring(0, 30));
                    
                } catch (e) {
                    console.log('게시글 처리 오류:', e.message);
                    continue;
                }
            }
            
            console.log('최종 추출된 유저 게시글 수:', userPosts.length);
            return userPosts;
        """)
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 게시글 발견")
        
        # 각 게시글 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                post_id = post_info['id']
                
                # URL 버그 수정 적용
                href = fix_url_bug(href)
                
                print(f"[DEBUG] 게시글 {i}/{len(user_posts)}: {title[:40]}...")
                print(f"[DEBUG] URL: {href}")
                
                # 중복 확인 (force_crawl이 False인 경우)
                if not force_crawl and href in crawled_links:
                    print(f"[SKIP] 이미 크롤링된 링크: {post_id}")
                    continue
                
                # 제목 길이 검증
                if len(title) < 5:
                    print(f"[SKIP] 제목이 너무 짧음: {title}")
                    continue
                
                # 🔥 핵심: 개선된 본문 추출 함수 사용
                content = get_stove_post_content(href, driver, source, schedule_type)
                
                # 게시글 데이터 구성
                post_data = {
                    "title": title,
                    "url": href,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "source": source,
                    "id": post_id,
                    "region": region,
                    "schedule_type": schedule_type
                }
                
                posts.append(post_data)
                crawled_links.append(href)
                
                print(f"[SUCCESS] 새 게시글 추가 ({i}): {title[:30]}...")
                print(f"[CONTENT] {content[:80]}...")
                
                # 크롤링 간 대기 (Rate Limiting)
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"[ERROR] 게시글 {i} 처리 중 오류: {e}")
                continue
        
        print(f"[INFO] {source} 크롤링 완료: {len(user_posts)}개 중 {len(posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] {source} 크롤링 실패: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

# =============================================================================
# 통합 크롤링 함수들
# =============================================================================

def crawl_frequent_sites(force_crawl: bool = False) -> List[Dict]:
    """15분 주기 - 버그 게시판 전용 크롤링"""
    all_posts = []
    
    print("[INFO] === 15분 주기: 버그 게시판 크롤링 시작 ===")
    
    try:
        # 한국 버그 게시판
        stove_kr_bug_posts = crawl_stove_board(
            board_url="https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST",
            source="stove_korea_bug",
            force_crawl=force_crawl,
            schedule_type="frequent",
            region="korea"
        )
        all_posts.extend(stove_kr_bug_posts)
        print(f"[INFO] 한국 버그 게시판: {len(stove_kr_bug_posts)}개")
        
        # 크롤링 간 대기
        time.sleep(random.uniform(8, 12))
        
        # 글로벌 버그 게시판
        stove_global_bug_posts = crawl_stove_board(
            board_url="https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST",
            source="stove_global_bug",
            force_crawl=force_crawl,
            schedule_type="frequent", 
            region="global"
        )
        all_posts.extend(stove_global_bug_posts)
        print(f"[INFO] 글로벌 버그 게시판: {len(stove_global_bug_posts)}개")
        
    except Exception as e:
        print(f"[ERROR] 버그 게시판 크롤링 실패: {e}")
    
    print(f"[INFO] === 15분 주기 완료: 총 {len(all_posts)}개 새 게시글 ===")
    return all_posts

def crawl_regular_sites(force_crawl: bool = False) -> List[Dict]:
    """30분 주기 - 일반 게시판 크롤링 (감성 분석용)"""
    all_posts = []
    
    print("[INFO] === 30분 주기: 일반 게시판 크롤링 시작 ===")
    
    try:
        # 한국 자유게시판
        stove_kr_general_posts = crawl_stove_board(
            board_url="https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST",
            source="stove_korea_general", 
            force_crawl=force_crawl,
            schedule_type="regular",
            region="korea"
        )
        all_posts.extend(stove_kr_general_posts)
        print(f"[INFO] 한국 자유게시판: {len(stove_kr_general_posts)}개")
        
        time.sleep(random.uniform(8, 12))
        
        # 글로벌 자유게시판
        stove_global_general_posts = crawl_stove_board(
            board_url="https://page.onstove.com/epicseven/global/list/989?page=1&direction=LATEST",
            source="stove_global_general",
            force_crawl=force_crawl,
            schedule_type="regular",
            region="global"
        )
        all_posts.extend(stove_global_general_posts)
        print(f"[INFO] 글로벌 자유게시판: {len(stove_global_general_posts)}개")
        
        time.sleep(random.uniform(8, 12))
        
        # 루리웹 (추가)
        ruliweb_posts = crawl_ruliweb_epic7()
        all_posts.extend(ruliweb_posts)
        print(f"[INFO] 루리웹: {len(ruliweb_posts)}개")
        
    except Exception as e:
        print(f"[ERROR] 일반 게시판 크롤링 실패: {e}")
    
    print(f"[INFO] === 30분 주기 완료: 총 {len(all_posts)}개 새 게시글 ===")
    return all_posts

def crawl_by_schedule(schedule_type: str, force_crawl: bool = False) -> List[Dict]:
    """스케줄 타입에 따른 크롤링 분기"""
    
    if schedule_type == "frequent" or schedule_type == "15min":
        return crawl_frequent_sites(force_crawl)
    elif schedule_type == "regular" or schedule_type == "30min":
        return crawl_regular_sites(force_crawl)
    else:
        print(f"[ERROR] 알 수 없는 스케줄 타입: {schedule_type}")
        return []

def get_all_posts_for_report() -> List[Dict]:
    """리포트용 - 모든 사이트 크롤링"""
    print("[INFO] === 리포트용 전체 크롤링 시작 ===")
    
    all_posts = []
    all_posts.extend(crawl_frequent_sites(force_crawl=True))
    all_posts.extend(crawl_regular_sites(force_crawl=True))
    
    print(f"[INFO] === 리포트용 크롤링 완료: 총 {len(all_posts)}개 ===")
    return all_posts

# =============================================================================
# 루리웹 크롤링 (보조)
# =============================================================================

def crawl_ruliweb_epic7() -> List[Dict]:
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    
    driver = None
    try:
        driver = get_chrome_driver()
        
        url = "https://bbs.ruliweb.com/game/84834"
        driver.get(url)
        time.sleep(CrawlingSchedule.RULIWEB_WAIT_TIME)
        
        selectors = [
            ".subject_link",
            ".table_body .subject a", 
            "td.subject a",
            "a[href*='/read/']"
        ]
        
        articles = []
        for selector in selectors:
            try:
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    break
            except:
                continue
        
        link_data = load_crawled_links()
        crawled_links = link_data["links"]
        
        for article in articles[:10]:
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 5:
                    continue
                
                if any(keyword in title for keyword in ['공지', '이벤트', '추천']):
                    continue
                
                if link.startswith('/'):
                    link = 'https://bbs.ruliweb.com' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": "루리웹 게시글 - 링크에서 확인",
                        "timestamp": datetime.now().isoformat(),
                        "source": "ruliweb_epic7",
                        "region": "korea"
                    }
                    posts.append(post_data)
                    crawled_links.append(link)
                
            except Exception as e:
                print(f"[ERROR] 루리웹 게시글 처리 실패: {e}")
                continue
        
        link_data["links"] = crawled_links
        save_crawled_links(link_data)
        
    except Exception as e:
        print(f"[ERROR] 루리웹 크롤링 실패: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

# =============================================================================
# 테스트 함수
# =============================================================================

def test_crawling():
    """크롤링 테스트 함수"""
    print("=== Epic7 크롤링 테스트 v3.6 - 본문 추출 최적화 ===")
    
    # 환경 설정 확인
    print(f"스케줄 대기시간: FREQUENT={CrawlingSchedule.FREQUENT_WAIT_TIME}초, REGULAR={CrawlingSchedule.REGULAR_WAIT_TIME}초")
    
    # 15분 주기 테스트
    print("\n[TEST] 15분 주기 - 버그 게시판 테스트")
    bug_posts = crawl_frequent_sites(force_crawl=True)
    
    # 30분 주기 테스트
    print("\n[TEST] 30분 주기 - 일반 게시판 테스트") 
    regular_posts = crawl_regular_sites(force_crawl=True)
    
    # 결과 출력
    print(f"\n=== 테스트 결과 ===")
    print(f"버그 게시판: {len(bug_posts)}개")
    print(f"일반 게시판: {len(regular_posts)}개") 
    print(f"총 합계: {len(bug_posts + regular_posts)}개")
    
    # 샘플 출력
    all_posts = bug_posts + regular_posts
    print(f"\n=== 샘플 게시글 (최대 5개) ===")
    for i, post in enumerate(all_posts[:5], 1):
        print(f"{i}. [{post['source']}] {post['title'][:50]}...")
        print(f"   내용: {post['content'][:70]}...")
        print(f"   URL: {post['url']}")
        print()
    
    return all_posts

if __name__ == "__main__":
    test_crawling()