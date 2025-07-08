from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def fetch_stove_bug_board():
    posts = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://page.onstove.com/epicseven/kr/list/1012")
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        containers = soup.select("div.s-detail-header")
        print(f"[DEBUG] 스토브 버그 게시판 fetched {len(containers)} elements.")
        for container in containers:
            title_elem = container.select_one("a.s-detail-header-link")
            if title_elem:
                title = title_elem.text.strip()
                link = title_elem['href']
                posts.append({
                    "title": title,
                    "url": link if link.startswith("http") else f"https://page.onstove.com{link}",
                    "source": "스토브 버그 게시판",
                    "force_bug": True
                })
        browser.close()
    return posts

def crawl_arca_sites():
    posts = []
    posts += fetch_stove_bug_board()
    return posts

def crawl_global_sites():
    # 필요시 추가
    return []

def crawl_all_sites():
    return crawl_arca_sites() + crawl_global_sites()
