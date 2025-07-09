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

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링 (수정된 버전 - 실제 유저 게시글 영역 타겟)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 현재 저장된 링크 수: {len(crawled_links)}")
    
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
        
        # 동적 콘텐츠 로딩 대기 (더 충분히)
        print("[DEBUG] 페이지 로딩 대기 중...")
        time.sleep(8)  # 더 길게 대기
        
        # 스크롤하여 콘텐츠 로딩 유도
        print("[DEBUG] 스크롤로 콘텐츠 로딩 유도 중...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        
        # 추가 스크롤로 더 많은 콘텐츠 로드
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        
        # 디버깅용 HTML 저장
        html_content = driver.page_source
        with open("stove_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 게시글 링크 탐색 중...")
        
        # 수정된 셀렉터들 - 실제 유저 게시글 영역 타겟
        selectors = [
            # 우선순위 1: 유저 게시글 영역의 링크들
            "div[class*='board'] a[href*='/epicseven/kr/view/']",
            "div[class*='list'] a[href*='/epicseven/kr/view/']",
            "div[class*='post'] a[href*='/epicseven/kr/view/']",
            "div[class*='item'] a[href*='/epicseven/kr/view/']",
            # 우선순위 2: 더 구체적인 게시글 영역
            ".post-list a[href*='/epicseven/kr/view/']",
            ".board-list a[href*='/epicseven/kr/view/']",
            ".community-list a[href*='/epicseven/kr/view/']",
            # 우선순위 3: 일반적인 링크 (공지 제외)
            "a[href*='/epicseven/kr/view/']"
        ]
        
        found_elements = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"[DEBUG] '{selector}'로 {len(elements)}개 요소 발견")
                    
                    # 공지 게시글 필터링 (제목이나 URL로 구분)
                    filtered_elements = []
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            if not href:
                                continue
                                
                            # 공지 게시글 ID 필터링 (알려진 공지 ID들)
                            exclude_ids = [
                                '10518001',  # PC 클라이언트 설치 가이드
                                '10855687',  # Epic Day 이벤트
                                '10855562',  # 데일리 루틴 이벤트
                                '10855132'   # NOTICE
                            ]
                            
                            # URL에서 게시글 ID 추출
                            import re
                            id_match = re.search(r'/view/(\d+)', href)
                            if id_match:
                                post_id = id_match.group(1)
                                if post_id not in exclude_ids:
                                    filtered_elements.append(element)
                                else:
                                    print(f"[DEBUG] 공지 게시글 제외: {post_id}")
                            else:
                                filtered_elements.append(element)
                                
                        except Exception as e:
                            print(f"[DEBUG] 요소 필터링 중 오류: {e}")
                            continue
                    
                    if filtered_elements:
                        found_elements = filtered_elements
                        print(f"[DEBUG] 필터링 후 {len(found_elements)}개 유저 게시글 발견")
                        break
                    
            except Exception as e:
                print(f"[DEBUG] '{selector}' 시도 중 오류: {e}")
                continue
        
        # 대안: JavaScript로 더 정확한 게시글 영역 탐색
        if not found_elements:
            print("[DEBUG] JavaScript로 게시글 영역 재탐색 중...")
            try:
                # JavaScript로 실제 게시글 영역 찾기
                js_links = driver.execute_script("""
                    var links = [];
                    var allLinks = document.querySelectorAll('a[href*="/epicseven/kr/view/"]');
                    
                    // 공지 제외 ID들
                    var excludeIds = ['10518001', '10855687', '10855562', '10855132'];
                    
                    for (var i = 0; i < allLinks.length; i++) {
                        var link = allLinks[i];
                        var href = link.href;
                        var match = href.match(/\/view\/(\d+)/);
                        
                        if (match) {
                            var postId = match[1];
                            // 공지가 아닌 게시글만 선택
                            if (excludeIds.indexOf(postId) === -1) {
                                // 부모 요소가 실제 게시글 영역인지 확인
                                var parent = link.closest('[class*="list"], [class*="board"], [class*="post"], [class*="item"]');
                                if (parent) {
                                    links.push({
                                        href: href,
                                        text: link.innerText.trim(),
                                        id: postId
                                    });
                                }
                            }
                        }
                    }
                    
                    return links.slice(0, 15); // 최신 15개만
                """)
                
                if js_links:
                    print(f"[DEBUG] JavaScript로 {len(js_links)}개 게시글 발견")
                    # JavaScript 결과를 found_elements 형태로 변환
                    found_elements = []
                    for link_info in js_links:
                        # 실제 element 찾기
                        try:
                            element = driver.find_element(By.XPATH, f"//a[@href='{link_info['href']}']")
                            found_elements.append(element)
                        except:
                            continue
                            
            except Exception as e:
                print(f"[DEBUG] JavaScript 탐색 실패: {e}")
        
        if not found_elements:
            print("[ERROR] 유저 게시글을 찾을 수 없습니다.")
            print("[DEBUG] HTML 구조 확인을 위해 stove_debug_selenium.html 파일을 확인하세요")
            return posts
        
        # 게시글 정보 추출
        for i, element in enumerate(found_elements[:15]):  # 최신 15개 체크
            try:
                href = element.get_attribute('href')
                if not href:
                    print(f"[DEBUG] 요소 {i+1}: href 없음")
                    continue
                
                # URL 수정 (h 빠진 문제 해결)
                if href.startswith('ttps://'):
                    href = 'h' + href
                elif not href.startswith('http'):
                    href = "https://page.onstove.com" + href
                
                print(f"[DEBUG] 요소 {i+1}: URL = {href[-50:]}")
                
                # 이미 처리된 링크인지 확인
                if href in crawled_links:
                    print(f"[DEBUG] 요소 {i+1}: 이미 크롤링된 링크")
                    continue
                
                # 제목 추출 (강화된 로직)
                title = ""
                
                # 방법 1: 링크 텍스트 직접
                link_text = element.text.strip()
                if link_text and len(link_text) > 3 and not link_text.isdigit():
                    title = link_text
                    print(f"[DEBUG] 요소 {i+1}: 제목 추출 성공 (직접텍스트) = {title[:30]}...")
                
                # 방법 2: 부모 요소에서 제목 찾기 (개선)
                if not title:
                    try:
                        current_element = element
                        for level in range(5):  # 최대 5레벨까지
                            parent = current_element.find_element(By.XPATH, "..")
                            parent_text = parent.text.strip()
                            
                            if parent_text:
                                lines = [line.strip() for line in parent_text.split('\n') if line.strip()]
                                for line in lines:
                                    if (len(line) > 5 and 
                                        not line.isdigit() and 
                                        '조회' not in line and 
                                        '등록일' not in line and
                                        '추천' not in line and
                                        '댓글' not in line and
                                        'OFFICIAL' not in line and
                                        'GM' not in line and
                                        not re.match(r'^\d{4}[./]\d{2}[./]\d{2}', line) and
                                        not re.match(r'^\d+$', line)):
                                        title = line
                                        print(f"[DEBUG] 요소 {i+1}: 제목 추출 성공 (부모{level+1}) = {title[:30]}...")
                                        break
                            
                            if title:
                                break
                            current_element = parent
                            
                    except Exception as e:
                        print(f"[DEBUG] 요소 {i+1}: 부모 요소 탐색 실패 = {e}")
                
                # 방법 3: JavaScript로 제목 추출
                if not title:
                    try:
                        js_title = driver.execute_script("""
                            var element = arguments[0];
                            var href = element.href;
                            
                            // 같은 href를 가진 모든 요소 찾기
                            var sameLinks = document.querySelectorAll('a[href="' + href + '"]');
                            
                            for (var i = 0; i < sameLinks.length; i++) {
                                var link = sameLinks[i];
                                var text = link.innerText.trim();
                                
                                // 유효한 제목인지 확인
                                if (text && text.length > 3 && !text.match(/^\d+$/) && 
                                    !text.includes('조회') && !text.includes('등록일') &&
                                    !text.includes('OFFICIAL') && !text.includes('GM')) {
                                    return text;
                                }
                            }
                            
                            return '';
                        """, element)
                        
                        if js_title and len(js_title.strip()) > 3:
                            title = js_title.strip()
                            print(f"[DEBUG] 요소 {i+1}: 제목 추출 성공 (JavaScript) = {title[:30]}...")
                        
                    except Exception as e:
                        print(f"[DEBUG] 요소 {i+1}: JavaScript 탐색 실패 = {e}")
                
                if not title:
                    print(f"[DEBUG] 요소 {i+1}: 모든 제목 추출 방법 실패")
                    continue
                
                # 제목 정리
                if title:
                    title = re.sub(r'\s+', ' ', title).strip()
                    title = title[:200]
                
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
                else:
                    print(f"[DEBUG] 요소 {i+1}: 조건 미충족 - title_len={len(title) if title else 0}")
                
            except Exception as e:
                print(f"[ERROR] 게시글 {i+1} 파싱 중 오류: {e}")
                continue
        
        print(f"[DEBUG] 처리 결과: 전체 {len(found_elements)}개 중 새 게시글 {len(posts)}개 발견")
        
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
