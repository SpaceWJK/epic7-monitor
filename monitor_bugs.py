#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 모니터링 시스템 - 메인 컨트롤러 (디스패처 호환 완전 버전)
Korean/Global/All 모드 분기 처리와 워크플로우 호환성 구현

Author: Epic7 Monitoring Team
Version: 2.1.0 (디스패처 호환)
Date: 2025-07-16
"""

import os
import sys
import json
import argparse
import time
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path

# 로컬 모듈 임포트 (수정된 함수명으로 정확히 매칭)
from crawler import (
    # 한국 사이트 크롤링 함수들
    fetch_stove_bug_board,
    fetch_stove_general_board,
    fetch_ruliweb_epic7_board,
    fetch_arca_epic7_board,
    
    # 글로벌 사이트 크롤링 함수들
    fetch_stove_global_bug_board,
    fetch_stove_global_general_board,
    fetch_reddit_epic7_board,
    fetch_epic7_official_forum,  # ✅ 수정됨 (forums_board → official_forum)
    
    # 유틸리티 함수들
    check_discord_webhooks,
    send_discord_message,
    load_crawled_links,
    save_crawled_links,
    get_file_paths  # ✅ 수정됨 (get_file_path → get_file_paths)
)

from classifier import (
    is_bug_post,
    classify_post,
    is_high_priority_bug,
    extract_bug_severity
)

from notifier import (
    send_bug_alert,
    send_sentiment_alert,
    format_korean_notification,
    format_global_notification,
    create_summary_embed
)

# 로깅 설정 (디스패처 호환)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_bugs.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MonitoringModes:
    """모니터링 모드 상수 (디스패처 호환)"""
    KOREAN = "korean"
    GLOBAL = "global"
    ALL = "all"
    
    @classmethod
    def get_valid_modes(cls) -> List[str]:
        return [cls.KOREAN, cls.GLOBAL, cls.ALL]
    
    @classmethod
    def is_dispatcher_mode(cls, mode: str) -> bool:
        """디스패처에서 호출되는 모드인지 확인"""
        return mode in [cls.KOREAN, cls.GLOBAL]

class Epic7Monitor:
    """Epic7 모니터링 시스템 메인 클래스 (디스패처 호환)"""
    
    def __init__(self, mode: str, debug: bool = False, test: bool = False):
        self.mode = mode
        self.debug = debug
        self.test = test
        self.start_time = datetime.now()
        self.is_dispatcher_mode = MonitoringModes.is_dispatcher_mode(mode)
        
        # 디스패처 모드에 따른 로깅 레벨 조정
        if self.is_dispatcher_mode:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # 웹훅 검증
        self.webhooks = check_discord_webhooks()
        
        # 통계 초기화
        self.stats = {
            'total_crawled': 0,
            'new_posts': 0,
            'bug_posts': 0,
            'sentiment_posts': 0,
            'errors': 0,
            'mode': mode,
            'dispatcher_mode': self.is_dispatcher_mode
        }
        
        # 모드 검증
        if mode not in MonitoringModes.get_valid_modes():
            raise ValueError(f"Invalid mode: {mode}. Valid modes: {MonitoringModes.get_valid_modes()}")
        
        logger.info(f"Epic7Monitor 초기화 완료 - 모드: {mode}, 디스패처 모드: {self.is_dispatcher_mode}")
    
    def get_crawling_functions(self) -> Dict[str, callable]:
        """모드에 따른 크롤링 함수 매핑 (디스패처 호환)"""
        korean_sites = {
            'stove_bug_kr': fetch_stove_bug_board,
            'stove_general_kr': fetch_stove_general_board,
            'ruliweb_epic7': fetch_ruliweb_epic7_board,
            'arca_epic7': fetch_arca_epic7_board,
        }
        
        global_sites = {
            'stove_bug_global': fetch_stove_global_bug_board,
            'stove_general_global': fetch_stove_global_general_board,
            'reddit_epic7': fetch_reddit_epic7_board,
            'epic7_official_forum': fetch_epic7_official_forum,  # ✅ 수정됨
        }
        
        if self.mode == MonitoringModes.KOREAN:
            return korean_sites
        elif self.mode == MonitoringModes.GLOBAL:
            return global_sites
        elif self.mode == MonitoringModes.ALL:
            return {**korean_sites, **global_sites}
        else:
            return {}
    
    def get_mode_specific_file_paths(self) -> Tuple[str, str]:
        """모드별 파일 경로 반환 (디스패처 호환)"""
        if self.mode == MonitoringModes.KOREAN:
            return get_file_paths("korean")
        elif self.mode == MonitoringModes.GLOBAL:
            return get_file_paths("global")
        else:
            return get_file_paths("all")
    
    def crawl_sites_parallel(self) -> List[Dict]:
        """병렬로 사이트 크롤링 실행 (디스패처 최적화)"""
        crawling_functions = self.get_crawling_functions()
        all_posts = []
        
        if not crawling_functions:
            logger.warning(f"모드 '{self.mode}'에 대한 크롤링 함수가 없습니다.")
            return all_posts
        
        # 디스패처 모드에서는 동시성 제한
        max_workers = 2 if self.is_dispatcher_mode else 4
        
        logger.info(f"병렬 크롤링 시작: {len(crawling_functions)}개 사이트 (디스패처 모드: {self.is_dispatcher_mode})")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 각 사이트별로 Future 생성
            future_to_site = {
                executor.submit(self.safe_crawl_site, site_name, crawl_func): site_name
                for site_name, crawl_func in crawling_functions.items()
            }
            
            # 결과 수집 (디스패처 모드에서는 타임아웃 단축)
            timeout = 180 if self.is_dispatcher_mode else 300
            
            for future in concurrent.futures.as_completed(future_to_site, timeout=timeout):
                site_name = future_to_site[future]
                try:
                    posts = future.result()
                    if posts:
                        all_posts.extend(posts)
                        logger.info(f"✅ {site_name}: {len(posts)}개 새 게시글")
                    else:
                        logger.info(f"⭕ {site_name}: 새 게시글 없음")
                        
                except Exception as e:
                    logger.error(f"❌ {site_name} 크롤링 실패: {e}")
                    self.stats['errors'] += 1
        
        self.stats['total_crawled'] = len(all_posts)
        logger.info(f"병렬 크롤링 완료: 총 {len(all_posts)}개 게시글")
        return all_posts
    
    def safe_crawl_site(self, site_name: str, crawl_func: callable) -> List[Dict]:
        """안전한 사이트 크롤링 (디스패처 호환 재시도 메커니즘)"""
        # 디스패처 모드에서는 재시도 횟수 제한
        max_retries = 2 if self.is_dispatcher_mode else 3
        retry_delay = 3 if self.is_dispatcher_mode else 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 {site_name} 크롤링 시도 {attempt + 1}/{max_retries}")
                
                # 테스트 모드에서는 제한된 결과만 반환
                if self.test:
                    posts = crawl_func()
                    return posts[:2] if posts else []
                
                # 모드별 파일 경로 전달
                if hasattr(crawl_func, '__code__') and 'mode' in crawl_func.__code__.co_varnames:
                    posts = crawl_func(mode=self.mode)
                else:
                    posts = crawl_func()
                
                if posts is None:
                    posts = []
                
                # 성공 시 반환
                return posts
                
            except Exception as e:
                logger.error(f"❌ {site_name} 크롤링 시도 {attempt + 1} 실패: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"⏳ {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"💥 {site_name} 크롤링 최종 실패")
                    
                    # 실패 알림 전송 (디스패처 모드에서는 생략)
                    if not self.is_dispatcher_mode and self.webhooks.get('bug'):
                        error_msg = f"🚨 **크롤링 실패 알림**\n\n"
                        error_msg += f"**사이트**: {site_name}\n"
                        error_msg += f"**오류**: {str(e)[:200]}...\n"
                        error_msg += f"**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        error_msg += f"**모드**: {self.mode}"
                        
                        send_discord_message(
                            self.webhooks['bug'],
                            error_msg,
                            f"Epic7 모니터링 - 크롤링 실패"
                        )
        
        return []
    
    def classify_and_filter_posts(self, posts: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """게시글 분류 및 필터링 (디스패처 호환)"""
        bug_posts = []
        sentiment_posts = []
        
        for post in posts:
            try:
                # 분류 수행
                classification = classify_post(post['title'])
                post['classification'] = classification
                post['mode'] = self.mode  # 모드 정보 추가
                
                # 버그 게시글 분류
                if classification == 'bug' or is_bug_post(post['title']) or post.get('source') == 'stove_bug':
                    # 심각도 평가
                    severity = extract_bug_severity(post['title'])
                    post['severity'] = severity
                    post['is_high_priority'] = is_high_priority_bug(post['title'])
                    
                    bug_posts.append(post)
                    self.stats['bug_posts'] += 1
                    
                    logger.info(f"🐛 버그 게시글 발견: {post['title'][:50]}... (심각도: {severity})")
                else:
                    # 감성 게시글 분류 (한국 사이트만)
                    if self.mode != MonitoringModes.GLOBAL:
                        sentiment_posts.append(post)
                        self.stats['sentiment_posts'] += 1
                        
                        logger.debug(f"📊 감성 게시글: {post['title'][:50]}... (분류: {classification})")
                    
            except Exception as e:
                logger.error(f"❌ 게시글 분류 실패: {e}")
                logger.error(f"   게시글: {post.get('title', 'N/A')}")
                self.stats['errors'] += 1
        
        self.stats['new_posts'] = len(posts)
        
        logger.info(f"분류 완료: 버그 {len(bug_posts)}개, 감성 {len(sentiment_posts)}개")
        return bug_posts, sentiment_posts
    
    def send_notifications(self, bug_posts: List[Dict], sentiment_posts: List[Dict]):
        """알림 전송 (디스패처 호환)"""
        
        # 버그 알림 전송
        if bug_posts and self.webhooks.get('bug'):
            try:
                # 모드에 따른 포맷팅
                if self.mode == MonitoringModes.KOREAN:
                    formatted_message = format_korean_notification(bug_posts, 'bug')
                elif self.mode == MonitoringModes.GLOBAL:
                    formatted_message = format_global_notification(bug_posts, 'bug')
                else:
                    formatted_message = create_summary_embed(bug_posts, 'bug')
                
                success = send_bug_alert(self.webhooks['bug'], bug_posts)
                
                if success:
                    logger.info(f"✅ 버그 알림 전송 성공: {len(bug_posts)}개 게시글")
                else:
                    logger.error(f"❌ 버그 알림 전송 실패")
                    
            except Exception as e:
                logger.error(f"❌ 버그 알림 전송 중 오류: {e}")
        
        # 감성 동향 알림 전송 (한국 사이트만, 디스패처 모드에서는 생략)
        if (sentiment_posts and self.webhooks.get('sentiment') and 
            self.mode != MonitoringModes.GLOBAL and not self.is_dispatcher_mode):
            try:
                # 높은 관심도의 게시글만 필터링
                high_interest_posts = [
                    post for post in sentiment_posts
                    if post.get('classification') in ['positive', 'negative'] and len(post.get('title', '')) > 10
                ]
                
                if high_interest_posts:
                    success = send_sentiment_alert(self.webhooks['sentiment'], high_interest_posts)
                    
                    if success:
                        logger.info(f"✅ 감성 동향 알림 전송 성공: {len(high_interest_posts)}개 게시글")
                    else:
                        logger.error(f"❌ 감성 동향 알림 전송 실패")
                        
            except Exception as e:
                logger.error(f"❌ 감성 동향 알림 전송 중 오류: {e}")
    
    def generate_execution_report(self) -> str:
        """실행 보고서 생성 (디스패처 호환)"""
        end_time = datetime.now()
        execution_time = end_time - self.start_time
        
        report = f"""
🔍 **Epic7 모니터링 실행 보고서**

**실행 정보**
- 모드: {self.mode.upper()}
- 디스패처 모드: {'Yes' if self.is_dispatcher_mode else 'No'}
- 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
- 실행 시간: {execution_time.total_seconds():.1f}초

**크롤링 결과**
- 총 크롤링 게시글: {self.stats['total_crawled']}개
- 새 게시글: {self.stats['new_posts']}개
- 버그 게시글: {self.stats['bug_posts']}개
- 감성 게시글: {self.stats['sentiment_posts']}개
- 오류 발생: {self.stats['errors']}개

**시스템 상태**
- 워크플로우 모드: {'DISPATCHER' if self.is_dispatcher_mode else 'DEBUG' if self.debug else 'TEST' if self.test else 'PRODUCTION'}
- 크롤링 대상: {', '.join(self.get_crawling_functions().keys())}
- 활성 웹훅: {', '.join(self.webhooks.keys())}

**성능 지표**
- 평균 처리 시간: {execution_time.total_seconds() / max(1, self.stats['total_crawled']):.2f}초/게시글
- 성공률: {((self.stats['total_crawled'] - self.stats['errors']) / max(1, self.stats['total_crawled']) * 100):.1f}%
- 메모리 최적화: {'적용됨' if self.is_dispatcher_mode else '표준'}

**현재 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report.strip()
    
    def run(self):
        """메인 실행 함수 (디스패처 호환)"""
        try:
            logger.info(f"🚀 Epic7 모니터링 시작 - 모드: {self.mode} (디스패처: {self.is_dispatcher_mode})")
            
            # 1. 병렬 크롤링 실행
            posts = self.crawl_sites_parallel()
            
            if not posts:
                logger.info("새로운 게시글이 없습니다.")
                return True
            
            # 2. 게시글 분류 및 필터링
            bug_posts, sentiment_posts = self.classify_and_filter_posts(posts)
            
            # 3. 알림 전송
            self.send_notifications(bug_posts, sentiment_posts)
            
            # 4. 실행 보고서 생성
            report = self.generate_execution_report()
            
            # 디스패처 모드에서는 간략한 로그만 출력
            if self.is_dispatcher_mode:
                logger.info(f"디스패처 실행 완료: {self.stats['new_posts']}개 게시글, {self.stats['bug_posts']}개 버그")
            else:
                logger.info("실행 보고서:\n" + report)
            
            # 5. 디버그 모드에서 보고서 Discord 전송 (디스패처 모드에서는 생략)
            if self.debug and not self.is_dispatcher_mode and self.webhooks.get('report'):
                send_discord_message(
                    self.webhooks['report'],
                    report,
                    f"Epic7 모니터링 실행 보고서 - {self.mode.upper()}"
                )
            
            logger.info("🎉 Epic7 모니터링 성공적으로 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 Epic7 모니터링 실행 중 치명적 오류: {e}")
            
            # 치명적 오류 알림 (디스패처 모드에서는 생략)
            if not self.is_dispatcher_mode and self.webhooks.get('bug'):
                error_report = f"""
🚨 **치명적 오류 발생**

**오류 내용**: {str(e)[:500]}...
**발생 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**모드**: {self.mode}
**디스패처 모드**: {self.is_dispatcher_mode}
**실행 통계**: {self.stats}

시스템 점검이 필요합니다.
"""
                send_discord_message(
                    self.webhooks['bug'],
                    error_report,
                    "Epic7 모니터링 - 치명적 오류"
                )
            
            return False

def parse_arguments():
    """명령행 인자 파싱 (디스패처 호환)"""
    parser = argparse.ArgumentParser(
        description="Epic7 모니터링 시스템 - 디스패처 호환 완전 버전",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
디스패처 사용 예시:
  python monitor_bugs.py --mode korean           # 한국 사이트만 (디스패처 모드)
  python monitor_bugs.py --mode global           # 글로벌 사이트만 (디스패처 모드)
  python monitor_bugs.py --mode all              # 모든 사이트 (통합 모드)
  python monitor_bugs.py --mode korean --debug   # 디버그 모드
  python monitor_bugs.py --mode global --test    # 테스트 모드
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=MonitoringModes.get_valid_modes(),
        default=MonitoringModes.KOREAN,
        help='모니터링 모드 선택 (default: korean)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='테스트 모드 활성화 (제한된 결과만 처리)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Epic7 Monitor v2.1.0 (디스패처 호환)'
    )
    
    return parser.parse_args()

def main():
    """메인 함수 (디스패처 호환)"""
    try:
        # 1. 인자 파싱
        args = parse_arguments()
        
        # 2. 환경 변수 확인
        if not any(os.getenv(key) for key in ['DISCORD_WEBHOOK_BUG', 'DISCORD_WEBHOOK_SENTIMENT']):
            logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다.")
            logger.warning("알림 기능이 제한될 수 있습니다.")
        
        # 3. 디스패처 모드 감지
        is_github_actions = os.getenv('GITHUB_ACTIONS', '').lower() == 'true'
        is_dispatcher_call = MonitoringModes.is_dispatcher_mode(args.mode) and is_github_actions
        
        if is_dispatcher_call:
            logger.info(f"디스패처 모드 감지: {args.mode} (GitHub Actions)")
        
        # 4. 모니터링 시스템 초기화
        monitor = Epic7Monitor(
            mode=args.mode,
            debug=args.debug,
            test=args.test
        )
        
        # 5. 모니터링 실행
        success = monitor.run()
        
        # 6. 종료 코드 반환
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링이 중단되었습니다.")
        sys.exit(130)
        
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()