# monitor_bugs.py - Epic7 모니터링 시스템 메인 컨트롤러
# Import 에러 해결, 실제 크롤러 함수와 매칭, 에러 핸들링 강화

import json
import os
import sys
import argparse
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import traceback

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('monitor_bugs.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

try:
    # 실제 존재하는 크롤러 함수들만 import
    from crawler import (
        fetch_stove_bug_board,
        fetch_stove_general_board,
        fetch_ruliweb_epic7_board,
        fetch_stove_global_bug_board,
        fetch_stove_global_general_board,
        fetch_reddit_epic7_board,
        get_chrome_driver,
        load_crawled_links,
        save_crawled_links,
        check_discord_webhooks
    )
    logger.info("크롤러 모듈 import 성공")
except ImportError as e:
    logger.error(f"크롤러 모듈 import 실패: {e}")
    sys.exit(1)

try:
    from classifier import classify_post, is_bug_post
    logger.info("분류기 모듈 import 성공")
except ImportError as e:
    logger.error(f"분류기 모듈 import 실패: {e}")
    sys.exit(1)

try:
    from notifier import send_bug_alert, send_system_alert
    logger.info("알림 모듈 import 성공")
except ImportError as e:
    logger.error(f"알림 모듈 import 실패: {e}")
    sys.exit(1)

# 번역 기능 (선택적 import)
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_ENABLED = True
    logger.info("번역 모듈 import 성공")
except ImportError as e:
    logger.warning(f"번역 모듈 import 실패: {e}")
    TRANSLATION_ENABLED = False

class MonitoringSystem:
    """Epic7 모니터링 시스템 메인 컨트롤러"""
    
    def __init__(self, mode: str = "korean", debug: bool = False, test: bool = False):
        self.mode = mode
        self.debug = debug
        self.test = test
        self.webhooks = check_discord_webhooks()
        self.translator = None
        
        # 번역기 초기화
        if TRANSLATION_ENABLED:
            try:
                self.translator = GoogleTranslator(source='auto', target='ko')
                logger.info("번역기 초기화 성공")
            except Exception as e:
                logger.warning(f"번역기 초기화 실패: {e}")
                self.translator = None
        
        # 크롤러 함수 매핑
        self.korean_crawlers = {
            'stove_bug': fetch_stove_bug_board,
            'stove_general': fetch_stove_general_board,
            'ruliweb_epic7': fetch_ruliweb_epic7_board
        }
        
        self.global_crawlers = {
            'stove_global_bug': fetch_stove_global_bug_board,
            'stove_global_general': fetch_stove_global_general_board,
            'reddit_epic7': fetch_reddit_epic7_board
        }
        
        logger.info(f"모니터링 시스템 초기화 완료: mode={mode}, debug={debug}, test={test}")
    
    def translate_text(self, text: str, source: str = 'auto', target: str = 'ko') -> str:
        """텍스트 번역 (영어→한국어)"""
        if not self.translator or not text:
            return text
        
        try:
            # 한국어 텍스트는 번역하지 않음
            if self.is_korean_text(text):
                return text
            
            # 영어 텍스트만 한국어로 번역
            translated = self.translator.translate(text)
            logger.debug(f"번역 완료: {text[:50]}... -> {translated[:50]}...")
            return translated
            
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
            return text
    
    def is_korean_text(self, text: str) -> bool:
        """한국어 텍스트 여부 확인"""
        if not text:
            return False
        
        korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7a3')
        return korean_chars > len(text) * 0.3
    
    def crawl_korean_sites(self) -> List[Dict]:
        """한국 사이트 크롤링"""
        all_posts = []
        
        for site_name, crawler_func in self.korean_crawlers.items():
            try:
                logger.info(f"크롤링 시작: {site_name}")
                start_time = time.time()
                
                posts = crawler_func()
                
                elapsed = time.time() - start_time
                logger.info(f"크롤링 완료: {site_name} ({len(posts)}개 게시글, {elapsed:.1f}초)")
                
                all_posts.extend(posts)
                
            except Exception as e:
                logger.error(f"크롤링 실패: {site_name} - {e}")
                if self.debug:
                    logger.error(traceback.format_exc())
                continue
        
        return all_posts
    
    def crawl_global_sites(self) -> List[Dict]:
        """글로벌 사이트 크롤링"""
        all_posts = []
        
        for site_name, crawler_func in self.global_crawlers.items():
            try:
                logger.info(f"크롤링 시작: {site_name}")
                start_time = time.time()
                
                posts = crawler_func()
                
                elapsed = time.time() - start_time
                logger.info(f"크롤링 완료: {site_name} ({len(posts)}개 게시글, {elapsed:.1f}초)")
                
                # 글로벌 사이트 게시글 번역
                if self.translator:
                    for post in posts:
                        original_title = post.get('title', '')
                        original_content = post.get('content', '')
                        
                        # 제목 번역
                        if original_title:
                            post['title_ko'] = self.translate_text(original_title)
                        
                        # 내용 번역
                        if original_content:
                            post['content_ko'] = self.translate_text(original_content)
                
                all_posts.extend(posts)
                
            except Exception as e:
                logger.error(f"크롤링 실패: {site_name} - {e}")
                if self.debug:
                    logger.error(traceback.format_exc())
                continue
        
        return all_posts
    
    def crawl_all_sites(self) -> List[Dict]:
        """모든 사이트 크롤링"""
        all_posts = []
        
        # 한국 사이트 크롤링
        korean_posts = self.crawl_korean_sites()
        all_posts.extend(korean_posts)
        
        # 글로벌 사이트 크롤링
        global_posts = self.crawl_global_sites()
        all_posts.extend(global_posts)
        
        return all_posts
    
    def classify_posts(self, posts: List[Dict]) -> Dict[str, List[Dict]]:
        """게시글 분류"""
        classified = {
            'bug': [],
            'general': []
        }
        
        for post in posts:
            try:
                title = post.get('title', '')
                
                # 버그 게시글 분류
                if is_bug_post(title):
                    classified['bug'].append(post)
                else:
                    classified['general'].append(post)
                
            except Exception as e:
                logger.warning(f"게시글 분류 실패: {e}")
                classified['general'].append(post)
        
        return classified
    
    def send_bug_notifications(self, bug_posts: List[Dict]) -> bool:
        """버그 알림 전송"""
        if not bug_posts:
            return True
        
        try:
            # 번역된 제목/내용 사용
            for post in bug_posts:
                if post.get('title_ko'):
                    post['display_title'] = f"{post['title_ko']} (원문: {post['title']})"
                else:
                    post['display_title'] = post['title']
                
                if post.get('content_ko'):
                    post['display_content'] = f"{post['content_ko']} (원문: {post['content']})"
                else:
                    post['display_content'] = post['content']
            
            success = send_bug_alert(bug_posts, self.mode)
            
            if success:
                logger.info(f"버그 알림 전송 성공: {len(bug_posts)}개 게시글")
            else:
                logger.error("버그 알림 전송 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"버그 알림 전송 중 오류: {e}")
            return False
    
    def send_system_notification(self, message: str, level: str = "info") -> bool:
        """시스템 알림 전송"""
        try:
            return send_system_alert(
                alert_type="모니터링 시스템",
                message=message,
                level=level,
                mode=self.mode
            )
        except Exception as e:
            logger.error(f"시스템 알림 전송 실패: {e}")
            return False
    
    def run(self) -> bool:
        """메인 실행 함수"""
        start_time = time.time()
        
        try:
            logger.info("=" * 50)
            logger.info(f"Epic7 모니터링 시스템 시작")
            logger.info(f"모드: {self.mode}")
            logger.info(f"디버그: {self.debug}")
            logger.info(f"테스트: {self.test}")
            logger.info("=" * 50)
            
            # 크롤링 실행
            all_posts = []
            
            if self.mode == "korean":
                all_posts = self.crawl_korean_sites()
            elif self.mode == "global":
                all_posts = self.crawl_global_sites()
            elif self.mode == "all":
                all_posts = self.crawl_all_sites()
            else:
                logger.error(f"지원하지 않는 모드: {self.mode}")
                return False
            
            # 게시글 분류
            classified = self.classify_posts(all_posts)
            
            # 결과 로깅
            logger.info(f"크롤링 완료: 총 {len(all_posts)}개 게시글")
            logger.info(f"버그 게시글: {len(classified['bug'])}개")
            logger.info(f"일반 게시글: {len(classified['general'])}개")
            
            # 버그 알림 전송
            if classified['bug']:
                self.send_bug_notifications(classified['bug'])
            
            # 완료 알림
            elapsed = time.time() - start_time
            completion_message = f"모니터링 완료: {len(all_posts)}개 게시글 처리 ({elapsed:.1f}초)"
            
            if not self.test:
                self.send_system_notification(completion_message, "success")
            
            logger.info(completion_message)
            logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            logger.error(f"모니터링 실행 중 오류: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            
            # 에러 알림
            error_message = f"모니터링 실행 실패: {str(e)}"
            if not self.test:
                self.send_system_notification(error_message, "error")
            
            return False

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Epic7 모니터링 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['korean', 'global', 'all'],
        default='korean',
        help='모니터링 모드 (기본값: korean)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 모드 활성화'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='테스트 모드 활성화 (알림 전송 안함)'
    )
    
    return parser.parse_args()

def main():
    """메인 실행 함수"""
    try:
        # 인자 파싱
        args = parse_arguments()
        
        # 모니터링 시스템 초기화
        monitor = MonitoringSystem(
            mode=args.mode,
            debug=args.debug,
            test=args.test
        )
        
        # 실행
        success = monitor.run()
        
        # 종료 코드 반환
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        sys.exit(0)
    except Exception as e:
        logger.error(f"치명적 오류: {e}")
        if '--debug' in sys.argv:
            logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()