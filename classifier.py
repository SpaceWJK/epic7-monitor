import re

def is_bug_post(title):
    """버그 관련 게시글 판별 (뽑기 관련 오탐지 제거)"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 뽑기 관련 키워드 (버그가 아님) - 확장
    gacha_keywords = [
        "뽑기", "뽑아", "뽑", "소환", "가챠", "테네", "호테네", "빛테네",
        "뉴다", "당첨", "나왔", "나와", "획득", "떴", "뜸", "1뽑", "10뽑",
        "픽업", "천장", "피티", "확률", "확정", "리롤", "리세", "리세마라",
        "뽑질", "소환권", "뽑템", "가챠템", "소환템", "뽑아봄", "뽑았음"
    ]
    
    # 뽑기 관련이면 버그가 아님
    if any(keyword in title_lower for keyword in gacha_keywords):
        return False
    
    # 버그 키워드 - 확장
    bug_keywords = [
        "버그", "오류", "에러", "error", "bug", "문제", "issue",
        "안되", "안돼", "작동안함", "실행안됨", "튕김", "크래시", "crash",
        "비정상", "이상함", "깨짐", "망가짐", "고장", "먹통",
        "로딩", "연결안", "접속안", "진행안", "표시안", "나오지않", "안나와",
        "실행불가", "동작안", "멈춤", "프리징", "freeze", "로그인안",
        "업데이트안", "다운안", "설치안", "인식안", "반응안", "클릭안"
    ]
    
    # 긍정적 키워드 (버그가 아닌 경우) - 확장
    positive_keywords = [
        "수정", "패치", "해결", "fix", "fixed", "개선", "완료", "복구",
        "정상", "해결됨", "수정됨", "고쳐짐", "개선됨", "안정화"
    ]
    
    # 버그 키워드 체크
    has_bug_keyword = any(keyword in title_lower for keyword in bug_keywords)
    
    # 긍정적 키워드가 있으면 버그가 아님
    has_positive_keyword = any(keyword in title_lower for keyword in positive_keywords)
    
    return has_bug_keyword and not has_positive_keyword

def is_positive_post(title):
    """긍정적 게시글 판별 - 확장"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    positive_keywords = [
        # 기본 긍정 키워드
        "좋아요", "감사", "굿", "추천", "최고", "완벽", "사랑",
        "good", "great", "awesome", "perfect", "love", "thanks",
        "고마워", "훌륭", "멋져", "대박", "짱",
        
        # 게임 관련 긍정 키워드
        "재밌", "재미있", "즐거", "신나", "흥미", "만족", "행복",
        "cool", "nice", "amazing", "fantastic", "excellent",
        "최고야", "좋다", "괜찮", "마음에", "예쁘", "이쁘",
        "잘만들", "잘됐", "성공", "쾌감", "뿌듯", "기분좋",
        
        # 칭찬 관련
        "칭찬", "박수", "응원", "격려", "지지", "찬성", "동감",
        "approve", "support", "like", "enjoy", "fun"
    ]
    
    return any(keyword in title_lower for keyword in positive_keywords)

def is_negative_post(title):
    """부정적 게시글 판별 - 확장"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    negative_keywords = [
        # 기본 부정 키워드
        "화남", "짜증", "실망", "별로", "최악", "싫어", "하지마",
        "angry", "disappointed", "hate", "worst", "bad", "terrible",
        "빡침", "열받", "어이없", "망함", "쓰레기",
        
        # 감정 관련 부정 키워드
        "우울", "슬프", "답답", "스트레스", "피곤", "지겨", "귀찮",
        "sad", "boring", "tired", "stress", "annoying", "frustrated",
        "후회", "아쉬", "불만", "불편", "문제", "고민", "걱정",
        
        # 비판 관련
        "비판", "비난", "욕", "욕설", "욕하", "까", "디스", "악플",
        "반대", "거부", "거절", "싫다", "안좋", "나쁘", "형편없",
        "criticize", "complain", "blame", "reject", "refuse",
        
        # 게임 관련 부정 키워드
        "노잼", "재미없", "지루", "밸런스", "밸패", "망겜", "똥겜",
        "너프", "nerf", "하향", "약화", "개악", "망친", "망쳤"
    ]
    
    return any(keyword in title_lower for keyword in negative_keywords)

def is_neutral_post(title):
    """중립적 게시글 판별 (질문, 정보, 일반적인 내용)"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 중립적 키워드 (질문, 정보, 안내 등)
    neutral_keywords = [
        # 질문 관련
        "질문", "문의", "궁금", "어떻게", "뭔가", "뭐가", "왜", "언제",
        "어디", "누구", "얼마", "몇", "question", "ask", "how", "what",
        "when", "where", "who", "why", "which", "help", "도움",
        
        # 정보 관련
        "정보", "안내", "가이드", "팁", "공략", "방법", "설명",
        "info", "guide", "tip", "tutorial", "manual", "instruction",
        "알려", "알아", "공유", "share", "inform", "notice",
        
        # 일반적인 키워드
        "확인", "체크", "검토", "비교", "선택", "추천받", "조언",
        "check", "confirm", "compare", "choose", "advice", "suggest",
        "의견", "생각", "opinion", "think", "believe", "consider",
        
        # 게임 관련 중립 키워드
        "스펙", "세팅", "설정", "장비", "아티팩트", "영웅", "캐릭터",
        "스킬", "각성", "전승", "육성", "강화", "업그레이드",
        "stats", "build", "setup", "equipment", "character", "skill",
        "awaken", "enhance", "upgrade", "level", "tier"
    ]
    
    return any(keyword in title_lower for keyword in neutral_keywords)

def classify_post(title):
    """게시글 종합 분류 (우선순위: 버그 > 긍정 > 부정 > 중립)"""
    if not title:
        return "중립"
    
    # 1순위: 버그 게시글 (가장 중요)
    if is_bug_post(title):
        return "버그"
    
    # 2순위: 긍정 게시글
    elif is_positive_post(title):
        return "긍정"
    
    # 3순위: 부정 게시글
    elif is_negative_post(title):
        return "부정"
    
    # 4순위: 중립 게시글
    elif is_neutral_post(title):
        return "중립"
    
    # 기타: 키워드가 없는 경우 중립으로 분류
    else:
        return "중립"

def get_classification_confidence(title):
    """분류 신뢰도 계산 (0.0 ~ 1.0)"""
    if not title:
        return 0.0
    
    title_lower = title.lower()
    confidence_scores = {
        "버그": 0.0,
        "긍정": 0.0,
        "부정": 0.0,
        "중립": 0.0
    }
    
    # 각 카테고리별 키워드 매칭 개수로 신뢰도 계산
    if is_bug_post(title):
        bug_matches = sum(1 for keyword in ["버그", "오류", "에러", "문제", "안되"] 
                         if keyword in title_lower)
        confidence_scores["버그"] = min(bug_matches * 0.3, 1.0)
    
    if is_positive_post(title):
        positive_matches = sum(1 for keyword in ["좋아", "감사", "최고", "대박", "굿"] 
                              if keyword in title_lower)
        confidence_scores["긍정"] = min(positive_matches * 0.25, 1.0)
    
    if is_negative_post(title):
        negative_matches = sum(1 for keyword in ["화남", "짜증", "최악", "싫어", "별로"] 
                              if keyword in title_lower)
        confidence_scores["부정"] = min(negative_matches * 0.25, 1.0)
    
    if is_neutral_post(title):
        neutral_matches = sum(1 for keyword in ["질문", "궁금", "정보", "가이드", "팁"] 
                             if keyword in title_lower)
        confidence_scores["중립"] = min(neutral_matches * 0.2, 1.0)
    
    category = classify_post(title)
    return confidence_scores.get(category, 0.1)  # 최소 0.1 신뢰도

def classify_posts_batch(posts):
    """여러 게시글을 한번에 분류"""
    results = []
    
    for post in posts:
        title = post.get('title', '') if isinstance(post, dict) else str(post)
        
        classification = {
            'title': title,
            'category': classify_post(title),
            'confidence': get_classification_confidence(title),
            'timestamp': post.get('timestamp') if isinstance(post, dict) else None,
            'url': post.get('url') if isinstance(post, dict) else None,
            'source': post.get('source') if isinstance(post, dict) else None
        }
        
        results.append(classification)
    
    return results

def get_classification_stats(classifications):
    """분류 결과 통계 생성"""
    stats = {
        "긍정": 0,
        "중립": 0,
        "부정": 0,
        "버그": 0,
        "총계": len(classifications)
    }
    
    for item in classifications:
        category = item.get('category', '중립')
        if category in stats:
            stats[category] += 1
    
    # 비율 계산
    if stats["총계"] > 0:
        for category in ["긍정", "중립", "부정", "버그"]:
            ratio = stats[category] / stats["총계"] * 100
            stats[f"{category}_비율"] = round(ratio, 1)
    
    return stats

# 테스트 함수
def test_classifier():
    """분류기 테스트"""
    test_cases = [
        ("버그 신고합니다", "버그"),
        ("게임이 너무 재밌어요!", "긍정"),
        ("이 게임 정말 별로네요", "부정"),
        ("영웅 추천 받고 싶어요", "중립"),
        ("호테네 뽑기 성공!", "중립"),  # 뽑기 관련은 중립
        ("로딩 화면에서 튕겨요", "버그"),
        ("정말 감사합니다", "긍정"),
        ("너무 화나네요", "부정"),
        ("장비 세팅 질문있어요", "중립")
    ]
    
    print("=== 분류기 테스트 결과 ===")
    for title, expected in test_cases:
        result = classify_post(title)
        confidence = get_classification_confidence(title)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{title}' → {result} (신뢰도: {confidence:.2f}) [예상: {expected}]")
    
    return test_cases

if __name__ == "__main__":
    test_classifier()