def is_bug_post(title):
    keywords = ["버그", "오류", "에러", "error", "bug"]
    return any(keyword in title.lower() for keyword in keywords)

def is_positive_post(title):
    keywords = ["좋아요", "감사", "굿", "추천"]
    return any(keyword in title.lower() for keyword in keywords)

def is_negative_post(title):
    keywords = ["화남", "짜증", "실망", "별로"]
    return any(keyword in title.lower() for keyword in keywords)
