#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 모니터링 시스템 공통 유틸리티
중복 코드 제거 및 공통 기능 통합

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
"""

import hashlib
import re
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps

from config import config

logger = logging.getLogger(__name__)

# =============================================================================
# 로깅 설정 통합
# =============================================================================

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    통합 로깅 설정
    
    Args:
        level: 로그 레벨
        log_file: 로그 파일 경로
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 로그 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 핸들러 설정
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 새 핸들러 추가
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    logger.info(f"로깅 설정 완료: 레벨={level}, 파일={log_file}")

# =============================================================================
# 문자열 처리 유틸리티
# =============================================================================

def get_url_hash(url: str) -> str:
    """URL 해시 생성"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def extract_content_summary(content: str, max_length: int = 100) -> str:
    """게시글 내용 요약"""
    if not content or len(content.strip()) < 10:
        return "게시글 내용 확인을 위해 링크를 클릭하세요."
    
    content = re.sub(r'\s+', ' ', content.strip())
    content = re.sub(r'[^\w\s가-힣.,!?]', '', content)
    
    sentences = re.split(r'[.!?]', content)
    first_sentence = sentences[0].strip() if sentences else content
    
    if len(first_sentence) > max_length:
        first_sentence = first_sentence[:max_length-3] + '...'
    elif len(first_sentence) > 10:
        first_sentence = first_sentence + '...'
    
    return first_sentence if first_sentence else "게시글 내용 확인을 위해 링크를 클릭하세요."

def truncate_text(text: str, max_length: int) -> str:
    """텍스트 길이 제한"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + '...'

def is_korean_text(text: str) -> bool:
    """한국어 텍스트 판별"""
    if not text:
        return False
    
    korean_count = len(re.findall(r'[가-힣]', text))
    total_chars = len(re.findall(r'[가-힣a-zA-Z]', text))
    
    if total_chars == 0:
        return False
    
    return korean_count / total_chars > 0.3

def fix_stove_url(url: str) -> str:
    """스토브 URL 정규화"""
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

# =============================================================================
# 시간 처리 유틸리티
# =============================================================================

def is_frequent_schedule() -> bool:
    """현재 시간이 15분 간격 스케줄인지 확인"""
    current_minute = datetime.now().minute
    return current_minute % 15 == 0

def is_regular_schedule() -> bool:
    """현재 시간이 30분 간격 스케줄인지 확인"""
    current_minute = datetime.now().minute
    return current_minute % 30 == 0

def format_timestamp(timestamp: str) -> str:
    """타임스탬프 포맷팅"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp[:19] if len(timestamp) > 19 else timestamp

def get_time_range(hours: int) -> tuple[datetime, datetime]:
    """시간 범위 계산"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    return start_time, end_time

# =============================================================================
# 재시도 및 에러 처리 유틸리티
# =============================================================================

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} 시도 {attempt + 1}/{max_retries} 실패: {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"{func.__name__} 최종 실패: {e}")
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator

def safe_execute(func, *args, default=None, **kwargs):
    """안전한 함수 실행"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"함수 실행 실패: {func.__name__}, 에러: {e}")
        return default

# =============================================================================
# 데이터 처리 유틸리티
# =============================================================================

def get_site_display_name(source: str) -> str:
    """소스 표시명 반환"""
    site_names = {
        'stove_bug': '스토브 버그신고',
        'stove_general': '스토브 일반게시판',
        'stove_global_bug': '스토브 글로벌 버그',
        'stove_global_general': '스토브 글로벌 일반',
        'ruliweb_epic7': '루리웹 에픽세븐',
        'arca_epic7': '아카라이브 에픽세븐',
        'reddit_epic7': 'Reddit EpicSeven',
        'official_forum': '공식 포럼'
    }
    return site_names.get(source, source)

def get_category_emoji(category: str) -> str:
    """카테고리별 이모지 반환"""
    emoji_map = {
        'bug': '🐛',
        'positive': '😊',
        'negative': '😞',
        'neutral': '😐',
        'critical': '🚨',
        'high': '⚠️',
        'medium': '⚡',
        'low': '💡'
    }
    return emoji_map.get(category, '❓')

def clean_data_list(data_list: List[Dict], max_items: int = 1000) -> List[Dict]:
    """데이터 리스트 정리"""
    if len(data_list) <= max_items:
        return data_list
    
    # 타임스탬프 기준 정렬 후 최신 데이터만 유지
    try:
        sorted_data = sorted(
            data_list,
            key=lambda x: x.get('timestamp', '2000-01-01'),
            reverse=True
        )
        return sorted_data[:max_items]
    except:
        return data_list[:max_items]

def merge_statistics(stats1: Dict, stats2: Dict) -> Dict:
    """통계 데이터 병합"""
    merged = stats1.copy()
    
    for key, value in stats2.items():
        if key in merged:
            if isinstance(value, (int, float)) and isinstance(merged[key], (int, float)):
                merged[key] += value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                merged[key] = merge_statistics(merged[key], value)
        else:
            merged[key] = value
    
    return merged

# =============================================================================
# 시스템 유틸리티
# =============================================================================

def get_random_user_agent() -> str:
    """랜덤 User-Agent 반환"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

def get_random_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> float:
    """랜덤 지연 시간 반환"""
    return random.uniform(min_delay, max_delay)

def validate_url(url: str) -> bool:
    """URL 유효성 검증"""
    if not url:
        return False
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None

def get_memory_usage() -> Dict[str, Any]:
    """메모리 사용량 조회"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss': memory_info.rss,
            'vms': memory_info.vms,
            'percent': process.memory_percent()
        }
    except ImportError:
        return {'error': 'psutil not available'}
    except Exception as e:
        return {'error': str(e)}

# =============================================================================
# 전역 유틸리티 초기화
# =============================================================================

def initialize_utils():
    """유틸리티 초기화"""
    setup_logging()
    logger.info("Epic7 유틸리티 초기화 완료")

# 모듈 로드 시 자동 초기화
initialize_utils()
