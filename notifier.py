import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import time
import re
import random

def send_bug_alert(webhook_url, bugs):
    """개선된 버그 알림 전송 (내용 추출 개선)"""
    if not webhook_url or not bugs:
        return
    
    try:
        # Discord 메시지 길이 제한 (2000자)
        MAX_MESSAGE_LENGTH = 1900  # 여유분 고려
        
        # 여러 메시지로 나누어 전송
        current_message = "🚨 **에픽세븐 버그 탐지 알림** 🚨\n\n"
        message_count = 1
        
        for bug in bugs:
            try:
                # 분류 타입 결정
                source_type = get_source_type_korean(bug.get('source', 'unknown'))
                
                # 시간 포맷 변경 (yyyy-mm-dd hh:mm)
                formatted_time = format_timestamp(bug.get('timestamp', ''))
                
                # 실제 게시글 내용 크롤링 및 요약 (개선)
                content_summary = get_post_content_summary(bug.get('url', ''), bug.get('source', ''))
                
                # 새로운 메시지 형태 구성
                bug_info = f"""**분류**: {source_type}
**제목**: {bug['title'][:80]}{'...' if len(bug['title']) > 80 else ''}
**시간**: {formatted_time}
**내용**: {content_summary}
**URL**: {bug['url']}

"""
                
                # 메시지 길이 체크
                if len(current_message + bug_info) > MAX_MESSAGE_LENGTH:
                    # 현재 메시지 전송
                    send_discord_message(webhook_url, current_message, message_count)
                    
                    # 새 메시지 시작
                    message_count += 1
                    current_message = f"🚨 **버그 알림 계속 ({message_count})** 🚨\n\n" + bug_info
                else:
                    current_message += bug_info
                    
            except Exception as e:
                print(f"[ERROR] 개별 버그 메시지 처리 중 오류: {e}")
                continue
        
        # 마지막 메시지 전송
        if current_message.strip():
            send_discord_message(webhook_url, current_message, message_count)
                
    except Exception as e:
        print(f"[ERROR] Discord 버그 알림 전송 중 오류: {e}")

def get_post_content_summary(post_url, source):
    """게시글 URL에서 실제 내용을 크롤링하여 요약 생성 (개선)"""
    try:
        print(f"[DEBUG] 게시글 내용 크롤링 시작: {post_url}")
        
        # 소스별 요청 헤더 최적화
        headers = get_headers_by_source(source)
        
        # 게시글 내용 크롤링 (타임아웃 조정)
        response = requests.get(post_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 소스별 게시글 내용 추출 로직 (개선)
        content_text = extract_content_by_source(soup, source)
        
        if content_text:
            # 내용 정제 및 요약
            summary = create_intelligent_summary(content_text)
            print(f"[DEBUG] 내용 요약 완료: {summary}")
            return summary
        else:
            print(f"[WARN] 게시글 내용 추출 실패")
            return get_default_summary_by_source(source)
            
    except requests.exceptions.Timeout:
        print(f"[WARN] 게시글 크롤링 타임아웃: {post_url}")
        return "게시글 로딩 시간이 초과되었습니다"
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 게시글 크롤링 실패: {e}")
        return "게시글에 접근할 수 없습니다"
    except Exception as e:
        print(f"[ERROR] 게시글 내용 요약 중 오류: {e}")
        return "내용 분석 중 오류가 발생했습니다"

def get_headers_by_source(source):
    """소스별 최적화된 요청 헤더"""
    base_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    if source in ['ruliweb_epic7', 'ruliweb']:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        base_headers['Referer'] = 'https://bbs.ruliweb.com/'
    elif source in ['stove_bug', 'stove_general']:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        base_headers['Referer'] = 'https://page.onstove.com/'
        # 스토브 전용 헤더 추가
        base_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
        base_headers['Sec-Fetch-Dest'] = 'document'
        base_headers['Sec-Fetch-Mode'] = 'navigate'
        base_headers['Sec-Fetch-Site'] = 'same-origin'
    else:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    
    return base_headers

def extract_content_by_source(soup, source):
    """소스별 게시글 내용 추출 (확장된 선택자)"""
    try:
        content_text = ""
        
        if source in ['stove_bug', 'stove_general']:
            # 스토브 게시글 내용 추출 (선택자 대폭 확장)
            content_selectors = [
                # 메인 컨텐츠 선택자
                '.s-article-content',
                '.s-board-content-text',
                '.s-article-body',
                '.s-board-view-content',
                '.s-content-text',
                '.s-view-content',
                
                # 일반적인 컨텐츠 선택자
                '.article-content',
                '.post-content',
                '.content-area',
                '.view-content',
                '.board-content',
                '.user-content',
                '.main-content',
                
                # 텍스트 컨테이너 선택자
                '.text-content',
                '.content-text',
                '.article-text',
                '.post-text',
                '.view-text',
                '.board-text',
                
                # 포괄적 선택자
                '[class*="content"]',
                '[class*="article"]',
                '[class*="post"]',
                '[class*="text"]',
                '[class*="view"]',
                
                # 최후의 수단 - 메인 컨테이너
                'main',
                '.main',
                '#main',
                '.container',
                '.wrapper'
            ]
            
        elif source in ['ruliweb_epic7', 'ruliweb']:
            # 루리웹 게시글 내용 추출 (선택자 확장)
            content_selectors = [
                '.article_container',
                '.article-content',
                '.post_content',
                '.view_content',
                '.board_main_view',
                '.content_text',
                '.article_text',
                '.user_content',
                '[class*="content"]',
                '[class*="article"]',
                'main',
                '.main'
            ]
            
        else:
            # 기타 사이트 - 일반적인 선택자
            content_selectors = [
                '.content',
                '.post-content',
                '.article-content',
                '.entry-content',
                '.main-content',
                '.text-content',
                'main',
                '[class*="content"]',
                '[class*="article"]',
                '[class*="post"]'
            ]
        
        # 선택자별 시도
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content_text = content_elem.get_text(strip=True)
                    if len(content_text) > 30:  # 최소 길이 조건
                        print(f"[DEBUG] 내용 추출 성공: {selector} ({len(content_text)}자)")
                        break
            except Exception as e:
                continue
        
        # 텍스트 길이 체크
        if content_text and len(content_text) > 20:
            return content_text
        else:
            # 대안: 모든 텍스트 노드 수집
            print("[DEBUG] 대안 방법으로 텍스트 수집 시도")
            all_text = soup.get_text(strip=True)
            if len(all_text) > 50:
                return all_text[:500]  # 최대 500자
        
        return ""
        
    except Exception as e:
        print(f"[ERROR] 게시글 내용 추출 중 오류: {e}")
        return ""

def get_default_summary_by_source(source):
    """소스별 기본 요약 메시지"""
    if source in ['stove_bug', 'stove_general']:
        return "스토브 게시글 내용을 확인해주세요"
    elif source in ['ruliweb_epic7', 'ruliweb']:
        return "루리웹 게시글 내용을 확인해주세요"
    else:
        return "게시글 내용을 직접 확인해주세요"

def create_intelligent_summary(content_text):
    """지능형 게시글 내용 요약 (개선)"""
    try:
        if not content_text:
            return "내용이 없습니다"
        
        # 내용 정제 (개선)
        cleaned_content = clean_content_text(content_text)
        
        if len(cleaned_content) <= 80:
            return cleaned_content
        
        # 버그 관련 키워드 우선 추출
        bug_summary = extract_bug_keywords(cleaned_content)
        if bug_summary:
            return bug_summary
        
        # 문장 단위로 분리 (개선)
        sentences = split_into_sentences(cleaned_content)
        
        if not sentences:
            return cleaned_content[:80] + "..."
        
        # 가장 중요한 문장 찾기 (개선)
        main_sentence = find_most_important_sentence(sentences)
        
        if main_sentence:
            # 요약 길이 조정
            if len(main_sentence) > 100:
                return main_sentence[:97] + "..."
            return main_sentence
        else:
            return cleaned_content[:80] + "..."
            
    except Exception as e:
        print(f"[ERROR] 지능형 요약 생성 중 오류: {e}")
        return "요약 생성 중 오류가 발생했습니다"

def extract_bug_keywords(content):
    """버그 관련 키워드 우선 추출"""
    try:
        # 버그 관련 패턴 매칭
        bug_patterns = [
            r'(.{0,40})(버그|오류|에러|문제|안(?:돼|되)(?:요|며|는|고))(.{0,40})',
            r'(.{0,40})(작동(?:안|하지)(?:해|함|요|며))(.{0,40})',
            r'(.{0,40})(튕(?:김|겨)(?:요|며|서))(.{0,40})',
            r'(.{0,40})(먹(?:통|먹)(?:이|해|요))(.{0,40})',
            r'(.{0,40})(로딩|연결|접속)(.{0,10})(안|못|불가)(.{0,30})',
            r'(.{0,40})(게임|앱)(.{0,10})(종료|다운|멈춤)(.{0,30})'
        ]
        
        for pattern in bug_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                bug_context = ''.join(match.groups()).strip()
                if len(bug_context) > 15:
                    return clean_bug_context(bug_context)
        
        return None
        
    except Exception as e:
        print(f"[ERROR] 버그 키워드 추출 중 오류: {e}")
        return None

def clean_bug_context(bug_context):
    """버그 컨텍스트 정제"""
    try:
        # 불필요한 문자 제거
        bug_context = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', bug_context)
        bug_context = re.sub(r'\s+', ' ', bug_context).strip()
        
        # 길이 조정
        if len(bug_context) > 90:
            return bug_context[:87] + "..."
        return bug_context
        
    except Exception as e:
        print(f"[ERROR] 버그 컨텍스트 정제 중 오류: {e}")
        return bug_context

def clean_content_text(content):
    """게시글 내용 정제 (개선)"""
    try:
        # 기본 정제
        content = re.sub(r'\s+', ' ', content)  # 연속 공백 제거
        content = re.sub(r'[\r\n\t]+', ' ', content)  # 개행문자 제거
        
        # 불필요한 텍스트 제거 (확장)
        unnecessary_phrases = [
            '로그인', '회원가입', '댓글', '추천', '비추천', '신고', '목록',
            '이전', '다음', '페이지', '공지사항', '이벤트', '운영정책',
            '이용약관', '개인정보', '쿠키', 'Cookie', '광고', '배너',
            '팝업', '알림', '설정', 'JavaScript', '더보기', '접기',
            '펼치기', '클릭', '터치', '스크롤', '복사', '공유', '북마크',
            '좋아요', '싫어요', '구독', '팔로우', '프로필', '메뉴'
        ]
        
        for phrase in unnecessary_phrases:
            content = content.replace(phrase, '')
        
        # 특수문자 정제 (한글/영문/숫자/기본 문장부호만 유지)
        content = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', content)
        
        # 연속된 같은 문자 제거 (3개 이상)
        content = re.sub(r'(.)\1{2,}', r'\1\1', content)
        
        return content.strip()
        
    except Exception as e:
        print(f"[ERROR] 내용 정제 중 오류: {e}")
        return content

def split_into_sentences(content):
    """내용을 문장 단위로 분리 (개선)"""
    try:
        # 한국어/영어 문장 분리 개선
        sentences = re.split(r'[.!?。！？]\s*', content)
        
        # 의미있는 문장만 필터링
        meaningful_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            # 최소 길이, 한글/영문 포함 조건
            if (len(sentence) >= 10 and 
                sentence and 
                (re.search(r'[가-힣]', sentence) or re.search(r'[a-zA-Z]', sentence))):
                meaningful_sentences.append(sentence)
        
        return meaningful_sentences
        
    except Exception as e:
        print(f"[ERROR] 문장 분리 중 오류: {e}")
        return [content]

def find_most_important_sentence(sentences):
    """가장 중요한 문장 찾기 (개선)"""
    try:
        # 중요도 기반 키워드 (가중치 적용)
        priority_keywords = {
            # 버그 관련 (최고 우선순위)
            '버그': 15, '오류': 15, '에러': 15, '문제': 12, '안됨': 10,
            '안돼': 10, '작동': 10, '튕김': 12, '먹통': 10, '로딩': 8,
            '연결': 8, '접속': 8, '서버': 8, '네트워크': 6, '강제종료': 12,
            
            # 게임 모드 (높은 우선순위)
            '아레나': 8, '길드': 8, '원정': 7, '헌트': 7, '던전': 7,
            '레이드': 7, '어비스': 6, '탑': 6, '미궁': 6, '월드': 5,
            
            # 게임 요소 (중간 우선순위)
            '영웅': 6, '스킬': 6, '아티팩트': 5, '장비': 5, '강화': 5,
            '소환': 5, '가챠': 4, '각성': 4, '전승': 4, '특성': 4,
            
            # 시스템 관련 (중간 우선순위)
            '업데이트': 6, '패치': 6, '점검': 5, '유지보수': 5,
            '클라이언트': 4, '앱': 4, '게임': 3
        }
        
        best_sentence = ""
        max_score = 0
        
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            # 키워드 가중치 점수 계산
            for keyword, weight in priority_keywords.items():
                if keyword in sentence:
                    score += weight
            
            # 문장 길이 보너스 (적절한 길이 선호)
            if 15 <= len(sentence) <= 120:
                score += 3
            elif 10 <= len(sentence) <= 200:
                score += 2
            elif len(sentence) <= 300:
                score += 1
            
            # 첫 번째 문장 보너스
            if sentence == sentences[0]:
                score += 2
            
            # 문장 완성도 보너스
            if sentence.endswith(('.', '!', '?', '다', '요', '네', '음')):
                score += 1
            
            if score > max_score:
                max_score = score
                best_sentence = sentence
        
        return best_sentence if max_score > 0 else (sentences[0] if sentences else "")
        
    except Exception as e:
        print(f"[ERROR] 중요 문장 찾기 중 오류: {e}")
        return sentences[0] if sentences else ""

def send_discord_message(webhook_url, message, count):
    """Discord 메시지 전송 (개선)"""
    try:
        data = {
            "content": message,
            "username": "Epic7 Bug Monitor",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=20)
        if response.status_code == 204:
            print(f"[SUCCESS] Discord 알림 {count} 전송 성공")
        else:
            print(f"[WARN] Discord 알림 {count} 전송 실패: {response.status_code}")
            
        # Discord Rate Limit 방지를 위한 딜레이
        time.sleep(2)
        
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")

def get_source_type_korean(source):
    """소스 타입을 한국어로 변환 (확장)"""
    source_map = {
        "stove_bug": "🏪 스토브 버그 게시판",
        "stove_general": "🏪 스토브 자유게시판",
        "ruliweb_epic7": "🎮 루리웹 에픽세븐",
        "ruliweb": "🎮 루리웹 에픽세븐",
        "reddit_epic7": "🌐 Reddit r/EpicSeven",
        "reddit": "🌐 Reddit r/EpicSeven",
        "forum": "🌍 에픽세븐 글로벌 포럼",
        "unknown": "❓ 알 수 없는 출처"
    }
    return source_map.get(source, f"🔸 기타 ({source})")

def format_timestamp(timestamp_str):
    """타임스탬프를 yyyy-mm-dd hh:mm 형태로 포맷"""
    try:
        if timestamp_str:
            # ISO 형태의 타임스탬프를 파싱
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        else:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"[WARN] 시간 포맷 변환 실패: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M')

def send_daily_report(webhook_url, report):
    """일일 리포트 전송 (버그 제외)"""
    if not webhook_url:
        return
        
    try:
        # 리포트 내용 생성 (버그 제외)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        
        # 버그 카테고리 제외하고 계산
        total_posts = 0
        for category, posts in report.items():
            if category != "버그":  # 버그 제외
                total_posts += len(posts)
        
        # Embed 형태로 전송
        embed = {
            "title": "📊 에픽세븐 일일 유저 동향 리포트",
            "description": f"📅 {current_time}\n📈 **분석 게시글 수: {total_posts}개**\n\n*버그 동향은 실시간 알림으로 별도 전송됩니다*",
            "color": 0x00ff00 if total_posts > 0 else 0x808080,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 모니터링 시스템 v2.1",
                "icon_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
            }
        }
        
        # 카테고리별 필드 추가 (버그 제외)
        for category, posts in report.items():
            if category == "버그":  # 버그 카테고리 제외
                continue
                
            if not posts:
                embed["fields"].append({
                    "name": f"{get_category_emoji(category)} {category}",
                    "value": "0개",
                    "inline": True
                })
                continue
            
            # 상위 3개 게시글 목록
            top_posts = []
            for i, post in enumerate(posts[:3], 1):
                title = post['title'][:35] + "..." if len(post['title']) > 35 else post['title']
                top_posts.append(f"{i}. {title}")
            
            if len(posts) > 3:
                top_posts.append(f"... 외 {len(posts) - 3}개")
            
            embed["fields"].append({
                "name": f"{get_category_emoji(category)} {category}",
                "value": f"**{len(posts)}개**\n" + "\n".join(top_posts),
                "inline": True
            })
        
        # Discord 전송
        data = {
            "embeds": [embed],
            "username": "Epic7 Daily Reporter",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=20)
        if response.status_code == 204:
            print("[SUCCESS] 일일 리포트 Discord 전송 성공")
        else:
            print(f"[WARN] 일일 리포트 Discord 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 전송 중 오류: {e}")

def get_category_emoji(category):
    """카테고리별 이모지 반환"""
    emoji_map = {
        "긍정": "😊",
        "부정": "😞", 
        "중립": "📝",
        "버그": "🐛",
        "질문": "❓",
        "정보": "ℹ️",
        "공략": "📋",
        "창작": "🎨",
        "이벤트": "🎉"
    }
    return emoji_map.get(category, "📌")

# 테스트 함수
def test_content_extraction():
    """내용 추출 테스트"""
    test_urls = [
        "https://page.onstove.com/epicseven/kr/view/10867127",
        "https://bbs.ruliweb.com/game/84834/read/30000"
    ]
    
    print("=== 내용 추출 테스트 ===")
    for url in test_urls:
        if "onstove" in url:
            source = "stove_bug"
        elif "ruliweb" in url:
            source = "ruliweb_epic7"
        else:
            source = "unknown"
        
        summary = get_post_content_summary(url, source)
        print(f"URL: {url}")
        print(f"요약: {summary}")
        print("-" * 50)

if __name__ == "__main__":
    test_content_extraction()