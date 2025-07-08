import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_posts(url, selector, title_selector, link_selector, source, force_bug=False):
    print(f"[DEBUG] Fetching from {source} ({url})")
    try:
        html = requests.get(url, headers=HEADERS, timeout=5).text
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"[ERROR] Failed to fetch {source}: {e}")
        return []
    posts = []
    elements = soup.select(selector)
    print(f"[DEBUG] {len(elements)} elements found in {source}")
    for el in elements:
        try:
            title_tag = el.select_one(title_selector)
            link_tag = el.select_one(link_selector)
            if not title_tag or not link_tag:
                continue
            post_data = {
                "title": title_tag.get_text(strip=True),
                "url": link_tag.get("href"),
                "source": source
            }
            if force_bug:
                post_data["force_bug"] = True
            posts.append(post_data)
        except Exception as ex:
            print(f"[WARN] Skipping element due to error: {ex}")
    print(f"[DEBUG] {len(posts)} posts prepared from {source}")
    return posts

def crawl_all_sites():
    all_posts = []
    all_posts += fetch_posts(
        "https://arca.live/b/epic7", 
        "div.title-area", 
        "span.title", 
        "a", 
        "아카라이브"
    )
    all_posts += fetch_posts(
        "https://bbs.ruliweb.com/family/493/board/179940", 
        "td.subject", 
        "a.deco", 
        "a.deco", 
        "루리웹"
    )
    all_posts += fetch_posts(
        "https://page.onstove.com/epicseven/kr/list/1012", 
        "div.s-detail-header", 
        "p.s-detail-header-title", 
        "a.s-detail-header-link", 
        "스토브 버그 게시판", 
        force_bug=True
    )
    # 글로벌 Reddit, Forum도 동일 로직으로 확장 가능
    return all_posts
