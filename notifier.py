import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import time
import re
import random

def get_stove_post_content(post_url):
    """스토브 게시글 내용 추출 개선"""
    try:
        print(f"[DEBUG] 스토브 게시글 내용 크롤링 시작: {post_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://page.onstove.com/'
        }
        
        response = requests.get(post_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 스토브 게시글 내용 선택자 (확장)
        content_selectors = [
            '.s-article-content',           # 기본 선택자
            '.s-board-content-text',        # 대체 선택자 1
            '.article-content',             # 대체 선택자 2
            '.post-content',                # 대체 선택자 3
            '.content-area',                # 대체 선택자 4
            '.view-content',                # 대체 선택자 5
            '.board-content',               # 대체 선택자 6
            '[class*="content"]',           # 패턴 매칭
            '.s-board-view-content',        # 대체 선택자 7
            '.s-article-body',              # 대체 선택자 8
            'div[class*="article"]',        # div 패턴
            'div[class*="board"]',          # div 패턴 2
            '.usertext-body'                # 대체 선택자 9
        ]
        
        content_text = ""
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content_text = content_elem.get_text(strip=True)
                    if len(content_text) > 20:  # 최소 길이 조건
                        print(f"[DEBUG] 스토브 내용 추출 성공: {selector}")
                        break
            except Exception as e:
                continue
        
        if not content_text:
            # 전체 텍스트에서 추출 시도
            body_text = soup.get_text()
            if len(body_text) > 100:
                # 본문으로 추정되는 부분 추출
                lines = body_text.split('\n')
                content_lines = []
                for line in lines:
                    line = line.strip()
                    if len(line) > 10 and len(line) < 200:
                        content_lines.append(line)
                        if len(content_lines) >= 3:
                            break
                content_text = ' '.join(content_lines)
        
        if content_text:
            # 내용 정제
            content_text = clean_stove_content(content_text)
            summary = create_stove_summary(content_text)
            print(f"[DEBUG] 스토브 내용 요약 완료: {summary[:50]}...")
            return summary
        else:
            print(f"[WARN] 스토브 게시글 내용 추출 실패")
            return "게시글 내용을 확인할 수 없습니다."
            
    except requests.exceptions.Timeout:
        print(f"[WARN] 스토브 게시글 크롤링 타임아웃: {post_url}")
        return "게시글 로딩 시간 초과"
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 스토브 게시글 크롤링 실패: {e}")
        return "게시글 접근 불가"
    except Exception as e:
        print(f"[ERROR] 스토브 게시글 내용 요약 중 오류: {e}")
        return "내용 요약 중 오류 발생"

def clean_stove_content(content):
    """스토브 게시글 내용 정제"""
    try:
        # 기본 정제
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[\r\n\t]+', ' ', content)
        
        # 스토브 특화 불필요한 텍스트 제거
        stove_unnecessary = [
            '로그인', '회원가입', '댓글', '추천', '비추천', '신고',
            '목록', '이전', '다음', '페이지', '공지사항', '이벤트',
            'STOVE', 'onstove', 'epic7', 'epicseven',
            '스토브', '에픽세븐', '게시판', '커뮤니티'
        ]
        
        for phrase in stove_unnecessary:
            content = content.replace(phrase, '')
        
        # 특수문자 정제
        content = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', content)
        
        return content.strip()
        
    except Exception as e:
        print(f"[ERROR] 스토브 내용 정제 중 오류: {e}")
        return content

def create_stove_summary(content_text):
    """스토브 게시글 내용 요약 생성"""
    try:
        if not content_text:
            return "내용이 없습니다."
        
        if len(content_text) <= 60:
            return content_text
        
        # 버그 관련 키워드 우선 추출
        bug_patterns = [
            r'(.{0,30})(버그|오류|에러|문제|안(?:돼|되)(?:요|며|는|고))(.{0,30})',
            r'(.{0,30})(작동(?:안|하지)(?:해|함|요|며))(.{0,30})',
            r'(.{0,30})(튕(?:김|겨)(?:요|며|서))(.{0,30})',
            r'(.{0,30})(먹(?:통|먹)(?:이|해|요))(.{0,30})',
        ]
        
        for pattern in bug_patterns:
            matches = re.finditer(pattern, content_text, re.IGNORECASE)
            for match in matches:
                bug_context = ''.join(match.groups()).strip()
                if len(bug_context) > 10:
                    return clean_bug_context(bug_context)
        
        # 문장 단위로 분리
        sentences = re.split(r'[.!?。！？]\s*', content_text)
        meaningful_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if (len(sentence) >= 15 and 
                sentence and 
                (re.search(r'[가-힣]', sentence) or re.search(r'[a-zA-Z]', sentence))):
                meaningful_sentences.append(sentence)
        
        if not meaningful_sentences:
            return content_text[:60] + "..."
        
        # 가장 중요한 문장 찾기
        priority_keywords = {
            '버그': 10, '오류': 10, '에러': 10, '문제': 9, '안됨': 8,
            '아레나': 7, '길드': 7, '원정': 6, '헌트': 6,
            '영웅': 5, '스킬': 5, '장비': 4, '강화': 4,
            '업데이트': 5, '패치': 5, '점검': 4
        }
        
        best_sentence = ""
        max_score = 0
        
        for sentence in meaningful_sentences:
            score = 0
            for keyword, weight in priority_keywords.items():
                if keyword in sentence:
                    score += weight
            
            if 20 <= len(sentence) <= 100:
                score += 2
            
            if sentence == meaningful_sentences[0]:
                score += 1
            
            if score > max_score:
                max_score = score
                best_sentence = sentence
        
        result = best_sentence if max_score > 0 else (meaningful_sentences[0] if meaningful_sentences else content_text[:60])
        
        if len(result) > 80:
            return result[:77] + "..."
        return result
        
    except Exception as e:
        print(f"[ERROR] 스토브 요약 생성 중 오류: {e}")
        return content_text[:60] + "..." if content_text else "요약 생성 실패"

def clean_bug_context(bug_context):
    """버그 컨텍스트 정제"""
    try:
        bug_context = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', bug_context)
        bug_context = re.sub(r'\s+', ' ', bug_context).strip()
        
        if len(bug_context) > 70:
            return bug_context[:67] + "..."
        return bug_context
        
    except Exception as e:
        print(f"[ERROR] 버그 컨텍스트 정제 중 오류: {e}")
        return bug_context

def get_post_content_summary(post_url, source):
    """게시글 URL에서 실제 내용을 크롤링하여 요약 생성"""
    try:
        print(f"[DEBUG] 게시글 내용 크롤링 시작: {post_url}")
        
        # 소스별 전용 함수 사용
        if source in ['stove_bug', 'stove_general']:
            return get_stove_post_content(post_url)
        
        # 기타 사이트 (기존 로직)
        headers = get_headers_by_source(source)
        response = requests.get(post_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_text = extract_content_by_source(soup, source)
        
        if content_text:
            summary = create_intelligent_summary(content_text)
            print(f"[DEBUG] 내용 요약 완료: {summary}")
            return summary
        else:
            print(f"[WARN] 게시글 내용 추출 실패")
            return "게시글 내용을 확인할 수 없습니다."
            
    except requests.exceptions.Timeout:
        print(f"[WARN] 게시글 크롤링 타임아웃: {post_url}")
        return "게시글 로딩 시간 초과"
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 게시글 크롤링 실패: {e}")
        return "게시글 접근 불가"
    except Exception as e:
        print(f"[ERROR] 게시글 내용 요약 중 오류: {e}")
        return "내용 요약 중 오류 발생"

def get_headers_by_source(source):
    """소스별 최적화된 요청 헤더"""
    base_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    if source in ['ruliweb_epic7', 'ruliweb']:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        base_headers['Referer'] = 'https://bbs.ruliweb.com/'
    elif source in ['stove_bug', 'stove_general']:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        base_headers['Referer'] = 'https://page.onstove.com/'
    else:
        base_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    
    return base_headers

def extract_content_by_source(soup, source):
    """소스별 게시글 내용 추출"""
    try:
        content_text = ""
        
        if source in ['ruliweb_epic7', 'ruliweb']:
            content_selectors = [
                '.article_container',
                '.article-content',
                '.post_content',
                '.view_content',
                '.board_main_view',
                '[class*="content"]',
                '.article_text'
            ]
        else:
            content_selectors = [
                '.content',
                '.post-content',
                '.article-content',
                '.entry-content',
                '.main-content',
                'main',
                '[class*="content"]'
            ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content_text = content_elem.get_text(strip=True)
                if len(content_text) > 20:
                    break
        
        return content_text
        
    except Exception as e:
        print(f"[ERROR] 게시글 내용 추출 중 오류: {e}")
        return ""

def create_intelligent_summary(content_text):
    """지능형 게시글 내용 요약"""
    try:
        if not content_text:
            return "내용이 없습니다."
        
        cleaned_content = clean_content_text(content_text)
        
        if len(cleaned_content) <= 60:
            return cleaned_content
        
        bug_summary = extract_bug_keywords(cleaned_content)
        if bug_summary:
            return bug_summary
        
        sentences = split_into_sentences(cleaned_content)
        
        if not sentences:
            return cleaned_content[:60] + "..."
        
        main_sentence = find_most_important_sentence(sentences)
        
        if main_sentence:
            if len(main_sentence) > 80:
                return main_sentence[:77] + "..."
            return main_sentence
        else:
            return cleaned_content[:60] + "..."
            
    except Exception as e:
        print(f"[ERROR] 지능형 요약 생성 중 오류: {e}")
        return "요약 생성 실패"

def extract_bug_keywords(content):
    """버그 관련 키워드 우선 추출"""
    try:
        bug_patterns = [
            r'(.{0,30})(버그|오류|에러|문제|안(?:돼|되)(?:요|며|는|고))(.{0,30})',
            r'(.{0,30})(작동(?:안|하지)(?:해|함|요|며))(.{0,30})',
            r'(.{0,30})(튕(?:김|겨)(?:요|며|서))(.{0,30})',
            r'(.{0,30})(먹(?:통|먹)(?:이|해|요))(.{0,30})',
        ]
        
        for pattern in bug_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                bug_context = ''.join(match.groups()).strip()
                if len(bug_context) > 10:
                    return clean_bug_context(bug_context)
        
        return None
        
    except Exception as e:
        print(f"[ERROR] 버그 키워드 추출 중 오류: {e}")
        return None

def clean_content_text(content):
    """게시글 내용 정제"""
    try:
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[\r\n\t]+', ' ', content)
        
        unnecessary_phrases = [
            '로그인', '회원가입', '댓글', '추천', '비추천', '신고',
            '목록', '이전', '다음', '페이지', '공지사항', '이벤트',
            '운영정책', '이용약관', '개인정보', '쿠키', 'Cookie',
            '광고', '배너', '팝업', '알림', '설정', 'JavaScript',
        ]
        
        for phrase in unnecessary_phrases:
            content = content.replace(phrase, '')
        
        content = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', content)
        
        return content.strip()
        
    except Exception as e:
        print(f"[ERROR] 내용 정제 중 오류: {e}")
        return content

def split_into_sentences(content):
    """내용을 문장 단위로 분리"""
    try:
        sentences = re.split(r'[.!?。！？]\s*', content)
        
        meaningful_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if (len(sentence) >= 15 and 
                sentence and 
                (re.search(r'[가-힣]', sentence) or re.search(r'[a-zA-Z]', sentence))):
                meaningful_sentences.append(sentence)
        
        return meaningful_sentences
        
    except Exception as e:
        print(f"[ERROR] 문장 분리 중 오류: {e}")
        return [content]

def find_most_important_sentence(sentences):
    """가장 중요한 문장 찾기"""
    try:
        priority_keywords = {
            '버그': 10, '오류': 10, '에러': 10, '문제': 9, '안됨': 8, '작동': 8,
            '튕김': 9, '먹통': 8, '로딩': 7, '연결': 6, '접속': 6,
            '아레나': 7, '길드': 7, '원정': 6, '헌트': 6, '던전': 6,
            '영웅': 5, '스킬': 5, '아티팩트': 4, '장비': 4, '강화': 4,
            '업데이트': 5, '패치': 5, '점검': 4, '유지보수': 4,
        }
        
        best_sentence = ""
        max_score = 0
        
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            for keyword, weight in priority_keywords.items():
                if keyword in sentence:
                    score += weight
            
            if 20 <= len(sentence) <= 100:
                score += 2
            elif 15 <= len(sentence) <= 150:
                score += 1
            
            if sentence == sentences[0]:
                score += 1
            
            if score > max_score:
                max_score = score
                best_sentence = sentence
        
        return best_sentence if max_score > 0 else (sentences[0] if sentences else "")
        
    except Exception as e:
        print(f"[ERROR] 중요 문장 찾기 중 오류: {e}")
        return sentences[0] if sentences else ""

def send_bug_alert(webhook_url, bugs):
    """개선된 버그 알림 전송"""
    if not webhook_url or not bugs:
        return
    
    try:
        MAX_MESSAGE_LENGTH = 1900
        current_message = "🚨 **에픽세븐 버그 탐지 알림** 🚨\n\n"
        message_count = 1
        
        for bug in bugs:
            try:
                source_type = get_source_type_korean(bug.get('source', 'unknown'))
                formatted_time = format_timestamp(bug.get('timestamp', ''))
                
                # 개선된 게시글 내용 크롤링
                content_summary = get_post_content_summary(bug.get('url', ''), bug.get('source', ''))
                
                bug_info = f"""**분류**: {source_type}
**제목**: {bug['title'][:80]}{'...' if len(bug['title']) > 80 else ''}
**시간**: {formatted_time}
**내용**: {content_summary}
**URL**: {bug['url']}

"""
                
                if len(current_message + bug_info) > MAX_MESSAGE_LENGTH:
                    send_discord_message(webhook_url, current_message, message_count)
                    message_count += 1
                    current_message = f"🚨 **버그 알림 계속 ({message_count})** 🚨\n\n" + bug_info
                else:
                    current_message += bug_info
                    
            except Exception as e:
                print(f"[ERROR] 개별 버그 메시지 처리 중 오류: {e}")
                continue
        
        if current_message.strip():
            send_discord_message(webhook_url, current_message, message_count)
                
    except Exception as e:
        print(f"[ERROR] Discord 버그 알림 전송 중 오류: {e}")

def send_discord_message(webhook_url, message, count):
    """Discord 메시지 전송"""
    try:
        data = {
            "content": message,
            "username": "Epic7 Bug Monitor",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print(f"[SUCCESS] Discord 알림 {count} 전송 성공")
        else:
            print(f"[WARN] Discord 알림 {count} 전송 실패: {response.status_code}")
            
        time.sleep(1.5)
        
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")

def get_source_type_korean(source):
    """소스 타입을 한국어로 변환"""
    source_map = {
        "stove_bug": "🏪 스토브 버그 게시판",
        "stove_general": "🏪 스토브 자유게시판",
        "ruliweb_epic7": "🎮 루리웹 에픽세븐",
        "ruliweb": "🎮 루리웹 에픽세븐",
        "unknown": "❓ 알 수 없는 출처"
    }
    return source_map.get(source, f"🔸 기타 ({source})")

def format_timestamp(timestamp_str):
    """타임스탬프를 yyyy-mm-dd hh:mm 형태로 포맷"""
    try:
        if timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        else:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"[WARN] 시간 포맷 변환 실패: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M')

def send_daily_report(webhook_url, report):
    """일일 리포트 전송 (개선)"""
    if not webhook_url:
        return
        
    try:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        total_posts = sum(len(posts) for posts in report.values())
        
        embed = {
            "title": "📊 에픽세븐 일일 감성 동향 리포트",
            "description": f"📅 {current_time}\n📈 **총 게시글 수: {total_posts}개**",
            "color": 0x00ff00 if total_posts > 0 else 0x808080,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 모니터링 시스템 v3.0",
                "icon_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
            }
        }
        
        for category, posts in report.items():
            if not posts:
                embed["fields"].append({
                    "name": f"{get_category_emoji(category)} {category}",
                    "value": "0개",
                    "inline": True
                })
                continue
            
            top_posts = []
            for i, post in enumerate(posts[:3], 1):
                title = post['title'][:40] + "..." if len(post['title']) > 40 else post['title']
                top_posts.append(f"{i}. {title}")
            
            if len(posts) > 3:
                top_posts.append(f"... 외 {len(posts) - 3}개")
            
            embed["fields"].append({
                "name": f"{get_category_emoji(category)} {category}",
                "value": f"**{len(posts)}개**\n" + "\n".join(top_posts),
                "inline": True
            })
        
        data = {
            "embeds": [embed],
            "username": "Epic7 Daily Reporter",
            "avatar_url": "https://cdn.discordapp.com/attachments/123456789/123456789/epic7_logo.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
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
        "버그": "🐛",
        "중립": "📝",
        "기타": "📝"
    }
    return emoji_map.get(category, "📌")