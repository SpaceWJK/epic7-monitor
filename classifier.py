# classifier.py
POSITIVE_KEYWORDS = ['감사', '좋다', '최고', '좋아요', '재밌다', '혜자', 'great', 'thanks', 'hope', 'helpful']
NEGATIVE_KEYWORDS = ['짜증', '불만', '망겜', 'broken', 'stupid', 'hate', 'problem']
BUG_KEYWORDS = ['버그', '오류', '팅김', '튕김', 'crash', 'bug', 'issue']

def is_positive_post(title):
    return any(keyword.lower() in title.lower() for keyword in POSITIVE_KEYWORDS)

def is_negative_post(title):
    return any(keyword.lower() in title.lower() for keyword in NEGATIVE_KEYWORDS)

def is_bug_post(title):
    return any(keyword.lower() in title.lower() for keyword in BUG_KEYWORDS)
