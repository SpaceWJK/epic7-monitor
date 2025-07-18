#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 감성 데이터 관리자 v3.1
감성 데이터 수집, 분석, 관리 및 트렌드 추적 시스템

주요 특징:
- 감성 데이터 수집 및 저장
- 감성 트렌드 분석 및 패턴 탐지
- 감성 데이터 정제 및 관리
- 시간대별 감성 분포 분석
- 키워드 기반 감성 분석
- 사이트별 감성 비교
- 리포트 생성기와 연동

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
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

# 로컬 모듈 임포트
from classifier import Epic7Classifier
from crawler import load_content_cache, get_all_posts_for_report

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 감성 데이터 관리 설정
# =============================================================================

class SentimentConfig:
    """감성 데이터 관리 설정"""
    
    # 데이터 파일 경로
    SENTIMENT_DATA_FILE = "sentiment_data.json"
    SENTIMENT_CACHE_FILE = "sentiment_cache.json"
    SENTIMENT_TRENDS_FILE = "sentiment_trends.json"
    SENTIMENT_KEYWORDS_FILE = "sentiment_keywords.json"
    
    # 데이터 보존 기간
    MAX_DATA_DAYS = 90          # 최대 90일간 데이터 보존
    TREND_ANALYSIS_DAYS = 30    # 트렌드 분석 기간
    PATTERN_ANALYSIS_DAYS = 14  # 패턴 분석 기간
    
    # 감성 분석 임계값
    POSITIVE_THRESHOLD = 0.3
    NEGATIVE_THRESHOLD = 0.3
    NEUTRAL_THRESHOLD = 0.5
    
    # 트렌드 분석 설정
    TREND_SMOOTHING_WINDOW = 5  # 이동평균 윈도우
    VOLATILITY_THRESHOLD = 0.2  # 변동성 임계값
    
    # 키워드 분석 설정
    MIN_KEYWORD_FREQUENCY = 3   # 최소 키워드 빈도
    MAX_KEYWORDS_PER_CATEGORY = 20  # 카테고리당 최대 키워드 수
    
    # 알림 설정
    SENTIMENT_ALERT_THRESHOLD = -30  # 감성 점수 알림 임계값
    VOLATILITY_ALERT_THRESHOLD = 0.5  # 변동성 알림 임계값

class SentimentDataManager:
    """Epic7 감성 데이터 관리자"""
    
    def __init__(self):
        """감성 데이터 관리자 초기화"""
        self.classifier = Epic7Classifier()
        self.sentiment_data = self.load_sentiment_data()
        self.sentiment_cache = self.load_sentiment_cache()
        self.sentiment_trends = self.load_sentiment_trends()
        self.sentiment_keywords = self.load_sentiment_keywords()
        
        # 통계 초기화
        self.stats = {
            'total_processed': 0,
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'trend_points': 0,
            'patterns_detected': 0,
            'last_updated': datetime.now().isoformat()
        }
        
        logger.info("Epic7 감성 데이터 관리자 v3.1 초기화 완료")
    
    def load_sentiment_data(self) -> Dict:
        """감성 데이터 로드"""
        if os.path.exists(SentimentConfig.SENTIMENT_DATA_FILE):
            try:
                with open(SentimentConfig.SENTIMENT_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"감성 데이터 로드 실패: {e}")
        
        return {
            'posts': [],
            'daily_stats': {},
            'hourly_stats': {},
            'site_stats': {},
            'keyword_stats': {},
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
    
    def save_sentiment_data(self) -> bool:
        """감성 데이터 저장"""
        try:
            # 데이터 정리 (90일 이상 된 데이터 제거)
            self._cleanup_old_data()
            
            # 마지막 업데이트 시간 갱신
            self.sentiment_data['last_updated'] = datetime.now().isoformat()
            
            with open(SentimentConfig.SENTIMENT_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_data, f, ensure_ascii=False, indent=2)
            
            logger.info("감성 데이터 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"감성 데이터 저장 실패: {e}")
            return False
    
    def load_sentiment_cache(self) -> Dict:
        """감성 캐시 로드"""
        if os.path.exists(SentimentConfig.SENTIMENT_CACHE_FILE):
            try:
                with open(SentimentConfig.SENTIMENT_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"감성 캐시 로드 실패: {e}")
        
        return {
            'processed_posts': {},
            'sentiment_scores': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def save_sentiment_cache(self) -> bool:
        """감성 캐시 저장"""
        try:
            # 캐시 크기 제한 (최대 5000개)
            if len(self.sentiment_cache['processed_posts']) > 5000:
                # 최근 데이터 5000개만 유지
                items = list(self.sentiment_cache['processed_posts'].items())
                sorted_items = sorted(items, key=lambda x: x[1].get('timestamp', ''), reverse=True)
                self.sentiment_cache['processed_posts'] = dict(sorted_items[:5000])
            
            self.sentiment_cache['last_updated'] = datetime.now().isoformat()
            
            with open(SentimentConfig.SENTIMENT_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_cache, f, ensure_ascii=False, indent=2)
            
            logger.info("감성 캐시 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"감성 캐시 저장 실패: {e}")
            return False
    
    def load_sentiment_trends(self) -> Dict:
        """감성 트렌드 로드"""
        if os.path.exists(SentimentConfig.SENTIMENT_TRENDS_FILE):
            try:
                with open(SentimentConfig.SENTIMENT_TRENDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"감성 트렌드 로드 실패: {e}")
        
        return {
            'daily_trends': {},
            'hourly_trends': {},
            'weekly_trends': {},
            'moving_averages': {},
            'volatility_data': {},
            'pattern_data': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def save_sentiment_trends(self) -> bool:
        """감성 트렌드 저장"""
        try:
            self.sentiment_trends['last_updated'] = datetime.now().isoformat()
            
            with open(SentimentConfig.SENTIMENT_TRENDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_trends, f, ensure_ascii=False, indent=2)
            
            logger.info("감성 트렌드 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"감성 트렌드 저장 실패: {e}")
            return False
    
    def load_sentiment_keywords(self) -> Dict:
        """감성 키워드 로드"""
        if os.path.exists(SentimentConfig.SENTIMENT_KEYWORDS_FILE):
            try:
                with open(SentimentConfig.SENTIMENT_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"감성 키워드 로드 실패: {e}")
        
        return {
            'positive_keywords': {},
            'negative_keywords': {},
            'neutral_keywords': {},
            'trending_keywords': {},
            'keyword_trends': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def save_sentiment_keywords(self) -> bool:
        """감성 키워드 저장"""
        try:
            self.sentiment_keywords['last_updated'] = datetime.now().isoformat()
            
            with open(SentimentConfig.SENTIMENT_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sentiment_keywords, f, ensure_ascii=False, indent=2)
            
            logger.info("감성 키워드 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"감성 키워드 저장 실패: {e}")
            return False
    
    def _cleanup_old_data(self):
        """오래된 데이터 정리"""
        cutoff_date = datetime.now() - timedelta(days=SentimentConfig.MAX_DATA_DAYS)
        cutoff_str = cutoff_date.isoformat()
        
        # 게시글 데이터 정리
        self.sentiment_data['posts'] = [
            post for post in self.sentiment_data['posts']
            if post.get('timestamp', '2000-01-01') > cutoff_str
        ]
        
        # 일별 통계 정리
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        self.sentiment_data['daily_stats'] = {
            date: stats for date, stats in self.sentiment_data['daily_stats'].items()
            if date >= cutoff_date_str
        }
        
        logger.info(f"오래된 데이터 정리 완료: {SentimentConfig.MAX_DATA_DAYS}일 이전 데이터 제거")
    
    def get_post_hash(self, post: Dict) -> str:
        """게시글 해시 생성"""
        import hashlib
        unique_str = f"{post.get('url', '')}{post.get('timestamp', '')}"
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()
    
    def process_post_sentiment(self, post: Dict) -> Dict:
        """게시글 감성 분석 처리"""
        post_hash = self.get_post_hash(post)
        
        # 캐시 확인
        if post_hash in self.sentiment_cache['processed_posts']:
            cached_result = self.sentiment_cache['processed_posts'][post_hash]
            # 캐시 유효성 확인 (24시간)
            try:
                cache_time = datetime.fromisoformat(cached_result.get('processed_at', '2000-01-01'))
                if datetime.now() - cache_time < timedelta(hours=24):
                    return cached_result
            except:
                pass
        
        # 감성 분석 실행
        try:
            classification = self.classifier.classify_post(post)
            
            # 감성 데이터 추출
            sentiment_analysis = classification.get('sentiment_analysis', {})
            sentiment = sentiment_analysis.get('sentiment', 'neutral')
            confidence = sentiment_analysis.get('confidence', 0.0)
            reason = sentiment_analysis.get('reason', '')
            
            # 감성 점수 계산 (-100 ~ +100)
            sentiment_score = 0
            if sentiment == 'positive':
                sentiment_score = confidence * 100
            elif sentiment == 'negative':
                sentiment_score = -confidence * 100
            else:
                sentiment_score = 0
            
            # 결과 데이터 구성
            result = {
                'post_hash': post_hash,
                'title': post.get('title', ''),
                'content': post.get('content', ''),
                'url': post.get('url', ''),
                'timestamp': post.get('timestamp', ''),
                'source': post.get('source', ''),
                'site': post.get('site', ''),
                'language': post.get('language', ''),
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
                'confidence': confidence,
                'reason': reason,
                'classification': classification,
                'processed_at': datetime.now().isoformat()
            }
            
            # 캐시에 저장
            self.sentiment_cache['processed_posts'][post_hash] = result
            
            # 통계 업데이트
            self.stats['total_processed'] += 1
            if sentiment == 'positive':
                self.stats['positive_count'] += 1
            elif sentiment == 'negative':
                self.stats['negative_count'] += 1
            else:
                self.stats['neutral_count'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"감성 분석 처리 실패: {e}")
            return None
    
    def collect_sentiment_data(self) -> int:
        """감성 데이터 수집"""
        logger.info("감성 데이터 수집 시작")
        
        try:
            # 크롤러에서 게시글 수집
            posts = get_all_posts_for_report()
            
            processed_count = 0
            
            for post in posts:
                try:
                    # 감성 분석 처리
                    sentiment_result = self.process_post_sentiment(post)
                    
                    if sentiment_result:
                        # 메인 데이터에 추가
                        self.sentiment_data['posts'].append(sentiment_result)
                        processed_count += 1
                        
                        # 통계 업데이트
                        self._update_statistics(sentiment_result)
                        
                        # 키워드 업데이트
                        self._update_keywords(sentiment_result)
                        
                except Exception as e:
                    logger.error(f"게시글 처리 오류: {e}")
                    continue
            
            logger.info(f"감성 데이터 수집 완료: {processed_count}개 처리")
            return processed_count
            
        except Exception as e:
            logger.error(f"감성 데이터 수집 실패: {e}")
            return 0
    
    def _update_statistics(self, sentiment_result: Dict):
        """통계 업데이트"""
        try:
            timestamp = datetime.fromisoformat(sentiment_result.get('timestamp', '2000-01-01'))
            date_key = timestamp.strftime('%Y-%m-%d')
            hour_key = timestamp.strftime('%Y-%m-%d %H')
            site = sentiment_result.get('site', 'unknown')
            sentiment = sentiment_result.get('sentiment', 'neutral')
            sentiment_score = sentiment_result.get('sentiment_score', 0)
            
            # 일별 통계 업데이트
            if date_key not in self.sentiment_data['daily_stats']:
                self.sentiment_data['daily_stats'][date_key] = {
                    'total_posts': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'sentiment_score_sum': 0,
                    'sentiment_score_avg': 0
                }
            
            daily_stats = self.sentiment_data['daily_stats'][date_key]
            daily_stats['total_posts'] += 1
            daily_stats[f'{sentiment}_count'] += 1
            daily_stats['sentiment_score_sum'] += sentiment_score
            daily_stats['sentiment_score_avg'] = daily_stats['sentiment_score_sum'] / daily_stats['total_posts']
            
            # 시간별 통계 업데이트
            if hour_key not in self.sentiment_data['hourly_stats']:
                self.sentiment_data['hourly_stats'][hour_key] = {
                    'total_posts': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'sentiment_score_avg': 0
                }
            
            hourly_stats = self.sentiment_data['hourly_stats'][hour_key]
            hourly_stats['total_posts'] += 1
            hourly_stats[f'{sentiment}_count'] += 1
            
            # 시간별 평균 점수 계산
            if hourly_stats['total_posts'] > 0:
                total_score = (hourly_stats['sentiment_score_avg'] * (hourly_stats['total_posts'] - 1) + sentiment_score)
                hourly_stats['sentiment_score_avg'] = total_score / hourly_stats['total_posts']
            
            # 사이트별 통계 업데이트
            if site not in self.sentiment_data['site_stats']:
                self.sentiment_data['site_stats'][site] = {
                    'total_posts': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'sentiment_score_avg': 0
                }
            
            site_stats = self.sentiment_data['site_stats'][site]
            site_stats['total_posts'] += 1
            site_stats[f'{sentiment}_count'] += 1
            
            # 사이트별 평균 점수 계산
            if site_stats['total_posts'] > 0:
                total_score = (site_stats['sentiment_score_avg'] * (site_stats['total_posts'] - 1) + sentiment_score)
                site_stats['sentiment_score_avg'] = total_score / site_stats['total_posts']
            
        except Exception as e:
            logger.error(f"통계 업데이트 실패: {e}")
    
    def _update_keywords(self, sentiment_result: Dict):
        """키워드 업데이트"""
        try:
            sentiment = sentiment_result.get('sentiment', 'neutral')
            reason = sentiment_result.get('reason', '')
            
            # 키워드 추출
            keywords = self._extract_keywords_from_reason(reason)
            
            if keywords:
                # 감성별 키워드 업데이트
                if sentiment not in self.sentiment_keywords:
                    self.sentiment_keywords[sentiment] = {}
                
                for keyword in keywords:
                    if keyword not in self.sentiment_keywords[sentiment]:
                        self.sentiment_keywords[sentiment][keyword] = 0
                    self.sentiment_keywords[sentiment][keyword] += 1
                
                # 전체 키워드 통계 업데이트
                timestamp = datetime.fromisoformat(sentiment_result.get('timestamp', '2000-01-01'))
                date_key = timestamp.strftime('%Y-%m-%d')
                
                if date_key not in self.sentiment_data['keyword_stats']:
                    self.sentiment_data['keyword_stats'][date_key] = {}
                
                for keyword in keywords:
                    if keyword not in self.sentiment_data['keyword_stats'][date_key]:
                        self.sentiment_data['keyword_stats'][date_key][keyword] = 0
                    self.sentiment_data['keyword_stats'][date_key][keyword] += 1
                
        except Exception as e:
            logger.error(f"키워드 업데이트 실패: {e}")
    
    def _extract_keywords_from_reason(self, reason: str) -> List[str]:
        """분석 이유에서 키워드 추출"""
        keywords = []
        
        try:
            # "키워드:" 패턴 찾기
            if '키워드:' in reason:
                keyword_part = reason.split('키워드:')[1].strip()
                # 쉼표로 분리
                raw_keywords = keyword_part.split(',')
                
                for keyword in raw_keywords:
                    keyword = keyword.strip()
                    if keyword and len(keyword) > 1:
                        keywords.append(keyword)
            
            # "keyword:" 패턴 찾기 (영어)
            elif 'keyword:' in reason.lower():
                keyword_part = reason.lower().split('keyword:')[1].strip()
                raw_keywords = keyword_part.split(',')
                
                for keyword in raw_keywords:
                    keyword = keyword.strip()
                    if keyword and len(keyword) > 1:
                        keywords.append(keyword)
            
        except Exception as e:
            logger.error(f"키워드 추출 실패: {e}")
        
        return keywords[:5]  # 최대 5개까지만 반환
    
    def analyze_sentiment_trends(self) -> Dict:
        """감성 트렌드 분석"""
        logger.info("감성 트렌드 분석 시작")
        
        try:
            # 최근 30일 데이터 분석
            cutoff_date = datetime.now() - timedelta(days=SentimentConfig.TREND_ANALYSIS_DAYS)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            # 일별 감성 점수 수집
            daily_scores = {}
            for date_key, stats in self.sentiment_data['daily_stats'].items():
                if date_key >= cutoff_str:
                    daily_scores[date_key] = stats.get('sentiment_score_avg', 0)
            
            # 일별 점수를 시간순으로 정렬
            sorted_dates = sorted(daily_scores.keys())
            score_series = [daily_scores[date] for date in sorted_dates]
            
            # 이동평균 계산
            moving_averages = self._calculate_moving_average(score_series, SentimentConfig.TREND_SMOOTHING_WINDOW)
            
            # 변동성 계산
            volatility = self._calculate_volatility(score_series)
            
            # 트렌드 방향 계산
            trend_direction = self._calculate_trend_direction(score_series)
            
            # 패턴 탐지
            patterns = self._detect_patterns(score_series)
            
            # 결과 저장
            self.sentiment_trends['daily_trends'] = {
                'dates': sorted_dates,
                'scores': score_series,
                'moving_averages': moving_averages,
                'volatility': volatility,
                'trend_direction': trend_direction,
                'patterns': patterns
            }
            
            # 시간별 트렌드 분석
            hourly_trends = self._analyze_hourly_trends()
            self.sentiment_trends['hourly_trends'] = hourly_trends
            
            # 주간 트렌드 분석
            weekly_trends = self._analyze_weekly_trends()
            self.sentiment_trends['weekly_trends'] = weekly_trends
            
            # 트렌드 요약
            trend_summary = {
                'current_score': score_series[-1] if score_series else 0,
                'trend_direction': trend_direction,
                'volatility_level': 'high' if volatility > SentimentConfig.VOLATILITY_THRESHOLD else 'normal',
                'patterns_detected': len(patterns),
                'analysis_period': SentimentConfig.TREND_ANALYSIS_DAYS,
                'data_points': len(score_series)
            }
            
            logger.info(f"감성 트렌드 분석 완료: {len(score_series)}개 데이터 포인트")
            return trend_summary
            
        except Exception as e:
            logger.error(f"감성 트렌드 분석 실패: {e}")
            return {}
    
    def _calculate_moving_average(self, data: List[float], window: int) -> List[float]:
        """이동평균 계산"""
        if len(data) < window:
            return data
        
        moving_avg = []
        for i in range(len(data)):
            if i < window - 1:
                moving_avg.append(data[i])
            else:
                avg = sum(data[i-window+1:i+1]) / window
                moving_avg.append(avg)
        
        return moving_avg
    
    def _calculate_volatility(self, data: List[float]) -> float:
        """변동성 계산"""
        if len(data) < 2:
            return 0.0
        
        try:
            mean = statistics.mean(data)
            variance = statistics.variance(data, mean)
            return sqrt(variance)
        except:
            return 0.0
    
    def _calculate_trend_direction(self, data: List[float]) -> str:
        """트렌드 방향 계산"""
        if len(data) < 2:
            return 'neutral'
        
        # 선형 회귀 기울기 계산
        n = len(data)
        x = list(range(n))
        
        try:
            x_mean = statistics.mean(x)
            y_mean = statistics.mean(data)
            
            numerator = sum((x[i] - x_mean) * (data[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            if denominator == 0:
                return 'neutral'
            
            slope = numerator / denominator
            
            if slope > 0.1:
                return 'positive'
            elif slope < -0.1:
                return 'negative'
            else:
                return 'neutral'
        except:
            return 'neutral'
    
    def _detect_patterns(self, data: List[float]) -> List[Dict]:
        """패턴 탐지"""
        patterns = []
        
        if len(data) < 5:
            return patterns
        
        try:
            # 급등/급락 패턴 탐지
            for i in range(1, len(data)):
                change = data[i] - data[i-1]
                change_rate = abs(change) / (abs(data[i-1]) + 1)  # 0으로 나누기 방지
                
                if change_rate > 0.3:  # 30% 이상 변화
                    pattern_type = 'surge' if change > 0 else 'plunge'
                    patterns.append({
                        'type': pattern_type,
                        'date_index': i,
                        'change': change,
                        'change_rate': change_rate
                    })
            
            # 연속 상승/하락 패턴 탐지
            consecutive_up = 0
            consecutive_down = 0
            
            for i in range(1, len(data)):
                if data[i] > data[i-1]:
                    consecutive_up += 1
                    consecutive_down = 0
                elif data[i] < data[i-1]:
                    consecutive_down += 1
                    consecutive_up = 0
                else:
                    consecutive_up = 0
                    consecutive_down = 0
                
                # 3일 이상 연속 패턴
                if consecutive_up >= 3:
                    patterns.append({
                        'type': 'consecutive_up',
                        'date_index': i,
                        'duration': consecutive_up
                    })
                elif consecutive_down >= 3:
                    patterns.append({
                        'type': 'consecutive_down',
                        'date_index': i,
                        'duration': consecutive_down
                    })
            
            self.stats['patterns_detected'] = len(patterns)
            
        except Exception as e:
            logger.error(f"패턴 탐지 실패: {e}")
        
        return patterns
    
    def _analyze_hourly_trends(self) -> Dict:
        """시간별 트렌드 분석"""
        hourly_data = defaultdict(list)
        
        # 시간별 데이터 수집
        for hour_key, stats in self.sentiment_data['hourly_stats'].items():
            try:
                timestamp = datetime.strptime(hour_key, '%Y-%m-%d %H')
                hour = timestamp.hour
                score = stats.get('sentiment_score_avg', 0)
                hourly_data[hour].append(score)
            except:
                continue
        
        # 시간별 평균 계산
        hourly_averages = {}
        for hour, scores in hourly_data.items():
            if scores:
                hourly_averages[hour] = statistics.mean(scores)
        
        return {
            'hourly_averages': hourly_averages,
            'peak_hours': self._find_peak_hours(hourly_averages),
            'low_hours': self._find_low_hours(hourly_averages)
        }
    
    def _find_peak_hours(self, hourly_averages: Dict) -> List[int]:
        """감성 점수가 높은 시간대 찾기"""
        if not hourly_averages:
            return []
        
        sorted_hours = sorted(hourly_averages.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, _ in sorted_hours[:3]]
    
    def _find_low_hours(self, hourly_averages: Dict) -> List[int]:
        """감성 점수가 낮은 시간대 찾기"""
        if not hourly_averages:
            return []
        
        sorted_hours = sorted(hourly_averages.items(), key=lambda x: x[1])
        return [hour for hour, _ in sorted_hours[:3]]
    
    def _analyze_weekly_trends(self) -> Dict:
        """주간 트렌드 분석"""
        weekly_data = defaultdict(list)
        
        # 요일별 데이터 수집
        for date_key, stats in self.sentiment_data['daily_stats'].items():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                weekday = date_obj.weekday()  # 0=Monday, 6=Sunday
                score = stats.get('sentiment_score_avg', 0)
                weekly_data[weekday].append(score)
            except:
                continue
        
        # 요일별 평균 계산
        weekly_averages = {}
        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        
        for weekday, scores in weekly_data.items():
            if scores:
                weekly_averages[weekday_names[weekday]] = statistics.mean(scores)
        
        return {
            'weekly_averages': weekly_averages,
            'best_day': max(weekly_averages.items(), key=lambda x: x[1])[0] if weekly_averages else 'N/A',
            'worst_day': min(weekly_averages.items(), key=lambda x: x[1])[0] if weekly_averages else 'N/A'
        }
    
    def get_sentiment_summary(self) -> Dict:
        """감성 분석 요약"""
        try:
            total_posts = len(self.sentiment_data['posts'])
            
            if total_posts == 0:
                return {
                    'total_posts': 0,
                    'sentiment_distribution': {},
                    'average_score': 0,
                    'trend_direction': 'neutral',
                    'volatility': 0,
                    'top_keywords': {},
                    'site_comparison': {}
                }
            
            # 감성 분포 계산
            sentiment_counts = Counter()
            sentiment_scores = []
            
            for post in self.sentiment_data['posts']:
                sentiment = post.get('sentiment', 'neutral')
                sentiment_counts[sentiment] += 1
                sentiment_scores.append(post.get('sentiment_score', 0))
            
            # 평균 감성 점수
            average_score = statistics.mean(sentiment_scores) if sentiment_scores else 0
            
            # 트렌드 분석
            trend_summary = self.analyze_sentiment_trends()
            
            # 상위 키워드 추출
            top_keywords = self._get_top_keywords()
            
            # 사이트별 비교
            site_comparison = self._get_site_comparison()
            
            return {
                'total_posts': total_posts,
                'sentiment_distribution': dict(sentiment_counts),
                'average_score': average_score,
                'trend_direction': trend_summary.get('trend_direction', 'neutral'),
                'volatility': trend_summary.get('volatility_level', 'normal'),
                'top_keywords': top_keywords,
                'site_comparison': site_comparison,
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"감성 요약 생성 실패: {e}")
            return {}
    
    def _get_top_keywords(self) -> Dict:
        """상위 키워드 추출"""
        top_keywords = {
            'positive': {},
            'negative': {},
            'neutral': {}
        }
        
        for sentiment, keywords in self.sentiment_keywords.items():
            if sentiment in top_keywords and isinstance(keywords, dict):
                # 빈도 순으로 정렬
                sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)
                top_keywords[sentiment] = dict(sorted_keywords[:10])
        
        return top_keywords
    
    def _get_site_comparison(self) -> Dict:
        """사이트별 감성 비교"""
        site_comparison = {}
        
        for site, stats in self.sentiment_data['site_stats'].items():
            if stats['total_posts'] > 0:
                site_comparison[site] = {
                    'total_posts': stats['total_posts'],
                    'positive_ratio': stats['positive_count'] / stats['total_posts'],
                    'negative_ratio': stats['negative_count'] / stats['total_posts'],
                    'neutral_ratio': stats['neutral_count'] / stats['total_posts'],
                    'average_score': stats['sentiment_score_avg']
                }
        
        return site_comparison
    
    def check_sentiment_alerts(self) -> List[Dict]:
        """감성 알림 확인"""
        alerts = []
        
        try:
            # 현재 감성 점수 확인
            recent_posts = [
                post for post in self.sentiment_data['posts']
                if datetime.fromisoformat(post.get('timestamp', '2000-01-01')) > datetime.now() - timedelta(hours=6)
            ]
            
            if recent_posts:
                recent_scores = [post.get('sentiment_score', 0) for post in recent_posts]
                current_score = statistics.mean(recent_scores)
                
                # 감성 점수 알림
                if current_score <= SentimentConfig.SENTIMENT_ALERT_THRESHOLD:
                    alerts.append({
                        'type': 'low_sentiment',
                        'severity': 'high',
                        'message': f"감성 점수가 {current_score:.1f}점으로 매우 낮습니다.",
                        'current_score': current_score,
                        'threshold': SentimentConfig.SENTIMENT_ALERT_THRESHOLD,
                        'timestamp': datetime.now().isoformat()
                    })
            
            # 변동성 알림
            trend_summary = self.analyze_sentiment_trends()
            if trend_summary.get('volatility_level') == 'high':
                alerts.append({
                    'type': 'high_volatility',
                    'severity': 'medium',
                    'message': "감성 변동성이 높습니다.",
                    'volatility_level': trend_summary.get('volatility_level'),
                    'timestamp': datetime.now().isoformat()
                })
            
            # 패턴 알림
            patterns_count = trend_summary.get('patterns_detected', 0)
            if patterns_count > 3:
                alerts.append({
                    'type': 'pattern_detected',
                    'severity': 'low',
                    'message': f"{patterns_count}개의 감성 패턴이 감지되었습니다.",
                    'patterns_count': patterns_count,
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"감성 알림 확인 실패: {e}")
        
        return alerts
    
    def run_full_analysis(self) -> Dict:
        """전체 분석 실행"""
        logger.info("전체 감성 분석 시작")
        
        try:
            # 1. 데이터 수집
            collected_count = self.collect_sentiment_data()
            
            # 2. 트렌드 분석
            trend_summary = self.analyze_sentiment_trends()
            
            # 3. 요약 생성
            summary = self.get_sentiment_summary()
            
            # 4. 알림 확인
            alerts = self.check_sentiment_alerts()
            
            # 5. 데이터 저장
            self.save_sentiment_data()
            self.save_sentiment_cache()
            self.save_sentiment_trends()
            self.save_sentiment_keywords()
            
            # 6. 결과 반환
            result = {
                'collected_posts': collected_count,
                'trend_analysis': trend_summary,
                'summary': summary,
                'alerts': alerts,
                'stats': self.stats,
                'analysis_completed_at': datetime.now().isoformat()
            }
            
            logger.info(f"전체 감성 분석 완료: {collected_count}개 게시글 처리")
            return result
            
        except Exception as e:
            logger.error(f"전체 감성 분석 실패: {e}")
            return {}
    
    def get_report_data(self, days: int = 7) -> Dict:
        """리포트용 감성 데이터 제공"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.isoformat()
            
            # 기간 내 게시글 필터링
            filtered_posts = [
                post for post in self.sentiment_data['posts']
                if post.get('timestamp', '2000-01-01') > cutoff_str
            ]
            
            # 기간 내 일별 통계
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            filtered_daily_stats = {
                date: stats for date, stats in self.sentiment_data['daily_stats'].items()
                if date >= cutoff_date_str
            }
            
            # 요약 데이터 생성
            if filtered_posts:
                sentiment_scores = [post.get('sentiment_score', 0) for post in filtered_posts]
                sentiment_counts = Counter(post.get('sentiment', 'neutral') for post in filtered_posts)
                
                report_data = {
                    'period_days': days,
                    'total_posts': len(filtered_posts),
                    'sentiment_distribution': dict(sentiment_counts),
                    'average_score': statistics.mean(sentiment_scores),
                    'daily_stats': filtered_daily_stats,
                    'trend_direction': self._calculate_trend_direction(sentiment_scores),
                    'volatility': self._calculate_volatility(sentiment_scores),
                    'top_keywords': self._get_top_keywords(),
                    'site_comparison': self._get_site_comparison(),
                    'generated_at': datetime.now().isoformat()
                }
            else:
                report_data = {
                    'period_days': days,
                    'total_posts': 0,
                    'sentiment_distribution': {},
                    'average_score': 0,
                    'daily_stats': {},
                    'trend_direction': 'neutral',
                    'volatility': 0,
                    'top_keywords': {},
                    'site_comparison': {},
                    'generated_at': datetime.now().isoformat()
                }
            
            return report_data
            
        except Exception as e:
            logger.error(f"리포트 데이터 생성 실패: {e}")
            return {}

# =============================================================================
# 편의 함수들
# =============================================================================

def collect_sentiment_data() -> int:
    """감성 데이터 수집 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.collect_sentiment_data()

def analyze_sentiment_trends() -> Dict:
    """감성 트렌드 분석 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.analyze_sentiment_trends()

def get_sentiment_summary() -> Dict:
    """감성 요약 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.get_sentiment_summary()

def check_sentiment_alerts() -> List[Dict]:
    """감성 알림 확인 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.check_sentiment_alerts()

def run_full_sentiment_analysis() -> Dict:
    """전체 감성 분석 실행 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.run_full_analysis()

def get_sentiment_report_data(days: int = 7) -> Dict:
    """리포트용 감성 데이터 (편의 함수)"""
    manager = SentimentDataManager()
    return manager.get_report_data(days)

# =============================================================================
# 메인 실행
# =============================================================================

def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Epic7 감성 데이터 관리자 v3.1"
    )
    
    parser.add_argument(
        '--action',
        choices=['collect', 'analyze', 'summary', 'alerts', 'full', 'report'],
        default='full',
        help='실행할 작업 (default: full)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='분석 기간 (일) (default: 7)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드'
    )
    
    args = parser.parse_args()
    
    # 디버그 모드 설정
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        manager = SentimentDataManager()
        
        if args.action == 'collect':
            # 데이터 수집
            count = manager.collect_sentiment_data()
            logger.info(f"데이터 수집 완료: {count}개")
            
        elif args.action == 'analyze':
            # 트렌드 분석
            result = manager.analyze_sentiment_trends()
            logger.info(f"트렌드 분석 완료: {result}")
            
        elif args.action == 'summary':
            # 요약 생성
            summary = manager.get_sentiment_summary()
            logger.info(f"요약 생성 완료: {summary}")
            
        elif args.action == 'alerts':
            # 알림 확인
            alerts = manager.check_sentiment_alerts()
            logger.info(f"알림 확인 완료: {len(alerts)}개 알림")
            
        elif args.action == 'report':
            # 리포트 데이터 생성
            report_data = manager.get_report_data(args.days)
            logger.info(f"리포트 데이터 생성 완료: {args.days}일 기간")
            
        else:  # full
            # 전체 분석
            result = manager.run_full_analysis()
            logger.info(f"전체 분석 완료: {result}")
        
    except Exception as e:
        logger.error(f"실행 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
