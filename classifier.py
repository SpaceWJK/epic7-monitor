import re

def is_bug_post(title):
    """버그 관련 게시글 판별 (뽑기 관련 오탐지 제거)"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 뽑기 관련 키워드 (버그가 아님)
    gacha_keywords = [
        "뽑기", "뽑아", "뽑", "소환", "가챠", "테네", "호테네", "빛테네",
        "뉴다", "당첨", "나왔", "나와", "획득", "떴", "뜸", "1뽑", "10뽑",
        "픽업", "천장", "피티", "확률", "확정"
    ]
    
    # 뽑기 관련이면 버그가 아님
    if any(keyword in title_lower for keyword in gacha_keywords):
        return False
    
    # 버그 키워드
    bug_keywords = [
        "버그", "오류", "에러", "error", "bug", "문제", "issue",
        "안되", "안돼", "작동안함", "실행안됨", "튕김", "크래시", "crash",
        "비정상", "이상함", "깨짐", "망가짐", "고장", "먹통",
        "로딩", "연결안", "접속안", "진행안", "표시안", "나오지않", "안나와"
    ]
    
    # 긍정적 키워드 (버그가 아닌 경우)
    positive_keywords = [
        "수정", "패치", "해결", "fix", "fixed", "개선", "완료", "복구"
    ]
    
    # 버그 키워드 체크
    has_bug_keyword = any(keyword in title_lower for keyword in bug_keywords)
    
    # 긍정적 키워드가 있으면 버그가 아님
    has_positive_keyword = any(keyword in title_lower for keyword in positive_keywords)
    
    return has_bug_keyword and not has_positive_keyword

def is_positive_post(title):
    """긍정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    positive_keywords = [
        "좋아요", "감사", "굿", "추천", "최고", "완벽", "사랑", "만족",
        "good", "great", "awesome", "perfect", "love", "thanks",
        "고마워", "훌륭", "멋져", "대박", "짱", "신", "개꿀", "쩐다",
        "재밌", "재미있", "즐거", "행복", "기쁘", "성공", "달성"
    ]
    
    return any(keyword in title_lower for keyword in positive_keywords)

def is_negative_post(title):
    """부정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    negative_keywords = [
        "화남", "짜증", "실망", "별로", "최악", "싫어", "하지마", "그만",
        "angry", "disappointed", "hate", "worst", "bad", "terrible",
        "빡침", "열받", "어이없", "망함", "쓰레기", "아깝", "후회",
        "노답", "답답", "스트레스", "포기", "그만둬", "접어"
    ]
    
    return any(keyword in title_lower for keyword in negative_keywords)

def is_neutral_post(title):
    """중립적 게시글 판별 (질문, 정보, 일반)"""
    if not title:
        return True
    
    title_lower = title.lower()
    
    # 이미 다른 카테고리로 분류된 경우 중립이 아님
    if is_bug_post(title) or is_positive_post(title) or is_negative_post(title):
        return False
    
    # 중립적 키워드
    neutral_keywords = [
        "질문", "문의", "궁금", "어떻", "뭐가", "언제", "어디서", "왜",
        "정보", "공유", "팁", "가이드", "방법", "추천", "비교",
        "question", "how", "what", "when", "where", "why", "info",
        "하는법", "방법좀", "알려", "도와", "조언", "의견"
    ]
    
    has_neutral_keyword = any(keyword in title_lower for keyword in neutral_keywords)
    
    # 중립 키워드가 있거나, 다른 카테고리에 해당하지 않으면 중립
    return has_neutral_keyword or True

def classify_post(title):
    """게시글 종합 분류 (우선순위: 버그 > 긍정 > 부정 > 중립)"""
    if is_bug_post(title):
        return "버그"
    elif is_positive_post(title):
        return "긍정"
    elif is_negative_post(title):
        return "부정"
    else:
        return "중립"

def classify_post_detailed(title):
    """상세 분류 정보 반환"""
    result = {
        "category": classify_post(title),
        "is_bug": is_bug_post(title),
        "is_positive": is_positive_post(title),
        "is_negative": is_negative_post(title),
        "is_neutral": is_neutral_post(title)
    }
    return result

# 테스트 함수
def test_classifier():
    """분류기 테스트"""
    test_titles = [
        "빛테네 1뽑에 뽑아옴",  # 중립 (뽑기)
        "오늘 테네 역시나!",     # 중립 (뽑기)
        "버그 신고합니다",       # 버그
        "로딩이 안되요",         # 버그
        "정말 재밌어요",         # 긍정
        "최악이네요",           # 부정
        "질문있습니다",         # 중립
        "어떻게 하나요?",       # 중립
    ]
    
    print("=== 분류기 테스트 ===")
    for title in test_titles:
        category = classify_post(title)
        detailed = classify_post_detailed(title)
        print(f"제목: {title}")
        print(f"분류: {category}")
        print(f"상세: {detailed}")
        print("-" * 50)

if __name__ == "__main__":
    test_classifier()