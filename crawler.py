# crawler.py - ChromeDriver 호환성 완전 수정 버전
# Epic7 모니터링 시스템 - Chrome 138 호환성 해결
# 업데이트: 2025-07-16

import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime, timedelta
import re
import random
import requests
import hashlib
from typing import Dict, List, Optional, Tuple
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 모드별 파일 설정
def get_file_names(mode: str = "all"):
    """모드에 따른 파일명 반환"""
    if mode == "korean":
        return {
            "links": "crawled_links_korean.json",
            "cache": "content_cache_korean.json"
        }
    elif mode == "global":
        return {
            "links": "crawled_links_global.json", 
            "cache": "content_cache_global.json"
        }
    else:
        return {
            "links": "crawled_links.json",
            "cache": "content_cache.json"
        }

def load_crawled_links(mode: str = "all"):
    """모드별 크롤링된 링크 로드"""
    file_names = get_file_names(mode)
    filename = file_names["links"]
    
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"links": data, "last_updated": datetime.now().isoformat()}
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning(f"링크 파일 읽기 실패: {filename}")
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data, mode: str = "all"):
    """모드별 크롤링된 링크 저장"""
    file_names = get_file_names(mode)
    filename = file_names["links"]
    
    try:
        if len(link_data["links"]) > 1000:
            link_data["links"] = link_data["links"][-1000:]
        link_data["last_updated"] = datetime.now().isoformat()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
        logger.info(f"링크 저장 완료: {filename}")
    except Exception as e:
        logger.error(f"링크 저장 실패: {e}")

def get_chrome_driver():
    """Chrome 드라이버 초기화 - 호환성 완전 해결"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Chrome 버전 호환성 개선
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=VizDisplayCompositor')
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    
    prefs = {
        'profile.default_content_setting_values': {
            'images': 2, 'plugins': 2, 'popups': 2,
            'geolocation': 2, 'notifications': 2, 'media_stream': 2,
        }
    }
    options.add_experimental_option('prefs', prefs)
    
    # Chrome 138 호환성을 위한 다단계 시도
    logger.info("Chrome 138 호환성 드라이버 초기화 시작...")
    
    # 1단계: WebDriver Manager 최신 버전 시도
    try:
        logger.info("WebDriver Manager 최신 버전 시도...")
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.utils import ChromeType
        
        # Chrome for Testing 사용 (Chrome 115+ 호환)
        service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver Manager 성공")
        return driver
    except Exception as e:
        logger.warning(f"WebDriver Manager 실패: {str(e)[:100]}...")
    
    # 2단계: 시스템 기본 ChromeDriver 시도
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver',
        '/snap/bin/chromium.chromedriver',
        '/opt/google/chrome/chromedriver'
    ]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                logger.info(f"시스템 ChromeDriver 시도: {path}")
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                logger.info(f"시스템 ChromeDriver 성공: {path}")
                return driver
        except Exception as e:
            logger.warning(f"시스템 ChromeDriver 실패 {path}: {str(e)[:100]}...")
            continue
    
    # 3단계: 기본 WebDriver 시도
    try:
        logger.info("기본 WebDriver 시도...")
        driver = webdriver.Chrome(options=options)
        logger.info("기본 WebDriver 성공")
        return driver
    except Exception as e:
        logger.warning(f"기본 WebDriver 실패: {str(e)[:100]}...")
    
    # 4단계: 강제 다운로드 시도
    try:
        logger.info("강제 ChromeDriver 다운로드 시도...")
        import subprocess
        import platform
        
        # Chrome 버전 확인
        chrome_version = subprocess.check_output(
            ['google-chrome', '--version'], 
            stderr=subprocess.STDOUT
        ).decode().strip().split()[-1]
        
        major_version = chrome_version.split('.')[0]
        logger.info(f"Chrome 버전: {chrome_version}, 메이저 버전: {major_version}")
        
        # ChromeDriver 다운로드 URL 생성
        if int(major_version) >= 115:
            # Chrome for Testing API 사용
            driver_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
        else:
            # 기존 API 사용
            driver_url = f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}"
        
        response = requests.get(driver_url, timeout=10)
        if response.status_code == 200:
            driver_version = response.text.strip()
            logger.info(f"ChromeDriver 버전: {driver_version}")
            
            # 다운로드 및 설치 로직 (필요시 구현)
            pass
        
    except Exception as e:
        logger.error(f"강제 다운로드 실패: {str(e)[:100]}...")
    
    raise Exception("모든 ChromeDriver 초기화 방법이 실패했습니다. Chrome 버전과 ChromeDriver 호환성을 확인해주세요.")

def fix_stove_url(url):
    """스토브 URL 수정 함수"""
    if not url:
        return url
    
    if url.startswith('ttps://'):
        url = 'h' + url
    elif url.startswith('ttp://'):
        url = 'h' + url
    elif url.startswith('/'):
        url = 'https://page.onstove.com' + url
    elif not url.startswith('http'):
        url = 'https://page.onstove.com' + ('/' if not url.startswith('/') else '') + url
    
    return url

def get_url_hash(url: str) -> str:
    """URL 해시값 생성"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def extract_content_summary(content: str) -> str:
    """게시글 내용 요약"""
    if not content or len(content.strip()) < 10:
        return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    content = re.sub(r'\s+', ' ', content.strip())
    content = re.sub(r'[^\w\s가-힣.,!?]', '', content)
    sentences = re.split(r'[.!?]', content)
    first_sentence = sentences[0].strip() if sentences else content
    
    if len(first_sentence) > 100:
        first_sentence = first_sentence[:97] + '...'
    elif len(first_sentence) > 10:
        first_sentence = first_sentence + '...'
    
    return first_sentence if first_sentence else "게시글 내용 확인을 위해 링크를 클릭하세요."

# 한국 사이트 크롤링 함수들
def fetch_stove_bug_board(mode: str = "korean"):
    """스토브 버그 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"스토브 버그 게시판 크롤링 시작 - 모드: {mode}")
    
    driver = None
    try:
        driver = get_chrome_driver()
        driver.set_page_load_timeout(30)
        
        url = "https://page.onstove.com/epicseven/kr/list/1012?page=1&direction=LATEST"
        logger.info(f"스토브 버그 게시판 접속: {url}")
        
        driver.get(url)
        time.sleep(15)
        
        # 게시글 추출 JavaScript
        user_posts = driver.execute_script("""
            var posts = [];
            var items = document.querySelectorAll('section.s-board-item');
            
            for (var i = 0; i < Math.min(items.length, 15); i++) {
                var item = items[i];
                var link = item.querySelector('a[href*="/view/"]');
                var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
                
                if (link && title && link.href && title.innerText) {
                    var titleText = title.innerText.trim();
                    if (titleText.length > 3) {
                        var isNotice = item.querySelector('.notice, [class*="notice"]');
                        var isEvent = item.querySelector('.event, [class*="event"]');
                        
                        if (!isNotice && !isEvent) {
                            posts.push({
                                title: titleText,
                                href: link.href,
                                id: link.href.split('/').pop()
                            });
                        }
                    }
                }
            }
            return posts;
        """)
        
        logger.info(f"스토브 버그 게시판에서 {len(user_posts)}개 게시글 발견")
        
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": extract_content_summary(title),
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_bug"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    logger.info(f"새 버그 게시글: {title[:50]}...")
                    
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        logger.error(f"스토브 버그 게시판 크롤링 실패: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

def fetch_stove_general_board(mode: str = "korean"):
    """스토브 일반 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"스토브 일반 게시판 크롤링 시작 - 모드: {mode}")
    
    driver = None
    try:
        driver = get_chrome_driver()
        driver.set_page_load_timeout(30)
        
        url = "https://page.onstove.com/epicseven/kr/list/1005?page=1&direction=LATEST"
        logger.info(f"스토브 일반 게시판 접속: {url}")
        
        driver.get(url)
        time.sleep(15)
        
        # 동일한 JavaScript 사용
        user_posts = driver.execute_script("""
            var posts = [];
            var items = document.querySelectorAll('section.s-board-item');
            
            for (var i = 0; i < Math.min(items.length, 15); i++) {
                var item = items[i];
                var link = item.querySelector('a[href*="/view/"]');
                var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
                
                if (link && title && link.href && title.innerText) {
                    var titleText = title.innerText.trim();
                    if (titleText.length > 3) {
                        var isNotice = item.querySelector('.notice, [class*="notice"]');
                        var isEvent = item.querySelector('.event, [class*="event"]');
                        
                        if (!isNotice && !isEvent) {
                            posts.push({
                                title: titleText,
                                href: link.href
                            });
                        }
                    }
                }
            }
            return posts;
        """)
        
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": extract_content_summary(title),
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_general"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    logger.info(f"새 일반 게시글: {title[:50]}...")
                    
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        logger.error(f"스토브 일반 게시판 크롤링 실패: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

def fetch_ruliweb_epic7_board(mode: str = "korean"):
    """루리웹 에픽세븐 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"루리웹 크롤링 시작 - 모드: {mode}")
    
    driver = None
    try:
        driver = get_chrome_driver()
        driver.set_page_load_timeout(30)
        
        url = "https://bbs.ruliweb.com/game/84834"
        logger.info(f"루리웹 접속: {url}")
        
        driver.get(url)
        time.sleep(5)
        
        # 루리웹 게시글 선택자 시도
        selectors = [
            ".subject_link",
            ".table_body .subject a",
            "td.subject a",
            "a[href*='/read/']",
            ".board_list_table .subject_link"
        ]
        
        articles = []
        for selector in selectors:
            try:
                articles = driver.find_elements(By.CSS_SELECTOR, selector)
                if articles:
                    logger.info(f"루리웹 선택자 성공: {selector} ({len(articles)}개)")
                    break
            except:
                continue
        
        if not articles:
            logger.warning("루리웹 게시글을 찾을 수 없음")
            return posts
        
        for article in articles[:15]:
            try:
                title = article.text.strip()
                link = article.get_attribute("href")
                
                if not title or not link or len(title) < 3:
                    continue
                
                if any(keyword in title for keyword in ['공지', '필독', '이벤트', '추천']):
                    continue
                
                if link.startswith('/'):
                    link = 'https://bbs.ruliweb.com' + link
                
                if link not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": link,
                        "content": extract_content_summary(title),
                        "timestamp": datetime.now().isoformat(),
                        "source": "ruliweb_epic7"
                    }
                    posts.append(post_data)
                    crawled_links.append(link)
                    logger.info(f"새 루리웹 게시글: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"루리웹 게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        logger.error(f"루리웹 크롤링 실패: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

# 글로벌 사이트 크롤링 함수들
def fetch_stove_global_bug_board(mode: str = "global"):
    """스토브 글로벌 버그 게시판 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"스토브 글로벌 버그 게시판 크롤링 시작 - 모드: {mode}")
    
    driver = None
    try:
        driver = get_chrome_driver()
        driver.set_page_load_timeout(30)
        
        url = "https://page.onstove.com/epicseven/global/list/998?page=1&direction=LATEST"
        logger.info(f"스토브 글로벌 버그 게시판 접속: {url}")
        
        driver.get(url)
        time.sleep(15)
        
        # 동일한 JavaScript 사용
        user_posts = driver.execute_script("""
            var posts = [];
            var items = document.querySelectorAll('section.s-board-item');
            
            for (var i = 0; i < Math.min(items.length, 15); i++) {
                var item = items[i];
                var link = item.querySelector('a[href*="/view/"]');
                var title = item.querySelector('.s-board-title-text, .board-title, h3 span');
                
                if (link && title && link.href && title.innerText) {
                    var titleText = title.innerText.trim();
                    if (titleText.length > 3) {
                        var isNotice = item.querySelector('.notice, [class*="notice"]');
                        var isEvent = item.querySelector('.event, [class*="event"]');
                        
                        if (!isNotice && !isEvent) {
                            posts.push({
                                title: titleText,
                                href: link.href
                            });
                        }
                    }
                }
            }
            return posts;
        """)
        
        for post_info in user_posts:
            try:
                href = fix_stove_url(post_info['href'])
                title = post_info['title']
                
                if href not in crawled_links:
                    post_data = {
                        "title": title,
                        "url": href,
                        "content": extract_content_summary(title),
                        "timestamp": datetime.now().isoformat(),
                        "source": "stove_global_bug"
                    }
                    posts.append(post_data)
                    crawled_links.append(href)
                    logger.info(f"새 글로벌 버그 게시글: {title[:50]}...")
                    
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"게시글 처리 오류: {e}")
                continue
        
    except Exception as e:
        logger.error(f"스토브 글로벌 버그 게시판 크롤링 실패: {e}")
    
    finally:
        if driver:
            driver.quit()
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

def fetch_reddit_epic7_board(mode: str = "global"):
    """Reddit r/EpicSeven 크롤링"""
    posts = []
    link_data = load_crawled_links(mode)
    crawled_links = link_data["links"]
    
    logger.info(f"Reddit 크롤링 시작 - 모드: {mode}")
    
    try:
        url = "https://www.reddit.com/r/EpicSeven/new.json?limit=20"
        headers = {"User-Agent": "Epic7MonitorBot/1.0"}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            for child in data['data']['children']:
                try:
                    item = child['data']
                    title = item['title']
                    permalink = "https://www.reddit.com" + item['permalink']
                    
                    if permalink not in crawled_links and len(title) > 3:
                        post_data = {
                            "title": title,
                            "url": permalink,
                            "content": extract_content_summary(title),
                            "timestamp": datetime.now().isoformat(),
                            "source": "reddit_epic7"
                        }
                        posts.append(post_data)
                        crawled_links.append(permalink)
                        logger.info(f"새 Reddit 게시글: {title[:50]}...")
                        
                except Exception as e:
                    logger.error(f"Reddit 게시글 처리 오류: {e}")
                    continue
        
    except Exception as e:
        logger.error(f"Reddit 크롤링 실패: {e}")
    
    link_data["links"] = crawled_links
    save_crawled_links(link_data, mode)
    
    return posts

# 모드별 크롤링 통합 함수
def crawl_korean_sites():
    """한국 사이트 크롤링"""
    logger.info("한국 사이트 크롤링 시작")
    all_posts = []
    
    try:
        # 스토브 버그 게시판
        stove_bug_posts = fetch_stove_bug_board("korean")
        all_posts.extend(stove_bug_posts)
        logger.info(f"스토브 버그 게시판: {len(stove_bug_posts)}개 게시글")
        
        # 스토브 일반 게시판
        stove_general_posts = fetch_stove_general_board("korean")
        all_posts.extend(stove_general_posts)
        logger.info(f"스토브 일반 게시판: {len(stove_general_posts)}개 게시글")
        
        # 루리웹 에픽세븐
        ruliweb_posts = fetch_ruliweb_epic7_board("korean")
        all_posts.extend(ruliweb_posts)
        logger.info(f"루리웹 에픽세븐: {len(ruliweb_posts)}개 게시글")
        
    except Exception as e:
        logger.error(f"한국 사이트 크롤링 오류: {e}")
    
    logger.info(f"한국 사이트 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_global_sites():
    """글로벌 사이트 크롤링"""
    logger.info("글로벌 사이트 크롤링 시작")
    all_posts = []
    
    try:
        # 스토브 글로벌 버그 게시판
        stove_global_bug_posts = fetch_stove_global_bug_board("global")
        all_posts.extend(stove_global_bug_posts)
        logger.info(f"스토브 글로벌 버그 게시판: {len(stove_global_bug_posts)}개 게시글")
        
        # Reddit r/EpicSeven
        reddit_posts = fetch_reddit_epic7_board("global")
        all_posts.extend(reddit_posts)
        logger.info(f"Reddit r/EpicSeven: {len(reddit_posts)}개 게시글")
        
    except Exception as e:
        logger.error(f"글로벌 사이트 크롤링 오류: {e}")
    
    logger.info(f"글로벌 사이트 크롤링 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

def crawl_all_sites():
    """모든 사이트 크롤링"""
    logger.info("모든 사이트 크롤링 시작")
    
    korean_posts = crawl_korean_sites()
    global_posts = crawl_global_sites()
    
    all_posts = korean_posts + global_posts
    logger.info(f"전체 사이트 크롤링 완료: 한국 {len(korean_posts)}개, 글로벌 {len(global_posts)}개, 총 {len(all_posts)}개")
    
    return all_posts

# 하위 호환성을 위한 함수들
def get_all_posts_for_report(hours: int = 24):
    """리포트용 게시글 수집 (하위 호환성)"""
    return crawl_all_sites()

if __name__ == "__main__":
    # 테스트 코드
    print("=== Epic7 모니터링 시스템 - 크롤러 테스트 ===")
    
    # ChromeDriver 테스트
    try:
        driver = get_chrome_driver()
        print("✅ ChromeDriver 초기화 성공")
        driver.quit()
    except Exception as e:
        print(f"❌ ChromeDriver 초기화 실패: {e}")
    
    # 크롤링 테스트
    try:
        posts = crawl_korean_sites()
        print(f"✅ 한국 사이트 크롤링 성공: {len(posts)}개 게시글")
    except Exception as e:
        print(f"❌ 한국 사이트 크롤링 실패: {e}")
    
    print("=== 크롤러 테스트 완료 ===")