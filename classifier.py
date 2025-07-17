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
            '실행안됨', '멈춤', '정지', '끊김', '튕김', '크래시', '렉', '렉걸림',
            '이상함', '이상해', '비정상', '정상작동안함', '고장', '망가짐', '훼손',
            '로딩안됨', '접속안됨', '연결안됨', '서버오류', '데이터 오류', '동작 안함', '오동작',
            '픽스', '수정', '해결', '패치', '고쳐줘', '개선좀', '제발', '빨리', '답답', '짜증', # 긴급성/해결 요구
            '프레임', '최적화', '끊김', '버벅임', '다운로드', '다운', # 성능, 다운로드 관련
            '충돌', '오류코드', '에러코드', '멈춤현상', '렉 발생', '팅김'
        ]
        
        # 글로벌 (영어) 버그 키워드
        self.global_bug_keywords = [
            'bug', 'error', 'issue', 'problem', 'not working', 'malfunction', 'crash', 'freeze',
            'stuck', 'disconnect', 'lag', 'glitch', 'broken', 'corrupted',
            'loading failed', 'connection failed', 'server error', 'data error',
            'fix', 'patch', 'resolve', 'fix it', 'please fix', 'urgent', 'annoying',
            'frame', 'optimization', 'stuttering', 'download',
            'conflict', 'error code', 'crash report', 'stalling', 'disconnecting'
        ]

        # 긍정 키워드
        self.positive_keywords = {
            'korean': [
                '좋아요', '좋다', '최고', '완벽', '만족', '감사', '고마워', '기대',
                '재밌다', '즐겁다', '행복', '사랑', '추천', '환영', '깔끔', '편리',
                '혜자', '이벤트', '선물', '보상', '업데이트', '신규', '대박', '흥미진진', '멋진',
                '수정', '해결', '개선', '고침', '해냈다', # 버그 해결 관련 긍정
            ],
            'global': [
                'good', 'great', 'best', 'perfect', 'satisfied', 'thanks', 'thank you', 'expect',
                'fun', 'enjoy', 'happy', 'love', 'recommend', 'welcome', 'clean', 'convenient',
                'generous', 'event', 'gift', 'reward', 'update', 'new', 'awesome', 'exciting', 'cool',
                'fixed', 'resolved', 'improved', 'correction', 'nailed it' # bug fix related positive
            ]
        }

        # 부정 키워드
        self.negative_keywords = {
            'korean': [
                '나빠요', '나쁘다', '불만', '불편', '최악', '실망', '화남', '짜증',
                '환불', '삭제', '망겜', '망했', '접음', '유료', '과금', '현질', '돈', '없다',
                '느림', '버벅임', '부족', '필요', '문제', '심각', '삭제', '불안정',
                '버그', '오류', '에러' # 버그 키워드도 부정으로 분류될 수 있음
            ],
            'global': [
                'bad', 'worst', 'disappointed', 'angry', 'frustrated', 'upset',
                'refund', 'delete', 'dead game', 'quit', 'paid', 'expensive', 'money', 'lack',
                'slow', 'laggy', 'insufficient', 'needs', 'issue', 'serious', 'unstable',
                'bug', 'error' # bug keywords can also be classified as negative
            ]
        }
        
        # 고우선순위 버그 키워드 (치명적이고 즉각적인 대응이 필요한 버그)
        self.high_priority_bug_keywords = {
            'korean': [
                '계정', '로그인', '접속', '데이터', '아이템', '재화', '골드', '장비', '재료', '결제',
                '사라짐', '증발', '삭제됨', '초기화', '오결제', '환불불가', '진행불가', '플레이 불가',
                '서버 다운', '서버 점검', '긴급 점검', '응급', '긴급', '바로', '지금 당장'
            ],
            'global': [
                'account', 'login', 'connect', 'data', 'item', 'currency', 'gold', 'equipment', 'materials', 'payment',
                'lost', 'missing', 'deleted', 'reset', 'mis-payment', 'cannot refund', 'unplayable', 'game breaking',
                'server down', 'server maintenance', 'emergency maintenance', 'urgent', 'critical', 'immediately', 'right now'
            ]
        }

    def load_source_config(self):
        """소스별 언어 설정을 로드 (향후 확장 대비)"""
        self.source_languages = {
            "stove_bug": "korean",
            "stove_general": "korean",
            "ruliweb_epic7": "korean",
            "arca_epic7": "korean",
            "stove_global_bug": "global",
            "stove_global_general": "global",
            "reddit_epic7": "global",
            "epic7_official_forum": "global"
        }
        
    def _get_language_mode(self, source: str) -> str:
        """소스에 따른 언어 모드 반환"""
        if self.mode == "all":
            return self.source_languages.get(source, "korean") # 기본값은 korean
        return self.mode # 'korean' 또는 'global' 모드일 경우 해당 모드 반환

    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """텍스트에 키워드가 포함되어 있는지 확인합니다."""
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        return False
        
    def _contains_regex_keywords(self, text: str, keywords: List[str]) -> bool:
        """정규식 키워드가 텍스트에 포함되어 있는지 확인합니다."""
        text_lower = text.lower()
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower): # 단어 경계 일치
                return True
        return False

    def classify_post(self, post: Dict[str, Any]) -> Dict[str, str]:
        """
        게시글을 버그/긍정/부정/중립으로 분류합니다.
        Args:
            post: {"title": "게시글 제목", "content": "게시글 내용", "source": "게시판 소스"}
        Returns:
            {"category": "버그"|"긍정"|"부정"|"중립", "sentiment": "positive"|"negative"|"neutral"}
        """
        title = post.get('title', '')
        content = post.get('content', '')
        source = post.get('source', '')
        
        language_mode = self._get_language_mode(source)
        
        combined_text = title + " " + content # 제목과 내용을 결합하여 분석

        # 1. 버그 분류 (가장 높은 우선순위)
        if self.is_bug_post(post):
            return {"category": "버그", "sentiment": "negative"}
            
        # 2. 감성 분류
        is_positive = self._contains_keywords(combined_text, self.positive_keywords.get(language_mode, []))
        is_negative = self._contains_keywords(combined_text, self.negative_keywords.get(language_mode, []))
        
        # 중복 분류 방지 및 우선순위
        if is_positive and is_negative:
            # 긍정/부정 키워드가 모두 있으면 복합적이거나 중립으로 판단
            return {"category": "중립", "sentiment": "neutral"}
        elif is_positive:
            return {"category": "긍정", "sentiment": "positive"}
        elif is_negative:
            return {"category": "부정", "sentiment": "negative"}
        
        # 3. 기타 (위 분류에 해당하지 않는 경우)
        return {"category": "기타", "sentiment": "neutral"}

    def is_bug_post(self, post: Dict[str, Any]) -> bool:
        """
        게시글이 버그 관련인지 판단합니다.
        classifier.py 외부에서 호출될 때 사용될 수 있는 wrapper 함수
        """
        title = post.get('title', '')
        content = post.get('content', '')
        source = post.get('source', '')
        
        language_mode = self._get_language_mode(source)
        
        combined_text = title + " " + content
        
        # 소스 자체가 버그 게시판인 경우
        if source in ["stove_bug", "stove_global_bug"]:
            return True # 버그 게시판에 올라온 글은 무조건 버그로 간주
            
        # 키워드 기반 분류
        bug_keywords = self.korean_bug_keywords if language_mode == "korean" else self.global_bug_keywords
        
        # 부정 키워드 중 버그 관련 키워드도 포함
        general_negative_bug_keywords = ['문제', 'problem', 'issue', '심각', 'serious']
        
        if self._contains_keywords(combined_text, bug_keywords):
            # 버그 해결 키워드가 동시에 있으면 버그가 아닐 가능성 있음 (예: "버그 수정 완료")
            positive_bug_resolution_keywords = self.positive_keywords.get(language_mode, [])
            if not self._contains_keywords(combined_text, positive_bug_resolution_keywords):
                return True
            else:
                print(f"[INFO] 버그 키워드와 해결 키워드 동시 발견 (버그 아님): {title}")
                return False
        
        # 일반 부정 키워드 중 버그와 연관될 수 있는 경우 추가 판단
        if self._contains_keywords(combined_text, general_negative_bug_keywords):
            # 추가적인 버그 관련 뉘앙스 확인 (예: '오류가 심각하다')
            # 이 부분은 더 복잡한 NLP 모델로 발전 가능
            if any(kw in combined_text for kw in ['안됨', 'crash', 'freeze', 'server error']): # 좀 더 명확한 버그 징후
                return True
        
        return False

    def is_positive_post(self, post: Dict[str, Any]) -> bool:
        """게시글이 긍정적인지 판단합니다."""
        title = post.get('title', '')
        content = post.get('content', '')
        source = post.get('source', '')
        language_mode = self._get_language_mode(source)
        combined_text = title + " " + content
        return self._contains_keywords(combined_text, self.positive_keywords.get(language_mode, []))

    def is_negative_post(self, post: Dict[str, Any]) -> bool:
        """게시글이 부정적인지 판단합니다."""
        title = post.get('title', '')
        content = post.get('content', '')
        source = post.get('source', '')
        language_mode = self._get_language_mode(source)
        combined_text = title + " " + content
        return self._contains_keywords(combined_text, self.negative_keywords.get(language_mode, []))
        
    def is_high_priority_bug(self, title: str, content: str) -> bool:
        """
        게시글이 고우선순위 버그인지 판단합니다 (치명적인 영향).
        제목과 내용에 고우선순위 버그 키워드가 포함되어 있는지 확인합니다.
        """
        # 이 함수는 `monitor_bugs.py`에서 `is_bug_post`와 별개로 직접 호출될 수 있음
        # 따라서 여기서도 언어 모드를 판단해야 합니다.
        # 이 예시에서는 단순화를 위해 모든 키워드를 사용하거나, 호출부에서 언어 정보를 넘겨줘야 합니다.
        # 현재는 한국어/글로벌 키워드를 모두 사용하여 탐지합니다.
        
        combined_text = (title + " " + content).lower()
        
        # 한국어 고우선순위 키워드 검사
        if self._contains_keywords(combined_text, self.high_priority_bug_keywords['korean']):
            return True
        
        # 글로벌 고우선순위 키워드 검사
        if self._contains_keywords(combined_text, self.high_priority_bug_keywords['global']):
            return True
            
        return False

    def get_category_emoji(self, category: str) -> str:
        """카테고리별 이모지 반환"""
        emojis = {
            "버그": "🐞",
            "긍정": "✨",
            "부정": "🚨",
            "중립": "💬",
            "기타": "📝"
        }
        return emojis.get(category, "❓")

# 외부에서 호출될 유틸리티 함수 (하위 호환성)
def classify_post(post: Dict[str, Any]) -> Dict[str, str]:
    """Epic7Classifier 인스턴스를 생성하여 게시글을 분류합니다 (외부 호출용 래퍼)."""
    classifier = Epic7Classifier() # 기본 'all' 모드로 초기화
    return classifier.classify_post(post)

def is_bug_post(post: Dict[str, Any]) -> bool:
    """Epic7Classifier 인스턴스를 생성하여 게시글이 버그인지 판단합니다 (외부 호출용 래퍼)."""
    classifier = Epic7Classifier() # 기본 'all' 모드로 초기화
    return classifier.is_bug_post(post)

def is_positive_post(post: Dict[str, Any]) -> bool:
    """Epic7Classifier 인스턴스를 생성하여 게시글이 긍정적인지 판단합니다 (외부 호출용 래퍼)."""
    classifier = Epic7Classifier() # 기본 'all' 모드로 초기화
    return classifier.is_positive_post(post)

def is_negative_post(post: Dict[str, Any]) -> bool:
    """Epic7Classifier 인스턴스를 생성하여 게시글이 부정적인지 판단합니다 (외부 호출용 래퍼)."""
    classifier = Epic7Classifier() # 기본 'all' 모드로 초기화
    return classifier.is_negative_post(post)
    
def get_category_emoji(category: str) -> str:
    """카테고리별 이모지 반환 (하위 호환성)"""
    classifier = Epic7Classifier()
    return classifier.get_category_emoji(category)


# 사용 예제
if __name__ == "__main__":
    # 분류기 초기화
    # mode를 "korean" 또는 "global"로 지정하여 특정 언어 모드 테스트 가능
    classifier_korean = Epic7Classifier(mode="korean")
    classifier_global = Epic7Classifier(mode="global")
    classifier_all = Epic7Classifier(mode="all")
    
    print("\n--- 한국어 모드 테스트 ---")
    test_posts_korean = [
        {
            'title': '게임에서 크래시 버그가 발생했어요',
            'content': '로그인할 때 계속 강제종료가 나요',
            'source': 'stove_bug'
        },
        {
            'title': '이번 업데이트 정말 좋아요',
            'content': '새로운 기능이 훌륭합니다. 개발팀 최고!',
            'source': 'stove_general'
        },
        {
            'title': '연결이 자주 끊겨요',
            'content': '서버 문제인가요? 접속이 너무 불안정합니다.',
            'source': 'ruliweb_epic7'
        },
        {
            'title': '버그 수정 완료! 감사합니다.',
            'content': '지난주에 제보했던 버그가 드디어 고쳐졌네요. 수고하셨습니다.',
            'source': 'arca_epic7'
        },
        {
            'title': '아이템 증발 버그',
            'content': '결제 후 아이템이 사라졌습니다. 긴급 확인 부탁드립니다.',
            'source': 'stove_bug'
        },
        {
            'title': '그냥 뭐.. 평범한데?',
            'content': '특별히 좋지도 나쁘지도 않아요.',
            'source': 'stove_general'
        }
    ]
    
    for post in test_posts_korean:
        result = classifier_korean.classify_post(post)
        print(f"제목: '{post['title']}'")
        print(f"소스: {post['source']}, 언어 모드: {classifier_korean._get_language_mode(post['source'])}")
        print(f"분류: {result['category']} ({classifier_korean.get_category_emoji(result['category'])}), 감성: {result['sentiment']}")
        print(f"고우선순위 버그: {classifier_korean.is_high_priority_bug(post.get('title',''), post.get('content',''))}")
        print("-" * 30)

    print("\n--- 글로벌 (영어) 모드 테스트 ---")
    test_posts_global = [
        {
            'title': 'Game has a severe crash bug',
            'content': 'Force close occurs during login frequently.',
            'source': 'stove_global_bug'
        },
        {
            'title': 'New character is amazing, love the design!',
            'content': 'This update truly improves the game experience. Thank you, Smilegate.',
            'source': 'epic7_official_forum'
        },
        {
            'title': 'Constant disconnections from server',
            'content': 'Having severe connection issues. Server problem?',
            'source': 'reddit_epic7'
        },
        {
            'title': 'Bug fix completed, thank you!',
            'content': 'The bug I reported last week has finally been fixed. Good job!',
            'source': 'stove_global_general'
        },
        {
            'title': 'Account reset bug!',
            'content': 'My account was completely reset after the patch. This is critical!',
            'source': 'reddit_epic7'
        },
        {
            'title': 'Nothing special, just average',
            'content': 'Neither good nor bad, just an average experience.',
            'source': 'epic7_official_forum'
        }
    ]

    for post in test_posts_global:
        result = classifier_global.classify_post(post)
        print(f"제목: '{post['title']}'")
        print(f"소스: {post['source']}, 언어 모드: {classifier_global._get_language_mode(post['source'])}")
        print(f"분류: {result['category']} ({classifier_global.get_category_emoji(result['category'])}), 감성: {result['sentiment']}")
        print(f"고우선순위 버그: {classifier_global.is_high_priority_bug(post.get('title',''), post.get('content',''))}")
        print("-" * 30)
        
    print("\n--- 'all' 모드 (혼합) 테스트 ---")
    test_posts_all = test_posts_korean + test_posts_global
    for post in test_posts_all:
        result = classifier_all.classify_post(post)
        print(f"제목: '{post['title']}'")
        print(f"소스: {post['source']}, 언어 모드: {classifier_all._get_language_mode(post['source'])}")
        print(f"분류: {result['category']} ({classifier_all.get_category_emoji(result['category'])}), 감성: {result['sentiment']}")
        print(f"고우선순위 버그: {classifier_all.is_high_priority_bug(post.get('title',''), post.get('content',''))}")
        print("-" * 30)

    print("\n--- 유틸리티 함수 테스트 ---")
    test_post_wrapper = {
        'title': '심각한 버그 발생, 게임이 멈췄어요.',
        'content': '로그인 후 아무것도 할 수 없습니다.',
        'source': 'stove_bug'
    }
    print(f"유틸리티 is_bug_post: {is_bug_post(test_post_wrapper)}")
    print(f"유틸리티 classify_post: {classify_post(test_post_wrapper)}")
    print(f"유틸리티 get_category_emoji('버그'): {get_category_emoji('버그')}")