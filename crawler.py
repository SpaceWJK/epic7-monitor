# crawler.py - Epic7 모니터링 시스템 완전 개선 버전 2.0
# Korean/Global 모드 분기 처리와 글로벌 크롤링 함수 완전 구현

import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime, timedelta
import re
import random
import requests
import hashlib
from typing import Dict, List, Optional, Tuple
import threading
import concurrent.futures
from urllib.parse import urljoin, urlparse

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
            print(f"[WARNING] {links_file} 파일 읽기 실패, 새로 생성")
    
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
        print(f"[INFO] {links_file} 저장 완료: {len(link_data['links'])}개 링크")
    except Exception as e:
        print(f"[ERROR] {links_file} 저장 실패: {e}")

def load_content_cache(mode: str = "korean"):
    """모드별 게시글 내용 캐시 로드"""
    _, cache_file = get_file_paths(mode)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"[WARNING] {cache_file} 파일 읽기 실패, 새로 생성")
    
    return {}

def save_content_cache(cache_data, mode: str = "korean"):
    """모드별 게시글 내용 캐시 저장"""
    _, cache_file = get_file_paths(mode)
    
    try:
        if len(cache_data) > 500:
            sorted_items = sorted(cache_data.items(), key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache_data = dict(sorted_items[:500])
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] {cache_file} 저장 완료: {len(cache_data)}개 캐시")
    except Exception as e:
        print(f"[ERROR] {cache_file} 저장 실패: {e}")

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
    
    content = re.sub(r'\s+', ' ', content.strip())
    content = re.sub(r'[^\w\s가-힣.,!?]', '', content)
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
                        print(f"[RETRY] {func.__name__} 시도 {attempt + 1}/{max_retries} 실패: {e}")
                        time.sleep(delay * (attempt + 1))
                    else:
                        print(f"[ERROR] {func.__name__} 최종 실패: {e}")
            
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator

# =============================================================================
# Chrome 드라이버 관리
# =============================================================================

@retry_on_failure(max_retries=3, delay=1.0)
def get_chrome_driver():
    """Chrome 드라이버 초기화 (재시도 로직 포함)"""
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
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    
    prefs = {
        'profile.default_content_setting_values': {
            'images': 2, 'plugins': 2, 'popups': 2,
            'geolocation': 2, 'notifications': 2, 'media_stream': 2,
        }
    }
    options.add_experimental_option('prefs', prefs)
    
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver',
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
                print(f"[SUCCESS] ChromeDriver 초기화 성공: {path}")
                return driver
        except Exception as e:
            print(f"[DEBUG] ChromeDriver 경로 {path} 실패: {str(e)[:100]}...")
            continue
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(15)
        print("[SUCCESS] 시스템 기본 ChromeDriver 초기화 성공")
        return driver
    except Exception as e:
        print(f"[DEBUG] 시스템 기본 ChromeDriver 실패: {str(e)[:100]}...")
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(15)
        print("[SUCCESS] WebDriver Manager 초기화 성공")
        return driver
    except Exception as e:
        print(f"[DEBUG] WebDriver Manager 실패: {str(e)[:100]}...")
    
    raise Exception("모든 ChromeDriver 초기화 방법이 실패했습니다.")

# =============================================================================
# 게시글 내용 추출 함수
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome = None, mode: str = "korean") -> str:
    """스토브 게시글 내용 추출 (강화된 버전)"""
    
    cache = load_content_cache(mode)
    url_hash = get_url_hash(post_url)
    
    if url_hash in cache:
        cached_item = cache[url_hash]
        cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
        if datetime.now() - cache_time < timedelta(hours=24):
            return cached_item.get('content', "게시글 내용 확인을 위해 링크를 클릭하세요.")
    
    driver_created = False
    if driver is None:
        try:
            driver = get_chrome_driver()
            driver_created = True
        except Exception as e:
            print(f"[ERROR] Driver 생성 실패: {e}")
            return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    content_summary = "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    try:
        driver.get(post_url)
        time.sleep(20)
        
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(5)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(5)
        
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
        successful_selector = ""
        
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 50:
                            if not any(skip_text in text.lower() for skip_text in 
                                     ['install stove', '스토브를 설치', '로그인이 필요', 'javascript']):
                                extracted_content = text
                                successful_selector = selector
                                break
                    if extracted_content:
                        break
            except Exception as e:
                continue
        
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
                print(f"[ERROR] JavaScript 추출 실패: {e}")
        
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
                print(f"[ERROR] BeautifulSoup 추출 실패: {e}")
        
        debug_filename = f"debug_stove_{mode}_{datetime.now().strftime('%H%M%S')}.html"
        with open(debug_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        cache[url_hash] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url,
            'selector_used': successful_selector
        }
        save_content_cache(cache, mode)
        
    except TimeoutException:
        print(f"[ERROR] 페이지 로딩 타임아웃: {post_url}")
        content_summary = "⏰ 게시글 로딩 시간 초과. 링크를 클릭하여 확인하세요."
    except Exception as e:
        print(f"[ERROR] 게시글 내용 추출 실패: {e}")
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
    
    print(f"[DEBUG] 스토브 버그 게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        driver.get(url)
        
        time.sleep(20)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(5)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(5)
        
        html_content = driver.page_source
        with open(f"stove_bug_debug_{mode}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
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
                    print(f"[NEW] 스토브 버그 새 게시글: {title[:50]}...")
                
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                print(f"[ERROR] 스토브 버그 게시글 {i} 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] 스토브 버그 게시판 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_general_board(mode: str = "korean"):
    """스토브 에픽세븐 자유게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 스토브 자유게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST"
        driver.get(url)
        
        time.sleep(20)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(5)
        
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
        
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href in crawled_links:
                    continue
                
                if not title or len(title) < 4:
                    continue
                
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
                print(f"[NEW] 스토브 자유게시판 새 게시글: {title[:50]}...")
                
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                print(f"[ERROR] 스토브 자유게시판 게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] 스토브 자유게시판 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_ruliweb_epic7_board(mode: str = "korean"):
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 루리웹 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://bbs.ruliweb.com/game/84834"
        driver.get(url)
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
                    print(f"[DEBUG] 루리웹 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        if not articles:
            print("[WARNING] 루리웹 게시글을 찾을 수 없음")
            with open(f"ruliweb_debug_{mode}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return posts
        
        for i, article in enumerate(articles[:15]):
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
                        "site": "루리웹"
                    }
                    posts.append(post_data)
                    crawled_links.append(link)
                    print(f"[NEW] 루리웹 새 게시글: {title[:50]}...")
                
            except Exception as e:
                print(f"[ERROR] 루리웹 게시글 {i+1} 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] 루리웹 크롤링 실패: {e}")
        if driver:
            try:
                with open(f"ruliweb_error_{mode}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_arca_epic7_board(mode: str = "korean"):
    """아카라이브 에픽세븐 채널 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 아카라이브 크롤링 시작 (mode: {mode})")
    
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
        
        html_content = driver.page_source
        with open(f"arca_debug_{mode}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
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
                    print(f"[DEBUG] 아카라이브 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        if not articles:
            print("[WARNING] 아카라이브 게시글을 찾을 수 없음")
            return posts
        
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천', '베스트']):
                    continue
                
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
                    print(f"[NEW] 아카라이브 새 게시글: {title[:50]}...")
                
            except Exception as e:
                print(f"[ERROR] 아카라이브 게시글 {i+1} 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] 아카라이브 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
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
    
    print(f"[DEBUG] STOVE 글로벌 버그 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST"
        driver.get(url)
        
        time.sleep(20)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(5)
        
        html_content = driver.page_source
        with open(f"stove_global_bug_debug_{mode}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
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
                print(f"[NEW] STOVE 글로벌 버그 새 게시글: {title[:50]}...")
                
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                print(f"[ERROR] STOVE 글로벌 버그 게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] STOVE 글로벌 버그 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_stove_global_general_board(mode: str = "global"):
    """STOVE 글로벌 자유게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] STOVE 글로벌 자유게시판 크롤링 시작 (mode: {mode})")
    
    driver = None
    try:
        driver = get_chrome_driver()
        url = "https://page.onstove.com/epicseven/global/list/989?page=1&direction=LATEST"
        driver.get(url)
        
        time.sleep(20)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {500 * (i + 1)});")
            time.sleep(5)
        
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
                print(f"[NEW] STOVE 글로벌 자유게시판 새 게시글: {title[:50]}...")
                
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                print(f"[ERROR] STOVE 글로벌 자유게시판 게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] STOVE 글로벌 자유게시판 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_reddit_epic7_board(mode: str = "global"):
    """Reddit r/EpicSeven 최신글 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] Reddit 크롤링 시작 (mode: {mode})")
    
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
                    print(f"[NEW] Reddit 새 게시글: {title[:50]}...")
                    
                except Exception as e:
                    print(f"[ERROR] Reddit 게시글 처리 오류: {e}")
                    continue
        
    except requests.RequestException as e:
        print(f"[ERROR] Reddit API 요청 실패: {e}")
    except Exception as e:
        print(f"[ERROR] Reddit 크롤링 실패: {e}")
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

@retry_on_failure(max_retries=2, delay=3.0)
def fetch_epic7_official_forum(mode: str = "global"):
    """Epic7 공식 포럼 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] Epic7 공식 포럼 크롤링 시작 (mode: {mode})")
    
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
        
        html_content = driver.page_source
        with open(f"epic7_forum_debug_{mode}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
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
                    print(f"[DEBUG] 공식 포럼 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except NoSuchElementException:
                continue
        
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                if link.startswith('/'):
                    link = 'https://epic7.gg' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": f"Epic7 공식 포럼 게시글: {title[:100]}...",
                        "timestamp": datetime.now().isoformat(),
                        "source": "epic7_forum",
                        "site": "Epic7 Official Forum"
                    }
                    posts.append(post_data)
                    crawled_links.append(link)
                    print(f"[NEW] Epic7 공식 포럼 새 게시글: {title[:50]}...")
                
            except Exception as e:
                print(f"[ERROR] Epic7 공식 포럼 게시글 {i+1} 처리 오류: {e}")
                continue
        
    except Exception as e:
        print(f"[ERROR] Epic7 공식 포럼 크롤링 실패: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

# =============================================================================
# 메인 크롤링 함수들
# =============================================================================

def crawl_korean_sites(mode: str = "korean"):
    """한국 사이트 통합 크롤링"""
    print(f"[INFO] 한국 사이트 크롤링 시작 (mode: {mode})")
    
    all_posts = []
    
    try:
        # 스토브 버그 게시판
        bug_posts = fetch_stove_bug_board(mode)
        all_posts.extend(bug_posts)
        print(f"[INFO] 스토브 버그 게시판: {len(bug_posts)}개 게시글")
        
        # 스토브 자유게시판
        general_posts = fetch_stove_general_board(mode)
        all_posts.extend(general_posts)
        print(f"[INFO] 스토브 자유게시판: {len(general_posts)}개 게시글")
        
        # 루리웹
        ruliweb_posts = fetch_ruliweb_epic7_board(mode)
        all_posts.extend(ruliweb_posts)
        print(f"[INFO] 루리웹: {len(ruliweb_posts)}개 게시글")
        
        # 아카라이브
        arca_posts = fetch_arca_epic7_board(mode)
        all_posts.extend(arca_posts)
        print(f"[INFO] 아카라이브: {len(arca_posts)}개 게시글")
        
    except Exception as e:
        print(f"[ERROR] 한국 사이트 크롤링 중 오류: {e}")
    
    print(f"[INFO] 한국 사이트 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_global_sites(mode: str = "global"):
    """글로벌 사이트 통합 크롤링"""
    print(f"[INFO] 글로벌 사이트 크롤링 시작 (mode: {mode})")
    
    all_posts = []
    
    try:
        # STOVE 글로벌 버그 게시판
        global_bug_posts = fetch_stove_global_bug_board(mode)
        all_posts.extend(global_bug_posts)
        print(f"[INFO] STOVE 글로벌 버그 게시판: {len(global_bug_posts)}개 게시글")
        
        # STOVE 글로벌 자유게시판
        global_general_posts = fetch_stove_global_general_board(mode)
        all_posts.extend(global_general_posts)
        print(f"[INFO] STOVE 글로벌 자유게시판: {len(global_general_posts)}개 게시글")
        
        # Reddit
        reddit_posts = fetch_reddit_epic7_board(mode)
        all_posts.extend(reddit_posts)
        print(f"[INFO] Reddit: {len(reddit_posts)}개 게시글")
        
        # Epic7 공식 포럼
        forum_posts = fetch_epic7_official_forum(mode)
        all_posts.extend(forum_posts)
        print(f"[INFO] Epic7 공식 포럼: {len(forum_posts)}개 게시글")
        
    except Exception as e:
        print(f"[ERROR] 글로벌 사이트 크롤링 중 오류: {e}")
    
    print(f"[INFO] 글로벌 사이트 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_all_sites():
    """모든 사이트 통합 크롤링"""
    print("[INFO] 전체 사이트 크롤링 시작")
    
    all_posts = []
    
    try:
        # 한국 사이트
        korean_posts = crawl_korean_sites("korean")
        all_posts.extend(korean_posts)
        
        # 글로벌 사이트
        global_posts = crawl_global_sites("global")
        all_posts.extend(global_posts)
        
    except Exception as e:
        print(f"[ERROR] 전체 사이트 크롤링 중 오류: {e}")
    
    print(f"[INFO] 전체 사이트 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def get_all_posts_for_report(mode: str = "all"):
    """리포트용 게시글 수집"""
    print(f"[INFO] 리포트용 게시글 수집 시작 (mode: {mode})")
    
    all_posts = []
    
    try:
        if mode == "korean":
            all_posts = crawl_korean_sites("korean")
        elif mode == "global":
            all_posts = crawl_global_sites("global")
        else:  # all
            all_posts = crawl_all_sites()
        
        # 24시간 이내 게시글만 필터링
        recent_posts = []
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for post in all_posts:
            try:
                post_time = datetime.fromisoformat(post['timestamp'])
                if post_time > cutoff_time:
                    recent_posts.append(post)
            except:
                continue
        
        print(f"[INFO] 리포트용 게시글 수집 완료: 최근 24시간 내 {len(recent_posts)}개 게시글")
        
    except Exception as e:
        print(f"[ERROR] 리포트용 게시글 수집 중 오류: {e}")
    
    return recent_posts

# =============================================================================
# 메인 실행 함수
# =============================================================================

def main_crawl(mode: str = "korean"):
    """메인 크롤링 함수"""
    print(f"[INFO] Epic7 모니터링 크롤링 시작 - 모드: {mode}")
    
    try:
        if mode == "korean":
            posts = crawl_korean_sites(mode)
        elif mode == "global":
            posts = crawl_global_sites(mode)
        elif mode == "all":
            posts = crawl_all_sites()
        else:
            print(f"[ERROR] 지원하지 않는 모드: {mode}")
            return []
        
        print(f"[INFO] 크롤링 완료: {len(posts)}개 게시글")
        return posts
        
    except Exception as e:
        print(f"[ERROR] 메인 크롤링 중 오류: {e}")
        return []

# =============================================================================
# 테스트 및 디버그 함수
# =============================================================================

def test_crawling():
    """크롤링 테스트 함수"""
    print("[TEST] 크롤링 테스트 시작")
    
    # 한국 사이트 테스트
    print("\n[TEST] 한국 사이트 테스트")
    korean_posts = crawl_korean_sites("korean")
    print(f"한국 사이트 결과: {len(korean_posts)}개")
    
    # 글로벌 사이트 테스트
    print("\n[TEST] 글로벌 사이트 테스트")
    global_posts = crawl_global_sites("global")
    print(f"글로벌 사이트 결과: {len(global_posts)}개")
    
    print("\n[TEST] 크롤링 테스트 완료")

if __name__ == "__main__":
    # 테스트 실행
    test_crawling()