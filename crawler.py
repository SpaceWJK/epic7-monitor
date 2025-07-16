#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 모니터링 시스템 크롤링 엔진 (완전 수정 버전)
Korean/Global 모드 분기 처리와 글로벌 크롤링 함수 완전 구현

Author: Epic7 Monitoring Team
Version: 2.1.0
Date: 2025-07-16
"""

import json
import os
import sys
import time
import random
import hashlib
import re
import requests
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

# HTML 파싱
from bs4 import BeautifulSoup

# 로깅 설정
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 모드 기반 파일 분리 시스템
# =============================================================================

def get_file_paths(mode: str = "korean"):
    """모드에 따른 파일 경로 반환"""
    is_debug = os.environ.get('GITHUB_WORKFLOW', '').lower() in ['debug', 'test']
    
    if mode == "korean":
        links_file = "crawled_links_korean_debug.json" if is_debug else "crawled_links_korean.json"
        cache_file = "content_cache_korean_debug.json" if is_debug else "content_cache_korean.json"
    elif mode == "global":
        links_file = "crawled_links_global_debug.json" if is_debug else "crawled_links_global.json"
        cache_file = "content_cache_global_debug.json" if is_debug else "content_cache_global.json"
    else:  # all mode
        links_file = "crawled_links_debug.json" if is_debug else "crawled_links.json"
        cache_file = "content_cache_debug.json" if is_debug else "content_cache.json"
    
    return links_file, cache_file

def load_crawled_links(mode: str = "korean"):
    """모드별 크롤링된 링크들을 로드"""
    links_file, _ = get_file_paths(mode)
    
    if os.path.exists(links_file):
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"links": data, "last_updated": datetime.now().isoformat()}
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning(f"{links_file} 파일 읽기 실패, 새로 생성")
    
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data, mode: str = "korean"):
    """모드별 크롤링된 링크들을 저장 (최대 1000개 유지)"""
    links_file, _ = get_file_paths(mode)
    
    try:
        if len(link_data["links"]) > 1000:
            link_data["links"] = link_data["links"][-1000:]
        
        link_data["last_updated"] = datetime.now().isoformat()
        
        with open(links_file, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"{links_file} 저장 완료: {len(link_data['links'])}개 링크")
    except Exception as e:
        logger.error(f"{links_file} 저장 실패: {e}")

def load_content_cache(mode: str = "korean"):
    """모드별 게시글 내용 캐시 로드"""
    _, cache_file = get_file_paths(mode)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning(f"{cache_file} 파일 읽기 실패, 새로 생성")
    
    return {}

def save_content_cache(cache_data, mode: str = "korean"):
    """모드별 게시글 내용 캐시 저장"""
    _, cache_file = get_file_paths(mode)
    
    try:
        # 캐시 크기 제한 (최대 500개)
        if len(cache_data) > 500:
            sorted_items = sorted(cache_data.items(), key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache_data = dict(sorted_items[:500])
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"{cache_file} 저장 완료: {len(cache_data)}개 캐시")
    except Exception as e:
        logger.error(f"{cache_file} 저장 실패: {e}")

# =============================================================================
# 유틸리티 함수들
# =============================================================================

def get_url_hash(url: str) -> str:
    """URL의 해시값 생성"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def extract_content_summary(content: str) -> str:
    """게시글 내용을 한 줄로 요약"""
    if not content or len(content.strip()) < 10:
        return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    # 내용 정리
    content = re.sub(r'\s+', ' ', content.strip())
    content = re.sub(r'[^\w\s가-힣.,!?]', '', content)
    
    # 첫 문장 추출
    sentences = re.split(r'[.!?]', content)
    first_sentence = sentences[0].strip() if sentences else content
    
    if len(first_sentence) > 100:
        first_sentence = first_sentence[:97] + '...'
    elif len(first_sentence) > 10:
        first_sentence = first_sentence + '...'
    
    return first_sentence if first_sentence else "게시글 내용 확인을 위해 링크를 클릭하세요."

def fix_stove_url(url):
    """스토브 URL 수정 함수"""
    if not url:
        return url
    
    if url.startswith('ttps://'):
        url = 'h' + url
    elif url.startswith('ttp://'):
        url = 'h' + url
    elif url.startswith('/'):
        url = 'https://page.onstove.com' + url
    elif not url.startswith('http'):
        url = 'https://page.onstove.com' + ('/' if not url.startswith('/') else '') + url
    
    return url

def retry_on_failure(max_retries: int = 3, delay: float = 2.0):
    """재시도 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} 시도 {attempt + 1}/{max_retries} 실패: {e}")
                        time.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"{func.__name__} 최종 실패: {e}")
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

# =============================================================================
# Chrome 드라이버 관리 (Chrome 138+ 호환성)
# =============================================================================

@retry_on_failure(max_retries=3, delay=1.0)
def get_chrome_driver():
    """Chrome 드라이버 초기화 (Chrome 138+ 호환성 완전 적용)"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User Agent 설정
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    
    # 프리퍼런스 설정
    prefs = {
        'profile.default_content_setting_values': {
            'images': 2,
            'plugins': 2,
            'popups': 2,
            'geolocation': 2,
            'notifications': 2,
            'media_stream': 2,
        }
    }
    options.add_experimental_option('prefs', prefs)
    
    # ChromeDriver 경로 시도
    possible_paths = [
        '/usr/local/bin/chromedriver',
        '/usr/bin/chromedriver',
        '/snap/bin/chromium.chromedriver',
        '/opt/chrome/chromedriver'
    ]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(45)
                driver.implicitly_wait(15)
                logger.info(f"ChromeDriver 초기화 성공: {path}")
                return driver
        except Exception as e:
            logger.debug(f"ChromeDriver 경로 {path} 실패: {str(e)[:100]}...")
            continue
    
    # 시스템 기본 ChromeDriver 시도
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(15)
        logger.info("시스템 기본 ChromeDriver 초기화 성공")
        return driver
    except Exception as e:
        logger.debug(f"시스템 기본 ChromeDriver 실패: {str(e)[:100]}...")
       
    raise Exception("ChromeDriver 초기화 실패 - 시스템 ChromeDriver를 확인하세요.")

# =============================================================================
# Discord 관련 함수들 (누락된 함수 완전 구현)
# =============================================================================

def check_discord_webhooks():
    """Discord 웹훅 환경변수 확인"""
    webhooks = {}
    
    # 버그 알림 웹훅
    bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
    if bug_webhook:
        webhooks['bug'] = bug_webhook
        logger.info("Discord 버그 알림 웹훅 확인됨")
    
    # 감성 알림 웹훅
    sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
    if sentiment_webhook:
        webhooks['sentiment'] = sentiment_webhook
        logger.info("Discord 감성 알림 웹훅 확인됨")
    
    # 리포트 웹훅
    report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
    if report_webhook:
        webhooks['report'] = report_webhook
        logger.info("Discord 리포트 웹훅 확인됨")
    
    if not webhooks:
        logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다.")
    
    return webhooks

def send_discord_message(webhook_url: str, message: str, title: str = "Epic7 모니터링"):
    """Discord 메시지 전송"""
    if not webhook_url:
        logger.error("Discord 웹훅 URL이 없습니다.")
        return False
    
    try:
        # 메시지 길이 제한 (Discord 한계 고려)
        if len(message) > 1900:
            message = message[:1900] + "\n...(메시지 길이 초과로 생략)"
        
        # Discord 웹훅 페이로드
        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": 0x3498db,
                    "timestamp": datetime.now().isoformat(),
                    "footer": {
                        "text": "Epic7 모니터링 시스템"
                    }
                }
            ]
        }
        
        # 웹훅 전송
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            logger.info("Discord 메시지 전송 성공")
            return True
        else:
            logger.error(f"Discord 메시지 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Discord 메시지 전송 중 오류: {e}")
        return False

def get_file_path(mode: str = "korean"):
    """호환성을 위한 wrapper 함수 - get_file_paths의 첫 번째 값만 반환"""
    links_file, cache_file = get_file_paths(mode)
    return links_file

# =============================================================================
# 게시글 내용 추출 함수
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome = None, mode: str = "korean") -> str:
    """스토브 게시글 내용 추출 (강화된 버전)"""
    cache = load_content_cache(mode)
    url_hash = get_url_hash(post_url)
    
    # 캐시 확인
    if url_hash in cache:
        cached_item = cache[url_hash]
        cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
        if datetime.now() - cache_time < timedelta(hours=24):
            return cached_item.get('content', "게시글 내용 확인을 위해 링크를 클릭하세요.")
    
    # 드라이버 초기화
    driver_created = False
    if driver is None:
        try:
            driver = get_chrome_driver()
            driver_created = True
        except Exception as e:
            logger.error(f"Driver 생성 실패: {e}")
            return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    content_summary = "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    try:
        driver.get(post_url)
        time.sleep(10)  # 페이지 로딩 대기
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링으로 콘텐츠 로딩
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(3)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        
        # 콘텐츠 선택자들
        content_selectors = [
            'div.s-article-content',
            'div.s-article-content-text',
            'div[class*="s-article-content"]',
            'section.s-article-body',
            'div.s-board-content',
            'div.article-content',
            'div.post-content',
            'div.content-body',
            'main.content',
            'div[class*="text-content"]',
            'div[class*="post-body"]',
            'div[class*="article-body"]'
        ]
        
        extracted_content = ""
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 50:
                            if not any(skip_text in text.lower() for skip_text in ['install stove', '스토브를 설치', '로그인이 필요', 'javascript']):
                                extracted_content = text
                                break
                    if extracted_content:
                        break
            except Exception:
                continue
        
        # 내용 처리
        if extracted_content:
            lines = extracted_content.split('\n')
            meaningful_lines = []
            for line in lines:
                line = line.strip()
                if (len(line) > 15 and 
                    '로그인' not in line and 
                    '회원가입' not in line and 
                    '메뉴' not in line and 
                    '검색' not in line and 
                    '공지사항' not in line and 
                    '이벤트' not in line and 
                    'Install STOVE' not in line and 
                    '스토브를 설치' not in line):
                    meaningful_lines.append(line)
            
            if meaningful_lines:
                longest_line = max(meaningful_lines, key=len)
                if len(longest_line) > 20:
                    content_summary = extract_content_summary(longest_line)
                else:
                    content_summary = extract_content_summary(meaningful_lines[0])
        
        # JavaScript 추출 시도
        if content_summary == "게시글 내용 확인을 위해 링크를 클릭하세요.":
            try:
                js_content = driver.execute_script("""
                var contentElements = [
                    document.querySelector('div.s-article-content'),
                    document.querySelector('div[class*="article-content"]'),
                    document.querySelector('div[class*="post-content"]'),
                    document.querySelector('main'),
                    document.querySelector('article')
                ];
                
                for (var i = 0; i < contentElements.length; i++) {
                    var element = contentElements[i];
                    if (element && element.innerText) {
                        var text = element.innerText.trim();
                        if (text.length > 50 && 
                            !text.toLowerCase().includes('install stove') && 
                            !text.includes('스토브를 설치') && 
                            !text.includes('로그인이 필요')) {
                            return text;
                        }
                    }
                }
                return '';
                """)
                
                if js_content and len(js_content.strip()) > 50:
                    content_summary = extract_content_summary(js_content)
            except Exception as e:
                logger.error(f"JavaScript 추출 실패: {e}")
        
        # BeautifulSoup 추출 시도
        if content_summary == "게시글 내용 확인을 위해 링크를 클릭하세요.":
            try:
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                stove_content_tags = [
                    soup.find('div', class_='s-article-content'),
                    soup.find('div', class_='s-article-content-text'),
                    soup.find('section', class_='s-article-body'),
                    soup.find('div', class_='s-board-content')
                ]
                
                for tag in stove_content_tags:
                    if tag:
                        text = tag.get_text(strip=True)
                        if text and len(text) > 50:
                            if not any(skip in text.lower() for skip in ['install stove', '스토브를 설치']):
                                content_summary = extract_content_summary(text)
                                break
            except Exception as e:
                logger.error(f"BeautifulSoup 추출 실패: {e}")
        
        # 캐시 저장
        cache[url_hash] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url
        }
        save_content_cache(cache, mode)
        
    except TimeoutException:
        logger.error(f"페이지 로딩 타임아웃: {post_url}")
        content_summary = "⏰ 게시글 로딩 시간 초과. 링크를 클릭하여 확인하세요."
    except Exception as e:
        logger.error(f"게시글 내용 추출 실패: {e}")
        content_summary = "🔗 게시글 내용 확인을 위해 링크를 클릭하세요."
    finally:
        if driver_created and driver:
            try:
                driver.quit()
            except:
                pass
    
    return content_summary

# =============================================================================
# 한국 사이트 크롤링 함수들
# =============================================================================

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_bug_board(mode: str = "korean"):
    """스토브 에픽세븐 버그 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"스토브 버그 게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        driver.get(url)
        time.sleep(15)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링으로 게시글 로딩
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(3)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        
        # JavaScript로 게시글 추출
        user_posts = driver.execute_script("""
        var posts = [];
        var items = document.querySelectorAll('section.s-board-item');
        
        for (var i = 0; i < Math.min(items.length, 15); i++) {
            var item = items[i];
            var link = item.querySelector('a[href*="/view/"]');
            var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
            
            if (link && title && link.href && title.innerText) {
                var titleText = title.innerText.trim();
                if (titleText.length > 3) {
                    var isNotice = item.querySelector('.notice, [class*="notice"]');
                    var isEvent = item.querySelector('.event, [class*="event"]');
                    if (!isNotice && !isEvent) {
                        posts.push({
                            title: titleText,
                            href: link.href,
                            id: link.href.split('/').pop()
                        });
                    }
                }
            }
        }
        return posts;
        """)
        
        # 게시글 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href in crawled_links:
                    continue
                
                if title and href and len(title) > 3:
                    content = get_stove_post_content(href, driver, mode)
                    
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_bug",
                        "site": "STOVE 버그신고"
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(href)
                    
                    logger.info(f"스토브 버그 새 게시글: {title[:50]}...")
                    time.sleep(random.uniform(2, 4))
                    
            except Exception as e:
                logger.error(f"스토브 버그 게시글 {i} 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"스토브 버그 게시판 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_general_board(mode: str = "korean"):
    """스토브 에픽세븐 자유게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"스토브 자유게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST"
        driver.get(url)
        time.sleep(15)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링으로 게시글 로딩
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(3)
        
        # JavaScript로 게시글 추출
        user_posts = driver.execute_script("""
        var posts = [];
        var items = document.querySelectorAll('section.s-board-item');
        
        for (var i = 0; i < Math.min(items.length, 15); i++) {
            var item = items[i];
            var link = item.querySelector('a[href*="/view/"]');
            var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
            
            if (link && title && link.href && title.innerText) {
                var titleText = title.innerText.trim();
                if (titleText.length > 3) {
                    var isNotice = item.querySelector('.notice, [class*="notice"]');
                    var isEvent = item.querySelector('.event, [class*="event"]');
                    if (!isNotice && !isEvent) {
                        posts.push({
                            title: titleText,
                            href: link.href
                        });
                    }
                }
            }
        }
        return posts;
        """)
        
        # 게시글 처리
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href in crawled_links:
                    continue
                
                if not title or len(title) < 4:
                    continue
                
                # 의미없는 제목 필터링
                meaningless_patterns = [
                    r'^[.]{3,}$',
                    r'^[ㅋㅎㅗㅜㅑ]{3,}$',
                    r'^[!@#$%^&*()]{3,}$',
                ]
                
                is_meaningless = any(re.match(pattern, title) for pattern in meaningless_patterns)
                if is_meaningless:
                    continue
                
                content = get_stove_post_content(href, driver, mode)
                
                post_data = {
                    "title": title,
                    "url": href,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "source": "stove_general",
                    "site": "STOVE 자유게시판"
                }
                
                posts.append(post_data)
                crawled_links.append(href)
                
                logger.info(f"스토브 자유게시판 새 게시글: {title[:50]}...")
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"스토브 자유게시판 게시글 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"스토브 자유게시판 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_ruliweb_epic7_board(mode: str = "korean"):
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"루리웹 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://bbs.ruliweb.com/game/84834"
        driver.get(url)
        time.sleep(10)
        
        # 다양한 선택자 시도
        selectors = [
            ".subject_link",
            ".table_body .subject a",
            "td.subject a",
            "a[href*='/read/']",
            ".board_list_table .subject_link",
            "table tr td a[href*='read']"
        ]
        
        articles = []
        for selector in selectors:
            try:
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    logger.info(f"루리웹 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        if not articles:
            logger.warning("루리웹 게시글을 찾을 수 없음")
            return posts
        
        # 게시글 처리
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                # 공지사항 제외
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천', '베스트', '공지사항']):
                    continue
                
                # 상대 경로 처리
                if link.startswith('/'):
                    link = 'https://bbs.ruliweb.com' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": "루리웹 게시글 내용 확인을 위해 링크를 클릭하세요.",
                        "timestamp": datetime.now().isoformat(),
                        "source": "ruliweb_epic7",
                        "site": "루리웹"
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(link)
                    
                    logger.info(f"루리웹 새 게시글: {title[:50]}...")
                    
            except Exception as e:
                logger.error(f"루리웹 게시글 {i+1} 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"루리웹 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_arca_epic7_board(mode: str = "korean"):
    """아카라이브 에픽세븐 채널 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"아카라이브 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://arca.live/b/epic7"
        driver.get(url)
        time.sleep(10)
        
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)
        
        # 다양한 선택자 시도
        selectors = [
            ".vrow .title a",
            ".vrow-inner .title a",
            "a[href*='/b/epic7/']",
            ".article-title a",
            ".list-table .title a"
        ]
        
        articles = []
        for selector in selectors:
            try:
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    logger.info(f"아카라이브 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        if not articles:
            logger.warning("아카라이브 게시글을 찾을 수 없음")
            return posts
        
        # 게시글 처리
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                # 공지사항 제외
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천', '베스트']):
                    continue
                
                # 상대 경로 처리
                if link.startswith('/'):
                    link = 'https://arca.live' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": "아카라이브 게시글 내용 확인을 위해 링크를 클릭하세요.",
                        "timestamp": datetime.now().isoformat(),
                        "source": "arca_epic7",
                        "site": "아카라이브"
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(link)
                    
                    logger.info(f"아카라이브 새 게시글: {title[:50]}...")
                    
            except Exception as e:
                logger.error(f"아카라이브 게시글 {i+1} 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"아카라이브 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

# =============================================================================
# 글로벌 사이트 크롤링 함수들
# =============================================================================

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_global_bug_board(mode: str = "global"):
    """STOVE 글로벌 버그 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"STOVE 글로벌 버그 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST"
        driver.get(url)
        time.sleep(15)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링으로 게시글 로딩
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(3)
        
        # JavaScript로 게시글 추출
        user_posts = driver.execute_script("""
        var posts = [];
        var items = document.querySelectorAll('section.s-board-item');
        
        for (var i = 0; i < Math.min(items.length, 15); i++) {
            var item = items[i];
            var link = item.querySelector('a[href*="/view/"]');
            var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
            
            if (link && title && link.href && title.innerText) {
                var titleText = title.innerText.trim();
                if (titleText.length > 3) {
                    var isNotice = item.querySelector('.notice, [class*="notice"]');
                    var isEvent = item.querySelector('.event, [class*="event"]');
                    if (!isNotice && !isEvent) {
                        posts.push({
                            title: titleText,
                            href: link.href
                        });
                    }
                }
            }
        }
        return posts;
        """)
        
        # 게시글 처리
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href in crawled_links:
                    continue
                
                content = get_stove_post_content(href, driver, mode)
                
                post_data = {
                    "title": title,
                    "url": href,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "source": "stove_global_bug",
                    "site": "STOVE Global Bug"
                }
                
                posts.append(post_data)
                crawled_links.append(href)
                
                logger.info(f"STOVE 글로벌 버그 새 게시글: {title[:50]}...")
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"STOVE 글로벌 버그 게시글 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"STOVE 글로벌 버그 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_global_general_board(mode: str = "global"):
    """STOVE 글로벌 자유게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"STOVE 글로벌 자유게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/global/list/989?page=1&direction=LATEST"
        driver.get(url)
        time.sleep(15)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링으로 게시글 로딩
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(3)
        
        # JavaScript로 게시글 추출
        user_posts = driver.execute_script("""
        var posts = [];
        var items = document.querySelectorAll('section.s-board-item');
        
        for (var i = 0; i < Math.min(items.length, 15); i++) {
            var item = items[i];
            var link = item.querySelector('a[href*="/view/"]');
            var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
            
            if (link && title && link.href && title.innerText) {
                var titleText = title.innerText.trim();
                if (titleText.length > 3) {
                    var isNotice = item.querySelector('.notice, [class*="notice"]');
                    var isEvent = item.querySelector('.event, [class*="event"]');
                    if (!isNotice && !isEvent) {
                        posts.push({
                            title: titleText,
                            href: link.href
                        });
                    }
                }
            }
        }
        return posts;
        """)
        
        # 게시글 처리
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href in crawled_links:
                    continue
                
                content = get_stove_post_content(href, driver, mode)
                
                post_data = {
                    "title": title,
                    "url": href,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "source": "stove_global_general",
                    "site": "STOVE Global General"
                }
                
                posts.append(post_data)
                crawled_links.append(href)
                
                logger.info(f"STOVE 글로벌 자유게시판 새 게시글: {title[:50]}...")
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"STOVE 글로벌 자유게시판 게시글 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"STOVE 글로벌 자유게시판 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_reddit_epic7_board(mode: str = "global"):
    """Reddit r/EpicSeven 최신글 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"Reddit 크롤링 시작 (mode: {mode})")
    
    try:
        url = "https://www.reddit.com/r/EpicSeven/new.json?limit=20"
        headers = {
            "User-Agent": "Epic7MonitorBot/2.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' in data and 'children' in data['data']:
            for child in data['data']['children']:
                try:
                    item = child['data']
                    title = item.get('title', '').strip()
                    permalink = "https://www.reddit.com" + item.get('permalink', '')
                    
                    if not title or not permalink or len(title) < 3:
                        continue
                    
                    if permalink in crawled_links:
                        continue
                    
                    post_data = {
                        "title": title,
                        "url": permalink,
                        "content": f"Reddit 게시글: {title[:100]}...",
                        "timestamp": datetime.now().isoformat(),
                        "source": "reddit_epic7",
                        "site": "Reddit"
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(permalink)
                    
                    logger.info(f"Reddit 새 게시글: {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Reddit 게시글 처리 오류: {e}")
                    continue
                    
    except requests.RequestException as e:
        logger.error(f"Reddit API 요청 실패: {e}")
    except Exception as e:
        logger.error(f"Reddit 크롤링 실패: {e}")
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_epic7_official_forum(mode: str = "global"):
    """Epic7 공식 포럼 크롤링 (함수명 수정됨)"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"Epic7 공식 포럼 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://epic7.gg/forum"
        driver.get(url)
        time.sleep(15)
        
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)
        
        # 다양한 선택자 시도
        selectors = [
            ".topic-title a",
            ".forum-post-title a",
            "a[href*='/topic/']",
            ".post-title a",
            ".thread-title a"
        ]
        
        articles = []
        for selector in selectors:
            try:
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    logger.info(f"공식 포럼 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        if not articles:
            logger.warning("공식 포럼 게시글을 찾을 수 없음")
            return posts
        
        # 게시글 처리
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                # 상대 경로 처리
                if link.startswith('/'):
                    link = 'https://epic7.gg' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": "Epic7 공식 포럼 게시글 내용 확인을 위해 링크를 클릭하세요.",
                        "timestamp": datetime.now().isoformat(),
                        "source": "epic7_official_forum",
                        "site": "Epic7 공식 포럼"
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(link)
                    
                    logger.info(f"공식 포럼 새 게시글: {title[:50]}...")
                    
            except Exception as e:
                logger.error(f"공식 포럼 게시글 {i+1} 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"공식 포럼 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

# =============================================================================
# 통합 크롤링 함수들
# =============================================================================

def crawl_korean_sites(mode: str = "korean"):
    """한국 사이트 통합 크롤링"""
    logger.info(f"한국 사이트 통합 크롤링 시작 (mode: {mode})")
    
    all_posts = []
    
    # 스토브 버그 게시판
    try:
        stove_bug_posts = fetch_stove_bug_board(mode)
        all_posts.extend(stove_bug_posts)
        logger.info(f"스토브 버그 게시판: {len(stove_bug_posts)}개 게시글")
    except Exception as e:
        logger.error(f"스토브 버그 게시판 크롤링 실패: {e}")
    
    # 스토브 자유게시판
    try:
        stove_general_posts = fetch_stove_general_board(mode)
        all_posts.extend(stove_general_posts)
        logger.info(f"스토브 자유게시판: {len(stove_general_posts)}개 게시글")
    except Exception as e:
        logger.error(f"스토브 자유게시판 크롤링 실패: {e}")
    
    # 루리웹
    try:
        ruliweb_posts = fetch_ruliweb_epic7_board(mode)
        all_posts.extend(ruliweb_posts)
        logger.info(f"루리웹: {len(ruliweb_posts)}개 게시글")
    except Exception as e:
        logger.error(f"루리웹 크롤링 실패: {e}")
    
    # 아카라이브
    try:
        arca_posts = fetch_arca_epic7_board(mode)
        all_posts.extend(arca_posts)
        logger.info(f"아카라이브: {len(arca_posts)}개 게시글")
    except Exception as e:
        logger.error(f"아카라이브 크롤링 실패: {e}")
    
    logger.info(f"한국 사이트 통합 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_global_sites(mode: str = "global"):
    """글로벌 사이트 통합 크롤링"""
    logger.info(f"글로벌 사이트 통합 크롤링 시작 (mode: {mode})")
    
    all_posts = []
    
    # STOVE 글로벌 버그 게시판
    try:
        stove_global_bug_posts = fetch_stove_global_bug_board(mode)
        all_posts.extend(stove_global_bug_posts)
        logger.info(f"STOVE 글로벌 버그: {len(stove_global_bug_posts)}개 게시글")
    except Exception as e:
        logger.error(f"STOVE 글로벌 버그 크롤링 실패: {e}")
    
    # STOVE 글로벌 자유게시판
    try:
        stove_global_general_posts = fetch_stove_global_general_board(mode)
        all_posts.extend(stove_global_general_posts)
        logger.info(f"STOVE 글로벌 자유게시판: {len(stove_global_general_posts)}개 게시글")
    except Exception as e:
        logger.error(f"STOVE 글로벌 자유게시판 크롤링 실패: {e}")
    
    # Reddit
    try:
        reddit_posts = fetch_reddit_epic7_board(mode)
        all_posts.extend(reddit_posts)
        logger.info(f"Reddit: {len(reddit_posts)}개 게시글")
    except Exception as e:
        logger.error(f"Reddit 크롤링 실패: {e}")
    
    # Epic7 공식 포럼
    try:
        forum_posts = fetch_epic7_official_forum(mode)
        all_posts.extend(forum_posts)
        logger.info(f"Epic7 공식 포럼: {len(forum_posts)}개 게시글")
    except Exception as e:
        logger.error(f"Epic7 공식 포럼 크롤링 실패: {e}")
    
    logger.info(f"글로벌 사이트 통합 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_all_sites(mode: str = "all"):
    """모든 사이트 통합 크롤링"""
    logger.info(f"모든 사이트 통합 크롤링 시작 (mode: {mode})")
    
    all_posts = []
    
    # 한국 사이트 크롤링
    korean_posts = crawl_korean_sites("korean")
    all_posts.extend(korean_posts)
    
    # 글로벌 사이트 크롤링
    global_posts = crawl_global_sites("global")
    all_posts.extend(global_posts)
    
    logger.info(f"모든 사이트 통합 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

# =============================================================================
# 리포트 생성 함수들
# =============================================================================

def get_all_posts_for_report(mode: str = "all"):
    """리포트용 모든 게시글 수집"""
    logger.info(f"리포트용 게시글 수집 시작 (mode: {mode})")
    
    all_posts = []
    
    # 한국 사이트
    korean_posts = crawl_korean_sites("korean")
    all_posts.extend(korean_posts)
    
    # 글로벌 사이트
    global_posts = crawl_global_sites("global")
    all_posts.extend(global_posts)
    
    # 시간순 정렬
    all_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    logger.info(f"리포트용 게시글 수집 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

# =============================================================================
# 메인 실행 함수들
# =============================================================================

def main_crawl(mode: str = "korean"):
    """메인 크롤링 실행 함수"""
    logger.info(f"Epic7 모니터링 시스템 크롤링 시작 (mode: {mode})")
    
    if mode == "korean":
        return crawl_korean_sites(mode)
    elif mode == "global":
        return crawl_global_sites(mode)
    elif mode == "all":
        return crawl_all_sites(mode)
    else:
        logger.error(f"지원되지 않는 모드: {mode}")
        return []

def test_crawling():
    """크롤링 테스트 함수"""
    logger.info("크롤링 테스트 시작")
    
    # 한국 사이트 테스트
    korean_posts = crawl_korean_sites("korean")
    logger.info(f"한국 사이트 테스트 결과: {len(korean_posts)}개 게시글")
    
    # 글로벌 사이트 테스트
    global_posts = crawl_global_sites("global")
    logger.info(f"글로벌 사이트 테스트 결과: {len(global_posts)}개 게시글")
    
    logger.info("크롤링 테스트 완료")
    return korean_posts + global_posts

if __name__ == "__main__":
    # 테스트 실행
    test_crawling()