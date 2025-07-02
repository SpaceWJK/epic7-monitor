from typing import Dict

KEYWORDS: Dict[str, Dict[str, list]] = {
    'bug': {
        'ko': ['오류', '버그', '팅김', '재접', '적용 안됨', '튕김', '렉', '검은화면', '먹통', '글리치'],
        'en': ['bug', 'glitch', 'crash', 'reconnect', 'issue', 'login crash', 'not loading', 'freeze', 'stuck', 'exploit'],
        'jp': ['バグ', '不具合', 'エラー', '落ちる', '固まる'],
    },
    'negative': {
        'ko': ['짜증', '불만', '개선', '운영', '똥겜', '노잼', '망겜', '접는다', '환불', '하향', '너프'],
        'en': ['hate', 'screw you', 'stupid', 'broken', 'server problem', 'disappointed', 'bad', 'nerf', 'rant'],
        'jp': ['不満', '下方修正', 'ナーフ', '改悪', '炎上', 'クソゲー', 'オワコン'],
    },
    'positive': {
        'ko': ['감사', '해결', '좋아요', '덕분에', '최고', '좋다', '잘됨', '갓겜', '혜자', '추천', '만족', '상향'],
        'en': ['helpful', 'thanks', 'managed', 'great', 'figured out', 'good', 'love', 'amazing', 'awesome', 'buff'],
        'jp': ['神ゲー', '面白い', 'おすすめ', '満足', '上方修正', '神引き'],
    }
}

def classify_post(title: str) -> str:
    """게시글 제목을 분석하여 미리 정의된 카테고리로 분류합니다."""
    lower_title = title.lower()
    for category, languages in KEYWORDS.items():
        for lang_keywords in languages.values():
            for keyword in lang_keywords:
                if keyword in lower_title:
                    return category
    return 'neutral'