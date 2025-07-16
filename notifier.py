import requests
from datetime import datetime, timedelta
import os
import json
import hashlib
from deep_translator import GoogleTranslator
import time
import re

# 번역 캐시 파일
TRANSLATION_CACHE_FILE = "translation_cache.json"

# Epic7 전용 용어 사전
EPIC7_TERMS = {
    # 게임 메커니즘
    "nerf": "너프",
    "buff": "버프", 
    "debuff": "디버프",
    "OP": "사기캐",
    "RNG": "확률",
    "gacha": "뽑기",
    "pity": "천장",
    "meta": "메타",
    
    # 게임 요소
    "artifact": "아티팩트",
    "imprint": "각인",
    "mola": "몰라고라",
    "stigma": "스티그마",
    "hunts": "헌트",
    "raid": "레이드",
    "abyss": "심연",
    "arena": "아레나",
    "guild war": "길드워",
    "world boss": "월드보스",
    
    # 캐릭터 관련
    "ML": "문광",
    "moonlight": "문광",
    "RGB": "일반",
    "5 star": "5성",
    "4 star": "4성",
    "tank": "탱커",
    "DPS": "딜러",
    "healer": "힐러",
    "support": "서포터",
    
    # 장비 관련
    "gear": "장비",
    "equipment": "장비",
    "speed": "속도",
    "crit": "치명타",
    "attack": "공격력",
    "defense": "방어력",
    "health": "체력",
    "effectiveness": "효과적중",
    "effect resistance": "효과저항",
    
    # 감정 표현
    "salty": "짜증나는",
    "tilted": "빡친",
    "mad": "화나는",
    "frustrated": "답답한",
    "disappointed": "실망한",
    "excited": "흥분한",
    "hyped": "기대되는"
}

# 번역 대상 사이트
ENGLISH_SITES = [
    "STOVE Global",
    "Reddit",
    "STOVE Global Bug",
    "STOVE Global General"
]

def load_translation_cache():
    """번역 캐시 로드"""
    if os.path.exists(TRANSLATION_CACHE_FILE):
        try:
            with open(TRANSLATION_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_translation_cache(cache):
    """번역 캐시 저장"""
    try:
        # 캐시 크기 제한 (최대 1000개)
        if len(cache) > 1000:
            sorted_items = sorted(cache.items(), key=lambda x: x[1].get('timestamp', ''), reverse=True)
            cache = dict(sorted_items[:1000])
        
        with open(TRANSLATION_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] 번역 캐시 저장 실패: {e}")

def get_text_hash(text):
    """텍스트 해시 생성"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def apply_epic7_terms(text):
    """Epic7 전용 용어 적용"""
    for eng_term, kor_term in EPIC7_TERMS.items():
        # 단어 경계를 고려한 치환
        pattern = r'\b' + re.escape(eng_term) + r'\b'
        text = re.sub(pattern, kor_term, text, flags=re.IGNORECASE)
    return text

def translate_text(text, target_lang='ko'):
    """텍스트 번역 (캐시 활용)"""
    if not text or not text.strip():
        return text
    
    # 이미 한국어인 경우 번역 스킵
    if any(char >= '\uac00' and char <= '\ud7af' for char in text):
        return text
    
    # 캐시 확인
    cache = load_translation_cache()
    text_hash = get_text_hash(text)
    
    if text_hash in cache:
        cached_item = cache[text_hash]
        # 캐시 만료 시간 확인 (7일)
        try:
            cache_time = datetime.fromisoformat(cached_item.get('timestamp', '2000-01-01'))
            if datetime.now() - cache_time < timedelta(days=7):
                return cached_item.get('translated', text)
        except:
            pass
    
    try:
        translator = Translator()
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated_text = translator.translate(text)
        
        # Epic7 전용 용어 적용
        translated_text = apply_epic7_terms(translated_text)
        
        # 캐시 저장
        cache[text_hash] = {
            'original': text,
            'translated': translated_text,
            'timestamp': datetime.now().isoformat()
        }
        save_translation_cache(cache)
        
        print(f"[TRANSLATE] '{text[:30]}...' → '{translated_text[:30]}...'")
        return translated_text
        
    except Exception as e:
        print(f"[ERROR] 번역 실패: {e}")
        return text

def needs_translation(site):
    """번역이 필요한 사이트인지 확인"""
    return site in ENGLISH_SITES

def send_discord_message(webhook_url, content):
    """Discord 메시지 전송"""
    if not webhook_url:
        print("[WARNING] Discord 웹훅 URL이 설정되지 않음")
        return False
    
    try:
        payload = {"content": content}
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            return True
        else:
            print(f"[ERROR] Discord 메시지 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")
        return False

def send_bug_alert(title, url, site, severity="보통"):
    """버그 알림 전송 (번역 지원)"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_BUG")
    if not webhook_url:
        print("[WARNING] 버그 알림 웹훅이 설정되지 않음")
        return False
    
    severity_emoji = {
        "높음": "🚨",
        "보통": "⚠️", 
        "낮음": "ℹ️"
    }
    emoji = severity_emoji.get(severity, "⚠️")
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 번역 처리
    translated_title = title
    translation_tag = ""
    if needs_translation(site):
        translated_title = translate_text(title)
        translation_tag = "(번역)"
    
    message = f"""
{emoji} **Epic7 버그 발견**

**제목:** {translated_title}{translation_tag}
**사이트:** {site}
**링크:** {url}
**심각도:** {severity}
**발견 시간:** {timestamp}

즉시 확인이 필요합니다.
"""
    
    return send_discord_message(webhook_url, message.strip())

def send_sentiment_alert(posts):
    """감성 알림 전송 (번역 지원)"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_SENTIMENT")
    if not webhook_url:
        print("[WARNING] 감성 동향 웹훅이 설정되지 않음")
        return False
    
    if not posts:
        print("[INFO] 전송할 감성 게시글이 없습니다.")
        return True
    
    for post in posts:
        sentiment = post.get('sentiment', '중립')
        emoji = {
            "긍정": "😊",
            "부정": "😠", 
            "중립": "😐"
        }.get(sentiment, "😐")
        
        site = post.get("site", "알 수 없음")
        site_emoji = {
            "STOVE 자유": "🚉",
            "STOVE 버그": "🐞",
            "루리웹": "🏯",
            "STOVE Global": "🌐",
            "STOVE Global Bug": "🌐",
            "STOVE Global General": "🌐",
            "Reddit": "🔴"
        }.get(site, "🌐")
        
        title = post.get("title", "제목 없음")
        url = post.get("url", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 번역 처리
        translated_title = title
        translation_tag = ""
        if needs_translation(site):
            translated_title = translate_text(title)
            translation_tag = "(번역)"
        
        color = {
            "긍정": 0x2ecc71,
            "부정": 0xe74c3c,
            "중립": 0xf1c40f
        }.get(sentiment, 0x95a5a6)
        
        payload = {
            "embeds": [
                {
                    "title": f"{emoji} Epic7 유저 동향 알림",
                    "description": f"**{translated_title}{translation_tag}** ({site_emoji} {site})\n> 🔗 [게시글 바로가기]({url})",
                    "color": color,
                    "footer": {
                        "text": f"{timestamp} | 감성 분석: {sentiment}"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code != 204:
                print(f"[ERROR] Discord 전송 실패: {response.status_code}")
            else:
                print(f"[SUCCESS] {emoji} {translated_title[:30]}...{translation_tag} 전송 완료")
        except Exception as e:
            print(f"[ERROR] Discord 전송 중 오류: {e}")
        
        # API 호출 제한 방지
        time.sleep(1)
    
    return True

def send_daily_report(report_content):
    """일일 리포트 전송"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_REPORT")
    if not webhook_url:
        print("[WARNING] 일간 리포트 웹훅이 설정되지 않음")
        return False
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"""
📊 **Epic7 일간 동향 리포트**

{report_content}

**생성 시간:** {timestamp}
**데이터 기간:** 전날 24시간 누적
"""
    
    return send_discord_message(webhook_url, message.strip())

def send_monitoring_status(status_message):
    """모니터링 상태 전송"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_SENTIMENT")
    if not webhook_url:
        print("[WARNING] 상태 알림 웹훅이 설정되지 않음")
        return False
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"""
🔧 **Epic7 모니터링 시스템 상태**

{status_message}

**확인 시간:** {timestamp}
"""
    
    return send_discord_message(webhook_url, message.strip())

def send_alert(title, url, site, alert_type="버그"):
    """통합 알림 전송"""
    if alert_type == "버그":
        return send_bug_alert(title, url, site)
    else:
        posts = [{'title': title, 'url': url, 'site': site, 'sentiment': '중립'}]
        return send_sentiment_alert(posts)

# 번역 테스트 함수
def test_translation():
    """번역 기능 테스트"""
    print("=== 번역 기능 테스트 ===")
    
    test_posts = [
        {
            'title': 'This new hero is OP, needs nerf badly',
            'url': 'https://example.com/1',
            'site': 'STOVE Global',
            'sentiment': '부정'
        },
        {
            'title': 'RNG in this game is terrible, so frustrated',
            'url': 'https://example.com/2', 
            'site': 'Reddit',
            'sentiment': '부정'
        },
        {
            'title': 'Finally got ML Ken from moonlight summon!',
            'url': 'https://example.com/3',
            'site': 'STOVE Global',
            'sentiment': '긍정'
        }
    ]
    
    send_sentiment_alert(test_posts)

if __name__ == "__main__":
    print("notifier.py 번역 기능 테스트 실행")
    test_translation()