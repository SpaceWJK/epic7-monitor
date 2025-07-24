#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 다국가 크롤러 v4.3 - Master 정밀 수정본
Master 요구사항: 글로벌 타임아웃 최적화 + Skip & Continue + 3회 재시도

핵심 수정사항:
- 글로벌 사이트 타임아웃 30초로 증가 (나머지는 15초 유지)
- Skip & Continue 로직 구현 (개별 실패해도 계속 진행)
- 3회 재시도 후 포기 메커니즘
- 기존 코드 구조 완전 유지

Author: Epic7 Monitoring Team  
Version: 4.3 (Master 정밀 수정)
Date: 2025-07-24
"""

import time
import random
import re
import requests
import concurrent.futures
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

# Selenium 관련 import
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains

# 웹드라이버 매니저
from webdriver_manager.chrome import ChromeDriverManager

# BeautifulSoup import
from bs4 import BeautifulSoup

# =============================================================================
# Epic7 크롤러 설정
# =============================================================================

# 크롤링 대상 사이트 설정
CRAWL_TARGETS = {
    "stove_korea_bug": {
        "name": "한국 버그 게시판",  
        "url": "https://page.onstove.com/epicseven/kr/board/list/e7kr001?listType=2&direction=latest&display_opt=usertag%2Cbattlerank%2Cnickname%2Cwritedate%2Ccomment%2Cthumb&afterback=true",
        "enabled": True,
        "timeout": 15
    },
    "stove_global_bug": {
        "name": "글로벌 버그 게시판",
        "url": "https://page.onstove.com/epicseven/global/board/list/e7en001?listType=2&direction=latest&display_opt=usertag%2Cbattlerank%2Cnickname%2Cwritedate%2Ccomment%2Cthumb&afterback=true",
        "enabled": True,
        "timeout": 30  # Master 수정: 글로벌만 30초로 증가
    },
    "stove_korea_general": {
        "name": "한국 자유 게시판",
        "url": "https://page.onstove.com/epicseven/kr/board/list/e7kr002?listType=2&direction=latest&display_opt=usertag%2Cbattlerank%2Cnickname%2Cwritedate%2Ccomment%2Cthumb&afterback=true",
        "enabled": True,
        "timeout": 15
    },
    "stove_global_general": {
        "name": "글로벌 자유 게시판", 
        "url": "https://page.onstove.com/epicseven/global/board/list/e7en002?listType=2&direction=latest&display_opt=usertag%2Cbattlerank%2Cnickname%2Cwritedate%2Ccomment%2Cthumb&afterback=true",
        "enabled": True,
        "timeout": 30  # Master 수정: 글로벌만 30초로 증가
    },
    "ruliweb": {
        "name": "루리웹 에픽세븐 게시판",
        "url": "https://bbs.ruliweb.com/game/85349",
        "enabled": True,
        "timeout": 15
    },
    "reddit": {
        "name": "Reddit Epic Seven",
        "url": "https://www.reddit.com/r/EpicSeven/new/",
        "enabled": True,
        "timeout": 15
    }
}

# Master 요구사항: 사이트별 차별 타임아웃 함수 추가
def get_site_timeout(url):
    """사이트별 최적화된 타임아웃 반환"""
    if 'stove.com/epicseven/global' in url:
        return 30  # 글로벌만 30초
    elif 'stove.com/epicseven/kr' in url:
        return 15  # 한국 사이트 15초 유지
    elif 'reddit.com' in url:
        return 15  # Reddit 15초 유지
    elif 'ruliweb.com' in url:
        return 15  # 루리웹 15초 유지
    else:
        return 20  # 기타 사이트 기본값

# 크롤링 결과 저장
crawling_results = {
    'posts': [],
    'errors': [],
    'stats': {
        'total_attempted': 0,
        'successful': 0,
        'failed': 0,
        'start_time': None,
        'end_time': None
    }
}

# Selenium WebDriver 설정
def setup_chrome_driver():
    """Chrome WebDriver 설정"""
    try:
        print("[INFO] Chrome WebDriver 설정 중...")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 웹드라이버 매니저를 사용하여 자동으로 Chrome 드라이버 설치
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 자동화 감지 방지
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("[INFO] Chrome WebDriver 설정 완료")
        return driver
        
    except Exception as e:
        print(f"[ERROR] Chrome WebDriver 설정 실패: {e}")
        return None

# =============================================================================
# 중복 체크 및 링크 관리 시스템
# =============================================================================

def load_crawled_links():
    """크롤링된 링크 목록 로드"""
    try:
        if os.path.exists("crawled_links.json"):
            with open("crawled_links.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # 24시간 이전 데이터 정리
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=24)
            
            # 24시간 이내 링크만 유지
            filtered_links = []
            for item in data.get("links", []):
                try:
                    processed_time = datetime.fromisoformat(item.get("processed_at", ""))
                    if processed_time > cutoff_time:
                        filtered_links.append(item)
                except ValueError:
                    continue
            
            # 최대 1000개로 제한
            if len(filtered_links) > 1000:
                filtered_links = filtered_links[-1000:]
            
            data["links"] = filtered_links
            
            # 정리된 데이터 저장
            save_crawled_links(data)
            
            print(f"[INFO] 크롤링된 링크 로드 완료: {len(filtered_links)}개")
            return data
        else:
            print("[INFO] 크롤링 링크 파일이 없어 새로 생성")
            return {"links": []}
            
    except Exception as e:
        print(f"[ERROR] 크롤링 링크 로드 실패: {e}")
        return {"links": []}

def save_crawled_links(data):
    """크롤링된 링크 목록 저장"""
    try:
        with open("crawled_links.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 크롤링 링크 저장 완료: {len(data.get('links', []))}개")
    except Exception as e:
        print(f"[ERROR] 크롤링 링크 저장 실패: {e}")

def is_recently_processed(url: str, hours: int = 24) -> bool:
    """최근 처리된 URL인지 확인 (24시간 기준)"""
    try:
        link_data = load_crawled_links()
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=hours)
        
        for item in link_data.get("links", []):
            if item.get("url") == url:
                try:
                    processed_time = datetime.fromisoformat(item.get("processed_at", ""))
                    if processed_time > cutoff_time:
                        return True
                except ValueError:
                    continue
        
        return False
        
    except Exception as e:
        print(f"[ERROR] 중복 체크 실패: {e}")
        return False

def mark_as_processed(url: str, notified: bool = False):
    """게시글을 처리됨으로 마킹 - 알림 성공 후에만 호출"""
    try:
        link_data = load_crawled_links()
        
        # 기존 항목 업데이트 또는 새 항목 추가
        found = False
        for item in link_data["links"]:
            if item.get("url") == url:
                item["processed_at"] = datetime.now().isoformat()
                item["notified"] = notified
                found = True
                break
        
        if not found:
            link_data["links"].append({
                "url": url,
                "processed_at": datetime.now().isoformat(),
                "notified": notified
            })
        
        save_crawled_links(link_data)
        print(f"[INFO] 링크 처리 완료 마킹: {url[:50]}... (알림: {notified})")
        
    except Exception as e:
        print(f"[ERROR] 링크 마킹 실패: {e}")

# =============================================================================
# 콘텐츠 캐시 시스템
# =============================================================================

def load_content_cache():
    """콘텐츠 캐시 로드"""
    try:
        if os.path.exists("content_cache.json"):
            with open("content_cache.json", "r", encoding="utf-8") as f:
                cache = json.load(f)
            
            # 7일 이전 캐시 정리
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(days=7)
            
            cleaned_cache = {}
            for url, data in cache.items():
                try:
                    cached_time = datetime.fromisoformat(data.get("cached_at", ""))
                    if cached_time > cutoff_time:
                        cleaned_cache[url] = data
                except ValueError:
                    continue
            
            # 정리된 캐시 저장
            if len(cleaned_cache) != len(cache):
                save_content_cache(cleaned_cache)
            
            return cleaned_cache
        else:
            return {}
            
    except Exception as e:
        print(f"[ERROR] 콘텐츠 캐시 로드 실패: {e}")
        return {}

def save_content_cache(cache):
    """콘텐츠 캐시 저장"""
    try:
        with open("content_cache.json", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 콘텐츠 캐시 저장 완료: {len(cache)}개")
    except Exception as e:
        print(f"[ERROR] 콘텐츠 캐시 저장 실패: {e}")

def get_cached_content(url: str) -> Optional[Dict]:
    """캐시된 콘텐츠 조회"""
    try:
        cache = load_content_cache()
        cached_data = cache.get(url)
        
        if cached_data:
            # 24시간 이내 캐시만 사용
            cached_time = datetime.fromisoformat(cached_data.get("cached_at", ""))
            if datetime.now() - cached_time < timedelta(hours=24):
                return cached_data
        
        return None
        
    except Exception as e:
        print(f"[ERROR] 캐시 조회 실패: {e}")
        return None

def cache_content(url: str, content: Dict):
    """콘텐츠 캐시에 저장"""
    try:
        cache = load_content_cache()
        
        content_with_timestamp = content.copy()
        content_with_timestamp["cached_at"] = datetime.now().isoformat()
        
        cache[url] = content_with_timestamp
        
        # 캐시 크기 제한 (최대 1000개)
        if len(cache) > 1000:
            # 가장 오래된 항목들 제거
            sorted_items = sorted(cache.items(), key=lambda x: x[1].get("cached_at", ""))
            cache = dict(sorted_items[-1000:])
        
        save_content_cache(cache)
        
    except Exception as e:
        print(f"[ERROR] 콘텐츠 캐시 저장 실패: {e}")

# =============================================================================
# Stove 게시판 크롤링
# =============================================================================

def crawl_stove_korea_bug_board():
    """Stove 한국 버그 게시판 크롤링"""
    print("[INFO] 🌐 한국 버그 게시판 크롤링 시작...")
    target = CRAWL_TARGETS["stove_korea_bug"]
    
    try:
        return crawl_stove_board(
            board_url=target["url"],
            board_name=target["name"],
            site_timeout=target["timeout"]
        )
    except Exception as e:
        print(f"[ERROR] 한국 버그 게시판 크롤링 실패: {e}")
        return []

def crawl_stove_global_bug_board():
    """Stove 글로벌 버그 게시판 크롤링"""
    print("[INFO] 🌐 글로벌 버그 게시판 크롤링 시작...")
    target = CRAWL_TARGETS["stove_global_bug"]
    
    try:
        return crawl_stove_board(
            board_url=target["url"],
            board_name=target["name"],
            site_timeout=target["timeout"]  # Master 수정: 30초 타임아웃 적용
        )
    except Exception as e:
        print(f"[ERROR] 글로벌 버그 게시판 크롤링 실패: {e}")
        return []

def crawl_stove_korea_general_board():
    """Stove 한국 자유 게시판 크롤링"""
    print("[INFO] 🌐 한국 자유 게시판 크롤링 시작...")
    target = CRAWL_TARGETS["stove_korea_general"]
    
    try:
        return crawl_stove_board(
            board_url=target["url"],
            board_name=target["name"],
            site_timeout=target["timeout"]
        )
    except Exception as e:
        print(f"[ERROR] 한국 자유 게시판 크롤링 실패: {e}")
        return []

def crawl_stove_global_general_board():
    """Stove 글로벌 자유 게시판 크롤링"""
    print("[INFO] 🌐 글로벌 자유 게시판 크롤링 시작...")
    target = CRAWL_TARGETS["stove_global_general"]
    
    try:
        return crawl_stove_board(
            board_url=target["url"],
            board_name=target["name"],
            site_timeout=target["timeout"]  # Master 수정: 30초 타임아웃 적용
        )
    except Exception as e:
        print(f"[ERROR] 글로벌 자유 게시판 크롤링 실패: {e}")
        return []

def crawl_stove_board(board_url: str, board_name: str, site_timeout: int = 15):
    """Stove 게시판 공통 크롤링 함수"""
    posts = []
    driver = None
    
    try:
        print(f"[INFO] {board_name} 크롤링 시작 - URL: {board_url}")
        
        # WebDriver 설정
        driver = setup_chrome_driver()
        if not driver:
            print(f"[ERROR] {board_name}: WebDriver 설정 실패")
            return posts
        
        # 페이지 로드
        print(f"[DEBUG] 페이지 로딩 중... (타임아웃: {site_timeout}초)")
        driver.get(board_url)
        
        # 페이지 로딩 대기
        WebDriverWait(driver, site_timeout).until(  # Master 수정: 사이트별 타임아웃 적용
            EC.presence_of_element_located((By.CLASS_NAME, "board_list"))
        )
        
        print(f"[DEBUG] 페이지 로딩 완료")
        
        # 게시글 목록 추출
        post_elements = driver.find_elements(By.CSS_SELECTOR, ".board_list tbody tr")
        
        if not post_elements:
            print(f"[WARNING] {board_name}: 게시글을 찾을 수 없음")
            return posts
        
        print(f"[INFO] {board_name}: {len(post_elements)}개 게시글 발견")
        
        # Master 요구사항: Skip & Continue + 3회 재시도 로직
        successful_posts = 0
        total_posts = len(post_elements)
        
        for i, post_element in enumerate(post_elements, 1):
            # 3회 재시도 로직
            retry_count = 0
            max_retries = 3
            post_processed = False
            
            while retry_count < max_retries and not post_processed:
                try:
                    print(f"[DEBUG] 게시글 {i}/{total_posts} 처리 중 (시도 {retry_count + 1}/{max_retries})...")
                    
                    # 게시글 링크 추출
                    link_element = post_element.find_element(By.CSS_SELECTOR, "td.title a")
                    post_url = link_element.get_attribute("href")
                    post_title = link_element.text.strip()
                    
                    if not post_url or not post_title:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 정보 부족, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(1)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 정보 부족")
                            break
                    
                    # 중복 확인
                    if is_recently_processed(post_url):
                        print(f"[INFO] 게시글 스킵 (24시간 내 처리됨): {post_title[:30]}...")
                        post_processed = True
                        successful_posts += 1
                        break
                    
                    # 게시글 메타데이터 추출
                    try:
                        author_element = post_element.find_element(By.CSS_SELECTOR, "td.writer")
                        author = author_element.text.strip()
                    except:
                        author = "Unknown"
                    
                    try:
                        date_element = post_element.find_element(By.CSS_SELECTOR, "td.date")
                        date = date_element.text.strip()
                    except:
                        date = ""
                    
                    # 게시글 상세 내용 추출
                    content = extract_post_content_selenium(driver, post_url, site_timeout)
                    
                    if content:
                        post_data = {
                            "title": post_title,
                            "url": post_url,
                            "author": author,
                            "date": date,
                            "content": content,
                            "board": board_name,
                            "site": "stove",
                            "language": "kr" if "/kr/" in board_url else "global",
                            "crawled_at": datetime.now().isoformat()
                        }
                        
                        posts.append(post_data)
                        successful_posts += 1
                        post_processed = True
                        
                        # 🚀 핵심 수정: 여기서는 링크를 추가하지 않음 (알림 성공 후에만 추가)
                        print(f"[INFO] ✅ 게시글 수집 완료: {post_title[:50]}...")
                        
                        # 캐시에 저장
                        cache_content(post_url, post_data)
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 내용 추출 실패, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(2)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 내용 추출 실패")
                            break
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"[ERROR] 게시글 {i} 처리 중 오류, 재시도 중... ({retry_count}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        print(f"[ERROR] 게시글 {i} 최종 실패 - 다음으로 진행: {e}")
                        break
                
                # 과부하 방지를 위한 딜레이
                time.sleep(random.uniform(1, 3))
        
        # Master 요구사항: 성공률 로깅
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
        print(f"[INFO] {board_name} 크롤링 완료: {successful_posts}/{total_posts} ({success_rate:.1f}%)")
        
    except TimeoutException:
        print(f"[ERROR] {board_name}: 페이지 로딩 타임아웃")
    except Exception as e:
        print(f"[ERROR] {board_name} 크롤링 중 오류: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

def extract_post_content_selenium(driver, url: str, timeout: int = 25):
    """Selenium을 사용한 게시글 상세 내용 추출"""
    try:
        print(f"[DEBUG] 게시글 내용 추출 시도: {url}")
        
        # 캐시 확인
        cached_content = get_cached_content(url)
        if cached_content:
            print(f"[DEBUG] 캐시에서 로드: {url}")
            return cached_content.get("content", "")
        
        # 새 탭에서 게시글 열기
        driver.execute_script(f"window.open('{url}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # 페이지 로딩 대기
        print(f"[DEBUG] 페이지 로딩 대기 중... ({timeout}초)")
        WebDriverWait(driver, timeout).until(  # Master 수정: 동적 타임아웃 적용
            EC.presence_of_element_located((By.CLASS_NAME, "board_view"))
        )
        
        # 최적화된 스크롤링
        print(f"[DEBUG] 최적화된 스크롤링 시작...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        print(f"[DEBUG] 최적화된 스크롤링 완료")
        
        # 콘텐츠 추출
        content_element = driver.find_element(By.CSS_SELECTOR, ".board_view .view_content")
        content = content_element.text.strip()
        
        # 탭 닫기
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        
        return content
        
    except TimeoutException:
        print(f"[ERROR] 게시글 내용 추출 타임아웃: {url}")
        # Master 수정: 탭 정리 후 None 반환 (전체 중단하지 않음)
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return None
    except Exception as e:
        print(f"[ERROR] 게시글 내용 추출 실패: {url} - {e}")
        # Master 수정: 탭 정리 후 None 반환 (전체 중단하지 않음)
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return None

# =============================================================================
# 루리웹 크롤링
# =============================================================================

def crawl_ruliweb_epic7():
    """루리웹 에픽세븐 게시판 크롤링"""
    print("[INFO] 🌐 루리웹 에픽세븐 게시판 크롤링 시작...")
    posts = []
    
    try:
        target = CRAWL_TARGETS["ruliweb"]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(target["url"], headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 게시글 목록 추출
        post_elements = soup.select('table.board_list_table tbody tr')
        
        if not post_elements:
            print("[WARNING] 루리웹: 게시글을 찾을 수 없음")
            return posts
        
        print(f"[INFO] 루리웹: {len(post_elements)}개 게시글 발견")
        
        # Master 요구사항: Skip & Continue + 3회 재시도 로직
        successful_posts = 0
        total_posts = len(post_elements)
        
        for i, post_element in enumerate(post_elements, 1):
            # 3회 재시도 로직
            retry_count = 0
            max_retries = 3
            post_processed = False
            
            while retry_count < max_retries and not post_processed:
                try:
                    print(f"[DEBUG] 루리웹 게시글 {i}/{total_posts} 처리 중 (시도 {retry_count + 1}/{max_retries})...")
                    
                    # 공지사항 제외
                    if post_element.select_one('.notice'):
                        post_processed = True
                        continue
                    
                    # 게시글 링크 및 제목 추출
                    title_element = post_element.select_one('td.subject a.deco')
                    if not title_element:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 정보 부족, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(1)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 정보 부족")
                            break
                    
                    post_title = title_element.text.strip()
                    post_url = urljoin(target["url"], title_element.get('href', ''))
                    
                    # 중복 확인
                    if is_recently_processed(post_url):
                        print(f"[INFO] 게시글 스킵 (24시간 내 처리됨): {post_title[:30]}...")
                        post_processed = True
                        successful_posts += 1
                        break
                    
                    # 게시글 메타데이터 추출
                    try:
                        author_element = post_element.select_one('td.writer')
                        author = author_element.text.strip() if author_element else "Unknown"
                    except:
                        author = "Unknown"
                    
                    try:
                        date_element = post_element.select_one('td.time')
                        date = date_element.text.strip() if date_element else ""
                    except:
                        date = ""
                    
                    # 게시글 상세 내용 추출
                    content = extract_ruliweb_post_content(post_url)
                    
                    if content:
                        post_data = {
                            "title": post_title,
                            "url": post_url,
                            "author": author,
                            "date": date,
                            "content": content,
                            "board": "루리웹 에픽세븐",
                            "site": "ruliweb",
                            "language": "kr",
                            "crawled_at": datetime.now().isoformat()
                        }
                        
                        posts.append(post_data)
                        successful_posts += 1
                        post_processed = True
                        
                        # 🚀 핵심 수정: 여기서는 링크를 추가하지 않음 (알림 성공 후에만 추가)
                        print(f"[INFO] ✅ 루리웹 게시글 수집 완료: {post_title[:50]}...")
                        
                        # 캐시에 저장
                        cache_content(post_url, post_data)
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 내용 추출 실패, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(2)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 내용 추출 실패")
                            break
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"[ERROR] 루리웹 게시글 {i} 처리 중 오류, 재시도 중... ({retry_count}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        print(f"[ERROR] 루리웹 게시글 {i} 최종 실패 - 다음으로 진행: {e}")
                        break
                    
                # 과부하 방지를 위한 딜레이
                time.sleep(random.uniform(2, 4))
        
        # Master 요구사항: 성공률 로깅
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
        print(f"[INFO] 루리웹 크롤링 완료: {successful_posts}/{total_posts} ({success_rate:.1f}%)")
        
    except requests.RequestException as e:
        print(f"[ERROR] 루리웹 페이지 요청 실패: {e}")
    except Exception as e:
        print(f"[ERROR] 루리웹 크롤링 중 오류: {e}")
    
    return posts

def extract_ruliweb_post_content(url: str):
    """루리웹 게시글 상세 내용 추출"""
    try:
        print(f"[DEBUG] 루리웹 게시글 내용 추출: {url}")
        
        # 캐시 확인
        cached_content = get_cached_content(url)
        if cached_content:
            print(f"[DEBUG] 캐시에서 로드: {url}")
            return cached_content.get("content", "")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 게시글 내용 추출
        content_element = soup.select_one('.view_content, .article_content')
        if content_element:
            content = content_element.get_text(strip=True)
            return content
        else:
            print(f"[WARNING] 루리웹 게시글 내용을 찾을 수 없음: {url}")
            return ""
            
    except requests.RequestException as e:
        print(f"[ERROR] 루리웹 게시글 요청 실패: {url} - {e}")
        return ""
    except Exception as e:
        print(f"[ERROR] 루리웹 게시글 내용 추출 실패: {url} - {e}")
        return ""

# =============================================================================
# Reddit 크롤링
# =============================================================================

def crawl_reddit_epic7():
    """Reddit Epic Seven 서브레딧 크롤링"""
    print("[INFO] 🌐 Reddit Epic Seven 크롤링 시작...")
    posts = []
    driver = None
    
    try:
        target = CRAWL_TARGETS["reddit"]
        
        # WebDriver 설정
        driver = setup_chrome_driver()
        if not driver:
            print("[ERROR] Reddit: WebDriver 설정 실패")
            return posts
        
        print(f"[INFO] Reddit 페이지 로딩: {target['url']}")
        driver.get(target["url"])
        
        # 페이지 로딩 대기 (Reddit은 동적 로딩)
        time.sleep(5)
        
        # 스크롤하여 더 많은 게시글 로드
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # 게시글 요소 찾기
        post_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="post-container"]')
        
        if not post_elements:
            print("[WARNING] Reddit: 게시글을 찾을 수 없음")
            return posts
        
        print(f"[INFO] Reddit: {len(post_elements)}개 게시글 발견")
        
        # Master 요구사항: Skip & Continue + 3회 재시도 로직
        successful_posts = 0
        total_posts = len(post_elements)
        
        for i, post_element in enumerate(post_elements, 1):
            # 3회 재시도 로직
            retry_count = 0
            max_retries = 3
            post_processed = False
            
            while retry_count < max_retries and not post_processed:
                try:
                    print(f"[DEBUG] Reddit 게시글 {i}/{total_posts} 처리 중 (시도 {retry_count + 1}/{max_retries})...")
                    
                    # 게시글 제목 및 링크 추출
                    title_element = post_element.find_element(By.CSS_SELECTOR, '[data-testid="post-title"]')
                    post_title = title_element.text.strip()
                    
                    # Reddit 게시글 URL 추출
                    link_element = post_element.find_element(By.CSS_SELECTOR, 'a[data-testid="post-title"]')
                    post_url = link_element.get_attribute("href")
                    
                    if not post_url or not post_title:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 정보 부족, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(1)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 정보 부족")
                            break
                    
                    # 중복 확인
                    if is_recently_processed(post_url):
                        print(f"[INFO] 게시글 스킵 (24시간 내 처리됨): {post_title[:30]}...")
                        post_processed = True
                        successful_posts += 1
                        break
                    
                    # 게시글 메타데이터 추출
                    try:
                        author_element = post_element.find_element(By.CSS_SELECTOR, '[data-testid="post-byline"] a')
                        author = author_element.text.strip()
                    except:
                        author = "Unknown"
                    
                    try:
                        time_element = post_element.find_element(By.CSS_SELECTOR, '[data-testid="post-timestamp"]')
                        date = time_element.get_attribute("title") or time_element.text.strip()
                    except:
                        date = ""
                    
                    # 게시글 내용 추출 (Reddit은 제목이 주요 내용)
                    try:
                        content_element = post_element.find_element(By.CSS_SELECTOR, '[data-testid="post-content"] p')
                        content = content_element.text.strip()
                    except:
                        content = post_title  # 내용이 없으면 제목 사용
                    
                    if content:
                        post_data = {
                            "title": post_title,
                            "url": post_url,
                            "author": author,
                            "date": date,
                            "content": content,
                            "board": "Reddit Epic Seven",
                            "site": "reddit",
                            "language": "en",
                            "crawled_at": datetime.now().isoformat()
                        }
                        
                        posts.append(post_data)
                        successful_posts += 1
                        post_processed = True
                        
                        # 🚀 핵심 수정: 여기서는 링크를 추가하지 않음 (알림 성공 후에만 추가)
                        print(f"[INFO] ✅ Reddit 게시글 수집 완료: {post_title[:50]}...")
                        
                        # 캐시에 저장
                        cache_content(post_url, post_data)
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"[WARNING] 게시글 내용 추출 실패, 재시도 중... ({retry_count}/{max_retries})")
                            time.sleep(2)
                            continue
                        else:
                            print(f"[WARNING] 게시글 {i} 스킵: 내용 추출 실패")
                            break
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"[ERROR] Reddit 게시글 {i} 처리 중 오류, 재시도 중... ({retry_count}/{max_retries}): {e}")
                        time.sleep(2)
                        continue
                    else:
                        print(f"[ERROR] Reddit 게시글 {i} 최종 실패 - 다음으로 진행: {e}")
                        break
                
                # 과부하 방지를 위한 딜레이
                time.sleep(random.uniform(1, 2))
        
        # Master 요구사항: 성공률 로깅
        success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
        print(f"[INFO] Reddit 크롤링 완료: {successful_posts}/{total_posts} ({success_rate:.1f}%)")
        
    except Exception as e:
        print(f"[ERROR] Reddit 크롤링 중 오류: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return posts

# =============================================================================
# 스케줄 기반 크롤링 제어
# =============================================================================

def crawl_by_schedule(schedule_type: str) -> List[Dict]:
    """스케줄에 따른 크롤링 실행"""
    all_posts = []
    
    try:
        print(f"[INFO] === {schedule_type} 크롤링 시작 ===")
        
        if schedule_type == "15min":
            # 15분 주기: 전체 사이트 크롤링
            print("[INFO] 15분 주기: 전체 사이트 크롤링")
            all_posts.extend(crawl_frequent_sites())
            
        elif schedule_type == "30min":
            # 30분 주기: 일반 게시판 크롤링
            print("[INFO] 30분 주기: 일반 게시판 크롤링")
            all_posts.extend(crawl_regular_sites())
            
        else:
            print(f"[WARNING] 알 수 없는 스케줄 타입: {schedule_type}")
            return []
        
        print(f"[INFO] === {schedule_type} 크롤링 완료: {len(all_posts)}개 게시글 ===")
        return all_posts
        
    except Exception as e:
        print(f"[ERROR] {schedule_type} 크롤링 실패: {e}")
        return []

def crawl_frequent_sites() -> List[Dict]:
    """15분 주기 크롤링 대상 사이트들"""
    all_posts = []
    
    try:
        # 버그 게시판 우선 크롤링
        all_posts.extend(crawl_stove_korea_bug_board())
        all_posts.extend(crawl_stove_global_bug_board())
        
        # Reddit 크롤링
        all_posts.extend(crawl_reddit_epic7())
        
        return all_posts
        
    except Exception as e:
        print(f"[ERROR] 빈번 사이트 크롤링 실패: {e}")
        return all_posts

def crawl_regular_sites() -> List[Dict]:
    """30분 주기 크롤링 대상 사이트들"""
    all_posts = []
    
    try:
        # 일반 게시판 크롤링
        all_posts.extend(crawl_stove_korea_general_board())
        all_posts.extend(crawl_stove_global_general_board())
        
        # 루리웹 크롤링
        all_posts.extend(crawl_ruliweb_epic7())
        
        return all_posts
        
    except Exception e:
        print(f"[ERROR] 일반 사이트 크롤링 실패: {e}")
        return all_posts

# =============================================================================
# 리포트용 데이터 수집
# =============================================================================

def get_all_posts_for_report(hours: int = 24) -> List[Dict]:
    """리포트 생성을 위한 모든 게시글 데이터 수집"""
    all_posts = []
    
    try:
        print(f"[INFO] 리포트용 데이터 수집 시작 (최근 {hours}시간)")
        
        # 캐시에서 최근 데이터 로드
        cache = load_content_cache()
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=hours)
        
        for url, data in cache.items():
            try:
                cached_time = datetime.fromisoformat(data.get("cached_at", ""))
                if cached_time > cutoff_time:
                    all_posts.append(data)
            except ValueError:
                continue
        
        print(f"[INFO] 리포트용 데이터 수집 완료: {len(all_posts)}개 게시글")
        return all_posts
        
    except Exception as e:
        print(f"[ERROR] 리포트용 데이터 수집 실패: {e}")
        return []

# =============================================================================
# 메인 실행 함수들
# =============================================================================

def main():
    """메인 실행 함수"""
    try:
        print("🎮 Epic7 크롤러 v4.3 시작")
        print("=" * 50)
        
        # 전체 크롤링 실행
        all_posts = []
        
        # 각 사이트별 크롤링
        all_posts.extend(crawl_stove_korea_bug_board())
        all_posts.extend(crawl_stove_global_bug_board())
        all_posts.extend(crawl_stove_korea_general_board())
        all_posts.extend(crawl_stove_global_general_board())
        all_posts.extend(crawl_ruliweb_epic7())
        all_posts.extend(crawl_reddit_epic7())
        
        print("=" * 50)
        print(f"🎯 전체 크롤링 완료: {len(all_posts)}개 게시글 수집")
        
        return all_posts
        
    except Exception as e:
        print(f"[ERROR] 메인 실행 중 오류: {e}")
        return []

if __name__ == "__main__":
    main()