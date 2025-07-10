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

# 중복 방지를 위한 링크 저장 파일
CRAWLED_LINKS_FILE = "crawled_links.json"

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

def get_chrome_driver():
    """Chrome 드라이버 초기화 (최적화)"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--window-size=1920,1080')
    
    # 봇 탐지 우회 설정
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
    
    # 성능 최적화
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
    
    # 호환 가능한 ChromeDriver 경로들
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver',
        '/snap/bin/chromium.chromedriver'
    ]
    
    # 방법 1: 수동 경로별 시도
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
    """스토브 에픽세븐 버그 게시판 크롤링"""
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
        time.sleep(8)
        
        # 스크롤하여 실제 유저 게시글 영역까지 로딩
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
        with open("stove_bug_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 스토브 버그 게시판 게시글 영역 탐색 중...")
        
        # JavaScript로 게시글 추출
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
                
                # URL 수정 (중요: ttps → https 버그 수정)
                if href.startswith('ttps://'):
                    href = 'h' + href
                elif not href.startswith('http'):
                    href = "https://page.onstove.com" + href
                
                print(f"[DEBUG] 스토브 버그 게시글 {i}: URL = {href[-50:]}")
                print(f"[DEBUG] 스토브 버그 게시글 {i}: 제목 = {title[:50]}...")
                
                if href in crawled_links:
                    print(f"[DEBUG] 스토브 버그 게시글 {i}: 이미 크롤링된 링크")
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
                    print(f"[NEW] 스토브 버그 새 게시글 발견 ({i}): {title[:50]}...")
                else:
                    print(f"[DEBUG] 스토브 버그 게시글 {i}: 조건 미충족")
                
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
    
    # 중복 방지 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def fetch_stove_general_board():
    """스토브 에픽세븐 자유게시판 크롤링 (신규 추가)"""
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
        time.sleep(8)
        
        # 스크롤하여 실제 유저 게시글 영역까지 로딩
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
        with open("stove_general_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 스토브 자유게시판 게시글 영역 탐색 중...")
        
        # JavaScript로 게시글 추출
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
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 자유게시판 게시글 발견")
        
        # 유저 게시글 처리
        for i, post_info in enumerate(user_posts, 1):
            try:
                href = post_info['href']
                title = post_info['title']
                
                # URL 수정 (중요: ttps → https 버그 수정)
                if href.startswith('ttps://'):
                    href = 'h' + href
                elif not href.startswith('http'):
                    href = "https://page.onstove.com" + href
                
                print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: URL = {href[-50:]}")
                print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 제목 = {title[:50]}...")
                
                if href in crawled_links:
                    print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 이미 크롤링된 링크")
                    continue
                
                if title and href and len(title) > 3:
                    post_data = {
                        "title": title,
                        "url": href,
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_general"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    print(f"[NEW] 스토브 자유게시판 게시글 발견 ({i}): {title[:50]}...")
                else:
                    print(f"[DEBUG] 스토브 자유게시판 게시글 {i}: 조건 미충족")
                
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
    
    # 중복 방지 링크 저장
    link_data["links"] = crawled_links
    save_crawled_links(link_data)
    
    print(f"[DEBUG] 스토브 자유게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def crawl_korean_sites():
    """한국 사이트들 크롤링 (루리웹 + 스토브 버그/자유게시판)"""
    all_posts = []
    
    try:
        print("[INFO] === 한국 사이트 크롤링 시작 ===")
        
        # 1. 루리웹 크롤링
        print("[INFO] 1/3 루리웹 에픽세븐 게시판 크롤링")
        ruliweb_posts = fetch_ruliweb_epic7_board()
        all_posts.extend(ruliweb_posts)
        print(f"[INFO] 루리웹: {len(ruliweb_posts)}개 새 게시글")
        
        # 크롤링 간 지연 (서버 부하 방지)
        time.sleep(random.uniform(5, 8))
        
        # 2. 스토브 버그 게시판 크롤링
        print("[INFO] 2/3 스토브 버그 게시판 크롤링")
        stove_bug_posts = fetch_stove_bug_board()
        all_posts.extend(stove_bug_posts)
        print(f"[INFO] 스토브 버그: {len(stove_bug_posts)}개 새 게시글")
        
        # 크롤링 간 지연
        time.sleep(random.uniform(5, 8))
        
        # 3. 스토브 자유게시판 크롤링
        print("[INFO] 3/3 스토브 자유게시판 크롤링")
        stove_general_posts = fetch_stove_general_board()
        all_posts.extend(stove_general_posts)
        print(f"[INFO] 스토브 자유: {len(stove_general_posts)}개 새 게시글")
        
    except Exception as e:
        print(f"[ERROR] 한국 사이트 크롤링 실패: {e}")
    
    print(f"[INFO] === 한국 사이트 크롤링 완료: 총 {len(all_posts)}개 새 게시글 ===")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트들 크롤링 (추후 구현 예정)"""
    print("[DEBUG] 글로벌 사이트 크롤링은 아직 구현되지 않음")
    return []

def get_all_posts_for_report():
    """일일 리포트용 - 한국 사이트 모든 게시글"""
    print("[INFO] 일일 리포트용 게시글 수집 중...")
    return crawl_korean_sites()

# 테스트 함수
def test_korean_crawling():
    """한국 사이트 크롤링 테스트"""
    print("=== 한국 사이트 크롤링 테스트 ===")
    
    print("\n1. 루리웹 테스트:")
    ruliweb_posts = fetch_ruliweb_epic7_board()
    
    print("\n2. 스토브 버그 게시판 테스트:")
    stove_bug_posts = fetch_stove_bug_board()
    
    print("\n3. 스토브 자유게시판 테스트:")
    stove_general_posts = fetch_stove_general_board()
    
    print(f"\n=== 테스트 결과 ===")
    print(f"루리웹: {len(ruliweb_posts)}개")
    print(f"스토브 버그: {len(stove_bug_posts)}개")
    print(f"스토브 자유: {len(stove_general_posts)}개")
    print(f"총 합계: {len(ruliweb_posts) + len(stove_bug_posts) + len(stove_general_posts)}개")
    
    return ruliweb_posts + stove_bug_posts + stove_general_posts

if __name__ == "__main__":
    test_korean_crawling()