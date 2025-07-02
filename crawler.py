# crawler.py
import requests
from bs4 import BeautifulSoup
import random
import time
from random import uniform

session = requests.Session()

# 헤더 변조를 위한 리스트
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_2 like Mac OS X)'
]
REFERERS = ['https://google.com', 'https://bing.com', 'https://duckduckgo.com']
LANGUAGES = ['ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7', 'en-US,en;q=0.9', 'ja-JP,ja;q=0.9']

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Referer': random.choice(REFERERS),
        'Accept-Language': random.choice(LANGUAGES),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

def fetch_posts(url, selector):
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
            posts.append({'title': title, 'url': link})
        return posts
    except Exception as e:
        print(f"[!] {url} 오류: {e}")
        return []

def crawl_all_sites():
    posts = []
    posts += fetch_posts("https://arca.live/b/epic7", "a.title")                     # 아카라이브
    posts += fetch_posts("https://bbs.ruliweb.com/game/84925", "a.deco")             # 루리웹
    posts += fetch_posts("https://page.onstove.com/epicseven/kr", "a.article-link")  # 스토브
    posts += fetch_posts("https://forum.epic7.global/", "a.node-title")              # 글로벌 포럼
    posts += fetch_posts("https://forum.gamer.com.tw/A.php?bsn=35366", "a.b-list__main__title") # 대만 바하무트
    posts += fetch_posts("https://x.com/Epic7_jp", "title")                          # 일본 X
    posts += fetch_posts("https://www.facebook.com/EpicSeven.tw", "title")           # 대만 페북
    posts += fetch_posts("https://www.facebook.com/EpicSeven.Thai", "title")         # 태국 페북
    posts += fetch_posts("https://www.taptap.cn/app/158697", "title")                # 중국 탭탭
    posts += crawl_reddit()
    return posts

def crawl_reddit():
    time.sleep(uniform(0.5,1.5))
    try:
        headers = get_headers()
        headers['User-Agent'] = 'Mozilla/5.0 RedditMonitor'
        resp = session.get("https://www.reddit.com/r/EpicSeven/.json", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        posts = [{"title": p["data"]["title"], "url": "https://reddit.com" + p["data"]["permalink"]}
                 for p in data["data"]["children"]]
        return posts
    except Exception as e:
        print(f"[!] reddit 오류: {e}")
        return []
