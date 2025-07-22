#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 분류기 v3.1
15분/30분 주기별 크롤링에 최적화된 실시간 분류 시스템

주요 특징:
- 실시간 알림 판별 (15분 간격 버그 게시판)
- 버그 우선순위 분류 (긴급/높음/중간/낮음)
- 감성 분석 통합 (긍정/부정/중립)
- 다국어 키워드 시스템 (한국어+영어)
- 주기별 분류 최적화

Author: Epic7 Monitoring Team
Version: 3.1
Date: 2025-07-17
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# 공통 모듈 임포트
from config import config
from utils import is_korean_text, get_category_emoji, setup_logging

# 로깅 설정
import logging
logger = logging.getLogger(__name__)

# =============================================================================
# Epic7 실시간 분류기
# =============================================================================

class Epic7Classifier:
    """Epic7 실시간 분류기"""
    
    def __init__(self):
        """분류기 초기화"""
        self.load_keywords()
        self.load_source_config()
        self.load_priority_patterns()
        
        # 설정에서 임계값 가져오기
        self.sentiment_thresholds = config.Classification.SENTIMENT_THRESHOLDS
        self.realtime_alert_sources = config.Crawling.REALTIME_ALERT_SOURCES
        self.realtime_alert_thresholds = config.Classification.REALTIME_ALERT_THRESHOLDS
        
        logger.info("Epic7 실시간 분류기 v3.1 초기화 완료")
    
    def load_keywords(self):
        """다국어 키워드 로드"""
        
        # ======= 버그 키워드 시스템 =======
        
        # 치명적 버그 키워드 (Critical)
        self.critical_bug_keywords = {
            'korean': [
                '서버다운', '서버장애', '서버오류', '접속불가', '접속장애',
                '로그인불가', '로그인안됨', '게임시작안됨', '게임안됨',
                '데이터손실', '데이터날아감', '세이브파일', '진행사항삭제',
                '결제오류', '결제안됨', '결제실패', '환불요청',
                '크래시', '강제종료', '게임꺼짐', '앱종료', '튕김',
                '완전먹통', '아예안됨', '전혀안됨', '완전망함'
            ],
            'english': [
                'server down', 'server crash', 'server error', 'cannot connect', 'connection failed',
                'login failed', 'cannot login', 'game wont start', 'game broken',
                'data loss', 'save file', 'progress lost', 'data corrupted',
                'payment error', 'payment failed', 'purchase failed', 'refund request',
                'crash', 'force close', 'game crash', 'app crash', 'freeze',
                'completely broken', 'totally broken', 'not working at all'
            ]
        }
        
        # 높은 우선순위 버그 키워드 (High)
        self.high_bug_keywords = {
            'korean': [
                '버그', '오류', '에러', '문제', '장애', '이상',
                '작동안함', '실행안됨', '멈춤', '정지', '끊김',
                '로딩안됨', '화면멈춤', '반응없음', '느림', '렉',
                '스킬버그', '캐릭터버그', '아이템버그', '매치버그',
                'pvp버그', 'pve버그', '길드버그', '상점버그',
                '업데이트오류', '패치오류', '설치오류'
            ],
            'english': [
                'bug', 'error', 'issue', 'problem', 'glitch', 'broken',
                'not working', 'not responding', 'stuck', 'frozen', 'lag',
                'loading issue', 'screen freeze', 'no response', 'slow', 'laggy',
                'skill bug', 'character bug', 'item bug', 'match bug',
                'pvp bug', 'pve bug', 'guild bug', 'shop bug',
                'update error', 'patch error', 'installation error'
            ]
        }
        
        # 중간 우선순위 버그 키워드 (Medium)
        self.medium_bug_keywords = {
            'korean': [
                '이상함', '이상해', '비정상', '불안정',
                '가끔안됨', '때때로', '종종', '자주',
                'ui버그', '인터페이스', '화면깨짐', '글자깨짐',
                '사운드오류', '음성오류', '그래픽오류', '표시오류',
                '번역오류', '텍스트오류', '맞춤법', '오타'
            ],
            'english': [
                'weird', 'strange', 'abnormal', 'unstable',
                'sometimes', 'occasionally', 'often', 'frequently',
                'ui bug', 'interface', 'screen broken', 'text broken',
                'sound error', 'audio error', 'graphic error', 'display error',
                'translation error', 'text error', 'typo', 'spelling'
            ]
        }
        
        # 낮은 우선순위 버그 키워드 (Low)
        self.low_bug_keywords = {
            'korean': [
                '불편', '아쉬움', '개선필요', '건의',
                '조금이상', '살짝', '약간', '미세하게',
                '색상', '폰트', '정렬', '배치',
                '툴팁', '설명', '가이드', '도움말'
            ],
            'english': [
                'inconvenient', 'suggestion', 'improvement needed', 'request',
                'slightly', 'a bit', 'minor', 'small',
                'color', 'font', 'alignment', 'layout',
                'tooltip', 'description', 'guide', 'help'
            ]
        }
        
        # 버그 제외 키워드 (긍정적 맥락)
        self.bug_exclusion_keywords = {
            'korean': [
                '수정', '해결', '고침', '패치', '업데이트', '개선',
                '버그수정', '오류수정', '문제해결', '해결됨',
                '수정됨', '개선됨', '업데이트됨', '패치됨'
            ],
            'english': [
                'fixed', 'solved', 'resolved', 'patched', 'updated', 'improved',
                'bug fix', 'error fix', 'issue resolved', 'problem solved',
                'has been fixed', 'has been resolved', 'has been updated'
            ]
        }
        
        # ======= 감성 키워드 시스템 =======
        
        # 긍정 감성 키워드
        self.positive_keywords = {
            'korean': [
                '좋아', '좋다', '최고', '굿', '굿굿', '감사', '고마워',
                '수고', '잘했', '잘만들', '완벽', '훌륭', '멋지', '쩐다',
                '대박', '개좋', '개쩐', '사랑', '❤️', '♥️', '👍',
                '👏', '🔥', '💯', '개선', '향상', '업그레이드',
                '패치굿', '업데이트굿', '밸런스굿', '재밌', '재미있',
                '만족', '행복', '즐거움', '기쁨', '추천', '강추'
            ],
            'english': [
                'good', 'great', 'awesome', 'amazing', 'excellent',
                'perfect', 'love', 'like', 'enjoy', 'fun', 'cool',
                'nice', 'wonderful', 'fantastic', 'brilliant', 'outstanding',
                'improvement', 'better', 'upgrade', 'enhanced', 'upgraded',
                'thanks', 'thank you', 'appreciate', 'well done', 'good job',
                'satisfied', 'happy', 'enjoyable', 'recommend', 'recommended',
                '❤️', '♥️', '👍', '👏', '🔥', '💯'
            ]
        }
        
        # 부정 감성 키워드
        self.negative_keywords = {
            'korean': [
                '싫어', '싫다', '별로', '안좋', '나쁘', '최악', '망했',
                '실망', '짜증', '화남', '열받', '빡침', '개빡', '개짜증',
                '쓰레기', '헛소리', '개소리', '뭐지', '이상해', '이상함',
                '너무어려워', '너무힘들어', '포기', '그만', '탈주', '삭제',
                '밸런스개판', '밸런스망', '운영진', '멍청', '바보',
                '돈벌이', '과금유도', '현질', '지갑털기', '사기'
            ],
            'english': [
                'bad', 'terrible', 'awful', 'horrible', 'hate',
                'dislike', 'annoying', 'frustrating', 'disappointed', 'disgusting',
                'angry', 'mad', 'stupid', 'dumb', 'trash', 'garbage',
                'worst', 'sucks', 'boring', 'too hard', 'too difficult',
                'give up', 'quit', 'uninstall', 'delete', 'remove',
                'balance sucks', 'devs suck', 'developers suck', 'greedy',
                'pay to win', 'p2w', 'cash grab', 'scam', 'wtf', 'wth'
            ]
        }
        
        # 중립 감성 키워드
        self.neutral_keywords = {
            'korean': [
                '그냥', '보통', '평범', '무난', '괜찮', '나쁘지않',
                '어떨까', '궁금', '질문', '문의', '확인', '체크',
                '정보', '공지', '알림', '안내', '가이드', '설명'
            ],
            'english': [
                'okay', 'normal', 'average', 'decent', 'not bad',
                'question', 'ask', 'wondering', 'curious', 'info',
                'information', 'notice', 'guide', 'explanation', 'how to'
            ]
        }
    
    def load_source_config(self):
        """소스별 설정 로드"""
        self.source_config = {
            # 15분 간격 - 버그 게시판 (실시간 알림)
            'stove_korea_bug': {
                'type': 'korean',
                'schedule': 'frequent',
                'weight': 1.0,
                'bug_priority_boost': 0.3,
                'realtime_alert': True,
                'alert_threshold': 0.5
            },
            'stove_global_bug': {
                'type': 'global',
                'schedule': 'frequent',
                'weight': 1.0,
                'bug_priority_boost': 0.3,
                'realtime_alert': True,
                'alert_threshold': 0.5
            },
            
            # 30분 간격 - 일반 게시판
            'stove_korea_general': {
                'type': 'korean',
                'schedule': 'regular',
                'weight': 0.8,
                'bug_priority_boost': 0.0,
                'realtime_alert': False,
                'alert_threshold': 0.7
            },
            'stove_global_general': {
                'type': 'global',
                'schedule': 'regular',
                'weight': 0.8,
                'bug_priority_boost': 0.0,
                'realtime_alert': False,
                'alert_threshold': 0.7
            },
            'ruliweb_epic7': {
                'type': 'korean',
                'schedule': 'regular',
                'weight': 0.7,
                'bug_priority_boost': 0.0,
                'realtime_alert': False,
                'alert_threshold': 0.8
            },
            'reddit_epic7': {
                'type': 'global',
                'schedule': 'regular',
                'weight': 0.7,
                'bug_priority_boost': 0.0,
                'realtime_alert': False,
                'alert_threshold': 0.8
            }
        }
    
    def load_priority_patterns(self):
        """우선순위 패턴 로드"""
        self.priority_patterns = {
            'critical': [
                r'서버.*다운', r'접속.*불가', r'로그인.*안됨', r'게임.*안됨',
                r'데이터.*손실', r'결제.*오류', r'강제.*종료', r'완전.*먹통',
                r'server.*down', r'cannot.*connect', r'login.*failed', r'game.*broken',
                r'data.*loss', r'payment.*error', r'force.*close', r'completely.*broken'
            ],
            'high': [
                r'버그|오류|에러|문제', r'작동.*안함', r'실행.*안됨', r'멈춤|정지',
                r'bug|error|issue|problem', r'not.*working', r'not.*responding', r'stuck|frozen'
            ],
            'medium': [
                r'이상함|이상해|비정상', r'가끔.*안됨', r'ui.*버그', r'화면.*깨짐',
                r'weird|strange|abnormal', r'sometimes', r'ui.*bug', r'screen.*broken'
            ],
            'low': [
                r'불편|아쉬움|개선.*필요', r'조금.*이상', r'색상|폰트|정렬',
                r'inconvenient|suggestion', r'slightly|minor', r'color|font|alignment'
            ]
        }
    
    def get_bug_priority(self, title: str, content: str = "", source: str = "") -> Tuple[str, float, str]:
        """버그 우선순위 판별"""
        if not title:
            return "low", 0.0, "제목 없음"
        
        # 텍스트 정규화
        text = (title + " " + content).lower().strip()
        
        # 버그 제외 키워드 확인
        language = 'korean' if is_korean_text(text) else 'english'
        
        for exclusion in self.bug_exclusion_keywords[language]:
            if exclusion in text:
                return "low", 0.0, f"버그 제외 키워드: {exclusion}"
        
        # 우선순위별 키워드 매칭
        priority_scores = {
            'critical': 0.0,
            'high': 0.0,
            'medium': 0.0,
            'low': 0.0
        }
        
        matched_keywords = []
        
        # 치명적 버그 키워드 확인
        for keyword in self.critical_bug_keywords[language]:
            if keyword in text:
                priority_scores['critical'] += 0.5
                matched_keywords.append(f"치명적:{keyword}")
        
        # 높은 우선순위 버그 키워드 확인
        for keyword in self.high_bug_keywords[language]:
            if keyword in text:
                priority_scores['high'] += 0.3
                matched_keywords.append(f"높음:{keyword}")
        
        # 중간 우선순위 버그 키워드 확인
        for keyword in self.medium_bug_keywords[language]:
            if keyword in text:
                priority_scores['medium'] += 0.2
                matched_keywords.append(f"중간:{keyword}")
        
        # 낮은 우선순위 버그 키워드 확인
        for keyword in self.low_bug_keywords[language]:
            if keyword in text:
                priority_scores['low'] += 0.1
                matched_keywords.append(f"낮음:{keyword}")
        
        # 패턴 매칭 추가 점수
        for priority, patterns in self.priority_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    priority_scores[priority] += 0.2
                    matched_keywords.append(f"패턴:{pattern}")
        
        # 소스별 가중치 적용
        if source in self.source_config:
            boost = self.source_config[source].get('bug_priority_boost', 0.0)
            for priority in priority_scores:
                priority_scores[priority] += boost
        
        # 최고 점수 우선순위 결정
        max_priority = max(priority_scores.items(), key=lambda x: x[1])
        
        if max_priority[1] >= 0.3:
            reason = f"매칭 키워드: {', '.join(matched_keywords[:5])}"
            return max_priority[0], min(max_priority[1], 1.0), reason
        else:
            return "low", 0.0, "버그 키워드 없음"
    
    def is_bug_post(self, title: str, content: str = "", source: str = "") -> Tuple[bool, float, str]:
        """버그 게시글 판별"""
        if not title:
            return False, 0.0, "제목 없음"
        
        # 소스가 버그 전용 게시판인 경우
        if source in self.realtime_alert_sources:
            return True, 1.0, f"버그 전용 게시판 ({source})"
        
        # 우선순위 기반 버그 판별
        priority, confidence, reason = self.get_bug_priority(title, content, source)
        
        # 우선순위가 낮음이 아니면 버그로 판별
        is_bug = priority != "low" or confidence >= 0.3
        
        return is_bug, confidence, reason
    
    def is_high_priority_bug(self, title: str, content: str = "", source: str = "") -> bool:
        """고우선순위 버그 판별"""
        if not title:
            return False
        
        # 먼저 버그 게시글인지 확인
        is_bug, confidence, _ = self.is_bug_post(title, content, source)
        
        if not is_bug:
            return False
        
        # 우선순위 확인
        priority, priority_confidence, _ = self.get_bug_priority(title, content, source)
        
        # 치명적 또는 높은 우선순위이면 고우선순위
        if priority in ['critical', 'high']:
            return True
        
        # 버그 신뢰도가 매우 높은 경우
        if confidence >= 0.8:
            return True
        
        return False
    
    def analyze_sentiment(self, title: str, content: str = "", source: str = "") -> Tuple[str, float, str]:
        """감성 분석"""
        if not title:
            return "neutral", 0.0, "제목 없음"
        
        # 텍스트 정규화
        text = (title + " " + content).lower().strip()
        
        # 언어 판별
        language = 'korean' if is_korean_text(text) else 'english'
        
        # 감성 점수 계산
        positive_score = 0.0
        negative_score = 0.0
        neutral_score = 0.0
        
        positive_matches = []
        negative_matches = []
        neutral_matches = []
        
        # 긍정 키워드 매칭
        for keyword in self.positive_keywords[language]:
            if keyword in text:
                positive_matches.append(keyword)
                positive_score += 0.3
        
        # 부정 키워드 매칭
        for keyword in self.negative_keywords[language]:
            if keyword in text:
                negative_matches.append(keyword)
                negative_score += 0.3
        
        # 중립 키워드 매칭
        for keyword in self.neutral_keywords[language]:
            if keyword in text:
                neutral_matches.append(keyword)
                neutral_score += 0.2
        
        # 소스별 가중치 적용
        if source in self.source_config:
            weight = self.source_config[source].get('weight', 1.0)
            positive_score *= weight
            negative_score *= weight
            neutral_score *= weight
        
        # 감성 판별
        max_score = max(positive_score, negative_score, neutral_score)
        
        if max_score < self.sentiment_thresholds['neutral']:
            sentiment = "neutral"
            confidence = 0.5
            reason = "감성 키워드 부족"
        elif positive_score == max_score:
            sentiment = "positive"
            confidence = min(positive_score, 1.0)
            reason = f"긍정 키워드: {', '.join(positive_matches[:3])}"
        elif negative_score == max_score:
            sentiment = "negative"
            confidence = min(negative_score, 1.0)
            reason = f"부정 키워드: {', '.join(negative_matches[:3])}"
        else:
            sentiment = "neutral"
            confidence = min(neutral_score, 1.0)
            reason = f"중립 키워드: {', '.join(neutral_matches[:3])}"
        
        return sentiment, confidence, reason
    
    def should_send_realtime_alert(self, post_data: Dict, classification: Dict) -> bool:
        """실시간 알림 전송 여부 판별"""
        source = post_data.get('source', '')
        
        # 실시간 알림 소스가 아니면 알림 안함
        if source not in self.realtime_alert_sources:
            return False
        
        # 버그 게시판 소스는 항상 실시간 알림
        if source in self.realtime_alert_sources:
            return True
        
        # 우선순위 기반 알림 판별
        bug_priority = classification.get('bug_priority', 'low')
        bug_confidence = classification.get('bug_confidence', 0.0)
        
        if bug_priority == 'critical':
            return True
        elif bug_priority == 'high' and bug_confidence >= 0.6:
            return True
        elif bug_priority == 'medium' and bug_confidence >= 0.8:
            return True
        
        # 강한 부정 감성도 실시간 알림
        sentiment = classification.get('sentiment', 'neutral')
        sentiment_confidence = classification.get('sentiment_confidence', 0.0)
        
        if sentiment == 'negative' and sentiment_confidence >= 0.8:
            return True
        
        return False
    
    def classify_post(self, post_data: Dict) -> Dict:
        """게시글 종합 분류"""
        title = post_data.get('title', '')
        content = post_data.get('content', '')
        source = post_data.get('source', '')
        
        # 버그 분석
        is_bug, bug_confidence, bug_reason = self.is_bug_post(title, content, source)
        bug_priority, priority_confidence, priority_reason = self.get_bug_priority(title, content, source)
        
        # 감성 분석
        sentiment, sentiment_confidence, sentiment_reason = self.analyze_sentiment(title, content, source)
        
        # 소스 정보
        source_config = self.source_config.get(source, {})
        source_type = source_config.get('type', 'unknown')
        schedule_type = source_config.get('schedule', 'regular')
        
        # 언어 판별
        language = 'korean' if is_korean_text(title + " " + content) else 'english'
        
        # 최종 카테고리 결정
        if is_bug:
            category = 'bug'
            primary_confidence = bug_confidence
        elif sentiment == 'positive':
            category = 'positive'
            primary_confidence = sentiment_confidence
        elif sentiment == 'negative':
            category = 'negative'
            primary_confidence = sentiment_confidence
        else:
            category = 'neutral'
            primary_confidence = 0.5
        
        # 실시간 알림 여부 판별
        classification_result = {
            'bug_priority': bug_priority,
            'bug_confidence': bug_confidence,
            'sentiment': sentiment,
            'sentiment_confidence': sentiment_confidence
        }
        
        should_alert = self.should_send_realtime_alert(post_data, classification_result)
        
        # 결과 반환
        result = {
            'category': category,
            'confidence': primary_confidence,
            'language': language,
            'source_type': source_type,
            'schedule_type': schedule_type,
            
            # 버그 분석 결과
            'bug_analysis': {
                'is_bug': is_bug,
                'priority': bug_priority,
                'confidence': bug_confidence,
                'reason': bug_reason
            },
            
            # 감성 분석 결과
            'sentiment_analysis': {
                'sentiment': sentiment,
                'confidence': sentiment_confidence,
                'reason': sentiment_reason
            },
            
            # 실시간 알림 설정
            'realtime_alert': {
                'should_alert': should_alert,
                'alert_reason': self._get_alert_reason(classification_result, should_alert),
                'alert_priority': self._get_alert_priority(bug_priority, sentiment)
            },
            
            # 메타데이터
            'classification_timestamp': datetime.now().isoformat(),
            'classifier_version': f'Epic7 Unified v{config.VERSION}'
        }
        
        return result
    
    def _get_alert_reason(self, classification: Dict, should_alert: bool) -> str:
        """알림 사유 반환"""
        if not should_alert:
            return "알림 임계값 미달"
        
        bug_priority = classification.get('bug_priority', 'low')
        sentiment = classification.get('sentiment', 'neutral')
        
        if bug_priority == 'critical':
            return "치명적 버그 발견"
        elif bug_priority == 'high':
            return "높은 우선순위 버그"
        elif bug_priority == 'medium':
            return "중간 우선순위 버그"
        elif sentiment == 'negative':
            return "강한 부정 감성"
        else:
            return "버그 게시판 실시간 알림"
    
    def _get_alert_priority(self, bug_priority: str, sentiment: str) -> int:
        """알림 우선순위 반환"""
        priority_map = config.Classification.BUG_PRIORITY_LEVELS
        
        if bug_priority in priority_map:
            return priority_map[bug_priority]
        elif sentiment == 'negative':
            return 4
        else:
            return 5
    
    def get_priority_emoji(self, priority: str) -> str:
        """우선순위별 이모지 반환"""
        return get_category_emoji(priority)
    
    def get_classification_summary(self, classifications: List[Dict]) -> Dict:
        """분류 결과 요약"""
        if not classifications:
            return {}
        
        total_count = len(classifications)
        category_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        language_counts = defaultdict(int)
        alert_counts = defaultdict(int)
        
        for classification in classifications:
            category_counts[classification.get('category', 'neutral')] += 1
            language_counts[classification.get('language', 'unknown')] += 1
            
            bug_priority = classification.get('bug_analysis', {}).get('priority', 'low')
            priority_counts[bug_priority] += 1
            
            should_alert = classification.get('realtime_alert', {}).get('should_alert', False)
            alert_counts['should_alert' if should_alert else 'no_alert'] += 1
        
        summary = {
            'total_posts': total_count,
            'category_distribution': dict(category_counts),
            'priority_distribution': dict(priority_counts),
            'language_distribution': dict(language_counts),
            'alert_distribution': dict(alert_counts),
            
            # 비율 계산
            'bug_ratio': category_counts['bug'] / total_count if total_count > 0 else 0,
            'positive_ratio': category_counts['positive'] / total_count if total_count > 0 else 0,
            'negative_ratio': category_counts['negative'] / total_count if total_count > 0 else 0,
            'alert_ratio': alert_counts['should_alert'] / total_count if total_count > 0 else 0,
            
            # 심각도 통계
            'critical_bugs': priority_counts['critical'],
            'high_priority_bugs': priority_counts['high'],
            'medium_priority_bugs': priority_counts['medium'],
            'low_priority_bugs': priority_counts['low'],
            
            'summary_timestamp': datetime.now().isoformat()
        }
        
        return summary

# =============================================================================
# 편의 함수들 (하위 호환성)
# =============================================================================

def is_bug_post(title: str, content: str = "", source: str = "") -> bool:
    """버그 게시글 판별 (하위 호환성)"""
    classifier = Epic7Classifier()
    is_bug, _, _ = classifier.is_bug_post(title, content, source)
    return is_bug

def is_high_priority_bug(title: str, content: str = "", source: str = "") -> bool:
    """고우선순위 버그 판별 (하위 호환성)"""
    classifier = Epic7Classifier()
    return classifier.is_high_priority_bug(title, content, source)

def extract_bug_severity(title: str, content: str = "", source: str = "") -> str:
    """버그 심각도 추출"""
    classifier = Epic7Classifier()
    priority, _, _ = classifier.get_bug_priority(title, content, source)
    return priority

def is_positive_post(title: str, content: str = "", source: str = "") -> bool:
    """긍정 게시글 판별 (하위 호환성)"""
    classifier = Epic7Classifier()
    sentiment, _, _ = classifier.analyze_sentiment(title, content, source)
    return sentiment == 'positive'

def is_negative_post(title: str, content: str = "", source: str = "") -> bool:
    """부정 게시글 판별 (하위 호환성)"""
    classifier = Epic7Classifier()
    sentiment, _, _ = classifier.analyze_sentiment(title, content, source)
    return sentiment == 'negative'

def classify_post(title: str, content: str = "", source: str = "") -> str:
    """게시글 분류 (하위 호환성)"""
    classifier = Epic7Classifier()
    post_data = {
        'title': title,
        'content': content,
        'source': source
    }
    result = classifier.classify_post(post_data)
    return result.get('category', 'neutral')

def should_send_realtime_alert(post_data: Dict) -> bool:
    """실시간 알림 전송 여부 판별 (새로운 함수)"""
    classifier = Epic7Classifier()
    classification = classifier.classify_post(post_data)
    return classification.get('realtime_alert', {}).get('should_alert', False)

# =============================================================================
# 메인 실행 및 테스트
# =============================================================================

def main():
    """메인 실행 함수"""
    logger.info("Epic7 통합 분류기 v3.1 테스트 시작")
    
    # 분류기 초기화
    classifier = Epic7Classifier()
    
    # 테스트 게시글
    test_posts = [
        {
            'title': '서버 다운으로 접속이 안되요',
            'content': '게임을 시작할 수가 없어요. 완전 먹통입니다.',
            'source': 'stove_korea_bug'
        },
        {
            'title': 'Game crash during PvP match',
            'content': 'The game force closes when starting PvP',
            'source': 'stove_global_bug'
        },
        {
            'title': '이번 업데이트 정말 좋아요',
            'content': '새로운 기능이 훌륭하고 재미있어요',
            'source': 'stove_korea_general'
        },
        {
            'title': 'Balance is terrible',
            'content': 'This game sucks now, devs dont care',
            'source': 'reddit_epic7'
        }
    ]
    
    # 분류 실행
    results = []
    for post in test_posts:
        result = classifier.classify_post(post)
        results.append(result)
        
        print(f"\n제목: {post['title']}")
        print(f"소스: {post['source']}")
        print(f"카테고리: {result['category']} {get_category_emoji(result['category'])}")
        print(f"버그 우선순위: {result['bug_analysis']['priority']} {classifier.get_priority_emoji(result['bug_analysis']['priority'])}")
        print(f"감성: {result['sentiment_analysis']['sentiment']}")
        print(f"실시간 알림: {'Yes' if result['realtime_alert']['should_alert'] else 'No'}")
        print(f"알림 사유: {result['realtime_alert']['alert_reason']}")
        print("---")
    
    # 요약 정보
    summary = classifier.get_classification_summary(results)
    print("\n=== 분류 요약 ===")
    print(f"총 게시글: {summary['total_posts']}")
    print(f"카테고리 분포: {summary['category_distribution']}")
    print(f"우선순위 분포: {summary['priority_distribution']}")
    print(f"실시간 알림 비율: {summary['alert_ratio']:.2%}")
    print(f"치명적 버그: {summary['critical_bugs']}개")
    print(f"높은 우선순위 버그: {summary['high_priority_bugs']}개")

if __name__ == "__main__":
    main()
