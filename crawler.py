import json
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
from datetime import datetime

# 중복 방지를 위한 링크 저장 파일
CRAWLED_LINKS_FILE = "crawled_links.json"

def load_crawled_links():
    """이미 크롤링된 링크들을 로드"""
    if os.path.exists(CRAWLED_LINKS_FILE):
        with open(CRAWLED_LINKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_crawled_links(links):
    """크롤링된 링크들을 저장"""
    with open(CRAWLED_LINKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

def fetch_stove_bug_board():
    """스토브 에픽세븐 버그 게시판 크롤링"""
    posts = []
    crawled_links = load_crawled_links()
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 스토브 버그 게시판 URL
            url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
            print(f"[DEBUG] 접속 중: {url}")
            
            page.goto(url, wait_until="networkidle")
            
            # 페이지 로딩 대기 (여러 셀렉터 시도)
            selectors_to_try = [
                ".post-item",
                ".list-item", 
                ".board-item",
                "[data-post-id]",
                ".title a",
                ".post-title"
            ]
            
            content_loaded = False
            for selector in selectors_to_try:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    content_loaded = True
                    print(f"[DEBUG] 콘텐츠 로딩 성공: {selector}")
                    break
                except:
                    continue
            
            if not content_loaded:
                print("[WARNING] 게시판 콘텐츠 로딩 실패, 강제 진행")
                time.sleep(3)
            
            html = page.content()
            
            # 디버깅용 HTML 저장
            with open("stove_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
                
            soup = BeautifulSoup(html, "html.parser")
            
            # 다양한 셀렉터로 게시글 찾기
            post_selectors = [
                "a[href*='/epicseven/kr/view/']",  # 에픽세븐 게시글 링크
                ".post-item a",
                ".list-item a", 
                ".board-item a",
                ".title a"
            ]
            
            found_posts = []
            for selector in post_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"[DEBUG] '{selector}'로 {len(elements)}개 게시글 발견")
                    found_posts = elements
                    break
            
            if not found_posts:
                print("[ERROR] 게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
                return posts
            
            # 게시글 정보 추출
            for element in found_posts[:10]:  # 최신 10개만 체크
                try:
                    # 링크 추출
                    href = element.get('href', '')
                    if not href.startswith('http'):
                        href = "https://page.onstove.com" + href
                    
                    # 제목 추출 (여러 방법 시도)
                    title = ""
                    if element.get_text(strip=True):
                        title = element.get_text(strip=True)
                    elif element.find(class_="title"):
                        title = element.find(class_="title").get_text(strip=True)
                    elif element.find("span"):
                        title = element.find("span").get_text(strip=True)
                    
                    if not title:
                        # 부모 요소에서 제목 찾기
                        parent = element.find_parent()
                        if parent:
                            title_elem = parent.find(string=True)
                            if title_elem:
                                title = title_elem.strip()
                    
                    if title and href and href not in crawled_links:
                        post_data = {
                            "title": title,
                            "url": href,
                            "timestamp": datetime.now().isoformat(),
                            "source": "stove_bug"
                        }
                        posts.append(post_data)
                        crawled_links.append(href)
                        print(f"[NEW] 새 게시글 발견: {title}")
                
                except Exception as e:
                    print(f"[ERROR] 게시글 파싱 중 오류: {e}")
                    continue
            
            browser.close()
            
        except Exception as e:
            print(f"[ERROR] 크롤링 중 오류 발생: {e}")
            
    # 중복 방지 링크 저장
    save_crawled_links(crawled_links)
    
    print(f"[DEBUG] 스토브 버그 게시판에서 {len(posts)}개 새 게시글 발견")
    return posts

def fetch_stove_general_board():
    """스토브 에픽세븐 일반 게시판 크롤링"""
    # 일반 게시판도 동일한 로직으로 구현
    return []

def crawl_arca_sites():
    """국내 사이트들 크롤링"""
    all_posts = []
    
    # 스토브 버그 게시판
    stove_bug_posts = fetch_stove_bug_board()
    all_posts.extend(stove_bug_posts)
    
    # 스토브 일반 게시판
    stove_general_posts = fetch_stove_general_board()
    all_posts.extend(stove_general_posts)
    
    print(f"[DEBUG] 전체 크롤링 결과: {len(all_posts)}개")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트들 크롤링"""
    return []
