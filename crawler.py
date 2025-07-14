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

# 워크플로우별 독립적인 링크 저장 파일
def get_crawled_links_file():
    """워크플로우별 독립적인 크롤링 링크 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')
    run_context = os.environ.get('GITHUB_RUN_NUMBER', 'local')
    
    # 워크플로우별 파일 분리
    if 'debug' in workflow_name.lower() or 'test' in workflow_name.lower():
        return f"crawled_links_debug_{run_context}.json"
    elif 'korean' in workflow_name.lower():
        return "crawled_links_korean.json"
    elif 'unified' in workflow_name.lower() or 'monitor' in workflow_name.lower():
        return "crawled_links_monitor.json"
    else:
        return "crawled_links.json"

def get_content_cache_file():
    """워크플로우별 독립적인 콘텐츠 캐시 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')
    
    if 'debug' in workflow_name.lower() or 'test' in workflow_name.lower():
        return "content_cache_debug.json"
    elif 'korean' in workflow_name.lower():
        return "content_cache_korean.json"
    elif 'unified' in workflow_name.lower() or 'monitor' in workflow_name.lower():
        return "content_cache_monitor.json"
    else:
        return "content_cache.json"

# 중복 방지를 위한 링크 저장 파일
CRAWLED_LINKS_FILE = get_crawled_links_file()
CONTENT_CACHE_FILE = get_content_cache_file()

def load_crawled_links():
    """이미 크롤링된 링크들을 로드"""
    if os.path.exists(CRAWLED_LINKS_FILE):
        try:
            with open(CRAWLED_LINKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"links": data, "last_updated": datetime.now().isoformat()}
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            print("[WARNING] crawled_links.json 파일 읽기 실패, 새로 생성")
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data):
    """크롤링된 링크들을 저장 (최대 1000개 유지)"""
    try:
        if len(link_data["links"]) > 1000:
            link_data["links"] = link_data["links"][-1000:]
        link_data["last_updated"] = datetime.now().isoformat()
        with open(CRAWLED_LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] 링크 저장 실패: {e}")

def load_content_cache():
    """게시글 내용 캐시 로드"""
    if os.path.exists(CONTENT_CACHE_FILE):
        try:
            with open(CONTENT_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("[WARNING] content_cache.json 파일 읽기 실패, 새로 생성")
    return {}

def save_content_cache(cache_data):
    """게시글 내용 캐시 저장"""
    try:
        if len(cache_data) > 500:
            sorted_items = sorted(cache_data.items(), key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache_data = dict(sorted_items[:500])
        with open(CONTENT_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] 캐시 저장 실패: {e}")

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
        print(f"[FIX] URL 수정됨: {url}")
    elif url.startswith('ttp://'):
        url = 'h' + url
        print(f"[FIX] URL 수정됨: {url}")
    elif url.startswith('/'):
        url = 'https://page.onstove.com' + url
        print(f"[FIX] 상대경로 URL 수정됨: {url}")
    elif not url.startswith('http'):
        url = 'https://page.onstove.com' + ('/' if not url.startswith('/') else '') + url
        print(f"[FIX] 비정상 URL 수정됨: {url}")
    
    return url

def get_chrome_driver():
    """Chrome 드라이버 초기화"""
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
        '/snap/bin/chromium.chromedriver'
    ]
    
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
    
    try:
        print("[DEBUG] 시스템 기본 ChromeDriver 시도")
        driver = webdriver.Chrome(options=options)
        print("[DEBUG] 시스템 기본 ChromeDriver 성공")
        return driver
    except Exception as e:
        print(f"[DEBUG] 시스템 기본 ChromeDriver 실패: {str(e)[:100]}...")
    
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

def check_discord_webhooks():
    """Discord 웹훅 환경변수 확인 - 수정 사항 1: 환경변수 처리 코드 완전 복원"""
    webhooks = {}
    
    # 버그 알림 웹훅
    bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG') or os.getenv('DISCORD_WEBHOOK_BUG')
    if bug_webhook:
        webhooks['bug'] = bug_webhook
        print("[INFO] 버그 알림 웹훅 설정 완료")
    else:
        print("[WARNING] DISCORD_WEBHOOK_BUG 환경변수가 설정되지 않았습니다.")
    
    # 감성 동향 웹훅 - 핵심 수정
    sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT') or os.getenv('DISCORD_WEBHOOK_SENTIMENT')
    if sentiment_webhook:
        webhooks['sentiment'] = sentiment_webhook
        print("[INFO] 감성 동향 웹훅 설정 완료")
    else:
        print("[WARNING] DISCORD_WEBHOOK_SENTIMENT 환경변수가 설정되지 않았습니다.")
        print("[WARNING] 감성 동향 알림이 비활성화됩니다.")
    
    # 일간 보고서 웹훅
    report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT') or os.getenv('DISCORD_WEBHOOK_REPORT')
    if report_webhook:
        webhooks['report'] = report_webhook
        print("[INFO] 일간 보고서 웹훅 설정 완료")
    else:
        print("[WARNING] DISCORD_WEBHOOK_REPORT 환경변수가 설정되지 않았습니다.")
    
    return webhooks

def send_discord_message(webhook_url: str, message: str, title: str = "Epic7 모니터링"):
    """Discord 메시지 전송"""
    if not webhook_url:
        print("[WARNING] 웹훅 URL이 없어 메시지 전송을 건너뜁니다.")
        return False
    
    try:
        data = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": 0x00ff00,
                "timestamp": datetime.now().isoformat()
            }]
        }
        
        response = requests.post(webhook_url, json=data, timeout=10)
        if response.status_code == 204:
            print("[INFO] Discord 메시지 전송 성공")
            return True
        else:
            print(f"[ERROR] Discord 메시지 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")
        return False

def get_stove_post_content(post_url: str, driver: webdriver.Chrome = None) -> str:
    """스토브 게시글 내용 추출 - 수정 사항 2,3,4: 완전 개선된 버전"""
    
    # 캐시 확인
    cache = load_content_cache()
    url_hash = get_url_hash(post_url)
    
    if url_hash in cache:
        cached_item = cache[url_hash]
        cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
        if datetime.now() - cache_time < timedelta(hours=24):
            print(f"[CACHE] 캐시된 내용 사용: {post_url}")
            return cached_item.get('content', "게시글 내용 확인을 위해 링크를 클릭하세요.")
    
    # Driver 생성 확인
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
        print(f"[DEBUG] 게시글 내용 추출 시도: {post_url}")
        
        # 수정 사항 3: JavaScript 로딩 대기 시간 대폭 증가 (8초 → 30초)
        driver.set_page_load_timeout(30)
        driver.get(post_url)
        
        # 페이지 완전 로딩 대기 - 기존 8초에서 30초로 증가
        print("[DEBUG] 페이지 로딩 대기 중... (30초)")
        time.sleep(15)  # 첫 번째 대기
        
        # JavaScript 완전 로딩 확인
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print("[DEBUG] JavaScript 로딩 완료 확인")
        
        # 추가 동적 콘텐츠 로딩 대기
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(5)
        
        print("[DEBUG] 동적 콘텐츠 로딩 완료")
        
        # 수정 사항 4: 특정 CSS 선택자를 활용한 정확한 게시글 내용 추출
        content_selectors = [
            # 스토브 게시글 전용 선택자 (우선순위 높음)
            'div.s-article-content',
            'div.s-article-content-text',
            'div[class*="s-article-content"]',
            'section.s-article-body',
            'div.s-board-content',
            
            # 일반적인 게시글 선택자
            'div.article-content',
            'div.post-content',
            'div.content-body',
            'main.content',
            
            # 텍스트 영역 선택자
            'div[class*="text-content"]',
            'div[class*="post-body"]',
            'div[class*="article-body"]'
        ]
        
        extracted_content = ""
        successful_selector = ""
        
        # 각 선택자로 내용 추출 시도
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 50:  # 충분한 길이의 텍스트만
                            # 불필요한 텍스트 필터링
                            if not any(skip_text in text.lower() for skip_text in 
                                     ['install stove', '스토브를 설치', '로그인이 필요', 'javascript']):
                                extracted_content = text
                                successful_selector = selector
                                print(f"[SUCCESS] 선택자 '{selector}'로 내용 추출 성공")
                                break
                    
                    if extracted_content:
                        break
                        
            except Exception as e:
                print(f"[DEBUG] 선택자 '{selector}' 실패: {e}")
                continue
        
        # 추출된 내용이 있으면 요약 처리
        if extracted_content:
            # 게시글 내용에서 실제 내용 부분만 추출
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
                # 가장 긴 줄을 게시글 내용으로 선택
                longest_line = max(meaningful_lines, key=len)
                if len(longest_line) > 20:
                    content_summary = extract_content_summary(longest_line)
                    print(f"[SUCCESS] 실제 게시글 내용 추출 성공: {content_summary[:50]}...")
                else:
                    content_summary = extract_content_summary(meaningful_lines[0])
                    print(f"[SUCCESS] 첫 번째 의미있는 내용 추출: {content_summary[:50]}...")
        
        # JavaScript를 통한 대체 추출 방법
        if content_summary == "게시글 내용 확인을 위해 링크를 클릭하세요.":
            try:
                js_content = driver.execute_script("""
                    // 스토브 게시글 내용을 정확히 추출하는 JavaScript
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
                    print(f"[SUCCESS] JavaScript 방식으로 내용 추출 성공: {content_summary[:50]}...")
                    
            except Exception as e:
                print(f"[ERROR] JavaScript 추출 실패: {e}")
        
        # 최후 수단: BeautifulSoup 사용
        if content_summary == "게시글 내용 확인을 위해 링크를 클릭하세요.":
            try:
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # 스토브 전용 태그들 확인
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
                                print(f"[SUCCESS] BeautifulSoup으로 내용 추출 성공: {content_summary[:50]}...")
                                break
                                
            except Exception as e:
                print(f"[ERROR] BeautifulSoup 추출 실패: {e}")
        
        # 디버그 정보 저장
        debug_filename = f"debug_stove_{datetime.now().strftime('%H%M%S')}.html"
        with open(debug_filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"[DEBUG] 디버그용 HTML 저장: {debug_filename}")
        
        # 캐시 저장
        cache[url_hash] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url,
            'selector_used': successful_selector
        }
        save_content_cache(cache)
        
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

def fetch_ruliweb_epic7_board():
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 루리웹 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] 루리웹용 Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://bbs.ruliweb.com/game/84834"
        print(f"[DEBUG] 루리웹 접속 중: {url}")
        
        driver.get(url)
        time.sleep(5)
        
        print("[DEBUG] 루리웹 게시글 목록 검색 중...")
        
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
            print("[WARNING] 루리웹 게시글을 찾을 수 없음. HTML 저장...")
            with open("ruliweb_debug_selenium.html", "w", encoding="utf-8") as f:
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
                        "source": "ruliweb_epic7"
                    }
                    posts.append(post_data)
                    crawled_links.append(link)
                    print(f"[NEW] 루리웹 새 게시글 ({i+1}): {title[:50]}...")
                
            except Exception as e:
                print(f"[ERROR] 루리웹 게시글 {i+1} 처리 오류: {e}")
                continue
        
        print(f"[DEBUG] 루리웹 크롤링 완료: {len(posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] 루리웹 크롤링 실패: {e}")
        if driver:
            try:
                with open("ruliweb_error_debug.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링 (완전 개선 버전)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 스토브 버그 게시판 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] 스토브 버그용 Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        print(f"[DEBUG] 스토브 버그 게시판 접속 중: {url}")
        
        driver.get(url)
        
        print("[DEBUG] 스토브 페이지 로딩 대기 중...")
        time.sleep(15)  # 증가된 대기 시간
        
        # 페이지 완전 로딩 확인
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(5)
        
        html_content = driver.page_source
        with open("stove_bug_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 개선된 JavaScript로 게시글 추출
        user_posts = driver.execute_script("""
            var posts = [];
            var items = document.querySelectorAll('section.s-board-item');
            
            console.log('발견된 전체 섹션:', items.length);
            
            for (var i = 0; i < Math.min(items.length, 15); i++) {
                var item = items[i];
                var link = item.querySelector('a[href*="/view/"]');
                var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
                
                if (link && title && link.href && title.innerText) {
                    var titleText = title.innerText.trim();
                    if (titleText.length > 3) {
                        // 공지/이벤트 제외
                        var isNotice = item.querySelector('.notice, [class*="notice"]');
                        var isEvent = item.querySelector('.event, [class*="event"]');
                        
                        if (!isNotice && !isEvent) {
                            posts.push({
                                title: titleText,
                                href: link.href,
                                id: link.href.split('/').pop()
                            });
                            console.log('게시글 추가:', titleText.substring(0, 30));
                        }
                    }
                }
            }
            
            console.log('최종 추출된 게시글 수:', posts.length);
            return posts;
        """)
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 유저 게시글 발견")
        
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                
                href = fix_stove_url(href)
                
                print(f"[DEBUG] 스토브 버그 게시글 {i}: URL = {href}")
                print(f"[DEBUG] 스토브 버그 게시글 {i}: 제목 = {title[:50]}...")
                
                if href in crawled_links:
                    print(f"[DEBUG] 스토브 버그 게시글 {i}: 이미 크롤링된 링크")
                    continue
                
                if title and href and len(title) > 3:
                    # 개선된 내용 추출 함수 사용
                    content = get_stove_post_content(href, driver)
                    
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_bug"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    print(f"[NEW] 스토브 버그 새 게시글 발견 ({i}): {title[:50]}...")
                    print(f"[CONTENT] 내용: {content[:100]}...")
                else:
                    print(f"[DEBUG] 스토브 버그 게시글 {i}: 조건 미충족")
                
                time.sleep(random.uniform(2, 4))  # 증가된 대기 시간
                
            except Exception as e:
                print(f"[ERROR] 스토브 버그 게시글 {i} 처리 중 오류: {e}")
                continue
        
        print(f"[DEBUG] 스토브 버그 게시판 처리 결과: {len(user_posts)}개 중 새 게시글 {len(posts)}개 발견")
        
    except Exception as e:
        print(f"[ERROR] 스토브 버그 게시판 크롤링 중 오류 발생: {e}")
        
    finally:
        if driver:
            print("[DEBUG] 스토브 버그 Chrome 드라이버 종료 중...")
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def fetch_stove_general_board():
    """스토브 에픽세븐 자유게시판 크롤링 (완전 개선 버전)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 스토브 자유게시판 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] 스토브 자유게시판용 Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST"
        print(f"[DEBUG] 스토브 자유게시판 접속 중: {url}")
        
        driver.get(url)
        
        print("[DEBUG] 스토브 자유게시판 페이지 로딩 대기 중...")
        time.sleep(15)  # 증가된 대기 시간
        
        # 페이지 완전 로딩 확인
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(5)
        
        html_content = driver.page_source
        with open("stove_general_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 동일한 개선된 JavaScript 사용
        user_posts = driver.execute_script("""
            var posts = [];
            var items = document.querySelectorAll('section.s-board-item');
            
            console.log('자유게시판 전체 섹션:', items.length);
            
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
                            console.log('자유게시판 게시글 추가:', titleText.substring(0, 30));
                        }
                    }
                }
            }
            
            console.log('자유게시판 최종 추출 수:', posts.length);
            return posts;
        """)
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 자유게시판 게시글 발견")
        
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                
                href = fix_stove_url(href)
                
                print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: URL = {href}")
                print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 제목 = {title[:50]}...")
                
                if href in crawled_links:
                    print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 이미 크롤링된 링크")
                    continue
                
                if not title or len(title) < 4:
                    print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 조건 미충족")
                    continue
                
                meaningless_patterns = [
                    r'^[.]{3,}$',
                    r'^[ㅋㅎㅗㅜㅑ]{3,}$',
                    r'^[!@#$%^&*()]{3,}$',
                ]
                
                is_meaningless = any(re.match(pattern, title) for pattern in meaningless_patterns)
                if is_meaningless:
                    print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 조건 미충족")
                    continue
                
                # 개선된 내용 추출 함수 사용
                content = get_stove_post_content(href, driver)
                
                post_data = {
                    "title": title,
                    "url": href,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "source": "stove_general"
                }
                posts.append(post_data)
                crawled_links.append(href)
                print(f"[NEW] 스토브 자유게시판 게시글 발견 ({i}): {title[:50]}...")
                print(f"[CONTENT] 내용: {content[:100]}...")
                
                time.sleep(random.uniform(2, 4))  # 증가된 대기 시간
                
            except Exception as e:
                print(f"[ERROR] 스토브 자유게시판 게시글 {i} 처리 중 오류: {e}")
                continue
        
        print(f"[DEBUG] 스토브 자유게시판 처리 완료: {len(posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] 스토브 자유게시판 크롤링 중 오류 발생: {e}")
        
    finally:
        if driver:
            print("[DEBUG] 스토브 자유게시판 Chrome 드라이버 종료 중...")
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 자유게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def process_sentiment_posts(posts):
    """감성 분석된 게시글 처리 및 Discord 알림"""
    webhooks = check_discord_webhooks()
    
    if not posts:
        print("[INFO] 처리할 감성 게시글이 없습니다.")
        return
    
    sentiment_webhook = webhooks.get('sentiment')
    if not sentiment_webhook:
        print(f"[WARNING] 감성 동향 {len(posts)}개 있지만 웹훅 미설정으로 알림 생략")
        return
    
    # 감성별 분류
    positive_posts = [p for p in posts if p.get('sentiment') == 'positive']
    neutral_posts = [p for p in posts if p.get('sentiment') == 'neutral']
    negative_posts = [p for p in posts if p.get('sentiment') == 'negative']
    
    if positive_posts or neutral_posts or negative_posts:
        message = f"📊 **유저 동향 분석 결과**\n\n"
        message += f"😊 긍정: {len(positive_posts)}개\n"
        message += f"😐 중립: {len(neutral_posts)}개\n"
        message += f"😠 부정: {len(negative_posts)}개\n\n"
        
        # 샘플 게시글 추가
        if negative_posts:
            message += "**주요 부정 반응:**\n"
            for post in negative_posts[:3]:
                message += f"• {post['title'][:50]}...\n"
        
        send_discord_message(sentiment_webhook, message, "Epic7 유저 동향")
        print(f"[INFO] 감성 동향 {len(posts)}개 알림 전송 완료")

def crawl_korean_sites():
    """한국 사이트들 크롤링 (환경변수 처리 포함)"""
    all_posts = []
    
    # 환경변수 확인
    webhooks = check_discord_webhooks()
    
    try:
        print("[INFO] === 한국 사이트 크롤링 시작 ===")
        
        print("[INFO] 1/3 루리웹 에픽세븐 게시판 크롤링")
        ruliweb_posts = fetch_ruliweb_epic7_board()
        all_posts.extend(ruliweb_posts)
        print(f"[INFO] 루리웹: {len(ruliweb_posts)}개 새 게시글")
        
        time.sleep(random.uniform(5, 8))
        
        print("[INFO] 2/3 스토브 버그 게시판 크롤링")
        stove_bug_posts = fetch_stove_bug_board()
        all_posts.extend(stove_bug_posts)
        print(f"[INFO] 스토브 버그: {len(stove_bug_posts)}개 새 게시글")
        
        time.sleep(random.uniform(5, 8))
        
        print("[INFO] 3/3 스토브 자유게시판 크롤링")
        stove_general_posts = fetch_stove_general_board()
        all_posts.extend(stove_general_posts)
        print(f"[INFO] 스토브 자유: {len(stove_general_posts)}개 새 게시글")
        
        # 감성 분석 결과가 있다면 알림 전송
        sentiment_posts = [p for p in all_posts if p.get('sentiment')]
        if sentiment_posts:
            process_sentiment_posts(sentiment_posts)
        
    except Exception as e:
        print(f"[ERROR] 한국 사이트 크롤링 실패: {e}")
    
    print(f"[INFO] === 한국 사이트 크롤링 완료: 총 {len(all_posts)}개 새 게시글 ===")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트들 크롤링"""
    print("[DEBUG] 글로벌 사이트 크롤링은 아직 구현되지 않음")
    return []

def get_all_posts_for_report():
    """일일 리포트용 - 새 게시글 수집"""
    print("[INFO] 일일 리포트용 게시글 수집 중...")
    return crawl_korean_sites()

def test_korean_crawling():
    """한국 사이트 크롤링 테스트"""
    print("=== 한국 사이트 크롤링 테스트 ===")
    
    # 환경변수 체크
    print("\n환경변수 확인:")
    webhooks = check_discord_webhooks()
    
    print("\n1. 루리웹 테스트:")
    ruliweb_posts = fetch_ruliweb_epic7_board()
    
    print("\n2. 스토브 버그 테스트:")
    stove_bug_posts = fetch_stove_bug_board()
    
    print("\n3. 스토브 자유 테스트:")
    stove_general_posts = fetch_stove_general_board()
    
    print(f"\n=== 테스트 결과 ===")
    print(f"루리웹: {len(ruliweb_posts)}개")
    print(f"스토브 버그: {len(stove_bug_posts)}개")
    print(f"스토브 자유: {len(stove_general_posts)}개")
    print(f"총 합계: {len(ruliweb_posts) + len(stove_bug_posts) + len(stove_general_posts)}개")
    
    print(f"\n=== 내용 추출 결과 샘플 ===")
    for i, post in enumerate((stove_bug_posts + stove_general_posts)[:3]):
        print(f"{i+1}. {post['title'][:50]}...")
        print(f"   내용: {post['content'][:100]}...")
        print(f"   소스: {post['source']}")
        print()
    
    return ruliweb_posts + stove_bug_posts + stove_general_posts

def test_content_extraction():
    """게시글 내용 추출 단독 테스트"""
    print("=== 게시글 내용 추출 테스트 ===")
    
    test_urls = [
        "https://page.onstove.com/epicseven/kr/view/10868434",
        "https://page.onstove.com/epicseven/kr/view/10650067",
        "https://page.onstove.com/epicseven/kr/view/10794251"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n{i}. 테스트 URL: {url}")
        content = get_stove_post_content(url)
        print(f"   추출된 내용: {content}")
        print(f"   길이: {len(content)}자")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test_content":
        test_content_extraction()
    else:
        test_korean_crawling()