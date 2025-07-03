# crawler.py
import requests
from bs4 import BeautifulSoup
import random
import time
from random import uniform

session = requests.Session()

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)'
]
REFERERS = ['https://google.com', 'https://bing.com', 'https://duckduckgo.com']
LANGUAGES = ['ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7', 'en-US,en;q=0.9']

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Referer': random.choice(REFERERS),
        'Accept-Language': random.choice(LANGUAGES),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

def fetch_posts(url, selector, source, force_bug=False):
    time.sleep(uniform(0.5, 1.5))
    try:
        resp = session.get(url, headers=get_headers(), timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        elements = soup.select(selector)
        posts = []
        for el in elements:
            title = el.get_text(strip=True)
            link = el.get('href')
            if link and not link.startswith("http"):
                link = url + link
            post_data = {'title': title, 'url': link, 'source': source}
            if force_bug:
                post_data['force_bug'] = True
            posts.append(post_data)
        return posts
    except Exception as e:
        print(f"[!] {source} 오류: {e}")
        return []

def crawl_arca_sites():
    posts = []
    posts += fetch_posts("https://arca.live/b/epic7", "a.title", "아카라이브")
    posts += fetch_posts("https://bbs.ruliweb.com/game/84925", "a.deco", "루리웹")
    posts += fetch_posts("https://page.onstove.com/epicseven/kr", "a.article-link", "스토브")
    posts += fetch_posts(
        "https://page.onstove.com/epicseven/kr/list/1012",
        "a.article-link",
        "스토브 버그 게시판",
        force_bug=True
    )
    return posts

def crawl_global_sites():
    posts = []
    posts += fetch_posts("https://forum.epic7.global/", "a.node-title", "글로벌 포럼")
    posts += fetch_posts("https://forum.gamer.com.tw/A.php?bsn=35366", "a.b-list__main__title", "바하무트")
    posts += crawl_reddit()
    return posts

def crawl_reddit():
    time.sleep(uniform(0.5, 1.5))
    try:
        headers = get_headers()
        headers['User-Agent'] = 'Mozilla/5.0 RedditMonitor'
        resp = session.get("https://www.reddit.com/r/EpicSeven/.json", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        posts = []
        for p in data["data"]["children"]:
            posts.append({
                "title": p["data"]["title"],
                "url": "https://reddit.com" + p["data"]["permalink"],
                "source": "Reddit"
            })
        return posts
    except Exception as e:
        print(f"[!] reddit 오류: {e}")
        return []
