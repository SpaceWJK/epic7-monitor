#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 모니터 v3.1 - 메인 컨트롤러
크롤러와 분류기를 통합하는 실시간 모니터링 시스템

주요 특징:
- 15분/30분 주기별 실시간 모니터링
- 버그 우선순위 기반 즉시 알림
- 감성 분석 및 동향 추적
- 통합 파일 시스템 관리
- 디버깅 및 모니터링 모드

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_bugs.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# 모니터링 시스템 설정
# =============================================================================

class MonitoringConfig:
    """모니터링 시스템 설정"""
    
    # 모니터링 모드
    MONITORING_MODE = "monitoring"  # monitoring, debug
    
    # 실행 주기 설정
    FREQUENT_INTERVAL = 15  # 15분 간격 (버그 게시판)
    REGULAR_INTERVAL = 30   # 30분 간격 (일반 게시판)
    
    # 알림 설정
    REALTIME_ALERT_ENABLED = True
    BATCH_ALERT_ENABLED = True
    DAILY_REPORT_ENABLED = True
    
    # 성능 설정
    MAX_CONCURRENT_CRAWLS = 4
    CRAWL_TIMEOUT = 300  # 5분
    ALERT_TIMEOUT = 30   # 30초
    
    # 디버깅 설정
    DEBUG_MODE = False
    VERBOSE_LOGGING = False
    SAVE_DEBUG_FILES = True
    
    # 파일 경로
    LOG_FILE = "monitor_bugs.log"
    STATS_FILE = "monitoring_stats.json"
    DEBUG_DIR = "debug"

class Epic7Monitor:
    """Epic7 통합 모니터링 시스템"""
    
    def __init__(self, mode: str = "monitoring", debug: bool = False):
        """
        모니터링 시스템 초기화
        
        Args:
            mode: 실행 모드 ('monitoring', 'debug')
            debug: 디버그 모드 여부
        """
        self.mode = mode
        self.debug = debug
        self.start_time = datetime.now()
        self._shutdown_event = False
        
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
            'start_time': self.start_time.isoformat()
        }
        
        # 웹훅 확인
        self.webhooks = self._check_discord_webhooks()
        
        # 디버그 설정
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            MonitoringConfig.DEBUG_MODE = True
            MonitoringConfig.VERBOSE_LOGGING = True
        
        # 디버그 디렉토리 생성
        if MonitoringConfig.SAVE_DEBUG_FILES:
            os.makedirs(MonitoringConfig.DEBUG_DIR, exist_ok=True)
        
        # 시그널 핸들러 설정
        self._setup_signal_handlers()
        
        logger.info(f"Epic7 모니터링 시스템 v3.1 초기화 완료 - 모드: {mode}")
    
    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        def signal_handler(signum, frame):
            logger.info(f"종료 신호 수신 ({signum}), 정리 작업 시작...")
            self._shutdown_event = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
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
    
    def _send_discord_message(self, webhook_url: str, message: str, title: str = "Epic7 모니터링") -> bool:
        """Discord 메시지 전송"""
        if not webhook_url:
            logger.error("Discord 웹훅 URL이 없습니다.")
            return False
        
        try:
            import requests
            
            # 메시지 길이 제한
            if len(message) > 1900:
                message = message[:1900] + "\n...(메시지 길이 초과로 생략)"
            
            # Discord 웹훅 페이로드
            payload = {
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": 0x3498db,
                        "timestamp": datetime.now().isoformat(),
                        "footer": {
                            "text": "Epic7 모니터링 시스템 v3.1"
                        }
                    }
                ]
            }
            
            # 웹훅 전송
            response = requests.post(webhook_url, json=payload, timeout=MonitoringConfig.ALERT_TIMEOUT)
            if response.status_code == 204:
                logger.info("Discord 메시지 전송 성공")
                return True
            else:
                logger.error(f"Discord 메시지 전송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Discord 메시지 전송 중 오류: {e}")
            return False
    
    def _safe_crawl_execution(self, crawl_func, func_name: str, timeout: int = 300):
        """안전한 크롤링 실행 (타임아웃 및 예외 처리)"""
        try:
            logger.info(f"{func_name} 실행 시작...")
            
            # 타임아웃 설정으로 크롤링 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(crawl_func)
                try:
                    result = future.result(timeout=timeout)
                    logger.info(f"{func_name} 완료: {len(result) if result else 0}개 결과")
                    return result if result else []
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{func_name} 타임아웃 ({timeout}초)")
                    future.cancel()
                    return []
                except Exception as e:
                    logger.error(f"{func_name} 실행 중 오류: {e}")
                    return []
        
        except Exception as e:
            logger.error(f"{func_name} 실행 설정 중 오류: {e}")
            return []
    
    def classify_posts(self, posts: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """게시글 분류 및 처리"""
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
        
        self.stats['new_posts'] = len(posts)
        
        logger.info(f"분류 완료: 버그 {len(bug_posts)}개, 감성 {len(sentiment_posts)}개, 실시간 알림 {len(realtime_alerts)}개")
        
        return bug_posts, sentiment_posts, realtime_alerts
    
    def send_realtime_alerts(self, alert_posts: List[Dict]) -> bool:
        """실시간 알림 전송"""
        if not alert_posts or not self.webhooks.get('bug'):
            return False
        
        try:
            # 우선순위별 정렬
            alert_posts.sort(key=lambda x: x.get('classification', {}).get('realtime_alert', {}).get('alert_priority', 99))
            
            # 알림 메시지 생성
            alert_message = self._create_alert_message(alert_posts)
            
            # Discord 전송
            success = self._send_discord_message(
                self.webhooks['bug'],
                alert_message,
                "🚨 Epic7 실시간 알림"
            )
            
            if success:
                logger.info(f"실시간 알림 전송 성공: {len(alert_posts)}개 게시글")
            else:
                logger.error("실시간 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"실시간 알림 전송 중 오류: {e}")
            return False
    
    def _create_alert_message(self, posts: List[Dict]) -> str:
        """알림 메시지 생성"""
        if not posts:
            return "알림할 게시글이 없습니다."
        
        message_parts = []
        
        # 헤더
        message_parts.append(f"**🚨 Epic7 실시간 알림 ({len(posts)}개 게시글)**")
        message_parts.append(f"**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        message_parts.append("")
        
        # 게시글별 알림
        for i, post in enumerate(posts[:10], 1):  # 최대 10개만 표시
            classification = post.get('classification', {})
            
            # 기본 정보
            title = post.get('title', 'N/A')
            site = post.get('site', 'N/A')
            url = post.get('url', '')
            
            # 분류 정보
            category = classification.get('category', 'neutral')
            category_emoji = self.classifier.get_category_emoji(category)
            
            # 버그 정보
            bug_analysis = classification.get('bug_analysis', {})
            bug_priority = bug_analysis.get('priority', 'low')
            priority_emoji = self.classifier.get_priority_emoji(bug_priority)
            
            # 알림 정보
            alert_info = classification.get('realtime_alert', {})
            alert_reason = alert_info.get('alert_reason', 'unknown')
            
            # 메시지 구성
            message_parts.append(f"**{i}. {category_emoji} {title[:80]}**")
            message_parts.append(f"   📍 **사이트**: {site}")
            message_parts.append(f"   {priority_emoji} **우선순위**: {bug_priority}")
            message_parts.append(f"   🔔 **알림 사유**: {alert_reason}")
            if url:
                message_parts.append(f"   🔗 **링크**: {url}")
            message_parts.append("")
        
        # 더 많은 게시글이 있는 경우
        if len(posts) > 10:
            message_parts.append(f"... 외 {len(posts) - 10}개 게시글 더 있음")
        
        return "\n".join(message_parts)
    
    def send_batch_alerts(self, bug_posts: List[Dict], sentiment_posts: List[Dict]) -> bool:
        """배치 알림 전송 (감성 동향)"""
        if not sentiment_posts or not self.webhooks.get('sentiment'):
            return False
        
        try:
            # 감성 분석 결과 요약
            sentiment_summary = self._create_sentiment_summary(sentiment_posts)
            
            # Discord 전송
            success = self._send_discord_message(
                self.webhooks['sentiment'],
                sentiment_summary,
                "📊 Epic7 감성 동향"
            )
            
            if success:
                logger.info(f"감성 동향 알림 전송 성공: {len(sentiment_posts)}개 게시글")
            else:
                logger.error("감성 동향 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"감성 동향 알림 전송 중 오류: {e}")
            return False
    
    def _create_sentiment_summary(self, posts: List[Dict]) -> str:
        """감성 분석 요약 생성"""
        if not posts:
            return "분석할 게시글이 없습니다."
        
        # 감성별 분류
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        by_sentiment = {'positive': [], 'negative': [], 'neutral': []}
        
        for post in posts:
            sentiment = post.get('classification', {}).get('sentiment_analysis', {}).get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
            by_sentiment[sentiment].append(post)
        
        # 메시지 생성
        message_parts = []
        
        # 헤더
        message_parts.append(f"**📊 Epic7 감성 동향 분석 ({len(posts)}개 게시글)**")
        message_parts.append(f"**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        message_parts.append("")
        
        # 감성 분포
        message_parts.append("**감성 분포:**")
        total = len(posts)
        message_parts.append(f"😊 긍정: {sentiment_counts['positive']}개 ({sentiment_counts['positive']/total*100:.1f}%)")
        message_parts.append(f"😞 부정: {sentiment_counts['negative']}개 ({sentiment_counts['negative']/total*100:.1f}%)")
        message_parts.append(f"😐 중립: {sentiment_counts['neutral']}개 ({sentiment_counts['neutral']/total*100:.1f}%)")
        message_parts.append("")
        
        # 대표 게시글 (각 감성별 2개씩)
        for sentiment, emoji in [('positive', '😊'), ('negative', '😞'), ('neutral', '😐')]:
            sentiment_posts = by_sentiment[sentiment]
            if sentiment_posts:
                message_parts.append(f"**{emoji} {sentiment.title()} 게시글 예시:**")
                for post in sentiment_posts[:2]:
                    title = post.get('title', 'N/A')
                    site = post.get('site', 'N/A')
                    message_parts.append(f"   • {title[:60]}... ({site})")
                message_parts.append("")
        
        return "\n".join(message_parts)
    
    def save_monitoring_stats(self) -> bool:
        """모니터링 통계 저장"""
        try:
            # 실행 시간 계산
            end_time = datetime.now()
            execution_time = (end_time - self.start_time).total_seconds()
            
            # 통계 업데이트
            self.stats.update({
                'end_time': end_time.isoformat(),
                'execution_time': execution_time,
                'success_rate': (self.stats['total_crawled'] - self.stats['errors']) / max(1, self.stats['total_crawled']) * 100,
                'alert_rate': self.stats['realtime_alerts'] / max(1, self.stats['new_posts']) * 100,
                'bug_rate': self.stats['bug_posts'] / max(1, self.stats['new_posts']) * 100
            })
            
            # 파일 저장
            with open(MonitoringConfig.STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"모니터링 통계 저장 완료: {MonitoringConfig.STATS_FILE}")
            return True
            
        except Exception as e:
            logger.error(f"모니터링 통계 저장 실패: {e}")
            return False
    
    def generate_execution_report(self) -> str:
        """실행 보고서 생성"""
        end_time = datetime.now()
        execution_time = end_time - self.start_time
        
        report = f"""
🎯 **Epic7 모니터링 실행 보고서**

**실행 정보**
- 모드: {self.mode.upper()}
- 디버그 모드: {'On' if self.debug else 'Off'}
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
- 평균 처리 시간: {(execution_time.total_seconds() / max(1, self.stats['total_crawled'])):.2f}초/게시글

**시스템 상태**
- 활성 웹훅: {', '.join(self.webhooks.keys()) if self.webhooks else 'None'}
- 디스크 웹훅: {'설정됨' if self.webhooks else '미설정'}
- 로그 파일: {MonitoringConfig.LOG_FILE}
- 통계 파일: {MonitoringConfig.STATS_FILE}

**현재 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report.strip()
    
    def run_monitoring_cycle(self) -> bool:
        """모니터링 사이클 실행"""
        try:
            logger.info("🚀 모니터링 사이클 시작")
            
            # 1. 스케줄 기반 크롤링 (안전한 실행)
            posts = self._safe_crawl_execution(crawl_by_schedule, "스케줄 기반 크롤링", 300)
            self.stats['total_crawled'] = len(posts)
            
            if not posts:
                logger.info("새로운 게시글이 없습니다.")
                return True
            
            # 2. 게시글 분류
            bug_posts, sentiment_posts, realtime_alerts = self.classify_posts(posts)
            
            # 3. 실시간 알림 전송
            if realtime_alerts and MonitoringConfig.REALTIME_ALERT_ENABLED:
                self.send_realtime_alerts(realtime_alerts)
            
            # 4. 배치 알림 전송 (감성 동향)
            if sentiment_posts and MonitoringConfig.BATCH_ALERT_ENABLED:
                self.send_batch_alerts(bug_posts, sentiment_posts)
            
            # 5. 통계 저장
            self.save_monitoring_stats()
            
            logger.info("✅ 모니터링 사이클 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 모니터링 사이클 실행 중 오류: {e}")
            
            # 오류 알림
            if self.webhooks.get('bug'):
                error_message = f"""
🚨 **모니터링 시스템 오류**

**오류 내용**: {str(e)[:500]}...
**발생 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**모드**: {self.mode}
**디버그**: {self.debug}

시스템 점검이 필요합니다.
"""
                self._send_discord_message(
                    self.webhooks['bug'],
                    error_message,
                    "🚨 Epic7 모니터링 오류"
                )
            
            return False
    
    def run_debug_mode(self) -> bool:
        """디버그 모드 실행"""
        try:
            logger.info("🔧 디버그 모드 시작")
            
            # 테스트 크롤링 (안전한 실행)
            logger.info("테스트 크롤링 실행...")
            frequent_posts = self._safe_crawl_execution(crawl_frequent_sites, "15분 간격 크롤링", 180)
            regular_posts = self._safe_crawl_execution(crawl_regular_sites, "30분 간격 크롤링", 180)
            
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
            
            # 디버그 파일 저장
            if MonitoringConfig.SAVE_DEBUG_FILES:
                debug_file = os.path.join(MonitoringConfig.DEBUG_DIR, f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'posts': all_posts,
                        'stats': self.stats,
                        'timestamp': datetime.now().isoformat()
                    }, f, ensure_ascii=False, indent=2)
                logger.info(f"디버그 파일 저장: {debug_file}")
            
            logger.info("✅ 디버그 모드 완료")
            return True
            
        except Exception as e:
            logger.error(f"💥 디버그 모드 실행 중 오류: {e}")
            return False
    
    def run(self) -> bool:
        """메인 실행 함수"""
        try:
            logger.info(f"🎯 Epic7 모니터링 시스템 시작 - 모드: {self.mode}")
            
            # 모드별 실행
            if self.mode == "debug":
                success = self.run_debug_mode()
            else:
                success = self.run_monitoring_cycle()
            
            # 실행 보고서 생성
            report = self.generate_execution_report()
            
            # 디버그 모드에서는 항상 보고서 출력
            if self.debug:
                logger.info("실행 보고서:")
                logger.info(report)
            
            # 리포트 웹훅 전송
            if self.webhooks.get('report') and success:
                self._send_discord_message(
                    self.webhooks['report'],
                    report,
                    f"📋 Epic7 모니터링 보고서 - {self.mode.upper()}"
                )
            
            logger.info("🎉 Epic7 모니터링 시스템 실행 완료")
            return success
            
        except Exception as e:
            logger.error(f"💥 Epic7 모니터링 시스템 실행 중 치명적 오류: {e}")
            return False
        finally:
            # 정리 작업
            self._cleanup()
    
    def _cleanup(self):
        """정리 작업"""
        try:
            logger.info("시스템 정리 작업 시작...")
            
            # 활성 futures 정리
            if hasattr(self, '_active_futures'):
                for future in self._active_futures:
                    if not future.done():
                        future.cancel()
                        logger.debug("미완료 future 취소됨")
            
            # 통계 저장
            self.save_monitoring_stats()
            
            logger.info("시스템 정리 작업 완료")
            
        except Exception as e:
            logger.error(f"정리 작업 중 오류: {e}")

# =============================================================================
# 명령행 인터페이스
# =============================================================================

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Epic7 통합 모니터링 시스템 v3.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python monitor_bugs.py                    # 기본 모니터링 모드
  python monitor_bugs.py --debug            # 디버그 모드
  python monitor_bugs.py --mode debug       # 디버그 모드 (명시적)
  python monitor_bugs.py --verbose          # 상세 로그
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['monitoring', 'debug', 'korean', 'global', 'all'],
        default='monitoring',
        help='실행 모드 (default: monitoring)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )

    # 통합 구조 bug_monitor.yml에서 사용하는 파라미터
    parser.add_argument(
        '--force-crawl',
        action='store_true',
        help='Force crawl ignoring cache'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Epic7 Monitor v3.1'
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
        
        # 모니터링 시스템 초기화
        monitor = Epic7Monitor(mode=mode, debug=args.debug)
        
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
