#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 감성 데이터 관리자 v3.2 - 즉시 저장 시스템 구현
감성 데이터 수집, 분석, 관리 및 트렌드 추적 시스템

주요 특징:
- 게시글별 즉시 저장 시스템 ✨NEW✨
- 감성 데이터 수집 및 저장
- 감성 트렌드 분석 및 패턴 탐지
- 감성 데이터 정제 및 관리
- 시간대별 감성 분포 분석
- 키워드 기반 감성 분석
- 사이트별 감성 비교
- 일간 리포트 데이터 구조 최적화 ✨NEW✨
- 리포트 생성기와 연동

Author: Epic7 Monitoring Team
Version: 3.2 (즉시 저장 시스템 구현)
Date: 2025-07-24
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, Counter, deque
import logging

# 통계 및 수학 연산
import statistics
from math import sqrt

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 감성 데이터 관리 설정
# =============================================================================

class SentimentConfig:
    """감성 데이터 관리 설정"""
    
    # 파일 경로
    SENTIMENT_DATA_FILE = "sentiment_data.json"
    SENTIMENT_CACHE_FILE = "sentiment_cache.json"
    SENTIMENT_TRENDS_FILE = "sentiment_trends.json"
    SENTIMENT_KEYWORDS_FILE = "sentiment_keywords.json"
    
    # 데이터 보존 기간
    DATA_RETENTION_DAYS = 90
    CACHE_RETENTION_HOURS = 72
    TRENDS_RETENTION_DAYS = 30
    
    # 분석 설정
    MIN_CONFIDENCE_THRESHOLD = 0.6
    KEYWORD_MIN_FREQUENCY = 3
    TREND_ANALYSIS_WINDOW = 7  # 7일 단위 트렌드
    
    # 통계 설정
    TOP_KEYWORDS_LIMIT = 20
    SENTIMENT_CATEGORIES = ['positive', 'negative', 'neutral']

# =============================================================================
# Epic7 감성 데이터 관리자 v3.2 - 즉시 저장 시스템
# =============================================================================

class Epic7SentimentManager:
    """Epic7 감성 데이터 관리자 v3.2 - 즉시 저장 시스템"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        감성 데이터 관리자 초기화
        
        Args:
            config: 사용자 정의 설정 (선택사항)
        """
        self.config = config or SentimentConfig()
        
        # 순환 임포트 방지를 위한 지연 임포트
        try:
            from classifier import Epic7Classifier
            self.classifier = Epic7Classifier()
        except ImportError as e:
            logger.warning(f"Classifier 임포트 실패: {e}")
            self.classifier = None
        
        # 데이터 구조 초기화
        self.sentiment_data = self.load_sentiment_data()
        self.sentiment_cache = self.load_sentiment_cache()
        self.sentiment_trends = self.load_sentiment_trends()
        self.sentiment_keywords = self.load_sentiment_keywords()
        
        # 통계 초기화
        self.stats = {
            'total_posts': 0,
            'processed_posts': 0,
            'immediate_saves': 0,  # ✨ 즉시 저장 통계
            'batch_saves': 0,      # ✨ 일괄 저장 통계
            'errors': 0,
            'start_time': datetime.now().isoformat()
        }
        
        logger.info(f"Epic7 감성 데이터 관리자 v3.2 초기화 완료 - 즉시 저장 시스템 활성화")
    
    # ✨ NEW: 즉시 저장 시스템 구현
    def save_sentiment_immediately(self, sentiment_result: Dict) -> bool:
        """
        ✨ 개별 게시글 감성 분석 결과 즉시 저장
        
        Args:
            sentiment_result: 감성 분석 결과 딕셔너리
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 1. 기본 검증
            if not sentiment_result or not sentiment_result.get('url'):
                logger.warning("❌ 유효하지 않은 감성 분석 결과")
                return False
            
            # 2. 타임스탬프 추가
            sentiment_result['processed_at'] = datetime.now().isoformat()
            sentiment_result['save_method'] = 'immediate'  # 즉시 저장 표시
            
            # 3. 메인 데이터에 추가
            self.sentiment_data['posts'].append(sentiment_result)
            
            # 4. 통계 즉시 업데이트
            self._update_statistics_immediately(sentiment_result)
            
            # 5. 키워드 즉시 업데이트
            self._update_keywords_immediately(sentiment_result)
            
            # 6. 일간 리포트 데이터 즉시 갱신 ✨
            self._update_daily_reports_immediately(sentiment_result)
            
            # 7. 데이터 정리 (용량 관리)
            self._cleanup_old_data()
            
            # 8. 파일 즉시 저장
            success = self.save_sentiment_data_file()
            
            if success:
                self.stats['immediate_saves'] += 1
                self.stats['processed_posts'] += 1
                
                post_title = sentiment_result.get('title', 'Unknown')[:50]
                sentiment = sentiment_result.get('sentiment', 'neutral')
                confidence = sentiment_result.get('confidence', 0.0)
                
                logger.info(f"💾 즉시 저장 성공: {post_title}... (감성: {sentiment}, 신뢰도: {confidence:.2f})")
                
                # 9. 캐시도 즉시 업데이트
                self._update_cache_immediately(sentiment_result)
                
                return True
            else:
                logger.error("💥 즉시 저장 파일 쓰기 실패")
                return False
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"💥 즉시 저장 실패: {e}")
            return False
    
    # ✨ NEW: 일간 리포트 데이터 구조 최적화
    def _update_daily_reports_immediately(self, sentiment_result: Dict) -> None:
        """
        ✨ 일간 리포트 데이터 즉시 갱신 (최적화된 구조)
        
        Args:
            sentiment_result: 감성 분석 결과
        """
        try:
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # daily_reports 구조 초기화
            if 'daily_reports' not in self.sentiment_data:
                self.sentiment_data['daily_reports'] = {}
            
            if current_date not in self.sentiment_data['daily_reports']:
                self.sentiment_data['daily_reports'][current_date] = {
                    'total_posts': 0,
                    'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
                    'average_confidence': 0.0,
                    'top_keywords': {},
                    'site_distribution': {},
                    'hourly_distribution': {},
                    'trend_direction': 'neutral',
                    'confidence_sum': 0.0,  # 평균 계산용
                    'last_updated': datetime.now().isoformat()
                }
            
            daily_report = self.sentiment_data['daily_reports'][current_date]
            
            # 기본 통계 업데이트
            daily_report['total_posts'] += 1
            
            # 감성 분포 업데이트
            sentiment = sentiment_result.get('sentiment', 'neutral')
            if sentiment in daily_report['sentiment_distribution']:
                daily_report['sentiment_distribution'][sentiment] += 1
            
            # 평균 신뢰도 업데이트
            confidence = sentiment_result.get('confidence', 0.0)
            daily_report['confidence_sum'] += confidence
            daily_report['average_confidence'] = daily_report['confidence_sum'] / daily_report['total_posts']
            
            # 사이트별 분포 업데이트
            source = sentiment_result.get('source', 'unknown')
            if source in daily_report['site_distribution']:
                daily_report['site_distribution'][source] += 1
            else:
                daily_report['site_distribution'][source] = 1
            
            # 시간대별 분포 업데이트
            current_hour = datetime.now().strftime('%H')
            if current_hour in daily_report['hourly_distribution']:
                daily_report['hourly_distribution'][current_hour] += 1
            else:
                daily_report['hourly_distribution'][current_hour] = 1
            
            # 키워드 업데이트 (제목에서 추출)
            title = sentiment_result.get('title', '')
            keywords = self._extract_keywords_from_text(title)
            for keyword in keywords:
                if keyword in daily_report['top_keywords']:
                    daily_report['top_keywords'][keyword] += 1
                else:
                    daily_report['top_keywords'][keyword] = 1
            
            # 상위 키워드만 유지 (성능 최적화)
            if len(daily_report['top_keywords']) > self.config.TOP_KEYWORDS_LIMIT:
                sorted_keywords = sorted(
                    daily_report['top_keywords'].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:self.config.TOP_KEYWORDS_LIMIT]
                daily_report['top_keywords'] = dict(sorted_keywords)
            
            # 트렌드 방향 계산 (간단한 버전)
            pos_ratio = daily_report['sentiment_distribution']['positive'] / max(1, daily_report['total_posts'])
            neg_ratio = daily_report['sentiment_distribution']['negative'] / max(1, daily_report['total_posts'])
            
            if pos_ratio > neg_ratio + 0.1:
                daily_report['trend_direction'] = 'positive'
            elif neg_ratio > pos_ratio + 0.1:
                daily_report['trend_direction'] = 'negative'
            else:
                daily_report['trend_direction'] = 'neutral'
            
            # 업데이트 시간 갱신
            daily_report['last_updated'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"일간 리포트 업데이트 실패: {e}")
    
    def _update_statistics_immediately(self, sentiment_result: Dict) -> None:
        """통계 즉시 업데이트"""
        try:
            # 기존 통계 구조 유지하면서 업데이트
            if 'statistics' not in self.sentiment_data:
                self.sentiment_data['statistics'] = {
                    'total_posts': 0,
                    'sentiment_counts': {'positive': 0, 'negative': 0, 'neutral': 0},
                    'average_confidence': 0.0,
                    'site_stats': {},
                    'last_updated': datetime.now().isoformat()
                }
            
            stats = self.sentiment_data['statistics']
            stats['total_posts'] += 1
            
            sentiment = sentiment_result.get('sentiment', 'neutral')
            if sentiment in stats['sentiment_counts']:
                stats['sentiment_counts'][sentiment] += 1
            
            # 사이트별 통계
            source = sentiment_result.get('source', 'unknown')
            if source not in stats['site_stats']:
                stats['site_stats'][source] = {'count': 0, 'sentiments': {'positive': 0, 'negative': 0, 'neutral': 0}}
            
            stats['site_stats'][source]['count'] += 1
            stats['site_stats'][source]['sentiments'][sentiment] += 1
            
            stats['last_updated'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"통계 업데이트 실패: {e}")
    
    def _update_keywords_immediately(self, sentiment_result: Dict) -> None:
        """키워드 즉시 업데이트"""
        try:
            title = sentiment_result.get('title', '')
            content = sentiment_result.get('content', '')
            
            keywords = self._extract_keywords_from_text(title + ' ' + content)
            
            if 'keywords' not in self.sentiment_data:
                self.sentiment_data['keywords'] = {}
            
            sentiment = sentiment_result.get('sentiment', 'neutral')
            
            for keyword in keywords:
                if keyword not in self.sentiment_data['keywords']:
                    self.sentiment_data['keywords'][keyword] = {
                        'total_count': 0,
                        'sentiments': {'positive': 0, 'negative': 0, 'neutral': 0}
                    }
                
                self.sentiment_data['keywords'][keyword]['total_count'] += 1
                self.sentiment_data['keywords'][keyword]['sentiments'][sentiment] += 1
            
        except Exception as e:
            logger.error(f"키워드 업데이트 실패: {e}")
    
    def _update_cache_immediately(self, sentiment_result: Dict) -> None:
        """캐시 즉시 업데이트"""
        try:
            url = sentiment_result.get('url', '')
            if url:
                self.sentiment_cache[url] = {
                    'sentiment': sentiment_result.get('sentiment'),
                    'confidence': sentiment_result.get('confidence'),
                    'cached_at': datetime.now().isoformat(),
                    'save_method': 'immediate'
                }
                
                # 캐시 파일 저장
                self.save_sentiment_cache()
                
        except Exception as e:
            logger.error(f"캐시 업데이트 실패: {e}")
    
    # ✨ NEW: 일간 요약 조회 함수
    def get_daily_summary(self, date: str = None) -> Dict:
        """
        ✨ 특정 날짜의 일간 요약 조회
        
        Args:
            date: 조회할 날짜 (YYYY-MM-DD), None이면 오늘
            
        Returns:
            Dict: 일간 요약 데이터
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        daily_reports = self.sentiment_data.get('daily_reports', {})
        
        if date in daily_reports:
            summary = daily_reports[date].copy()
            
            # 추가 계산된 지표들
            total = summary.get('total_posts', 0)
            if total > 0:
                dist = summary.get('sentiment_distribution', {})
                summary['sentiment_percentages'] = {
                    sentiment: (count / total * 100) 
                    for sentiment, count in dist.items()
                }
            
            return summary
        else:
            return {
                'date': date,
                'total_posts': 0,
                'message': '해당 날짜의 데이터가 없습니다.'
            }
    
    # 기존 함수들 (완전 보존)
    def load_sentiment_data(self) -> Dict:
        """감성 데이터 로드"""
        try:
            if os.path.exists(self.config.SENTIMENT_DATA_FILE):
                with open(self.config.SENTIMENT_DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"감성 데이터 로드 완료: {len(data.get('posts', []))}개 게시글")
                    return data
            else:
                logger.info("새로운 감성 데이터 파일 생성")
                return {
                    'posts': [],
                    'statistics': {},
                    'daily_reports': {},  # ✨ 새로운 구조
                    'keywords': {},
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'version': '3.2'  # ✨ 버전 표시
                }
        except Exception as e:
            logger.error(f"감성 데이터 로드 실패: {e}")
            return {'posts': [], 'statistics': {}, 'daily_reports': {}, 'keywords': {}}
    
    def save_sentiment_data_file(self) -> bool:
        """감성 데이터 저장 (기존 방식 + 즉시 저장 지원)"""
        try:
            # 메타데이터 업데이트
            self.sentiment_data['last_updated'] = datetime.now().isoformat()
            self.sentiment_data['total_posts'] = len(self.sentiment_data.get('posts', []))
            self.sentiment_data['version'] = '3.2'
            
            # 파일 저장
            with open(self.config.SENTIMENT_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"감성 데이터 저장 실패: {e}")
            return False
    
    def load_sentiment_cache(self) -> Dict:
        """감성 캐시 로드"""
        try:
            if os.path.exists(self.config.SENTIMENT_CACHE_FILE):
                with open(self.config.SENTIMENT_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"감성 캐시 로드 실패: {e}")
            return {}
    
    def save_sentiment_cache(self) -> bool:
        """감성 캐시 저장"""
        try:
            with open(self.config.SENTIMENT_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_cache, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"감성 캐시 저장 실패: {e}")
            return False
    
    def load_sentiment_trends(self) -> Dict:
        """감성 트렌드 로드"""
        try:
            if os.path.exists(self.config.SENTIMENT_TRENDS_FILE):
                with open(self.config.SENTIMENT_TRENDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"감성 트렌드 로드 실패: {e}")
            return {}
    
    def load_sentiment_keywords(self) -> Dict:
        """감성 키워드 로드"""
        try:
            if os.path.exists(self.config.SENTIMENT_KEYWORDS_FILE):
                with open(self.config.SENTIMENT_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"감성 키워드 로드 실패: {e}")
            return {}
    
    def process_post_sentiment(self, post: Dict) -> Dict:
        """
        개별 게시글 감성 분석 처리 (기존 함수 유지)
        
        Args:
            post: 게시글 데이터
            
        Returns:
            Dict: 감성 분석 결과
        """
        try:
            # 기본 데이터 검증
            if not post or not post.get('title'):
                return {}
            
            # 캐시 확인
            url = post.get('url', '')
            if url in self.sentiment_cache:
                cached_result = self.sentiment_cache[url]
                # 캐시된 결과에 최신 메타데이터 추가
                cached_result.update({
                    'title': post.get('title'),
                    'url': url,
                    'source': post.get('source'),
                    'from_cache': True
                })
                return cached_result
            
            # 분류기를 통한 감성 분석
            if self.classifier:
                classification_result = self.classifier.classify_post(post)
                
                # 감성 분석 결과 추출
                sentiment_analysis = classification_result.get('sentiment_analysis', {})
                sentiment = sentiment_analysis.get('sentiment', 'neutral')
                confidence = sentiment_analysis.get('confidence', 0.0)
            else:
                # 폴백: 기본 감성 분석
                sentiment = 'neutral'
                confidence = 0.5
                classification_result = {}
            
            # 결과 구성
            result = {
                'title': post.get('title'),
                'url': url,
                'content': post.get('content', '')[:500],  # 500자 제한
                'source': post.get('source'),
                'timestamp': post.get('timestamp', datetime.now().isoformat()),
                'sentiment': sentiment,
                'confidence': confidence,
                'classification': classification_result,
                'processed_at': datetime.now().isoformat(),
                'from_cache': False
            }
            
            return result
            
        except Exception as e:
            logger.error(f"게시글 감성 분석 실패: {e}")
            return {}
    
    # ✨ MODIFIED: 기존 일괄 저장 함수 (하위 호환성 보장)
    def collect_sentiment_data(self, posts: List[Dict], save_method: str = 'batch') -> int:
        """
        감성 데이터 수집 (일괄 처리 + 즉시 처리 지원)
        
        Args:
            posts: 처리할 게시글 목록
            save_method: 저장 방식 ('batch' 또는 'immediate')
            
        Returns:
            int: 처리된 게시글 수
        """
        if not posts:
            logger.info("처리할 게시글이 없습니다.")
            return 0
        
        processed_count = 0
        results = []
        
        logger.info(f"감성 데이터 수집 시작: {len(posts)}개 게시글 ({save_method} 모드)")
        
        for i, post in enumerate(posts, 1):
            try:
                # 개별 게시글 감성 분석
                result = self.process_post_sentiment(post)
                
                if result:
                    if save_method == 'immediate':
                        # ✨ 즉시 저장 모드
                        if self.save_sentiment_immediately(result):
                            processed_count += 1
                            logger.info(f"즉시 처리 완료 ({i}/{len(posts)}): {result.get('title', '')[:50]}...")
                        else:
                            logger.error(f"즉시 저장 실패 ({i}/{len(posts)})")
                    else:
                        # 기존 일괄 처리 모드
                        results.append(result)
                        processed_count += 1
                        logger.info(f"일괄 처리 대기 ({i}/{len(posts)}): {result.get('title', '')[:50]}...")
                
                self.stats['total_posts'] += 1
                
            except Exception as e:
                logger.error(f"게시글 {i} 처리 실패: {e}")
                self.stats['errors'] += 1
        
        # 일괄 처리 모드에서 최종 저장
        if save_method == 'batch' and results:
            # 기존 방식으로 일괄 저장
            self.sentiment_data['posts'].extend(results)
            
            # 통계 및 키워드 업데이트
            for result in results:
                self._update_statistics_immediately(result)
                self._update_keywords_immediately(result)
                self._update_daily_reports_immediately(result)
            
            # 데이터 정리 및 저장
            self._cleanup_old_data()
            if self.save_sentiment_data_file():
                self.stats['batch_saves'] += 1
                logger.info(f"일괄 저장 완료: {len(results)}개 게시글")
            else:
                logger.error("일괄 저장 실패")
        
        logger.info(f"감성 데이터 수집 완료: {processed_count}개 처리됨 ({save_method} 모드)")
        return processed_count
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """텍스트에서 키워드 추출"""
        if not text:
            return []
        
        # Epic7 관련 키워드 필터링
        epic7_keywords = [
            '버그', '오류', '문제', '에러', '안됨', '작동', '실행',
            '캐릭터', '스킬', '아티팩트', '장비', '던전', '아레나',
            '길드', '이벤트', '업데이트', '패치', '밸런스', '너프',
            '게임', '플레이', '유저', '운영', '공지', '확률',
            '뽑기', '소환', '6성', '각성', '초월', '룬', '젬'
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in epic7_keywords:
            if keyword in text_lower or keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords[:10]  # 최대 10개
    
    def _cleanup_old_data(self) -> None:
        """오래된 데이터 정리"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.DATA_RETENTION_DAYS)
            cutoff_iso = cutoff_date.isoformat()
            
            # 오래된 게시글 제거
            original_count = len(self.sentiment_data.get('posts', []))
            self.sentiment_data['posts'] = [
                post for post in self.sentiment_data.get('posts', [])
                if post.get('processed_at', '') > cutoff_iso
            ]
            
            cleaned_count = original_count - len(self.sentiment_data['posts'])
            if cleaned_count > 0:
                logger.info(f"오래된 데이터 정리: {cleaned_count}개 게시글 제거")
            
            # 오래된 일간 리포트 정리
            if 'daily_reports' in self.sentiment_data:
                cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
                old_dates = [
                    date for date in self.sentiment_data['daily_reports'].keys()
                    if date < cutoff_date_str
                ]
                
                for date in old_dates:
                    del self.sentiment_data['daily_reports'][date]
                
                if old_dates:
                    logger.info(f"오래된 일간 리포트 정리: {len(old_dates)}개 날짜")
            
        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")
    
    def get_statistics_summary(self) -> Dict:
        """통계 요약 반환"""
        return {
            'runtime_stats': self.stats,
            'data_stats': self.sentiment_data.get('statistics', {}),
            'total_posts': len(self.sentiment_data.get('posts', [])),
            'daily_reports_count': len(self.sentiment_data.get('daily_reports', {})),
            'keywords_count': len(self.sentiment_data.get('keywords', {})),
            'cache_size': len(self.sentiment_cache),
            'last_updated': self.sentiment_data.get('last_updated'),
            'version': '3.2'
        }

# =============================================================================
# 편의 함수들 (외부 호출용) - 기존 유지
# =============================================================================

def save_sentiment_data_immediately(post_data: Dict) -> bool:
    """
    편의 함수: 개별 게시글 즉시 저장
    
    Args:
        post_data: 게시글 데이터 또는 감성 분석 결과
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        manager = Epic7SentimentManager()
        
        # 게시글 데이터인 경우 감성 분석 먼저 수행
        if 'sentiment' not in post_data:
            sentiment_result = manager.process_post_sentiment(post_data)
            if not sentiment_result:
                return False
        else:
            sentiment_result = post_data
        
        # 즉시 저장
        return manager.save_sentiment_immediately(sentiment_result)
        
    except Exception as e:
        logger.error(f"편의 함수 즉시 저장 실패: {e}")
        return False

def get_today_sentiment_summary() -> Dict:
    """
    편의 함수: 오늘의 감성 요약 조회
    
    Returns:
        Dict: 오늘의 감성 요약
    """
    try:
        manager = Epic7SentimentManager()
        return manager.get_daily_summary()
    except Exception as e:
        logger.error(f"오늘 요약 조회 실패: {e}")
        return {}
      
if __name__ == "__main__":
    main()
# =============================================================================
# 하위 호환성 보장 함수들 (monitor_bugs.py와의 인터페이스) ✨FIXED✨
# =============================================================================

def save_sentiment_data(posts: List[Dict]) -> bool:
    """
    하위 호환성 함수: monitor_bugs.py에서 호출하는 save_sentiment_data
    
    Args:
        posts: 게시글 목록 (감성 분석 결과 포함)
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        if not posts:
            return True
        
        manager = Epic7SentimentManager()
        
        # 즉시 저장 모드로 처리
        success_count = 0
        for post in posts:
            # 감성 분석이 안 된 경우 먼저 처리
            if 'sentiment' not in post:
                result = manager.process_post_sentiment(post)
                if result:
                    post.update(result)
            
            if manager.save_sentiment_immediately(post):
                success_count += 1
        
        logger.info(f"하위 호환 저장 완료: {success_count}/{len(posts)}개")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"하위 호환 저장 실패: {e}")
        return False

def get_sentiment_summary() -> Dict:
    """
    하위 호환성 함수: monitor_bugs.py에서 호출하는 get_sentiment_summary
    
    Returns:
        Dict: 감성 요약 데이터
    """
    try:
        manager = Epic7SentimentManager()
        
        # 오늘의 일간 요약 반환
        daily_summary = manager.get_daily_summary()
        
        # monitor_bugs.py가 기대하는 형식으로 변환
        return {
            "total_posts": daily_summary.get("total_posts", 0),
            "sentiment_distribution": daily_summary.get("sentiment_distribution", {}),
            "time_period": "today",
            "timestamp": datetime.now().isoformat(),
            "daily_data": daily_summary  # 추가 정보
        }
        
    except Exception as e:
        logger.error(f"하위 호환 요약 실패: {e}")
        return {
            "total_posts": 0,
            "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
            "time_period": "today",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# =============================================================================
# 메인 실행 부분 (기존 유지)
# =============================================================================

def main():
    """메인 실행 함수"""
    try:
        logger.info("Epic7 감성 데이터 관리자 v3.2 시작")
        
        # 관리자 초기화
        manager = Epic7SentimentManager()
        
        # 테스트용 게시글 데이터 수집 (실제 사용시에는 crawler에서 받아옴)
        # 순환 임포트 방지를 위한 지연 임포트
        try:
            from crawler import get_all_posts_for_report
            posts = get_all_posts_for_report()
        except ImportError as e:
            logger.warning(f"Crawler 임포트 실패: {e} - 테스트 모드로 진행")
            posts = []
        
        if posts:
            # 기본적으로 일괄 처리 (하위 호환성)
            processed_count = manager.collect_sentiment_data(posts, save_method='batch')
            logger.info(f"감성 데이터 처리 완료: {processed_count}개")
            
            # 통계 출력
            stats = manager.get_statistics_summary()
            logger.info(f"처리 통계: {stats}")
            
            # 오늘의 요약
            today_summary = manager.get_daily_summary()
            logger.info(f"오늘의 감성 요약: {today_summary}")
        else:
            logger.info("처리할 게시글이 없습니다.")
        
    except Exception as e:
        logger.error(f"메인 실행 중 오류: {e}")