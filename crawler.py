import requests
from bs4 import BeautifulSoup

def fetch_posts(url, container_selector, title_selector, link_selector, source, force_bug=False):
    posts = []
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch {source}: HTTP {response.status_code}")
            return posts
        soup = BeautifulSoup(response.text, "html.parser")
        containers = soup.select(container_selector)
        print(f"[DEBUG] Fetched {len(containers)} elements from {source}")
        for container in containers:
            title_elem = container.select_one(title_selector)
            link_elem = container.select_one(link_selector)
            if title_elem and link_elem:
                title = title_elem.text.strip()
                link = link_elem['href']
                posts.append({
                    "title": title,
                    "url": link if link.startswith("http") else f"https://page.onstove.com{link}",
                    "source": source,
                    "force_bug": force_bug
                })
    except Exception as e:
        print(f"[ERROR] {source} failed: {e}")
    return posts

def crawl_arca_sites():
    posts = []
    posts += fetch_posts(
        "https://arca.live/b/epic7",
        "div.title",
        "span > a",
        "span > a",
        "아카라이브"
    )
    posts += fetch_posts(
        "https://bbs.ruliweb.com/game/85238",
        "div.board_main div.table_body",
        "td.subject a",
        "td.subject a",
        "루리웹"
    )
    posts += fetch_posts(
        "https://page.onstove.com/epicseven/kr/list/1012",
        "div.s-detail-header",
        "p.s-detail-header-title",
        "a.s-detail-header-link",
        "스토브 버그 게시판",
        force_bug=True
    )
    return posts

def crawl_global_sites():
    posts = []
    posts += fetch_posts(
        "https://www.reddit.com/r/EpicSeven/",
        "div.Post",
        "h3",
        "a[data-click-id='body']",
        "레딧"
    )
    posts += fetch_posts(
        "https://forum.global.epic7.com/",
        "div.board_main",
        "span > a",
        "span > a",
        "글로벌 포럼"
    )
    return posts

def crawl_all_sites():
    return crawl_arca_sites() + crawl_global_sites()
