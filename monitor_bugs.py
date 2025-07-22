#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 모니터 v3.2 - 주기 분리 완성본
크롤러와 분류기를 통합하는 실시간 모니터링 시스템

핵심 수정:
- bug_only/sentiment_only 모드 추가 (15분/30분 주기 분리)
- Force Crawl 옵션이 crawler.py에 제대로 전달됨
- 새 게시글 판별 로직 개선
- Discord 알림 정상화
- 에러 핸들링 강화
- 실행보고서 Discord 전송 제거 (일간 리포트 채널 정리)

Author: Epic7 Monitoring Team
Version: 3.2
Date: 2025-07-22
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
import signal

# 로컬 모듈 임포트
from crawler import (
    crawl_by_schedule,
    crawl_frequent_sites,
    crawl_regular_sites,
    get_all_posts_for_report    
)

from classifier import (
    Epic7Classifier,
    is_bug_post,
    is_high_priority_bug,
    extract_bug_severity,
    should_send_realtime_alert
)

from notifier import (
    send_bug_alert,
    send_sentiment_notification,
    send_daily_report,
    send_health_check
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# 모니터링 시스템 설정
# =============================================================================

class Epic7Monitor:
    """Epic7 통합 모니터링 시스템"""
    
    def __init__(self, mode: str = "monitoring", debug: bool = False, force_crawl: bool = False):
        """
        모니터링 시스템 초기화
        
        Args:
            mode: 실행 모드 ('monitoring', 'debug', 'bug_only', 'sentiment_only')
            debug: 디버그 모드 여부
            force_crawl: 강제 크롤링 여부
        """
        self.mode = mode
        self.debug = debug
        self.force_crawl = force_crawl
        self.start_time = datetime.now()
        
        # 컴포넌트 초기화
        self.classifier = Epic7Classifier()
        
        # 통계 초기화
        self.stats = {
            'total_crawled': 0,
            'new_posts': 0,
            'bug_posts': 0,
            'high_priority_bugs': 0,
            'realtime_alerts': 0,
            'sentiment_posts': 0,
            'errors': 0,
            'mode': mode,
            'debug': debug,
            'force_crawl': force_crawl,
            'start_time': self.start_time.isoformat()
        }
        
        # 웹훅 확인
        self.webhooks = self._check_discord_webhooks()
        
        # 디버그 설정
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Epic7 모니터링 시스템 v3.2 초기화 완료 - 모드: {mode}, force_crawl: {force_crawl}")
    
    def _check_discord_webhooks(self) -> Dict[str, str]:
        """Discord 웹훅 환경변수 확인"""
        webhooks = {}
        
        # 버그 알림 웹훅
        bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
        if bug_webhook:
            webhooks['bug'] = bug_webhook
            logger.info("Discord 버그 알림 웹훅 확인됨")
        
        # 감성 알림 웹훅
        sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
        if sentiment_webhook:
            webhooks['sentiment'] = sentiment_webhook
            logger.info("Discord 감성 알림 웹훅 확인됨")
        
        # 리포트 웹훅
        report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
        if report_webhook:
            webhooks['report'] = report_webhook
            logger.info("Discord 리포트 웹훅 확인됨")
        
        if not webhooks:
            logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다.")
        
        return webhooks
    
    def _safe_crawl_execution(self, crawl_func, func_name: str, *args, **kwargs):
        """안전한 크롤링 실행"""
        try:
            logger.info(f"{func_name} 실행 시작... (force_crawl={self.force_crawl})")
            
            # Force Crawl 파라미터 전달
            result = crawl_func(*args, force_crawl=self.force_crawl, **kwargs)
            
            logger.info(f"{func_name} 완료: {len(result) if result else 0}개 결과")
            return result if result else []
            
        except Exception as e:
            logger.error(f"{func_name} 실행 중 오류: {e}")
            return []
    
    def classify_posts(self, posts: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """게시글 분류 및 처리"""
        if not posts:
            logger.info("분류할 게시글이 없습니다.")
            return [], [], []
        
        logger.info(f"게시글 분류 시작: {len(posts)}개")
        
        bug_posts = []
        sentiment_posts = []
        realtime_alerts = []
        
        for post in posts:
            try:
                # 분류 실행
                classification = self.classifier.classify_post(post)
                
                # 분류 결과를 post에 추가
                post['classification'] = classification
                
                # 카테고리별 처리
                category = classification.get('category', 'neutral')
                
                if category == 'bug':
                    bug_posts.append(post)
                    self.stats['bug_posts'] += 1
                    
                    # 고우선순위 버그 체크
                    bug_priority = classification.get('bug_analysis', {}).get('priority', 'low')
                    if bug_priority in ['critical', 'high']:
                        self.stats['high_priority_bugs'] += 1
                        logger.warning(f"고우선순위 버그 발견: {post['title'][:50]}... (우선순위: {bug_priority})")
                else:
                    sentiment_posts.append(post)
                    self.stats['sentiment_posts'] += 1
                
                # 실시간 알림 대상 체크
                should_alert = classification.get('realtime_alert', {}).get('should_alert', False)
                if should_alert:
                    realtime_alerts.append(post)
                    self.stats['realtime_alerts'] += 1
                    
                    logger.info(f"실시간 알림 대상: {post['title'][:50]}... (사유: {classification.get('realtime_alert', {}).get('alert_reason', 'unknown')})")
                
            except Exception as e:
                logger.error(f"게시글 분류 실패: {e}")
                logger.error(f"   게시글: {post.get('title', 'N/A')}")
                self.stats['errors'] += 1
        
        # Force Crawl 모드에서는 모든 게시글을 새 게시글로 처리
        if self.force_crawl:
            self.stats['new_posts'] = len(posts)
            logger.info(f"🔥 Force Crawl 모드: {len(posts)}개 게시글을 모두 새 게시글로 처리")
        else:
            # 일반 모드에서는 실제 새 게시글만 카운트
            new_count = len([post for post in posts if not post.get('is_cached', False)])
            self.stats['new_posts'] = new_count
        
        logger.info(f"분류 완료: 버그 {len(bug_posts)}개, 감성 {len(sentiment_posts)}개, 실시간 알림 {len(realtime_alerts)}개")
        
        return bug_posts, sentiment_posts, realtime_alerts
    
    def send_realtime_alerts(self, alert_posts: List[Dict]) -> bool:
        """실시간 알림 전송"""
        if not alert_posts:
            logger.info("실시간 알림: 전송할 게시글이 없습니다.")
            return True
        
        if not self.webhooks.get('bug'):
            logger.warning("실시간 알림: Discord 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            logger.info(f"🚨 실시간 알림 전송 시작: {len(alert_posts)}개 게시글")
            
            # 알림 전송
            success = send_bug_alert(alert_posts)
            
            if success:
                logger.info(f"🚨 실시간 알림 전송 성공: {len(alert_posts)}개 게시글")
            else:
                logger.error("🚨 실시간 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"실시간 알림 전송 중 오류: {e}")
            return False
    
    def send_batch_alerts(self, bug_posts: List[Dict], sentiment_posts: List[Dict]) -> bool:
        """배치 알림 전송 (감성 동향)"""
        if not sentiment_posts or not self.webhooks.get('sentiment'):
            return False
        
        try:
            logger.info(f"📊 감성 동향 알림 전송 시작: {len(sentiment_posts)}개 게시글")
            
            # 감성 분석 요약
            sentiment_summary = self._create_sentiment_summary(sentiment_posts)
            
            # 알림 전송
            success = send_sentiment_notification(sentiment_posts, sentiment_summary)
            
            if success:
                logger.info(f"📊 감성 동향 알림 전송 성공: {len(sentiment_posts)}개 게시글")
            else:
                logger.error("📊 감성 동향 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"감성 동향 알림 전송 중 오류: {e}")
            return False
    
    def _create_sentiment_summary(self, posts: List[Dict]) -> Dict:
        """감성 분석 요약 생성"""
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for post in posts:
            sentiment = post.get('classification', {}).get('sentiment_analysis', {}).get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
        
        return {
            'total_posts': len(posts),
            'sentiment_distribution': sentiment_counts,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_execution_report(self) -> str:
        """실행 보고서 생성"""
        end_time = datetime.now()
        execution_time = end_time - self.start_time
        
        report = f"""
🎯 **Epic7 모니터링 실행 보고서**

**실행 정보**
- 모드: {self.mode.upper()}
- 디버그 모드: {'On' if self.debug else 'Off'}
- Force Crawl: {'On' if self.force_crawl else 'Off'}
- 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
- 실행 시간: {execution_time.total_seconds():.1f}초

**크롤링 결과**
- 총 크롤링 시도: {self.stats['total_crawled']}개
- 새 게시글 발견: {self.stats['new_posts']}개
- 버그 게시글: {self.stats['bug_posts']}개
- 고우선순위 버그: {self.stats['high_priority_bugs']}개
- 감성 게시글: {self.stats['sentiment_posts']}개
- 실시간 알림 전송: {self.stats['realtime_alerts']}개
- 오류 발생: {self.stats['errors']}개

**성능 지표**
- 성공률: {((self.stats['total_crawled'] - self.stats['errors']) / max(1, self.stats['total_crawled']) * 100):.1f}%
- 알림 비율: {(self.stats['realtime_alerts'] / max(1, self.stats['new_posts']) * 100):.1f}%
- 버그 비율: {(self.stats['bug_posts'] / max(1, self.stats['new_posts']) * 100):.1f}%

**시스템 상태**
- 활성 웹훅: {', '.join(self.webhooks.keys()) if self.webhooks else 'None'}
- Discord 웹훅: {'설정됨' if self.webhooks else '미설정'}

**현재 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report.strip()
    
    def run_monitoring_cycle(self) -> bool:
        """기본 모니터링 사이클 실행"""
        try:
            logger.info("🚀 기본 모니터링 사이클 시작")
            
            posts = self._safe_crawl_execution(crawl_by_schedule, "스케줄 기반 크롤링")
            self.stats['total_crawled'] = len(posts)
            
            if not posts:
                logger.info("새로운 게시글이 없습니다.")
                return True
            
            # 게시글 분류
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(posts)
            
            # 실시간 알림 전송
            if realtime_alerts:
                self.send_realtime_alerts(realtime_alerts)
            
            # 배치 알림 전송 (감성 동향)
            if sentiment_posts:
                self.send_batch_alerts(bug_posts, sentiment_posts)
            
            logger.info("✅ 기본 모니터링 사이클 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 기본 모니터링 사이클 실행 중 오류: {e}")
            return False
    
    def run_bug_only_mode(self) -> bool:
        """버그 전용 모니터링 (15분 주기)"""
        try:
            logger.info("🐛 버그 전용 모니터링 시작 (15분 주기)")
            
            # 버그 게시판만 크롤링
            posts = self._safe_crawl_execution(crawl_frequent_sites, "버그 게시판 크롤링")
            self.stats['total_crawled'] = len(posts)
            
            if not posts:
                logger.info("버그 게시판에 새로운 게시글이 없습니다.")
                return True
            
            # 게시글 분류
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(posts)
            
            # 버그 알림만 전송 (실시간 + 일반 게시판에서 버그로 분류된 것 포함)
            all_bug_alerts = realtime_alerts + [post for post in bug_posts if post not in realtime_alerts]
            
            if all_bug_alerts:
                self.send_realtime_alerts(all_bug_alerts)
                logger.info(f"🐛 버그 알림 전송 완료: {len(all_bug_alerts)}개")
            
            logger.info("✅ 버그 전용 모니터링 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 버그 전용 모니터링 실행 중 오류: {e}")
            return False
    
    def run_sentiment_only_mode(self) -> bool:
        """유저 동향 분석 전용 (30분 주기)"""
        try:
            logger.info("📊 유저 동향 분석 전용 시작 (30분 주기)")
            
            # 일반 게시판만 크롤링
            posts = self._safe_crawl_execution(crawl_regular_sites, "일반 게시판 크롤링")
            self.stats['total_crawled'] = len(posts)
            
            if not posts:
                logger.info("일반 게시판에 새로운 게시글이 없습니다.")
                return True
            
            # 게시글 분류
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(posts)
            
            # 일반 게시판에서 버그로 분류된 것은 즉시 버그 알림
            bug_from_sentiment = [post for post in bug_posts] + [post for post in realtime_alerts]
            if bug_from_sentiment:
                logger.info(f"📊 일반 게시판에서 버그 감지: {len(bug_from_sentiment)}개 → 즉시 버그 알림")
                self.send_realtime_alerts(bug_from_sentiment)
            
            # 유저 동향 알림 전송 (긍정/부정/중립)
            if sentiment_posts:
                self.send_batch_alerts(bug_posts, sentiment_posts)
                logger.info(f"📊 유저 동향 알림 전송 완료: {len(sentiment_posts)}개")
            
            logger.info("✅ 유저 동향 분석 전용 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 유저 동향 분석 전용 실행 중 오류: {e}")
            return False
    
    def run_debug_mode(self) -> bool:
        """디버그 모드 실행"""
        try:
            logger.info("🔧 디버그 모드 시작")
            
            # 테스트 크롤링
            logger.info("테스트 크롤링 실행...")
            frequent_posts = self._safe_crawl_execution(crawl_frequent_sites, "15분 간격 크롤링")
            regular_posts = self._safe_crawl_execution(crawl_regular_sites, "30분 간격 크롤링")
            
            all_posts = frequent_posts + regular_posts
            self.stats['total_crawled'] = len(all_posts)
            
            if not all_posts:
                logger.info("테스트 크롤링: 새로운 게시글이 없습니다.")
                return True
            
            # 테스트 분류
            logger.info("테스트 분류 실행...")
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(all_posts)
            
            # 디버그 정보 출력
            logger.info(f"디버그 결과:")
            logger.info(f"  - 총 게시글: {len(all_posts)}개")
            logger.info(f"  - 버그 게시글: {len(bug_posts)}개")
            logger.info(f"  - 감성 게시글: {len(sentiment_posts)}개")
            logger.info(f"  - 실시간 알림: {len(realtime_alerts)}개")
            
            # 샘플 출력
            if bug_posts:
                logger.info("버그 게시글 샘플:")
                for post in bug_posts[:3]:
                    classification = post.get('classification', {})
                    bug_priority = classification.get('bug_analysis', {}).get('priority', 'low')
                    logger.info(f"  - {post['title'][:50]}... (우선순위: {bug_priority})")
            
            # 디버그 모드에서도 알림 테스트
            if realtime_alerts and self.webhooks.get('bug'):
                logger.info("🔧 디버그 모드 알림 테스트 시작...")
                test_success = self.send_realtime_alerts(realtime_alerts[:3])  # 최대 3개만 테스트
                logger.info(f"🔧 디버그 모드 알림 테스트 결과: {'성공' if test_success else '실패'}")
            
            logger.info("✅ 디버그 모드 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 디버그 모드 실행 중 오류: {e}")
            return False
    
    def run(self) -> bool:
        """메인 실행 함수"""
        try:
            logger.info(f"🎯 Epic7 모니터링 시스템 시작 - 모드: {self.mode}, force_crawl: {self.force_crawl}")
            
            # 모드별 실행
            if self.mode == "debug":
                success = self.run_debug_mode()
            elif self.mode == "bug_only":
                success = self.run_bug_only_mode()
            elif self.mode == "sentiment_only":
                success = self.run_sentiment_only_mode()
            else:
                success = self.run_monitoring_cycle()
            
            # 실행 보고서 생성
            report = self.generate_execution_report()
            
            # 보고서 출력
            logger.info("실행 보고서:")
            logger.info(report)
            
            # 실행 보고서 Discord 전송 제거 (Master 요청에 따라)
            # 일간 리포트 채널은 24시간 주기 generate_report.py에서 생성하는 진짜 일간 리포트만 받아야 함
            logger.info("📋 실행 보고서 생성 완료 (Discord 전송 생략)")
            
            logger.info("🎉 Epic7 모니터링 시스템 실행 완료")
            return success
            
        except Exception as e:
            logger.error(f"💥 Epic7 모니터링 시스템 실행 중 치명적 오류: {e}")
            return False

# =============================================================================
# 명령행 인터페이스
# =============================================================================

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Epic7 통합 모니터링 시스템 v3.2 (주기 분리 완성본)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python monitor_bugs.py                      # 기본 모니터링 모드
  python monitor_bugs.py --debug              # 디버그 모드
  python monitor_bugs.py --mode bug_only      # 버그 전용 모드 (15분 주기)
  python monitor_bugs.py --mode sentiment_only # 유저 동향 전용 모드 (30분 주기)
  python monitor_bugs.py --force-crawl        # 강제 크롤링 모드
  python monitor_bugs.py --mode bug_only --force-crawl # 버그 전용 + 강제 크롤링
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['monitoring', 'debug', 'bug_only', 'sentiment_only'],
        default='monitoring',
        help='실행 모드 (default: monitoring)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화'
    )
    
    parser.add_argument(
        '--force-crawl',
        action='store_true',
        help='강제 크롤링 모드 (캐시 무시)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Epic7 Monitor v3.2 (Schedule Separated)'
    )
        
    return parser.parse_args()

def main():
    """메인 함수"""
    try:
        # 인자 파싱
        args = parse_arguments()
        
        # 모드 설정
        mode = "debug" if args.debug else args.mode
        
        # 로그 레벨 설정
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # 환경 변수 확인
        if not any(os.getenv(key) for key in ['DISCORD_WEBHOOK_BUG', 'DISCORD_WEBHOOK_SENTIMENT', 'DISCORD_WEBHOOK_REPORT']):
            logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다.")
            logger.warning("알림 기능이 제한될 수 있습니다.")
        
        # 모니터 초기화 및 실행
        monitor = Epic7Monitor(
            mode=mode, 
            debug=args.debug, 
            force_crawl=args.force_crawl
        )
        
        # 모니터링 실행
        success = monitor.run()
        
        # 종료 코드 반환
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링이 중단되었습니다.")
        sys.exit(130)
        
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()