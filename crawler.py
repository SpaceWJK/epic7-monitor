# crawler.py
import requests
from bs4 import BeautifulSoup
import random
import time
from random import uniform

session = requests.Session()

# 헤더 변조 리스트
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

def fetch_posts(url, selector, source_name):
    """지정 URL에서 selector로 게시글 제목과 링크를 수집하고 source 이름을 같이 리턴"""
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
            posts.append({'title': title, 'url': link, 'source': source_name})
        return posts
    except Exception as e:
        print(f"[!] {url} 오류: {e}")
        return []

def crawl_reddit():
    """레딧 JSON API 사용 (Reddit 전용 처리)"""
    time.sleep(uniform(0.5,1.5))
    try:
        headers = get_headers()
        headers['User-Agent'] = 'Mozilla/5.0 RedditMonitor'
        resp = session.get("https://www.reddit.com/r/EpicSeven/.json", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        posts = [{"title": p["data"]["title"], 
                  "url": "https://reddit.com" + p["data"]["permalink"],
                  "source": "reddit"}
                 for p in data["data"]["children"]]
        return posts
    except Exception as e:
        print(f"[!] reddit 오류: {e}")
        return []

def crawl_all_sites():
    """전체 사이트 순회 크롤링"""
    posts = []
    posts += fetch_posts("https://arca.live/b/epic7", "a.title", "arca.live")
    posts += fetch_posts("https://bbs.ruliweb.com/game/84925", "a.deco", "ruliweb")
    posts += fetch_posts("https://page.onstove.com/epicseven/kr", "a.article-link", "stove")
    posts += fetch_posts("https://forum.epic7.global/", "a.node-title", "global-forum")
    posts += fetch_posts("https://forum.gamer.com.tw/A.php?bsn=35366", "a.b-list__main__title", "bahamut")
    posts += fetch_posts("https://x.com/Epic7_jp", "title", "x-jp")
    posts += fetch_posts("https://www.facebook.com/EpicSeven.tw", "title", "fb-tw")
    posts += fetch_posts("https://www.facebook.com/EpicSeven.Thai", "title", "fb-th")
    posts += fetch_posts("https://www.taptap.cn/app/158697", "title", "taptap-cn")
    posts += crawl_reddit()
    return posts
