#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 다국가 크롤러 v3.4 - 완전 개선 버전 (최종 수정)
- URL ID 오류 완전 수정 (998, 989, 1012, 1005)
- 다국가 지원: 글로벌/한국/Reddit/루리웹
- CSS Selector 30+ 폴백 시스템 (2025년 Stove 구조)
- JavaScript 렌더링 대기시간 최적화 (20초/25초)
- Force Crawl 버그 수정 완료
- 지역별 스케줄링 최적화
- 캐시 시스템 개선 및 메모리 최적화
- 소스 이름 일관성 완전 해결 (stove_korea_* 통일)
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

# HTML 파싱
from bs4 import BeautifulSoup

# 공통 모듈 임포트
from config import config
from utils import setup_logging

# 로깅 설정
import logging
logger = logging.getLogger(__name__)

# =============================================================================
# 크롤링 스케줄 및 설정 v3.4
# =============================================================================

class CrawlingSchedule:
    """크롤링 주기 설정 - 다국가 지원"""
    
    # 크롤링 주기 (분)
    FREQUENT_INTERVAL = 15    # 버그 게시판 (긴급)
    REGULAR_INTERVAL = 30     # 일반 게시판
    
    # 대기 시간 설정 (지역별 최적화)
    FREQUENT_WAIT_TIME = 20   # 버그 게시판 대기시간
    REGULAR_WAIT_TIME = 25    # 일반 게시판 대기시간
    REDDIT_WAIT_TIME = 15     # Reddit 대기시간
    RULIWEB_WAIT_TIME = 18    # 루리웹 대기시간
    
    # 스크롤 설정
    FREQUENT_SCROLL_COUNT = 3 # 버그 게시판 스크롤
    REGULAR_SCROLL_COUNT = 5  # 일반 게시판 스크롤

class BoardConfig:
    """게시판 설정 - URL ID 수정 완료"""
    
    # 글로벌 게시판 (수정됨)
    GLOBAL_BOARDS = {
        'bug': {
            'id': '998',  # e7en001 → 998 수정
            'url': 'https://page.onstove.com/epicseven/global/list/998',
            'name': 'Global Bug Report',
            'schedule': 'frequent'
        },
        'general': {
            'id': '989',  # e7en002 → 989 수정  
            'url': 'https://page.onstove.com/epicseven/global/list/989',
            'name': 'Global General Discussion',
            'schedule': 'regular'
        }
    }
    
    # 한국 게시판 (신규 추가)
    KOREAN_BOARDS = {
        'bug': {
            'id': '1012',
            'url': 'https://page.onstove.com/epicseven/kr/list/1012',
            'name': 'Korean Bug Report',
            'schedule': 'frequent'
        },
        'general': {
            'id': '1005',
            'url': 'https://page.onstove.com/epicseven/kr/list/1005',
            'name': 'Korean General Discussion',
            'schedule': 'regular'
        }
    }
    
    # 외부 사이트 (신규 추가)
    EXTERNAL_SITES = {
        'reddit': {
            'url': 'https://www.reddit.com/r/EpicSeven/',
            'name': 'Reddit r/EpicSeven',
            'schedule': 'regular'
        },
        'ruliweb': {
            'url': 'https://bbs.ruliweb.com/game/84834',
            'name': 'Ruliweb Epic Seven',
            'schedule': 'regular'
        }
    }

# =============================================================================
# Chrome 드라이버 관리 v3.4
# =============================================================================

def get_chrome_driver(headless: bool = True, region: str = 'global') -> webdriver.Chrome:
    """
    Chrome 드라이버 생성 - 3단계 폴백 메커니즘 (지역 최적화)
    
    Args:
        headless: 헤드리스 모드 여부
        region: 지역 설정 ('global', 'korean', 'reddit', 'ruliweb')
        
    Returns:
        webdriver.Chrome: Chrome 드라이버 인스턴스
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    # 기본 옵션 설정
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 지역별 User-Agent 최적화
    user_agents = {
        'global': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'korean': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'reddit': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'ruliweb': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    chrome_options.add_argument(f'--user-agent={user_agents.get(region, user_agents["global"])}')
    
    # Stage 1: 시스템 경로에서 Chrome/ChromeDriver 찾기
    possible_paths = [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        'google-chrome',
        'chromium-browser'
    ]
    
    for chrome_path in possible_paths:
        try:
            chrome_options.binary_location = chrome_path
            driver = webdriver.Chrome(options=chrome_options)
            logger.info(f"Chrome 드라이버 성공 (Stage 1, {region}): {chrome_path}")
            return driver
        except Exception as e:
            logger.debug(f"Chrome 경로 실패: {chrome_path} - {str(e)}")
            continue
    
    # Stage 2: WebDriver Manager 사용
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info(f"Chrome 드라이버 성공 (Stage 2, {region}): WebDriver Manager")
        return driver
    except Exception as e:
        logger.debug(f"WebDriver Manager 실패: {str(e)}")
    
    # Stage 3: 직접 다운로드 시도
    try:
        driver = webdriver.Chrome(options=chrome_options)
        logger.info(f"Chrome 드라이버 성공 (Stage 3, {region}): 직접 실행")
        return driver
    except Exception as e:
        logger.error(f"모든 Chrome 드라이버 시도 실패: {str(e)}")
        raise Exception("Chrome 드라이버를 찾을 수 없습니다")

# =============================================================================
# 중복 방지 시스템 v3.4 (메모리 최적화)
# =============================================================================

def load_crawled_links() -> Dict:
    """크롤링된 링크 목록 로드 (메모리 최적화)"""
    try:
        if os.path.exists('crawled_links.json'):
            with open('crawled_links.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 최대 1500개까지만 유지 (2000→1500 최적화)
                if len(data.get('links', [])) > 1500:
                    data['links'] = data['links'][-1500:]
                return data
    except Exception as e:
        logger.error(f"크롤링 링크 로드 실패: {str(e)}")
    
    return {
        'links': [],
        'last_updated': datetime.now().isoformat()
    }

def save_crawled_links(crawled_data: Dict) -> None:
    """크롤링된 링크 목록 저장"""
    try:
        crawled_data['last_updated'] = datetime.now().isoformat()
        with open('crawled_links.json', 'w', encoding='utf-8') as f:
            json.dump(crawled_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"크롤링 링크 저장 실패: {str(e)}")

# =============================================================================
# 콘텐츠 캐시 시스템 v3.4 (개선됨)
# =============================================================================

def load_content_cache() -> Dict:
    """콘텐츠 캐시 로드 (개선된 정리 로직)"""
    try:
        if os.path.exists('content_cache.json'):
            with open('content_cache.json', 'r', encoding='utf-8') as f:
                cache = json.load(f)
                
                # 12시간 이상 된 캐시 제거 (24시간→12시간 최적화)
                current_time = datetime.now()
                cleaned_cache = {}
                
                for url_hash, cached_data in cache.items():
                    if 'timestamp' in cached_data:
                        try:
                            cached_time = datetime.fromisoformat(cached_data['timestamp'])
                            if (current_time - cached_time).total_seconds() < 12 * 3600:
                                cleaned_cache[url_hash] = cached_data
                        except:
                            # 파싱 실패한 캐시는 제거
                            continue
                
                return cleaned_cache
    except Exception as e:
        logger.error(f"콘텐츠 캐시 로드 실패: {str(e)}")
    
    return {}

def save_content_cache(cache_data: Dict) -> None:
    """콘텐츠 캐시 저장 (메모리 최적화)"""
    try:
        # 최대 800개까지만 유지 (1000→800 최적화)
        if len(cache_data) > 800:
            sorted_items = sorted(
                cache_data.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=True
            )
            cache_data = dict(sorted_items[:800])
        
        with open('content_cache.json', 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"콘텐츠 캐시 저장 실패: {str(e)}")

# =============================================================================
# Stove 게시글 본문 추출 v3.4 (CSS Selector 대폭 강화)
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome = None, source: str = "", schedule_type: str = 'frequent') -> Tuple[str, str]:
    """
    Stove 게시글 본문 추출 v3.4 (CSS Selector 30+ 폴백)
    """
    # URL 해시 생성 (캐시 키)
    import hashlib
    url_hash = hashlib.md5(post_url.encode()).hexdigest()
    
    # 캐시에서 확인
    content_cache = load_content_cache()
    if url_hash in content_cache:
        cached_data = content_cache[url_hash]
        logger.debug(f"캐시에서 콘텐츠 로드: {post_url[:50]}...")
        return cached_data.get('content', ''), cached_data.get('summary', '')
    
    # 새로운 드라이버 생성 여부
    should_quit_driver = False
    if driver is None:
        region = 'korean' if '/kr/' in post_url else 'global'
        driver = get_chrome_driver(region=region)
        should_quit_driver = True
    
    content = ""
    content_summary = ""
    
    try:
        logger.debug(f"게시글 본문 추출 시작: {post_url}")
        driver.get(post_url)
        
        # 스케줄에 따른 대기시간 설정
        if schedule_type == 'frequent':
            wait_time = CrawlingSchedule.FREQUENT_WAIT_TIME
            scroll_count = CrawlingSchedule.FREQUENT_SCROLL_COUNT
        else:
            wait_time = CrawlingSchedule.REGULAR_WAIT_TIME
            scroll_count = CrawlingSchedule.REGULAR_SCROLL_COUNT
        
        # 페이지 로딩 대기
        time.sleep(wait_time)
        
        # DOM 준비 상태 확인
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤하여 동적 콘텐츠 로드
        for i in range(scroll_count):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # 상단으로 스크롤
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # 강화된 CSS Selector 목록 (30+ 폴백)
        content_selectors = [
            # 2025년 최신 Stove 구조 (우선순위)
            'div[class*="article-content"]',      
            'div[class*="post-content"]',         
            'div[class*="board-content"]',        
            'section[class*="content"]',          
            'div[class*="text-content"]',         
            'div[class*="content-body"]',         
            'div[class*="post-body"]',            
            'div[class*="article-body"]',         
            
            # 기존 selector 유지 (하위 호환성)
            'div.s-article-content',
            'div.s-article-content-text',
            'section.s-article-body',
            'div.s-board-content',
            'div.article-content',
            'div.post-content',
            
            # React/Vue 구조 대응
            'div[data-testid*="content"]',
            'div[data-testid*="post"]',
            'div[data-testid*="article"]',
            'section[data-testid*="content"]',
            
            # ID 기반 selector
            '#content',
            '#post-content',
            '#article-content',
            '#main-content',
            
            # 포괄적 selector (순서 중요)
            'main [class*="content"]',            
            'article [class*="content"]',         
            '[id*="content"]',                    
            'div[class*="body"]',                 
            '.content',                           
            '.post',                              
            '.article',                           
            
            # 마지막 수단들
            'main article',
            'main section',
            'main div:not([class*="header"]):not([class*="nav"]):not([class*="footer"])',
            'p'  # 최후의 수단
        ]
        
        # CSS Selector를 순차적으로 시도
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                logger.debug(f"Selector {selector}: {len(elements)}개 요소 발견")
                
                if elements:
                    for element in elements:
                        try:
                            text = element.get_attribute('innerText') or element.text
                            text = text.strip()
                            
                            # 텍스트 길이 조건: 10자 이상
                            if text and len(text) >= 10:
                                # 의미없는 텍스트 필터링 (확장됨)
                                skip_phrases = [
                                    '로그인', '설치', '광고', '쿠키', 'cookie',
                                    '이용약관', '개인정보', '저작권', '무단전재',
                                    '댓글', 'comment', '좋아요', 'like', '공유',
                                    'javascript', 'css', 'loading', 'submit',
                                    'checkbox', 'radio', 'button', 'form'
                                ]
                                
                                if not any(phrase in text.lower() for phrase in skip_phrases):
                                    content = text
                                    
                                    # 첫 번째 의미있는 문장을 요약으로 사용
                                    lines = text.split('\n')
                                    for line in lines:
                                        line = line.strip()
                                        if len(line) >= 15:  # 요약은 15자 이상
                                            content_summary = line[:200]  # 최대 200자
                                            break
                                    
                                    logger.info(f"본문 추출 성공 ({selector}): {len(content)}자")
                                    break
                        except Exception as e:
                            logger.debug(f"요소 텍스트 추출 오류: {str(e)}")
                            continue
                
                if content:
                    break
                    
            except Exception as e:
                logger.debug(f"Selector {selector} 오류: {str(e)}")
                continue
        
        # 콘텐츠가 추출되지 않은 경우
        if not content:
            logger.warning(f"본문 추출 실패: {post_url}")
            content = "게시글 내용 확인을 위해 링크를 클릭하세요."
            content_summary = "본문 추출 실패"
        
        # 캐시에 저장
        content_cache[url_hash] = {
            'content': content,
            'summary': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url,
            'source': source
        }
        save_content_cache(content_cache)
        
    except Exception as e:
        logger.error(f"게시글 본문 추출 오류 {post_url}: {str(e)}")
        content = f"본문 추출 중 오류 발생: {str(e)}"
        content_summary = "오류 발생"
    
    finally:
        if should_quit_driver and driver:
            try:
                driver.quit()
            except:
                pass
    
    return content, content_summary

# =============================================================================
# Stove 게시판 크롤링 v3.4 (소스 이름 최종 수정)
# =============================================================================

def fetch_stove_bug_board(force_crawl: bool = False, schedule_type: str = 'frequent', region: str = 'global') -> List[Dict]:
    """Stove 에픽세븐 버그 게시판 크롤링 v3.4 (소스 이름 최종 수정)"""
    
    # 지역별 URL 설정 (소스 이름 수정 완료)
    if region == 'global':
        url = BoardConfig.GLOBAL_BOARDS['bug']['url']
        source = "stove_global_bug"
    else:  # korean
        url = BoardConfig.KOREAN_BOARDS['bug']['url']
        source = "stove_korea_bug"  # stove_korean_bug → stove_korea_bug 수정
    
    return crawl_stove_board(url, source, force_crawl, schedule_type, region)

def fetch_stove_general_board(force_crawl: bool = False, schedule_type: str = 'regular', region: str = 'global') -> List[Dict]:
    """Stove 에픽세븐 일반 게시판 크롤링 v3.4 (소스 이름 최종 수정)"""
    
    # 지역별 URL 설정 (소스 이름 수정 완료)
    if region == 'global':
        url = BoardConfig.GLOBAL_BOARDS['general']['url']
        source = "stove_global_general"
    else:  # korean
        url = BoardConfig.KOREAN_BOARDS['general']['url']
        source = "stove_korea_general"  # stove_korean_general → stove_korea_general 수정
    
    return crawl_stove_board(url, source, force_crawl, schedule_type, region)

def crawl_stove_board(board_url: str, source: str, force_crawl: bool = False, schedule_type: str = 'frequent', region: str = 'global') -> List[Dict]:
    """Stove 게시판 크롤링 (통합) v3.4"""
    posts = []
    driver = None
    
    try:
        logger.info(f"Stove 게시판 크롤링 시작: {source}" + (f" (Force Crawl)" if force_crawl else ""))
        
        # 중복 방지 시스템 로드
        crawled_data = load_crawled_links()
        crawled_links = set(crawled_data.get('links', []))
        
        driver = get_chrome_driver(region=region)
        driver.get(board_url)
        
        # 스케줄에 따른 대기시간 설정
        if schedule_type == 'frequent':
            wait_time = CrawlingSchedule.FREQUENT_WAIT_TIME
        else:
            wait_time = CrawlingSchedule.REGULAR_WAIT_TIME
        
        time.sleep(wait_time)
        
        # DOM 준비 상태 확인
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 강화된 JavaScript로 게시글 목록 추출
        posts_script = """
        const posts = [];
        
        // 다양한 셀렉터 시도 (순서 중요)
        const selectors = [
            'h3.s-board-title',           // 기존 selector
            '[class*="board-title"]',      // 클래스명 포함
            '[class*="post-title"]',       // post-title 포함
            '[class*="article-title"]',    // article-title 포함
            'h3[class*="title"]',         // h3 태그 title 포함
            'a[href*="/view/"]'           // view 링크 직접 찾기
        ];
        
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            
            if (elements.length > 0) {
                elements.forEach((element, index) => {
                    try {
                        let linkElement, titleElement, href, title;
                        
                        if (selector === 'a[href*="/view/"]') {
                            linkElement = element;
                            titleElement = element;
                        } else {
                            linkElement = element.querySelector('a') || element.querySelector('span.s-board-title-text')?.parentElement;
                            titleElement = element.querySelector('span.s-board-title-text') || element;
                        }
                        
                        if (linkElement && titleElement) {
                            href = linkElement.href || linkElement.getAttribute('href');
                            title = titleElement.textContent?.trim() || titleElement.innerText?.trim();
                            
                            if (href && title && title.length > 2) {
                                const fullUrl = href.startsWith('http') ? href : 'https://page.onstove.com' + href;
                                
                                // ID 추출
                                const idMatch = fullUrl.match(/view\/(\d+)/);
                                const id = idMatch ? idMatch[1] : '';
                                
                                // 공지사항 제외
                                const noticeElement = element.querySelector('i.element-badge__s.notice, i.element-badge__s.event, [class*="notice"], [class*="event"]');
                                if (!noticeElement && !title.includes('[공지]') && !title.includes('[이벤트]')) {
                                    posts.push({
                                        href: fullUrl,
                                        id: id,
                                        title: title,
                                        selector_used: selector
                                    });
                                }
                            }
                        }
                    } catch (e) {
                        console.log('게시글 추출 오류:', e);
                    }
                });
                
                if (posts.length > 0) {
                    console.log(`성공한 selector: ${selector}, 게시글 수: ${posts.length}`);
                    break;  // 성공하면 다음 셀렉터 시도하지 않음
                }
            }
        }
        
        return posts;
        """
        
        js_posts = driver.execute_script(posts_script)
        logger.info(f"JavaScript 크롤링 성공: {len(js_posts)}개 게시글 발견")
        
        if not js_posts:
            logger.warning("JavaScript로 게시글을 찾을 수 없음")
            return []
        
        # 게시글 상세 정보 추출
        for post_data in js_posts:
            href = post_data.get('href', '')
            title = post_data.get('title', '')
            post_id = post_data.get('id', '')
            
            if not href or not title:
                continue
            
            # Force Crawl이 아닐 때 중복 체크
            if not force_crawl and href in crawled_links:
                logger.debug(f"중복 게시글 스킵: {title[:30]}...")
                continue
            
            try:
                # 게시글 본문 추출
                content, content_summary = get_stove_post_content(
                    href, driver, source, schedule_type
                )
                
                post = {
                    'title': title,
                    'url': href,
                    'content': content,
                    'content_summary': content_summary,
                    'timestamp': datetime.now().isoformat(),
                    'source': source,
                    'post_id': post_id,
                    'region': region
                }
                
                posts.append(post)
                
                # 새 링크 추가 (중복 방지)
                if href not in crawled_links:
                    crawled_data['links'].append(href)
                    crawled_links.add(href)
                
                logger.debug(f"게시글 수집 완료: {title[:40]}...")
                
                # API 호출 제한을 위한 지연
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"게시글 처리 오류 {href}: {str(e)}")
                continue
        
        # 중복 방지 데이터 저장
        save_crawled_links(crawled_data)
        
        # 디버그 HTML 저장
        try:
            with open(f'{source}_debug_selenium.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
        except:
            pass
        
        logger.info(f"Stove {region} 게시판 크롤링 완료: {len(posts)}개 게시글 수집")
        
    except Exception as e:
        logger.error(f"Stove 게시판 크롤링 오류: {str(e)}")
        return []
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

# =============================================================================
# Reddit 크롤링 v3.4 (신규 추가)
# =============================================================================

def fetch_reddit_posts(force_crawl: bool = False, schedule_type: str = 'regular') -> List[Dict]:
    """Reddit r/EpicSeven 크롤링"""
    posts = []
    driver = None
    
    try:
        logger.info("Reddit 크롤링 시작" + (f" (Force Crawl)" if force_crawl else ""))
        
        # 중복 방지 시스템 로드
        crawled_data = load_crawled_links()
        crawled_links = set(crawled_data.get('links', []))
        
        driver = get_chrome_driver(region='reddit')
        driver.get(BoardConfig.EXTERNAL_SITES['reddit']['url'])
        
        time.sleep(CrawlingSchedule.REDDIT_WAIT_TIME)
        
        # DOM 준비 상태 확인
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Reddit 게시글 추출
        reddit_script = """
        const posts = [];
        const postElements = document.querySelectorAll('[data-testid="post-container"], .Post, [class*="Post"]');
        
        postElements.forEach((element, index) => {
            try {
                const titleElement = element.querySelector('h3, [data-testid*="post-title"], [class*="title"]');
                const linkElement = element.querySelector('a[href*="/comments/"]');
                
                if (titleElement && linkElement) {
                    const title = titleElement.textContent.trim();
                    const href = linkElement.href;
                    
                    if (title && href && title.length > 5) {
                        posts.push({
                            href: href,
                            title: title,
                            id: href.match(/comments\/([^\/]+)/)?.[1] || ''
                        });
                    }
                }
            } catch (e) {
                console.log('Reddit 게시글 추출 오류:', e);
            }
        });
        
        return posts;
        """
        
        js_posts = driver.execute_script(reddit_script)
        logger.info(f"Reddit 크롤링 성공: {len(js_posts)}개 게시글 발견")
        
        # 게시글 처리 (기본 로직과 동일)
        for post_data in js_posts:
            href = post_data.get('href', '')
            title = post_data.get('title', '')
            post_id = post_data.get('id', '')
            
            if not href or not title:
                continue
            
            if not force_crawl and href in crawled_links:
                continue
            
            try:
                # Reddit은 본문 추출 대신 제목만 사용
                content = f"Reddit 게시글 - 자세한 내용은 링크 참조"
                content_summary = title[:100]
                
                post = {
                    'title': title,
                    'url': href,
                    'content': content,
                    'content_summary': content_summary,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'reddit',
                    'post_id': post_id,
                    'region': 'reddit'
                }
                
                posts.append(post)
                
                if href not in crawled_links:
                    crawled_data['links'].append(href)
                    crawled_links.add(href)
                
                time.sleep(0.5)  # Reddit은 더 짧은 지연
                
            except Exception as e:
                logger.error(f"Reddit 게시글 처리 오류 {href}: {str(e)}")
                continue
        
        save_crawled_links(crawled_data)
        logger.info(f"Reddit 크롤링 완료: {len(posts)}개 게시글 수집")
        
    except Exception as e:
        logger.error(f"Reddit 크롤링 오류: {str(e)}")
        return []
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

# =============================================================================
# 루리웹 크롤링 v3.4 (신규 추가)
# =============================================================================

def fetch_ruliweb_posts(force_crawl: bool = False, schedule_type: str = 'regular') -> List[Dict]:
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    driver = None
    
    try:
        logger.info("루리웹 크롤링 시작" + (f" (Force Crawl)" if force_crawl else ""))
        
        crawled_data = load_crawled_links()
        crawled_links = set(crawled_data.get('links', []))
        
        driver = get_chrome_driver(region='ruliweb')
        driver.get(BoardConfig.EXTERNAL_SITES['ruliweb']['url'])
        
        time.sleep(CrawlingSchedule.RULIWEB_WAIT_TIME)
        
        # DOM 준비 상태 확인
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 루리웹 게시글 추출
        ruliweb_script = """
        const posts = [];
        const postElements = document.querySelectorAll('.board_list_table tr, [class*="list"] tr, [class*="board"] tr');
        
        postElements.forEach((element, index) => {
            try {
                const titleElement = element.querySelector('.subject a, [class*="subject"] a, [class*="title"] a');
                
                if (titleElement) {
                    const title = titleElement.textContent.trim();
                    const href = titleElement.href;
                    
                    if (title && href && title.length > 3 && !title.includes('[공지]')) {
                        posts.push({
                            href: href,
                            title: title,
                            id: href.match(/board\/(\d+)/)?.[1] || ''
                        });
                    }
                }
            } catch (e) {
                console.log('루리웹 게시글 추출 오류:', e);
            }
        });
        
        return posts;
        """
        
        js_posts = driver.execute_script(ruliweb_script)
        logger.info(f"루리웹 크롤링 성공: {len(js_posts)}개 게시글 발견")
        
        # 게시글 처리
        for post_data in js_posts:
            href = post_data.get('href', '')
            title = post_data.get('title', '')
            post_id = post_data.get('id', '')
            
            if not href or not title:
                continue
            
            if not force_crawl and href in crawled_links:
                continue
            
            try:
                content = f"루리웹 게시글 - 자세한 내용은 링크 참조"
                content_summary = title[:100]
                
                post = {
                    'title': title,
                    'url': href,
                    'content': content,
                    'content_summary': content_summary,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'ruliweb',
                    'post_id': post_id,
                    'region': 'ruliweb'
                }
                
                posts.append(post)
                
                if href not in crawled_links:
                    crawled_data['links'].append(href)
                    crawled_links.add(href)
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"루리웹 게시글 처리 오류 {href}: {str(e)}")
                continue
        
        save_crawled_links(crawled_data)
        logger.info(f"루리웹 크롤링 완료: {len(posts)}개 게시글 수집")
        
    except Exception as e:
        logger.error(f"루리웹 크롤링 오류: {str(e)}")
        return []
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

# =============================================================================
# 주기별 크롤링 실행 함수들 v3.4 (다국가 지원)
# =============================================================================

def crawl_frequent_sites(force_crawl: bool = False) -> List[Dict]:
    """15분 주기 크롤링 (버그 게시판) - 다국가 지원"""
    logger.info("🔥 === 15분 간격 크롤링 시작 (글로벌+한국 버그 게시판" + (", force_crawl=True)" if force_crawl else ") ==="))
    
    all_posts = []
    
    # 글로벌 버그 게시판
    try:
        global_posts = fetch_stove_bug_board(force_crawl, 'frequent', 'global')
        all_posts.extend(global_posts)
        logger.info(f"글로벌 버그 게시판: {len(global_posts)}개 게시글")
    except Exception as e:
        logger.error(f"글로벌 버그 게시판 크롤링 실패: {str(e)}")
    
    # 한국 버그 게시판
    try:
        korean_posts = fetch_stove_bug_board(force_crawl, 'frequent', 'korean')
        all_posts.extend(korean_posts)
        logger.info(f"한국 버그 게시판: {len(korean_posts)}개 게시글")
    except Exception as e:
        logger.error(f"한국 버그 게시판 크롤링 실패: {str(e)}")
    
    logger.info(f"🔥 === 15분 간격 크롤링 완료: 총 {len(all_posts)}개 게시글 ===")
    return all_posts

def crawl_regular_sites(force_crawl: bool = False) -> List[Dict]:
    """30분 주기 크롤링 (일반 게시판 + 외부 사이트) - 다국가 지원"""
    logger.info("⏰ === 30분 간격 크롤링 시작 (모든 게시판" + (", force_crawl=True)" if force_crawl else ") ==="))
    
    all_posts = []
    
    # 글로벌 일반 게시판
    try:
        global_posts = fetch_stove_general_board(force_crawl, 'regular', 'global')
        all_posts.extend(global_posts)
        logger.info(f"글로벌 일반 게시판: {len(global_posts)}개 게시글")
    except Exception as e:
        logger.error(f"글로벌 일반 게시판 크롤링 실패: {str(e)}")
    
    # 한국 일반 게시판
    try:
        korean_posts = fetch_stove_general_board(force_crawl, 'regular', 'korean')
        all_posts.extend(korean_posts)
        logger.info(f"한국 일반 게시판: {len(korean_posts)}개 게시글")
    except Exception as e:
        logger.error(f"한국 일반 게시판 크롤링 실패: {str(e)}")
    
    # Reddit
    try:
        reddit_posts = fetch_reddit_posts(force_crawl, 'regular')
        all_posts.extend(reddit_posts)
        logger.info(f"Reddit: {len(reddit_posts)}개 게시글")
    except Exception as e:
        logger.error(f"Reddit 크롤링 실패: {str(e)}")
    
    # 루리웹
    try:
        ruliweb_posts = fetch_ruliweb_posts(force_crawl, 'regular')
        all_posts.extend(ruliweb_posts)
        logger.info(f"루리웹: {len(ruliweb_posts)}개 게시글")
    except Exception as e:
        logger.error(f"루리웹 크롤링 실패: {str(e)}")
    
    logger.info(f"⏰ === 30분 간격 크롤링 완료: 총 {len(all_posts)}개 게시글 ===")
    return all_posts

def crawl_by_schedule(current_time: datetime = None, force_crawl: bool = False) -> List[Dict]:
    """스케줄에 따른 크롤링 실행 v3.4"""
    if current_time is None:
        current_time = datetime.now()
    
    all_posts = []
    
    # 15분마다 실행 (버그 게시판들)
    if current_time.minute % CrawlingSchedule.FREQUENT_INTERVAL == 0 or force_crawl:
        frequent_posts = crawl_frequent_sites(force_crawl)
        all_posts.extend(frequent_posts)
    
    # 30분마다 실행 (일반 게시판들 + 외부 사이트)
    if current_time.minute % CrawlingSchedule.REGULAR_INTERVAL == 0 or force_crawl:
        regular_posts = crawl_regular_sites(force_crawl)
        all_posts.extend(regular_posts)
    
    return all_posts

# =============================================================================
# 리포트용 데이터 수집 v3.4
# =============================================================================

def get_all_posts_for_report(hours: int = 24, force_crawl: bool = False) -> List[Dict]:
    """리포트 생성을 위한 전체 게시글 수집 v3.4"""
    logger.info(f"📊 === 리포트용 데이터 수집 시작 (최근 {hours}시간" + (", force_crawl=True)" if force_crawl else ") ==="))
    
    all_posts = []
    
    # 모든 게시판에서 데이터 수집
    try:
        # 글로벌 게시판들
        all_posts.extend(fetch_stove_bug_board(force_crawl, 'frequent', 'global'))
        all_posts.extend(fetch_stove_general_board(force_crawl, 'regular', 'global'))
        
        # 한국 게시판들
        all_posts.extend(fetch_stove_bug_board(force_crawl, 'frequent', 'korean'))
        all_posts.extend(fetch_stove_general_board(force_crawl, 'regular', 'korean'))
        
        # 외부 사이트들
        all_posts.extend(fetch_reddit_posts(force_crawl, 'regular'))
        all_posts.extend(fetch_ruliweb_posts(force_crawl, 'regular'))
        
    except Exception as e:
        logger.error(f"리포트용 데이터 수집 오류: {str(e)}")
    
    # 시간 범위 필터링
    cutoff_time = datetime.now() - timedelta(hours=hours)
    filtered_posts = []
    
    for post in all_posts:
        try:
            post_time = datetime.fromisoformat(post.get('timestamp', ''))
            if post_time >= cutoff_time:
                filtered_posts.append(post)
        except:
            # timestamp 파싱 실패 시 포함
            filtered_posts.append(post)
    
    logger.info(f"📊 === 리포트용 데이터 수집 완료: {len(filtered_posts)}개 게시글 ===")
    return filtered_posts

# =============================================================================
# 메인 실행 부 v3.4
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    # 로깅 설정
    setup_logging()
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description='Epic7 다국가 크롤러 v3.4')
    parser.add_argument('--force-crawl', action='store_true', help='강제 크롤링 (중복 체크 무시)')
    parser.add_argument('--schedule', action='store_true', help='스케줄에 따른 크롤링')
    parser.add_argument('--frequent', action='store_true', help='15분 주기 크롤링만 실행 (버그 게시판)')
    parser.add_argument('--regular', action='store_true', help='30분 주기 크롤링만 실행 (일반+외부)')
    parser.add_argument('--report', type=int, metavar='HOURS', help='리포트용 데이터 수집 (시간 지정)')
    parser.add_argument('--region', choices=['global', 'korean', 'all'], default='all', help='크롤링 지역 선택')
    parser.add_argument('--site', choices=['stove', 'reddit', 'ruliweb', 'all'], default='all', help='크롤링 사이트 선택')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"Epic7 다국가 크롤러 v3.4 시작 - 지역: {args.region}, 사이트: {args.site}")
        
        if args.report:
            # 리포트용 데이터 수집
            posts = get_all_posts_for_report(args.report, args.force_crawl)
            print(f"리포트용 데이터 수집 완료: {len(posts)}개 게시글")
            
        elif args.frequent:
            # 15분 주기 크롤링만 실행
            posts = crawl_frequent_sites(args.force_crawl)
            print(f"15분 주기 크롤링 완료: {len(posts)}개 게시글")
            
        elif args.regular:
            # 30분 주기 크롤링만 실행
            posts = crawl_regular_sites(args.force_crawl)
            print(f"30분 주기 크롤링 완료: {len(posts)}개 게시글")
            
        elif args.schedule:
            # 스케줄에 따른 크롤링
            posts = crawl_by_schedule(force_crawl=args.force_crawl)
            print(f"스케줄 기반 크롤링 완료: {len(posts)}개 게시글")
            
        else:
            # 전체 크롤링 (기본)
            posts = []
            posts.extend(crawl_frequent_sites(args.force_crawl))
            posts.extend(crawl_regular_sites(args.force_crawl))
            print(f"전체 크롤링 완료: {len(posts)}개 게시글")
        
        # 결과 요약 출력
        if posts:
            print(f"\n=== 수집 결과 요약 ===")
            for post in posts[:5]:  # 상위 5개만 출력
                print(f"- {post.get('title', '제목 없음')[:50]}... [{post.get('source', 'Unknown')}]")
            
            # 소스별 통계
            source_stats = {}
            for post in posts:
                source = post.get('source', 'Unknown')
                source_stats[source] = source_stats.get(source, 0) + 1
            
            print(f"\n=== 소스별 통계 ===")
            for source, count in source_stats.items():
                print(f"- {source}: {count}개")
        
    except KeyboardInterrupt:
        print("\n크롤링이 중단되었습니다.")
    except Exception as e:
        logger.error(f"크롤링 실행 오류: {str(e)}")
        print(f"오류 발생: {str(e)}")