#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 파일 매니저 - 파일 잠금 및 안전한 접근 관리
JSON 파일 충돌 방지 및 원자적 파일 연산 보장

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
"""

import json
import os
import time
import fcntl
import tempfile
import shutil
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from config import config

logger = logging.getLogger(__name__)

class FileManager:
    """파일 안전 관리자"""
    
    def __init__(self):
        """파일 매니저 초기화"""
        self.lock_dir = Path(".file_locks")
        self.lock_dir.mkdir(exist_ok=True)
        logger.info("파일 매니저 초기화 완료")
    
    @contextmanager
    def file_lock(self, file_path: str, timeout: float = 30.0):
        """
        파일 잠금 컨텍스트 매니저
        
        Args:
            file_path: 잠금할 파일 경로
            timeout: 잠금 대기 시간 (초)
        """
        lock_file = self.lock_dir / f"{Path(file_path).name}.lock"
        
        acquired = False
        start_time = time.time()
        
        try:
            # 잠금 파일 생성 및 잠금 시도
            with open(lock_file, 'w') as f:
                while time.time() - start_time < timeout:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        logger.debug(f"파일 잠금 획득: {file_path}")
                        break
                    except IOError:
                        time.sleep(0.1)
                
                if not acquired:
                    raise TimeoutError(f"파일 잠금 획득 실패: {file_path} (타임아웃: {timeout}초)")
                
                yield
                
        finally:
            if acquired:
                try:
                    lock_file.unlink()
                    logger.debug(f"파일 잠금 해제: {file_path}")
                except FileNotFoundError:
                    pass
    
    def safe_load_json(self, file_path: str, default: Any = None) -> Any:
        """
        안전한 JSON 파일 로드
        
        Args:
            file_path: JSON 파일 경로
            default: 파일이 없을 때 반환할 기본값
        """
        with self.file_lock(file_path):
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.debug(f"JSON 파일 로드 성공: {file_path}")
                    return data
                else:
                    logger.debug(f"JSON 파일 없음, 기본값 반환: {file_path}")
                    return default
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"JSON 파일 로드 실패: {file_path}, 에러: {e}")
                return default
    
    def safe_save_json(self, file_path: str, data: Any, backup: bool = True) -> bool:
        """
        안전한 JSON 파일 저장 (원자적 쓰기)
        
        Args:
            file_path: JSON 파일 경로
            data: 저장할 데이터
            backup: 백업 파일 생성 여부
        """
        with self.file_lock(file_path):
            try:
                # 백업 파일 생성
                if backup and os.path.exists(file_path):
                    backup_path = f"{file_path}.backup"
                    shutil.copy2(file_path, backup_path)
                
                # 임시 파일에 먼저 저장
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    suffix='.tmp',
                    dir=os.path.dirname(file_path) or '.',
                    delete=False
                )
                
                with temp_file:
                    json.dump(data, temp_file, ensure_ascii=False, indent=2)
                
                # 원자적 이동
                shutil.move(temp_file.name, file_path)
                
                logger.debug(f"JSON 파일 저장 성공: {file_path}")
                return True
                
            except Exception as e:
                logger.error(f"JSON 파일 저장 실패: {file_path}, 에러: {e}")
                # 임시 파일 정리
                try:
                    if 'temp_file' in locals():
                        os.unlink(temp_file.name)
                except:
                    pass
                return False
    
    def cleanup_old_files(self, max_age_days: int = 30):
        """
        오래된 파일들 정리
        
        Args:
            max_age_days: 최대 보존 일수
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        cleanup_patterns = [
            "*.backup",
            "*.tmp",
            "debug/*.html",
            "debug/*.log"
        ]
        
        cleaned_count = 0
        for pattern in cleanup_patterns:
            for file_path in Path(".").glob(pattern):
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"오래된 파일 삭제: {file_path}")
                except Exception as e:
                    logger.error(f"파일 삭제 실패: {file_path}, 에러: {e}")
        
        logger.info(f"파일 정리 완료: {cleaned_count}개 파일 삭제")
    
    def get_file_status(self, file_path: str) -> Dict[str, Any]:
        """
        파일 상태 정보 조회
        
        Args:
            file_path: 파일 경로
        """
        try:
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                return {
                    'exists': True,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'readable': os.access(file_path, os.R_OK),
                    'writable': os.access(file_path, os.W_OK)
                }
            else:
                return {
                    'exists': False,
                    'size': 0,
                    'modified': None,
                    'readable': False,
                    'writable': False
                }
        except Exception as e:
            logger.error(f"파일 상태 조회 실패: {file_path}, 에러: {e}")
            return {
                'exists': False,
                'size': 0,
                'modified': None,
                'readable': False,
                'writable': False,
                'error': str(e)
            }

# 전역 파일 매니저 인스턴스
file_manager = FileManager()

# 편의 함수들
def load_json(file_path: str, default: Any = None) -> Any:
    """JSON 파일 로드 (편의 함수)"""
    return file_manager.safe_load_json(file_path, default)

def save_json(file_path: str, data: Any, backup: bool = True) -> bool:
    """JSON 파일 저장 (편의 함수)"""
    return file_manager.safe_save_json(file_path, data, backup)

def with_file_lock(file_path: str, timeout: float = 30.0):
    """파일 잠금 데코레이터"""
    return file_manager.file_lock(file_path, timeout)
