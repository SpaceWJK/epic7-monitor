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
    """스토브 에픽세븐 버그 게시판 크롤링 (실제 유저 게시글 영역 타겟)"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    print(f"[DEBUG] 현재 저장된 링크 수: {len(crawled_links)}")
    
    driver = None
    try:
        print("[DEBUG] Chrome 드라이버 초기화 중...")
        driver = get_chrome_driver()
        
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        print(f"[DEBUG] 스토브 접속 중: {url}")
        
        driver.get(url)
        
        # 충분한 로딩 대기
        print("[DEBUG] 페이지 로딩 대기 중...")
        time.sleep(8)
        
        # 스크롤하여 실제 유저 게시글 영역까지 로딩
        print("[DEBUG] 유저 게시글 영역까지 스크롤...")
        driver.execute_script("window.scrollTo(0, 500);")  # 공지 영역 넘어서
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 800);")  # 유저 게시글 영역
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 1200);") # 더 많은 게시글 로드
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")    # 맨 위로 돌아가기
        time.sleep(2)
        
        # 디버깅용 HTML 저장
        html_content = driver.page_source
        with open("stove_debug_selenium.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print("[DEBUG] 실제 유저 게시글 영역 탐색 중...")
        
        # JavaScript로 공지 영역과 유저 게시글 영역 구분
        user_posts = driver.execute_script("""
            var userPosts = [];
            
            // 모든 게시글 링크 찾기
            var allLinks = document.querySelectorAll('a[href*="/epicseven/kr/view/"]');
            console.log('전체 링크 수:', allLinks.length);
            
            // 공지 영역의 특징: OFFICIAL, GM, 이벤트 태그 등
            var officialKeywords = ['OFFICIAL', 'GM', '이벤트', 'EVENT', '공지', 'NOTICE', 'ADMIN'];
            
            // 알려진 공지 게시글 ID들
            var officialIds = ['10518001', '10855687', '10855562', '10855132'];
            
            for (var i = 0; i < allLinks.length; i++) {
                var link = allLinks[i];
                var href = link.href;
                var linkText = link.innerText.trim();
                
                // 게시글 ID 추출
                var idMatch = href.match(/\/view\/(\d+)/);
                if (!idMatch) continue;
                var postId = idMatch[1];
                
                // 공지 게시글 ID 제외
                if (officialIds.includes(postId)) {
                    console.log('공지 ID 제외:', postId);
                    continue;
                }
                
                // 부모 요소들 검사하여 공지 영역인지 판단
                var isInOfficialArea = false;
                var current = link;
                
                // 최대 5레벨까지 부모 요소 검사
                for (var level = 0; level < 5; level++) {
                    if (!current || !current.parentElement) break;
                    current = current.parentElement;
                    
                    var classList = current.classList ? Array.from(current.classList).join(' ') : '';
                    var elementText = current.innerText || '';
                    
                    // 클래스명에서 공지 영역 탐지
                    if (classList.includes('notice') || 
                        classList.includes('official') || 
                        classList.includes('event') ||
                        classList.includes('admin') ||
                        classList.includes('top')) {
                        isInOfficialArea = true;
                        break;
                    }
                    
                    // 텍스트에서 공지 키워드 탐지
                    for (var j = 0; j < officialKeywords.length; j++) {
                        if (elementText.includes(officialKeywords[j])) {
                            isInOfficialArea = true;
                            break;
                        }
                    }
                    
                    if (isInOfficialArea) break;
                }
                
                if (isInOfficialArea) {
                    console.log('공지 영역 제외:', linkText.substring(0, 30));
                    continue;
                }
                
                // 링크 텍스트 자체에서 공지 키워드 확인
                var hasOfficialKeyword = false;
                for (var k = 0; k < officialKeywords.length; k++) {
                    if (linkText.includes(officialKeywords[k])) {
                        hasOfficialKeyword = true;
                        break;
                    }
                }
                
                if (hasOfficialKeyword) {
                    console.log('공지 키워드 제외:', linkText.substring(0, 30));
                    continue;
                }
                
                // 실제 제목 추출 (더 정교하게)
                var title = '';
                
                // 방법 1: 링크 자체 텍스트
                if (linkText && linkText.length > 3 && !linkText.match(/^\d+$/)) {
                    title = linkText;
                }
                
                // 방법 2: 부모 요소에서 제목 찾기
                if (!title) {
                    var titleCurrent = link;
                    for (var level = 0; level < 4; level++) {
                        titleCurrent = titleCurrent.parentElement;
                        if (!titleCurrent) break;
                        
                        var allText = titleCurrent.innerText || '';
                        var lines = allText.split('\\n');
                        
                        for (var m = 0; m < lines.length; m++) {
                            var line = lines[m].trim();
                            if (line.length > 5 && 
                                line.length < 200 &&
                                !line.match(/^\d+$/) && 
                                !line.includes('조회') && 
                                !line.includes('추천') && 
                                !line.includes('댓글') &&
                                !line.includes('등록일') &&
                                !line.includes('작성자') &&
                                !line.match(/^\d{4}[./]\d{2}[./]\d{2}/) &&
                                !officialKeywords.some(keyword => line.includes(keyword))) {
                                title = line;
                                break;
                            }
                        }
                        if (title) break;
                    }
                }
                
                // 방법 3: 인근 요소에서 제목 찾기
                if (!title) {
                    var siblings = link.parentElement ? link.parentElement.children : [];
                    for (var n = 0; n < siblings.length; n++) {
                        var sibling = siblings[n];
                        var siblingText = sibling.innerText ? sibling.innerText.trim() : '';
                        
                        if (siblingText && 
                            siblingText.length > 5 && 
                            siblingText.length < 200 &&
                            !siblingText.match(/^\d+$/) &&
                            !siblingText.includes('조회') &&
                            !siblingText.includes('등록일') &&
                            !officialKeywords.some(keyword => siblingText.includes(keyword))) {
                            title = siblingText;
                            break;
                        }
                    }
                }
                
                if (title && title.length > 3) {
                    userPosts.push({
                        title: title.substring(0, 200).trim(),
                        href: href,
                        id: postId
                    });
                    console.log('유저 게시글 추가:', title.substring(0, 30));
                }
            }
            
            console.log('최종 발견된 유저 게시글 수:', userPosts.length);
            return userPosts.slice(0, 15); // 최신 15개만
        """)
        
        print(f"[DEBUG] JavaScript로 {len(user_posts)}개 유저 게시글 발견")
        
        if not user_posts:
            print("[WARNING] 유저 게시글을 찾을 수 없습니다.")
            print("[DEBUG] HTML 구조 확인을 위해 stove_debug_selenium.html 파일을 확인하세요")
            
            # 대안: 기본 방법으로 모든 링크 수집 (공지 필터링 없이)
            print("[DEBUG] 대안 방법으로 모든 게시글 수집...")
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/epicseven/kr/view/']")
            
            for i, element in enumerate(all_links[:20]):  # 상위 20개 확인
                try:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    if href and text:
                        print(f"[DEBUG] 대안 {i+1}: {text[:40]}... = {href[-20:]}")
                except:
                    continue
            
            return posts
        
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
                
                print(f"[DEBUG] 유저 게시글 {i}: URL = {href[-50:]}")
                print(f"[DEBUG] 유저 게시글 {i}: 제목 = {title[:50]}...")
                
                # 이미 처리된 링크인지 확인
                if href in crawled_links:
                    print(f"[DEBUG] 유저 게시글 {i}: 이미 크롤링된 링크")
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
                    print(f"[NEW] 새 유저 게시글 발견 ({i}): {title[:50]}...")
                else:
                    print(f"[DEBUG] 유저 게시글 {i}: 조건 미충족 - title_len={len(title) if title else 0}")
                
            except Exception as e:
                print(f"[ERROR] 유저 게시글 {i} 처리 중 오류: {e}")
                continue
        
        print(f"[DEBUG] 처리 결과: 전체 {len(user_posts)}개 중 새 유저 게시글 {len(posts)}개 발견")
        
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
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 유저 게시글 발견")
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
