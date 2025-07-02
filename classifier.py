# classifier.py

BUG_KEYWORDS_KO = ['버그', '오류', '팅김', '튕김', '서버', '연결', '점검']
BUG_KEYWORDS_EN = ['bug', 'glitch', 'crash', 'issue', 'disconnect']

POSITIVE_KEYWORDS_KO = ['좋다', '좋아요', '최고', '덕분에', '잘됨', '갓겜']
POSITIVE_KEYWORDS_EN = ['good', 'great', 'thanks', 'helpful', 'amazing']

NEGATIVE_KEYWORDS_KO = ['망겜', '짜증', '불만', '개선', '운영', '노잼']
NEGATIVE_KEYWORDS_EN = ['hate', 'broken', 'problem', 'stupid', 'bad']

def is_bug_post(title):
    title_lower = title.lower()
    return any(kw in title_lower for kw in BUG_KEYWORDS_KO + BUG_KEYWORDS_EN)

def classify_post(title):
    title_lower = title.lower()
    if any(kw in title_lower for kw in BUG_KEYWORDS_KO + BUG_KEYWORDS_EN):
        return "bugs"
    elif any(kw in title_lower for kw in POSITIVE_KEYWORDS_KO + POSITIVE_KEYWORDS_EN):
        return "positive"
    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS_KO + NEGATIVE_KEYWORDS_EN):
        return "negative"
    return None
