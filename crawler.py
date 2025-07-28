#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 다국가 크롤러 v4.4 - 정확한 문제점 해결 완성형
Master 요구사항: 게시글별 즉시 처리 (크롤링→감성분석→알림→마킹)

핵심 개선사항 (v4.4):
- 재시도 큐 영속성 확보 (JSON 파일 기반) ✨FIXED✨
- 에러 유형별 분류 및 통계 시스템 ✨FIXED✨ 
- 안전한 URL 해시 시스템 (SHA256 기반) ✨FIXED✨
- 강화된 Epic7 모듈 fallback ✨ENHANCED✨
- 디버그 파일 관리 및 리소스 최적화 ✨NEW✨

기존 기능 100% 보존:
- 게시글별 즉시 처리 완전 구현
- 에러 격리 및 복원력 강화
- 재시도 메커니즘 자동 관리
- 모든 API 인터페이스 호환성 유지

Author: Epic7 Monitoring Team  
Version: 4.4 (정확한 문제점 해결 완성형)
Date: 2025-07-28
Fixed: 재시도 큐, 에러 분류, 해시 충돌, fallback 강화
"""

import time
import random
import re
import requests
import concurrent.futures
import os
import sys
import json
import hashlib  # ✨ NEW: SHA256 해시용
import traceback  # ✨ NEW: 에러 상세 분석용
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Union
from urllib.parse import urljoin, urlparse
from enum import Enum  # ✨ NEW: 에러 유형 정의용

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


# =============================================================================
# ✨ NEW v4.4: 에러 유형 정의 및 통계 시스템
# =============================================================================

class ErrorType(Enum):
    """에러 유형 분류"""
    IMPORT = "import_error"
    NETWORK = "network_error"
    PARSE = "parse_error"
    CLASSIFICATION = "classification_error"
    NOTIFICATION = "notification_error"
    FILE_IO = "file_io_error"
    DRIVER = "driver_error"
    GENERAL = "general_error"

class ErrorManager:
    """에러 관리 및 통계 시스템"""
    
    def __init__(self):
        self.error_stats = {error_type.value: 0 for error_type in ErrorType}
        self.error_log = []
        self.stats_file = "error_stats.json"
        self.load_error_stats()
    
    def record_error(self, error_type: ErrorType, error: Exception, context: Dict = None):
        """에러 기록 및 통계 업데이트"""
        try:
            self.error_stats[error_type.value] += 1
            
            error_entry = {
                "type": error_type.value,
                "message": str(error),
                "traceback": traceback.format_exc(),
                "context": context or {},
                "timestamp": datetime.now().isoformat()
            }
            
            self.error_log.append(error_entry)
            
            # 로그 크기 제한 (최대 1000개)
            if len(self.error_log) > 1000:
                self.error_log = self.error_log[-500:]
            
            self.save_error_stats()
            
        except Exception as e:
            print(f"[ERROR] 에러 기록 실패: {e}")
    
    def load_error_stats(self):
        """에러 통계 로드"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.error_stats.update(data.get('stats', {}))
                    self.error_log = data.get('log', [])
        except Exception as e:
            print(f"[WARNING] 에러 통계 로드 실패: {e}")
    
    def save_error_stats(self):
        """에러 통계 저장"""
        try:
            data = {
                'stats': self.error_stats,
                'log': self.error_log[-100:],  # 최근 100개만 저장
                'last_updated': datetime.now().isoformat()
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 에러 통계 저장 실패: {e}")
    
    def get_error_summary(self) -> Dict:
        """에러 통계 요약 반환"""
        total_errors = sum(self.error_stats.values())
        return {
            'total_errors': total_errors,
            'by_type': self.error_stats,
            'recent_errors': len(self.error_log),
            'most_common': max(self.error_stats, key=self.error_stats.get) if total_errors > 0 else None
        }

# 전역 에러 매니저 인스턴스
error_manager = ErrorManager()


# Epic7 시스템 모듈 import (즉시 처리용)
try:
    from classifier import Epic7Classifier, is_bug_post, is_high_priority_bug, should_send_realtime_alert
    from notifier import send_bug_alert, send_sentiment_notification
    from sentiment_data_manager import save_sentiment_data, get_sentiment_summary
    EPIC7_MODULES_AVAILABLE = True
    print("[INFO] Epic7 처리 모듈들 로드 완료")
except ImportError as e:
    

    # ✨ ENHANCED v4.4: 향상된 임포트 에러 진단
    import_error_details = {
        'error_message': str(e),
        'missing_module': getattr(e, 'name', 'unknown'),
        'python_version': sys.version,
        'python_path': sys.path,
        'current_directory': os.getcwd()
    }
    
    error_manager.record_error(ErrorType.IMPORT, e, import_error_details)
    
    print(f"[WARNING] Epic7 처리 모듈 로드 실패: {e}")
    print(f"[WARNING] 누락 모듈: {import_error_details['missing_module']}")
    print("[WARNING] 즉시 처리 기능이 제한됩니다.")
    print("[INFO] 상세 진단 정보가 error_stats.json에 저장되었습니다.")
    

    EPIC7_MODULES_AVAILABLE = False

# Reddit 크롤링용 import
try:
    import praw
    REDDIT_AVAILABLE = True
except ImportError as e:
    error_manager.record_error(ErrorType.IMPORT, e, {'module': 'praw'})
    print("[WARNING] PRAW 라이브러리가 설치되지 않았습니다. Reddit 크롤링을 건너뜁니다.")
    REDDIT_AVAILABLE = False


# =============================================================================
# ✨ FIXED v4.4: 재시도 큐 영속성 확보 (JSON 파일 기반)
# =============================================================================

class PersistentRetryQueue:
    """영속성을 가진 재시도 큐 관리자"""
    
    def __init__(self, queue_file: str = "retry_queue.json"):
        self.queue_file = queue_file
        self.queue = self.load_queue()
        self.max_queue_size = 500  # 큐 크기 제한
    
    def load_queue(self) -> List[Dict]:
        """재시도 큐 로드"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    queue = data.get('queue', [])
                    print(f"[INFO] 재시도 큐 로드 완료: {len(queue)}개 항목")
                    return queue
        except Exception as e:
            error_manager.record_error(ErrorType.FILE_IO, e, {'file': self.queue_file})
            print(f"[WARNING] 재시도 큐 로드 실패: {e}")
        
        return []
    
    def save_queue(self):
        """재시도 큐 저장"""
        try:
            # 큐 크기 제한
            if len(self.queue) > self.max_queue_size:
                # 오래된 항목부터 제거
                self.queue = sorted(
                    self.queue, 
                    key=lambda x: x.get('timestamp', ''), 
                    reverse=True
                )[:self.max_queue_size]
                print(f"[INFO] 재시도 큐 크기 제한 적용: {self.max_queue_size}개로 축소")
            
            data = {
                'queue': self.queue,
                'last_updated': datetime.now().isoformat(),
                'queue_size': len(self.queue)
            }
            
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            error_manager.record_error(ErrorType.FILE_IO, e, {'file': self.queue_file})
            print(f"[ERROR] 재시도 큐 저장 실패: {e}")
    
    def add(self, post_data: Dict, sentiment_result: Optional[Dict] = None, error_type: str = "general"):
        """재시도 큐에 항목 추가"""
        retry_item = {
            "post_data": post_data,
            "sentiment_result": sentiment_result,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0,
            "priority": self._calculate_priority(error_type)
        }
        
        self.queue.append(retry_item)
        self._sort_by_priority()
        self.save_queue()
        
        print(f"[RETRY] 재시도 큐 추가: {len(self.queue)}개 대기중 (유형: {error_type})")
    
    def _calculate_priority(self, error_type: str) -> int:
        """에러 유형에 따른 우선순위 계산"""
        priority_map = {
            "import_error": 1,      # 낮은 우선순위 (시스템 문제)
            "network_error": 5,    # 높은 우선순위 (일시적)
            "parse_error": 3,      # 중간 우선순위
            "classification_error": 4, # 중간-높음 우선순위
            "general": 2           # 기본 우선순위
        }
        return priority_map.get(error_type, 2)
    
    def _sort_by_priority(self):
        """우선순위별 정렬"""
        self.queue.sort(key=lambda x: x.get('priority', 2), reverse=True)
    
    def remove(self, item: Dict):
        """큐에서 항목 제거"""
        try:
            self.queue.remove(item)
            self.save_queue()
        except ValueError:
            pass  # 이미 제거된 항목
    
    def get_stats(self) -> Dict:
        """큐 통계 반환"""
        error_types = {}
        for item in self.queue:
            error_type = item.get('error_type', 'unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_items': len(self.queue),
            'by_error_type': error_types,
            'oldest_item': min(self.queue, key=lambda x: x.get('timestamp', '')).get('timestamp') if self.queue else None
        }


# =============================================================================
# 🚀 Master 요구사항: 즉시 처리 시스템 구현 (v4.4 강화)
# =============================================================================

class ImmediateProcessor:
    """게시글별 즉시 처리 시스템 v4.4"""
    
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        

        # ✨ FIXED v4.4: 영속성을 가진 재시도 큐
        self.retry_queue = PersistentRetryQueue()
        

        self.classifier = None
        self.error_manager = error_manager
        
        if EPIC7_MODULES_AVAILABLE:
            try:
                self.classifier = Epic7Classifier()
                print("[INFO] 즉시 처리 시스템 초기화 완료")
            except Exception as e:
                self.error_manager.record_error(ErrorType.CLASSIFICATION, e)
                print(f"[ERROR] 분류기 초기화 실패: {e}")
                
    def process_post_immediately(self, post_data: Dict) -> bool:
        """
        게시글별 즉시 처리 메인 함수 v4.4
        Master 요구사항: 크롤링 → 감성분석 → 알림 → 마킹
        """
        try:
            print(f"[IMMEDIATE] 즉시 처리 시작: {post_data.get('title', '')[:50]}...")
            
            if not EPIC7_MODULES_AVAILABLE:
                print("[WARNING] 처리 모듈 없음, 강화된 기본 처리 수행")
                

                # ✨ ENHANCED v4.4: 강화된 fallback 처리
                return self._enhanced_basic_processing(post_data)
                

            
            # 1. 유저 동향 감성 분석
            sentiment_result = self._analyze_sentiment(post_data)
            
            # 2. 알림 전송 여부 체크 및 전송
            notification_sent = self._handle_notifications(post_data, sentiment_result)
            
            # 3. 처리 완료 마킹 (알림 성공 시에만)
            if notification_sent:
                self._mark_as_processed(post_data['url'], notified=True)
                self.processed_count += 1
                print(f"[SUCCESS] 즉시 처리 완료: {post_data.get('title', '')[:30]}...")
            else:
                # 실패한 경우 재시도 큐에 추가
                self.retry_queue.add(post_data, sentiment_result, "notification_error")
                self.failed_count += 1
                
            return notification_sent
            
        

        # ✨ ENHANCED v4.4: 에러 유형별 분류 처리
        except ImportError as e:
            self._handle_import_error(e, post_data)
            return False
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            self._handle_network_error(e, post_data)
            return False
        except (ValueError, KeyError, AttributeError) as e:
            self._handle_parse_error(e, post_data)
            return False
        

        except Exception as e:
            self._handle_general_error(e, post_data)
            return False
    
    

    # ✨ NEW v4.4: 에러 유형별 처리 메서드들
    def _handle_import_error(self, error: ImportError, post_data: Dict):
        """임포트 에러 처리"""
        context = {'post_title': post_data.get('title', '')[:50]}
        self.error_manager.record_error(ErrorType.IMPORT, error, context)
        self.retry_queue.add(post_data, None, "import_error")
        self.failed_count += 1
        print(f"[ERROR] 임포트 에러 - 낮은 우선순위로 재시도 큐 추가: {error}")
    
    def _handle_network_error(self, error: Exception, post_data: Dict):
        """네트워크 에러 처리"""
        context = {
            'post_url': post_data.get('url', ''),
            'post_title': post_data.get('title', '')[:50]
        }
        self.error_manager.record_error(ErrorType.NETWORK, error, context)
        self.retry_queue.add(post_data, None, "network_error")
        self.failed_count += 1
        print(f"[ERROR] 네트워크 에러 - 높은 우선순위로 재시도: {error}")
    
    def _handle_parse_error(self, error: Exception, post_data: Dict):
        """파싱 에러 처리"""
        context = {'post_source': post_data.get('source', '')}
        self.error_manager.record_error(ErrorType.PARSE, error, context)
        self.retry_queue.add(post_data, None, "parse_error")
        self.failed_count += 1
        print(f"[ERROR] 파싱 에러: {error}")
    
    def _handle_general_error(self, error: Exception, post_data: Dict):
        """일반 에러 처리"""
        context = {'post_data_keys': list(post_data.keys())}
        self.error_manager.record_error(ErrorType.GENERAL, error, context)
        self.retry_queue.add(post_data, None, "general")
        self.failed_count += 1
        print(f"[ERROR] 일반 에러: {error}")
    

    
    def _analyze_sentiment(self, post_data: Dict) -> Dict:
        """감성 분석 수행"""
        try:
            if not self.classifier:
                return {"sentiment": "neutral", "confidence": 0.5}
                
            result = self.classifier.classify_post(post_data)
            print(f"[SENTIMENT] 분석 결과: {result.get('sentiment', 'unknown')}")
            return result
            
        except Exception as e:
            self.error_manager.record_error(ErrorType.CLASSIFICATION, e)
            print(f"[ERROR] 감성 분석 실패: {e}")
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}
    
    

    # ✨ ENHANCED v4.4: 강화된 기본 처리
    def _enhanced_basic_processing(self, post_data: Dict) -> bool:
        """강화된 기본 처리 (Epic7 모듈 없을 때)"""
        try:
            print(f"[ENHANCED_BASIC] 강화된 기본 처리: {post_data.get('title', '')[:50]}...")
            
            # 1. 기본 정보 추출 및 저장
            basic_info = {
                'title': post_data.get('title', ''),
                'url': post_data.get('url', ''),
                'source': post_data.get('source', ''),
                'processed_at': datetime.now().isoformat(),
                'processing_method': 'enhanced_basic',
                'epic7_modules_available': False
            }
            
            # 2. 기본 데이터 저장
            self._save_basic_data(basic_info)
            
            # 3. 처리 완료 마킹
            self._mark_as_processed(post_data['url'], notified=False)
            self.processed_count += 1
            
            print("[SUCCESS] 강화된 기본 처리 완료 - 기본 데이터 저장됨")
            return True
            
        except Exception as e:
            self.error_manager.record_error(ErrorType.GENERAL, e)
            print(f"[ERROR] 강화된 기본 처리 실패: {e}")
            return False
    
    def _save_basic_data(self, data: Dict):
        """기본 데이터 저장"""
        try:
            basic_data_file = "basic_processed_data.json"
            
            # 기존 데이터 로드
            existing_data = []
            if os.path.exists(basic_data_file):
                with open(basic_data_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            
            # 새 데이터 추가
            existing_data.append(data)
            
            # 최대 1000개로 제한
            if len(existing_data) > 1000:
                existing_data = existing_data[-500:]
            
            # 저장
            with open(basic_data_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.error_manager.record_error(ErrorType.FILE_IO, e)
            print(f"[ERROR] 기본 데이터 저장 실패: {e}")
    

    
    def _handle_notifications(self, post_data: Dict, sentiment_result: Dict) -> bool:
        """분류별 알림 처리"""
        try:
            source = post_data.get('source', '')
            sentiment = sentiment_result.get('sentiment', 'neutral')
            
            # Master 요구사항: 버그 게시판 글이라면 실시간 버그 메시지
            if source.endswith('_bug') or 'bug' in source.lower():
                print("[ALERT] 버그 게시판 글 → 즉시 버그 알림")
                return self._send_bug_alert(post_data)
            
            # Master 요구사항: 동향 분석 후 버그로 분류된 글도 실시간 버그 메시지
            elif is_bug_post(sentiment_result) or should_send_realtime_alert(sentiment_result):
                print("[ALERT] 버그 분류 글 → 즉시 버그 알림")
                return self._send_bug_alert(post_data)
            
            # Master 요구사항: 긍정/중립/부정 동향은 감성 알림 + 저장
            else:
                print(f"[ALERT] 감성 동향 글 ({sentiment}) → 즉시 감성 알림")
                return self._send_sentiment_alert(post_data, sentiment_result)
                
        except Exception as e:
            self.error_manager.record_error(ErrorType.NOTIFICATION, e)
            print(f"[ERROR] 알림 처리 실패: {e}")
            return False
    
    def _send_bug_alert(self, post_data: Dict) -> bool:
        """버그 알림 전송"""
        try:
            success = send_bug_alert(post_data)
            if success:
                print("[SUCCESS] 버그 알림 전송 완료")
            else:
                print("[FAILED] 버그 알림 전송 실패")
            return success
        except Exception as e:
            self.error_manager.record_error(ErrorType.NOTIFICATION, e)
            print(f"[ERROR] 버그 알림 전송 오류: {e}")
            return False
    
    def _send_sentiment_alert(self, post_data: Dict, sentiment_result: Dict) -> bool:
        """감성 알림 전송 및 데이터 저장"""
        try:
            # Master 요구사항: 일간 리포트용 데이터 저장
            save_success = save_sentiment_data(post_data, sentiment_result)
            
            # 즉시 감성 알림 전송
            alert_success = send_sentiment_notification(post_data, sentiment_result)
            
            if save_success and alert_success:
                print("[SUCCESS] 감성 알림 전송 및 데이터 저장 완료")
                return True
            else:
                print(f"[PARTIAL] 저장: {save_success}, 알림: {alert_success}")
                return False
                
        except Exception as e:
            self.error_manager.record_error(ErrorType.NOTIFICATION, e)
            print(f"[ERROR] 감성 처리 오류: {e}")
            return False
    
    def _mark_as_processed(self, url: str, notified: bool = True):
        """처리 완료 마킹"""
        try:
            mark_as_processed(url, notified)
        except Exception as e:
            self.error_manager.record_error(ErrorType.FILE_IO, e)
            print(f"[ERROR] 마킹 실패: {e}")
    
    def process_retry_queue(self):
        """재시도 큐 처리 v4.4"""
        if not self.retry_queue.queue:
            return
            
        print(f"[RETRY] 재시도 큐 처리 시작: {len(self.retry_queue.queue)}개")
        processed_items = []
        
        for item in self.retry_queue.queue:
            try:
                if item["retry_count"] >= 3:
                    print(f"[SKIP] 최대 재시도 횟수 초과: {item.get('error_type', 'unknown')}")
                    processed_items.append(item)
                    continue
                
                item["retry_count"] += 1
                success = self.process_post_immediately(item["post_data"])
                
                if success:
                    processed_items.append(item)
                    
            except Exception as e:
                self.error_manager.record_error(ErrorType.GENERAL, e)
                print(f"[ERROR] 재시도 처리 실패: {e}")
        
        # 처리 완료된 항목들 제거
        for item in processed_items:
            self.retry_queue.remove(item)
        
        print(f"[RETRY] 재시도 완료: {len(processed_items)}개 처리, {len(self.retry_queue.queue)}개 남음")
    
    def get_stats(self) -> Dict:
        """처리 통계 반환 v4.4"""
        return {
            "processed": self.processed_count,
            "failed": self.failed_count,
            "retry_queue": self.retry_queue.get_stats(),
            "error_summary": self.error_manager.get_error_summary(),
            "epic7_modules_available": EPIC7_MODULES_AVAILABLE
        }

# 전역 즉시 처리기 인스턴스
immediate_processor = ImmediateProcessor()


# =============================================================================
# ✨ NEW v4.4: 디버그 파일 관리 시스템
# =============================================================================

class DebugFileManager:
    """디버그 파일 관리 시스템"""
    
    def __init__(self, max_debug_files: int = 10):
        self.max_debug_files = max_debug_files
        self.debug_dir = "debug_files"
        self._ensure_debug_dir()
    
    def _ensure_debug_dir(self):
        """디버그 디렉토리 생성"""
        try:
            if not os.path.exists(self.debug_dir):
                os.makedirs(self.debug_dir)
        except Exception as e:
            print(f"[WARNING] 디버그 디렉토리 생성 실패: {e}")
    
    def save_debug_html(self, filename: str, content: str) -> str:
        """디버그 HTML 파일 저장 (관리됨)"""
        try:
            # 기존 디버그 파일들 정리
            self._cleanup_old_files()
            
            filepath = os.path.join(self.debug_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"[DEBUG] 디버그 파일 저장: {filepath}")
            return filepath
            
        except Exception as e:
            error_manager.record_error(ErrorType.FILE_IO, e)
            print(f"[ERROR] 디버그 파일 저장 실패: {e}")
            return ""
    
    def _cleanup_old_files(self):
        """오래된 디버그 파일 정리"""
        try:
            if not os.path.exists(self.debug_dir):
                return
            
            files = []
            for filename in os.listdir(self.debug_dir):
                filepath = os.path.join(self.debug_dir, filename)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    files.append((filepath, mtime))
            
            # 파일 수가 제한을 초과하면 오래된 파일부터 삭제
            if len(files) >= self.max_debug_files:
                files.sort(key=lambda x: x[1])  # 수정시간 기준 정렬
                files_to_delete = files[:len(files) - self.max_debug_files + 1]
                
                for filepath, _ in files_to_delete:
                    os.remove(filepath)
                    print(f"[CLEANUP] 오래된 디버그 파일 삭제: {filepath}")
                    
        except Exception as e:
            print(f"[WARNING] 디버그 파일 정리 실패: {e}")

# 전역 디버그 파일 매니저
debug_file_manager = DebugFileManager()


# =============================================================================
# 크롤링 스케줄 설정 클래스 (기존 유지)
# =============================================================================

class CrawlingSchedule:
    """크롤링 스케줄별 설정 관리"""

    FREQUENT_WAIT_TIME = 25      # 15분 주기 대기시간
    REGULAR_WAIT_TIME = 30       # 30분 주기 대기시간  
    REDDIT_WAIT_TIME = 15        # Reddit 대기시간
    RULIWEB_WAIT_TIME = 20       # 루리웹 대기시간

    # 스크롤 횟수 설정
    FREQUENT_SCROLL_COUNT = 2    # 15분 주기 스크롤
    REGULAR_SCROLL_COUNT = 3

    @staticmethod
    def get_wait_time(schedule_type: str) -> int:
        """스케줄 타입별 대기시간 반환"""
        if schedule_type == 'frequent':
            return CrawlingSchedule.FREQUENT_WAIT_TIME
        elif schedule_type == 'regular':
            return CrawlingSchedule.REGULAR_WAIT_TIME
        elif schedule_type == 'reddit':
            return CrawlingSchedule.REDDIT_WAIT_TIME
        elif schedule_type == 'ruliweb':
            return CrawlingSchedule.RULIWEB_WAIT_TIME
        else:
            return CrawlingSchedule.REGULAR_WAIT_TIME

    @staticmethod
    def get_scroll_count(schedule_type: str) -> int:
        """스케줄 타입별 스크롤 횟수 반환"""
        if schedule_type == 'frequent':
            return CrawlingSchedule.FREQUENT_SCROLL_COUNT
        else:
            return CrawlingSchedule.REGULAR_SCROLL_COUNT

# =============================================================================
# 파일 관리 시스템 - 시간 기반 중복 관리 (기존 유지)
# =============================================================================

def get_crawled_links_file():
    """워크플로우별 독립적인 크롤링 링크 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')

    if 'debug' in workflow_name.lower() or 'test' in workflow_name.lower():
        return "crawled_links_debug.json"
    elif 'monitor' in workflow_name.lower():
        return "crawled_links_monitor.json"
    else:
        return "crawled_links.json"

def get_content_cache_file():
    """워크플로우별 독립적인 콘텐츠 캐시 파일명 생성"""
    workflow_name = os.environ.get('GITHUB_WORKFLOW', 'default')

    if 'debug' in workflow_name.lower():
        return "content_cache_debug.json"
    else:
        return "content_cache.json"

def load_crawled_links():
    """크롤링 링크 로드 - 시간 기반 구조 적용"""
    crawled_links_file = get_crawled_links_file()
    
    if os.path.exists(crawled_links_file):
        try:
            with open(crawled_links_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 기존 단순 리스트 형태를 새 구조로 변환
                if isinstance(data, dict) and "links" in data:
                    if isinstance(data["links"], list) and len(data["links"]) > 0:
                        if isinstance(data["links"][0], str):
                            converted_links = []
                            for link in data["links"]:
                                converted_links.append({
                                    "url": link,
                                    "processed_at": (datetime.now() - timedelta(hours=25)).isoformat(),
                                    "notified": False
                                })
                            data["links"] = converted_links
                            print(f"[INFO] 기존 {len(converted_links)}개 링크를 새 구조로 변환")
                
                # 24시간 지난 항목 자동 제거
                now = datetime.now()
                valid_links = []
                for item in data.get("links", []):
                    try:
                        processed_time = datetime.fromisoformat(item["processed_at"])
                        if now - processed_time < timedelta(hours=24):
                            valid_links.append(item)
                    except:
                        continue
                
                data["links"] = valid_links
                print(f"[INFO] 24시간 기준 유효한 링크: {len(valid_links)}개")
                return data
                        
        except Exception as e:
            print(f"[WARNING] 크롤링 링크 파일 읽기 실패: {e}")
    
    return {"links": [], "last_updated": datetime.now().isoformat()}

def save_crawled_links(link_data):
    """크롤링 링크 저장 - 적극적 크기 관리"""
    try:
        if len(link_data["links"]) > 100:
            link_data["links"] = sorted(
                link_data["links"], 
                key=lambda x: x.get("processed_at", ""), 
                reverse=True
            )[:100]
            print(f"[INFO] 링크 목록을 최신 100개로 정리")

        link_data["last_updated"] = datetime.now().isoformat()

        crawled_links_file = get_crawled_links_file()
        with open(crawled_links_file, 'w', encoding='utf-8') as f:
            json.dump(link_data, f, ensure_ascii=False, indent=2)
            
        print(f"[INFO] 크롤링 링크 저장 완료: {len(link_data['links'])}개")

    except Exception as e:
        print(f"[ERROR] 링크 저장 실패: {e}")

def is_recently_processed(url: str, links_data: List[Dict], hours: int = 24) -> bool:
    """시간 기반 중복 체크"""
    try:
        now = datetime.now()
        for item in links_data:
            if item.get("url") == url:
                processed_time = datetime.fromisoformat(item["processed_at"])
                if now - processed_time < timedelta(hours=hours):
                    return True
        return False
    except Exception as e:
        print(f"[DEBUG] 중복 체크 오류: {e}")
        return False

def mark_as_processed(url: str, notified: bool = False):
    """게시글을 처리됨으로 마킹"""
    try:
        link_data = load_crawled_links()
        
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

def load_content_cache():
    """게시글 내용 캐시 로드"""
    content_cache_file = get_content_cache_file()

    if os.path.exists(content_cache_file):
        try:
            with open(content_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"[WARNING] {content_cache_file} 파일 읽기 실패, 새로 생성")
    return {}

def save_content_cache(cache_data):
    """게시글 내용 캐시 저장"""
    try:
        if len(cache_data) > 500:
            sorted_items = sorted(cache_data.items(), 
                                key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache_data = dict(sorted_items[:500])

        content_cache_file = get_content_cache_file()
        with open(content_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[ERROR] 캐시 저장 실패: {e}")

# =============================================================================
# Chrome Driver 관리 - 리소스 최적화 강화 (기존 유지)
# =============================================================================

def get_chrome_driver():
    """Chrome 드라이버 초기화 - 리소스 최적화 및 안정성 강화"""
    options = Options()

    # 기본 최적화 옵션들
    basic_options = [
        '--headless', '--no-sandbox', '--disable-dev-shm-usage',
        '--disable-gpu', '--disable-extensions', '--disable-plugins',
        '--disable-images', '--window-size=1920,1080'
    ]
    
    # 추가 리소스 최적화 옵션
    performance_options = [
        '--memory-pressure-off', '--max_old_space_size=2048',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding', '--disable-features=TranslateUI',
        '--disable-default-apps', '--disable-web-security',
        '--disable-features=VizDisplayCompositor'
    ]
    
    # 봇 탐지 우회
    stealth_options = [
        '--disable-blink-features=AutomationControlled'
    ]
    
    for option_list in [basic_options, performance_options, stealth_options]:
        for option in option_list:
            options.add_argument(option)
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 랜덤 User-Agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')

    # 성능 최적화
    prefs = {
        'profile.default_content_setting_values': {
            'images': 2, 'plugins': 2, 'popups': 2,
            'geolocation': 2, 'notifications': 2, 'media_stream': 2
        }
    }
    options.add_experimental_option('prefs', prefs)

    # 3단계 폴백 메커니즘
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver', 
        '/snap/bin/chromium.chromedriver'
    ]

    for path in possible_paths:
        try:
            if os.path.exists(path):
                print(f"[DEBUG] ChromeDriver 시도: {path}")
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=options)
                print(f"[DEBUG] ChromeDriver 성공: {path}")
                return driver
        except Exception as e:
            error_manager.record_error(ErrorType.DRIVER, e, {'driver_path': path})
            print(f"[DEBUG] ChromeDriver 실패 {path}: {str(e)[:100]}...")
            continue

    # WebDriver Manager 시도
    try:
        print("[DEBUG] WebDriver Manager 시도")
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("[DEBUG] WebDriver Manager 성공")
        return driver
    except Exception as e:
        error_manager.record_error(ErrorType.DRIVER, e)
        print(f"[DEBUG] WebDriver Manager 실패: {str(e)[:100]}...")

    raise Exception("모든 ChromeDriver 초기화 방법이 실패했습니다.")

# =============================================================================
# URL 처리 유틸리티 (기존 유지)
# =============================================================================

def fix_url_bug(url):
    """URL 버그 수정 함수"""
    if not url:
        return url

    if url.startswith('ttps://'):
        url = 'h' + url
        print(f"[URL FIX] ttps → https: {url}")
    elif url.startswith('/'):
        if 'onstove.com' in url or 'epicseven' in url:
            url = 'https://page.onstove.com' + url
        elif 'ruliweb.com' in url:
            url = 'https://bbs.ruliweb.com' + url
        elif 'reddit.com' in url:
            url = 'https://www.reddit.com' + url
        print(f"[URL FIX] 상대경로 수정: {url}")
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        print(f"[URL FIX] 프로토콜 추가: {url}")

    return url

# =============================================================================
# 의미있는 본문 추출 함수 (기존 유지)
# =============================================================================

def extract_meaningful_content(text: str) -> str:
    """의미있는 본문 내용 추출 알고리즘"""
    if not text or len(text) < 30:
        return ""

    sentences = re.split(r'[.!?。！？]\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:100].strip()

    meaningful_sentences = []
    for sentence in sentences:
        if len(sentence) < 10:
            continue

        meaningless_patterns = [
            r'^[ㅋㅎㄷㅠㅜㅡ]+$',
            r'^[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?`~]+$',
            r'^\d+$',
            r'^(음|어|아|네|예|응|ㅇㅇ|ㅠㅠ|ㅜㅜ)$'
        ]

        if any(re.match(pattern, sentence) for pattern in meaningless_patterns):
            continue

        meaningful_keywords = [
            '버그', '오류', '문제', '에러', '안됨', '작동', '실행',
            '캐릭터', '스킬', '아티팩트', '장비', '던전', '아레나', 
            '길드', '이벤트', '업데이트', '패치', '밸런스', '너프',
            '게임', '플레이', '유저', '운영', '공지', '확률',
            '뽑기', '소환', '6성', '각성', '초월', '룬', '젬'
        ]

        score = sum(1 for keyword in meaningful_keywords if keyword in sentence)

        if score > 0 or len(sentence) >= 30:
            meaningful_sentences.append(sentence)

    if not meaningful_sentences:
        long_sentences = [s for s in sentences if len(s) >= 20]
        if long_sentences:
            return long_sentences[0]
        else:
            return sentences[0] if sentences else text[:100]

    result = meaningful_sentences[0]
    if len(result) < 50 and len(meaningful_sentences) > 1:
        result += ' ' + meaningful_sentences[1]
    if len(result) < 80 and len(meaningful_sentences) > 2:
        result += ' ' + meaningful_sentences[2]

    return result.strip()


# =============================================================================
# ✨ FIXED v4.4: 안전한 URL 해시 시스템 (SHA256 기반)
# =============================================================================

def get_safe_url_hash(url: str) -> str:
    """안전한 URL 해시 생성 (SHA256 기반, 충돌 방지)"""
    try:
        # SHA256 해시 생성
        url_bytes = url.encode('utf-8')
        hash_object = hashlib.sha256(url_bytes)
        
        # 16자리 해시 (충돌 확률 극소)
        safe_hash = hash_object.hexdigest()[:16]
        
        return safe_hash
        
    except Exception as e:
        error_manager.record_error(ErrorType.GENERAL, e, {'url': url[:100]})
        # 폴백: 기존 방식 (호환성)
        return str(hash(url) % (10**8))


# =============================================================================
# Stove 게시글 내용 추출 함수 (v4.4 안전한 해시 적용)
# =============================================================================

def get_stove_post_content(post_url: str, driver: webdriver.Chrome, 
                          source: str = "stove_korea_bug", 
                          schedule_type: str = "frequent") -> str:
    """Stove 게시글 내용 추출 - v4.4 안전한 해시 적용"""

    # 캐시 확인
    cache = load_content_cache()
    

    # ✨ FIXED v4.4: 안전한 해시 사용
    url_hash = get_safe_url_hash(post_url)
    


    if url_hash in cache:
        cached_item = cache[url_hash]
        cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
        if datetime.now() - cache_time < timedelta(hours=24):
            print(f"[CACHE] 캐시된 내용 사용: {post_url}")
            return cached_item.get('content', "게시글 내용을 확인할 수 없습니다.")

    content_summary = "게시글 내용을 확인할 수 없습니다."

    try:
        print(f"[DEBUG] 게시글 내용 추출 시도: {post_url}")

        wait_time = CrawlingSchedule.get_wait_time(schedule_type)
        driver.set_page_load_timeout(wait_time + 10)
        driver.get(post_url)

        print(f"[DEBUG] 페이지 로딩 대기 중... ({wait_time}초)")
        time.sleep(wait_time)

        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # 최적화된 스크롤링
        print("[DEBUG] 최적화된 스크롤링 시작...")
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        print("[DEBUG] 최적화된 스크롤링 완료")

        content_selectors = [
            'meta[data-vmid="description"]',
            'meta[name="description"]',
            'div.s-article-content',
            'div.s-article-content-text',
            'section.s-article-body',
            'div.s-board-content',
            '.article-content',
            '.post-content',
            '[class*="content"]'
        ]

        for i, selector in enumerate(content_selectors):
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        if selector.startswith('meta'):
                            raw_text = element.get_attribute('content').strip()
                        else:
                            raw_text = element.text.strip()

                        if not raw_text or len(raw_text) < 30:
                            continue

                        skip_keywords = [
                            'install stove', '스토브를 설치', '로그인이 필요', 
                            'javascript', '댓글', '공유', '좋아요', '추천', '신고',
                            '작성자', '작성일', '조회수', '첨부파일', '다운로드'
                        ]

                        if any(skip.lower() in raw_text.lower() for skip in skip_keywords):
                            continue

                        meaningful_content = extract_meaningful_content(raw_text)

                        if len(meaningful_content) >= 50:
                            if len(meaningful_content) > 150:
                                content_summary = meaningful_content[:147] + '...'
                            else:
                                content_summary = meaningful_content

                            print(f"[SUCCESS] 선택자 {i+1}/{len(content_selectors)} '{selector}'로 내용 추출 성공")
                            print(f"[CONTENT] {content_summary[:80]}...")
                            break

                    if content_summary != "게시글 내용을 확인할 수 없습니다.":
                        break

            except Exception as e:
                error_manager.record_error(ErrorType.PARSE, e, {'selector': selector})
                print(f"[DEBUG] 선택자 '{selector}' 실패: {e}")
                continue

        # 캐시 저장
        cache[url_hash] = {
            'content': content_summary,
            'timestamp': datetime.now().isoformat(),
            'url': post_url,
            'source': source
        }
        save_content_cache(cache)

    except TimeoutException as e:
        error_manager.record_error(ErrorType.NETWORK, e, {'url': post_url})
        print(f"[ERROR] 페이지 로딩 타임아웃: {post_url}")
        content_summary = "⏰ 게시글 로딩 시간 초과"
    except Exception as e:
        error_manager.record_error(ErrorType.GENERAL, e, {'url': post_url})
        print(f"[ERROR] 게시글 내용 추출 실패: {e}")
        content_summary = "🔗 게시글 내용 확인 실패"

    return content_summary

# =============================================================================
# 🚀 Stove 게시판 크롤링 + 즉시 처리 통합 (v4.4 강화)
# =============================================================================

def crawl_stove_board(board_url: str, source: str, force_crawl: bool = False, 
                     schedule_type: str = "frequent", region: str = "korea",
                     on_post_process: Optional[Callable[[Dict], None]] = None) -> List[Dict]:
    """
    Stove 게시판 크롤링 + 즉시 처리 통합 v4.4
    Master 요구사항: 게시글별 즉시 처리 (크롤링→감성분석→알림→마킹)
    """

    posts = []
    link_data = load_crawled_links()

    print(f"[INFO] {source} 크롤링 시작 - URL: {board_url}")
    print(f"[DEBUG] 기존 링크 수: {len(link_data['links'])}, Force Crawl: {force_crawl}")

    driver = None
    try:
        driver = get_chrome_driver()

        wait_time = CrawlingSchedule.get_wait_time(schedule_type)
        driver.set_page_load_timeout(wait_time + 10)
        driver.implicitly_wait(15)

        print(f"[DEBUG] 게시판 접속 중: {board_url}")
        driver.get(board_url)

        print(f"[DEBUG] 페이지 로딩 대기 중... ({wait_time}초)")
        time.sleep(wait_time)

        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(3)

        

        # ✨ ENHANCED v4.4: 관리된 디버그 파일 저장
        debug_filename = f"{source}_debug_selenium.html"
        debug_file_manager.save_debug_html(debug_filename, driver.page_source)
        


        # JavaScript로 게시글 정보 추출
        user_posts = driver.execute_script("""
            var userPosts = [];
            const selectors = [
                'section.s-board-item',
                'h3.s-board-title',
                '[class*="board-title"]',
                '[class*="post-title"]',
                'a[href*="/view/"]'
            ];

            var elements = [];
            var successful_selector = '';

            for (var i = 0; i < selectors.length; i++) {
                try {
                    elements = document.querySelectorAll(selectors[i]);
                    if (elements && elements.length > 0) {
                        successful_selector = selectors[i];
                        break;
                    }
                } catch (e) {
                    continue;
                }
            }

            if (!elements || elements.length === 0) {
                return [];
            }

            const officialIds = ['10518001', '10855687', '10855562', '10855132'];

            for (var i = 0; i < Math.min(elements.length, 20); i++) {
                var element = elements[i];