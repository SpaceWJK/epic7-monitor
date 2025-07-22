#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 모니터 v3.3 - 아키텍처 수정 완료본
크롤러와 분류기를 통합하는 실시간 모니터링 시스템

핵심 수정:
- 15분 주기: 통합 크롤링 + 분석 → 버그만 즉시 알림
- 30분 주기: 크롤링 없음 → 누적 감성 데이터 알림
- 중복 크롤링 완전 제거
- 감성 데이터 누적 저장 시스템 추가
- 24시간 일간 리포트는 generate_report.py에서 처리

Author: Epic7 Monitoring Team
Version: 3.3
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
# 감성 데이터 저장 설정
# =============================================================================

SENTIMENT_DATA_FILE = "sentiment_data_accumulated.json"
SENTIMENT_DATA_RETENTION_HOURS = 72  # 72시간 데이터 보존

# =============================================================================
# 모니터링 시스템 설정
# =============================================================================

class Epic7Monitor:
    """Epic7 통합 모니터링 시스템"""
    
    def __init__(self, mode: str = "unified", debug: bool = False, force_crawl: bool = False):
        """
        모니터링 시스템 초기화
        
        Args:
            mode: 실행 모드 ('unified', 'sentiment_alert', 'debug')
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
            'accumulated_sentiment_sent': 0,
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
        
        logger.info(f"Epic7 모니터링 시스템 v3.3 초기화 완료 - 모드: {mode}, force_crawl: {force_crawl}")
    
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
    
    def save_sentiment_data(self, sentiment_posts: List[Dict]) -> bool:
        """감성 분석 결과 누적 저장"""
        if not sentiment_posts:
            return True
            
        try:
            # 기존 데이터 로드
            accumulated_data = self.load_accumulated_sentiment_data()
            
            # 새로운 감성 데이터 추가
            current_time = datetime.now()
            for post in sentiment_posts:
                sentiment_entry = {
                    'timestamp': current_time.isoformat(),
                    'title': post.get('title', ''),
                    'url': post.get('url', ''),
                    'source': post.get('source', ''),
                    'classification': post.get('classification', {}),
                    'sentiment': post.get('classification', {}).get('sentiment_analysis', {}).get('sentiment', 'neutral'),
                    'confidence': post.get('classification', {}).get('sentiment_analysis', {}).get('confidence', 0.0),
                    'save_time': current_time.isoformat()
                }
                accumulated_data.append(sentiment_entry)
            
            # 72시간 이전 데이터 정리
            cutoff_time = current_time - timedelta(hours=SENTIMENT_DATA_RETENTION_HOURS)
            accumulated_data = [
                entry for entry in accumulated_data 
                if datetime.fromisoformat(entry['save_time']) > cutoff_time
            ]
            
            # 파일에 저장
            with open(SENTIMENT_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(accumulated_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 감성 데이터 저장 완료: {len(sentiment_posts)}개 추가, 총 {len(accumulated_data)}개 누적")
            return True
            
        except Exception as e:
            logger.error(f"감성 데이터 저장 실패: {e}")
            return False
    
    def load_accumulated_sentiment_data(self) -> List[Dict]:
        """누적된 감성 데이터 로드"""
        try:
            if os.path.exists(SENTIMENT_DATA_FILE):
                with open(SENTIMENT_DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 72시간 이전 데이터 필터링
                cutoff_time = datetime.now() - timedelta(hours=SENTIMENT_DATA_RETENTION_HOURS)
                filtered_data = [
                    entry for entry in data 
                    if datetime.fromisoformat(entry['save_time']) > cutoff_time
                ]
                
                logger.info(f"📊 누적 감성 데이터 로드: {len(filtered_data)}개")
                return filtered_data
            else:
                logger.info("📊 누적 감성 데이터 파일 없음 - 새로 시작")
                return []
                
        except Exception as e:
            logger.error(f"감성 데이터 로드 실패: {e}")
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
        """실시간 알림 전송 (버그만)"""
        if not alert_posts:
            logger.info("실시간 버그 알림: 전송할 게시글이 없습니다.")
            return True
        
        if not self.webhooks.get('bug'):
            logger.warning("실시간 버그 알림: Discord 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            logger.info(f"🚨 실시간 버그 알림 전송 시작: {len(alert_posts)}개 게시글")
            
            # 알림 전송
            success = send_bug_alert(alert_posts)
            
            if success:
                logger.info(f"🚨 실시간 버그 알림 전송 성공: {len(alert_posts)}개 게시글")
            else:
                logger.error("🚨 실시간 버그 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"실시간 버그 알림 전송 중 오류: {e}")
            return False
    
    def send_accumulated_sentiment_alerts(self) -> bool:
        """누적된 감성 데이터 알림 전송 (30분 주기)"""
        if not self.webhooks.get('sentiment'):
            logger.warning("감성 동향 알림: Discord 웹훅이 설정되지 않았습니다.")
            return False
        
        try:
            # 누적된 감성 데이터 로드
            accumulated_data = self.load_accumulated_sentiment_data()
            
            if not accumulated_data:
                logger.info("📊 감성 동향 알림: 누적된 감성 데이터가 없습니다.")
                return True
            
            # 최근 30분간 데이터만 필터링 (30분 주기 알림용)
            cutoff_time = datetime.now() - timedelta(minutes=30)
            recent_data = [
                entry for entry in accumulated_data
                if datetime.fromisoformat(entry['timestamp']) > cutoff_time
            ]
            
            if not recent_data:
                logger.info("📊 감성 동향 알림: 최근 30분간 새로운 감성 데이터가 없습니다.")
                return True
            
            logger.info(f"📊 감성 동향 알림 전송 시작: 최근 30분간 {len(recent_data)}개 데이터")
            
            # 감성 분석 요약
            sentiment_summary = self._create_accumulated_sentiment_summary(recent_data)
            
            # 알림 전송 (recent_data를 posts 형태로 변환)
            posts_for_notification = []
            for entry in recent_data:
                post_data = {
                    'title': entry['title'],
                    'url': entry['url'],
                    'source': entry['source'],
                    'classification': entry['classification'],
                    'timestamp': entry['timestamp']
                }
                posts_for_notification.append(post_data)
            
            success = send_sentiment_notification(posts_for_notification, sentiment_summary)
            
            if success:
                self.stats['accumulated_sentiment_sent'] = len(recent_data)
                logger.info(f"📊 감성 동향 알림 전송 성공: {len(recent_data)}개 데이터")
            else:
                logger.error("📊 감성 동향 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"감성 동향 알림 전송 중 오류: {e}")
            return False
    
    def _create_accumulated_sentiment_summary(self, data: List[Dict]) -> Dict:
        """누적된 감성 데이터 요약 생성"""
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for entry in data:
            sentiment = entry.get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
        
        return {
            'total_posts': len(data),
            'sentiment_distribution': sentiment_counts,
            'time_period': '최근 30분간',
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_execution_report(self) -> str:
        """실행 보고서 생성"""
        end_time = datetime.now()
        execution_time = end_time - self.start_time
        
        report = f"""
🎯 **Epic7 모니터링 실행 보고서 v3.3**

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
- 실시간 버그 알림: {self.stats['realtime_alerts']}개
- 감성 동향 알림: {self.stats['accumulated_sentiment_sent']}개
- 오류 발생: {self.stats['errors']}개

**아키텍처 정보**
- 15분 주기: {'통합 크롤링 + 버그 알림' if self.mode == 'unified' else 'N/A'}
- 30분 주기: {'감성 데이터 알림만' if self.mode == 'sentiment_alert' else 'N/A'}
- 중복 크롤링: 제거됨 ✅
- 감성 데이터 저장: 활성화됨 ✅

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
    
    def run_unified_monitoring(self) -> bool:
        """통합 모니터링 (15분 주기) - 전체 크롤링 + 버그만 즉시 알림"""
        try:
            logger.info("🚀 통합 모니터링 시작 (15분 주기) - 전체 크롤링 + 분석")
            
            # 전체 크롤링 (버그 + 일반 게시판 모두)
            posts = self._safe_crawl_execution(crawl_by_schedule, "통합 게시판 크롤링")
            self.stats['total_crawled'] = len(posts)
            
            if not posts:
                logger.info("통합 모니터링: 새로운 게시글이 없습니다.")
                return True
            
            # 게시글 분류
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(posts)
            
            # 1. 버그 관련 알림만 즉시 전송
            all_bug_alerts = realtime_alerts + [post for post in bug_posts if post not in realtime_alerts]
            
            if all_bug_alerts:
                self.send_realtime_alerts(all_bug_alerts)
                logger.info(f"🚨 통합 모니터링: 버그 알림 전송 완료 {len(all_bug_alerts)}개")
            
            # 2. 감성 분석 결과는 저장만 (알림 안함)
            if sentiment_posts:
                self.save_sentiment_data(sentiment_posts)
                logger.info(f"💾 통합 모니터링: 감성 데이터 저장 완료 {len(sentiment_posts)}개 (알림 없음)")
            
            logger.info("✅ 통합 모니터링 완료 - 버그 알림 전송 + 감성 데이터 저장")
            return True
            
        except Exception as e:
            logger.error(f"💥 통합 모니터링 실행 중 오류: {e}")
            return False
    
    def run_sentiment_alert_only(self) -> bool:
        """감성 알림 전용 (30분 주기) - 크롤링 없음, 누적 데이터만 알림"""
        try:
            logger.info("📊 감성 알림 전용 시작 (30분 주기) - 크롤링 없음, 누적 데이터 알림만")
            
            # 크롤링은 하지 않음! 누적된 감성 데이터만 알림
            self.stats['total_crawled'] = 0  # 크롤링 안함
            
            # 누적된 감성 데이터 알림 전송
            success = self.send_accumulated_sentiment_alerts()
            
            if success:
                logger.info("📊 감성 알림 전용 완료 - 누적 감성 데이터 알림 전송 완료")
            else:
                logger.info("📊 감성 알림 전용 완료 - 전송할 감성 데이터 없음")
            
            logger.info("✅ 감성 알림 전용 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 감성 알림 전용 실행 중 오류: {e}")
            return False
    
    def run_debug_mode(self) -> bool:
        """디버그 모드 실행"""
        try:
            logger.info("🔧 디버그 모드 시작")
            
            # 테스트 크롤링
            logger.info("테스트 크롤링 실행...")
            test_posts = self._safe_crawl_execution(crawl_by_schedule, "디버그 테스트 크롤링")
            
            self.stats['total_crawled'] = len(test_posts)
            
            if not test_posts:
                logger.info("디버그 테스트: 새로운 게시글이 없습니다.")
                return True
            
            # 테스트 분류
            logger.info("테스트 분류 실행...")
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(test_posts)
            
            # 디버그 정보 출력
            logger.info(f"디버그 결과:")
            logger.info(f"  - 총 게시글: {len(test_posts)}개")
            logger.info(f"  - 버그 게시글: {len(bug_posts)}개")
            logger.info(f"  - 감성 게시글: {len(sentiment_posts)}개")
            logger.info(f"  - 실시간 알림: {len(realtime_alerts)}개")
            
            # 감성 데이터 저장 테스트
            if sentiment_posts:
                logger.info("🔧 감성 데이터 저장 테스트...")
                save_success = self.save_sentiment_data(sentiment_posts)
                logger.info(f"🔧 감성 데이터 저장 테스트 결과: {'성공' if save_success else '실패'}")
            
            # 감성 데이터 로드 테스트
            logger.info("🔧 누적 감성 데이터 로드 테스트...")
            accumulated_data = self.load_accumulated_sentiment_data()
            logger.info(f"🔧 누적 감성 데이터: {len(accumulated_data)}개")
            
            # 샘플 출력
            if bug_posts:
                logger.info("버그 게시글 샘플:")
                for post in bug_posts[:3]:
                    classification = post.get('classification', {})
                    bug_priority = classification.get('bug_analysis', {}).get('priority', 'low')
                    logger.info(f"  - {post['title'][:50]}... (우선순위: {bug_priority})")
            
            # 디버그 모드에서도 알림 테스트 (소량)
            if realtime_alerts and self.webhooks.get('bug'):
                logger.info("🔧 디버그 모드 버그 알림 테스트 시작...")
                test_success = self.send_realtime_alerts(realtime_alerts[:2])  # 최대 2개만 테스트
                logger.info(f"🔧 디버그 모드 버그 알림 테스트 결과: {'성공' if test_success else '실패'}")
            
            # 감성 알림 테스트
            if accumulated_data and self.webhooks.get('sentiment'):
                logger.info("🔧 디버그 모드 감성 알림 테스트 시작...")
                test_sentiment_success = self.send_accumulated_sentiment_alerts()
                logger.info(f"🔧 디버그 모드 감성 알림 테스트 결과: {'성공' if test_sentiment_success else '실패'}")
            
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
            elif self.mode == "unified":
                success = self.run_unified_monitoring()  # 15분 주기
            elif self.mode == "sentiment_alert":
                success = self.run_sentiment_alert_only()  # 30분 주기
            else:
                # 기본값은 unified 모드
                logger.warning(f"알 수 없는 모드 '{self.mode}', unified 모드로 실행합니다.")
                success = self.run_unified_monitoring()
            
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
        description="Epic7 통합 모니터링 시스템 v3.3 (아키텍처 수정 완료본)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python monitor_bugs.py                        # 통합 모니터링 모드 (15분 주기)
  python monitor_bugs.py --mode unified         # 통합 모니터링 모드 (15분 주기)
  python monitor_bugs.py --mode sentiment_alert # 감성 알림 모드 (30분 주기)
  python monitor_bugs.py --debug                # 디버그 모드
  python monitor_bugs.py --force-crawl          # 강제 크롤링 모드
  python monitor_bugs.py --mode unified --force-crawl # 통합 모니터링 + 강제 크롤링

모드 설명:
  unified       : 15분 주기 - 전체 크롤링 + 분류 → 버그만 즉시 알림
  sentiment_alert: 30분 주기 - 크롤링 없음 → 누적 감성 데이터 알림
  debug         : 디버그 모드 - 모든 기능 테스트
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['unified', 'sentiment_alert', 'debug'],
        default='unified',
        help='실행 모드 (default: unified)'
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
        version='Epic7 Monitor v3.3 (Architecture Fixed)'
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