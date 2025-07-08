from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def fetch_stove_bug_board():
    posts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36")
        
        page.goto("https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST")
        page.wait_for_selector(".s-detail-header-title", timeout=10000)

        html = page.content()
        with open("stove_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".s-detail-header-title"):
            title = item.get_text(strip=True)
            link_tag = item.find_parent("a")
            url = "https://page.onstove.com" + link_tag["href"] if link_tag else ""
            posts.append({"title": title, "url": url})
        
        browser.close()
    print(f"[DEBUG] 스토브 버그 게시판 fetched {len(posts)} elements.")
    return posts

def crawl_arca_sites():
    posts = []
    posts += fetch_stove_bug_board()
    print(f"[DEBUG] 전체 크롤링 결과: {posts}")
    return posts

def crawl_global_sites():
    # Global 사이트를 크롤링하는 로직 (필요 시 추가)
    return []
