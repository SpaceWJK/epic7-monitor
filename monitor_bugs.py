#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 모니터 v4.6 - Mode 분리 완성본
Master 요구사항: --mode 파라미터와 15분 주기 korea/global 분리 로직 추가

v4.6 핵심 추가사항:
- --mode 파라미터 지원 (korea/global/all) ✨NEW✨
- 15분 주기 스케줄 로직 구현 ✨NEW✨
- korea/global 모드별 크롤링 분리 ✨NEW✨
- 사이트별 독립 크롤링 함수 ✨NEW✨

v4.5 기존 기능 완전 보존:
- 에러 핸들링 고도화 및 관리자 알림 시스템 ✅
- 치명적 에러 자동 알림 ✅
- 에러 복구 전략 및 자동 복구 ✅
- 게시글별 즉시 처리 시스템 안정성 강화 ✅

Author: Epic7 Monitoring Team
Version: 4.6 (Mode 분리 완성본)
Date: 2025-07-28
Enhanced: --mode 파라미터, 15분 주기 korea/global 분리
Fixed: 데이터 검증, 의존성 안전화, json 처리, 중복 실행 방지 (Master 5단계 프로세스 완료)
"""

import os
import sys
import json
import argparse
import time
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
from pathlib import Path
import signal
import fcntl
import traceback
import psutil
import requests

# 🔧 수정 3: crawler 의존성 안전화 (try-except import 보호)
try:
    from crawler import (
        crawl_by_schedule,
        crawl_frequent_sites,
        crawl_regular_sites,
        get_all_posts_for_report,
        mark_as_processed
    )
    CRAWLER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"crawler 모듈 로드 실패: {e}")
    CRAWLER_AVAILABLE = False
    # 폴백 함수들 정의
    def crawl_by_schedule(*args, **kwargs):
        return []
    def crawl_frequent_sites(*args, **kwargs):
        return []
    def crawl_regular_sites(*args, **kwargs):
        return []
    def get_all_posts_for_report(*args, **kwargs):
        return []
    def mark_as_processed(*args, **kwargs):
        pass

try:
    from classifier import (
        Epic7Classifier,
        is_bug_post,
        is_high_priority_bug,
        extract_bug_severity,
        should_send_realtime_alert
    )
    CLASSIFIER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"classifier 모듈 로드 실패: {e}")
    CLASSIFIER_AVAILABLE = False
    # 폴백 클래스 정의
    class Epic7Classifier:
        def classify_post(self, post_data):
            return {
                'category': 'neutral',
                'sentiment_analysis': {'sentiment': 'neutral', 'confidence': 0.5}
            }

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
# v4.5 에러 관리 시스템 완전 보존
# =============================================================================

class ErrorType:
    """에러 유형 정의"""
    FILE_IO = "file_io"
    NETWORK = "network"
    MEMORY = "memory"
    IMPORT = "import"
    DATA_PARSING = "data_parsing"
    CLASSIFICATION = "classification"
    NOTIFICATION = "notification"
    CRAWLING = "crawling"
    CRITICAL = "critical"

class ErrorSeverity:
    """에러 심각도 정의"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class ErrorRecoveryStrategy:
    """에러 복구 전략 정의"""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ALERT_AND_CONTINUE = "alert_and_continue"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"

class ErrorManager:
    """고도화된 에러 관리 시스템 (v4.5 완전 보존)"""
    
    def __init__(self):
        self.error_stats = {
            'total_errors': 0,
            'by_type': {},
            'by_severity': {},
            'recovery_attempts': 0,
            'recovery_success': 0,
            'critical_alerts_sent': 0,
            'last_critical_alert': None,
            'start_time': datetime.now().isoformat()
        }
        self.critical_alert_cooldown = 300  # 5분 쿨다운
        self.max_recovery_attempts = 3
        
        # 에러 유형별 복구 전략
        self.recovery_strategies = {
            ErrorType.FILE_IO: ErrorRecoveryStrategy.RETRY,
            ErrorType.NETWORK: ErrorRecoveryStrategy.RETRY,
            ErrorType.MEMORY: ErrorRecoveryStrategy.FALLBACK,
            ErrorType.IMPORT: ErrorRecoveryStrategy.FALLBACK,
            ErrorType.DATA_PARSING: ErrorRecoveryStrategy.SKIP,
            ErrorType.CLASSIFICATION: ErrorRecoveryStrategy.SKIP,
            ErrorType.NOTIFICATION: ErrorRecoveryStrategy.ALERT_AND_CONTINUE,
            ErrorType.CRAWLING: ErrorRecoveryStrategy.RETRY,
            ErrorType.CRITICAL: ErrorRecoveryStrategy.EMERGENCY_SHUTDOWN
        }
        
        logger.info("✨ 고도화된 에러 관리 시스템 v4.5 초기화 완료")
    
    def handle_error(self, 
                      error: Exception, 
                      error_type: str, 
                      severity: int, 
                      context: Dict = None,
                      recovery_callback: Callable = None) -> bool:
        """통합 에러 핸들링 시스템 (v4.5 완전 보존)"""
        try:
            # 에러 통계 업데이트
            self._update_error_stats(error_type, severity)
            
            # 에러 상세 정보 로깅
            error_info = self._format_error_info(error, error_type, severity, context)
            
            if severity == ErrorSeverity.CRITICAL:
                logger.critical(error_info)
                self._send_critical_alert(error, error_type, context)
                
                if self.recovery_strategies.get(error_type) == ErrorRecoveryStrategy.EMERGENCY_SHUTDOWN:
                    logger.critical("🚨 치명적 에러로 인한 비상 종료 시작")
                    return False
                    
            elif severity == ErrorSeverity.HIGH:
                logger.error(error_info)
                self._send_high_priority_alert(error, error_type, context)
            elif severity == ErrorSeverity.MEDIUM:
                logger.warning(error_info)
            else:
                logger.info(error_info)
            
            # 복구 시도
            recovery_success = self._attempt_recovery(error, error_type, recovery_callback)
            
            return recovery_success
            
        except Exception as e:
            logger.critical(f"💥 에러 핸들러 자체에서 오류 발생: {e}")
            return False
    
    def _update_error_stats(self, error_type: str, severity: int):
        """에러 통계 업데이트"""
        self.error_stats['total_errors'] += 1
        
        if error_type not in self.error_stats['by_type']:
            self.error_stats['by_type'][error_type] = 0
        self.error_stats['by_type'][error_type] += 1
        
        if severity not in self.error_stats['by_severity']:
            self.error_stats['by_severity'][severity] = 0
        self.error_stats['by_severity'][severity] += 1
    
    def _format_error_info(self, error: Exception, error_type: str, severity: int, context: Dict = None) -> str:
        """에러 정보 포맷팅"""
        severity_labels = {
            ErrorSeverity.LOW: "🟢 LOW",
            ErrorSeverity.MEDIUM: "🟡 MEDIUM",
            ErrorSeverity.HIGH: "🟠 HIGH",
            ErrorSeverity.CRITICAL: "🔴 CRITICAL"
        }
        
        error_info = f"""
⚠️ 에러 발생 상세 정보:
- 유형: {error_type}
- 심각도: {severity_labels.get(severity, 'UNKNOWN')}
- 메시지: {str(error)}
- 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 스택 트레이스: {traceback.format_exc()}
"""
        
        if context:
            error_info += f"- 컨텍스트: {json.dumps(context, ensure_ascii=False, indent=2)}"
        
        return error_info.strip()
    
    def _send_critical_alert(self, error: Exception, error_type: str, context: Dict = None):
        """치명적 에러 자동 알림 (v4.5 완전 보존)"""
        try:
            if self._is_alert_cooldown():
                logger.warning("치명적 에러 알림이 쿨다운 중입니다")
                return
            
            critical_webhook = os.environ.get('DISCORD_WEBHOOK_CRITICAL_ERROR')
            if not critical_webhook:
                logger.error("치명적 에러 웹훅이 설정되지 않았습니다")
                return
            
            system_info = self._get_system_info()
            
            alert_message = {
                "username": "Epic7 Critical Alert",
                "avatar_url": "https://cdn.discordapp.com/emojis/1234567890123456789.png",
                "embeds": [{
                    "title": "🚨 Epic7 모니터링 시스템 치명적 오류",
                    "description": f"**에러 유형:** {error_type}\\n**에러 메시지:** {str(error)}",
                    "color": 16711680,
                    "fields": [
                        {
                            "name": "🕐 발생 시간",
                            "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "inline": True
                        },
                        {
                            "name": "💻 시스템 상태",
                            "value": system_info,
                            "inline": True
                        },
                        {
                            "name": "📊 에러 통계",
                            "value": f"총 에러: {self.error_stats['total_errors']}개\\n치명적 알림: {self.error_stats['critical_alerts_sent']}개",
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": "Epic7 Critical Error Alert System v4.6"
                    },
                    "timestamp": datetime.now().isoformat()
                }]
            }
            
            if context:
                alert_message["embeds"][0]["fields"].append({
                    "name": "📋 컨텍스트",
                    "value": f"```json\\n{json.dumps(context, ensure_ascii=False, indent=2)[:500]}```",
                    "inline": False
                })
            
            response = requests.post(
                critical_webhook,
                json=alert_message,
                timeout=10
            )
            
            if response.status_code == 204:
                self.error_stats['critical_alerts_sent'] += 1
                self.error_stats['last_critical_alert'] = datetime.now().isoformat()
                logger.info("🚨 치명적 에러 알림 전송 성공")
            else:
                logger.error(f"치명적 에러 알림 전송 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"치명적 에러 알림 전송 중 오류: {e}")
    
    def _send_high_priority_alert(self, error: Exception, error_type: str, context: Dict = None):
        """높은 우선순위 에러 알림"""
        try:
            bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
            if not bug_webhook:
                return
            
            alert_message = {
                "username": "Epic7 High Priority Alert",
                "content": f"⚠️ **높은 우선순위 에러 발생**\\n에러 유형: {error_type}\\n메시지: {str(error)[:200]}..."
            }
            
            requests.post(bug_webhook, json=alert_message, timeout=5)
            logger.info("⚠️ 높은 우선순위 에러 알림 전송 완료")
            
        except Exception as e:
            logger.error(f"높은 우선순위 에러 알림 전송 실패: {e}")
    
    def _is_alert_cooldown(self) -> bool:
        """알림 쿨다운 체크"""
        if not self.error_stats['last_critical_alert']:
            return False
        
        last_alert = datetime.fromisoformat(self.error_stats['last_critical_alert'])
        return (datetime.now() - last_alert).total_seconds() < self.critical_alert_cooldown
    
    def _get_system_info(self) -> str:
        """시스템 상태 정보 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return f"CPU: {cpu_percent}%\\nMEM: {memory.percent}%\\nDISK: {disk.percent}%"
        except:
            return "시스템 정보 수집 실패"
    
    def _attempt_recovery(self, error: Exception, error_type: str, recovery_callback: Callable = None) -> bool:
        """에러 복구 시도 (v4.5 완전 보존)"""
        try:
            self.error_stats['recovery_attempts'] += 1
            
            strategy = self.recovery_strategies.get(error_type, ErrorRecoveryStrategy.SKIP)
            
            if strategy == ErrorRecoveryStrategy.RETRY:
                return self._retry_recovery(error, error_type, recovery_callback)
            elif strategy == ErrorRecoveryStrategy.FALLBACK:
                return self._fallback_recovery(error, error_type)
            elif strategy == ErrorRecoveryStrategy.SKIP:
                logger.info(f"에러 복구: {error_type} 건너뛰기")
                return True
            elif strategy == ErrorRecoveryStrategy.ALERT_AND_CONTINUE:
                logger.warning(f"에러 복구: {error_type} 알림 후 계속 진행")
                return True
            else:
                logger.error(f"에러 복구: {error_type} 복구 불가")
                return False
                
        except Exception as e:
            logger.error(f"에러 복구 시도 중 오류: {e}")
            return False
    
    def _retry_recovery(self, error: Exception, error_type: str, recovery_callback: Callable = None) -> bool:
        """재시도 복구 전략"""
        for attempt in range(self.max_recovery_attempts):
            try:
                logger.info(f"에러 복구 재시도 {attempt + 1}/{self.max_recovery_attempts}: {error_type}")
                
                if attempt > 0:
                    wait_time = 2 ** attempt
                    logger.info(f"재시도 전 대기: {wait_time}초")
                    time.sleep(wait_time)
                
                if error_type == ErrorType.FILE_IO:
                    self._recover_file_io()
                elif error_type == ErrorType.NETWORK:
                    self._recover_network()
                elif error_type == ErrorType.CRAWLING:
                    self._recover_crawling()
                
                if recovery_callback:
                    recovery_callback()
                
                logger.info(f"에러 복구 성공: {error_type}")
                self.error_stats['recovery_success'] += 1
                return True
                
            except Exception as e:
                logger.warning(f"재시도 {attempt + 1} 실패: {e}")
                continue
        
        logger.error(f"에러 복구 실패: {error_type} (모든 재시도 실패)")
        return False
    
    def _fallback_recovery(self, error: Exception, error_type: str) -> bool:
        """폴백 복구 전략"""
        try:
            logger.info(f"폴백 복구 시도: {error_type}")
            
            if error_type == ErrorType.MEMORY:
                self._cleanup_memory()
            elif error_type == ErrorType.IMPORT:
                self._use_alternative_import()
            
            self.error_stats['recovery_success'] += 1
            return True
            
        except Exception as e:
            logger.error(f"폴백 복구 실패: {e}")
            return False
    
    def _recover_file_io(self):
        """파일 I/O 복구"""
        data_files = [
            "epic7_monitor_execution.lock",
            "epic7_monitor_retry_queue.json",
            "daily_sentiment_data.json"
        ]
        
        for file_path in data_files:
            if os.path.exists(file_path):
                os.chmod(file_path, 0o644)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_path.endswith('.json'):
                        json.dump([], f)
                    else:
                        f.write('')
    
    def _recover_network(self):
        """네트워크 복구"""
        try:
            requests.get('https://www.google.com', timeout=5)
            logger.info("네트워크 연결 복구 확인")
        except:
            raise Exception("네트워크 연결 복구 실패")
    
    def _recover_crawling(self):
        """크롤링 복구"""
        cache_files = ["crawled_links.json", "content_cache.json"]
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if len(data) > 500:
                            data = data[-500:]
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                except:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump([], f)
    
    def _cleanup_memory(self):
        """메모리 정리"""
        import gc
        gc.collect()
        logger.info("메모리 정리 완료")
    
    def _use_alternative_import(self):
        """대안 임포트 사용"""
        logger.info("대안 임포트 방식 사용")
    
    def get_error_report(self) -> str:
        """에러 통계 보고서 생성"""
        return f"""
✨ Epic7 에러 관리 시스템 v4.6 통계 보고서

📊 전체 통계:
- 총 에러 발생: {self.error_stats['total_errors']}개
- 복구 시도: {self.error_stats['recovery_attempts']}개
- 복구 성공: {self.error_stats['recovery_success']}개
- 복구 성공률: {(self.error_stats['recovery_success'] / max(1, self.error_stats['recovery_attempts']) * 100):.1f}%

🔥 에러 유형별 통계:
{chr(10).join([f"- {error_type}: {count}개" for error_type, count in self.error_stats['by_type'].items()])}

⚠️ 심각도별 통계:
{chr(10).join([f"- {severity}: {count}개" for severity, count in self.error_stats['by_severity'].items()])}

🚨 치명적 알림:
- 전송된 치명적 알림: {self.error_stats['critical_alerts_sent']}개
- 마지막 치명적 알림: {self.error_stats['last_critical_alert'] or 'None'}

시작 시간: {self.error_stats['start_time']}
""".strip()

# 전역 에러 매니저 인스턴스 (v4.5 완전 보존)
error_manager = ErrorManager()

# =============================================================================
# 실행 상태 관리 (v4.5 완전 보존)
# =============================================================================

EXECUTION_LOCK_FILE = "epic7_monitor_execution.lock"
RETRY_QUEUE_FILE = "epic7_monitor_retry_queue.json"

MAX_RETRY_QUEUE_SIZE = 1000
RETRY_QUEUE_CLEANUP_THRESHOLD = 800
RETRY_QUEUE_CLEANUP_HOURS = 24

class ExecutionManager:
    """실행 상태 관리자 (v4.5 완전 보존)"""
    
    @staticmethod
    def is_running() -> bool:
        """실행 중인지 확인"""
        if not os.path.exists(EXECUTION_LOCK_FILE):
            return False
        
        try:
            with open(EXECUTION_LOCK_FILE, 'r') as f:
                lock_data = json.load(f)
                start_time = datetime.fromisoformat(lock_data['start_time'])
                
                if datetime.now() - start_time > timedelta(hours=2):
                    logger.warning("실행 락이 2시간 이상 유지됨 - 비정상 종료로 간주하여 락 해제")
                    ExecutionManager.release_lock()
                    return False
                
                return True
        except Exception as e:
            error_manager.handle_error(e, ErrorType.FILE_IO, ErrorSeverity.MEDIUM, 
                                     {'function': 'ExecutionManager.is_running'})
            return False
    
    @staticmethod
    def acquire_lock() -> bool:
        """실행 락 획득"""
        try:
            if ExecutionManager.is_running():
                return False
            
            lock_data = {
                'start_time': datetime.now().isoformat(),
                'pid': os.getpid()
            }
            
            with open(EXECUTION_LOCK_FILE, 'w') as f:
                json.dump(lock_data, f, indent=2)
            
            logger.info("실행 락 획득 성공")
            return True
        except Exception as e:
            error_manager.handle_error(e, ErrorType.FILE_IO, ErrorSeverity.HIGH, 
                                     {'function': 'ExecutionManager.acquire_lock'})
            return False
    
    @staticmethod
    def release_lock():
        """실행 락 해제"""
        try:
            if os.path.exists(EXECUTION_LOCK_FILE):
                os.remove(EXECUTION_LOCK_FILE)
                logger.info("실행 락 해제 완료")
        except Exception as e:
            error_manager.handle_error(e, ErrorType.FILE_IO, ErrorSeverity.MEDIUM, 
                                     {'function': 'ExecutionManager.release_lock'})

# =============================================================================
# ✨ NEW v4.6: 인자 파싱 - --mode 파라미터 추가
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """✨ v4.6: --mode 파라미터 추가된 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Epic7 통합 모니터링 시스템 v4.6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 한국 사이트만 15분 주기 모니터링
  python monitor_bugs.py --schedule 15min --mode korea
  
  # 글로벌 사이트만 15분 주기 모니터링
  python monitor_bugs.py --schedule 15min --mode global
  
  # 모든 사이트 15분 주기 모니터링 (기본값)
  python monitor_bugs.py --schedule 15min --mode all
  
  # 기존 30분 주기 통합 모니터링 (하위 호환성)
  python monitor_bugs.py --schedule 30min
  
  # 24시간 일간 리포트
  python monitor_bugs.py --schedule 24h
        """
    )
    
    # 기존 파라미터들 (v4.5 완전 보존)
    parser.add_argument(
        '--schedule', 
        choices=['15min', '30min', '24h'], 
        default='15min',
        help='실행 스케줄 (15min: 15분 주기, 30min: 30분 주기, 24h: 24시간 리포트)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='디버그 모드 활성화'
    )
    
    parser.add_argument(
        '--force-crawl', 
        action='store_true',
        help='강제 크롤링 (캐시 무시)'
    )
    
    # ✨ NEW v4.6: --mode 파라미터 추가
    parser.add_argument(
        '--mode', 
        choices=['korea', 'global', 'all'], 
        default='all',
        help='크롤링 모드 (korea: 한국 사이트만, global: 글로벌 사이트만, all: 모든 사이트)'
    )
    
    return parser.parse_args()

# =============================================================================
# Epic7 통합 모니터 v4.6 - Mode 분리 완성본
# =============================================================================

class Epic7Monitor:
    """Epic7 통합 모니터링 시스템 v4.6 - Mode 분리 완성본"""
    
    def __init__(self, mode: str = "all", schedule: str = "15min", debug: bool = False, force_crawl: bool = False):
        """모니터링 시스템 초기화 (v4.6: mode 파라미터 추가)"""
        self.mode = mode  # ✨ NEW v4.6
        self.schedule = schedule
        self.debug = debug
        self.force_crawl = force_crawl
        self.start_time = datetime.now()
        
        # 컴포넌트 초기화
        if CLASSIFIER_AVAILABLE:
            self.classifier = Epic7Classifier()
        else:
            self.classifier = Epic7Classifier()  # 폴백 클래스 사용
        self.error_manager = error_manager
        
        # 통계 초기화 (v4.5 기존 + v4.6 확장)
        self.stats = {
            'total_crawled': 0,
            'new_posts': 0,
            'bug_posts': 0,
            'sentiment_posts': 0,
            'immediate_bug_alerts': 0,
            'immediate_sentiment_alerts': 0,
            'processed_posts': 0,
            'failed_posts': 0,
            'retry_processed': 0,
            'sentiment_save_success': 0,
            'sentiment_save_failed': 0,
            'errors': 0,
            'error_recoveries': 0,
            'critical_alerts': 0,
            'high_priority_alerts': 0,
            # ✨ NEW v4.6: 모드별 통계
            'mode': mode,
            'korea_sites_crawled': 0,
            'global_sites_crawled': 0,
            'schedule': schedule,
            'debug': debug,
            'force_crawl': force_crawl,
            'start_time': self.start_time.isoformat()
        }
        
        # 웹훅 확인
        self.webhooks = self._check_discord_webhooks()
        
        # 디버그 설정
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Epic7 모니터링 시스템 v4.6 초기화 완료 - Mode 분리 (모드: {mode}, 스케줄: {schedule})")
    
    def _check_discord_webhooks(self) -> Dict[str, str]:
        """Discord 웹훅 환경변수 확인 (v4.5 완전 보존)"""
        webhooks = {}
        
        try:
            bug_webhook = os.environ.get('DISCORD_WEBHOOK_BUG')
            if bug_webhook:
                webhooks['bug'] = bug_webhook
                logger.info("Discord 버그 알림 웹훅 확인됨")
            
            sentiment_webhook = os.environ.get('DISCORD_WEBHOOK_SENTIMENT')
            if sentiment_webhook:
                webhooks['sentiment'] = sentiment_webhook
                logger.info("Discord 감성 알림 웹훅 확인됨")
            
            report_webhook = os.environ.get('DISCORD_WEBHOOK_REPORT')
            if report_webhook:
                webhooks['report'] = report_webhook
                logger.info("Discord 리포트 웹훅 확인됨")
            
            critical_webhook = os.environ.get('DISCORD_WEBHOOK_CRITICAL_ERROR')
            if critical_webhook:
                webhooks['critical'] = critical_webhook
                logger.info("Discord 치명적 에러 웹훅 확인됨")
            else:
                logger.warning("Discord 치명적 에러 웹훅이 설정되지 않았습니다 (DISCORD_WEBHOOK_CRITICAL_ERROR)")
            
            if not webhooks:
                logger.warning("Discord 웹훅 환경변수가 설정되지 않았습니다.")
            
            return webhooks
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.IMPORT, ErrorSeverity.MEDIUM, 
                                          {'function': '_check_discord_webhooks'})
            return {}

    def _crawl_site(self, site: str) -> List[Dict]:
        """✨ v4.6: 개별 사이트 크롤링 (사이트별 함수 호출)"""
        try:
            if not CRAWLER_AVAILABLE:
                logger.warning(f"crawler 모듈 사용 불가 - {site} 건너뛰기")
                return []
                
            # 사이트별 크롤링 함수 매핑
            site_crawlers = {
                'stove_korea_bug': lambda: crawl_by_schedule('stove_korea_bug', False, 'korea'),
                'stove_korea_general': lambda: crawl_by_schedule('stove_korea_general', False, 'korea'),
                'stove_global_bug': lambda: crawl_by_schedule('stove_global_bug', False, 'global'),
                'stove_global_general': lambda: crawl_by_schedule('stove_global_general', False, 'global'),
                'ruliweb_epic7': lambda: crawl_by_schedule('ruliweb_epic7', False, 'korea'),
                'reddit_epicseven': lambda: crawl_by_schedule('reddit_epicseven', False, 'global')
            }
        
            if site not in site_crawlers:
                logger.error(f"지원하지 않는 사이트: {site}")
                return []
        
            # 크롤링 실행
            crawler_func = site_crawlers[site]
            posts = crawler_func()
        
            return posts if posts else []
        
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.MEDIUM, 
                                          {'site': site})
            return []

    # =============================================================================
    # ✨ NEW v4.6: 15분 주기 모드별 분리 로직
    # =============================================================================
    
    def run_15min_crawling_and_bug_alert(self) -> bool:
        """✨ v4.6: 15분 주기 크롤링 및 버그 알림 (모드별 분리)"""
        try:
            logger.info(f"15분 주기 크롤링 시작 - 모드: {self.mode}")
            
            if self.mode == 'korea':
                return self._crawl_korea_sites_only()
            elif self.mode == 'global':
                return self._crawl_global_sites_only()
            elif self.mode == 'all':
                return self._crawl_all_sites()
            else:
                logger.error(f"지원하지 않는 모드: {self.mode}")
                return False
                
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRITICAL, ErrorSeverity.HIGH, 
                                          {'function': 'run_15min_crawling_and_bug_alert', 'mode': self.mode})
            return False
    
    def _crawl_korea_sites_only(self) -> bool:
        """✨ v4.6: 한국 사이트만 크롤링"""
        try:
            logger.info("🇰🇷 한국 사이트 전용 크롤링 시작")
            
            # 한국 사이트 목록
            korea_sites = [
                'stove_korea_bug',      # 스토브 한국 버그 게시판
                'stove_korea_general',  # 스토브 한국 자유 게시판
                'ruliweb_epic7'         # 루리웹 에픽세븐
            ]
            
            total_success = True
            
            for site in korea_sites:
                try:
                    logger.info(f"🕷️ {site} 크롤링 시작")
                    
                    # 사이트별 크롤링 실행
                    posts = self._crawl_site(site)
                    
                    if posts:
                        # 게시글별 즉시 처리
                        for post in posts:
                            self.process_post_immediately(post)
                        
                        self.stats['korea_sites_crawled'] += len(posts)
                        logger.info(f"✅ {site} 크롤링 완료: {len(posts)}개 게시글")
                    else:
                        logger.info(f"📭 {site} 새로운 게시글 없음")
                        
                except Exception as e:
                    self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.MEDIUM, 
                                                  {'site': site, 'mode': 'korea'})
                    total_success = False
                    continue
            
            logger.info(f"🇰🇷 한국 사이트 크롤링 완료 - 총 {self.stats['korea_sites_crawled']}개 게시글")
            return total_success
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.HIGH, 
                                          {'function': '_crawl_korea_sites_only'})
            return False
    
    def _crawl_global_sites_only(self) -> bool:
        """✨ v4.6: 글로벌 사이트만 크롤링"""
        try:
            logger.info("🌐 글로벌 사이트 전용 크롤링 시작")
            
            # 글로벌 사이트 목록
            global_sites = [
                'stove_global_bug',      # 스토브 글로벌 버그 게시판
                'stove_global_general',  # 스토브 글로벌 자유 게시판
                'reddit_epicseven'       # Reddit r/EpicSeven
            ]
            
            total_success = True
            
            for site in global_sites:
                try:
                    logger.info(f"🕷️ {site} 크롤링 시작")
                    
                    # 사이트별 크롤링 실행
                    posts = self._crawl_site(site)
                    
                    if posts:
                        # 게시글별 즉시 처리
                        for post in posts:
                            self.process_post_immediately(post)
                        
                        self.stats['global_sites_crawled'] += len(posts)
                        logger.info(f"✅ {site} 크롤링 완료: {len(posts)}개 게시글")
                    else:
                        logger.info(f"📭 {site} 새로운 게시글 없음")
                        
                except Exception as e:
                    self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.MEDIUM, 
                                                  {'site': site, 'mode': 'global'})
                    total_success = False
                    continue
            
            logger.info(f"🌐 글로벌 사이트 크롤링 완료 - 총 {self.stats['global_sites_crawled']}개 게시글")
            return total_success
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.HIGH, 
                                          {'function': '_crawl_global_sites_only'})
            return False
    
    def _crawl_all_sites(self) -> bool:
        """✨ v4.6: 모든 사이트 크롤링 (기존 방식 유지)"""
        try:
            logger.info("🌏 전체 사이트 통합 크롤링 시작")
            
            # 한국 + 글로벌 사이트 순차 실행
            korea_success = self._crawl_korea_sites_only()
            global_success = self._crawl_global_sites_only()
            
            total_posts = self.stats['korea_sites_crawled'] + self.stats['global_sites_crawled']
            logger.info(f"🌏 전체 사이트 크롤링 완료 - 총 {total_posts}개 게시글")
            
            return korea_success and global_success
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRAWLING, ErrorSeverity.HIGH, 
                                          {'function': '_crawl_all_sites'})
            return False
    
    # =============================================================================
    # 기존 v4.5 기능들 완전 보존
    # =============================================================================
    
    def process_post_immediately(self, post_data: Dict) -> bool:
        """게시글별 즉시 처리 콜백 함수 - v4.5 완전 보존 + 🔧 수정 2: 데이터 검증 강화"""
        try:
            self.stats['total_crawled'] += 1
            
            # 🔧 수정 2: 강화된 데이터 유효성 검증
            if not post_data or not isinstance(post_data, dict):
                raise ValueError("유효하지 않은 post_data 구조")
            
            # 필수 필드 존재 확인
            required_fields = ['title', 'content', 'url', 'source']
            for field in required_fields:
                if field not in post_data:
                    logger.warning(f"필수 필드 누락: {field}, 기본값 설정")
                    post_data[field] = ''
            
            # 타입 검증 및 안전화
            title = str(post_data.get('title', '')).strip()
            content = str(post_data.get('content', '')).strip()
            url = str(post_data.get('url', '')).strip()
            source = str(post_data.get('source', '')).strip()
            
            if not title and not content:
                raise ValueError("제목과 내용이 모두 비어있는 게시글")
            
            # 1. 감성 분석
            logger.info(f"[IMMEDIATE] 즉시 처리 시작: {title[:50]}...")
            
            try:
                classification = self.classifier.classify_post(post_data)
                post_data['classification'] = classification
            except Exception as e:
                recovery_success = self.error_manager.handle_error(
                    e, ErrorType.CLASSIFICATION, ErrorSeverity.MEDIUM, 
                    {'post_title': title[:50], 'post_url': url}
                )
                if not recovery_success:
                    raise Exception(f"감성 분석 실패: {e}")
            
            # 2. 알림 전송
            category = classification.get('category', 'neutral')
            
            if source.endswith('_bug') or category == 'bug' or classification.get('realtime_alert', {}).get('should_alert', False):
                # 버그 알림
                success = self._send_immediate_bug_alert(post_data)
                if success:
                    self.stats['immediate_bug_alerts'] += 1
                    self.stats['bug_posts'] += 1
                    logger.info(f"🚨 즉시 버그 알림 전송 성공: {title[:30]}...")
                else:
                    raise Exception("버그 알림 전송 실패")
            else:
                # 감성 알림
                success = self._send_immediate_sentiment_alert(post_data)
                if success:
                    self.stats['immediate_sentiment_alerts'] += 1
                    self.stats['sentiment_posts'] += 1
                    logger.info(f"📊 즉시 감성 알림 전송 성공: {title[:30]}...")
                else:
                    raise Exception("감성 알림 전송 실패")
            
            # 3. 감성 데이터 저장
            sentiment_save_success = self._save_sentiment_for_daily_report(post_data, classification)
            if sentiment_save_success:
                self.stats['sentiment_save_success'] += 1
            else:
                self.stats['sentiment_save_failed'] += 1
                logger.warning(f"감성 데이터 저장 실패하였지만 처리 계속: {title[:30]}...")
            
            # 4. 처리 완료 마킹
            try:
                mark_as_processed(url, notified=True)
            except Exception as e:
                self.error_manager.handle_error(e, ErrorType.FILE_IO, ErrorSeverity.LOW, 
                                              {'url': url})
            
            self.stats['processed_posts'] += 1
            logger.info(f"✅ [SUCCESS] 즉시 처리 완료: {title[:30]}...")
            return True
            
        except ValueError as e:
            self.error_manager.handle_error(e, ErrorType.DATA_PARSING, ErrorSeverity.LOW, 
                                          {'post_data': str(post_data)[:200]})
            self.stats['failed_posts'] += 1
            return False
        
        except (IOError, OSError) as e:
            recovery_success = self.error_manager.handle_error(
                e, ErrorType.FILE_IO, ErrorSeverity.MEDIUM, 
                {'post_title': post_data.get('title', 'N/A')[:50]},
                recovery_callback=lambda: self._recreate_data_files()
            )
            if recovery_success:
                self.stats['error_recoveries'] += 1
                return self.process_post_immediately(post_data)
            else:
                self.stats['failed_posts'] += 1
                return False
        
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            recovery_success = self.error_manager.handle_error(
                e, ErrorType.NETWORK, ErrorSeverity.MEDIUM, 
                {'post_title': post_data.get('title', 'N/A')[:50]}
            )
            if recovery_success:
                self.stats['error_recoveries'] += 1
                return self.process_post_immediately(post_data)
            else:
                self.stats['failed_posts'] += 1
                return False
        
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRITICAL, ErrorSeverity.HIGH, 
                                          {'function': 'process_post_immediately',
                                           'post_title': post_data.get('title', 'N/A')[:50]})
            
            self.stats['failed_posts'] += 1
            self.stats['errors'] += 1
            return False
    
    def _send_immediate_bug_alert(self, post_data: Dict) -> bool:
        """즉시 버그 알림 전송 - v4.5 완전 보존"""
        try:
            if not self.webhooks.get('bug'):
                raise Exception("버그 알림 웹훅이 설정되지 않았습니다")
            
            success = send_bug_alert([post_data])
            return success
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.NOTIFICATION, ErrorSeverity.HIGH, 
                                          {'alert_type': 'bug', 'post_title': post_data.get('title', '')[:50]})
            return False
    
    def _send_immediate_sentiment_alert(self, post_data: Dict) -> bool:
        """즉시 감성 알림 전송 - v4.5 완전 보존"""
        try:
            if not self.webhooks.get('sentiment'):
                raise Exception("감성 알림 웹훅이 설정되지 않았습니다")
            
            classification = post_data.get('classification', {})
            sentiment = classification.get('sentiment_analysis', {}).get('sentiment', 'neutral')
            
            sentiment_summary = {
                'total_posts': 1,
                'sentiment_distribution': {sentiment: 1},
                'time_period': '즉시 처리',
                'timestamp': datetime.now().isoformat()
            }
            
            success = send_sentiment_notification([post_data], sentiment_summary)
            return success
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.NOTIFICATION, ErrorSeverity.HIGH, 
                                          {'alert_type': 'sentiment', 'post_title': post_data.get('title', '')[:50]})
            return False
    
    def _save_sentiment_for_daily_report(self, post_data: Dict, classification: Dict) -> bool:
        """일간 리포트용 감성 데이터 저장 - v4.5 완전 보존 + 🔧 수정 4: json 파일 처리 안전화"""
        try:
            # 🔧 수정 4: json 파일 처리 안전화
            try:
                from sentiment_data_manager import save_sentiment_data_immediately
                
                sentiment_data = {
                    'title': post_data.get('title', ''),
                    'content': post_data.get('content', '')[:200],
                    'url': post_data.get('url', ''),
                    'source': post_data.get('source', ''),
                    'sentiment': classification.get('sentiment_analysis', {}).get('sentiment', 'neutral'),
                    'confidence': classification.get('sentiment_analysis', {}).get('confidence', 0.0),
                    'category': classification.get('category', 'neutral'),
                    'timestamp': datetime.now().isoformat()
                }
                
                success = save_sentiment_data_immediately(sentiment_data)
                if success:
                    logger.debug(f"감성 데이터 저장 성공: {sentiment_data['title'][:30]}...")
                    return True
                else:
                    raise Exception("sentiment_data_manager 저장 실패")
                    
            except ImportError:
                # 폴백: 직접 JSON 파일 처리 (안전화)
                return self._save_sentiment_direct(post_data, classification)
                
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.FILE_IO, ErrorSeverity.MEDIUM, 
                                          {'function': '_save_sentiment_for_daily_report',
                                           'post_title': post_data.get('title', '')[:30]})
            return False
    
    def _save_sentiment_direct(self, post_data: Dict, classification: Dict) -> bool:
        """감성 데이터 직접 저장 (폴백) - 🔧 수정 4: json 파일 처리 안전화 적용"""
        try:
            sentiment_file = "daily_sentiment_data.json"
            
            # 🔧 수정 4: 안전한 json 파일 처리
            try:
                if os.path.exists(sentiment_file):
                    with open(sentiment_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if not content:
                            sentiment_data = []
                        else:
                            sentiment_data = json.loads(content)
                            
                    # 데이터 타입 검증
                    if not isinstance(sentiment_data, list):
                        logger.warning("sentiment_data.json이 배열이 아님 - 새로 생성")
                        sentiment_data = []
                else:
                    sentiment_data = []
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"sentiment_data.json 파싱 실패 - 새로 생성: {e}")
                sentiment_data = []
            except Exception as e:
                logger.error(f"sentiment_data.json 읽기 실패: {e}")
                return False
                
            # 새로운 데이터 추가
            new_entry = {
                'title': post_data.get('title', ''),
                'content': post_data.get('content', '')[:200],
                'url': post_data.get('url', ''),
                'source': post_data.get('source', ''),
                'sentiment': classification.get('sentiment_analysis', {}).get('sentiment', 'neutral'),
                'confidence': classification.get('sentiment_analysis', {}).get('confidence', 0.0),
                'category': classification.get('category', 'neutral'),
                'timestamp': datetime.now().isoformat(),
                'saved_at': datetime.now().isoformat()
            }
            
            sentiment_data.append(new_entry)
            
            # 24시간 이전 데이터 정리
            cutoff_time = datetime.now() - timedelta(hours=24)
            sentiment_data = [
                entry for entry in sentiment_data
                if datetime.fromisoformat(entry.get('saved_at', entry.get('timestamp', datetime.now().isoformat()))) > cutoff_time
            ]
            
            # 파일에 안전하게 저장
            try:
                with open(sentiment_file, 'w', encoding='utf-8') as f:
                    json.dump(sentiment_data, f, ensure_ascii=False, indent=2)
                    
                logger.debug(f"감성 데이터 직접 저장 성공: {new_entry['title'][:30]}...")
                return True
                
            except Exception as e:
                logger.error(f"sentiment_data.json 쓰기 실패: {e}")
                return False
                
        except Exception as e:
            logger.error(f"감성 데이터 직접 저장 실패: {e}")
            return False
    
    def _recreate_data_files(self):
        """데이터 파일 재생성 - v4.5 완전 보존"""
        try:
            # 필수 데이터 파일들 재생성
            essential_files = [
                ("daily_sentiment_data.json", []),
                ("epic7_monitor_retry_queue.json", []),
                ("crawled_links.json", {}),
                ("content_cache.json", {})
            ]
            
            for file_path, default_data in essential_files:
                if not os.path.exists(file_path):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(default_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"데이터 파일 재생성: {file_path}")
                    
        except Exception as e:
            logger.error(f"데이터 파일 재생성 실패: {e}")
    
    def run_30min_sentiment_notification(self) -> bool:
        """30분 주기 감성 동향 알림 - v4.5 완전 보존"""
        try:
            logger.info("📊 30분 주기 감성 동향 알림 시작")
            
            if not self.webhooks.get('sentiment'):
                logger.warning("감성 알림 웹훅이 설정되지 않았습니다")
                return False
            
            # 30분간 감성 데이터 수집
            sentiment_summary = self._get_30min_sentiment_summary()
            
            if not sentiment_summary or sentiment_summary.get('total_posts', 0) == 0:
                logger.info("📭 30분간 감성 분석할 게시글이 없습니다")
                return True
            
            # 감성 동향 알림 전송
            success = send_sentiment_notification([], sentiment_summary)
            
            if success:
                logger.info(f"📊 30분 주기 감성 동향 알림 전송 성공: {sentiment_summary.get('total_posts', 0)}개 게시글")
                return True
            else:
                raise Exception("30분 주기 감성 동향 알림 전송 실패")
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.NOTIFICATION, ErrorSeverity.HIGH, 
                                          {'function': 'run_30min_sentiment_notification'})
            return False
    
    def _get_30min_sentiment_summary(self) -> Dict:
        """30분간 감성 요약 데이터 생성 - v4.5 완전 보존 + 🔧 수정 4: json 처리 안전화"""
        try:
            sentiment_file = "daily_sentiment_data.json"
            
            # 🔧 수정 4: 안전한 json 파일 처리
            try:
                if not os.path.exists(sentiment_file):
                    return {'total_posts': 0}
                    
                with open(sentiment_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return {'total_posts': 0}
                    sentiment_data = json.loads(content)
                    
                if not isinstance(sentiment_data, list):
                    logger.warning("sentiment_data.json이 배열이 아님")
                    return {'total_posts': 0}
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"sentiment_data.json 파싱 실패: {e}")
                return {'total_posts': 0}
            except Exception as e:
                logger.error(f"sentiment_data.json 읽기 실패: {e}")
                return {'total_posts': 0}
            
            # 30분 이전 데이터 필터링
            cutoff_time = datetime.now() - timedelta(minutes=30)
            recent_data = [
                entry for entry in sentiment_data
                if datetime.fromisoformat(entry.get('timestamp', datetime.now().isoformat())) > cutoff_time
            ]
            
            if not recent_data:
                return {'total_posts': 0}
            
            # 감성별 통계 계산
            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
            
            for entry in recent_data:
                sentiment = entry.get('sentiment', 'neutral')
                if sentiment in sentiment_counts:
                    sentiment_counts[sentiment] += 1
            
            return {
                'total_posts': len(recent_data),
                'sentiment_distribution': sentiment_counts,
                'time_period': '최근 30분간',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"30분 감성 요약 데이터 생성 실패: {e}")
            return {'total_posts': 0}
    
    def run_24h_daily_report(self) -> bool:
        """24시간 일간 리포트 - v4.5 완전 보존"""
        try:
            logger.info("📈 24시간 일간 리포트 생성 시작")
            
            if not self.webhooks.get('report'):
                logger.warning("리포트 웹훅이 설정되지 않았습니다")
                return False
            
            # 24시간 데이터 수집
            if not CRAWLER_AVAILABLE:
                logger.warning("crawler 모듈 사용 불가 - 리포트 데이터 수집 제한")
                all_posts = []
            else:
                try:
                    all_posts = get_all_posts_for_report()
                except Exception as e:
                    logger.warning(f"리포트 데이터 수집 실패 - 빈 리포트 생성: {e}")
                    all_posts = []
            
            # 리포트 데이터 구성
            report_data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'total_posts': len(all_posts) if all_posts else 0,
                'bug_posts': len([p for p in all_posts if p.get('source', '').endswith('_bug')]) if all_posts else 0,
                'sentiment_summary': self._get_24h_sentiment_summary(),
                'top_keywords': self._extract_top_keywords(all_posts) if all_posts else [],
                'system_stats': self.get_execution_report()
            }
            
            # 일간 리포트 전송
            success = send_daily_report(report_data)
            
            if success:
                logger.info(f"📈 24시간 일간 리포트 전송 성공: {report_data['total_posts']}개 게시글")
                return True
            else:
                raise Exception("24시간 일간 리포트 전송 실패")
            
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.NOTIFICATION, ErrorSeverity.HIGH, 
                                          {'function': 'run_24h_daily_report'})
            return False
    
    def _get_24h_sentiment_summary(self) -> Dict:
        """24시간 감성 요약 - v4.5 완전 보존 + 🔧 수정 4: json 처리 안전화"""
        try:
            sentiment_file = "daily_sentiment_data.json"
            
            # 🔧 수정 4: 안전한 json 파일 처리
            try:
                if not os.path.exists(sentiment_file):
                    return {'positive': 0, 'negative': 0, 'neutral': 0}
                    
                with open(sentiment_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return {'positive': 0, 'negative': 0, 'neutral': 0}
                    sentiment_data = json.loads(content)
                    
                if not isinstance(sentiment_data, list):
                    logger.warning("sentiment_data.json이 배열이 아님")
                    return {'positive': 0, 'negative': 0, 'neutral': 0}
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"sentiment_data.json 파싱 실패: {e}")
                return {'positive': 0, 'negative': 0, 'neutral': 0}
            except Exception as e:
                logger.error(f"sentiment_data.json 읽기 실패: {e}")
                return {'positive': 0, 'negative': 0, 'neutral': 0}
            
            # 24시간 데이터만 필터링
            cutoff_time = datetime.now() - timedelta(hours=24)
            daily_data = [
                entry for entry in sentiment_data
                if datetime.fromisoformat(entry.get('timestamp', datetime.now().isoformat())) > cutoff_time
            ]
            
            # 감성별 카운트
            sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
            
            for entry in daily_data:
                sentiment = entry.get('sentiment', 'neutral')
                if sentiment in sentiment_counts:
                    sentiment_counts[sentiment] += 1
            
            return sentiment_counts
            
        except Exception as e:
            logger.error(f"24시간 감성 요약 생성 실패: {e}")
            return {'positive': 0, 'negative': 0, 'neutral': 0}
    
    def _extract_top_keywords(self, posts: List[Dict]) -> List[str]:
        """상위 키워드 추출 - v4.5 완전 보존"""
        try:
            if not posts:
                return []
            
            # 간단한 키워드 추출 (실제로는 더 정교한 NLP 처리 필요)
            from collections import Counter
            import re
            
            all_text = ""
            for post in posts:
                title = post.get('title', '')
                content = post.get('content', '')
                all_text += f" {title} {content}"
            
            # 단순 키워드 추출 (한글, 영문 3자 이상)
            keywords = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', all_text.lower())
            
            # 상위 10개 키워드 반환
            counter = Counter(keywords)
            return [keyword for keyword, count in counter.most_common(10)]
            
        except Exception as e:
            logger.error(f"키워드 추출 실패: {e}")
            return []
    
    def get_execution_report(self) -> str:
        """실행 통계 보고서 - v4.5 완전 보존"""
        execution_time = datetime.now() - self.start_time
        
        report = f"""
✨ Epic7 모니터링 시스템 v4.6 실행 보고서

🕐 실행 정보:
- 모드: {self.stats['mode']}
- 스케줄: {self.stats['schedule']}
- 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- 실행 시간: {str(execution_time).split('.')[0]}

📊 크롤링 통계:
- 총 크롤링: {self.stats['total_crawled']}개
- 한국 사이트: {self.stats['korea_sites_crawled']}개
- 글로벌 사이트: {self.stats['global_sites_crawled']}개
- 처리 성공: {self.stats['processed_posts']}개
- 처리 실패: {self.stats['failed_posts']}개

🚨 알림 전송:
- 즉시 버그 알림: {self.stats['immediate_bug_alerts']}개
- 즉시 감성 알림: {self.stats['immediate_sentiment_alerts']}개
- 버그 게시글: {self.stats['bug_posts']}개
- 감성 게시글: {self.stats['sentiment_posts']}개

💾 데이터 저장:
- 감성 데이터 저장 성공: {self.stats['sentiment_save_success']}개
- 감성 데이터 저장 실패: {self.stats['sentiment_save_failed']}개

⚠️ 에러 통계:
- 총 에러: {self.stats['errors']}개
- 에러 복구 성공: {self.stats['error_recoveries']}개
- 치명적 알림: {self.stats['critical_alerts']}개
- 높은 우선순위 알림: {self.stats['high_priority_alerts']}개

💡 시스템 상태:
- 디버그 모드: {'활성화' if self.stats['debug'] else '비활성화'}
- 강제 크롤링: {'활성화' if self.stats['force_crawl'] else '비활성화'}
- Crawler 모듈: {'사용 가능' if CRAWLER_AVAILABLE else '사용 불가'}
- Classifier 모듈: {'사용 가능' if CLASSIFIER_AVAILABLE else '사용 불가'}

{self.error_manager.get_error_report()}
""".strip()
        
        return report
    
    def run(self) -> bool:
        """메인 실행 함수 - v4.6 스케줄별 분기"""
        try:
            logger.info(f"Epic7 모니터링 시스템 v4.6 실행 시작: {self.schedule} 스케줄, {self.mode} 모드")
            
            if self.schedule == "15min":
                return self.run_15min_crawling_and_bug_alert()
            elif self.schedule == "30min":
                return self.run_30min_sentiment_notification()
            elif self.schedule == "24h":
                return self.run_24h_daily_report()
            else:
                logger.error(f"지원하지 않는 스케줄: {self.schedule}")
                return False
                
        except Exception as e:
            self.error_manager.handle_error(e, ErrorType.CRITICAL, ErrorSeverity.CRITICAL, 
                                          {'function': 'run', 'schedule': self.schedule, 'mode': self.mode})
            return False
        finally:
            logger.info("Epic7 모니터링 시스템 v4.6 실행 완료")

# =============================================================================
# 시그널 핸들러 (v4.5 완전 보존)
# =============================================================================

def signal_handler(signum, frame):
    """시그널 핸들러 - 안전한 종료"""
    logger.info(f"시그널 {signum} 수신 - 안전한 종료 시작")
    ExecutionManager.release_lock()
    sys.exit(0)

# =============================================================================
# 메인 함수
# =============================================================================

def main():
    """메인 실행 함수 - 🔧 수정 5: 중복 실행 방지 적용"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 인자 파싱
        args = parse_arguments()
        
        # 실행 락 획득
        if not ExecutionManager.acquire_lock():
            logger.error("다른 프로세스가 실행 중입니다. 종료합니다.")
            return False
        
        logger.info("=" * 80)
        logger.info(f"Epic7 통합 모니터링 시스템 v4.6 시작")
        logger.info(f"모드: {args.mode}, 스케줄: {args.schedule}, 디버그: {args.debug}")
        logger.info("=" * 80)
        
        # 🔧 수정 5: 중복 실행 방지 - crawl_all() 호출 제거
        # 기존에 있던 중복 crawl_all() 호출을 제거하여 중복 실행 방지
        
        # Epic7Monitor 인스턴스 생성 및 실행
        monitor = Epic7Monitor(
            mode=args.mode,
            schedule=args.schedule,
            debug=args.debug,
            force_crawl=args.force_crawl
        )
        
        # 모니터링 실행
        success = monitor.run()
        
        # 실행 결과 보고
        logger.info("=" * 80)
        logger.info("Epic7 모니터링 시스템 v4.6 실행 완료 보고서")
        logger.info("=" * 80)
        print(monitor.get_execution_report())
        
        return success
        
    except KeyboardInterrupt:
        logger.info("사용자에 의한 중단")
        return False
    except Exception as e:
        error_manager.handle_error(e, ErrorType.CRITICAL, ErrorSeverity.CRITICAL, 
                                 {'function': 'main'})
        return False
    finally:
        # 실행 락 해제
        ExecutionManager.release_lock()
        logger.info("Epic7 모니터링 시스템 v4.6 종료")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)