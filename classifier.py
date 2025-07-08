import re

def is_bug_post(title):
    """버그 관련 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 버그 키워드 (확장)
    bug_keywords = [
        "버그", "오류", "에러", "error", "bug", "문제", "issue",
        "안되", "작동안함", "실행안됨", "튕김", "크래시", "crash",
        "비정상", "이상함", "깨짐", "망가짐", "고장"
    ]
    
    # 긍정적 키워드 (버그가 아닌 경우)
    positive_keywords = [
        "수정", "패치", "해결", "fix", "fixed", "개선"
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
        "좋아요", "감사", "굿", "추천", "최고", "완벽", "사랑",
        "good", "great", "awesome", "perfect", "love", "thanks",
        "고마워", "훌륭", "멋져", "대박", "짱"
    ]
    
    return any(keyword in title_lower for keyword in positive_keywords)

def is_negative_post(title):
    """부정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    negative_keywords = [
        "화남", "짜증", "실망", "별로", "최악", "싫어", "하지마",
        "angry", "disappointed", "hate", "worst", "bad", "terrible",
        "빡침", "열받", "어이없", "망함", "쓰레기"
    ]
    
    return any(keyword in title_lower for keyword in negative_keywords)

def classify_post(title):
    """게시글 종합 분류"""
    if is_bug_post(title):
        return "버그"
    elif is_positive_post(title):
        return "긍정"
    elif is_negative_post(title):
        return "부정"
    else:
        return "기타"
