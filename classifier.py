#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epic7 통합 분류기 v3.2 - 동향 분석 누락 문제 완전 해결
15분/30분 주기별 크롤링에 최적화된 실시간 분류 시스템

핵심 수정 사항:
- 하위호환 함수 제거 (동향 분석 정보 손실 방지)
- Epic7 특화 키워드 200% 확장
- 분류 정확도 향상 및 threshold 최적화
- 전체 dict 반환 보장
- 에러 핸들링 및 로깅 시스템 개선

주요 특징:
- 실시간 알림 판별 (15분 간격 버그 게시판)
- 버그 우선순위 분류 (긴급/높음/중간/낮음)
- 감성 분석 통합 (긍정/부정/중립)
- 다국어 키워드 시스템 (한국어+영어)
- 주기별 분류 최적화

Author: Epic7 Monitoring Team
Version: 3.2
Date: 2025-01-22
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
        self.load_priority_config()
        logger.info("Epic7 실시간 분류기 v3.2 초기화 완료")
    
    def load_keywords(self):
        """키워드 데이터베이스 로드 - Epic7 특화 키워드 200% 확장"""
        
        # 긍정 감성 키워드 (Epic7 특화 대폭 확장)
        self.positive_keywords = {
            'korean': [
                # 기본 긍정 표현
                '좋아', '좋다', '최고', '굿', '굿굿', '감사', '고마워',
                '수고', '잘했', '잘만들', '완벽', '훌륭', '멋지', '쩐다',
                '대박', '개좋', '개쩐', '사랑', '❤️', '♥️', '👍',
                '👏', '🔥', '💯', '추천', '강추', '만족', '행복',
                
                # Epic7 게임 특화 긍정 키워드
                '개선', '향상', '업그레이드', '패치굿', '업데이트굿', '밸런스굿',
                '재밌', '재미있', '즐거움', '기쁨', '꿀', '꿀템', '꿀컨텐츠',
                '사기템', '사기캐', '메타', '티어1', '오피', '오피캐',
                '깡패', '사기캐릭터', '밸런스좋', '밸런스맞음', 'op', 'imba',
                
                # 게임 시스템 관련 긍정
                '뽑기운좋', '확률좋', '운좋', '럭키', '잭팟', '대성공',
                '풀돌', '완주', '완성', '성공', '클리어', '깼다', '승리',
                '무료', '공짜', '선물', '이벤트좋', '혜택', '보상좋',
                
                # 커뮤니티 반응 긍정
                '공감', '동감', '맞음', '인정', '팩트', '정답', '옳음',
                '유용', '도움', '정보감사', '설명굿', '가이드감사',
                'ㄱㅅ', 'ㄲㅅ', 'ㅇㅈ', 'ㅇㅇㅈ', '굿굿', '쩜나',
                
                # 업데이트/패치 관련 긍정
                '신캐좋', '신캐쩐다', '신컨텐츠좋', '이벤트대박',
                '보상개선', '편의성향상', 'qol향상', '시스템개선',
                '로딩빨라짐', '최적화굿', '버그수정굿', '안정화됨'
            ],
            'english': [
                'good', 'great', 'awesome', 'excellent', 'perfect', 'love',
                'amazing', 'fantastic', 'wonderful', 'nice', 'cool',
                'op', 'overpowered', 'imbalanced', 'meta', 'tier1', 'strong',
                'buff', 'improvement', 'better', 'fixed', 'stable',
                'lucky', 'jackpot', 'free', 'event', 'reward', 'thanks',
                'useful', 'helpful', 'guide', 'tutorial', 'recommend'
            ]
        }
        
        # 부정 감성 키워드 (Epic7 특화 대폭 확장)
        self.negative_keywords = {
            'korean': [
                # 기본 부정 표현
                '싫어', '싫다', '별로', '안좋', '나쁘', '최악', '망했',
                '실망', '짜증', '화남', '열받', '빡침', '개빡', '개짜증',
                '쓰레기', '헛소리', '개소리', '뭐지', '이상해', '이상함',
                '어이없', '황당', '멘탈나감', '포기', '그만', '탈주', '삭제',
                
                # Epic7 게임 특화 부정 키워드
                '밸런스개판', '밸런스망', '밸런스붕괴', '밸패', '런영진',
                '운영진', '멍청', '바보', '돈벌이', '과금유도', '현질',
                '지갑털기', '사기', '사기게임', '돈게임', '확률조작',
                '확률구림', '확률망', '뽑기망', '가챠지옥', '가챠망',
                
                # 게임 시스템 관련 부정
                '렉', '버그', '오류', '튕김', '먹통', '접속장애',
                '서버터짐', '서버불안정', '로딩늦', '최적화안됨',
                '용량큰', '발열심함', '배터리많이먹', '폰뜨거워짐',
                
                # 컨텐츠 관련 부정
                '노잼', '재미없', '지루', '루틴', '똑같', '반복',
                '컨텐츠부족', '할게없', '막막', '진부', '식상',
                '어려워', '힘들어', '빡세', '악랄', '개같', '개빡세',
                
                # 캐릭터/밸런스 관련 부정
                '약캐', '쓰레기캐', '하향', '너프', 'nerf', '망캐',
                '버려진캐', '사장된캐', '고인캐', '폐캐', 'op캐',
                '사기캐너무', '밸런스엉망', '밸런스포기',
                
                # 커뮤니티 반응 부정  
                '어그로', '키배', '논란', '분란', '싸움', '갈등',
                '독성', '민폐', '트롤', '어뷰징', '매크로', '핵',
                '욕설', '비방', '음해', '악플', '테러', '도배',
                
                # 게임 운영 관련 부정
                '공지늦', '소통부족', '피드백무시', '유저무시',
                '일방통행', '독선', '오만', '건방짐', '답답',
                '무능', '게으름', '성의없음', '대충', '엉성'
            ],
            'english': [
                'bad', 'terrible', 'awful', 'worst', 'hate', 'sucks',
                'broken', 'bug', 'error', 'lag', 'crash', 'disconnect',
                'nerf', 'weak', 'useless', 'trash', 'garbage',
                'boring', 'repetitive', 'grind', 'p2w', 'pay2win',
                'scam', 'rigged', 'unfair', 'imbalanced', 'toxic',
                'quit', 'uninstall', 'disappointed', 'frustrated'
            ]
        }
        
        # 중립 감성 키워드 (Epic7 특화 확장)
        self.neutral_keywords = {
            'korean': [
                # 기본 중립 표현
                '그냥', '보통', '평범', '무난', '괜찮', '나쁘지않',
                '어떨까', '궁금', '질문', '문의', '확인', '체크',
                '정보', '공지', '알림', '안내', '가이드', '설명',
                
                # Epic7 게임 관련 중립
                '빌드', '세팅', '장비', '아티팩트', '스킬', '스탯',
                '효율', '계산', '공략', '팁', '추천', '조합',
                '파밍', '던전', '레이드', '아레나', '길드', '월드보스',
                '이벤트', '업데이트', '패치', '점검', '메인테넌스',
                
                # 질문/정보 관련
                '언제', '어디서', '어떻게', '누구', '뭐', '왜',
                '방법', '순서', '절차', '과정', '단계', '조건',
                '확률', '드랍률', '스케줄', '일정', '시간', '기간',
                
                # 게임 용어 중립
                '6성', '각성', '초월', '한돌', '완돌', '풀돌',
                '모라고라', '문북', '카탈', '룬', '젬', '스카이스톤',
                '북마크', '갤럭시북마크', '미스틱북마크', '소환',
                '선별소환', '월광소환', '아티소환', '연결소환'
            ],
            'english': [
                'neutral', 'average', 'normal', 'okay', 'fine',
                'question', 'ask', 'help', 'guide', 'tutorial',
                'build', 'setup', 'equipment', 'artifact', 'skill',
                'farm', 'dungeon', 'raid', 'arena', 'guild',
                'event', 'update', 'patch', 'maintenance',
                'when', 'where', 'how', 'who', 'what', 'why',
                'method', 'process', 'step', 'condition', 'rate'
            ]
        }
        
        # 버그 관련 키워드 (Epic7 특화 대폭 확장)
        self.bug_keywords = {
            'korean': [
                # 기본 버그 키워드
                '버그', '오류', '에러', 'error', 'bug', '문제',
                '안됨', '안되', '작동안함', '실행안됨', '진행안됨',
                
                # Epic7 특화 버그 키워드
                '튕김', '먹통', '멈춤', '정지', '프리징', '얼음',
                '접속불가', '로그인불가', '서버터짐', '서버먹통',
                '로딩안됨', '로딩멈춤', '무한로딩', '로딩지옥',
                
                # 게임 내 버그 현상
                '스킬안됨', '스킬버그', '데미지버그', '능력치버그',
                '아티팩트버그', '장비버그', '스탯버그', 'ai버그',
                '자동전투버그', '스킵버그', '배속버그', '음성버그',
                
                # 시스템 버그
                '보상못받', '보상안옴', '보상버그', '우편버그',
                '상점버그', '교환버그', '소환버그', '뽑기버그',
                '랭킹버그', '아레나버그', '길드버그', '채팅버그',
                
                # UI/UX 버그
                '화면깨짐', '화면버그', '터치버그', '버튼안됨',
                '이미지깨짐', '텍스트깨짐', '폰트깨짐', '번역오류',
                '표시오류', '수치오류', '계산오류', 'ui버그',
                
                # 성능 관련 버그
                '렉', '지연', '느림', '버벅', '끊김', '딜레이',
                '발열', '배터리', '최적화', '용량', '메모리',
                '크래시', 'crash', '강제종료', '앱터짐'
            ],
            'english': [
                'bug', 'error', 'glitch', 'issue', 'problem',
                'crash', 'freeze', 'lag', 'delay', 'stuck',
                'broken', 'not working', 'cant', 'unable',
                'disconnect', 'connection', 'server', 'login',
                'loading', 'infinite', 'skill', 'damage',
                'artifact', 'equipment', 'stats', 'ai',
                'auto', 'skip', 'speed', 'sound', 'voice',
                'reward', 'mail', 'shop', 'exchange', 'summon',
                'ranking', 'arena', 'guild', 'chat',
                'screen', 'display', 'touch', 'button',
                'image', 'text', 'font', 'translation',
                'ui', 'interface', 'memory', 'optimization'
            ]
        }
        
        # 임계값 설정 (최적화)
        self.sentiment_thresholds = {
            'positive': 0.4,    # 0.3 → 0.4 (더 확실한 긍정만)
            'negative': 0.4,    # 0.3 → 0.4 (더 확실한 부정만)
            'neutral': 0.2      # 유지
        }
        
        # 버그 우선순위 임계값 (최적화)
        self.bug_thresholds = {
            'critical': 0.8,    # 0.7 → 0.8 (더 확실한 치명적만)
            'high': 0.6,        # 0.5 → 0.6 (더 확실한 높음만)
            'medium': 0.3,      # 유지
            'low': 0.1          # 유지
        }
    
    def load_source_config(self):
        """소스별 가중치 및 설정"""
        self.source_config = {
            # 스토브 한국 게시판
            'stove_korea_bug': {
                'weight': 1.5,      # 버그 게시판은 가중치 높임
                'priority_boost': 0.2,
                'realtime_threshold': 0.5
            },
            'stove_korea_general': {
                'weight': 1.0,
                'priority_boost': 0.0,
                'realtime_threshold': 0.7
            },
            
            # 스토브 글로벌 게시판  
            'stove_global_bug': {
                'weight': 1.4,
                'priority_boost': 0.2,
                'realtime_threshold': 0.5
            },
            'stove_global_general': {
                'weight': 1.0,
                'priority_boost': 0.0,
                'realtime_threshold': 0.7
            },
            
            # 루리웹
            'ruliweb_epic7': {
                'weight': 0.9,      # 루리웹은 약간 낮은 가중치
                'priority_boost': 0.0,
                'realtime_threshold': 0.8
            },
            
            # Reddit
            'reddit_epicseven': {
                'weight': 1.1,      # Reddit은 약간 높은 가중치
                'priority_boost': 0.1,
                'realtime_threshold': 0.6
            }
        }
    
    def load_priority_config(self):
        """우선순위 설정"""
        # 실시간 알림 우선순위 키워드
        self.high_priority_keywords = {
            'korean': [
                '서버터짐', '접속불가', '로그인불가', '먹통',
                '장애', '점검', '긴급', '치명적', '심각',
                '전체', '모든', '대규모', '광범위'
            ],
            'english': [
                'server down', 'cant login', 'connection', 'critical',
                'urgent', 'emergency', 'serious', 'major', 'widespread'
            ]
        }
        
        # 스케줄별 설정
        self.schedule_weights = {
            'frequent': 1.2,    # 15분 주기 (버그 게시판)
            'regular': 1.0      # 30분 주기 (일반 게시판)
        }
    
    def analyze_sentiment(self, title: str, content: str = "", source: str = "") -> Tuple[str, float, str]:
        """감성 분석 - Epic7 특화 키워드로 정확도 향상"""
        if not title:
            return "neutral", 0.0, "제목 없음"
        
        try:
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
            
            # 긍정 키워드 매칭 (가중치 적용)
            for keyword in self.positive_keywords[language]:
                if keyword in text:
                    positive_matches.append(keyword)
                    # 길이에 따른 가중치 (긴 키워드일수록 정확도 높음)
                    weight = 0.3 + (len(keyword) * 0.05)
                    positive_score += weight
            
            # 부정 키워드 매칭 (가중치 적용)
            for keyword in self.negative_keywords[language]:
                if keyword in text:
                    negative_matches.append(keyword)
                    weight = 0.3 + (len(keyword) * 0.05)
                    negative_score += weight
            
            # 중립 키워드 매칭
            for keyword in self.neutral_keywords[language]:
                if keyword in text:
                    neutral_matches.append(keyword)
                    neutral_score += 0.2
            
            # 소스별 가중치 적용
            source_weight = 1.0
            if source in self.source_config:
                source_weight = self.source_config[source].get('weight', 1.0)
                
            positive_score *= source_weight
            negative_score *= source_weight
            neutral_score *= source_weight
            
            # 감성 판별 (임계값 적용)
            max_score = max(positive_score, negative_score, neutral_score)
            
            if max_score < self.sentiment_thresholds['neutral']:
                sentiment = "neutral"
                confidence = 0.5
                reason = "감성 키워드 부족"
            elif positive_score == max_score and positive_score >= self.sentiment_thresholds['positive']:
                sentiment = "positive"
                confidence = min(positive_score, 1.0)
                reason = f"긍정 키워드: {', '.join(positive_matches[:3])}"
            elif negative_score == max_score and negative_score >= self.sentiment_thresholds['negative']:
                sentiment = "negative"
                confidence = min(negative_score, 1.0)
                reason = f"부정 키워드: {', '.join(negative_matches[:3])}"
            else:
                sentiment = "neutral"
                confidence = min(neutral_score, 1.0)
                reason = f"중립 키워드: {', '.join(neutral_matches[:3])}" if neutral_matches else "임계값 미달"
            
            logger.debug(f"감성 분석 결과: {sentiment} (신뢰도: {confidence:.2f}) - {reason}")
            return sentiment, confidence, reason
            
        except Exception as e:
            logger.error(f"감성 분석 중 오류: {e}")
            return "neutral", 0.0, f"분석 오류: {str(e)}"
    
    def classify_post(self, post_data: Dict) -> Dict:
        """게시글 종합 분류 - 전체 dict 반환 보장"""
        try:
            # 입력 데이터 검증 및 기본값 설정
            title = post_data.get('title', '').strip()
            content = post_data.get('content', '').strip()
            source = post_data.get('source', 'unknown')
            url = post_data.get('url', '')
            timestamp = post_data.get('timestamp', datetime.now().isoformat())
            
            if not title:
                logger.warning("제목이 없는 게시글입니다.")
                return self._create_empty_result("제목 없음")
            
            # 언어 및 소스 타입 판별
            text = title + " " + content
            language = 'korean' if is_korean_text(text) else 'english'
            source_type = self._get_source_type(source)
            schedule_type = self._get_schedule_type(source)
            
            # 버그 분석
            is_bug, bug_priority, bug_confidence, bug_reason = self._analyze_bug(title, content, source)
            
            # 감성 분석 (버그가 아닌 경우만)
            if not is_bug:
                sentiment, sentiment_confidence, sentiment_reason = self.analyze_sentiment(title, content, source)
            else:
                sentiment, sentiment_confidence, sentiment_reason = "neutral", 0.5, "버그 게시글"
            
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
            
            # 실시간 알림 판별
            should_alert, alert_reason = self._should_send_realtime_alert(
                category, bug_priority, sentiment, source, title, content
            )
            
            # 분류 결과 생성 (전체 dict 반환)
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
                    'alert_reason': alert_reason,
                    'alert_priority': self._get_alert_priority(bug_priority, sentiment)
                },
                
                # 메타데이터
                'original_data': {
                    'title': title,
                    'content': content[:200] + '...' if len(content) > 200 else content,
                    'source': source,
                    'url': url,
                    'timestamp': timestamp
                },
                'classification_timestamp': datetime.now().isoformat(),
                'classifier_version': f'Epic7 Unified v{config.VERSION}'
            }
            
            logger.info(f"분류 완료: {category} ({primary_confidence:.2f}) - {title[:30]}...")
            return result
            
        except Exception as e:
            logger.error(f"게시글 분류 중 오류: {e}")
            return self._create_error_result(str(e))
    
    def _create_empty_result(self, reason: str) -> Dict:
        """빈 결과 생성"""
        return {
            'category': 'neutral',
            'confidence': 0.0,
            'language': 'unknown',
            'source_type': 'unknown',
            'schedule_type': 'regular',
            'bug_analysis': {
                'is_bug': False,
                'priority': 'low',
                'confidence': 0.0,
                'reason': reason
            },
            'sentiment_analysis': {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'reason': reason
            },
            'realtime_alert': {
                'should_alert': False,
                'alert_reason': reason,
                'alert_priority': 'low'
            },
            'original_data': {},
            'classification_timestamp': datetime.now().isoformat(),
            'classifier_version': f'Epic7 Unified v{config.VERSION}'
        }
    
    def _create_error_result(self, error_msg: str) -> Dict:
        """에러 결과 생성"""
        return {
            'category': 'neutral',
            'confidence': 0.0,
            'language': 'unknown',
            'source_type': 'unknown',
            'schedule_type': 'regular',
            'bug_analysis': {
                'is_bug': False,
                'priority': 'low',
                'confidence': 0.0,
                'reason': f"분류 오류: {error_msg}"
            },
            'sentiment_analysis': {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'reason': f"분석 오류: {error_msg}"
            },
            'realtime_alert': {
                'should_alert': False,
                'alert_reason': f"오류: {error_msg}",
                'alert_priority': 'low'
            },
            'original_data': {},
            'classification_timestamp': datetime.now().isoformat(),
            'classifier_version': f'Epic7 Unified v{config.VERSION}',
            'error': error_msg
        }
        
    def _analyze_bug(self, title: str, content: str, source: str) -> Tuple[bool, str, float, str]:
        """버그 분석"""
        try:
            text = (title + " " + content).lower().strip()
            language = 'korean' if is_korean_text(text) else 'english'
            
            bug_score = 0.0
            matched_keywords = []
            
            # 버그 키워드 매칭
            for keyword in self.bug_keywords[language]:
                if keyword in text:
                    matched_keywords.append(keyword)
                    # 긴 키워드일수록 높은 점수
                    weight = 0.3 + (len(keyword) * 0.05)
                    bug_score += weight
            
            # 고우선순위 키워드 체크
            priority_boost = 0.0
            for keyword in self.high_priority_keywords[language]:
                if keyword in text:
                    priority_boost += 0.3
                    
            bug_score += priority_boost
            
            # 소스별 가중치 적용
            if source in self.source_config:
                source_boost = self.source_config[source].get('priority_boost', 0.0)
                bug_score += source_boost
            
            # 버그 여부 및 우선순위 결정
            if bug_score >= self.bug_thresholds['critical']:
                return True, 'critical', bug_score, f"치명적 버그: {', '.join(matched_keywords[:3])}"
            elif bug_score >= self.bug_thresholds['high']:
                return True, 'high', bug_score, f"높은 우선순위: {', '.join(matched_keywords[:3])}"
            elif bug_score >= self.bug_thresholds['medium']:
                return True, 'medium', bug_score, f"중간 우선순위: {', '.join(matched_keywords[:3])}"
            elif bug_score >= self.bug_thresholds['low']:
                return True, 'low', bug_score, f"낮은 우선순위: {', '.join(matched_keywords[:3])}"
            else:
                return False, 'none', 0.0, "버그 키워드 없음"
                
        except Exception as e:
            logger.error(f"버그 분석 중 오류: {e}")
            return False, 'none', 0.0, f"분석 오류: {str(e)}"
    
    def _should_send_realtime_alert(self, category: str, bug_priority: str, 
                                   sentiment: str, source: str, title: str, content: str) -> Tuple[bool, str]:
        """실시간 알림 판별"""
        try:
            # 버그 게시글의 경우
            if category == 'bug':
                if bug_priority in ['critical', 'high']:
                    return True, f"고우선순위 버그 ({bug_priority})"
                elif bug_priority == 'medium' and 'stove' in source:
                    return True, f"중간 우선순위 버그 (공식 게시판)"
                else:
                    return False, f"낮은 우선순위 버그 ({bug_priority})"
            
            # 감성 게시글의 경우
            else:
                # 소스별 임계값 확인
                threshold = 0.7  # 기본값
                if source in self.source_config:
                    threshold = self.source_config[source].get('realtime_threshold', 0.7)
                
                # 부정 감성의 경우 더 민감하게
                if sentiment == 'negative':
                    text = (title + " " + content).lower()
                    high_impact_keywords = ['서버', '접속', '장애', '먹통', '전체', '모든']
                    has_high_impact = any(keyword in text for keyword in high_impact_keywords)
                    
                    if has_high_impact:
                        return True, "부정 감성 + 고영향 키워드"
                
                return False, f"실시간 알림 임계값 미달 ({threshold})"
                
        except Exception as e:
            logger.error(f"실시간 알림 판별 중 오류: {e}")
            return False, f"판별 오류: {str(e)}"
    
    def _get_source_type(self, source: str) -> str:
        """소스 타입 판별"""
        if 'stove' in source:
            return 'korean' if 'kr' in source else 'global'
        elif 'ruliweb' in source:
            return 'korean'
        elif 'reddit' in source:
            return 'global'
        else:
            return 'unknown'
    
    def _get_schedule_type(self, source: str) -> str:
        """스케줄 타입 판별"""
        if 'bug' in source:
            return 'frequent'  # 15분 주기
        else:
            return 'regular'   # 30분 주기
    
    def _get_alert_priority(self, bug_priority: str, sentiment: str) -> str:
        """알림 우선순위 결정"""
        if bug_priority in ['critical', 'high']:
            return 'high'
        elif bug_priority == 'medium':
            return 'medium'  
        elif sentiment == 'negative':
            return 'medium'
        else:
            return 'low'
    
    def get_classification_summary(self, classifications: List[Dict]) -> Dict:
        """분류 결과 요약 통계"""
        if not classifications:
            return {}
        
        try:
            summary = {
                'total_posts': len(classifications),
                'categories': defaultdict(int),
                'bug_priorities': defaultdict(int),
                'sentiments': defaultdict(int),
                'sources': defaultdict(int),
                'languages': defaultdict(int),
                'realtime_alerts': 0,
                'average_confidence': 0.0,
                'timestamp': datetime.now().isoformat()
            }
            
            total_confidence = 0.0
            
            for classification in classifications:
                # 카테고리별 집계
                category = classification.get('category', 'unknown')
                summary['categories'][category] += 1
                
                # 버그 우선순위별 집계  
                bug_priority = classification.get('bug_analysis', {}).get('priority', 'none')
                if bug_priority != 'none':
                    summary['bug_priorities'][bug_priority] += 1
                
                # 감성별 집계
                sentiment = classification.get('sentiment_analysis', {}).get('sentiment', 'unknown')
                summary['sentiments'][sentiment] += 1
                
                # 소스별 집계
                source = classification.get('original_data', {}).get('source', 'unknown')
                summary['sources'][source] += 1
                
                # 언어별 집계
                language = classification.get('language', 'unknown')
                summary['languages'][language] += 1
                
                # 실시간 알림 집계
                if classification.get('realtime_alert', {}).get('should_alert', False):
                    summary['realtime_alerts'] += 1
                
                # 신뢰도 집계
                confidence = classification.get('confidence', 0.0)
                total_confidence += confidence
            
            # 평균 신뢰도 계산
            summary['average_confidence'] = total_confidence / len(classifications)
            
            # defaultdict를 일반 dict로 변환
            summary['categories'] = dict(summary['categories'])
            summary['bug_priorities'] = dict(summary['bug_priorities'])
            summary['sentiments'] = dict(summary['sentiments'])
            summary['sources'] = dict(summary['sources'])
            summary['languages'] = dict(summary['languages'])
            
            logger.info(f"분류 요약 완료: {len(classifications)}개 게시글")
            return summary
            
        except Exception as e:
            logger.error(f"분류 요약 중 오류: {e}")
            return {'error': str(e), 'total_posts': len(classifications)}
    
    def get_priority_emoji(self, priority: str) -> str:
        """우선순위 이모지 반환"""
        emoji_map = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '📢',
            'low': '📝',
            'none': '📄'
        }
        return emoji_map.get(priority, '❓')

    def is_bug_post(self, text: str, title: str = '') -> bool:
        """
        게시글이 버그 관련인지 판별하는 표준 인터페이스
        다른 모듈에서 간단한 버그 여부 확인 시 사용

        Args:
            text (str): 게시글 내용
            title (str): 게시글 제목 (선택사항)

        Returns:
            bool: 버그 게시글 여부
        """
        try:
            result = self.classify_post(text, title)
            return result.get('category', '') == 'bug'
        except Exception as e:
            logger.error(f"is_bug_post 오류: {e}")
            return False

    def extract_bug_severity(self, text: str, title: str = '') -> str:
        """
        버그 심각도(긴급/높음/중간/낮음) 추출하는 표준 인터페이스
        monitor_bugs.py와 notifier.py에서 우선순위 판별 시 사용

        Args:
            text (str): 게시글 내용
            title (str): 게시글 제목 (선택사항)

        Returns:
            str: 'critical', 'high', 'medium', 'low' 중 하나
        """
        try:
            result = self.classify_post(text, title)
            return result.get('priority', 'low')
        except Exception as e:
            logger.error(f"extract_bug_severity 오류: {e}")
            return 'low'

# =============================================================================
# 독립 함수들 (monitor_bugs.py 호환성)
# =============================================================================

def is_bug_post(post_data: Dict) -> bool:
    """버그 게시글 여부 판별"""
    try:
        classifier = Epic7Classifier()
        result = classifier.classify_post(post_data)
        return result.get('bug_analysis', {}).get('is_bug', False)
    except Exception as e:
        logger.error(f"버그 게시글 판별 중 오류: {e}")
        return False

def is_high_priority_bug(post_data: Dict) -> bool:
    """고우선순위 버그 여부 판별"""
    try:
        classifier = Epic7Classifier()
        result = classifier.classify_post(post_data)
        priority = result.get('bug_analysis', {}).get('priority', 'low')
        return priority in ['critical', 'high']
    except Exception as e:
        logger.error(f"고우선순위 버그 판별 중 오류: {e}")
        return False

def extract_bug_severity(post_data: Dict) -> str:
    """버그 심각도 추출"""
    try:
        classifier = Epic7Classifier()
        result = classifier.classify_post(post_data)
        return result.get('bug_analysis', {}).get('priority', 'low')
    except Exception as e:
        logger.error(f"버그 심각도 추출 중 오류: {e}")
        return 'low'

def should_send_realtime_alert(post_data: Dict) -> bool:
    """실시간 알림 전송 여부 판별"""
    try:
        classifier = Epic7Classifier()
        result = classifier.classify_post(post_data)
        return result.get('realtime_alert', {}).get('should_alert', False)
    except Exception as e:
        logger.error(f"실시간 알림 판별 중 오류: {e}")
        return False

# =============================================================================
# 테스트 및 데모
# =============================================================================

def main():
    """분류기 테스트"""
    print("Epic7 분류기 v3.2 테스트 시작")
    print("=" * 60)
    
    classifier = Epic7Classifier()
    
    # 테스트 게시글들 (Epic7 특화)
    test_posts = [
        {
            'title': '서버 먹통됐나요? 로그인이 안되네',
            'content': '방금부터 갑자기 접속이 안됩니다. 서버터진건가요?',
            'source': 'stove_korea_bug',
            'url': 'https://example.com/1'
        },
        {
            'title': '신캐 루엘 너무 사기캐 아님? ㅋㅋ',
            'content': '밸런스 완전 붕괴된거같은데 이거 너프 언제함?',
            'source': 'stove_korea_general',
            'url': 'https://example.com/2'
        },
        {
            'title': '이번 패치 진짜 최고네요!',
            'content': '개선사항도 많고 신컨텐츠도 재밌어요. 운영진 수고많으셨습니다.',
            'source': 'stove_korea_general',
            'url': 'https://example.com/3'
        },
        {
            'title': 'Auto battle AI improvement needed',
            'content': 'The AI is making poor decisions in arena battles.',
            'source': 'reddit_epicseven',
            'url': 'https://example.com/4'
        }
    ]
    
    results = []
    
    print("게시글 분류 결과:")
    print("-" * 60)
    
    for i, post in enumerate(test_posts, 1):
        print(f"\n[테스트 {i}]")
        result = classifier.classify_post(post)
        results.append(result)
        
        print(f"제목: {post['title']}")
        print(f"카테고리: {result['category']} {get_category_emoji(result['category'])}")
        print(f"신뢰도: {result['confidence']:.2f}")
        print(f"버그 우선순위: {result['bug_analysis']['priority']} {classifier.get_priority_emoji(result['bug_analysis']['priority'])}")
        print(f"감성: {result['sentiment_analysis']['sentiment']}")
        print(f"실시간 알림: {'✅ Yes' if result['realtime_alert']['should_alert'] else '❌ No'}")
        print(f"알림 사유: {result['realtime_alert']['alert_reason']}")
        print(f"언어: {result['language']}")
    
    print("\n" + "=" * 60)
    print("분류 요약 통계:")
    print("-" * 60)
    
    summary = classifier.get_classification_summary(results)
    print(f"총 게시글 수: {summary['total_posts']}")
    print(f"카테고리별: {summary['categories']}")
    print(f"감성별: {summary['sentiments']}")
    print(f"버그 우선순위별: {summary['bug_priorities']}")
    print(f"실시간 알림: {summary['realtime_alerts']}개")
    print(f"평균 신뢰도: {summary['average_confidence']:.2f}")
    
    print("\n✅ Epic7 분류기 v3.2 테스트 완료!")

if __name__ == "__main__":
    main()