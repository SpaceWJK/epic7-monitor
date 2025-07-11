import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import time
import re
import random

def get_stove_post_content(post_url):
    """스토브 게시글 내용 추출 완전 개선"""
    try:
        print(f"[DEBUG] 스토브 게시글 내용 크롤링 시작: {post_url}")
        
        # URL 유효성 검사 및 수정
        if not post_url or not post_url.startswith('http'):
            print(f"[ERROR] 유효하지 않은 URL: {post_url}")
            return "URL이 유효하지 않습니다."
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://page.onstove.com/',
            'Cache-Control': 'no-cache'
        }
        
        # 재시도 로직 추가
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(post_url, headers=headers, timeout=15)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                print(f"[WARN] 타임아웃 (시도 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return "페이지 로딩 시간 초과"
                time.sleep(2)
            except requests.exceptions.RequestException as e:
                print(f"[WARN] 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return "페이지 접근 불가"
                time.sleep(2)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 스토브 게시글 내용 선택자 (우선순위별)
        content_selectors = [
            # 메인 컨텐츠 영역
            '.s-article-content .s-article-body',
            '.s-article-content',
            '.s-board-content-text',
            
            # 게시글 본문
            '.article-content .content-body',
            '.article-content',
            '.post-content',
            
            # 뷰어 영역
            '.content-area .main-content',
            '.content-area',
            '.view-content',
            
            # 일반적인 컨텐츠
            '.board-content',
            '.main-content',
            '[class*="content"]',
            
            # 백업 선택자
            '.s-article-body',
            '.s-board-view-content',
            'main .content',
            
            # 최후 선택자
            'article',
            'main'
        ]
        
        content_text = ""
        used_selector = None
        
        # 선택자별 시도
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content_text = content_elem.get_text(strip=True)
                    if len(content_text) > 20:  # 최소 길이 조건
                        used_selector = selector
                        print(f"[DEBUG] 성공한 선택자: {selector}")
                        break
            except Exception as e:
                print(f"[DEBUG] 선택자 {selector} 실패: {e}")
                continue
        
        # 내용이 없으면 전체 페이지에서 추출 시도
        if not content_text:
            print("[DEBUG] 메인 선택자 실패, 전체 페이지 분석 시도")
            
            # 헤더, 푸터, 네비게이션 제거
            for unwanted in soup(['header', 'footer', 'nav', 'aside', 'script', 'style']):
                unwanted.decompose()
            
            # class나 id에 content가 포함된 모든 요소 검색
            content_elements = soup.find_all(['div', 'section', 'article'], 
                                           class_=re.compile(r'content|article|post|view', re.I))
            
            for elem in content_elements:
                text = elem.get_text(strip=True)
                if len(text) > len(content_text):
                    content_text = text
                    used_selector = "fallback_search"
        
        # 여전히 내용이 없으면 body 전체에서 추출
        if not content_text:
            print("[DEBUG] 폴백 검색도 실패, body 전체 텍스트 추출")
            body = soup.find('body')
            if body:
                content_text = body.get_text(separator=' ', strip=True)
                used_selector = "body_fallback"
        
        if content_text:
            # 내용 정제
            cleaned_content = clean_stove_content(content_text)
            summary = create_smart_summary(cleaned_content)
            
            print(f"[SUCCESS] 내용 추출 성공 (선택자: {used_selector})")
            print(f"[DEBUG] 원본 길이: {len(content_text)}, 정제 후: {len(cleaned_content)}")
            return summary
        else:
            print(f"[ERROR] 게시글 내용 추출 완전 실패")
            return "게시글 내용을 찾을 수 없습니다."
            
    except requests.exceptions.Timeout:
        print(f"[ERROR] 타임아웃: {post_url}")
        return "페이지 로딩 시간 초과"
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 네트워크 오류: {e}")
        return "페이지 접근 불가"
    except Exception as e:
        print(f"[ERROR] 내용 추출 중 예외: {e}")
        return "내용 분석 중 오류 발생"

def clean_stove_content(content):
    """스토브 게시글 내용 정제 개선"""
    try:
        if not content:
            return ""
        
        # 1. 기본 정제
        content = re.sub(r'\s+', ' ', content)  # 연속 공백 정리
        content = re.sub(r'[\r\n\t]+', ' ', content)  # 개행문자 제거
        
        # 2. 스토브 특화 불필요한 텍스트 제거
        stove_noise_patterns = [
            # 네비게이션 및 메뉴
            r'로그인\s*회원가입',
            r'마이페이지\s*로그아웃',
            r'홈\s*게임\s*커뮤니티',
            
            # 게시판 관련
            r'목록\s*이전\s*다음',
            r'추천\s*비추천\s*신고',
            r'댓글\s*답글\s*삭제',
            
            # 공통 UI 요소
            r'더보기\s*접기\s*펼치기',
            r'클릭\s*터치\s*스크롤',
            r'페이지\s*\d+',
            
            # 광고 및 프로모션
            r'광고\s*배너\s*이벤트',
            r'쿠키\s*설정\s*개인정보',
            
            # 스토브 특화
            r'STOVE\s*스토브',
            r'에픽세븐\s*Epic7',
            r'공지사항\s*이벤트\s*업데이트'
        ]
        
        for pattern in stove_noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 3. 의미없는 반복 제거
        content = re.sub(r'(.{1,10})\1{3,}', r'\1', content)  # 반복 패턴 제거
        
        # 4. 특수문자 정리 (한글/영문/숫자/기본 문장부호만 유지)
        content = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', ' ', content)
        
        # 5. 최종 정리
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
        
    except Exception as e:
        print(f"[ERROR] 내용 정제 중 오류: {e}")
        return content

def create_smart_summary(content):
    """지능형 게시글 요약 생성"""
    try:
        if not content:
            return "내용이 없습니다."
        
        # 내용이 충분히 짧으면 그대로 반환
        if len(content) <= 80:
            return content
        
        # 문장 단위로 분리
        sentences = re.split(r'[.!?。！？]\s*', content)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if not sentences:
            return content[:80] + "..." if len(content) > 80 else content
        
        # 핵심 키워드 기반 중요도 점수 계산
        keyword_weights = {
            # 게임 관련 핵심 키워드
            '버그': 10, '오류': 10, '에러': 10, '문제': 9, '안됨': 8,
            '안되': 8, '작동': 7, '실행': 6, '로딩': 6,
            
            # 게임 요소
            '스킬': 7, '캐릭터': 6, '장비': 6, '아레나': 6,
            '길드': 5, '원정': 5, '헌트': 5, '던전': 5,
            
            # 감정 표현
            '짜증': 6, '화남': 6, '좋아': 5, '감사': 5,
            '최고': 4, '최악': 6, '실망': 5,
            
            # 요청 및 건의
            '수정': 8, '개선': 7, '요청': 6, '건의': 5,
            '해결': 7, '해주': 6, '부탁': 5
        }
        
        # 각 문장의 중요도 계산
        sentence_scores = []
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            # 키워드 점수 합산
            for keyword, weight in keyword_weights.items():
                if keyword in sentence:
                    score += weight
            
            # 문장 길이 보너스 (적절한 길이 선호)
            if 15 <= len(sentence) <= 100:
                score += 3
            elif 10 <= len(sentence) <= 150:
                score += 1
            
            # 첫 번째/두 번째 문장 보너스
            if sentence == sentences[0]:
                score += 2
            elif len(sentences) > 1 and sentence == sentences[1]:
                score += 1
            
            sentence_scores.append((sentence, score))
        
        # 점수 기준으로 정렬하여 최고 점수 문장 선택
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        
        if sentence_scores[0][1] > 0:
            best_sentence = sentence_scores[0][0]
        else:
            best_sentence = sentences[0]  # 점수가 모두 0이면 첫 번째 문장
        
        # 길이 조정
        if len(best_sentence) > 100:
            return best_sentence[:97] + "..."
        
        return best_sentence
        
    except Exception as e:
        print(f"[ERROR] 지능형 요약 생성 중 오류: {e}")
        return content[:80] + "..." if len(content) > 80 else content

def send_bug_alert(webhook_url, bugs):
    """버그 알림 전송 (내용 추출 개선)"""
    if not webhook_url or not bugs:
        return
    
    try:
        # Discord 메시지 길이 제한
        MAX_MESSAGE_LENGTH = 1900
        
        # 여러 메시지로 나누어 전송
        current_message = "🚨 **에픽세븐 버그 탐지 알림** 🚨\n\n"
        message_count = 1
        
        for i, bug in enumerate(bugs, 1):
            try:
                # 소스 타입 결정
                source_type = get_source_type_korean(bug.get('source', 'unknown'))
                
                # 시간 포맷 변경
                formatted_time = format_timestamp(bug.get('timestamp', ''))
                
                # 게시글 내용 추출 (개선된 로직)
                content_summary = "내용 로딩 중..."
                if bug.get('source', '').startswith('stove'):
                    content_summary = get_stove_post_content(bug.get('url', ''))
                else:
                    content_summary = get_general_post_content(bug.get('url', ''), bug.get('source', ''))
                
                # 메시지 구성
                bug_info = f"""**{i}. {source_type}**
📝 **제목**: {bug['title'][:80]}{'...' if len(bug['title']) > 80 else ''}
⏰ **시간**: {formatted_time}
📄 **내용**: {content_summary}
🔗 **링크**: {bug['url']}

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

def get_general_post_content(post_url, source):
    """일반 사이트 게시글 내용 추출"""
    try:
        if not post_url:
            return "URL이 없습니다."
        
        headers = get_headers_by_source(source)
        response = requests.get(post_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_text = extract_content_by_source(soup, source)
        
        if content_text:
            cleaned_content = clean_general_content(content_text)
            return create_smart_summary(cleaned_content)
        else:
            return "내용을 찾을 수 없습니다."
            
    except Exception as e:
        print(f"[ERROR] 일반 게시글 내용 추출 실패: {e}")
        return "내용 추출 실패"

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
            # 기타 사이트 - 일반적인 선택자
            content_selectors = [
                '.content',
                '.post-content',
                '.article-content',
                '.entry-content',
                '.main-content',
                'main',
                '[class*="content"]'
            ]
        
        # 선택자별 시도
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

def clean_general_content(content):
    """일반 게시글 내용 정제"""
    try:
        if not content:
            return ""
        
        # 기본 정제
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[\r\n\t]+', ' ', content)
        
        # 불필요한 텍스트 제거
        unnecessary_phrases = [
            '로그인', '회원가입', '댓글', '추천', '비추천', '신고',
            '목록', '이전', '다음', '페이지', '공지사항', '이벤트',
            '운영정책', '이용약관', '개인정보', '쿠키', 'Cookie',
            '광고', '배너', '팝업', '알림', '설정'
        ]
        
        for phrase in unnecessary_phrases:
            content = content.replace(phrase, '')
        
        # 특수문자 정제
        content = re.sub(r'[^\w\s가-힣.,!?()[\]""'':-]', '', content)
        
        return content.strip()
        
    except Exception as e:
        print(f"[ERROR] 일반 내용 정제 중 오류: {e}")
        return content

def send_daily_report(webhook_url, report_data):
    """일일 리포트 전송 (감성 보고서 지원)"""
    if not webhook_url:
        return
        
    try:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')
        
        # 감성 보고서인지 확인
        if isinstance(report_data, dict) and 'sentiment_report' in report_data:
            send_sentiment_report(webhook_url, report_data, current_time)
        else:
            send_traditional_report(webhook_url, report_data, current_time)
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 전송 실패: {e}")

def send_sentiment_report(webhook_url, report_data, current_time):
    """감성 분석 보고서 전송"""
    try:
        sentiment_report = report_data['sentiment_report']
        analysis = report_data.get('analysis', {})
        bug_count = report_data.get('bug_count', 0)
        
        total_sentiment = sum(len(posts) for posts in sentiment_report.values())
        
        # Embed 형태로 전송
        embed = {
            "title": "📊 에픽세븐 일일 감성 동향 보고서",
            "description": f"📅 {current_time}\n📈 **감성 분석 게시글: {total_sentiment}개**",
            "color": 0x00ff00 if total_sentiment > 0 else 0x808080,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 감성 모니터링 시스템 v2.0"
            }
        }
        
        # 감성 카테고리별 필드 추가
        for category, posts in sentiment_report.items():
            emoji_map = {"긍정": "😊", "중립": "😐", "부정": "😞"}
            emoji = emoji_map.get(category, "📝")
            
            if not posts:
                embed["fields"].append({
                    "name": f"{emoji} {category}",
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
            
            percentage = (len(posts) / total_sentiment * 100) if total_sentiment > 0 else 0
            
            embed["fields"].append({
                "name": f"{emoji} {category}",
                "value": f"**{len(posts)}개** ({percentage:.1f}%)\n" + "\n".join(top_posts),
                "inline": True
            })
        
        # 분석 결과 추가
        if analysis:
            trend_emoji = {"긍정적": "📈", "부정적": "📉", "중립적": "📊", "혼재": "🔄"}.get(analysis.get('trend', ''), "📊")
            embed["fields"].append({
                "name": f"{trend_emoji} 전체 동향",
                "value": f"**{analysis.get('trend', '분석 중')}**\n{analysis.get('insight', '')}",
                "inline": False
            })
            
            if analysis.get('recommendation'):
                embed["fields"].append({
                    "name": "💡 권장사항",
                    "value": analysis['recommendation'],
                    "inline": False
                })
        
        # 버그 정보 추가
        if bug_count > 0:
            embed["fields"].append({
                "name": "🐛 버그 리포트",
                "value": f"**{bug_count}개** 버그 관련 게시글이 실시간 알림으로 전송되었습니다.",
                "inline": False
            })
        
        # Discord 전송
        data = {
            "embeds": [embed],
            "username": "Epic7 Sentiment Reporter",
            "avatar_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/1f4ca.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print("[SUCCESS] 감성 보고서 Discord 전송 성공")
        else:
            print(f"[WARN] 감성 보고서 Discord 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 감성 보고서 전송 중 오류: {e}")

def send_traditional_report(webhook_url, report, current_time):
    """기존 방식 일일 리포트 전송"""
    try:
        total_posts = sum(len(posts) for posts in report.values())
        
        embed = {
            "title": "📊 에픽세븐 일일 동향 리포트",
            "description": f"📅 {current_time}\n📈 **총 게시글 수: {total_posts}개**",
            "color": 0x00ff00 if total_posts > 0 else 0x808080,
            "fields": [],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Epic7 모니터링 시스템 v2.0"
            }
        }
        
        # 카테고리별 필드 추가
        for category, posts in report.items():
            emoji = get_category_emoji(category)
            
            if not posts:
                embed["fields"].append({
                    "name": f"{emoji} {category}",
                    "value": "0개",
                    "inline": True
                })
                continue
            
            # 상위 3개 게시글 목록
            top_posts = []
            for i, post in enumerate(posts[:3], 1):
                title = post['title'][:40] + "..." if len(post['title']) > 40 else post['title']
                top_posts.append(f"{i}. {title}")
            
            if len(posts) > 3:
                top_posts.append(f"... 외 {len(posts) - 3}개")
            
            embed["fields"].append({
                "name": f"{emoji} {category}",
                "value": f"**{len(posts)}개**\n" + "\n".join(top_posts),
                "inline": True
            })
        
        # Discord 전송
        data = {
            "embeds": [embed],
            "username": "Epic7 Daily Reporter"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print("[SUCCESS] 일일 리포트 Discord 전송 성공")
        else:
            print(f"[WARN] 일일 리포트 Discord 전송 실패: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] 일일 리포트 전송 중 오류: {e}")

def send_discord_message(webhook_url, message, count=1):
    """Discord 메시지 전송"""
    try:
        data = {
            "content": message,
            "username": "Epic7 Bug Monitor",
            "avatar_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/1f41b.png"
        }
        
        response = requests.post(webhook_url, json=data, timeout=15)
        if response.status_code == 204:
            print(f"[SUCCESS] Discord 알림 {count} 전송 성공")
        else:
            print(f"[WARN] Discord 알림 {count} 전송 실패: {response.status_code}")
            
        # Discord Rate Limit 방지
        time.sleep(1.5)
        
    except Exception as e:
        print(f"[ERROR] Discord 메시지 전송 중 오류: {e}")

def get_source_type_korean(source):
    """소스 타입을 한국어로 변환"""
    source_map = {
        "stove_bug": "🏪 스토브 버그 게시판",
        "stove_general": "🏪 스토브 자유 게시판",
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
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        else:
            return datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"[WARN] 시간 포맷 변환 실패: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M')

def get_category_emoji(category):
    """카테고리별 이모지 반환"""
    emoji_map = {
        "긍정": "😊",
        "부정": "😞", 
        "버그": "🐛",
        "기타": "📝",
        "중립": "😐",
        "질문": "❓",
        "정보": "ℹ️",
        "공략": "📋",
        "창작": "🎨",
        "이벤트": "🎉"
    }
    return emoji_map.get(category, "📌")

# 테스트 함수
def test_stove_content_extraction():
    """스토브 내용 추출 테스트"""
    test_url = "https://page.onstove.com/epicseven/kr/view/10867127"
    print(f"테스트 URL: {test_url}")
    
    result = get_stove_post_content(test_url)
    print(f"추출 결과: {result}")
    
    return result

if __name__ == "__main__":
    test_stove_content_extraction()