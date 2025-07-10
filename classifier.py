import re

def is_bug_post(title):
    """버그 관련 게시글 판별 (뽑기 키워드 제외)"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 뽑기 관련 키워드 (버그가 아님)
    gacha_keywords = [
        "뽑기", "뽑아", "뽑", "소환", "가챠", "테네", "호테네", "빛테네",
        "신캐", "신규", "리세", "리롤", "10연", "단뽑", "천장", "확정",
        "뽑았", "뽑나", "뽑을", "뽑자", "뽑고", "뽑히", "뽑진", "뽑네",
        "소환했", "소환할", "소환해", "소환", "가챠해", "가챠할", "가챠",
        "신캐릭터", "신규캐릭터", "리세마라", "리롤링", "연차", "연소환"
    ]
    
    # 뽑기 키워드가 있으면 버그가 아님
    if any(keyword in title_lower for keyword in gacha_keywords):
        return False
    
    # 버그 키워드 (확장)
    bug_keywords = [
        "버그", "오류", "에러", "error", "bug", "문제", "issue",
        "안되", "안돼", "작동안함", "실행안됨", "튕김", "크래시", "crash",
        "비정상", "이상함", "깨짐", "망가짐", "고장", "먹통", "멈춤",
        "접속", "연결", "로딩", "로그인", "서버", "네트워크", "끊김",
        "강제종료", "앱종료", "게임종료", "다운", "freeze", "lag"
    ]
    
    # 긍정적 키워드 (버그가 아닌 경우)
    positive_keywords = [
        "수정", "패치", "해결", "fix", "fixed", "개선", "업데이트",
        "완료", "복구", "정상", "해결됨", "고쳐짐"
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
        "좋아요", "감사", "굿", "추천", "최고", "완벽", "사랑", "대박", "짱",
        "good", "great", "awesome", "perfect", "love", "thanks", "amazing",
        "고마워", "훌륭", "멋져", "예쁘", "이쁘", "아름다", "멋있", "쩐다",
        "개꿀", "개좋", "개만족", "만족", "행복", "기쁘", "즐거", "재밌",
        "재미있", "신나", "흥미", "놀라", "대단", "훌륭", "완전", "정말",
        "역시", "최고다", "좋다", "괜찮", "나이스", "nice", "cool", "awesome"
    ]
    
    return any(keyword in title_lower for keyword in positive_keywords)

def is_negative_post(title):
    """부정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    negative_keywords = [
        "화남", "짜증", "실망", "별로", "최악", "싫어", "하지마", "그만",
        "angry", "disappointed", "hate", "worst", "bad", "terrible", "awful",
        "빡침", "열받", "어이없", "망함", "쓰레기", "개같", "개빡", "개열받",
        "노답", "답없", "멍청", "바보", "병신", "미친", "돌았", "어처구니",
        "말이안돼", "말안돼", "이해안돼", "황당", "어이상실", "개노답",
        "개별로", "개싫", "개싫어", "개못하", "개못해", "개나쁘", "개나빠"
    ]
    
    return any(keyword in title_lower for keyword in negative_keywords)

def is_neutral_post(title):
    """중립적 게시글 판별"""
    if not title:
        return True
        
    # 버그, 긍정, 부정이 모두 아니면 중립
    return not (is_bug_post(title) or is_positive_post(title) or is_negative_post(title))

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

def get_classification_stats(posts):
    """게시글 분류 통계"""
    stats = {
        "버그": 0,
        "긍정": 0,
        "부정": 0,
        "중립": 0
    }
    
    for post in posts:
        title = post.get('title', '')
        category = classify_post(title)
        stats[category] += 1
    
    return stats

# 테스트 함수
def test_classifier():
    """분류기 테스트"""
    test_titles = [
        "버그 발생했어요",
        "뽑기 버그인가요?",  # 뽑기 키워드 있으면 버그 아님
        "테네 뽑기 간다",
        "호테네 1뽑에 나왔어요",
        "게임 정말 좋아요",
        "이번 업데이트 최악이네요",
        "질문 있습니다",
        "로딩이 안되네요",
        "접속 오류",
        "뽑기 오류인가요?",  # 뽑기 + 오류 → 뽑기 우선이므로 버그 아님
    ]
    
    print("=== 분류기 테스트 ===")
    for title in test_titles:
        category = classify_post(title)
        print(f"{title:20} → {category}")

if __name__ == "__main__":
    test_classifier()