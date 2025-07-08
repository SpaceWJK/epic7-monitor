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
import time
from datetime import datetime, timedelta
import re

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
    """Chrome 드라이버 초기화 (여러 방법 시도)"""
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
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    
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
    
    # 방법 1: 시스템 ChromeDriver 직접 사용
    try:
        driver = webdriver.Chrome(options=options)
        print("[DEBUG] 시스템 ChromeDriver로 초기화 성공")
        return driver
    except Exception as e1:
        print(f"[DEBUG] 시스템 ChromeDriver 실패: {e1}")
    
    # 방법 2: 수동 경로 지정
    possible_paths = [
        '/usr/local/bin/chromedriver',
        '/usr/bin/chromedriver',
        '/snap/bin/chromium.chromedriver'
    ]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                print(f"[DEBUG] 수동 경로에서 ChromeDriver 로드 성공: {path}")
                return driver
        except Exception as e:
            print(f"[DEBUG] 경로 {path} 실패: {e}")
            continue
    
    # 방법 3: WebDriver Manager 사용 (백업)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("[DEBUG] WebDriver Manager로 초기화 성공")
        return driver
    except Exception as e3:
        print(f"[DEBUG] WebDriver Manager 실패: {e3}")
    
    raise Exception("모든 ChromeDriver 초기화 방법이 실패했습니다.")

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링 (Selenium 버전)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    driver = None
    try:
        print("[DEBUG] Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        # 페이지 로드 타임아웃 설정
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        print(f"[DEBUG] 스토브 접속 중: {url}")
        
        # 페이지 로딩
        driver.get(url)
        
        # 동적 콘텐츠 로딩 대기
        print("[DEBUG] 페이지 로딩 대기 중...")
        time.sleep(5)
        
        # 스크롤하여 콘텐츠 로딩 유도
        print("[DEBUG] 스크롤로 콘텐츠 로딩 유도 중...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        # 디버깅용 HTML 저장
        html_content = driver.page_source
        with open("stove_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 게시글 링크 탐색 중...")
        
        # 다양한 셀렉터로 게시글 찾기
        selectors = [
            "a[href*='/epicseven/kr/view/']",
            ".board-list .list-row a",
            ".post-list-wrap .post-item a", 
            ".board-item-wrap .board-item a",
            ".title a",
            ".subject a",
            "[data-href*='/view/']"
        ]
        
        found_elements = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"[DEBUG] '{selector}'로 {len(elements)}개 요소 발견")
                    found_elements = elements
                    break
            except Exception as e:
                print(f"[DEBUG] '{selector}' 시도 중 오류: {e}")
                continue
        
        # 대안: 모든 링크에서 view 패턴 찾기
        if not found_elements:
            print("[DEBUG] 대안 방법으로 모든 링크 탐색 중...")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            found_elements = [link for link in all_links if '/epicseven/kr/view/' in (link.get_attribute('href') or '')]
            print(f"[DEBUG] 대안 방법으로 {len(found_elements)}개 게시글 링크 발견")
        
        if not found_elements:
            print("[ERROR] 게시글을 찾을 수 없습니다.")
            print("[DEBUG] HTML 구조 확인을 위해 stove_debug_selenium.html 파일을 확인하세요")
            return posts
        
        # 게시글 정보 추출
        for i, element in enumerate(found_elements[:15]):  # 최신 15개 체크
            try:
                href = element.get_attribute('href')
                if not href:
                    continue
                
                if not href.startswith('http'):
                    href = "https://page.onstove.com" + href
                
                # 이미 처리된 링크인지 확인
                if href in crawled_links:
                    continue
                
                # 제목 추출
                title = ""
                
                # 방법 1: 링크 텍스트 직접
                link_text = element.text.strip()
                if link_text and len(link_text) > 3:
                    title = link_text
                
                # 방법 2: 부모 요소에서 제목 찾기
                if not title:
                    try:
                        parent = element.find_element(By.XPATH, "..")
                        parent_text = parent.text.strip()
                        if parent_text and len(parent_text) > 3:
                            title = parent_text
                    except:
                        pass
                
                # 방법 3: 제목 관련 요소 찾기
                if not title:
                    try:
                        title_selectors = ['.title', '.subject', '.post-title', '.board-title']
                        for sel in title_selectors:
                            title_elem = element.find_element(By.CSS_SELECTOR, sel)
                            if title_elem:
                                title = title_elem.text.strip()
                                break
                    except:
                        pass
                
                # 제목 정리
                if title:
                    title = re.sub(r'\s+', ' ', title).strip()  # 공백 정리
                    title = title[:200]  # 길이 제한
                
                if title and href and len(title) > 3:
                    post_data = {
                        "title": title,
                        "url": href,
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_bug"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    print(f"[NEW] 새 게시글 발견 ({i+1}): {title[:50]}...")
                
            except Exception as e:
                print(f"[ERROR] 게시글 {i+1} 파싱 중 오류: {e}")
                continue
        
    except TimeoutException:
        print("[ERROR] 페이지 로딩 타임아웃")
    except WebDriverException as e:
        print(f"[ERROR] WebDriver 오류: {e}")
    except Exception as e:
        print(f"[ERROR] 스토브 크롤링 중 오류 발생: {e}")
        
    finally:
        if driver:
            print("[DEBUG] Chrome 드라이버 종료 중...")
            driver.quit()
    
    # 중복 방지 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def fetch_stove_general_board():
    """스토브 에픽세븐 일반 게시판 크롤링"""
    # TODO: 필요시 구현
    print("[DEBUG] 일반 게시판 크롤링은 아직 구현되지 않음")
    return []

def crawl_arca_sites():
    """국내 사이트들 크롤링"""
    all_posts = []
    
    try:
        # 스토브 버그 게시판
        print("[INFO] 스토브 버그 게시판 크롤링 시작")
        stove_bug_posts = fetch_stove_bug_board()
        all_posts.extend(stove_bug_posts)
        
        # TODO: 추가 사이트들
        # stove_general_posts = fetch_stove_general_board()
        # all_posts.extend(stove_general_posts)
        
    except Exception as e:
        print(f"[ERROR] ARCA 사이트 크롤링 실패: {e}")
    
    print(f"[INFO] ARCA 크롤링 완료: {len(all_posts)}개 새 게시글")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트들 크롤링"""
    print("[DEBUG] 글로벌 사이트 크롤링은 아직 구현되지 않음")
    return []

def get_all_posts_for_report():
    """일일 리포트용 - 새 게시글만이 아닌 최근 24시간 게시글"""
    # daily report는 새 게시글이 아닌 최근 게시글들을 분석
    print("[INFO] 일일 리포트용 게시글 수집 중...")
    
    # 임시로 현재 크롤링 결과 반환
    # TODO: 실제로는 최근 24시간 게시글을 별도 수집해야 함
    return crawl_arca_sites() + crawl_global_sites()
