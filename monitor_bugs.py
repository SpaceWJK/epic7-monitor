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
    load_content_cache,
    save_content_cache,
    get_file_path,
    crawl_korean_sites,
    crawl_global_sites,
    crawl_all_sites
)

from classifier import (
    is_bug_post,
    classify_post,
    is_high_priority_bug
)

from notifier import (
    send_bug_alert,
    send_sentiment_update,
    format_bug_notification,
    format_sentiment_notification
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('monitor_bugs.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class Epic7MonitoringSystem:
    """Epic7 모니터링 시스템 메인 컨트롤러"""
    
    def __init__(self, mode: str = "all"):
        """
        모니터링 시스템 초기화
        Args:
            mode: 'korean', 'global', 'all'
        """
        self.mode = mode
        self.valid_modes = self.get_valid_modes()
        self.is_dispatcher = self.is_dispatcher_mode()
        
        if mode not in self.valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Valid modes: {self.valid_modes}")
        
        logger.info(f"[INIT] Epic7 모니터링 시스템 초기화 완료 (모드: {mode})")
        
    def get_valid_modes(self) -> List[str]:
        """유효한 모드 목록 반환"""
        return ["korean", "global", "all"]
    
    def is_dispatcher_mode(self) -> bool:
        """디스패처 모드인지 확인"""
        return os.getenv('GITHUB_WORKFLOW') == 'Epic Seven Bug Monitor Dispatcher'
    
    def get_crawling_functions(self) -> Dict[str, callable]:
        """모드별 크롤링 함수 반환"""
        korean_functions = {
            'stove_bug': fetch_stove_bug_board,
            'stove_general': fetch_stove_general_board,
            'ruliweb': fetch_ruliweb_epic7_board,
            'arca': fetch_arca_epic7_board
        }
        
        global_functions = {
            'stove_global_bug': fetch_stove_global_bug_board,
            'stove_global_general': fetch_stove_global_general_board,
            'reddit': fetch_reddit_epic7_board,
            'official_forum': fetch_epic7_official_forum
        }
        
        if self.mode == "korean":
            return korean_functions
        elif self.mode == "global":
            return global_functions
        else:  # all
            return {**korean_functions, **global_functions}
    
    def get_mode_specific_file_paths(self) -> Dict[str, str]:
        """모드별 파일 경로 반환"""
        if self.mode == "korean":
            return {
                'links': get_file_path('crawled_links_korean.json'),
                'cache': get_file_path('content_cache_korean.json')
            }
        elif self.mode == "global":
            return {
                'links': get_file_path('crawled_links_global.json'),
                'cache': get_file_path('content_cache_global.json')
            }
        else:  # all
            return {
                'links': get_file_path('crawled_links.json'),
                'cache': get_file_path('content_cache.json')
            }
    
    async def crawl_sites_parallel(self) -> Dict[str, List[Dict]]:
        """사이트별 병렬 크롤링 실행"""
        crawl_functions = self.get_crawling_functions()
        results = {}
        
        # 병렬 실행을 위한 태스크 생성
        tasks = []
        for site_name, crawl_func in crawl_functions.items():
            task = asyncio.create_task(
                self.safe_crawl_site(site_name, crawl_func)
            )
            tasks.append((site_name, task))
        
        # 모든 태스크 완료 대기
        for site_name, task in tasks:
            try:
                result = await task
                results[site_name] = result
                logger.info(f"[CRAWL] {site_name} 크롤링 완료: {len(result)}개 게시글")
            except Exception as e:
                logger.error(f"[CRAWL] {site_name} 크롤링 실패: {e}")
                results[site_name] = []
        
        return results
    
    async def safe_crawl_site(self, site_name: str, crawl_func: callable) -> List[Dict]:
        """안전한 사이트 크롤링 (에러 처리 포함)"""
        try:
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, crawl_func)
                result = await future
            
            if result is None:
                logger.warning(f"[CRAWL] {site_name} 크롤링 결과 없음")
                return []
            
            # 결과가 리스트가 아닌 경우 변환
            if not isinstance(result, list):
                if isinstance(result, dict):
                    result = [result]
                else:
                    logger.warning(f"[CRAWL] {site_name} 예상치 못한 결과 타입: {type(result)}")
                    return []
            
            return result
            
        except Exception as e:
            logger.error(f"[CRAWL] {site_name} 크롤링 중 오류 발생: {e}")
            return []
    
    def classify_and_filter_posts(self, crawled_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """크롤링된 게시글 분류 및 필터링"""
        classified_results = {
            'bug_posts': [],
            'high_priority_bugs': [],
            'general_posts': [],
            'classification_stats': {}
        }
        
        total_posts = 0
        bug_count = 0
        high_priority_count = 0
        
        for site_name, posts in crawled_data.items():
            site_bug_count = 0
            site_high_priority_count = 0
            
            for post in posts:
                total_posts += 1
                
                try:
                    # 기본 분류
                    is_bug = is_bug_post(post.get('title', ''), post.get('content', ''), site_name)
                    
                    if is_bug:
                        bug_count += 1
                        site_bug_count += 1
                        
                        # 분류 정보 추가
                        classification = classify_post(post.get('title', ''), post.get('content', ''), site_name)
                        post['classification'] = classification
                        post['source_site'] = site_name
                        
                        classified_results['bug_posts'].append(post)
                        
                        # 고우선순위 버그 확인
                        if is_high_priority_bug(post.get('title', ''), post.get('content', ''), site_name):
                            high_priority_count += 1
                            site_high_priority_count += 1
                            classified_results['high_priority_bugs'].append(post)
                    else:
                        post['source_site'] = site_name
                        classified_results['general_posts'].append(post)
                        
                except Exception as e:
                    logger.error(f"[CLASSIFY] 게시글 분류 중 오류: {e}")
                    post['source_site'] = site_name
                    classified_results['general_posts'].append(post)
            
            # 사이트별 통계
            classified_results['classification_stats'][site_name] = {
                'total_posts': len(posts),
                'bug_posts': site_bug_count,
                'high_priority_bugs': site_high_priority_count
            }
        
        # 전체 통계
        classified_results['classification_stats']['total'] = {
            'total_posts': total_posts,
            'bug_posts': bug_count,
            'high_priority_bugs': high_priority_count
        }
        
        logger.info(f"[CLASSIFY] 분류 완료 - 전체: {total_posts}, 버그: {bug_count}, 고우선순위: {high_priority_count}")
        
        return classified_results
    
    async def send_notifications(self, classified_data: Dict[str, List[Dict]]) -> Dict[str, bool]:
        """분류된 데이터 기반 알림 전송"""
        notification_results = {
            'bug_alerts': False,
            'sentiment_updates': False,
            'errors': []
        }
        
        try:
            # Discord 웹훅 상태 확인
            webhook_status = check_discord_webhooks()
            if not webhook_status['all_valid']:
                logger.warning("[NOTIFY] 일부 Discord 웹훅이 설정되지 않았습니다")
            
            # 버그 알림 전송
            if classified_data['high_priority_bugs']:
                try:
                    for bug_post in classified_data['high_priority_bugs']:
                        notification_data = format_bug_notification(bug_post)
                        success = send_bug_alert(notification_data)
                        if success:
                            notification_results['bug_alerts'] = True
                        await asyncio.sleep(0.5)  # 알림 간격 조절
                        
                except Exception as e:
                    error_msg = f"버그 알림 전송 실패: {e}"
                    logger.error(f"[NOTIFY] {error_msg}")
                    notification_results['errors'].append(error_msg)
            
            # 감성 업데이트 전송
            if classified_data['general_posts']:
                try:
                    sentiment_data = {
                        'total_posts': len(classified_data['general_posts']),
                        'bug_posts': len(classified_data['bug_posts']),
                        'high_priority_bugs': len(classified_data['high_priority_bugs']),
                        'stats': classified_data['classification_stats']
                    }
                    
                    notification_data = format_sentiment_notification(sentiment_data)
                    success = send_sentiment_update(notification_data)
                    if success:
                        notification_results['sentiment_updates'] = True
                        
                except Exception as e:
                    error_msg = f"감성 업데이트 전송 실패: {e}"
                    logger.error(f"[NOTIFY] {error_msg}")
                    notification_results['errors'].append(error_msg)
            
            logger.info(f"[NOTIFY] 알림 전송 완료: {notification_results}")
            
        except Exception as e:
            error_msg = f"알림 전송 중 전체 오류: {e}"
            logger.error(f"[NOTIFY] {error_msg}")
            notification_results['errors'].append(error_msg)
        
        return notification_results
    
    def generate_execution_report(self, crawled_data: Dict[str, List[Dict]], 
                                classified_data: Dict[str, List[Dict]], 
                                notification_results: Dict[str, bool]) -> Dict[str, Any]:
        """실행 결과 리포트 생성"""
        report = {
            'execution_time': datetime.now().isoformat(),
            'mode': self.mode,
            'crawling_summary': {
                'total_sites': len(crawled_data),
                'successful_sites': len([site for site, posts in crawled_data.items() if posts]),
                'total_posts': sum(len(posts) for posts in crawled_data.values()),
                'site_details': {
                    site: len(posts) for site, posts in crawled_data.items()
                }
            },
            'classification_summary': classified_data.get('classification_stats', {}),
            'notification_summary': {
                'bug_alerts_sent': notification_results.get('bug_alerts', False),
                'sentiment_updates_sent': notification_results.get('sentiment_updates', False),
                'errors': notification_results.get('errors', [])
            },
            'performance_metrics': {
                'total_execution_time': None,  # 실행 시간 계산 필요
                'average_posts_per_site': None,
                'success_rate': None
            }
        }
        
        # 성능 메트릭 계산
        if report['crawling_summary']['total_sites'] > 0:
            report['performance_metrics']['average_posts_per_site'] = (
                report['crawling_summary']['total_posts'] / report['crawling_summary']['total_sites']
            )
            report['performance_metrics']['success_rate'] = (
                report['crawling_summary']['successful_sites'] / report['crawling_summary']['total_sites']
            ) * 100
        
        return report
    
    async def run_monitoring_cycle(self) -> Dict[str, Any]:
        """모니터링 사이클 실행"""
        start_time = time.time()
        
        try:
            logger.info(f"[MONITOR] 모니터링 사이클 시작 (모드: {self.mode})")
            
            # 1. 병렬 크롤링 실행
            logger.info("[MONITOR] 1단계: 사이트 크롤링 시작")
            crawled_data = await self.crawl_sites_parallel()
            
            # 2. 게시글 분류 및 필터링
            logger.info("[MONITOR] 2단계: 게시글 분류 시작")
            classified_data = self.classify_and_filter_posts(crawled_data)
            
            # 3. 알림 전송
            logger.info("[MONITOR] 3단계: 알림 전송 시작")
            notification_results = await self.send_notifications(classified_data)
            
            # 4. 실행 리포트 생성
            execution_time = time.time() - start_time
            report = self.generate_execution_report(crawled_data, classified_data, notification_results)
            report['performance_metrics']['total_execution_time'] = execution_time
            
            logger.info(f"[MONITOR] 모니터링 사이클 완료 (소요시간: {execution_time:.2f}초)")
            
            return report
            
        except Exception as e:
            logger.error(f"[MONITOR] 모니터링 사이클 실행 중 오류: {e}")
            raise


# 메인 실행 함수들
async def main_async(mode: str = "all") -> Dict[str, Any]:
    """비동기 메인 함수"""
    try:
        # 모니터링 시스템 초기화
        monitoring_system = Epic7MonitoringSystem(mode)
        
        # 모니터링 사이클 실행
        report = await monitoring_system.run_monitoring_cycle()
        
        return report
        
    except Exception as e:
        logger.error(f"[MAIN] 메인 실행 중 오류: {e}")
        raise


def main(mode: str = "all") -> Dict[str, Any]:
    """동기 메인 함수 (GitHub Actions 호환)"""
    try:
        # 비동기 이벤트 루프 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            report = loop.run_until_complete(main_async(mode))
            return report
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"[MAIN] 동기 메인 실행 중 오류: {e}")
        raise


if __name__ == "__main__":
    # 명령행 인수 처리
    parser = argparse.ArgumentParser(description='Epic7 모니터링 시스템')
    parser.add_argument('--mode', choices=['korean', 'global', 'all'], 
                      default='all', help='모니터링 모드')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    
    args = parser.parse_args()
    
    # 디버그 모드 설정
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("[DEBUG] 디버그 모드 활성화")
    
    try:
        # 메인 실행
        report = main(args.mode)
        
        # 결과 출력
        print("\n" + "="*50)
        print("Epic7 모니터링 시스템 실행 완료")
        print("="*50)
        print(f"실행 시간: {report['execution_time']}")
        print(f"모드: {report['mode']}")
        print(f"크롤링된 게시글: {report['crawling_summary']['total_posts']}개")
        print(f"버그 게시글: {report['classification_summary']['total']['bug_posts']}개")
        print(f"고우선순위 버그: {report['classification_summary']['total']['high_priority_bugs']}개")
        print(f"알림 전송: {'성공' if report['notification_summary']['bug_alerts_sent'] else '실패'}")
        print("="*50)
        
        # 성공 종료
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("[MAIN] 사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[MAIN] 실행 실패: {e}")
        sys.exit(1)