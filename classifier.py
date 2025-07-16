# classifier.py
# Epic7 모니터링 시스템 - 완전 개선된 분류 엔진
# Korean/Global 모드 분기 처리와 다국어 키워드 분석 지원

import re
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

class Epic7Classifier:
    """Epic7 모니터링 시스템 분류 엔진"""
    
    def __init__(self, mode: str = "all"):
        """
        분류기 초기화
        Args:
            mode: 'korean', 'global', 'all'
        """
        self.mode = mode
        self.load_keywords()
        self.load_source_config()
        
        print(f"[INFO] Epic7 분류기 초기화 완료 (모드: {mode})")
    
    def load_keywords(self):
        """다국어 키워드 로드"""
        
        # 한국어 버그 키워드
        self.korean_bug_keywords = [
            '버그', '오류', '에러', '문제', '안되', '안됨', '작동안함',
            '실행안됨', '멈춤', '정지', '끊김', '튕김', '크래시',
            '이상함', '이상해', '비정상', '정상작동안함',
            '로딩안됨', '접속안됨', '연결안됨', '서버오류',
            '게임오류', '앱오류', '화면오류', '사운드오류',
            '결제오류', '업데이트오류', '설치오류'
        ]
        
        # 영어 버그 키워드
        self.english_bug_keywords = [
            'bug', 'error', 'issue', 'problem', 'glitch', 'crash',
            'broken', 'not working', 'doesnt work', 'not responding',
            'frozen', 'stuck', 'loading issue', 'connection error',
            'server error', 'payment error', 'update error',
            'installation error', 'game error', 'app error',
            'screen error', 'sound error', 'visual bug',
            'gameplay bug', 'ui bug', 'interface bug'
        ]
        
        # 한국어 긍정 키워드
        self.korean_positive_keywords = [
            '좋아', '좋다', '최고', '굿', '굿굿', '감사', '고마워',
            '수고', '잘했', '잘만들', '완벽', '훌륭', '멋지', '쩐다',
            '대박', '개좋', '개쩐', '사랑', '❤️', '♥️', '👍',
            '👏', '🔥', '💯', '개선', '향상', '업그레이드',
            '패치굿', '업데이트굿', '밸런스굿'
        ]
        
        # 영어 긍정 키워드
        self.english_positive_keywords = [
            'good', 'great', 'awesome', 'amazing', 'excellent',
            'perfect', 'love', 'like', 'enjoy', 'fun', 'cool',
            'nice', 'wonderful', 'fantastic', 'brilliant',
            'improvement', 'better', 'upgrade', 'enhanced',
            'thanks', 'thank you', 'appreciate', 'well done',
            '❤️', '♥️', '👍', '👏', '🔥', '💯'
        ]
        
        # 한국어 부정 키워드
        self.korean_negative_keywords = [
            '싫어', '싫다', '별로', '안좋', '나쁘', '최악', '망했',
            '실망', '짜증', '화남', '열받', '빡침', '개빡', '개짜증',
            '쓰레기', '헛소리', '개소리', '뭐지', '이상해', '이상함',
            '너무어려워', '너무힘들어', '포기', '그만', '탈주',
            '밸런스개판', '밸런스망', '운영진', '멍청', '바보'
        ]
        
        # 영어 부정 키워드
        self.english_negative_keywords = [
            'bad', 'terrible', 'awful', 'horrible', 'hate',
            'dislike', 'annoying', 'frustrating', 'disappointed',
            'angry', 'mad', 'stupid', 'dumb', 'trash', 'garbage',
            'worst', 'sucks', 'boring', 'too hard', 'too difficult',
            'give up', 'quit', 'uninstall', 'balance sucks',
            'devs suck', 'developers suck', 'wtf', 'wth'
        ]
        
        # 버그 제외 키워드 (긍정적 맥락)
        self.bug_exclusion_keywords = [
            '수정', '해결', '고침', '패치', '업데이트', '개선',
            'fixed', 'solved', 'patched', 'updated', 'improved',
            '버그수정', '오류수정', 'bug fix', 'error fix',
            '문제해결', 'issue resolved'
        ]
        
        # 고우선순위 버그 키워드 (추가됨)
        self.high_priority_bug_keywords = [
            '크래시', '강제종료', '멈춤', '정지', '튕김',
            'crash', 'force close', 'frozen', 'stuck',
            '서버오류', '접속안됨', '로그인안됨',
            'server error', 'connection error', 'login error',
            '결제오류', '업데이트오류', '설치오류',
            'payment error', 'update error', 'installation error',
            '데이터손실', '진행안됨', '게임안됨',
            'data loss', 'progress lost', 'game broken'
        ]
    
    def load_source_config(self):
        """소스별 설정 로드"""
        self.source_config = {
            # 한국 소스
            'stove_bug': {
                'type': 'korean',
                'weight': 1.0,
                'bug_priority': 'high',
                'sentiment_weight': 0.8
            },
            'stove_general': {
                'type': 'korean',
                'weight': 0.8,
                'bug_priority': 'medium',
                'sentiment_weight': 1.0
            },
            'ruliweb_epic7': {
                'type': 'korean',
                'weight': 0.9,
                'bug_priority': 'medium',
                'sentiment_weight': 0.9
            },
            
            # 글로벌 소스
            'stove_global_bug': {
                'type': 'global',
                'weight': 1.0,
                'bug_priority': 'high',
                'sentiment_weight': 0.8
            },
            'stove_global_general': {
                'type': 'global',
                'weight': 0.8,
                'bug_priority': 'medium',
                'sentiment_weight': 1.0
            },
            'reddit_epic7': {
                'type': 'global',
                'weight': 0.9,
                'bug_priority': 'medium',
                'sentiment_weight': 0.9
            },
            'official_forum': {
                'type': 'global',
                'weight': 0.7,
                'bug_priority': 'low',
                'sentiment_weight': 0.7
            }
        }
    
    def is_korean_text(self, text: str) -> bool:
        """한국어 텍스트 판별"""
        if not text:
            return False
        
        korean_count = len(re.findall(r'[가-힣]', text))
        total_chars = len(re.findall(r'[가-힣a-zA-Z]', text))
        
        if total_chars == 0:
            return False
        
        return korean_count / total_chars > 0.3
    
    def is_bug_post(self, title: str, content: str = "", source: str = "") -> Tuple[bool, float, str]:
        """
        버그 게시글 판별 (다국어 지원)
        
        Returns:
            (is_bug, confidence, reason)
        """
        if not title:
            return False, 0.0, "제목 없음"
        
        # 소스가 버그 전용 게시판인 경우
        if source in ['stove_bug', 'stove_global_bug']:
            return True, 1.0, f"버그 전용 게시판 ({source})"
        
        # 텍스트 정규화
        text = (title + " " + content).lower().strip()
        
        # 버그 제외 키워드 확인 (긍정적 맥락)
        for exclusion in self.bug_exclusion_keywords:
            if exclusion in text:
                return False, 0.0, f"버그 제외 키워드 발견: {exclusion}"
        
        # 언어 판별
        is_korean = self.is_korean_text(text)
        
        # 버그 키워드 매칭
        bug_keywords = self.korean_bug_keywords if is_korean else self.english_bug_keywords
        
        matched_keywords = []
        confidence = 0.0
        
        for keyword in bug_keywords:
            if keyword in text:
                matched_keywords.append(keyword)
                
                # 키워드별 가중치 적용
                if keyword in ['버그', 'bug', '오류', 'error']:
                    confidence += 0.4
                elif keyword in ['문제', 'issue', 'problem']:
                    confidence += 0.3
                else:
                    confidence += 0.2
        
        # 소스별 가중치 적용
        if source in self.source_config:
            source_weight = self.source_config[source]['weight']
            confidence *= source_weight
        
        # 임계값 판별
        is_bug = confidence >= 0.3
        
        reason = f"매칭 키워드: {', '.join(matched_keywords)}" if matched_keywords else "키워드 없음"
        
        return is_bug, min(confidence, 1.0), reason
    
    def is_high_priority_bug(self, title: str, content: str = "", source: str = "") -> bool:
        """
        고우선순위 버그 판별 (새로 추가된 함수)
        
        Args:
            title: 게시글 제목
            content: 게시글 내용
            source: 소스 타입
            
        Returns:
            bool: 고우선순위 버그 여부
        """
        if not title:
            return False
        
        # 먼저 버그 게시글인지 확인
        is_bug, confidence, _ = self.is_bug_post(title, content, source)
        
        if not is_bug:
            return False
        
        # 소스별 우선순위 확인
        if source in self.source_config:
            source_priority = self.source_config[source].get('bug_priority', 'medium')
            if source_priority == 'high':
                return True
        
        # 텍스트 정규화
        text = (title + " " + content).lower().strip()
        
        # 고우선순위 키워드 매칭
        for keyword in self.high_priority_bug_keywords:
            if keyword in text:
                return True
        
        # 버그 신뢰도가 매우 높은 경우
        if confidence >= 0.8:
            return True
        
        return False
    
    def analyze_sentiment(self, title: str, content: str = "", source: str = "") -> Tuple[str, float, str]:
        """
        감성 분석 (다국어 지원)
        
        Returns:
            (sentiment, confidence, reason)
        """
        if not title:
            return "neutral", 0.0, "제목 없음"
        
        # 텍스트 정규화
        text = (title + " " + content).lower().strip()
        
        # 언어 판별
        is_korean = self.is_korean_text(text)
        
        # 감성 키워드 선택
        positive_keywords = self.korean_positive_keywords if is_korean else self.english_positive_keywords
        negative_keywords = self.korean_negative_keywords if is_korean else self.english_negative_keywords
        
        # 감성 점수 계산
        positive_score = 0.0
        negative_score = 0.0
        
        positive_matches = []
        negative_matches = []
        
        # 긍정 키워드 매칭
        for keyword in positive_keywords:
            if keyword in text:
                positive_matches.append(keyword)
                positive_score += 0.3
        
        # 부정 키워드 매칭
        for keyword in negative_keywords:
            if keyword in text:
                negative_matches.append(keyword)
                negative_score += 0.3
        
        # 소스별 가중치 적용
        if source in self.source_config:
            sentiment_weight = self.source_config[source]['sentiment_weight']
            positive_score *= sentiment_weight
            negative_score *= sentiment_weight
        
        # 감성 판별
        if positive_score > negative_score and positive_score >= 0.3:
            sentiment = "positive"
            confidence = min(positive_score, 1.0)
            reason = f"긍정 키워드: {', '.join(positive_matches)}"
        elif negative_score > positive_score and negative_score >= 0.3:
            sentiment = "negative"
            confidence = min(negative_score, 1.0)
            reason = f"부정 키워드: {', '.join(negative_matches)}"
        else:
            sentiment = "neutral"
            confidence = 0.5
            reason = "중립적 내용"
        
        return sentiment, confidence, reason
    
    def classify_post(self, post_data: Dict) -> Dict:
        """
        게시글 종합 분류
        
        Args:
            post_data: {
                'title': str,
                'content': str,
                'source': str,
                'url': str,
                'timestamp': str
            }
        
        Returns:
            분류 결과 딕셔너리
        """
        title = post_data.get('title', '')
        content = post_data.get('content', '')
        source = post_data.get('source', '')
        
        # 버그 분석
        is_bug, bug_confidence, bug_reason = self.is_bug_post(title, content, source)
        
        # 감성 분석
        sentiment, sentiment_confidence, sentiment_reason = self.analyze_sentiment(title, content, source)
        
        # 소스 타입 확인
        source_type = 'unknown'
        if source in self.source_config:
            source_type = self.source_config[source]['type']
        
        # 언어 판별
        language = 'korean' if self.is_korean_text(title + " " + content) else 'english'
        
        # 최종 카테고리 결정
        if is_bug:
            category = 'bug'
            priority = self.source_config.get(source, {}).get('bug_priority', 'medium')
        elif sentiment == 'positive':
            category = 'positive'
            priority = 'low'
        elif sentiment == 'negative':
            category = 'negative'
            priority = 'medium'
        else:
            category = 'neutral'
            priority = 'low'
        
        # 결과 반환
        result = {
            'category': category,
            'priority': priority,
            'language': language,
            'source_type': source_type,
            'bug_analysis': {
                'is_bug': is_bug,
                'confidence': bug_confidence,
                'reason': bug_reason
            },
            'sentiment_analysis': {
                'sentiment': sentiment,
                'confidence': sentiment_confidence,
                'reason': sentiment_reason
            },
            'classification_timestamp': datetime.now().isoformat(),
            'classifier_version': 'Enhanced Complete v2.0'
        }
        
        return result
    
    def get_category_emoji(self, category: str) -> str:
        """카테고리별 이모지 반환"""
        emoji_map = {
            'bug': '🐛',
            'positive': '😊',
            'negative': '😞',
            'neutral': '😐'
        }
        return emoji_map.get(category, '❓')
    
    def should_send_alert(self, classification: Dict) -> bool:
        """알림 전송 여부 판별"""
        category = classification.get('category', 'neutral')
        priority = classification.get('priority', 'low')
        
        # 버그는 항상 알림
        if category == 'bug':
            return True
        
        # 우선순위가 높은 경우 알림
        if priority == 'high':
            return True
        
        # 부정적 감성이 높은 경우 알림
        sentiment_confidence = classification.get('sentiment_analysis', {}).get('confidence', 0.0)
        if category == 'negative' and sentiment_confidence >= 0.7:
            return True
        
        return False
    
    def get_classification_summary(self, classifications: List[Dict]) -> Dict:
        """분류 결과 요약"""
        if not classifications:
            return {}
        
        total_count = len(classifications)
        category_counts = defaultdict(int)
        language_counts = defaultdict(int)
        source_type_counts = defaultdict(int)
        
        for classification in classifications:
            category_counts[classification.get('category', 'neutral')] += 1
            language_counts[classification.get('language', 'unknown')] += 1
            source_type_counts[classification.get('source_type', 'unknown')] += 1
        
        summary = {
            'total_posts': total_count,
            'category_distribution': dict(category_counts),
            'language_distribution': dict(language_counts),
            'source_type_distribution': dict(source_type_counts),
            'bug_ratio': category_counts['bug'] / total_count if total_count > 0 else 0,
            'positive_ratio': category_counts['positive'] / total_count if total_count > 0 else 0,
            'negative_ratio': category_counts['negative'] / total_count if total_count > 0 else 0,
            'summary_timestamp': datetime.now().isoformat()
        }
        
        return summary


# 편의 함수들
def is_bug_post(title: str, content: str = "", source: str = "") -> bool:
    """버그 게시글 판별 (하위 호환성)"""
    classifier = Epic7Classifier()
    is_bug, _, _ = classifier.is_bug_post(title, content, source)
    return is_bug

def is_high_priority_bug(title: str, content: str = "", source: str = "") -> bool:
    """고우선순위 버그 판별 (새로 추가된 편의 함수)"""
    classifier = Epic7Classifier()
    return classifier.is_high_priority_bug(title, content, source)

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

def get_category_emoji(category: str) -> str:
    """카테고리별 이모지 반환 (하위 호환성)"""
    classifier = Epic7Classifier()
    return classifier.get_category_emoji(category)


# 사용 예제
if __name__ == "__main__":
    # 분류기 초기화
    classifier = Epic7Classifier(mode="all")
    
    # 테스트 게시글
    test_posts = [
        {
            'title': '게임에서 크래시 버그가 발생했어요',
            'content': '로그인할 때 계속 강제종료가 나요',
            'source': 'stove_bug'
        },
        {
            'title': 'Game has a crash bug',
            'content': 'Force close occurs during login',
            'source': 'stove_global_bug'
        },
        {
            'title': '이번 업데이트 정말 좋아요',
            'content': '새로운 기능이 훌륭합니다',
            'source': 'stove_general'
        }
    ]
    
    # 분류 실행
    results = []
    for post in test_posts:
        result = classifier.classify_post(post)
        results.append(result)
        print(f"제목: {post['title']}")
        print(f"분류: {result['category']} ({classifier.get_category_emoji(result['category'])})")
        print(f"고우선순위 버그: {classifier.is_high_priority_bug(post['title'], post['content'], post['source'])}")
        print(f"언어: {result['language']}")
        print(f"소스: {result['source_type']}")
        print("---")
    
    # 요약 정보
    summary = classifier.get_classification_summary(results)
    print("분류 요약:")
    print(f"총 게시글: {summary['total_posts']}")
    print(f"카테고리 분포: {summary['category_distribution']}")
    print(f"언어 분포: {summary['language_distribution']}")