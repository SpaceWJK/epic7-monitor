BUG_KEYWORDS = ["에러", "버그", "오류", "튕김", "죽음", "깨짐", "멈춤", "먹통"]
POS_KEYWORDS = ["좋다", "만족", "추천"]
NEG_KEYWORDS = ["별로", "실망", "불만"]

def classify_post(post):
    title = post.get("title", "").lower()
    if post.get("force_bug"):
        return "bug"
    if any(k in title for k in BUG_KEYWORDS):
        return "bug"
    elif any(k in title for k in POS_KEYWORDS):
        return "positive"
    elif any(k in title for k in NEG_KEYWORDS):
        return "negative"
    return "neutral"
