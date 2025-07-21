#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 주기별 크롤러 v3.3 - Force Crawl 지원
- CSS Selector 다중 폴백 시스템 적용
- JavaScript 렌더링 대기시간 최적화 (20초/25초)
- Force Crawl 옵션으로 중복 체크 우회 가능
- 버그 게시판: 15분 간격, 일반 게시판: 30분 간격
- 실시간 알림: 버그 게시판 즉시 전송
"""

import time
import random
import re
import requests
import concurrent.futures
import os
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
from file_manager import load_json, save_json, with_file_lock
from utils import (
    get_url_hash, extract_content_summary, fix_stove_url,
    is_frequent_schedule, is_regular_schedule, retry_on_failure,
    get_random_user_agent, get_random_delay, setup_logging,
    format_timestamp, clean_data_list
)

# 로깅 설정
import logging
logger = logging.getLogger(__name__)

# =============================================================================
# 통합 파일 시스템 및 유틸리티
# =============================================================================

def load_crawled_links():
    """크롤링된 링크들을 로드"""
    default_data = {
        "links": [], 
        "last_updated": datetime.now().isoformat()
    }
    return load_json(config.Files.CRAWLED_LINKS, default_data)

def save_crawled_links(link_data):
    """크롤링된 링크들을 저장"""
    try:
        # 링크 수 제한
        if len(link_data["links"]) > 2000:
            link_data["links"] = link_data["links"][-2000:]
        
        link_data["last_updated"] = datetime.now().isoformat()
        
        success = save_json(config.Files.CRAWLED_LINKS, link_data)
        if success:
            logger.info(f"크롤링 링크 저장 완료: {len(link_data['links'])}개")
        else:
            logger.error("크롤링 링크 저장 실패")
        
        return success
    except Exception as e:
        logger.error(f"크롤링 링크 저장 실패: {e}")
        return False

def load_content_cache():
    """게시글 내용 캐시 로드"""
    return load_json(config.Files.CONTENT_CACHE, {})

def save_content_cache(cache_data):
    """게시글 내용 캐시 저장"""
    try:
        # 캐시 크기 제한
        if len(cache_data) > 1000:
            cache_data = clean_data_list(list(cache_data.items()), 1000)
            cache_data = dict(cache_data)
        
        success = save_json(config.Files.CONTENT_CACHE, cache_data)
        if success:
            logger.info(f"콘텐츠 캐시 저장 완료: {len(cache_data)}개")
        else:
            logger.error("콘텐츠 캐시 저장 실패")
        
        return success
    except Exception as e:
        logger.error(f"콘텐츠 캐시 저장 실패: {e}")
        return False

# =============================================================================
# Chrome 드라이버
# =============================================================================

@retry_on_failure(max_retries=2, delay=1.0)
def get_chrome_driver(schedule_type='frequent'):
    """Chrome 드라이버 초기화 (주기별 최적화)"""
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
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 15분 간격 크롤링 최적화
    if schedule_type == 'frequent':
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-flooding-protection')
        timeout = config.Crawling.BUG_BOARD_TIMEOUT
    else:
        timeout = config.Crawling.GENERAL_BOARD_TIMEOUT
    
    # 랜덤 User-Agent 사용
    options.add_argument(f'--user-agent={get_random_user_agent()}')
    
    # 성능 최적화 설정
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
    
    # Chrome Driver 경로 탐색
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
                driver.set_page_load_timeout(timeout)
                driver.implicitly_wait(10)
                logger.info(f"ChromeDriver 초기화 성공: {path} (타임아웃: {timeout}초)")
                return driver
        except Exception as e:
            continue
    
    # 시스템 기본 경로 시도
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout)
        driver.implicitly_wait(10)
        logger.info(f"시스템 기본 ChromeDriver 초기화 성공 (타임아웃: {timeout}초)")
        return driver
    except Exception as e:
        logger.error(f"ChromeDriver 초기화 실패: {e}")
        raise Exception("ChromeDriver 초기화 실패")

# =============================================================================
# 게시글 내용 추출
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome = None, source: str = "", schedule_type: str = 'frequent') -> str:
    """스토브 게시글 내용 추출"""
    cache = load_content_cache()
    url_hash = get_url_hash(post_url)
    
    # 주기별 캐시 시간 차별화
    cache_hours = config.Crawling.BUG_CACHE_HOURS if schedule_type == 'frequent' else config.Crawling.GENERAL_CACHE_HOURS
    
    if url_hash in cache:
        cached_item = cache[url_hash]
        try:
            cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
            if datetime.now() - cache_time < timedelta(hours=cache_hours):
                return cached_item.get('content', "게시글 내용 확인을 위해 링크를 클릭하세요.")
        except:
            pass
    
    driver_created = False
    if driver is None:
        try:
            driver = get_chrome_driver(schedule_type)
            driver_created = True
        except Exception as e:
            logger.error(f"Driver 생성 실패: {e}")
            return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    content_summary = "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    try:
        driver.get(post_url)
        
        # 주기별 로딩 시간 최적화
        if schedule_type == 'frequent':
            time.sleep(8)
        else:
            time.sleep(10)
        
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 주기별 스크롤링 최적화
        scroll_count = 2 if schedule_type == 'frequent' else 3
        for i in range(scroll_count):
            driver.execute_script(f"window.scrollTo(0, {400 * (i + 1)});")
            time.sleep(2)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # 콘텐츠 선택자들
        content_selectors = [
            'div.s-article-content',
            'div.s-article-content-text',
            'section.s-article-body',
            'div.s-board-content',
            'div.article-content',
            'div.post-content'
        ]
        
        extracted_content = ""
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 30:
                            if not any(skip_text in text.lower() for skip_text in 
                                     ['install stove', '스토브를 설치', '로그인이 필요', 'javascript']):
                                extracted_content = text
                                break
                    if extracted_content:
                        break
            except Exception:
                continue
        
        if extracted_content:
            lines = extracted_content.split('\n')
            meaningful_lines = []
            for line in lines:
                line = line.strip()
                if (len(line) > 15 and 
                    not any(skip in line for skip in ['로그인', '회원가입', '메뉴', '검색', '공지사항', '이벤트', 'Install STOVE', '스토브를 설치'])):
                    meaningful_lines.append(line)
            
            if meaningful_lines:
                content_summary = extract_content_summary(meaningful_lines[0])
        
        # 캐시 저장
        cache[url_hash] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url
        }
        save_content_cache(cache)
        
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
# ⭐ 핵심 수정: STOVE 크롤링 함수 (Force Crawl 지원)
# =============================================================================

@retry_on_failure(max_retries=2, delay=2.0)
def crawl_stove_board(source: str, site_config: Dict, schedule_type: str = 'frequent', force_crawl: bool = False):
    """스토브 게시판 크롤링 (CSS Selector 다중 폴백 + Force Crawl 지원)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    logger.info(f"🔄 {site_config['site']} 크롤링 시작 ({schedule_type}, force_crawl={force_crawl})")
    
    driver = None
    try:
        driver = get_chrome_driver(schedule_type)
        driver.get(site_config['url'])
        
        # 대기시간 최적화
        if schedule_type == 'frequent':
            time.sleep(20)  # 15분 간격
        else:
            time.sleep(25)  # 30분 간격
        
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 스크롤링 최적화
        scroll_count = 2 if schedule_type == 'frequent' else 3
        for i in range(scroll_count):
            driver.execute_script(f"window.scrollTo(0, {400 * (i + 1)});")
            time.sleep(3)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        
        # JavaScript 다중 폴백 시스템
        user_posts = []
        try:
            user_posts = driver.execute_script(f"""
            var posts = [];
            
            // 다중 CSS Selector 폴백 시스템
            var containerSelectors = [
                'section.s-board-item',
                'div[class*="board-item"]',
                'article[class*="post"]',
                'div[class*="list-item"]',
                '[data-testid*="post"]',
                '.post-item',
                '.board-list-item',
                'li[class*="item"]',
                'div[class*="post"]'
            ];
            
            var items = [];
            for (var selector of containerSelectors) {{
                try {{
                    items = document.querySelectorAll(selector);
                    if (items && items.length > 0) {{
                        console.log('성공한 선택자:', selector, '개수:', items.length);
                        break;
                    }}
                }} catch(e) {{
                    continue;
                }}
            }}
            
            // 컨테이너를 찾지 못한 경우 전체 링크 탐색
            if (!items || items.length === 0) {{
                console.log('컨테이너를 찾지 못함, 전체 링크 탐색');
                var allLinks = document.querySelectorAll('a[href*="/view/"]');
                for (var i = 0; i < Math.min(allLinks.length, {site_config['limit']}); i++) {{
                    var link = allLinks[i];
                    if (link.href && link.innerText && link.innerText.trim().length > 3) {{
                        posts.push({{
                            title: link.innerText.trim(),
                            href: link.href,
                            id: link.href.split('/').pop()
                        }});
                    }}
                }}
                return posts;
            }}
            
            // 정상적으로 컨테이너를 찾은 경우 처리
            for (var i = 0; i < Math.min(items.length, {site_config['limit']}); i++) {{
                var item = items[i];
                
                // 링크 추출 다중 폴백
                var link = item.querySelector('a[href*="/view/"]') ||
                          item.querySelector('a[href*="/board/"]') ||
                          item.querySelector('a[href*="/post/"]') ||
                          item.querySelector('a[href]');
                
                // 제목 추출 다중 폴백
                var titleSelectors = [
                    '.s-board-title-text',
                    '.board-title',
                    'h3 span',
                    '[class*="title"]',
                    'h1, h2, h3, h4, h5, h6',
                    '.post-title',
                    'span[class*="text"]',
                    '.text'
                ];
                
                var title = null;
                for (var titleSelector of titleSelectors) {{
                    try {{
                        var titleElement = item.querySelector(titleSelector);
                        if (titleElement && titleElement.innerText && titleElement.innerText.trim().length > 3) {{
                            title = titleElement;
                            break;
                        }}
                    }} catch(e) {{
                        continue;
                    }}
                }}
                
                // 제목을 찾지 못한 경우 링크의 텍스트 사용
                if (!title && link && link.innerText && link.innerText.trim().length > 3) {{
                    title = link;
                }}
                
                if (link && title && link.href && title.innerText) {{
                    var titleText = title.innerText.trim();
                    if (titleText.length > 3) {{
                        // 공지사항/이벤트 제외
                        var isNotice = item.querySelector('.notice, [class*="notice"], [class*="Notice"]');
                        var isEvent = item.querySelector('.event, [class*="event"], [class*="Event"]');
                        var isPinned = item.querySelector('[class*="pin"], [class*="top"], [class*="sticky"]');
                        
                        if (!isNotice && !isEvent && !isPinned) {{
                            posts.push({{
                                title: titleText,
                                href: link.href,
                                id: link.href.split('/').pop()
                            }});
                        }}
                    }}
                }}
            }}
            
            console.log('최종 추출된 게시글 수:', posts.length);
            return posts;
            """)
            
            logger.info(f"JavaScript 크롤링 성공: {len(user_posts)}개 게시글 발견")
            
        except Exception as js_error:
            logger.warning(f"JavaScript 실행 실패: {js_error}")
            # BeautifulSoup 백업 크롤링
            logger.info("BeautifulSoup 백업 크롤링 시작")
            try:
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # 다양한 링크 패턴으로 탐색
                link_patterns = [
                    'a[href*="/view/"]',
                    'a[href*="/board/"]', 
                    'a[href*="/post/"]'
                ]
                
                found_links = []
                for pattern in link_patterns:
                    links = soup.select(pattern)
                    if links:
                        found_links = links[:site_config['limit']]
                        logger.info(f"BeautifulSoup로 {pattern} 패턴에서 {len(found_links)}개 링크 발견")
                        break
                
                for link in found_links:
                    title = link.get_text(strip=True)
                    href = link.get('href')
                    if title and href and len(title) > 3:
                        if href.startswith('/'):
                            href = 'https://page.onstove.com' + href
                        user_posts.append({
                            'title': title,
                            'href': href, 
                            'id': href.split('/')[-1]
                        })
                        
            except Exception as soup_error:
                logger.error(f"BeautifulSoup 백업도 실패: {soup_error}")
                user_posts = []
        
        # ⭐ 핵심 수정: Force Crawl 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                # ⭐ 중복 체크 수정: force_crawl=True면 중복 체크 스킵
                if not force_crawl and href in crawled_links:
                    logger.debug(f"중복 게시글 스킵: {title[:30]}...")
                    continue
                
                if title and href and len(title) > 3:
                    content = get_stove_post_content(href, driver, source, schedule_type)
                    
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "source": source,
                        "site": site_config['site'],
                        "language": site_config['language'],
                        "priority": site_config['priority'],
                        "schedule_type": schedule_type,
                        "is_realtime": source in config.Crawling.REALTIME_ALERT_SOURCES
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(href)
                    
                    # Force Crawl 모드에 따른 로그 구분
                    if force_crawl:
                        logger.info(f"🔄 {site_config['site']} Force Crawl: {title[:50]}...")
                    else:
                        logger.info(f"✅ {site_config['site']} 새 게시글: {title[:50]}...")
                    
                    # 주기별 지연 시간 최적화
                    if schedule_type == 'frequent':
                        time.sleep(get_random_delay(1, 2))
                    else:
                        time.sleep(get_random_delay(2, 3))
                    
                    # 실시간 알림 소스는 5개 이상 발견시 즉시 반환
                    if source in config.Crawling.REALTIME_ALERT_SOURCES and len(posts) >= 5:
                        break
                        
            except Exception as e:
                logger.error(f"{site_config['site']} 게시글 {i} 처리 오류: {e}")
                continue
                
    except Exception as e:
        logger.error(f"{site_config['site']} 크롤링 실패: {e}")
    finally:
        if driver:
            driver.quit()
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

# =============================================================================
# 기타 크롤링 함수들 (기존 코드 보존)
# =============================================================================

@retry_on_failure(max_retries=2, delay=2.0)
def crawl_ruliweb_board():
    """루리웹 에픽세븐 게시판 크롤링 (30분 간격)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    logger.info("🌐 루리웹 크롤링 시작 (30분 간격)")
    
    driver = None
    try:
        driver = get_chrome_driver('regular')
        site_config = config.Crawling.REGULAR_SOURCES['ruliweb_epic7']
        driver.get(site_config['url'])
        time.sleep(10)
        
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
        for i, article in enumerate(articles[:site_config['limit']]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천', '베스트', '공지사항']):
                    continue
                
                if link.startswith('/'):
                    link = 'https://bbs.ruliweb.com' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": "루리웹 게시글 내용 확인을 위해 링크를 클릭하세요.",
                        "timestamp": datetime.now().isoformat(),
                        "source": "ruliweb_epic7",
                        "site": site_config['site'],
                        "language": site_config['language'],
                        "priority": site_config['priority'],
                        "schedule_type": "regular",
                        "is_realtime": False
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(link)
                    
                    logger.info(f"📰 루리웹 새 게시글: {title[:50]}...")
                    
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
    save_crawled_links(link_data)
    
    return posts

@retry_on_failure(max_retries=2, delay=2.0)
def crawl_reddit_board():
    """Reddit r/EpicSeven 최신글 크롤링 (30분 간격)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    logger.info("🌐 Reddit 크롤링 시작 (30분 간격)")
    
    try:
        site_config = config.Crawling.REGULAR_SOURCES['reddit_epic7']
        url = site_config['url']
        headers = {
            "User-Agent": get_random_user_agent(),
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
                        "site": site_config['site'],
                        "language": site_config['language'],
                        "priority": site_config['priority'],
                        "schedule_type": "regular",
                        "is_realtime": False
                    }
                    
                    posts.append(post_data)
                    crawled_links.append(permalink)
                    
                    logger.info(f"📰 Reddit 새 게시글: {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Reddit 게시글 처리 오류: {e}")
                    continue
                    
    except requests.RequestException as e:
        logger.error(f"Reddit API 요청 실패: {e}")
    except Exception as e:
        logger.error(f"Reddit 크롤링 실패: {e}")
    
    # 링크 데이터 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

# =============================================================================
# ⭐ 수정: 주기별 통합 크롤링 실행 (Force Crawl 지원)
# =============================================================================

def crawl_frequent_sites(force_crawl=False):
    """15분 간격 크롤링 (버그 게시판)"""
    logger.info(f"🔥 === 15분 간격 크롤링 시작 (버그 게시판, force_crawl={force_crawl}) ===")
    
    frequent_posts = []
    
    # 버그 게시판 병렬 크롤링
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        
        for source, site_config in config.Crawling.FREQUENT_SOURCES.items():
            futures[executor.submit(crawl_stove_board, source, site_config, 'frequent', force_crawl)] = source
        
        for future in concurrent.futures.as_completed(futures, timeout=90):
            source = futures[future]
            try:
                posts = future.result()
                if posts:
                    frequent_posts.extend(posts)
                    logger.info(f"✅ {source}: {len(posts)}개 (15분 간격, force_crawl={force_crawl})")
                else:
                    logger.info(f"⭕ {source}: 새 게시글 없음")
            except Exception as e:
                logger.error(f"❌ {source} 크롤링 실패: {e}")
    
    logger.info(f"🔥 15분 간격 크롤링 완료: 총 {len(frequent_posts)}개")
    return frequent_posts

def crawl_regular_sites(force_crawl=False):
    """30분 간격 크롤링 (일반 게시판)"""
    logger.info(f"📝 === 30분 간격 크롤링 시작 (일반 게시판, force_crawl={force_crawl}) ===")
    
    regular_posts = []
    
    # 스토브 일반 게시판 크롤링
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        
        for source, site_config in config.Crawling.REGULAR_SOURCES.items():
            if source in ['stove_general', 'stove_global_general']:
                futures[executor.submit(crawl_stove_board, source, site_config, 'regular', force_crawl)] = source
        
        for future in concurrent.futures.as_completed(futures, timeout=120):
            source = futures[future]
            try:
                posts = future.result()
                if posts:
                    regular_posts.extend(posts)
                    logger.info(f"✅ {source}: {len(posts)}개 (30분 간격, force_crawl={force_crawl})")
                else:
                    logger.info(f"⭕ {source}: 새 게시글 없음")
            except Exception as e:
                logger.error(f"❌ {source} 크롤링 실패: {e}")
    
    # 커뮤니티 사이트 크롤링 (force_crawl 영향 없음)
    try:
        ruliweb_posts = crawl_ruliweb_board()
        if ruliweb_posts:
            regular_posts.extend(ruliweb_posts)
            logger.info(f"✅ ruliweb_epic7: {len(ruliweb_posts)}개 (30분 간격)")
    except Exception as e:
        logger.error(f"❌ ruliweb_epic7 크롤링 실패: {e}")
    
    try:
        reddit_posts = crawl_reddit_board()
        if reddit_posts:
            regular_posts.extend(reddit_posts)
            logger.info(f"✅ reddit_epic7: {len(reddit_posts)}개 (30분 간격)")
    except Exception as e:
        logger.error(f"❌ reddit_epic7 크롤링 실패: {e}")
    
    logger.info(f"📝 30분 간격 크롤링 완료: 총 {len(regular_posts)}개")
    return regular_posts

def crawl_by_schedule(force_crawl=False):
    """스케줄에 따른 크롤링 실행"""
    logger.info(f"📅 === 스케줄 기반 크롤링 시작 (force_crawl={force_crawl}) ===")
    
    all_posts = []
    
    # 15분 간격 체크 (버그 게시판)
    if is_frequent_schedule():
        frequent_posts = crawl_frequent_sites(force_crawl)
        all_posts.extend(frequent_posts)
    
    # 30분 간격 체크 (일반 게시판)
    if is_regular_schedule():
        regular_posts = crawl_regular_sites(force_crawl)
        all_posts.extend(regular_posts)
    
    # 스케줄 외 수동 실행시 모든 사이트 크롤링
    if not all_posts:
        logger.info("⚠️ 스케줄 외 실행 - 모든 사이트 크롤링")
        frequent_posts = crawl_frequent_sites(force_crawl)
        regular_posts = crawl_regular_sites(force_crawl)
        all_posts.extend(frequent_posts)
        all_posts.extend(regular_posts)
    
    # 우선순위별 정렬
    all_posts.sort(key=lambda x: (x.get('priority', 99), x.get('timestamp', '')), reverse=True)
    
    logger.info(f"📅 === 스케줄 기반 크롤링 완료: 총 {len(all_posts)}개 ===")
    return all_posts

# =============================================================================
# 리포트용 데이터 수집
# =============================================================================

def get_all_posts_for_report():
    """일간 리포트용 게시글 수집"""
    logger.info("📊 일간 리포트용 데이터 수집 시작")
    
    cutoff_time = datetime.now() - timedelta(hours=24)
    cache = load_content_cache()
    recent_posts = []
    
    for url_hash, cached_item in cache.items():
        try:
            timestamp = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
            if timestamp >= cutoff_time:
                post_data = {
                    'title': cached_item.get('title', ''),
                    'url': cached_item.get('url', ''),
                    'content': cached_item.get('content', ''),
                    'timestamp': cached_item.get('timestamp', ''),
                    'source': cached_item.get('source', 'unknown'),
                    'site': cached_item.get('site', 'unknown'),
                    'language': cached_item.get('language', 'unknown'),
                    'priority': cached_item.get('priority', 99),
                    'schedule_type': cached_item.get('schedule_type', 'regular'),
                    'is_realtime': cached_item.get('is_realtime', False)
                }
                recent_posts.append(post_data)
        except Exception as e:
            logger.error(f"캐시 항목 처리 오류: {e}")
            continue
    
    logger.info(f"📊 일간 리포트용 데이터 수집 완료: {len(recent_posts)}개")
    return recent_posts

# =============================================================================
# 메인 실행 함수
# =============================================================================

def main():
    """메인 실행 함수"""
    logger.info("🚀 Epic7 주기별 크롤러 v3.3 시작")
    
    try:
        # 스케줄 기반 크롤링
        all_posts = crawl_by_schedule()
        
        if all_posts:
            logger.info(f"총 {len(all_posts)}개의 새 게시글을 크롤링했습니다.")
            
            # 주기별 통계
            schedule_stats = {}
            for post in all_posts:
                schedule_type = post.get('schedule_type', 'unknown')
                if schedule_type not in schedule_stats:
                    schedule_stats[schedule_type] = 0
                schedule_stats[schedule_type] += 1
            
            logger.info("주기별 통계:")
            for schedule_type, count in schedule_stats.items():
                schedule_name = {
                    'frequent': "15분 간격",
                    'regular': "30분 간격"
                }.get(schedule_type, schedule_type)
                logger.info(f"  {schedule_name}: {count}개")
            
            # 실시간 알림 대상 통계
            realtime_posts = [post for post in all_posts if post.get('is_realtime', False)]
            logger.info(f"실시간 알림 대상: {len(realtime_posts)}개")
            
            # 사이트별 통계
            site_stats = {}
            for post in all_posts:
                site = post.get('site', 'unknown')
                if site not in site_stats:
                    site_stats[site] = 0
                site_stats[site] += 1
            
            logger.info("사이트별 통계:")
            for site, count in site_stats.items():
                logger.info(f"  {site}: {count}개")
        else:
            logger.info("새로운 게시글이 없습니다.")
        
        return all_posts
        
    except Exception as e:
        logger.error(f"크롤링 실행 중 오류 발생: {e}")
        return []

if __name__ == "__main__":
    main()
