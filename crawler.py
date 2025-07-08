import json
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
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

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links()
    crawled_links = link_data["links"]
    
    with sync_playwright() as p:
        try:
            # 브라우저 설정 개선
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            # 스토브 버그 게시판 URL
            url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
            print(f"[DEBUG] 스토브 접속 중: {url}")
            
            # 페이지 로딩 및 대기
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 스토브 특성상 동적 로딩 대기
            time.sleep(5)
            
            # 스크롤하여 콘텐츠 로딩 유도
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)
            
            html = page.content()
            
            # 디버깅용 HTML 저장 (매번 덮어씀)
            with open("stove_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
                
            soup = BeautifulSoup(html, "html.parser")
            
            # 스토브 실제 구조에 맞는 셀렉터들
            post_selectors = [
                # 스토브 게시판의 실제 구조 기반
                ".board-list .list-row",
                ".post-list-wrap .post-item", 
                ".board-item-wrap .board-item",
                "a[href*='/epicseven/kr/view/']",
                ".title a",
                ".subject a",
                "[data-href*='/view/']"
            ]
            
            found_posts = []
            for selector in post_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"[DEBUG] '{selector}'로 {len(elements)}개 요소 발견")
                    found_posts = elements
                    break
            
            if not found_posts:
                print("[ERROR] 게시글을 찾을 수 없습니다.")
                print("[DEBUG] HTML 구조 확인을 위해 stove_debug.html 파일을 확인하세요")
                
                # 대안: 모든 링크에서 view 패턴 찾기
                all_links = soup.find_all('a', href=True)
                view_links = [link for link in all_links if '/epicseven/kr/view/' in link.get('href', '')]
                
                if view_links:
                    print(f"[DEBUG] 대안 방법으로 {len(view_links)}개 게시글 링크 발견")
                    found_posts = view_links
                else:
                    return posts
            
            # 게시글 정보 추출
            for i, element in enumerate(found_posts[:15]):  # 최신 15개 체크
                try:
                    # 링크 추출
                    href = ""
                    if element.name == 'a':
                        href = element.get('href', '')
                    else:
                        link_elem = element.find('a', href=True)
                        if link_elem:
                            href = link_elem.get('href', '')
                    
                    if not href:
                        continue
                        
                    if not href.startswith('http'):
                        href = "https://page.onstove.com" + href
                    
                    # 이미 처리된 링크인지 확인
                    if href in crawled_links:
                        continue
                    
                    # 제목 추출 (다양한 방법 시도)
                    title = ""
                    
                    # 방법 1: 링크 텍스트 직접
                    if element.name == 'a' and element.get_text(strip=True):
                        title = element.get_text(strip=True)
                    
                    # 방법 2: 제목 관련 클래스 찾기
                    if not title:
                        title_selectors = ['.title', '.subject', '.post-title', '.board-title']
                        for sel in title_selectors:
                            title_elem = element.select_one(sel)
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                                break
                    
                    # 방법 3: 부모 요소에서 제목 찾기
                    if not title:
                        parent = element if element.name != 'a' else element.find_parent()
                        if parent:
                            # 텍스트가 있는 첫 번째 요소 찾기
                            text_elements = parent.find_all(string=True)
                            for text in text_elements:
                                clean_text = text.strip()
                                if clean_text and len(clean_text) > 3 and not clean_text.isdigit():
                                    title = clean_text
                                    break
                    
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
            
            browser.close()
            
        except Exception as e:
            print(f"[ERROR] 스토브 크롤링 중 오류 발생: {e}")
            if 'browser' in locals():
                browser.close()
    
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
