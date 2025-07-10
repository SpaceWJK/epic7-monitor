import re

def is_bug_post(title):
    """버그 관련 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 버그 키워드 (확장 및 최적화)
    bug_keywords = [
        # 직접적인 버그 표현
        "버그", "오류", "에러", "error", "bug", "문제", "issue",
        "안되", "안됨", "작동안함", "실행안됨", "동작안함",
        "튕김", "튕겨", "크래시", "crash", "멈춤", "정지",
        "비정상", "이상함", "이상해", "깨짐", "망가짐", "고장",
        "먹통", "먹먹", "로딩", "연결", "접속", "네트워크",
        "서버", "클라이언트", "업데이트", "패치", "버전",
        "설치", "다운로드", "실행", "시작", "종료", "강제종료",
        "화면", "디스플레이", "그래픽", "사운드", "음성",
        "입력", "출력", "저장", "불러오기", "로그인", "로그아웃",
        # 게임 특화 버그 표현
        "인게임", "게임", "플레이", "캐릭터", "아이템", "스킬",
        "퀘스트", "미션", "던전", "레이드", "pvp", "길드",
        "가챠", "소환", "강화", "승급", "각성", "전승",
        "스테이지", "라운드", "레벨", "경험치", "골드", "다이아",
        "인벤토리", "장비", "아티팩트", "룬", "젬", "재료",
        # 상황 설명 표현
        "이상하게", "왜", "어떻게", "뭔가", "갑자기", "계속",
        "자꾸", "반복", "매번", "때문에", "해서", "때문",
        "불가능", "못함", "안생김", "안나옴", "안보임",
        "표시", "나타남", "보여줌", "화면에", "창에",
        # 특수 문자 포함 표현
        "??", "!", "ㅠ", "ㅜ", "ㅡ", "..."
    ]
    
    # 긍정적 키워드 (버그가 아닌 경우)
    positive_keywords = [
        "수정", "패치", "해결", "fix", "fixed", "개선", "업데이트",
        "출시", "릴리즈", "공지", "안내", "이벤트", "혜택",
        "감사", "고마워", "좋아", "훌륭", "최고", "완벽"
    ]
    
    # 질문/문의 키워드 (버그가 아닌 경우)
    question_keywords = [
        "질문", "문의", "어떻게", "방법", "추천", "의견",
        "생각", "어떤", "어디서", "언제", "누구", "뭐가",
        "팁", "공략", "가이드", "도움", "조언", "정보"
    ]
    
    # 버그 키워드 체크
    has_bug_keyword = any(keyword in title_lower for keyword in bug_keywords)
    
    # 긍정적 키워드가 있으면 버그가 아님
    has_positive_keyword = any(keyword in title_lower for keyword in positive_keywords)
    
    # 질문/문의 키워드가 있으면 버그가 아님
    has_question_keyword = any(keyword in title_lower for keyword in question_keywords)
    
    return has_bug_keyword and not has_positive_keyword and not has_question_keyword

def is_positive_post(title):
    """긍정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 긍정적 감정 키워드 (확장)
    positive_keywords = [
        # 직접적인 긍정 표현
        "좋아요", "좋아", "좋다", "감사", "고마워", "고맙",
        "굿", "좋은", "훌륭", "멋져", "멋있", "대박", "짱",
        "최고", "완벽", "우수", "뛰어난", "탁월", "놀라운",
        "사랑", "좋아해", "마음에", "든다", "맘에", "들어",
        # 영어 긍정 표현
        "good", "great", "awesome", "amazing", "perfect", 
        "excellent", "wonderful", "fantastic", "love", "like",
        "thanks", "thank", "nice", "cool", "super", "best",
        # 감탄사 및 긍정적 반응
        "와", "오", "헉", "대단", "신기", "재미있", "재밌",
        "즐거", "행복", "기쁘", "만족", "성공", "승리",
        "잘했", "잘한", "성취", "달성", "해냈", "클리어",
        # 추천 및 공유 의도
        "추천", "공유", "소개", "보여주", "자랑", "소문",
        "인정", "칭찬", "박수", "응원", "지지", "동의",
        # 게임 특화 긍정 표현
        "얻었", "뽑았", "성공", "클리어", "깼다", "이겼",
        "달성", "완료", "해냈", "성취", "돌파", "통과",
        "레전드", "에픽", "최강", "강함", "쎄다", "op",
        # 만족도 표현
        "만족", "흡족", "괜찮", "나쁘지", "할만", "쓸만",
        "이정도", "충분", "나름", "적당", "양호", "무난"
    ]
    
    # 부정적 키워드와 함께 사용되면 긍정이 아님
    negative_context = [
        "안", "못", "없", "아니", "싫", "별로", "그냥",
        "not", "no", "dont", "can't", "won't", "bad"
    ]
    
    has_positive = any(keyword in title_lower for keyword in positive_keywords)
    has_negative_context = any(keyword in title_lower for keyword in negative_context)
    
    # 긍정 키워드가 있고 부정적 맥락이 없어야 함
    return has_positive and not has_negative_context

def is_negative_post(title):
    """부정적 게시글 판별"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 부정적 감정 키워드 (확장)
    negative_keywords = [
        # 직접적인 부정 표현
        "화남", "화나", "짜증", "빡침", "열받", "속상",
        "실망", "실망스", "별로", "최악", "싫어", "싫다",
        "하지마", "하지말", "그만", "안해", "못해",
        # 영어 부정 표현
        "angry", "mad", "upset", "disappointed", "hate",
        "dislike", "worst", "bad", "terrible", "awful",
        "horrible", "suck", "sucks", "damn", "shit",
        # 감정적 반응
        "어이없", "황당", "멘붕", "빡쳐", "뻘쭘", "당황",
        "스트레스", "우울", "답답", "갑갑", "막막", "막히",
        "포기", "그만둠", "그만두", "접음", "접는", "끝",
        # 불만 표현
        "불만", "컴플레인", "항의", "따지", "따져", "욕",
        "욕먹", "욕나", "욕할", "비판", "비난", "질타",
        "성토", "원망", "후회", "반성", "자책", "탓",
        # 상황 부정 표현
        "망함", "망한", "망했", "죽었", "죽는", "끝났",
        "파산", "쓰레기", "폐기", "버림", "버려", "포기",
        "실패", "낙제", "탈락", "미달", "부족", "부실",
        # 게임 특화 부정 표현
        "너프", "하향", "약화", "뺏기", "빼앗", "손해",
        "손실", "잃었", "잃어", "날렸", "날려", "망쳤",
        "개악", "개판", "개똥", "개쓰레기", "개노답",
        "똥겜", "망겜", "접겜", "과금", "현질", "사기",
        # 강도 표현
        "극혐", "극악", "극한", "한계", "끝", "막장",
        "지옥", "헬", "hell", "미친", "crazy", "insane"
    ]
    
    # 긍정적 맥락과 함께 사용되면 부정이 아님
    positive_context = [
        "좋", "괜찮", "만족", "나름", "그래도", "하지만",
        "그런데", "다행", "relief", "glad", "happy"
    ]
    
    has_negative = any(keyword in title_lower for keyword in negative_keywords)
    has_positive_context = any(keyword in title_lower for keyword in positive_context)
    
    # 부정 키워드가 있고 긍정적 맥락이 없어야 함
    return has_negative and not has_positive_context

def is_neutral_post(title):
    """중립적 게시글 판별 (질문, 정보, 일반적인 내용)"""
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 중립적 키워드 (질문, 정보, 일반)
    neutral_keywords = [
        # 질문 표현
        "질문", "문의", "궁금", "어떻게", "어떤", "어디서",
        "언제", "누구", "뭐가", "왜", "어째서", "방법",
        "how", "what", "where", "when", "who", "why",
        "which", "can", "could", "should", "would",
        # 정보 공유
        "정보", "소식", "뉴스", "공지", "안내", "알려드",
        "알림", "공유", "나누", "전달", "보고", "소개",
        "info", "news", "update", "notice", "guide",
        # 일반적인 표현
        "생각", "의견", "견해", "관점", "판단", "평가",
        "분석", "검토", "연구", "조사", "살펴", "확인",
        "think", "opinion", "view", "analysis", "review",
        # 중립적 상황 설명
        "상황", "현재", "지금", "요즘", "최근", "오늘",
        "어제", "내일", "이번", "다음", "status", "current",
        # 일반적인 게임 용어
        "캐릭터", "아이템", "스킬", "스테이지", "레벨",
        "퀘스트", "미션", "던전", "길드", "아레나",
        "character", "item", "skill", "stage", "level",
        # 중립적 행동 표현
        "해봤", "해보", "시도", "테스트", "확인", "체크",
        "try", "test", "check", "attempt", "experiment",
        # 비교 및 선택
        "비교", "선택", "고르", "추천", "조언", "팁",
        "compare", "choose", "select", "recommend", "tip"
    ]
    
    return any(keyword in title_lower for keyword in neutral_keywords)

def classify_post(title):
    """게시글 종합 분류 (우선순위: 버그 > 긍정 > 부정 > 중립)"""
    if not title:
        return "중립"
    
    # 1순위: 버그 관련 게시글
    if is_bug_post(title):
        return "버그"
    
    # 2순위: 긍정적 게시글
    elif is_positive_post(title):
        return "긍정"
    
    # 3순위: 부정적 게시글
    elif is_negative_post(title):
        return "부정"
    
    # 4순위: 중립적 게시글 (질문, 정보 등)
    elif is_neutral_post(title):
        return "중립"
    
    # 기본값: 중립 (분류되지 않은 경우)
    else:
        return "중립"

def get_classification_stats(titles):
    """분류 통계 정보 반환"""
    if not titles:
        return {}
    
    stats = {"긍정": 0, "중립": 0, "부정": 0, "버그": 0}
    
    for title in titles:
        category = classify_post(title)
        stats[category] += 1
    
    total = len(titles)
    percentages = {k: round((v / total) * 100, 1) for k, v in stats.items()}
    
    return {
        "counts": stats,
        "percentages": percentages,
        "total": total
    }

# 테스트용 함수
def test_classifier():
    """분류기 테스트"""
    test_titles = [
        "버그인가요? 게임이 튕겨요",
        "정말 좋은 게임입니다! 추천해요",
        "이 게임 최악이에요 별로",
        "캐릭터 추천 좀 해주세요",
        "로그인 안되는 문제",
        "감사합니다 덕분에 해결했어요",
        "화나네요 진짜 짜증나",
        "어떤 팀 조합이 좋을까요?"
    ]
    
    print("=== 분류기 테스트 ===")
    for title in test_titles:
        category = classify_post(title)
        print(f"'{title}' → {category}")
    
    # 통계 출력
    stats = get_classification_stats(test_titles)
    print("\n=== 분류 통계 ===")
    for category, count in stats["counts"].items():
        percentage = stats["percentages"][category]
        print(f"{category}: {count}개 ({percentage}%)")

if __name__ == "__main__":
    test_classifier()