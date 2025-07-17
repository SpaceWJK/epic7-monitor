#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 모니터링 시스템 크롤링 엔진 (완전 수정 버전)
Korean/Global 모드 분기 처리와 글로벌 크롤링 함수 완전 구현

Author: Epic7 Monitoring Team
Version: 2.1.0
Date: 2025-07-16
"""

import json
import os
import sys
import time
import random
import hashlib
import re
import requests
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
from selenium.webdriver.common.keys import Keys

# HTML 파싱
from bs4 import BeautifulSoup

# 로깅 설정
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 모드 기반 파일 분리 시스템
# =============================================================================

DEFAULT_CRAWLED_LINKS_FILE = "crawled_links.json"
DEFAULT_CONTENT_CACHE_FILE = "content_cache.json"

def get_mode_specific_filepath(base_filename: str, mode: str) -> str:
    """모드에 따라 파일 경로를 반환합니다."""
    if mode == "korean":
        return base_filename.replace(".json", "_korean.json")
    elif mode == "global":
        return base_filename.replace(".json", "_global.json")
    return base_filename

def load_crawled_links(filename: str) -> Dict[str, Any]:
    """크롤링된 링크 데이터를 파일에서 로드합니다."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("links", {}) # 링크를 딕셔너리로 저장
        return {"links": {}, "last_updated": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"[ERROR] 크롤링된 링크 로드 실패 ({filename}): {e}")
        return {"links": {}, "last_updated": datetime.now().isoformat()}

def save_crawled_links(links: Dict[str, Any], filename: str, max_links: int = 1000):
    """크롤링된 링크 데이터를 파일에 저장합니다 (최신 1000개 유지)."""
    try:
        # 날짜별로 정렬하여 오래된 링크 제거
        sorted_links = sorted(links.items(), key=lambda item: item[1]['timestamp'], reverse=True)
        links_to_save = dict(sorted_links[:max_links])
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({"links": links_to_save, "last_updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        logger.info(f"크롤링된 링크 {len(links_to_save)}개 저장 완료 ({filename}).")
    except Exception as e:
        logger.error(f"[ERROR] 크롤링된 링크 저장 실패 ({filename}): {e}")

def load_content_cache(filename: str) -> Dict[str, Dict[str, Any]]:
    """게시글 내용 캐시를 파일에서 로드합니다."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"[ERROR] 내용 캐시 로드 실패 ({filename}): {e}")
        return {}

def save_content_cache(cache: Dict[str, Dict[str, Any]], filename: str, max_age_days: int = 30):
    """게시글 내용 캐시를 파일에 저장하고 오래된 항목을 정리합니다."""
    try:
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cleaned_cache = {}
        for url, data in cache.items():
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                try:
                    post_timestamp = datetime.fromisoformat(timestamp_str)
                    if post_timestamp >= cutoff_time:
                        cleaned_cache[url] = data
                except ValueError:
                    # 타임스탬프 형식 오류 시 해당 항목은 유지 (오류 방지)
                    cleaned_cache[url] = data
            else:
                cleaned_cache[url] = data # 타임스탬프 없는 항목은 일단 유지

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(cleaned_cache, f, ensure_ascii=False, indent=2)
        logger.info(f"내용 캐시 {len(cleaned_cache)}개 저장 및 정리 완료 ({filename}).")
    except Exception as e:
        logger.error(f"[ERROR] 내용 캐시 저장 실패 ({filename}): {e}")

# =============================================================================
# Selenium WebDriver 관리 (webdriver_manager 제거)
# =============================================================================

# 이제 get_chrome_driver 함수는 WebDriver 인스턴스를 직접 반환하는 대신
# 호출하는 쪽(monitor_bugs.py)에서 명시적으로 초기화하도록 변경되었습니다.
# 따라서 이 함수는 더 이상 외부에서 직접 사용되지 않지만, 내부 테스트용으로 남겨둘 수 있습니다.
# CI 환경에서는 ChromeDriver가 이미 설치되어 있다고 가정합니다.
def get_chrome_driver():
    """
    ChromeDriver를 초기화하고 반환합니다.
    (로컬 테스트용. CI 환경에서는 이미 설치되어 사용됨)
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # ChromeDriver 경로를 직접 지정하거나 환경 변수에서 가져오는 방식
    # GitHub Actions에서는 /usr/local/bin/chromedriver 에 설치됨
    driver_path = os.getenv('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver') 
    
    if not os.path.exists(driver_path):
        logger.error(f"ChromeDriver를 찾을 수 없습니다: {driver_path}")
        logger.error("GitHub Actions 환경이 아니거나, ChromeDriver가 설치되지 않았습니다.")
        raise FileNotFoundError(f"ChromeDriver not found at {driver_path}")
    
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    logger.info(f"Chrome Driver 버전: {driver.capabilities['browserVersion']}")
    logger.info(f"Chrome Driver 경로: {driver_path}")
    return driver

# =============================================================================
# Discord 웹훅 유틸리티 함수 (notifier.py로 이동됨. 하위 호환성 위해 남겨둠)
# =============================================================================

def check_discord_webhooks():
    """Discord 웹훅 환경변수 유무를 확인합니다."""
    webhook_bug = os.getenv('DISCORD_WEBHOOK_BUG')
    webhook_sentiment = os.getenv('DISCORD_WEBHOOK_SENTIMENT')
    webhook_report = os.getenv('DISCORD_WEBHOOK_REPORT')
    
    if not webhook_bug and not webhook_sentiment and not webhook_report:
        logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다. 알림을 보낼 수 없습니다.")
        return False
    return True

def send_discord_message(webhook_url: str, message: str, title: str = "알림", color: int = 3447003):
    """
    Discord 웹훅을 통해 메시지를 전송합니다.
    (notifier.py로 로직이 이동되었으므로 이 함수는 사용하지 않는 것이 권장됨)
    """
    if not webhook_url:
        logger.warning("웹훅 URL이 없어 메시지를 보낼 수 없습니다.")
        return False
        
    payload = {
        "embeds": [{
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }]
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
        response.raise_for_status()
        # logger.info(f"Discord 메시지 전송 성공: {title}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord 메시지 전송 실패: {e}")
        return False

# =============================================================================
# 크롤링 헬퍼 함수
# =============================================================================

def _parse_post_data(element, source_name: str, base_url: Optional[str] = None) -> Optional[Dict[str, str]]:
    """HTML 요소에서 게시글 제목, URL, 시간 등을 파싱합니다."""
    try:
        title_element = element.select_one('h3.s-board-title span.s-board-title-text')
        # 스토브는 a 태그 안에 제목 있음
        if not title_element:
            title_element = element.select_one('a.link-item') # 루리웹이나 아카라이브 등 다른 사이트의 제목 선택자

        url_element = element.select_one('a.link-item') # URL이 포함된 a 태그
        
        if not title_element or not url_element:
            return None # 필수 요소 없으면 스킵

        title = title_element.get_text(strip=True)
        relative_url = url_element['href']
        
        # 상대 URL을 절대 URL로 변환
        url = urljoin(base_url, relative_url) if base_url else relative_url
        
        # 공지사항 필터링 (스토브 기준)
        if element.select_one('i.element-badge__s.notice') or element.select_one('i.element-badge__s.event'):
            logger.debug(f"공지/이벤트 게시글 필터링: {title}")
            return None
            
        timestamp = datetime.now().isoformat() # 크롤링 시간 기준으로 저장

        post_id = hashlib.md5(url.encode('utf-8')).hexdigest() # URL 해시로 고유 ID 생성

        return {
            "id": post_id,
            "title": title,
            "url": url,
            "timestamp": timestamp,
            "source": source_name,
            "content": "" # 초기에는 비워둠, 필요시 상세 크롤링 시 채움
        }
    except Exception as e:
        logger.error(f"게시글 파싱 중 오류 발생 (소스: {source_name}): {e}", exc_info=True)
        return None

def _get_page_source(driver) -> str:
    """WebDriver의 현재 페이지 소스를 반환합니다."""
    return driver.page_source

def _perform_scroll(driver, scroll_count: int, scroll_pause_time: float = 1.0):
    """지정된 횟수만큼 페이지를 스크롤합니다."""
    for _ in range(scroll_count):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)

# =============================================================================
# 사이트별 크롤링 함수 (한국)
# =============================================================================

def fetch_stove_bug_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """스토브 에픽세븐 버그 게시판을 크롤링합니다."""
    logger.info("스토브 버그 게시판 크롤링 시작...")
    base_url = "https://page.onstove.com/epicseven/kr/bug/list"
    new_posts = []
    
    if test_mode:
        logger.info("테스트 모드: 스토브 버그 게시판 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.s-board-list'))
        )
        
        # 동적 스크롤링: 유저 게시글 영역까지 로딩을 위해 2회 스크롤
        _perform_scroll(driver, 2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('ul.s-board-list li')

        if debug_mode:
            with open("stove_bug_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("stove_bug_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10: # 테스트 모드에서는 10개만 처리
                break
            post = _parse_post_data(element, "stove_bug", base_url)
            if post and post['url'] not in crawled_links['links']:
                new_posts.append(post)
                crawled_links['links'][post['url']] = {"id": post['id'], "timestamp": post['timestamp']}
                content_cache[post['url']] = post # 캐시에 게시글 전체 내용 저장
                logger.info(f"새로운 게시글 발견 (스토브 버그): {post['title']}")
        
        logger.info(f"스토브 버그 게시판 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"스토브 버그 게시판 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_stove_general_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """스토브 에픽세븐 일반 게시판을 크롤링합니다."""
    logger.info("스토브 일반 게시판 크롤링 시작...")
    base_url = "https://page.onstove.com/epicseven/kr/view/list/85145" # 일반 게시판 ID
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 스토브 일반 게시판 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.s-board-list'))
        )
        
        _perform_scroll(driver, 2) # 동적 로딩을 위해 2회 스크롤

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('ul.s-board-list li')

        if debug_mode:
            with open("stove_general_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("stove_general_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10: # 테스트 모드에서는 10개만 처리
                break
            post = _parse_post_data(element, "stove_general", base_url)
            if post and post['url'] not in crawled_links['links']:
                new_posts.append(post)
                crawled_links['links'][post['url']] = {"id": post['id'], "timestamp": post['timestamp']}
                content_cache[post['url']] = post
                logger.info(f"새로운 게시글 발견 (스토브 일반): {post['title']}")
        
        logger.info(f"스토브 일반 게시판 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"스토브 일반 게시판 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_ruliweb_epic7_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """루리웹 에픽세븐 게시판을 크롤링합니다."""
    logger.info("루리웹 에픽세븐 게시판 크롤링 시작...")
    base_url = "https://bbs.ruliweb.com/game/84518" # 에픽세븐 게시판 ID
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 루리웹 에픽세븐 게시판 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.board_list_table table.board_list'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('div.board_list_table table.board_list tbody tr.table_body')

        if debug_mode:
            with open("ruliweb_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("ruliweb_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10: # 테스트 모드에서는 10개만 처리
                break
            # 루리웹 파싱 로직은 _parse_post_data와 다를 수 있으므로 별도 구현
            try:
                title_a_tag = element.select_one('td.subject a')
                if not title_a_tag: continue
                
                title = title_a_tag.get_text(strip=True)
                url = title_a_tag['href']

                # 공지사항 필터링 (고정된 공지는 title_a_tag에 '공지' 같은 텍스트가 있을 수 있음)
                # 루리웹은 "공지" 클래스나 "공지" 텍스트로 구분
                if element.select_one('td.subject strong.notice_icon') or "공지" in title:
                    logger.debug(f"루리웹 공지사항 필터링: {title}")
                    continue

                timestamp = datetime.now().isoformat()
                post_id = hashlib.md5(url.encode('utf-8')).hexdigest()

                post_data = {
                    "id": post_id,
                    "title": title,
                    "url": url,
                    "timestamp": timestamp,
                    "source": "ruliweb_epic7",
                    "content": ""
                }
                
                if post_data['url'] not in crawled_links['links']:
                    new_posts.append(post_data)
                    crawled_links['links'][post_data['url']] = {"id": post_data['id'], "timestamp": post_data['timestamp']}
                    content_cache[post_data['url']] = post_data
                    logger.info(f"새로운 게시글 발견 (루리웹): {post_data['title']}")
            except Exception as e:
                logger.error(f"루리웹 게시글 파싱 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"루리웹 에픽세븐 게시판 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"루리웹 에픽세븐 게시판 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_arca_epic7_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """아카라이브 에픽세븐 채널을 크롤링합니다."""
    logger.info("아카라이브 에픽세븐 채널 크롤링 시작...")
    base_url = "https://arca.live/b/epic7"
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 아카라이브 에픽세븐 채널 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.board-article-list'))
        )
        
        _perform_scroll(driver, 2) # 동적 로딩을 위해 스크롤

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('div.board-article-list div.list-group-item')

        if debug_mode:
            with open("arca_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("arca_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10: # 테스트 모드에서는 10개만 처리
                break
            # 아카라이브 파싱 로직은 _parse_post_data와 다를 수 있으므로 별도 구현
            try:
                title_a_tag = element.select_one('a.article-link')
                if not title_a_tag: continue
                
                title = title_a_tag.get_text(strip=True)
                url = urljoin(base_url, title_a_tag['href'])

                # 공지사항 필터링 (아카라이브는 'notice' 클래스 등으로 구분)
                if element.select_one('div.badge.notice'):
                    logger.debug(f"아카라이브 공지사항 필터링: {title}")
                    continue

                timestamp = datetime.now().isoformat()
                post_id = hashlib.md5(url.encode('utf-8')).hexdigest()

                post_data = {
                    "id": post_id,
                    "title": title,
                    "url": url,
                    "timestamp": timestamp,
                    "source": "arca_epic7",
                    "content": ""
                }
                
                if post_data['url'] not in crawled_links['links']:
                    new_posts.append(post_data)
                    crawled_links['links'][post_data['url']] = {"id": post_data['id'], "timestamp": post_data['timestamp']}
                    content_cache[post_data['url']] = post_data
                    logger.info(f"새로운 게시글 발견 (아카라이브): {post_data['title']}")
            except Exception as e:
                logger.error(f"아카라이브 게시글 파싱 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"아카라이브 에픽세븐 채널 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"아카라이브 에픽세븐 채널 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

# =============================================================================
# 사이트별 크롤링 함수 (글로벌)
# =============================================================================

def fetch_stove_global_bug_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """스토브 에픽세븐 글로벌 버그 게시판을 크롤링합니다."""
    logger.info("스토브 글로벌 버그 게시판 크롤링 시작...")
    base_url = "https://page.onstove.com/epicseven/global/bug/list"
    new_posts = []
    
    if test_mode:
        logger.info("테스트 모드: 스토브 글로벌 버그 게시판 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.s-board-list'))
        )
        
        _perform_scroll(driver, 2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('ul.s-board-list li')

        if debug_mode:
            with open("stove_global_bug_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("stove_global_bug_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10:
                break
            post = _parse_post_data(element, "stove_global_bug", base_url)
            if post and post['url'] not in crawled_links['links']:
                new_posts.append(post)
                crawled_links['links'][post['url']] = {"id": post['id'], "timestamp": post['timestamp']}
                content_cache[post['url']] = post
                logger.info(f"새로운 게시글 발견 (스토브 글로벌 버그): {post['title']}")
        
        logger.info(f"스토브 글로벌 버그 게시판 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"스토브 글로벌 버그 게시판 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_stove_global_general_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """스토브 에픽세븐 글로벌 일반 게시판을 크롤링합니다."""
    logger.info("스토브 글로벌 일반 게시판 크롤링 시작...")
    base_url = "https://page.onstove.com/epicseven/global/view/list/96860" # 일반 게시판 ID
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 스토브 글로벌 일반 게시판 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.s-board-list'))
        )
        
        _perform_scroll(driver, 2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('ul.s-board-list li')

        if debug_mode:
            with open("stove_global_general_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("stove_global_general_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10:
                break
            post = _parse_post_data(element, "stove_global_general", base_url)
            if post and post['url'] not in crawled_links['links']:
                new_posts.append(post)
                crawled_links['links'][post['url']] = {"id": post['id'], "timestamp": post['timestamp']}
                content_cache[post['url']] = post
                logger.info(f"새로운 게시글 발견 (스토브 글로벌 일반): {post['title']}")
        
        logger.info(f"스토브 글로벌 일반 게시판 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"스토브 글로벌 일반 게시판 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_reddit_epic7_board(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """레딧 에픽세븐 서브레딧을 크롤링합니다."""
    logger.info("레딧 에픽세븐 서브레딧 크롤링 시작...")
    base_url = "https://www.reddit.com/r/EpicSeven/"
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 레딧 에픽세븐 서브레딧 상위 10개 게시글만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="post-container"]'))
        )
        
        _perform_scroll(driver, 3) # 여러 번 스크롤하여 더 많은 게시글 로딩

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Reddit은 구조가 복잡하므로, 가장 바깥쪽 게시글 컨테이너를 찾고 내부에서 파싱
        post_containers = soup.select('div[data-testid="post-container"]')

        if debug_mode:
            with open("reddit_epic7_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("reddit_epic7_debug_selenium.html 저장 완료.")

        for i, container in enumerate(post_containers):
            if test_mode and i >= 10: # 테스트 모드에서는 10개만 처리
                break
            try:
                # 제목 추출
                title_element = container.select_one('h3')
                if not title_element: continue
                title = title_element.get_text(strip=True)

                # URL 추출
                url_element = container.select_one('a[data-testid="post-title"]')
                if not url_element: continue
                url = url_element['href']
                if not url.startswith('http'):
                    url = urljoin(base_url, url)

                # Reddit은 공지나 광고가 복잡하게 섞여있으므로, 간단하게 필터링
                if "sponsored" in url or "reddit.com/r/all" in url: # 광고성 게시물 필터링
                    logger.debug(f"레딧 광고/공지 필터링: {title}")
                    continue

                timestamp = datetime.now().isoformat() # 크롤링 시간 기준
                post_id = hashlib.md5(url.encode('utf-8')).hextime
                
                post_data = {
                    "id": post_id,
                    "title": title,
                    "url": url,
                    "timestamp": timestamp,
                    "source": "reddit_epic7",
                    "content": ""
                }
                
                if post_data['url'] not in crawled_links['links']:
                    new_posts.append(post_data)
                    crawled_links['links'][post_data['url']] = {"id": post_data['id'], "timestamp": post_data['timestamp']}
                    content_cache[post_data['url']] = post_data
                    logger.info(f"새로운 게시글 발견 (레딧): {post_data['title']}")
            except Exception as e:
                logger.error(f"레딧 게시글 파싱 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"레딧 에픽세븐 서브레딧 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"레딧 에픽세븐 서브레딧 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

def fetch_epic7_official_forum(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """에픽세븐 공식 글로벌 포럼을 크롤링합니다."""
    logger.info("에픽세븐 공식 글로벌 포럼 크롤링 시작...")
    base_url = "https://epic7.smilegatemegaport.com/ 자유게시판_URL" # 실제 자유게시판 URL로 변경 필요
    # 예시: "https://epic7.smilegatemegaport.com/community/free/list"
    new_posts = []

    if test_mode:
        logger.info("테스트 모드: 공식 글로벌 포럼 1페이지만 크롤링")

    try:
        driver.get(base_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.board_list table tbody'))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        board_elements = soup.select('div.board_list table tbody tr')

        if debug_mode:
            with open("official_forum_debug_selenium.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.debug("official_forum_debug_selenium.html 저장 완료.")

        for i, element in enumerate(board_elements):
            if test_mode and i >= 10:
                break
            try:
                title_a_tag = element.select_one('td.td_subject a')
                if not title_a_tag: continue
                
                title = title_a_tag.get_text(strip=True)
                url = urljoin(base_url, title_a_tag['href'])

                # 공지사항 필터링 (공식 포럼의 공지사항 클래스나 텍스트 확인)
                if element.select_one('td.td_notice') or "Notice" in title or "공지" in title:
                    logger.debug(f"공식 포럼 공지사항 필터링: {title}")
                    continue

                timestamp = datetime.now().isoformat()
                post_id = hashlib.md5(url.encode('utf-8')).hexdigest()

                post_data = {
                    "id": post_id,
                    "title": title,
                    "url": url,
                    "timestamp": timestamp,
                    "source": "epic7_official_forum",
                    "content": ""
                }
                
                if post_data['url'] not in crawled_links['links']:
                    new_posts.append(post_data)
                    crawled_links['links'][post_data['url']] = {"id": post_data['id'], "timestamp": post_data['timestamp']}
                    content_cache[post_data['url']] = post_data
                    logger.info(f"새로운 게시글 발견 (공식 포럼): {post_data['title']}")
            except Exception as e:
                logger.error(f"공식 포럼 게시글 파싱 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"에픽세븐 공식 글로벌 포럼 크롤링 완료: {len(new_posts)}개의 새로운 게시글 발견.")
    except Exception as e:
        logger.error(f"에픽세븐 공식 글로벌 포럼 크롤링 중 오류 발생: {e}", exc_info=True)
    return new_posts

# =============================================================================
# 통합 크롤링 함수
# =============================================================================

def crawl_korean_sites(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """모든 한국 사이트를 통합하여 크롤링합니다."""
    all_new_posts = []
    
    # 각 한국 사이트 크롤링 함수 호출
    all_new_posts.extend(fetch_stove_bug_board(driver, crawled_links, content_cache, debug_mode, test_mode))
    # all_new_posts.extend(fetch_stove_general_board(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    # all_new_posts.extend(fetch_ruliweb_epic7_board(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    # all_new_posts.extend(fetch_arca_epic7_board(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    
    # 시간순 정렬 (최신 게시글 우선)
    all_new_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    logger.info(f"통합 한국 사이트 크롤링 완료: 총 {len(all_new_posts)}개의 새로운 게시글 발견.")
    return all_new_posts

def crawl_global_sites(driver, crawled_links: Dict[str, Any], content_cache: Dict[str, Dict[str, Any]], debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """모든 글로벌 사이트를 통합하여 크롤링합니다."""
    all_new_posts = []

    # 각 글로벌 사이트 크롤링 함수 호출
    all_new_posts.extend(fetch_stove_global_bug_board(driver, crawled_links, content_cache, debug_mode, test_mode))
    # all_new_posts.extend(fetch_stove_global_general_board(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    # all_new_posts.extend(fetch_reddit_epic7_board(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    # all_new_posts.extend(fetch_epic7_official_forum(driver, crawled_links, content_cache, debug_mode, test_mode)) # 필요시 주석 해제
    
    # 시간순 정렬 (최신 게시글 우선)
    all_new_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    logger.info(f"통합 글로벌 사이트 크롤링 완료: 총 {len(all_new_posts)}개의 새로운 게시글 발견.")
    return all_new_posts

def crawl_all_sites(driver, crawled_links_korean: Dict[str, Any], crawled_links_global: Dict[str, Any], 
                    content_cache_korean: Dict[str, Dict[str, Any]], content_cache_global: Dict[str, Dict[str, Any]], 
                    debug_mode: bool, test_mode: bool) -> List[Dict[str, Any]]:
    """모든 한국 및 글로벌 사이트를 통합하여 크롤링합니다."""
    logger.info("모든 사이트 통합 크롤링 시작...")
    all_new_posts = []

    # 한국 사이트 크롤링 (한국어 링크/캐시 파일 사용)
    all_new_posts.extend(crawl_korean_sites(driver, crawled_links_korean, content_cache_korean, debug_mode, test_mode))
    
    # 글로벌 사이트 크롤링 (글로벌 링크/캐시 파일 사용)
    all_new_posts.extend(crawl_global_sites(driver, crawled_links_global, content_cache_global, debug_mode, test_mode))
    
    # 시간순 정렬
    all_new_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    logger.info(f"모든 사이트 통합 크롤링 완료: 총 {len(all_new_posts)}개 게시글 발견.")
    return all_new_posts

# =============================================================================
# 리포트용 게시글 수집 함수 (generate_report.py 에서 사용)
# =============================================================================

# 이 함수는 이제 generate_report.py의 GlobalDataManager.load_all_data()로 대체됨.
# 따라서 여기서 호출되지 않음.
def get_all_posts_for_report(mode: str = "all", hours: int = 24) -> List[Dict[str, Any]]:
    """
    일일 리포트 생성을 위해 최근 게시글을 모두 수집합니다.
    이 함수는 실제 크롤링을 수행하지 않고, 저장된 캐시에서 데이터를 로드합니다.
    """
    logger.info(f"리포트용 게시글 수집 시작 (모드: {mode}, 지난 {hours}시간)")
    
    all_posts = []
    
    # 여기서 직접 크롤러 드라이버를 생성하지 않음.
    # generate_report.py의 GlobalDataManager가 파일에서 직접 데이터를 로드함.
    # 따라서 이 함수는 기능적으로 필요가 없어짐.
    # 기존 코드와의 호환성을 위해 형식만 유지.
    
    logger.info(f"리포트용 게시글 수집 완료: 총 {len(all_posts)}개 게시글")
    return all_posts

# =============================================================================
# 메인 실행 함수들
# =============================================================================

def main_crawl(mode: str = "korean"):
    """
    메인 크롤링 실행 함수.
    주로 generate_report.py에서 호출되어 데이터를 최신화할 때 사용됩니다.
    """
    logger.info(f"Epic7 모니터링 시스템 크롤링 시작 (mode: {mode}) - generate_report.py 호출용")
    
    # GitHub Actions 환경에서는 드라이버가 이미 설치되어 있다고 가정합니다.
    # 따라서 여기서 get_chrome_driver를 호출하지 않고,
    # monitor_bugs.py 에서 드라이버를 직접 초기화하고 전달하는 방식이 더 견고합니다.
    # 여기서는 임시로 드라이버를 생성하거나, 드라이버가 없으면 에러를 발생시킵니다.
    
    driver = None
    try:
        driver = get_chrome_driver() # 로컬 테스트 시 여기서 드라이버 생성
        if not driver:
            logger.error("ChromeDriver를 초기화할 수 없습니다. main_crawl 실행 불가.")
            return []

        crawled_links_korean = load_crawled_links(get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "korean"))
        content_cache_korean = load_content_cache(get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "korean"))
        crawled_links_global = load_crawled_links(get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "global"))
        content_cache_global = load_content_cache(get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "global"))

        all_posts = []
        if mode == "korean":
            all_posts = crawl_korean_sites(driver, crawled_links_korean, content_cache_korean, debug_mode=True, test_mode=False)
        elif mode == "global":
            all_posts = crawl_global_sites(driver, crawled_links_global, content_cache_global, debug_mode=True, test_mode=False)
        elif mode == "all":
            all_posts = crawl_all_sites(driver, crawled_links_korean, crawled_links_global, 
                                        content_cache_korean, content_cache_global, debug_mode=True, test_mode=False)
        else:
            logger.error(f"지원되지 않는 모드: {mode}")
            return []
        
        save_crawled_links(crawled_links_korean, get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "korean"))
        save_content_cache(content_cache_korean, get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "korean"))
        save_crawled_links(crawled_links_global, get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "global"))
        save_content_cache(content_cache_global, get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "global"))

        logger.info(f"크롤링 실행 완료 (mode: {mode}): 총 {len(all_posts)}개 게시글 처리")
        return all_posts
    except Exception as e:
        logger.error(f"main_crawl 실행 중 오류 발생: {e}", exc_info=True)
        return []
    finally:
        if driver:
            driver.quit()

def test_crawling():
    """크롤링 테스트 함수"""
    logger.info("크롤링 테스트 함수 시작...")
    driver = None
    try:
        driver = get_chrome_driver()
        if not driver:
            logger.error("ChromeDriver 초기화 실패. 크롤링 테스트 불가.")
            return

        test_crawled_links_korean = load_crawled_links(get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "korean"))
        test_content_cache_korean = load_content_cache(get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "korean"))
        test_crawled_links_global = load_crawled_links(get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "global"))
        test_content_cache_global = load_content_cache(get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "global"))

        logger.info("테스트: 스토브 버그 게시판")
        fetch_stove_bug_board(driver, test_crawled_links_korean, test_content_cache_korean, debug_mode=True, test_mode=True)
        save_crawled_links(test_crawled_links_korean, get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "korean"))
        save_content_cache(test_content_cache_korean, get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "korean"))

        # 필요에 따라 다른 크롤링 함수 테스트 추가
        logger.info("테스트: 레딧 에픽세븐 서브레딧")
        fetch_reddit_epic7_board(driver, test_crawled_links_global, test_content_cache_global, debug_mode=True, test_mode=True)
        save_crawled_links(test_crawled_links_global, get_mode_specific_filepath(DEFAULT_CRAWLED_LINKS_FILE, "global"))
        save_content_cache(test_content_cache_global, get_mode_specific_filepath(DEFAULT_CONTENT_CACHE_FILE, "global"))

        logger.info("크롤링 테스트 완료.")
    except Exception as e:
        logger.error(f"크롤링 테스트 중 오류 발생: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # 이 스크립트 단독 실행 시 테스트 용도
    test_crawling()