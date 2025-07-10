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

# SeleniumBase 추가
from seleniumbase import Driver

# 중복 방지를 위한 링크 저장 파일
CRAWLED_LINKS_FILE = "crawled_links.json"

def load_crawled_links():
    """이미 크롤링된 링크들을 로드"""
    if os.path.exists(CRAWLED_LINKS_FILE):
        try:
            with open(CRAWLED_LINKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 구 버전 호환성 (리스트 형태)
                if isinstance(data, list):
                    return {"links": data, "last_updated": datetime.now().isoformat()}
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            print("[WARNING] crawled_links.json 파일 읽기 실패, 새로 생성")
    
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data):
    """크롤링된 링크들을 저장 (최대 1000개 유지)"""
    try:
        # 최신 1000개만 유지 (메모리 절약)
        if len(link_data["links"]) > 1000:
            link_data["links"] = link_data["links"][-1000:]
        
        link_data["last_updated"] = datetime.now().isoformat()
        
        with open(CRAWLED_LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"[ERROR] 링크 저장 실패: {e}")

def get_chrome_driver():
    """Chrome 드라이버 초기화 (버전 호환성 우선)"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript-harmony-shipping')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--window-size=1920,1080')
    
    # 봇 탐지 우회 설정 추가
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 랜덤 User-Agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    
    # 추가 성능 최적화
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
    
    driver = None
    
    # 호환 가능한 ChromeDriver 경로들 (버전별 우선순위)
    possible_paths = [
        '/usr/bin/chromedriver',  # 우분투 패키지 (가장 호환성 좋음)
        '/usr/local/bin/chromedriver',  # 수동 설치
        '/snap/bin/chromium.chromedriver'  # Snap 패키지
    ]
    
    # 방법 1: 수동 경로별 시도 (버전 호환성 우선)
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
    
    # 방법 2: 시스템 기본 ChromeDriver
    try:
        print("[DEBUG] 시스템 기본 ChromeDriver 시도")
        driver = webdriver.Chrome(options=options)
        print("[DEBUG] 시스템 기본 ChromeDriver 성공")
        return driver
    except Exception as e:
        print(f"[DEBUG] 시스템 기본 ChromeDriver 실패: {str(e)[:100]}...")
    
    # 방법 3: WebDriver Manager (최후 수단)
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

def fetch_arca_epic7_seleniumbase():
    """SeleniumBase UC 모드로 아카라이브 크롤링 (Cloudflare 우회)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] SeleniumBase 아카라이브 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] SeleniumBase UC 드라이버 초기화 중...")
        
        # SeleniumBase UC 모드 드라이버 생성
        driver = Driver(
            uc=True,                    # Undetected Chrome 모드
            headless=True,              # 헤드리스 모드
            stealth=True,               # 스텔스 모드 
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            do_not_track=True,          # Do Not Track 헤더
            undetectable=True,          # 탐지 방지 강화
            block_images=True,          # 이미지 차단으로 속도 향상
            no_sandbox=True,            # 샌드박스 비활성화
            disable_gpu=True,           # GPU 비활성화
        )
        
        print("[DEBUG] SeleniumBase 드라이버 초기화 완료")
        
        url = "https://arca.live/b/epic7"
        print(f"[DEBUG] 아카라이브 접속 시도: {url}")
        
        # 페이지 접속
        driver.get(url)
        
        # Cloudflare 검증 대기 (더 긴 시간)
        print("[DEBUG] Cloudflare 우회 및 페이지 로딩 대기...")
        time.sleep(15)  # SeleniumBase는 더 오래 기다림
        
        # 페이지 상태 확인
        page_title = driver.get_title()
        current_url = driver.get_current_url()
        print(f"[DEBUG] 페이지 제목: {page_title}")
        print(f"[DEBUG] 현재 URL: {current_url}")
        
        # Cloudflare 검증 중인지 확인
        page_source = driver.get_page_source()
        if "Just a moment" in page_title or "Verifying" in page_source or "Ray ID" in page_source:
            print("[WARNING] 여전히 Cloudflare 검증 중... 추가 대기")
            time.sleep(20)
            
            # 재확인
            page_title = driver.get_title()
            page_source = driver.get_page_source()
            print(f"[DEBUG] 재확인 페이지 제목: {page_title}")
        
        # 성공적으로 통과했는지 확인
        if "Just a moment" not in page_title and "에픽세븐" in page_source:
            print("[SUCCESS] Cloudflare 우회 성공!")
            
            # 게시글 추출 시도
            print("[DEBUG] 게시글 목록 검색 중...")
            
            # 다양한 선택자로 게시글 찾기
            selectors = [
                "a[href*='/b/epic7/'][href*='?p=']",  # 게시글 링크 패턴
                ".vrow .title a",                     # 기본 선택자
                ".article-wrapper .title a",          # 대체 선택자 1
                ".list-table .title a",               # 대체 선택자 2
                ".article-list .title a",             # 대체 선택자 3
                "a[title][href*='/b/epic7/']"         # title 속성이 있는 링크
            ]
            
            articles = []
            for selector in selectors:
                try:
                    articles = driver.find_elements("css selector", selector)
                    if articles:
                        print(f"[DEBUG] SeleniumBase 선택자 성공: {selector} ({len(articles)}개)")
                        break
                except Exception as e:
                    print(f"[DEBUG] 선택자 실패 {selector}: {e}")
                    continue
            
            # JavaScript로 동적 검색도 시도
            if not articles:
                print("[DEBUG] JavaScript로 게시글 동적 검색...")
                articles_js = driver.execute_script("""
                    var articles = [];
                    var links = document.querySelectorAll('a');
                    
                    for (var i = 0; i < links.length; i++) {
                        var link = links[i];
                        var href = link.href;
                        var text = link.innerText || link.textContent || link.title || '';
                        
                        if (href && href.includes('/b/epic7/') && 
                            text.length > 3 && 
                            !text.includes('공지') && 
                            !text.includes('필독') &&
                            !text.includes('이벤트')) {
                            articles.push({
                                title: text.trim(),
                                href: href
                            });
                        }
                    }
                    
                    return articles.slice(0, 20);
                """)
                
                if articles_js:
                    print(f"[DEBUG] JavaScript로 {len(articles_js)}개 게시글 발견")
                    for item in articles_js:
                        if item['href'] not in crawled_links:
                            post_data = {
                                "title": item['title'],
                                "url": item['href'],
                                "timestamp": datetime.now().isoformat(),
                                "source": "arca_epic7"
                            }
                            posts.append(post_data)
                            crawled_links.append(item['href'])
                            print(f"[NEW] SeleniumBase 아카라이브 새 게시글: {item['title'][:50]}...")
            
            # 일반적인 요소 처리
            else:
                for i, article in enumerate(articles[:20]):
                    try:
                        title = article.text.strip() if hasattr(article, 'text') else article.get_attribute('title')
                        link = article.get_attribute('href') if hasattr(article, 'get_attribute') else None
                        
                        if not title or not link or len(title) < 3:
                            continue
                        
                        # 공지사항 필터링
                        if any(keyword in title for keyword in ['공지', '필독', '이벤트', '안내', '규칙']):
                            continue
                        
                        # URL 정규화
                        if link.startswith('/'):
                            link = 'https://arca.live' + link
                        
                        if link not in crawled_links:
                            post_data = {
                                "title": title,
                                "url": link,
                                "timestamp": datetime.now().isoformat(),
                                "source": "arca_epic7"
                            }
                            posts.append(post_data)
                            crawled_links.append(link)
                            print(f"[NEW] SeleniumBase 아카라이브 새 게시글 ({i+1}): {title[:50]}...")
                            
                            time.sleep(random.uniform(0.5, 1.0))
                    
                    except Exception as e:
                        print(f"[ERROR] SeleniumBase 게시글 {i+1} 처리 오류: {e}")
                        continue
            
        else:
            print("[FAIL] Cloudflare 우회 실패 - SeleniumBase도 차단됨")
            # 디버깅용 HTML 저장
            with open("arca_seleniumbase_debug.html", "w", encoding="utf-8") as f:
                f.write(page_source)
        
        print(f"[DEBUG] SeleniumBase 아카라이브 크롤링 완료: {len(posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] SeleniumBase 아카라이브 크롤링 실패: {e}")
        if driver:
            try:
                with open("arca_seleniumbase_error.html", "w", encoding="utf-8") as f:
                    f.write(driver.get_page_source())
            except:
                pass
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

def fetch_arca_epic7_board():
    """아카라이브 에픽세븐 채널 크롤링 (SeleniumBase 우선, 기존 방법 폴백)"""
    posts = []
    
    # 1차: SeleniumBase UC 모드 시도
    try:
        print("[INFO] === SeleniumBase UC 모드로 아카라이브 크롤링 시도 ===")
        posts = fetch_arca_epic7_seleniumbase()
        if posts:
            print(f"[SUCCESS] SeleniumBase로 {len(posts)}개 아카라이브 게시글 수집 성공!")
            return posts
    except Exception as e:
        print(f"[WARN] SeleniumBase 크롤링 실패: {e}")
    
    # 2차: 기존 방법 폴백
    try:
        print("[INFO] === 기존 방법으로 아카라이브 크롤링 폴백 시도 ===")
        posts = fetch_arca_epic7_board_legacy()
        if posts:
            print(f"[SUCCESS] 기존 방법으로 {len(posts)}개 아카라이브 게시글 수집!")
            return posts
    except Exception as e:
        print(f"[WARN] 기존 방법도 실패: {e}")
    
    print("[FAIL] 모든 아카라이브 크롤링 방법 실패")
    return []

def fetch_arca_epic7_board_legacy():
    """기존 아카라이브 크롤링 방법 (폴백용)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 기존 아카라이브 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] 기존 Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        # 봇 탐지 우회 스크립트
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("delete window.chrome")
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(15)
        
        url = "https://arca.live/b/epic7"
        print(f"[DEBUG] 아카라이브 접속 시도: {url}")
        
        driver.get(url)
        
        # Cloudflare 검증 대기
        print("[DEBUG] Cloudflare 검증 및 페이지 로딩 대기 중...")
        time.sleep(random.uniform(10, 15))
        
        # 페이지 상태 확인
        page_title = driver.title
        page_source_preview = driver.page_source[:500]
        print(f"[DEBUG] 페이지 제목: {page_title}")
        
        if "Verifying" in page_title or "security" in page_title.lower() or "Ray ID" in page_source_preview:
            print("[WARNING] Cloudflare 검증 감지, 추가 대기...")
            time.sleep(random.uniform(15, 20))
        
        # 다양한 방법으로 게시글 추출 시도
        print("[DEBUG] 게시글 목록 검색 중...")
        
        # 방법 1: 일반적인 선택자들
        selectors = [
            "a[href*='/b/epic7/'][href*='?p=']",  # 게시글 링크 패턴
            ".vrow .title a",                     # 기본 선택자
            ".article-wrapper .title a",          # 대체 선택자 1
            ".list-table .title a",               # 대체 선택자 2
            ".article-list .title a",             # 대체 선택자 3
            "a[title][href*='/b/epic7/']"         # title 속성이 있는 링크
        ]
        
        articles = []
        for selector in selectors:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    print(f"[DEBUG] 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except TimeoutException:
                continue
        
        # 방법 2: JavaScript로 동적 검색
        if not articles:
            print("[DEBUG] JavaScript로 게시글 동적 검색...")
            articles_js = driver.execute_script("""
                var articles = [];
                var links = document.querySelectorAll('a');
                
                for (var i = 0; i < links.length; i++) {
                    var link = links[i];
                    var href = link.href;
                    var text = link.innerText || link.textContent || link.title || '';
                    
                    if (href && href.includes('/b/epic7/') && 
                        text.length > 3 && 
                        !text.includes('공지') && 
                        !text.includes('필독') &&
                        !text.includes('이벤트')) {
                        articles.push({
                            title: text.trim(),
                            href: href
                        });
                    }
                }
                
                return articles.slice(0, 20);
            """)
            
            if articles_js:
                print(f"[DEBUG] JavaScript로 {len(articles_js)}개 게시글 발견")
                for item in articles_js:
                    if item['href'] not in crawled_links:
                        post_data = {
                            "title": item['title'],
                            "url": item['href'],
                            "timestamp": datetime.now().isoformat(),
                            "source": "arca_epic7"
                        }
                        posts.append(post_data)
                        crawled_links.append(item['href'])
                        print(f"[NEW] 아카라이브 새 게시글: {item['title'][:50]}...")
        
        # 방법 3: 일반적인 요소 처리
        else:
            for i, article in enumerate(articles[:20]):
                try:
                    title = article.text.strip() if hasattr(article, 'text') else article.get_attribute('title')
                    link = article.get_attribute('href') if hasattr(article, 'get_attribute') else None
                    
                    if not title or not link or len(title) < 3:
                        continue
                    
                    # 공지사항 필터링
                    if any(keyword in title for keyword in ['공지', '필독', '이벤트', '안내', '규칙']):
                        continue
                    
                    # URL 정규화
                    if link.startswith('/'):
                        link = 'https://arca.live' + link
                    
                    if link not in crawled_links:
                        post_data = {
                            "title": title,
                            "url": link,
                            "timestamp": datetime.now().isoformat(),
                            "source": "arca_epic7"
                        }
                        posts.append(post_data)
                        crawled_links.append(link)
                        print(f"[NEW] 아카라이브 새 게시글 ({i+1}): {title[:50]}...")
                        
                        time.sleep(random.uniform(0.5, 1.0))
                
                except Exception as e:
                    print(f"[ERROR] 아카라이브 게시글 {i+1} 처리 오류: {e}")
                    continue
        
        # 디버깅용 HTML 저장
        if not posts:
            with open("arca_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("[DEBUG] 디버깅용 HTML 저장: arca_debug_selenium.html")
        
        print(f"[DEBUG] 기존 아카라이브 크롤링 완료: {len(posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] 기존 아카라이브 크롤링 실패: {e}")
        if driver:
            try:
                with open("arca_error_debug.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
    
    finally:
        if driver:
            driver.quit()
    
    # 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

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
        
        # 루리웹 게시글 추출
        selectors = [
            ".subject_link",                  # 주제 링크 (기본)
            ".table_body .subject a",         # 테이블 내 주제 링크
            "td.subject a",                   # 테이블 셀 내 링크
            "a[href*='/read/']",              # 게시글 읽기 링크 패턴
            ".board_list_table .subject_link", # 게시판 목록 테이블
            "table tr td a[href*='read']"     # 테이블 기반 링크
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
        
        # 게시글 정보 추출
        for i, article in enumerate(articles[:15]):
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                # 공지사항 및 추천글 필터링
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천', '베스트', '공지사항']):
                    continue
                
                # URL 정규화
                if link.startswith('/'):
                    link = 'https://bbs.ruliweb.com' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
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
    
    # 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    return posts

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링 (기존 로직 유지)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 스토브 크롤링 시작 - 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] 스토브용 Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        print(f"[DEBUG] 스토브 접속 중: {url}")
        
        driver.get(url)
        
        print("[DEBUG] 스토브 페이지 로딩 대기 중...")
        time.sleep(8)
        
        # 스크롤하여 실제 유저 게시글 영역까지 로딩
        print("[DEBUG] 유저 게시글 영역까지 스크롤...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # 디버깅용 HTML 저장
        html_content = driver.page_source
        with open("stove_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 실제 유저 게시글 영역 탐색 중...")
        
        # 기존 JavaScript 로직 사용
        user_posts = driver.execute_script("""
            var userPosts = [];
            
            var sections = document.querySelectorAll('section.s-board-item');
            console.log('전체 게시글 섹션 수:', sections.length);
            
            var officialIds = ['10518001', '10855687', '10855562', '10855132'];
            
            for (var i = 0; i < sections.length; i++) {
                var section = sections[i];
                
                try {
                    var linkElement = section.querySelector('a.s-board-link');
                    if (!linkElement) continue;
                    
                    var href = linkElement.href;
                    if (!href) continue;
                    
                    var idMatch = href.match(/\/view\/(\d+)/);
                    if (!idMatch) continue;
                    var postId = idMatch[1];
                    
                    if (officialIds.includes(postId)) {
                        console.log('공지 ID 제외:', postId);
                        continue;
                    }
                    
                    var isNotice = section.querySelector('i.element-badge__s.notice');
                    var isEvent = section.querySelector('i.element-badge__s.event');
                    var isOfficial = section.querySelector('span.s-profile-staff-official');
                    
                    if (isNotice || isEvent || isOfficial) {
                        console.log('공지/이벤트 제외:', postId);
                        continue;
                    }
                    
                    var titleElement = section.querySelector('h3.s-board-title span.s-board-title-text');
                    if (!titleElement) {
                        console.log('제목 요소 없음:', postId);
                        continue;
                    }
                    
                    var title = titleElement.innerText.trim();
                    if (!title || title.length < 3) {
                        console.log('제목 없음 또는 너무 짧음:', postId);
                        continue;
                    }
                    
                    userPosts.push({
                        title: title.substring(0, 200).trim(),
                        href: href,
                        id: postId
                    });
                    
                    console.log('유저 게시글 추가:', title.substring(0, 30));
                    
                } catch (e) {
                    console.log('게시글 처리 오류:', e.message);
                    continue;
                }
            }
            
            console.log('최종 발견된 유저 게시글 수:', userPosts.length);
            return userPosts.slice(0, 15);
        """)
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 유저 게시글 발견")
        
        # 유저 게시글 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                
                # URL 수정
                if href.startswith('ttps://'):
                    href = 'h' + href
                elif not href.startswith('http'):
                    href = "https://page.onstove.com" + href
                
                print(f"[DEBUG] 스토브 게시글 {i}: URL = {href[-50:]}")
                print(f"[DEBUG] 스토브 게시글 {i}: 제목 = {title[:50]}...")
                
                if href in crawled_links:
                    print(f"[DEBUG] 스토브 게시글 {i}: 이미 크롤링된 링크")
                    continue
                
                if title and href and len(title) > 3:
                    post_data = {
                        "title": title,
                        "url": href,
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_bug"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    print(f"[NEW] 스토브 새 게시글 발견 ({i}): {title[:50]}...")
                else:
                    print(f"[DEBUG] 스토브 게시글 {i}: 조건 미충족")
                
            except Exception as e:
                print(f"[ERROR] 스토브 게시글 {i} 처리 중 오류: {e}")
                continue
        
        print(f"[DEBUG] 스토브 처리 결과: {len(user_posts)}개 중 새 게시글 {len(posts)}개 발견")
        
    except Exception as e:
        print(f"[ERROR] 스토브 크롤링 중 오류 발생: {e}")
        
    finally:
        if driver:
            print("[DEBUG] 스토브 Chrome 드라이버 종료 중...")
            driver.quit()
    
    # 중복 방지 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def crawl_arca_sites():
    """국내 사이트들 크롤링 (아카라이브 + 루리웹 + 스토브)"""
    all_posts = []
    
    try:
        print("[INFO] === 국내 사이트 크롤링 시작 ===")
        
        # 1. 아카라이브 크롤링 (SeleniumBase 우선)
        print("[INFO] 1/3 아카라이브 에픽세븐 채널 크롤링")
        arca_posts = fetch_arca_epic7_board()
        all_posts.extend(arca_posts)
        print(f"[INFO] 아카라이브: {len(arca_posts)}개 새 게시글")
        
        # 크롤링 간 지연 (서버 부하 방지)
        time.sleep(random.uniform(5, 8))
        
        # 2. 루리웹 크롤링
        print("[INFO] 2/3 루리웹 에픽세븐 게시판 크롤링")
        ruliweb_posts = fetch_ruliweb_epic7_board()
        all_posts.extend(ruliweb_posts)
        print(f"[INFO] 루리웹: {len(ruliweb_posts)}개 새 게시글")
        
        # 크롤링 간 지연
        time.sleep(random.uniform(5, 8))
        
        # 3. 스토브 크롤링
        print("[INFO] 3/3 스토브 버그 게시판 크롤링")
        stove_posts = fetch_stove_bug_board()
        all_posts.extend(stove_posts)
        print(f"[INFO] 스토브: {len(stove_posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] 국내 사이트 크롤링 실패: {e}")
    
    print(f"[INFO] === 국내 사이트 크롤링 완료: 총 {len(all_posts)}개 새 게시글 ===")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트들 크롤링 (추후 구현)"""
    print("[DEBUG] 글로벌 사이트 크롤링은 아직 구현되지 않음")
    return []

def get_all_posts_for_report():
    """일일 리포트용 - 새 게시글만이 아닌 최근 24시간 게시글"""
    print("[INFO] 일일 리포트용 게시글 수집 중...")
    return crawl_arca_sites() + crawl_global_sites()

# 테스트 함수
def test_all_crawling():
    """전체 크롤링 테스트"""
    print("=== 전체 크롤링 테스트 (SeleniumBase 포함) ===")
    
    print("\n1. 아카라이브 테스트 (SeleniumBase UC 모드):")
    arca_posts = fetch_arca_epic7_board()
    
    print("\n2. 루리웹 테스트:")
    ruliweb_posts = fetch_ruliweb_epic7_board()
    
    print("\n3. 스토브 테스트:")
    stove_posts = fetch_stove_bug_board()
    
    print(f"\n=== 테스트 결과 ===")
    print(f"아카라이브: {len(arca_posts)}개")
    print(f"루리웹: {len(ruliweb_posts)}개")
    print(f"스토브: {len(stove_posts)}개")
    print(f"총 합계: {len(arca_posts) + len(ruliweb_posts) + len(stove_posts)}개")
    
    return arca_posts + ruliweb_posts + stove_posts

if __name__ == "__main__":
    test_all_crawling()