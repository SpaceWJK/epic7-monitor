import requests
from bs4 import BeautifulSoup
from typing import List, Dict

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def crawl_stove(base_url: str) -> List[Dict[str, str]]:
    """STOVE 커뮤니티의 게시글 목록을 크롤링합니다."""
    posts = []
    try:
        response = requests.get(base_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        post_list = soup.select('ul.list-area > li:not(.notice)')
        for post in post_list:
            title_element = post.select_one('a.list-title-link')
            if title_element:
                title = title_element.text.strip()
                url = "https://page.onstove.com" + title_element['href']
                posts.append({'title': title, 'url': url})
    except requests.exceptions.RequestException as e:
        print(f"[크롤링 에러] STOVE 접속 실패: {e}")
    return posts

def crawl_dcinside(base_url: str) -> List[Dict[str, str]]:
    """디시인사이드 갤러리의 게시글 목록을 크롤링합니다."""
    posts = []
    try:
        response = requests.get(base_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        post_list = soup.select('tr.us-post')
        for post in post_list:
            title_element = post.select_one('td.gall_tit a:not(.icon_notice)')
            if title_element:
                title = title_element.text.strip()
                url = "https://gall.dcinside.com" + title_element['href']
                posts.append({'title': title, 'url': url})
    except requests.exceptions.RequestException as e:
        print(f"[크롤링 에러] DCinside 접속 실패: {e}")
    return posts

def crawl_reddit(subreddit_url: str) -> List[Dict[str, str]]:
    """Reddit 서브레딧의 'new' 게시글 목록을 크롤링합니다."""
    posts = []
    try:
        old_reddit_url = subreddit_url.replace("www.reddit.com", "old.reddit.com")
        response = requests.get(old_reddit_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        post_list = soup.select('div.thing')
        for post in post_list:
            title_element = post.select_one('p.title a.title')
            if title_element:
                title = title_element.text.strip()
                url = title_element['href']
                if not url.startswith('http'):
                    url = "https://old.reddit.com" + url
                posts.append({'title': title, 'url': url})
    except requests.exceptions.RequestException as e:
        print(f"[크롤링 에러] Reddit 접속 실패: {e}")
    return posts